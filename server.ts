import express from 'express';
import path from 'path';
import cookieParser from 'cookie-parser';
import rateLimit from 'express-rate-limit';
import { createServer as createViteServer } from 'vite';

import { initDB, db } from './src/lib/db';
import { verifyPassword, generateToken, setAuthCookie, clearAuthCookie, requireAuth, AuthRequest } from './src/lib/auth';
import { runCommand } from './src/lib/runner';

// Initialize Phase 1 Database
initDB();

async function startServer() {
  const app = express();
  // PORT 3000 is required by the reverse proxy infrastructure
  const PORT = 3000;

  // Middlewares
  app.use(express.json());
  app.use(cookieParser());

  // Rate Limiting (Phase 1 constraint)
  const loginLimiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 5, // Limit each IP to 5 login requests per window
    message: { success: false, error: 'Too many login attempts, please try again after 15 minutes' }
  });

  // --- API Routes (Phase 1) ---

  // Auth: Login
  app.post('/api/auth/login', loginLimiter, (req, res) => {
    const { username, password } = req.body;
    if (!username || !password) {
      return res.status(400).json({ success: false, error: 'Username and password required' });
    }

    const stmt = db.prepare('SELECT id, username, password_hash FROM users WHERE username = ?');
    const user = stmt.get(username) as any;

    if (!user || !verifyPassword(password, user.password_hash)) {
      return res.status(401).json({ success: false, error: 'Invalid credentials' });
    }

    // Log the successful login action
    const logStmt = db.prepare('INSERT INTO audit_logs (user_id, action, ip_address) VALUES (?, ?, ?)');
    logStmt.run(user.id, 'login_success', req.ip || 'unknown');

    const token = generateToken(user.id, user.username);
    setAuthCookie(res, token);
    
    res.json({ success: true, user: { id: user.id, username: user.username } });
  });

  // Auth: Logout
  app.post('/api/auth/logout', (req, res) => {
    clearAuthCookie(res);
    res.json({ success: true });
  });

  // Auth: Verify Session
  app.get('/api/auth/me', requireAuth, (req: AuthRequest, res) => {
    res.json({ success: true, user: req.user });
  });

  // System: Status (Requires Auth)
  app.get('/api/system/status', requireAuth, async (req: AuthRequest, res) => {
    try {
      // Secure Command Execution via Strict Whitelist Abstraction
      const uptimeResult = await runCommand('uptime', ['-p']);
      const memoryResult = await runCommand('free', ['-m']);
      const osResult = await runCommand('uname', ['-r']);
      
      const memLines = memoryResult.stdout.split('\n');
      const memLine = memLines.length > 1 ? memLines[1] : memLines[0];

      res.json({
        success: true,
        data: {
          uptime: uptimeResult.stdout,
          memory: memLine,
          kernel: osResult.stdout
        }
      });
    } catch (error: any) {
      // Fallback if system commands fail (e.g. running locally without Linux utils)
      console.error("System command failed, returning fallback metrics.", error);
      const mins = Math.floor(process.uptime() / 60);
      const mem = process.memoryUsage();
      const usedMb = Math.round(mem.heapUsed / (1024 * 1024));
      const totalMb = Math.round(mem.heapTotal / (1024 * 1024));

      res.json({
        success: true,
        data: {
          uptime: `up ${mins} minutes (fallback)`,
          memory: `Mem: ${totalMb} ${usedMb} 0 0 0 0`,
          kernel: 'Unknown (fallback)'
        }
      });
    }
  });

  // Health check for platform
  app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', uptime: process.uptime() });
  });

  // --- Frontend Delivery ---
  
  // Vite middleware for development
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    // Production delivery (Simulating compiled assets embedded into binary concept)
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`VPS Control Panel API Daemon running on port ${PORT}`);
  });
}

startServer().catch(err => {
  console.error("Failed to start server daemon:", err);
  process.exit(1);
});
