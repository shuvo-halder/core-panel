import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

// Ensure data directory exists
const dataDir = path.join(process.cwd(), 'data');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

export const db = new Database(path.join(dataDir, 'panel.db'));

// Initialize Database Schema (Phase 1)
export function initDB() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'admin',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS settings (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      action TEXT NOT NULL,
      details TEXT,
      ip_address TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
  `);

  // Seed default admin if no users exist
  const countStmt = db.prepare('SELECT COUNT(*) as count FROM users');
  const count = (countStmt.get() as any).count;

  if (count === 0) {
    // Note: In production, password should be set via a one-time setup screen.
    // We are seeding 'admin' / 'admin123' for Phase 1 testing.
    const { hashPassword } = require('./auth');
    const hash = hashPassword('admin123');
    const insertStmt = db.prepare('INSERT INTO users (username, password_hash) VALUES (?, ?)');
    insertStmt.run('admin', hash);
    console.log("Default admin user created (admin / admin123)");
  }
}
