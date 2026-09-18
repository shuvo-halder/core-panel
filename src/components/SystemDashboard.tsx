import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  AlertCircle,
  Clock,
  Cpu,
  HardDrive,
  Network,
  RefreshCw,
  Server,
  Zap,
} from 'lucide-react';
import { apiClient, ApiError } from '../api/client';
import { SystemOverview } from '../types/system';

// Utility functions for telemetry formatting
function formatBytes(bytes: number, decimals: number = 2): string {
  if (!bytes || bytes <= 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const idx = Math.min(i, sizes.length - 1);
  return `${parseFloat((bytes / Math.pow(k, idx)).toFixed(dm))} ${sizes[idx]}`;
}

function formatUptime(totalSeconds: number): string {
  if (!totalSeconds || totalSeconds <= 0) return '0s';
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);

  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0 || days > 0) parts.push(`${hours}h`);
  if (minutes > 0 || hours > 0 || days > 0) parts.push(`${minutes}m`);
  parts.push(`${seconds}s`);

  return parts.join(' ');
}

function getUsageColor(percent: number): { text: string; bg: string; bar: string } {
  if (percent >= 85) {
    return { text: 'text-rose-400', bg: 'bg-rose-950/40 border-rose-800/50', bar: 'bg-rose-500' };
  }
  if (percent >= 65) {
    return { text: 'text-amber-400', bg: 'bg-amber-950/40 border-amber-800/50', bar: 'bg-amber-500' };
  }
  return { text: 'text-emerald-400', bg: 'bg-emerald-950/40 border-emerald-800/50', bar: 'bg-emerald-500' };
}

