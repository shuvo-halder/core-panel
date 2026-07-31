import express from 'express';
import path from 'path';
import { createServer as createViteServer } from 'vite';
import { runSafeCommand } from './src/syscmd';

async function startServer() {
  const app = express();
  // We must bind to port 3000 in this environment
  const PORT = process.env.PORT || 3000;

  app.use(express.json());

  // ==========================================
  // API ROUTES (Backend setup)
  // ==========================================
  
  // Health check endpoint
  app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', uptime: process.uptime() });
  });

  // Example: Secure System Status Endpoint
  app.get('/api/system/status', async (req, res) => {
    try {
      // Safely run 'uptime -p' to get human-readable uptime
      const uptimeStr = await runSafeCommand('uptime', ['-p']);
      // Safely run 'free -m' to get memory usage
      const memoryStr = await runSafeCommand('free', ['-m']);
      
      res.json({
        success: true,
        data: {
          uptime: uptimeStr,
          memory: memoryStr.split('\n')[1] // Just a quick parse of the Mem line for demonstration
        }
      });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  });

  // ==========================================
  // VITE MIDDLEWARE (Frontend integration)
  // ==========================================
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  // Bind to 0.0.0.0 to ensure external accessibility in containerized environments
  app.listen(PORT as number, '0.0.0.0', () => {
    console.log(`[Server] VPS Control Panel running on http://0.0.0.0:${PORT}`);
  });
}

startServer().catch(console.error);
