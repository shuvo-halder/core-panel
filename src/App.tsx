import { useEffect, useState } from 'react';

export default function App() {
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [activeTab, setActiveTab] = useState('dashboard');

  useEffect(() => {
    // Fetch initial system status
    fetch('/api/system/status')
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setSystemStatus(data.data);
        }
      })
      .catch(err => console.error("Failed to fetch status", err));
  }, []);

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return (
          <>
            <section className="grid grid-cols-2 lg:grid-cols-4 gap-0 border border-[#141414] shrink-0">
              <div className="p-6 border-r border-[#141414] border-b lg:border-b-0">
                <div className="col-header mb-4">CPU Usage</div>
                <div className="data-value text-3xl">12.4<span className="text-sm">%</span></div>
                <div className="mt-2 h-1 bg-[#D1D0CC] w-full relative">
                  <div className="absolute top-0 left-0 h-full bg-[#141414]" style={{ width: '12.4%' }}></div>
                </div>
              </div>
              <div className="p-6 lg:border-r border-[#141414] border-b lg:border-b-0">
                <div className="col-header mb-4">RAM Memory</div>
                <div className="data-value text-3xl">{systemStatus?.memory ? systemStatus.memory.match(/\d+/g)?.[0] : "4.2"}<span className="text-sm">MB</span></div>
                <div className="mt-2 h-1 bg-[#D1D0CC] w-full relative">
                  <div className="absolute top-0 left-0 h-full bg-[#141414]" style={{ width: '26%' }}></div>
                </div>
              </div>
              <div className="p-6 border-r border-[#141414]">
                <div className="col-header mb-4">Disk Storage</div>
                <div className="data-value text-3xl">42.1<span className="text-sm">%</span></div>
                <div className="mt-2 h-1 bg-[#D1D0CC] w-full relative">
                  <div className="absolute top-0 left-0 h-full bg-[#141414]" style={{ width: '42.1%' }}></div>
                </div>
              </div>
              <div className="p-6">
                <div className="col-header mb-4">Net I/O</div>
                <div className="data-value text-xl">↑ 1.2 MB/s</div>
                <div className="data-value text-xl">↓ 8.4 MB/s</div>
              </div>
            </section>
            
            <section className="flex-1 flex flex-col min-h-0 min-h-[300px]">
              <div className="grid grid-cols-[120px_1.5fr_1fr_1fr_80px] gap-0 px-4 mb-2 shrink-0">
                <div className="col-header">Service</div>
                <div className="col-header">Status</div>
                <div className="col-header">Process ID</div>
                <div className="col-header">Resource usage</div>
                <div className="col-header text-right">Actions</div>
              </div>
              <div className="border border-[#141414] flex-1 overflow-y-auto bg-white/30">
                <div className="data-row">
                  <span className="data-value">nginx</span>
                  <span>
                    <span className="status-dot bg-green-600"></span>
                    <span className="text-[10px] uppercase font-bold">Running</span>
                  </span>
                  <span className="data-value">1022, 1023</span>
                  <span className="data-value">0.2% CPU / 45MB</span>
                  <span className="text-right">...</span>
                </div>
                <div className="data-row">
                  <span className="data-value">mariadb</span>
                  <span>
                    <span className="status-dot bg-green-600"></span>
                    <span className="text-[10px] uppercase font-bold">Running</span>
                  </span>
                  <span className="data-value">4421</span>
                  <span className="data-value">1.1% CPU / 842MB</span>
                  <span className="text-right">...</span>
                </div>
                <div className="data-row">
                  <span className="data-value">php-fpm8.2</span>
                  <span>
                    <span className="status-dot bg-green-600"></span>
                    <span className="text-[10px] uppercase font-bold">Running</span>
                  </span>
                  <span className="data-value">8901, 8902</span>
                  <span className="data-value">0.5% CPU / 120MB</span>
                  <span className="text-right">...</span>
                </div>
                <div className="data-row">
                  <span className="data-value">docker</span>
                  <span>
                    <span className="status-dot bg-red-600"></span>
                    <span className="text-[10px] uppercase font-bold">Stopped</span>
                  </span>
                  <span className="data-value">-</span>
                  <span className="data-value">0% CPU / 0MB</span>
                  <span className="text-right">...</span>
                </div>
              </div>
            </section>
          </>
        );
      case 'file-manager':
        return (
          <section className="flex-1 flex flex-col border border-[#141414] bg-white/30">
            <div className="p-4 border-b border-[#141414] flex justify-between items-center bg-[#E4E3E0]">
              <div className="font-mono text-sm font-bold">/var/www/html</div>
              <div className="flex gap-2">
                <button className="border border-[#141414] px-3 py-1 text-[10px] font-bold uppercase hover:bg-[#141414] hover:text-[#E4E3E0] transition-colors cursor-pointer">New Folder</button>
                <button className="border border-[#141414] px-3 py-1 text-[10px] font-bold uppercase hover:bg-[#141414] hover:text-[#E4E3E0] transition-colors cursor-pointer">Upload</button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto">
              <div className="grid grid-cols-[auto_1fr_auto_auto] gap-4 p-2 border-b border-[#141414]/20 hover:bg-[#141414] hover:text-[#E4E3E0] cursor-pointer">
                <span className="font-mono">📁</span>
                <span className="font-mono font-bold text-sm">public</span>
                <span className="font-mono text-xs opacity-60">4 KB</span>
                <span className="font-mono text-xs opacity-60">Oct 24, 10:23</span>
              </div>
              <div className="grid grid-cols-[auto_1fr_auto_auto] gap-4 p-2 border-b border-[#141414]/20 hover:bg-[#141414] hover:text-[#E4E3E0] cursor-pointer">
                <span className="font-mono">📄</span>
                <span className="font-mono font-bold text-sm">index.php</span>
                <span className="font-mono text-xs opacity-60">1.2 KB</span>
                <span className="font-mono text-xs opacity-60">Oct 24, 11:45</span>
              </div>
              <div className="grid grid-cols-[auto_1fr_auto_auto] gap-4 p-2 border-b border-[#141414]/20 hover:bg-[#141414] hover:text-[#E4E3E0] cursor-pointer">
                <span className="font-mono">📄</span>
                <span className="font-mono font-bold text-sm">wp-config.php</span>
                <span className="font-mono text-xs opacity-60">3.4 KB</span>
                <span className="font-mono text-xs opacity-60">Oct 23, 09:12</span>
              </div>
            </div>
          </section>
        );
      case 'web-server':
        return (
          <section className="flex-1 flex flex-col border border-[#141414] bg-white/30 p-6">
            <h2 className="text-lg font-bold font-serif italic mb-6 border-b border-[#141414] pb-2">Virtual Hosts (Nginx)</h2>
            <div className="grid gap-4">
              <div className="border border-[#141414] p-4 flex justify-between items-center bg-[#E4E3E0]">
                <div>
                  <div className="font-mono font-bold text-lg">example.com</div>
                  <div className="text-xs opacity-60 font-mono mt-1">/var/www/example.com/public</div>
                </div>
                <div className="flex gap-2">
                  <span className="bg-green-200 text-green-800 border border-green-800 px-2 py-0.5 text-[10px] uppercase font-bold flex items-center">SSL Active</span>
                  <button className="border border-[#141414] px-3 py-1 text-[10px] font-bold uppercase hover:bg-[#141414] hover:text-[#E4E3E0] transition-colors cursor-pointer">Configure</button>
                </div>
              </div>
            </div>
            <button className="mt-6 border border-[#141414] px-4 py-2 text-xs font-bold uppercase hover:bg-[#141414] hover:text-[#E4E3E0] transition-colors cursor-pointer self-start">
              + Add New Domain
            </button>
          </section>
        );
      case 'databases':
        return (
          <section className="flex-1 flex flex-col border border-[#141414] bg-white/30 p-6">
            <h2 className="text-lg font-bold font-serif italic mb-6 border-b border-[#141414] pb-2">MySQL / MariaDB Databases</h2>
            <div className="grid grid-cols-[1fr_1fr_auto] gap-4 p-2 border-b border-[#141414] font-bold uppercase text-[10px] opacity-60">
              <div>Database Name</div>
              <div>User</div>
              <div>Actions</div>
            </div>
            <div className="grid grid-cols-[1fr_1fr_auto] gap-4 p-3 border-b border-[#141414]/20 hover:bg-[#141414] hover:text-[#E4E3E0] transition-colors items-center">
              <div className="font-mono font-bold text-sm">wp_prod_db</div>
              <div className="font-mono text-sm">wp_user</div>
              <button className="border border-current px-3 py-1 text-[10px] font-bold uppercase transition-colors cursor-pointer">Manage</button>
            </div>
            <button className="mt-6 border border-[#141414] px-4 py-2 text-xs font-bold uppercase hover:bg-[#141414] hover:text-[#E4E3E0] transition-colors cursor-pointer self-start">
              + Create Database
            </button>
          </section>
        );
      case 'terminal':
        return (
          <section className="flex-1 bg-[#141414] text-[#E4E3E0] p-4 font-mono text-[13px] overflow-hidden rounded-sm border border-white/10 flex flex-col">
            <div className="opacity-40 mb-2 border-b border-white/20 pb-1 flex justify-between shrink-0">
              <span>WEB TERMINAL</span>
              <span>/dev/pts/1 (bash)</span>
            </div>
            <div className="flex-1 overflow-y-auto">
              <div className="text-green-400">Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-89-generic x86_64)</div>
              <br/>
              <div className="flex mt-1">
                <span>[root@vps-prod-us-01]:~# </span>
                <span className="w-2 h-4 bg-white/60 ml-1 animate-pulse"></span>
              </div>
            </div>
          </section>
        );
      default:
        return (
          <div className="flex-1 flex items-center justify-center border border-[#141414] bg-white/30 text-sm font-mono font-bold uppercase opacity-50">
            Module Under Construction
          </div>
        );
    }
  };

  return (
    <div className="w-full h-screen overflow-hidden bg-[#E4E3E0] text-[#141414] flex flex-row font-sans selection:bg-[#141414] selection:text-[#E4E3E0]">
      <aside className="w-[240px] border-r border-[#141414] flex flex-col h-full shrink-0">
        <div className="p-6 border-b border-[#141414]">
          <div className="text-xs font-bold tracking-widest uppercase mb-1">Core Panel v1.0</div>
          <div className="text-[10px] font-mono opacity-60 uppercase">Root Systems Engineering</div>
        </div>
        <nav className="flex-1 overflow-y-auto flex flex-col">
          <button onClick={() => setActiveTab('dashboard')} className={`sidebar-link flex items-center p-4 pl-6 text-xs font-bold uppercase tracking-wider text-left ${activeTab === 'dashboard' ? 'active' : ''}`}>Dashboard</button>
          <button onClick={() => setActiveTab('file-manager')} className={`sidebar-link flex items-center p-4 pl-6 text-xs font-bold uppercase tracking-wider text-left ${activeTab === 'file-manager' ? 'active' : ''}`}>File Manager</button>
          <button onClick={() => setActiveTab('web-server')} className={`sidebar-link flex items-center p-4 pl-6 text-xs font-bold uppercase tracking-wider text-left ${activeTab === 'web-server' ? 'active' : ''}`}>Web Server</button>
          <button onClick={() => setActiveTab('databases')} className={`sidebar-link flex items-center p-4 pl-6 text-xs font-bold uppercase tracking-wider text-left ${activeTab === 'databases' ? 'active' : ''}`}>Databases</button>
          <button onClick={() => setActiveTab('services')} className={`sidebar-link flex items-center p-4 pl-6 text-xs font-bold uppercase tracking-wider text-left ${activeTab === 'services' ? 'active' : ''}`}>System Services</button>
          <button onClick={() => setActiveTab('security')} className={`sidebar-link flex items-center p-4 pl-6 text-xs font-bold uppercase tracking-wider text-left ${activeTab === 'security' ? 'active' : ''}`}>Security / FW</button>
          <button onClick={() => setActiveTab('terminal')} className={`sidebar-link flex items-center p-4 pl-6 text-xs font-bold uppercase tracking-wider text-left ${activeTab === 'terminal' ? 'active' : ''}`}>Web Terminal</button>
          <button onClick={() => setActiveTab('cron')} className={`sidebar-link flex items-center p-4 pl-6 text-xs font-bold uppercase tracking-wider text-left ${activeTab === 'cron' ? 'active' : ''}`}>Cron Jobs</button>
        </nav>
        <div className="p-6 border-t border-[#141414] bg-[#D1D0CC]">
          <div className="text-[10px] uppercase font-bold mb-2 opacity-60">System Node</div>
          <div className="text-xs font-mono">vps-prod-us-01</div>
          <div className="text-[10px] text-green-700 font-bold mt-1">● SESSION ACTIVE</div>
        </div>
      </aside>
      
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        <header className="h-16 shrink-0 border-b border-[#141414] flex items-center justify-between px-8 bg-[#E4E3E0]">
          <div className="flex items-center gap-8">
            <div className="text-xs">
              <span className="opacity-50 uppercase mr-2 italic font-serif">OS:</span>
              <span className="font-bold font-mono">Ubuntu 22.04.3 LTS</span>
            </div>
            <div className="text-xs hidden md:block">
              <span className="opacity-50 uppercase mr-2 italic font-serif">Kernel:</span>
              <span className="font-bold font-mono">5.15.0-generic</span>
            </div>
            <div className="text-xs">
              <span className="opacity-50 uppercase mr-2 italic font-serif">Uptime:</span>
              <span className="font-bold font-mono">{systemStatus?.uptime || "Loading..."}</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button className="border border-[#141414] px-3 py-1 text-[10px] font-bold uppercase hover:bg-[#141414] hover:text-[#E4E3E0] transition-colors cursor-pointer">
              Update System
            </button>
            <div className="w-8 h-8 rounded-full border border-[#141414] bg-[#D1D0CC] flex items-center justify-center font-bold text-xs">JD</div>
          </div>
        </header>
        
        <div className="p-4 md:p-8 flex-1 flex flex-col gap-4 md:gap-8 overflow-y-auto">
          {renderContent()}
          
          {activeTab !== 'terminal' && (
            <section className="h-[180px] shrink-0 bg-[#141414] text-[#E4E3E0] p-4 font-mono text-[11px] overflow-hidden rounded-sm border border-white/10 flex flex-col mt-auto">
              <div className="opacity-40 mb-2 border-b border-white/20 pb-1 flex justify-between shrink-0">
                <span>TERMINAL OVERVIEW</span>
                <span>/dev/pts/0 (bash)</span>
              </div>
              <div className="flex-1 overflow-y-auto">
                <div>[root@vps-prod-us-01]:~# systemctl status nginx</div>
                <div className="text-green-400">● nginx.service - A high performance web server and a reverse proxy server</div>
                <div className="text-white/80">   Loaded: loaded (/lib/systemd/system/nginx.service; enabled; vendor preset: enabled)</div>
                <div className="text-white/80">   Active: active (running) since Wed 2023-10-25 08:12:34 UTC; 4 days ago</div>
                <div className="flex mt-1">
                  <span>[root@vps-prod-us-01]:~# </span>
                  <span className="w-2 h-4 bg-white/60 ml-1 animate-pulse"></span>
                </div>
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
