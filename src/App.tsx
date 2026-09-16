import React, { useEffect, useState } from 'react';
import { LogIn, Server, Settings, Terminal, Shield, LogOut, HardDrive, Cpu, Activity, Clock } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [user, setUser] = useState<any>(null);
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  // Login State
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');

  // Initial Auth Check
  useEffect(() => {
    fetch('/api/auth/me')
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setIsAuthenticated(true);
          setUser(data.user);
        } else {
          setIsAuthenticated(false);
        }
      })
      .catch(() => setIsAuthenticated(false))
      .finally(() => setLoading(false));
  }, []);

  // Fetch System Status when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      const fetchStatus = () => {
        fetch('/api/system/status')
          .then(res => res.json())
          .then(data => {
            if (data.success) setSystemStatus(data.data);
          })
          .catch(err => console.error("Failed to fetch status", err));
      };
      fetchStatus();
      const interval = setInterval(fetchStatus, 15000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (data.success) {
        setIsAuthenticated(true);
        setUser(data.user);
      } else {
        setLoginError(data.error || 'Login failed');
      }
    } catch (err) {
      setLoginError('Network error occurred.');
    }
  };

  const handleLogout = async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    setIsAuthenticated(false);
    setUser(null);
  };

  if (loading) {
    return <div className="min-h-screen bg-[#E4E3E0] flex items-center justify-center font-mono text-sm opacity-50">Initializing Secure Container...</div>;
  }

  // --- Phase 1: Authentication View ---
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#E4E3E0] flex flex-col items-center justify-center p-4">
        <div className="w-full max-w-sm border border-[#141414] bg-white/50 p-8 shadow-sm">
          <div className="flex items-center gap-3 mb-8 pb-4 border-b border-[#141414]">
            <Server className="w-6 h-6" />
            <h1 className="font-serif italic font-bold text-xl tracking-wide">Core Panel</h1>
          </div>
          
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-[10px] uppercase font-bold tracking-wider mb-1 opacity-70">Username</label>
              <input 
                type="text" 
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full border border-[#141414] bg-transparent p-2 text-sm font-mono focus:outline-none focus:bg-[#141414] focus:text-[#E4E3E0] transition-colors"
                autoComplete="username"
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase font-bold tracking-wider mb-1 opacity-70">Password</label>
              <input 
                type="password" 
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full border border-[#141414] bg-transparent p-2 text-sm font-mono focus:outline-none focus:bg-[#141414] focus:text-[#E4E3E0] transition-colors"
                autoComplete="current-password"
              />
            </div>
            
            {loginError && (
              <div className="text-red-700 text-xs font-mono font-bold bg-red-100 border border-red-700 p-2">
                {loginError}
              </div>
            )}
            
            <button 
              type="submit"
              className="w-full mt-4 border border-[#141414] bg-[#141414] text-[#E4E3E0] p-2 text-xs uppercase font-bold tracking-widest hover:bg-transparent hover:text-[#141414] transition-colors"
            >
              Authenticate
            </button>
          </form>
          
          <div className="mt-8 text-center text-[10px] font-mono opacity-40">
            Phase 1 &mdash; Initial Setup (admin / admin123)
          </div>
        </div>
      </div>
    );
  }

  // --- Phase 1: Dashboard Structure ---
  return (
    <div className="h-screen bg-[#E4E3E0] text-[#141414] font-sans flex flex-col md:flex-row overflow-hidden">
      
      {/* Sidebar Navigation */}
      <aside className="w-full md:w-64 border-b md:border-b-0 md:border-r border-[#141414] bg-[#E4E3E0] flex flex-col shrink-0">
        <div className="p-6 border-b border-[#141414] flex items-center justify-between">
          <div className="flex flex-col">
            <span className="font-serif italic font-bold text-xl tracking-wide">Core Panel</span>
            <span className="font-mono text-[10px] uppercase opacity-60 mt-1 flex items-center gap-1">
              <Shield className="w-3 h-3" /> System root
            </span>
          </div>
        </div>
        
        <nav className="flex-1 overflow-y-auto py-4 flex flex-col">
          {[
            { id: 'dashboard', icon: Activity, label: 'System Overview' },
            { id: 'terminal', icon: Terminal, label: 'Secure Shell (WIP)' },
            { id: 'settings', icon: Settings, label: 'Configuration' }
          ].map(item => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`sidebar-link flex items-center gap-3 px-6 py-3 text-sm font-bold uppercase tracking-wider text-left ${activeTab === item.id ? 'active' : ''}`}
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </button>
          ))}
        </nav>
        
        <div className="p-4 border-t border-[#141414]">
          <div className="flex items-center justify-between mb-4 px-2">
            <span className="font-mono text-[10px] opacity-70">Logged in as <b className="uppercase">{user?.username}</b></span>
          </div>
          <button onClick={handleLogout} className="w-full flex items-center justify-center gap-2 border border-[#141414] p-2 text-xs uppercase font-bold hover:bg-[#141414] hover:text-[#E4E3E0] transition-colors">
            <LogOut className="w-3 h-3" /> Terminate Session
          </button>
        </div>
      </aside>
      
      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 bg-white/40">
        
        {/* Header Bar */}
        <header className="h-14 border-b border-[#141414] flex items-center justify-between px-6 shrink-0 bg-[#E4E3E0]">
          <div className="font-mono text-xs uppercase opacity-70 font-bold flex items-center gap-4">
            <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {systemStatus?.uptime || 'Loading...'}</span>
            <span className="hidden md:inline-block">| OS: {systemStatus?.kernel || 'Unknown'}</span>
          </div>
          <div className="flex items-center gap-2">
             <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
             <span className="font-mono text-[10px] uppercase font-bold tracking-widest">Daemon Active</span>
          </div>
        </header>

        {/* Content Pane */}
        <div className="flex-1 overflow-auto p-4 md:p-8">
          {activeTab === 'dashboard' && (
            <div className="max-w-5xl mx-auto space-y-8">
              <div>
                <h2 className="font-serif italic text-2xl font-bold border-b border-[#141414] pb-2 mb-6">Phase 1: Foundation Overview</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  
                  {/* Metric Card */}
                  <div className="border border-[#141414] p-6 bg-white/60">
                    <div className="flex items-center gap-2 col-header mb-4 text-[#141414]">
                      <Cpu className="w-4 h-4" /> System Memory
                    </div>
                    <div className="data-value text-2xl break-all">
                      {systemStatus?.memory ? systemStatus.memory.match(/\d+/g)?.[0] : "---"}
                      <span className="text-sm ml-1 opacity-60">MB Used</span>
                    </div>
                  </div>

                  <div className="border border-[#141414] p-6 bg-white/60">
                    <div className="flex items-center gap-2 col-header mb-4 text-[#141414]">
                      <HardDrive className="w-4 h-4" /> SQLite Engine
                    </div>
                    <div className="data-value text-2xl">
                      Operational
                    </div>
                    <div className="text-[10px] mt-2 opacity-60 font-mono uppercase">Panel.db via abstract layer</div>
                  </div>
                  
                  <div className="border border-[#141414] p-6 bg-white/60">
                    <div className="flex items-center gap-2 col-header mb-4 text-[#141414]">
                      <Shield className="w-4 h-4" /> Security Context
                    </div>
                    <div className="data-value text-2xl text-green-700">
                      Strict Mode
                    </div>
                    <div className="text-[10px] mt-2 opacity-60 font-mono uppercase">JWT Auth + Whitelist Runner</div>
                  </div>
                  
                </div>
              </div>
              
              <div className="border border-[#141414] bg-white/60">
                <div className="p-4 border-b border-[#141414] bg-[#E4E3E0] col-header">
                  Architecture Readiness
                </div>
                <div className="p-6 font-mono text-sm space-y-4 opacity-80 leading-relaxed">
                  <p>&gt; Modular directory structure initialized.</p>
                  <p>&gt; JWT Authentication middleware injected and verified via HttpOnly cookies.</p>
                  <p>&gt; <code>CommandRunner</code> strict-whitelist activated. Zero-concatenation system calls enforcing.</p>
                  <p>&gt; Single-port asynchronous daemon listening.</p>
                  <p className="pt-4 border-t border-[#141414]/20">&gt; Proceeding to Phase 2 (Metrics Engine & WebSSH)...</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'terminal' && (
            <div className="h-full border border-[#141414] bg-[#141414] text-green-500 font-mono text-sm p-4 flex flex-col">
              <div className="opacity-50 text-xs mb-4 border-b border-white/20 pb-2">SECURE SHELL INITIALIZATION [PENDING PHASE 2]</div>
              <div className="flex-1 flex items-end">
                <span>[root@core-panel ~]# <span className="animate-pulse w-2 h-4 bg-green-500 inline-block align-middle ml-1"></span></span>
              </div>
            </div>
          )}
          
          {activeTab === 'settings' && (
            <div className="flex items-center justify-center h-full border border-[#141414] bg-white/30 text-sm font-mono font-bold uppercase opacity-50">
              Module Under Construction
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
