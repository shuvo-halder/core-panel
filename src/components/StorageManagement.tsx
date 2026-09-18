import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  HardDrive,
  Database,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertCircle,
  FolderTree,
  SlidersHorizontal,
  Disc,
  Layers,
  Lock,
  ExternalLink,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { BlockDeviceInfo, FilesystemInfo, StorageOverview } from '../types/storage';

export const StorageManagement: React.FC = () => {
  const [overview, setOverview] = useState<StorageOverview | null>(null);
  const [devices, setDevices] = useState<BlockDeviceInfo[]>([]);
  const [filesystems, setFilesystems] = useState<FilesystemInfo[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // View & Filter States
  const [activeSubTab, setActiveSubTab] = useState<'filesystems' | 'devices'>('filesystems');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [includePseudo, setIncludePseudo] = useState<boolean>(false);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState<number>(10);
  const [expandedDevices, setExpandedDevices] = useState<Record<string, boolean>>({});

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const fetchData = useCallback(async (showLoading: boolean = false) => {
    if (showLoading) setIsLoading(true);
    setIsRefreshing(true);
    setError(null);

    try {
      const [overviewData, devicesData, fsData] = await Promise.all([
        apiClient.getStorageOverview(),
        apiClient.getStorageDevices(),
        apiClient.getStorageFilesystems(includePseudo),
      ]);

      setOverview(overviewData);
      setDevices(devicesData);
      setFilesystems(fsData);

      // Auto expand all block devices with children by default
      const autoExpanded: Record<string, boolean> = {};
      devicesData.forEach((d) => {
        if (d.children && d.children.length > 0) {
          autoExpanded[d.name] = true;
        }
      });
      setExpandedDevices((prev) => ({ ...autoExpanded, ...prev }));
    } catch (err: any) {
      console.error('Failed fetching storage telemetry:', err);
      setError(err.message || 'Failed to load storage telemetry');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [includePseudo]);

  useEffect(() => {
    fetchData(true);
  }, [fetchData]);

  // Polling Auto-Refresh
  useEffect(() => {
    if (autoRefreshInterval <= 0) return;

    const timer = setInterval(() => {
      fetchData(false);
    }, autoRefreshInterval * 1000);

    return () => clearInterval(timer);
  }, [autoRefreshInterval, fetchData]);

  const toggleDeviceExpand = (name: string) => {
    setExpandedDevices((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  // Filtered Filesystems
  const filteredFilesystems = useMemo(() => {
    if (!searchQuery.trim()) return filesystems;
    const q = searchQuery.toLowerCase();
    return filesystems.filter(
      (fs) =>
        fs.mount_point.toLowerCase().includes(q) ||
        fs.device.toLowerCase().includes(q) ||
        fs.fstype.toLowerCase().includes(q) ||
        (fs.label && fs.label.toLowerCase().includes(q)) ||
        (fs.uuid && fs.uuid.toLowerCase().includes(q))
    );
  }, [filesystems, searchQuery]);

  // Filtered Block Devices
  const filteredDevices = useMemo(() => {
    if (!searchQuery.trim()) return devices;
    const q = searchQuery.toLowerCase();
    return devices.filter(
      (d) =>
        d.name.toLowerCase().includes(q) ||
        d.path.toLowerCase().includes(q) ||
        d.device_type.toLowerCase().includes(q) ||
        (d.model && d.model.toLowerCase().includes(q)) ||
        (d.vendor && d.vendor.toLowerCase().includes(q)) ||
        (d.mount_point && d.mount_point.toLowerCase().includes(q)) ||
        d.children.some(
          (c) =>
            c.name.toLowerCase().includes(q) ||
            c.path.toLowerCase().includes(q) ||
            (c.mount_point && c.mount_point.toLowerCase().includes(q))
        )
    );
  }, [devices, searchQuery]);

  const getUsageColorClass = (percent: number) => {
    if (percent >= 90) return 'bg-rose-500 text-rose-400';
    if (percent >= 75) return 'bg-amber-500 text-amber-400';
    return 'bg-emerald-500 text-emerald-400';
  };

  return (
    <div className="space-y-6">
      {/* Header and Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-neutral-800">
        <div>
          <h2 className="text-lg font-medium text-white flex items-center gap-2">
            <HardDrive className="w-5 h-5 text-neutral-400" />
            Storage &amp; Disks
          </h2>
          <p className="text-xs text-neutral-400 mt-0.5">
            Real-time physical block device inventory, mounted filesystems, and partition telemetry
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start sm:self-auto">
          {/* Refresh Interval Selector */}
          <div className="flex items-center gap-1.5 text-xs text-neutral-400 bg-neutral-900 border border-neutral-800 rounded-md px-2.5 py-1.5">
            <span className="text-[11px] uppercase tracking-wider font-mono">Refresh:</span>
            <select
              id="storage-refresh-interval-select"
              value={autoRefreshInterval}
              onChange={(e) => setAutoRefreshInterval(Number(e.target.value))}
              className="bg-transparent text-neutral-200 border-none outline-hidden cursor-pointer text-xs font-mono pr-1"
            >
              <option value={0} className="bg-neutral-900 text-neutral-200">
                Off
              </option>
              <option value={5} className="bg-neutral-900 text-neutral-200">
                5s
              </option>
              <option value={10} className="bg-neutral-900 text-neutral-200">
                10s
              </option>
              <option value={30} className="bg-neutral-900 text-neutral-200">
                30s
              </option>
              <option value={60} className="bg-neutral-900 text-neutral-200">
                60s
              </option>
            </select>
          </div>

          {/* Manual Refresh Button */}
          <button
            id="storage-manual-refresh-btn"
            onClick={() => fetchData(false)}
            disabled={isRefreshing}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 disabled:opacity-50 text-neutral-300 hover:text-white rounded-md text-xs font-medium border border-neutral-700 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-rose-950/40 border border-rose-800/80 rounded-lg flex items-start gap-3 text-xs text-rose-200">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold">Storage Telemetry Error:</span> {error}
          </div>
          <button
            onClick={() => fetchData(true)}
            className="px-2 py-1 bg-rose-900/60 hover:bg-rose-900 text-rose-200 rounded text-[11px] font-medium border border-rose-700/60 transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Storage Overview KPI Cards */}
      {overview && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-neutral-400 uppercase tracking-wider font-mono">
                Total Storage
              </span>
              <Database className="w-4 h-4 text-neutral-400" />
            </div>
            <div className="text-xl font-semibold text-white font-mono mt-1.5">
              {formatBytes(overview.total_bytes)}
            </div>
            <div className="text-[11px] text-neutral-400 mt-1">
              Across {overview.filesystem_count} physical filesystem{overview.filesystem_count === 1 ? '' : 's'}
            </div>
          </div>

          <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-neutral-400 uppercase tracking-wider font-mono">
                Used Capacity
              </span>
              <span className={`text-xs font-mono font-medium ${getUsageColorClass(overview.usage_percent).split(' ')[1]}`}>
                {overview.usage_percent}%
              </span>
            </div>
            <div className="text-xl font-semibold text-white font-mono mt-1.5">
              {formatBytes(overview.used_bytes)}
            </div>
            <div className="w-full bg-neutral-800 rounded-full h-1.5 mt-2 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${
                  getUsageColorClass(overview.usage_percent).split(' ')[0]
                }`}
                style={{ width: `${Math.min(overview.usage_percent, 100)}%` }}
              />
            </div>
          </div>

          <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-neutral-400 uppercase tracking-wider font-mono">
                Available Free Space
              </span>
              <HardDrive className="w-4 h-4 text-neutral-400" />
            </div>
            <div className="text-xl font-semibold text-white font-mono mt-1.5">
              {formatBytes(overview.available_bytes)}
            </div>
            <div className="text-[11px] text-neutral-400 mt-1">
              Unallocated on host partitions
            </div>
          </div>

          <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-neutral-400 uppercase tracking-wider font-mono">
                Disks &amp; Mounts
              </span>
              <Layers className="w-4 h-4 text-neutral-400" />
            </div>
            <div className="text-xl font-semibold text-white font-mono mt-1.5">
              {overview.device_count} <span className="text-xs font-normal text-neutral-400 font-sans">Disks</span> /{' '}
              {overview.mount_count} <span className="text-xs font-normal text-neutral-400 font-sans">Mounts</span>
            </div>
            <div className="text-[11px] text-neutral-400 mt-1">
              Unprivileged /sys/block &amp; /proc/mounts
            </div>
          </div>
        </div>
      )}

      {/* Sub-tab Navigation and Search Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 bg-neutral-900/80 p-3 border border-neutral-800 rounded-lg">
        <div className="flex items-center gap-1.5">
          <button
            id="tab-btn-filesystems"
            onClick={() => setActiveSubTab('filesystems')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 ${
              activeSubTab === 'filesystems'
                ? 'bg-neutral-800 text-white border border-neutral-700 shadow-xs'
                : 'text-neutral-400 hover:text-white hover:bg-neutral-800/50'
            }`}
          >
            <FolderTree className="w-3.5 h-3.5" />
            <span>Mounted Filesystems ({filesystems.length})</span>
          </button>

          <button
            id="tab-btn-devices"
            onClick={() => setActiveSubTab('devices')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 ${
              activeSubTab === 'devices'
                ? 'bg-neutral-800 text-white border border-neutral-700 shadow-xs'
                : 'text-neutral-400 hover:text-white hover:bg-neutral-800/50'
            }`}
          >
            <Disc className="w-3.5 h-3.5" />
            <span>Block Devices &amp; Disks ({devices.length})</span>
          </button>
        </div>

        <div className="flex items-center gap-3">
          {/* Search Input */}
          <div className="relative flex-1 md:w-64">
            <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              id="storage-search-input"
              type="text"
              placeholder={activeSubTab === 'filesystems' ? 'Filter by mount, device, type...' : 'Filter devices, models...'}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded-md text-xs text-neutral-200 placeholder-neutral-500 focus:outline-hidden focus:border-neutral-600"
            />
          </div>

          {/* Toggle for Virtual Filesystems */}
          {activeSubTab === 'filesystems' && (
            <label className="flex items-center gap-2 text-xs text-neutral-400 cursor-pointer select-none">
              <input
                id="toggle-pseudo-fs-checkbox"
                type="checkbox"
                checked={includePseudo}
                onChange={(e) => setIncludePseudo(e.target.checked)}
                className="rounded border-neutral-700 bg-neutral-950 text-neutral-300 focus:ring-0 focus:ring-offset-0"
              />
              <span>Virtual / Pseudo</span>
            </label>
          )}
        </div>
      </div>

      {/* Main Table View */}
      {isLoading && filesystems.length === 0 ? (
        <div className="p-12 text-center text-xs text-neutral-400 font-mono bg-neutral-900 border border-neutral-800 rounded-lg">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-neutral-500" />
          <span>Scanning Linux storage subsystem and block devices...</span>
        </div>
      ) : activeSubTab === 'filesystems' ? (
        /* Filesystems Table */
        <div className="border border-neutral-800 rounded-lg overflow-hidden bg-neutral-900">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-neutral-950/80 border-b border-neutral-800 text-[11px] font-mono text-neutral-400 uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Mount Point</th>
                  <th className="py-3 px-4">Device</th>
                  <th className="py-3 px-4">Type &amp; Flags</th>
                  <th className="py-3 px-4">Total</th>
                  <th className="py-3 px-4">Used</th>
                  <th className="py-3 px-4">Available</th>
                  <th className="py-3 px-4 min-w-[140px]">Usage</th>
                  <th className="py-3 px-4">UUID / Label</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800/60 font-sans">
                {filteredFilesystems.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-neutral-400 text-xs font-mono">
                      No filesystems matched your filter criteria
                    </td>
                  </tr>
                ) : (
                  filteredFilesystems.map((fs, idx) => (
                    <tr
                      key={`${fs.device}-${fs.mount_point}-${idx}`}
                      className="hover:bg-neutral-850/60 transition-colors"
                    >
                      <td className="py-2.5 px-4 font-mono font-medium text-white flex items-center gap-1.5">
                        <FolderTree className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
                        <span>{fs.mount_point}</span>
                      </td>
                      <td className="py-2.5 px-4 font-mono text-neutral-300 text-[11px]">
                        {fs.device}
                      </td>
                      <td className="py-2.5 px-4">
                        <div className="flex items-center gap-1.5">
                          <span className="px-1.5 py-0.5 bg-neutral-800 border border-neutral-700 text-neutral-300 rounded text-[10px] font-mono uppercase">
                            {fs.fstype}
                          </span>
                          {fs.is_read_only && (
                            <span className="px-1.5 py-0.5 bg-amber-950/80 border border-amber-800/60 text-amber-300 rounded text-[10px] font-mono flex items-center gap-1">
                              <Lock className="w-2.5 h-2.5" /> RO
                            </span>
                          )}
                          {fs.is_pseudo && (
                            <span className="px-1.5 py-0.5 bg-neutral-800/80 border border-neutral-700/60 text-neutral-400 rounded text-[10px] font-mono">
                              Virtual
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-2.5 px-4 font-mono text-neutral-300">
                        {fs.total_bytes > 0 ? formatBytes(fs.total_bytes) : '—'}
                      </td>
                      <td className="py-2.5 px-4 font-mono text-neutral-300">
                        {fs.total_bytes > 0 ? formatBytes(fs.used_bytes) : '—'}
                      </td>
                      <td className="py-2.5 px-4 font-mono text-neutral-300">
                        {fs.total_bytes > 0 ? formatBytes(fs.available_bytes) : '—'}
                      </td>
                      <td className="py-2.5 px-4">
                        {fs.total_bytes > 0 ? (
                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-[11px] font-mono">
                              <span className={getUsageColorClass(fs.usage_percent).split(' ')[1]}>
                                {fs.usage_percent}%
                              </span>
                            </div>
                            <div className="w-full bg-neutral-800 rounded-full h-1.5 overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all duration-300 ${
                                  getUsageColorClass(fs.usage_percent).split(' ')[0]
                                }`}
                                style={{ width: `${Math.min(fs.usage_percent, 100)}%` }}
                              />
                            </div>
                          </div>
                        ) : (
                          <span className="text-neutral-500 font-mono text-[11px]">N/A</span>
                        )}
                      </td>
                      <td className="py-2.5 px-4 font-mono text-neutral-400 text-[11px] max-w-[150px] truncate">
                        {fs.label ? (
                          <span className="text-neutral-200">{fs.label}</span>
                        ) : fs.uuid ? (
                          <span className="text-neutral-400">{fs.uuid}</span>
                        ) : (
                          <span className="text-neutral-600">—</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Block Devices Table / Tree */
        <div className="border border-neutral-800 rounded-lg overflow-hidden bg-neutral-900">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-neutral-950/80 border-b border-neutral-800 text-[11px] font-mono text-neutral-400 uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Device</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Model / Vendor</th>
                  <th className="py-3 px-4">Size</th>
                  <th className="py-3 px-4">Mount Point</th>
                  <th className="py-3 px-4">Filesystem</th>
                  <th className="py-3 px-4">Flags</th>
                  <th className="py-3 px-4">UUID / Label</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800/60 font-sans">
                {filteredDevices.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-neutral-400 text-xs font-mono">
                      No block devices matched your filter criteria
                    </td>
                  </tr>
                ) : (
                  filteredDevices.map((dev) => (
                    <React.Fragment key={dev.name}>
                      {/* Main Device Row */}
                      <tr className="hover:bg-neutral-850/60 transition-colors bg-neutral-900/90 font-medium">
                        <td className="py-3 px-4 font-mono text-white flex items-center gap-1.5">
                          {dev.children && dev.children.length > 0 ? (
                            <button
                              onClick={() => toggleDeviceExpand(dev.name)}
                              className="p-0.5 hover:bg-neutral-800 rounded text-neutral-400 hover:text-white"
                            >
                              {expandedDevices[dev.name] ? (
                                <ChevronDown className="w-3.5 h-3.5" />
                              ) : (
                                <ChevronRight className="w-3.5 h-3.5" />
                              )}
                            </button>
                          ) : (
                            <Disc className="w-3.5 h-3.5 text-neutral-400 shrink-0 ml-1" />
                          )}
                          <span>{dev.name}</span>
                          <span className="text-[10px] text-neutral-400 font-mono">({dev.path})</span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-1.5 py-0.5 bg-neutral-800 border border-neutral-700 text-neutral-300 rounded text-[10px] font-mono uppercase">
                            {dev.device_type}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-neutral-300">
                          {dev.model ? (
                            <span>
                              {dev.vendor ? `${dev.vendor} ` : ''}
                              {dev.model}
                            </span>
                          ) : dev.vendor ? (
                            <span>{dev.vendor}</span>
                          ) : (
                            <span className="text-neutral-500 font-mono">—</span>
                          )}
                        </td>
                        <td className="py-3 px-4 font-mono text-white font-semibold">
                          {dev.size_bytes > 0 ? formatBytes(dev.size_bytes) : '—'}
                        </td>
                        <td className="py-3 px-4 font-mono text-neutral-300">
                          {dev.mount_point ? (
                            <span className="text-emerald-400">{dev.mount_point}</span>
                          ) : (
                            <span className="text-neutral-500">—</span>
                          )}
                        </td>
                        <td className="py-3 px-4 font-mono text-neutral-300">
                          {dev.filesystem || <span className="text-neutral-500">—</span>}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-1.5">
                            {dev.is_read_only && (
                              <span className="px-1.5 py-0.5 bg-amber-950/80 border border-amber-800/60 text-amber-300 rounded text-[10px] font-mono">
                                RO
                              </span>
                            )}
                            {dev.is_removable && (
                              <span className="px-1.5 py-0.5 bg-sky-950/80 border border-sky-800/60 text-sky-300 rounded text-[10px] font-mono">
                                Removable
                              </span>
                            )}
                            {!dev.is_read_only && !dev.is_removable && (
                              <span className="text-neutral-500 font-mono text-[11px]">rw</span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4 font-mono text-neutral-400 text-[11px] max-w-[150px] truncate">
                          {dev.label || dev.uuid || <span className="text-neutral-600">—</span>}
                        </td>
                      </tr>

                      {/* Child Partitions */}
                      {expandedDevices[dev.name] &&
                        dev.children.map((part) => (
                          <tr
                            key={part.name}
                            className="bg-neutral-950/40 hover:bg-neutral-850/40 text-neutral-300 text-xs border-t border-neutral-850"
                          >
                            <td className="py-2.5 px-4 pl-9 font-mono flex items-center gap-1.5">
                              <span className="text-neutral-600 font-mono">└─</span>
                              <span className="text-neutral-200">{part.name}</span>
                              <span className="text-[10px] text-neutral-400 font-mono">({part.path})</span>
                            </td>
                            <td className="py-2.5 px-4">
                              <span className="px-1.5 py-0.5 bg-neutral-900 border border-neutral-800 text-neutral-400 rounded text-[10px] font-mono uppercase">
                                part
                              </span>
                            </td>
                            <td className="py-2.5 px-4 text-neutral-500 font-mono text-[11px]">
                              Partition of {dev.name}
                            </td>
                            <td className="py-2.5 px-4 font-mono text-neutral-300">
                              {part.size_bytes > 0 ? formatBytes(part.size_bytes) : '—'}
                            </td>
                            <td className="py-2.5 px-4 font-mono">
                              {part.mount_point ? (
                                <span className="text-emerald-400 font-medium">{part.mount_point}</span>
                              ) : (
                                <span className="text-neutral-500">Unmounted</span>
                              )}
                            </td>
                            <td className="py-2.5 px-4 font-mono text-neutral-300">
                              {part.filesystem || <span className="text-neutral-500">—</span>}
                            </td>
                            <td className="py-2.5 px-4">
                              {part.is_read_only ? (
                                <span className="px-1.5 py-0.5 bg-amber-950/80 border border-amber-800/60 text-amber-300 rounded text-[10px] font-mono">
                                  RO
                                </span>
                              ) : (
                                <span className="text-neutral-500 font-mono text-[11px]">rw</span>
                              )}
                            </td>
                            <td className="py-2.5 px-4 font-mono text-neutral-400 text-[11px] max-w-[150px] truncate">
                              {part.label ? (
                                <span className="text-neutral-200">{part.label}</span>
                              ) : part.uuid ? (
                                <span className="text-neutral-400">{part.uuid}</span>
                              ) : (
                                <span className="text-neutral-600">—</span>
                              )}
                            </td>
                          </tr>
                        ))}
                    </React.Fragment>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
