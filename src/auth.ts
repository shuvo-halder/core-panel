import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-key-change-in-production';

export interface AuthRequest extends Request {
  user?: any;
}

/**
 * Middleware to verify JWT tokens
 */
export function requireAuth(req: AuthRequest, res: Response, next: NextFunction) {
  const authHeader = req.headers.authorization;
  
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ success: false, error: 'Unauthorized: Missing or invalid token' });
  }

  const token = authHeader.split(' ')[1];

  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    req.user = decoded;
    next();
  } catch (err) {
    return res.status(401).json({ success: false, error: 'Unauthorized: Expired or invalid token' });
  }
}

/**
 * Generate a new JWT token
 */
export function generateToken(payload: object, expiresIn: string = '24h'): string {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: expiresIn as any });
}
