import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginForm } from './components/LoginForm';
import { UserManagement } from './components/UserManagement';
import { RoleManagement } from './components/RoleManagement';
import { ServiceManagement } from './components/ServiceManagement';
import { SystemDashboard } from './components/SystemDashboard';
import { ProcessManagement } from './components/ProcessManagement';
import { StorageManagement } from './components/StorageManagement';
import { NetworkManagement } from './components/NetworkManagement';
import { PackageManagement } from './components/PackageManagement';
import { CronManagement } from './components/CronManagement';
import { LogManagement } from './components/LogManagement';
import {
  Shield,
  Users,
  LogOut,
  Activity,
  Layers,
  CheckCircle2,
  Lock,
  Server,
  Loader2,
  Cpu,
  HardDrive,
  Radio,
  Package,
  Clock,
  FileText,
} from 'lucide-react';

const AppContent: React.FC = () => {
  const { user, permissions, isAuthenticated, isLoading, logout, hasPermission } = useAuth();
  const [activeTab, setActiveTab] = useState<'system' | 'services' | 'processes' | 'storage' | 'network' | 'packages' | 'cron' | 'logs' | 'overview' | 'users' | 'roles'>('system');

  if (isLoading) {
    return (
      <div className="min-h-screen bg-neutral-900 text-neutral-300 flex flex-col items-center justify-center font-mono text-xs space-y-3">
        <Loader2 className="w-6 h-6 animate-spin text-neutral-400" />
        <span>Validating session credentials...</span>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <LoginForm />;
  }

  const canReadSystem = hasPermission('system.read');
  const canReadServices = hasPermission('services.read');
  const canReadProcesses = hasPermission('processes.read');
  const canReadStorage = hasPermission('storage.read');
  const canReadNetwork = hasPermission('network.read');
  const canReadPackages = hasPermission('packages.read');
  const canReadCron = hasPermission('cron.read');
  const canReadLogs = hasPermission('logs.read');
  const canReadAudit = hasPermission('audit.read');
  const canReadUsers = hasPermission('users.read');
  const canReadRoles = hasPermission('roles.read');

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col antialiased">
      {/* Top Navigation Bar */}
      <header className="h-14 border-b border-neutral-800 bg-neutral-900/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center space-x-3">
          <div className="p-1.5 bg-neutral-800 border border-neutral-700 rounded-md">
            <Server className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight text-white flex items-center gap-2">
              CorePanel
              <span className="text-[10px] font-mono px-1.5 py-0.2 bg-neutral-800 text-neutral-400 border border-neutral-700 rounded">
                v0.1.0-phase3
              </span>
            </div>
          </div>
        </div>

        {/* User Status and Logout */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 text-xs">
            <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
            <span className="text-neutral-300 font-medium">{user.username}</span>
            <div className="flex gap-1">
              {user.roles.map((r) => (
                <span
                  key={r}
                  className="px-1.5 py-0.5 bg-neutral-800 border border-neutral-700 text-neutral-400 rounded text-[10px] font-mono uppercase"
                >
                  {r}
                </span>
              ))}
            </div>
          </div>

          <button
            id="header-logout-btn"
            onClick={logout}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 hover:text-white rounded-md text-xs font-medium border border-neutral-700 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </header>

      {/* Main Body */}
      <div className="flex-1 flex flex-col md:flex-row">
        {/* Navigation Sidebar */}
        <aside className="w-full md:w-56 border-b md:border-b-0 md:border-r border-neutral-800 bg-neutral-900/50 p-4 shrink-0">
          <div className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider mb-2 px-3">
            Navigation
          </div>
          <nav className="space-y-1">
            {canReadSystem && (
              <button
                id="nav-system-btn"
                onClick={() => setActiveTab('system')}
                className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'system'
                    ? 'bg-neutral-800 text-white shadow-xs'
                    : 'text-neutral-400 hover:text-white hover:bg-neutral-850'
                }`}
              >
                <Cpu className="w-4 h-4 text-neutral-400" />
                <span>System Monitor</span>
              </button>
            )}

            {canReadServices && (
              <button
                id="nav-services-btn"
                onClick={() => setActiveTab('services')}
                className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'services'
                    ? 'bg-neutral-800 text-white shadow-xs'
                    : 'text-neutral-400 hover:text-white hover:bg-neutral-850'
                }`}
              >
                <Server className="w-4 h-4 text-neutral-400" />
                <span>Services</span>
              </button>
            )}

            {canReadProcesses && (
              <button
                id="nav-processes-btn"
                onClick={() => setActiveTab('processes')}
                className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'processes'
                    ? 'bg-neutral-800 text-white shadow-xs'
                    : 'text-neutral-400 hover:text-white hover:bg-neutral-850'
                }`}
              >
                <Activity className="w-4 h-4 text-neutral-400" />
                <span>Processes</span>
              </button>
            )}

            {canReadStorage && (
              <button
                id="nav-storage-btn"
                onClick={() => setActiveTab('storage')}
                className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'storage'
                    ? 'bg-neutral-800 text-white shadow-xs'
                    : 'text-neutral-400 hover:text-white hover:bg-neutral-850'
                }`}
              >
                <HardDrive className="w-4 h-4 text-neutral-400" />
                <span>Storage &amp; Disks</span>
              </button>
            )}

            {canReadNetwork && (
              <button
                id="nav-network-btn"
                onClick={() => setActiveTab('network')}
                className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'network'
                    ? 'bg-neutral-800 text-white shadow-xs'
                    : 'text-neutral-400 hover:text-white hover:bg-neutral-850'
                }`}
              >
                <Radio className="w-4 h-4 text-neutral-400" />
                <span>Network</span>
              </button>
            )}

            {canReadPackages && (
              <button
                id="nav-packages-btn"
                onClick={() => setActiveTab('packages')}
                className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'packages'
                    ? 'bg-neutral-800 text-white shadow-xs'
                    : 'text-neutral-400 hover:text-white hover:bg-neutral-850'
                }`}
              >
                <Package className="w-4 h-4 text-neutral-400" />
                <span>Packages</span>
              </button>
            )}

            {canReadCron && (
              <button
                id="nav-cron-btn"
                onClick={() => setActiveTab('cron')}
                className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'cron'
                    ? 'bg-neutral-800 text-white shadow-xs'
                    : 'text-neutral-400 hover:text-white hover:bg-neutral-850'
                }`}
              >
                <Clock className="w-4 h-4 text-neutral-400" />
                <span>Cron Jobs</span>
              </button>
            )}

            {(canReadLogs || canReadAudit) && (
              <button
                id="nav-logs-btn"
                onClick={() => setActiveTab('logs')}
                className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'logs'
                    ? 'bg-neutral-800 text-white shadow-xs'
                    : 'text-neutral-400 hover:text-white hover:bg-neutral-850'
                }`}
              >
                <FileText className="w-4 h-4 text-neutral-400" />
                <span>System &amp; Audit Logs</span>
              </button>
            )}

            <button
              id="nav-overview-btn"
              onClick={() => setActiveTab('overview')}
              className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                activeTab === 'overview'
                  ? 'bg-neutral-800 text-white shadow-xs'
                  : 'text-neutral-400 hover:text-white hover:bg-neutral-850'
              }`}
            >
              <Shield className="w-4 h-4 text-neutral-400" />
              <span>Auth &amp; Session</span>
            </button>

            {canReadUsers && (
              <button
                id="nav-users-btn"
                onClick={() => setActiveTab('users')}
                className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'users'
                    ? 'bg-neutral-800 text-white shadow-xs'
                    : 'text-neutral-400 hover:text-white hover:bg-neutral-850'
                }`}
              >
                <Users className="w-4 h-4 text-neutral-400" />
                <span>User Accounts</span>
              </button>
            )}

            {canReadRoles && (
              <button
                id="nav-roles-btn"
                onClick={() => setActiveTab('roles')}
                className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'roles'
                    ? 'bg-neutral-800 text-white shadow-xs'
                    : 'text-neutral-400 hover:text-white hover:bg-neutral-850'
                }`}
              >
                <Layers className="w-4 h-4 text-neutral-400" />
                <span>Roles &amp; RBAC</span>
              </button>
            )}
          </nav>

          <div className="mt-8 pt-4 border-t border-neutral-800/80 px-3">
            <div className="text-[10px] font-mono text-neutral-400 uppercase">Privilege Boundary</div>
            <div className="text-[11px] text-neutral-300 mt-1">Control Plane Protected</div>
          </div>
        </aside>

        {/* Content View */}
        <main className="flex-1 p-6 md:p-8 max-w-6xl">
          {activeTab === 'system' && canReadSystem && <SystemDashboard />}
          {activeTab === 'services' && canReadServices && <ServiceManagement />}
          {activeTab === 'processes' && canReadProcesses && <ProcessManagement />}
          {activeTab === 'storage' && canReadStorage && <StorageManagement />}
          {activeTab === 'network' && canReadNetwork && <NetworkManagement />}
          {activeTab === 'packages' && canReadPackages && <PackageManagement />}
          {activeTab === 'cron' && canReadCron && <CronManagement />}
          {activeTab === 'logs' && (canReadLogs || canReadAudit) && <LogManagement permissions={permissions} />}

          {activeTab === 'overview' && (
            <div className="space-y-6">
              <div className="pb-4 border-b border-neutral-800">
                <h2 className="text-lg font-medium text-white flex items-center gap-2">
                  <Shield className="w-5 h-5 text-neutral-400" />
                  Authenticated Security Context
                </h2>
                <p className="text-xs text-neutral-400 mt-0.5">
                  Current authenticated principal, session attributes, and resolved RBAC permissions
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
                  <div className="text-[11px] text-neutral-400 uppercase tracking-wider mb-1">Username</div>
                  <div className="text-sm font-semibold text-white font-mono">{user.username}</div>
                  <div className="text-[11px] text-neutral-400 font-mono mt-1">ID: {user.id}</div>
                </div>

                <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
                  <div className="text-[11px] text-neutral-400 uppercase tracking-wider mb-1">Status</div>
                  <div className="text-sm font-semibold text-emerald-400 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4" /> Active Session
                  </div>
                  <div className="text-[11px] text-neutral-400 mt-1">HttpOnly Cookie Bound</div>
                </div>

                <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
                  <div className="text-[11px] text-neutral-400 uppercase tracking-wider mb-1">Assigned Roles</div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {user.roles.map((r) => (
                      <span
                        key={r}
                        className="px-2 py-0.5 bg-neutral-800 border border-neutral-700 text-neutral-200 rounded text-xs font-mono"
                      >
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Effective Permissions Matrix */}
              <div className="border border-neutral-800 bg-neutral-900/60 rounded-lg p-5">
                <div className="flex items-center justify-between mb-3 pb-2 border-b border-neutral-800">
                  <div className="text-xs font-medium text-white flex items-center gap-2">
                    <Lock className="w-4 h-4 text-neutral-400" />
                    Effective Permissions ({permissions.length})
                  </div>
                  <span className="text-[11px] text-neutral-400 font-mono">Inherited via RBAC</span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                  {permissions.map((perm) => (
                    <div
                      key={perm}
                      className="p-2 bg-neutral-900 border border-neutral-800 rounded text-[11px] font-mono text-neutral-300 flex items-center gap-1.5"
                    >
                      <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                      <span className="truncate">{perm}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'users' && canReadUsers && <UserManagement />}
          {activeTab === 'roles' && canReadRoles && <RoleManagement />}
        </main>
      </div>
    </div>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