export const SystemDashboard: React.FC = () => {
  const [overview, setOverview] = useState<SystemOverview | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshInterval, setRefreshInterval] = useState<number>(5000); // 5 seconds default
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  const isMountedRef = useRef<boolean>(true);

  const fetchTelemetry = useCallback(async (isManual: boolean = false) => {
    if (isManual) {
      setIsRefreshing(true);
    }
    setError(null);

    try {
      const data = await apiClient.getSystemOverview();
      if (isMountedRef.current) {
        setOverview(data);
        setLastFetched(new Date());
      }
    } catch (err) {
      if (isMountedRef.current) {
        if (err instanceof ApiError) {
          setError(`Telemetry Error (${err.code}): ${err.message}`);
        } else {
          setError('Failed to reach system telemetry API.');
        }
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    fetchTelemetry(false);

    if (refreshInterval <= 0) return;

    const timer = setInterval(() => {
      fetchTelemetry(false);
    }, refreshInterval);

    return () => {
      isMountedRef.current = false;
      clearInterval(timer);
    };
  }, [fetchTelemetry, refreshInterval]);

  if (isLoading && !overview) {
    return (
      <div id="system-loading-view" className="p-8 flex flex-col items-center justify-center space-y-3 min-h-[400px]">
        <RefreshCw className="w-6 h-6 animate-spin text-neutral-400" />
        <div className="text-xs font-mono text-neutral-400">Querying Linux host telemetry...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-neutral-800">
        <div>
          <h2 className="text-lg font-medium text-white flex items-center gap-2">
            <Activity className="w-5 h-5 text-neutral-300" />
            System Telemetry &amp; Resource Monitor
          </h2>
          <p className="text-xs text-neutral-400 mt-0.5">
            Real-time kernel inspection, hardware compute metrics, filesystem utilization, and network traffic
          </p>
        </div>

        {/* Polling & Refresh Toolbar */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-[11px] text-neutral-400 font-mono">Interval:</span>
            <select
              id="refresh-interval-select"
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              className="bg-neutral-900 border border-neutral-700 text-neutral-200 rounded px-2 py-1 text-xs font-mono focus:outline-hidden focus:border-neutral-500"
            >
              <option value={0}>Paused</option>
              <option value={2000}>2s</option>
              <option value={5000}>5s</option>
              <option value={10000}>10s</option>
              <option value={30000}>30s</option>
            </select>
          </div>

          <button
            id="system-refresh-btn"
            onClick={() => fetchTelemetry(true)}
            disabled={isRefreshing}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 disabled:opacity-50 text-neutral-200 hover:text-white rounded-md text-xs font-medium border border-neutral-700 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-white' : 'text-neutral-400'}`} />
            <span>Refresh</span>
          </button>

          {lastFetched && (
            <div className="hidden lg:flex items-center gap-1.5 text-[11px] font-mono text-neutral-400">
              <div className={`w-2 h-2 rounded-full ${error ? 'bg-rose-500' : 'bg-emerald-500 animate-pulse'}`} />
              <span>{lastFetched.toLocaleTimeString()}</span>
            </div>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div id="system-error-banner" className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-lg flex items-center gap-2 text-xs text-rose-300">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {overview && (
        <>
          {/* Top Identity Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Hostname & OS */}
            <div id="card-identity" className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-neutral-400 uppercase tracking-wider">Host Identity</span>
                <Server className="w-4 h-4 text-neutral-400" />
              </div>
              <div className="text-sm font-semibold text-white font-mono truncate">{overview.identity.hostname}</div>
              <div className="flex items-center gap-1.5 text-xs text-neutral-300">
                <span className="px-1.5 py-0.5 bg-neutral-800 border border-neutral-700 rounded text-[10px] font-mono uppercase">
                  {overview.identity.distribution} {overview.identity.distribution_version}
                </span>
                <span className="text-[11px] text-neutral-400 font-mono">({overview.identity.architecture})</span>
              </div>
            </div>

            {/* Kernel & Architecture */}
            <div id="card-kernel" className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-neutral-400 uppercase tracking-wider">Kernel Release</span>
                <Zap className="w-4 h-4 text-neutral-400" />
              </div>
              <div className="text-sm font-semibold text-white font-mono truncate" title={overview.identity.kernel_version}>
                {overview.identity.kernel_version}
              </div>
              <div className="text-xs text-neutral-400 font-mono">
                Platform: {overview.identity.operating_system}
              </div>
            </div>

            {/* Uptime */}
            <div id="card-uptime" className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-neutral-400 uppercase tracking-wider">System Uptime</span>
                <Clock className="w-4 h-4 text-neutral-400" />
              </div>
              <div className="text-sm font-semibold text-emerald-400 font-mono">
                {formatUptime(overview.identity.uptime_seconds)}
              </div>
              <div className="text-[11px] text-neutral-400 font-mono">
                {Math.floor(overview.identity.uptime_seconds).toLocaleString()} seconds
              </div>
            </div>

            {/* Boot Time */}
            <div id="card-boot-time" className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-neutral-400 uppercase tracking-wider">Boot Timestamp</span>
                <Clock className="w-4 h-4 text-neutral-400" />
              </div>
              <div className="text-xs font-semibold text-neutral-200 font-mono truncate">
                {overview.identity.boot_time ? new Date(overview.identity.boot_time).toUTCString() : 'N/A'}
              </div>
              <div className="text-[11px] text-neutral-400 font-mono">
                UTC Synchronized
              </div>
            </div>
          </div>

          {/* Compute & Memory Dynamics */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* CPU Metrics Card */}
            <div id="card-cpu-metrics" className="p-5 bg-neutral-900 border border-neutral-800 rounded-lg space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-neutral-800">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-neutral-400" />
                  <span className="text-xs font-semibold text-white uppercase tracking-wider">Processor &amp; Compute</span>
                </div>
                <span className="text-[11px] font-mono px-2 py-0.5 bg-neutral-800 text-neutral-300 border border-neutral-700 rounded">
                  {overview.cpu.logical_cores} Logical {overview.cpu.logical_cores === 1 ? 'Core' : 'Cores'}
                </span>
              </div>

              <div>
                <div className="text-xs text-neutral-400 font-mono truncate mb-3" title={overview.cpu.model_name}>
                  {overview.cpu.model_name}
                </div>

                {/* Real-time Usage Progress Bar */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-neutral-400">Total CPU Utilization</span>
                    <span className={`font-mono font-semibold ${getUsageColor(overview.cpu.usage_percent).text}`}>
                      {overview.cpu.usage_percent.toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-2 w-full bg-neutral-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${getUsageColor(overview.cpu.usage_percent).bar}`}
                      style={{ width: `${Math.min(100, Math.max(0, overview.cpu.usage_percent))}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Load Averages */}
              <div className="pt-2 border-t border-neutral-800/80">
                <div className="text-[11px] text-neutral-400 uppercase tracking-wider mb-2">Load Average</div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 bg-neutral-950 border border-neutral-800 rounded">
                    <div className="text-[10px] text-neutral-400 font-mono">1 min</div>
                    <div className="text-sm font-mono font-semibold text-neutral-100">
                      {overview.cpu.load_average.load_1m.toFixed(2)}
                    </div>
                  </div>
                  <div className="p-2 bg-neutral-950 border border-neutral-800 rounded">
                    <div className="text-[10px] text-neutral-400 font-mono">5 min</div>
                    <div className="text-sm font-mono font-semibold text-neutral-100">
                      {overview.cpu.load_average.load_5m.toFixed(2)}
                    </div>
                  </div>
                  <div className="p-2 bg-neutral-950 border border-neutral-800 rounded">
                    <div className="text-[10px] text-neutral-400 font-mono">15 min</div>
                    <div className="text-sm font-mono font-semibold text-neutral-100">
                      {overview.cpu.load_average.load_15m.toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Memory & Swap Card */}
            <div id="card-memory-metrics" className="p-5 bg-neutral-900 border border-neutral-800 rounded-lg space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-neutral-800">
                <div className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-neutral-400" />
                  <span className="text-xs font-semibold text-white uppercase tracking-wider">Memory &amp; Swap</span>
                </div>
                <span className="text-[11px] font-mono px-2 py-0.5 bg-neutral-800 text-neutral-300 border border-neutral-700 rounded">
                  {formatBytes(overview.memory.total_bytes)} Total RAM
                </span>
              </div>

              {/* RAM Usage Bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-neutral-400">RAM Physical Allocation</span>
                  <span className={`font-mono font-semibold ${getUsageColor(overview.memory.usage_percent).text}`}>
                    {overview.memory.usage_percent.toFixed(1)}% ({formatBytes(overview.memory.used_bytes)} / {formatBytes(overview.memory.total_bytes)})
                  </span>
                </div>
                <div className="h-2 w-full bg-neutral-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${getUsageColor(overview.memory.usage_percent).bar}`}
                    style={{ width: `${Math.min(100, Math.max(0, overview.memory.usage_percent))}%` }}
                  />
                </div>
                <div className="flex justify-between text-[11px] font-mono text-neutral-400 pt-0.5">
                  <span>Available: {formatBytes(overview.memory.available_bytes)}</span>
                  <span>Free: {formatBytes(overview.memory.free_bytes)}</span>
                </div>
              </div>

              {/* Swap Usage */}
              <div className="pt-2 border-t border-neutral-800/80 space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-neutral-400">Swap Space</span>
                  {overview.memory.swap.total_bytes > 0 ? (
                    <span className="font-mono text-neutral-300">
                      {overview.memory.swap.usage_percent.toFixed(1)}% ({formatBytes(overview.memory.swap.used_bytes)} / {formatBytes(overview.memory.swap.total_bytes)})
                    </span>
                  ) : (
                    <span className="text-[11px] text-neutral-400 font-mono">None Configured</span>
                  )}
                </div>
                {overview.memory.swap.total_bytes > 0 && (
                  <div className="h-1.5 w-full bg-neutral-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-neutral-400 transition-all duration-300"
                      style={{ width: `${Math.min(100, Math.max(0, overview.memory.swap.usage_percent))}%` }}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Mounted Filesystems */}
          <div id="section-filesystems" className="border border-neutral-800 bg-neutral-900 rounded-lg p-5 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-neutral-800">
              <div className="flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-neutral-400" />
                <span className="text-xs font-semibold text-white uppercase tracking-wider">
                  Mounted Local Filesystems ({overview.disks.length})
                </span>
              </div>
              <span className="text-[11px] text-neutral-400 font-mono">Unprivileged statvfs</span>
            </div>

            {overview.disks.length === 0 ? (
              <div className="text-xs text-neutral-400 font-mono py-4 text-center">No local mount points detected</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-neutral-800 text-[11px] font-mono text-neutral-400 uppercase">
                      <th className="pb-2 font-medium">Mount Point</th>
                      <th className="pb-2 font-medium">Device</th>
                      <th className="pb-2 font-medium">Type</th>
                      <th className="pb-2 font-medium">Capacity</th>
                      <th className="pb-2 font-medium">Used</th>
                      <th className="pb-2 font-medium">Available</th>
                      <th className="pb-2 font-medium w-48">Utilization</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-800/60 font-mono">
                    {overview.disks.map((disk) => {
                      const colors = getUsageColor(disk.usage_percent);
                      return (
                        <tr key={disk.mount_point} className="hover:bg-neutral-850/50">
                          <td className="py-2.5 font-semibold text-white">{disk.mount_point}</td>
                          <td className="py-2.5 text-neutral-300 truncate max-w-[150px]">{disk.device}</td>
                          <td className="py-2.5 text-neutral-400">{disk.filesystem_type}</td>
                          <td className="py-2.5 text-neutral-200">{formatBytes(disk.total_bytes)}</td>
                          <td className="py-2.5 text-neutral-300">{formatBytes(disk.used_bytes)}</td>
                          <td className="py-2.5 text-neutral-400">{formatBytes(disk.available_bytes)}</td>
                          <td className="py-2.5">
                            <div className="space-y-1">
                              <div className="flex justify-between text-[10px]">
                                <span className={colors.text}>{disk.usage_percent.toFixed(1)}%</span>
                              </div>
                              <div className="h-1.5 w-full bg-neutral-800 rounded-full overflow-hidden">
                                <div
                                  className={`h-full transition-all duration-300 ${colors.bar}`}
                                  style={{ width: `${Math.min(100, Math.max(0, disk.usage_percent))}%` }}
                                />
                              </div>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Network Interfaces */}
          <div id="section-network" className="border border-neutral-800 bg-neutral-900 rounded-lg p-5 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-neutral-800">
              <div className="flex items-center gap-2">
                <Network className="w-4 h-4 text-neutral-400" />
                <span className="text-xs font-semibold text-white uppercase tracking-wider">
                  Network Interfaces &amp; Traffic ({overview.network.length})
                </span>
              </div>
              <span className="text-[11px] text-neutral-400 font-mono">Unprivileged /sys/class/net &amp; /proc/net/dev</span>
            </div>

            {overview.network.length === 0 ? (
              <div className="text-xs text-neutral-400 font-mono py-4 text-center">No active interfaces discovered</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {overview.network.map((iface) => (
                  <div
                    key={iface.name}
                    className="p-4 bg-neutral-950 border border-neutral-800 rounded-lg space-y-2.5 font-mono text-xs"
                  >
                    <div className="flex items-center justify-between pb-1.5 border-b border-neutral-800">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-white text-sm">{iface.name}</span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                            iface.state.toLowerCase() === 'up'
                              ? 'bg-emerald-950 border border-emerald-800 text-emerald-400'
                              : 'bg-neutral-800 border border-neutral-700 text-neutral-400'
                          }`}
                        >
                          {iface.state}
                        </span>
                      </div>
                      <span className="text-[11px] text-neutral-400">{iface.mac_address}</span>
                    </div>

                    {/* IP Addresses */}
                    <div className="space-y-1">
                      {iface.ipv4_addresses.length > 0 && (
                        <div className="flex items-center gap-2 text-[11px]">
                          <span className="text-neutral-400 uppercase text-[10px] w-8">IPv4:</span>
                          <div className="flex flex-wrap gap-1">
                            {iface.ipv4_addresses.map((ip) => (
                              <span key={ip} className="px-1.5 py-0.2 bg-neutral-900 border border-neutral-700 text-neutral-200 rounded">
                                {ip}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {iface.ipv6_addresses.length > 0 && (
                        <div className="flex items-start gap-2 text-[11px]">
                          <span className="text-neutral-400 uppercase text-[10px] w-8 mt-0.5">IPv6:</span>
                          <div className="flex flex-wrap gap-1 truncate">
                            {iface.ipv6_addresses.slice(0, 2).map((ip) => (
                              <span key={ip} className="px-1.5 py-0.2 bg-neutral-900 border border-neutral-700 text-neutral-400 rounded truncate max-w-[280px]" title={ip}>
                                {ip}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Cumulative Traffic */}
                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-neutral-800/80 text-[11px]">
                      <div className="p-1.5 bg-neutral-900 border border-neutral-800/60 rounded flex justify-between items-center">
                        <span className="text-neutral-400">RX (Received)</span>
                        <span className="text-emerald-400 font-semibold">{formatBytes(iface.rx_bytes)}</span>
                      </div>
                      <div className="p-1.5 bg-neutral-900 border border-neutral-800/60 rounded flex justify-between items-center">
                        <span className="text-neutral-400">TX (Sent)</span>
                        <span className="text-neutral-200 font-semibold">{formatBytes(iface.tx_bytes)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
