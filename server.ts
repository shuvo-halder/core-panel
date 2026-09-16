import express from 'express';
import path from 'path';
import { createServer as createViteServer } from 'vite';
import { runSafeCommand } from './src/syscmd';

async function startServer() {
  const app = express();
  // PORT 3000 is required by the reverse proxy infrastructure
  const PORT = 3000;

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
      let uptimeStr = '';
      try {
        uptimeStr = await runSafeCommand('uptime', ['-p']);
      } catch {
        try {
          uptimeStr = await runSafeCommand('uptime');
        } catch {
          const mins = Math.floor(process.uptime() / 60);
          uptimeStr = `up ${mins} minutes`;
        }
      }

      let memoryStr = '';
      try {
        memoryStr = await runSafeCommand('free', ['-m']);
      } catch {
        const mem = process.memoryUsage();
        const totalMb = Math.round(mem.heapTotal / (1024 * 1024));
        const usedMb = Math.round(mem.heapUsed / (1024 * 1024));
        memoryStr = `Mem: ${totalMb} ${usedMb} 0 0 0 0`;
      }

      const memLines = memoryStr.split('\n');
      const memLine = memLines.length > 1 ? memLines[1] : memLines[0];
      
      res.json({
        success: true,
        data: {
          uptime: uptimeStr,
          memory: memLine
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
