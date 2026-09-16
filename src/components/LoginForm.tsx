import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Shield, KeyRound, User as UserIcon, AlertCircle, Loader2 } from 'lucide-react';

export const LoginForm: React.FC = () => {
  const { login, error } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setLocalError('Please provide both username and password.');
      return;
    }
    setLocalError(null);
    setIsSubmitting(true);
    try {
      await login(username.trim(), password);
    } catch {
      // Error is set in AuthContext
    } finally {
      setIsSubmitting(false);
    }
  };

  const displayError = localError || error;

  return (
    <div className="min-h-screen bg-neutral-900 text-neutral-100 flex flex-col justify-center items-center px-4 py-12">
      <div className="w-full max-w-md bg-neutral-800/90 border border-neutral-700/80 rounded-xl p-8 shadow-2xl backdrop-blur-sm">
        
        {/* Header */}
        <div className="flex items-center space-x-3 mb-6 pb-4 border-b border-neutral-700">
          <div className="p-2.5 bg-neutral-700 rounded-lg text-neutral-100">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-white">CorePanel</h1>
            <p className="text-xs text-neutral-400">Linux Control Plane &bull; Authentication</p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {displayError && (
            <div className="flex items-start space-x-2.5 p-3 rounded-lg bg-red-950/60 border border-red-800/80 text-red-200 text-sm">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-red-400" />
              <div className="text-xs leading-relaxed">{displayError}</div>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-neutral-300 mb-1.5 uppercase tracking-wider">
              Username
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-400">
                <UserIcon className="w-4 h-4" />
              </div>
              <input
                id="login-username-input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isSubmitting}
                className="w-full pl-9 pr-3 py-2.5 bg-neutral-900/90 border border-neutral-700 rounded-lg text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-neutral-400 focus:border-transparent transition-all disabled:opacity-50"
                placeholder="Enter your username"
                autoComplete="username"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-neutral-300 mb-1.5 uppercase tracking-wider">
              Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-400">
                <KeyRound className="w-4 h-4" />
              </div>
              <input
                id="login-password-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                className="w-full pl-9 pr-3 py-2.5 bg-neutral-900/90 border border-neutral-700 rounded-lg text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-neutral-400 focus:border-transparent transition-all disabled:opacity-50"
                placeholder="••••••••"
                autoComplete="current-password"
                required
              />
            </div>
          </div>

          <button
            id="login-submit-btn"
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-2 py-2.5 px-4 bg-neutral-100 hover:bg-white text-neutral-900 font-medium text-sm rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-neutral-400 transition-all flex items-center justify-center space-x-2 disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Authenticating...</span>
              </>
            ) : (
              <span>Sign In</span>
            )}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-neutral-700/60 text-center text-xs text-neutral-500">
          Argon2id Hash &bull; HttpOnly Session Cookie &bull; RBAC Protected
        </div>
      </div>
    </div>
  );
};
