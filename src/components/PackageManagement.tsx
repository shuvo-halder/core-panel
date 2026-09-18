import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowUpDown,
  Boxes,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  ExternalLink,
  Eye,
  FileCode,
  HardDrive,
  Info,
  Layers,
  Package,
  RefreshCw,
  Search,
  Server,
  Shield,
  Tag,
  X,
} from 'lucide-react';
import { apiClient } from '../api/client';
import {
  PackageDetails,
  PackageItem,
  PackageOverview,
  PackageUpdateInfo,
  RepositoryInfo,
} from '../types/packages';

export const PackageManagement: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'packages' | 'repositories' | 'updates'>('packages');

  // Data states
  const [overview, setOverview] = useState<PackageOverview | null>(null);
  const [packages, setPackages] = useState<PackageItem[]>([]);
  const [totalPackages, setTotalPackages] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [repositories, setRepositories] = useState<RepositoryInfo[]>([]);
  const [updates, setUpdates] = useState<PackageUpdateInfo[]>([]);

  // Selected package for detail inspection
  const [selectedPackage, setSelectedPackage] = useState<PackageDetails | null>(null);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(false);

  // Filter & Pagination states
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [sortBy, setSortBy] = useState<string>('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Loading & error states
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState<number>(0);

  const fetchOverview = useCallback(async () => {
    try {
      const data = await apiClient.getPackagesOverview();
      setOverview(data);
    } catch (err: any) {
      console.error('Failed to fetch package overview:', err);
    }
  }, []);

  const fetchPackages = useCallback(async () => {
    try {
      const data = await apiClient.getPackages({
        page,
        page_size: pageSize,
        search: searchTerm.trim() || undefined,
        sort: sortBy,
        order: sortOrder,
      });
      setPackages(data.items);
      setTotalPackages(data.total);
      setTotalPages(data.total_pages);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch package inventory');
    }
  }, [page, pageSize, searchTerm, sortBy, sortOrder]);

  const fetchRepositories = useCallback(async () => {
    try {
      const data = await apiClient.getPackageRepositories();
      setRepositories(data);
    } catch (err: any) {
      console.error('Failed to fetch package repositories:', err);
    }
  }, []);

  const fetchUpdates = useCallback(async () => {
    try {
      const data = await apiClient.getPackageUpdates();
      setUpdates(data);
    } catch (err: any) {
      console.error('Failed to fetch package updates:', err);
    }
  }, []);

  const loadAllData = useCallback(async (isInitial = false) => {
    if (isInitial) setLoading(true);
    else setRefreshing(true);
    setError(null);

    try {
      await Promise.all([fetchOverview(), fetchPackages(), fetchRepositories(), fetchUpdates()]);
    } catch (err: any) {
      setError(err?.message || 'Failed to communicate with package management API');
    } finally {
      if (isInitial) setLoading(false);
      else setRefreshing(false);
    }
  }, [fetchOverview, fetchPackages, fetchRepositories, fetchUpdates]);

  // Initial load
  useEffect(() => {
    loadAllData(true);
  }, [loadAllData]);

  // Handle auto-refresh interval
  useEffect(() => {
    if (autoRefreshInterval <= 0) return;

    const interval = setInterval(() => {
      loadAllData(false);
    }, autoRefreshInterval * 1000);

    return () => clearInterval(interval);
  }, [autoRefreshInterval, loadAllData]);

  // Fetch package details on modal click
  const handleInspectPackage = async (name: string) => {
    setLoadingDetails(true);
    try {
      const details = await apiClient.getPackage(name);
      setSelectedPackage(details);
    } catch (err: any) {
      console.error('Failed to load package details:', err);
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
    setPage(1);
  };

  const formatSize = (kb?: number | null) => {
    if (kb === undefined || kb === null) return '—';
    if (kb < 1024) return `${kb} KB`;
    return `${(kb / 1024).toFixed(1)} MB`;
  };

  const filteredPackages = packages.filter((pkg) => {
    if (statusFilter === 'all') return true;
    return pkg.status.toLowerCase().includes(statusFilter.toLowerCase());
  });

  return (
    <div id="package-management-root" className="space-y-6">
      {/* Header with Title and Global Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-neutral-800">
        <div>
          <h2 className="text-xl font-semibold text-white flex items-center gap-2">
            <Package className="w-5 h-5 text-neutral-400" />
            Package Management Foundation
          </h2>
          <p className="text-xs text-neutral-400 mt-1">
            Read-only operating system package inventory, repositories, and cached update status.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Auto Refresh Interval */}
          <div className="flex items-center gap-1.5 bg-neutral-900 border border-neutral-800 rounded-md px-2.5 py-1.5 text-xs text-neutral-300">
            <Clock className="w-3.5 h-3.5 text-neutral-400" />
            <span className="text-neutral-400">Refresh:</span>
            <select
              id="package-auto-refresh-select"
              value={autoRefreshInterval}
              onChange={(e) => setAutoRefreshInterval(Number(e.target.value))}
              aria-label="Auto-refresh interval"
              className="bg-transparent border-0 text-white font-medium focus:ring-0 focus:outline-none cursor-pointer"
            >
              <option value={0} className="bg-neutral-900 text-white">Manual</option>
              <option value={10} className="bg-neutral-900 text-white">10s</option>
              <option value={30} className="bg-neutral-900 text-white">30s</option>
              <option value={60} className="bg-neutral-900 text-white">60s</option>
            </select>
          </div>

          {/* Refresh Button */}
          <button
            id="package-manual-refresh-btn"
            onClick={() => loadAllData(false)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-neutral-800 hover:bg-neutral-700 text-neutral-200 border border-neutral-700 rounded-md transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/80 rounded-md text-red-200 text-xs flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
          <div className="flex-1">
            <div className="font-semibold">Package Collector Warning</div>
            <div className="text-red-300/90">{error}</div>
          </div>
        </div>
      )}

      {/* High-Level Overview KPI Cards */}
      {overview && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-400 font-medium">Package Manager</span>
              <Server className="w-4 h-4 text-blue-400" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-xl font-bold text-white uppercase">{overview.manager}</span>
              <span className="text-xs text-neutral-400 uppercase">({overview.family})</span>
            </div>
            <div className="text-[11px] text-neutral-400 mt-1 truncate" title={overview.distribution}>
              {overview.distribution} ({overview.architecture})
            </div>
          </div>

          <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-400 font-medium">Installed Packages</span>
              <Boxes className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="mt-2 text-xl font-bold text-white">
              {overview.installed_package_count.toLocaleString()}
            </div>
            <div className="text-[11px] text-emerald-400/90 mt-1 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              <span>Database readable</span>
            </div>
          </div>

          <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-400 font-medium">Software Repositories</span>
              <Layers className="w-4 h-4 text-purple-400" />
            </div>
            <div className="mt-2 text-xl font-bold text-white">
              {overview.repository_count}
            </div>
            <div className="text-[11px] text-neutral-400 mt-1">
              Configured sources / channels
            </div>
          </div>

          <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-400 font-medium">Status & Safety</span>
              <Shield className="w-4 h-4 text-amber-400" />
            </div>
            <div className="mt-2 flex items-center gap-1.5">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-950/60 border border-amber-800/60 text-amber-300">
                Read-Only Mode
              </span>
            </div>
            <div className="text-[11px] text-neutral-400 mt-1 truncate" title="Zero mutation guaranteed">
              CoreAgent operations: 0
            </div>
          </div>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-2 border-b border-neutral-800">
        <button
          id="tab-packages-btn"
          onClick={() => setActiveSubTab('packages')}
          className={`pb-2.5 px-3 text-xs font-medium transition border-b-2 flex items-center gap-2 ${
            activeSubTab === 'packages'
              ? 'border-blue-500 text-white font-semibold'
              : 'border-transparent text-neutral-400 hover:text-neutral-200'
          }`}
        >
          <Package className="w-4 h-4" />
          <span>Installed Packages ({totalPackages.toLocaleString()})</span>
        </button>

        <button
          id="tab-repositories-btn"
          onClick={() => setActiveSubTab('repositories')}
          className={`pb-2.5 px-3 text-xs font-medium transition border-b-2 flex items-center gap-2 ${
            activeSubTab === 'repositories'
              ? 'border-blue-500 text-white font-semibold'
              : 'border-transparent text-neutral-400 hover:text-neutral-200'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Repositories ({repositories.length})</span>
        </button>

        <button
          id="tab-updates-btn"
          onClick={() => setActiveSubTab('updates')}
          className={`pb-2.5 px-3 text-xs font-medium transition border-b-2 flex items-center gap-2 ${
            activeSubTab === 'updates'
              ? 'border-blue-500 text-white font-semibold'
              : 'border-transparent text-neutral-400 hover:text-neutral-200'
          }`}
        >
          <Info className="w-4 h-4" />
          <span>Available Updates ({updates.length})</span>
        </button>
      </div>

      {/* Sub-Tab 1: Installed Packages */}
      {activeSubTab === 'packages' && (
        <div className="space-y-4">
          {/* Search, Status Filter & Page Size Bar */}
          <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
            <div className="flex-1 relative">
              <Search className="w-4 h-4 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                id="package-search-input"
                type="text"
                placeholder="Search by package name, summary, or source..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setPage(1);
                }}
                className="w-full pl-9 pr-4 py-2 bg-neutral-900 border border-neutral-800 rounded-md text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-blue-500 transition"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                id="package-status-filter"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                aria-label="Filter packages by status"
                className="bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-xs text-neutral-300 focus:outline-none focus:border-blue-500"
              >
                <option value="all">All Statuses</option>
                <option value="installed">Installed</option>
                <option value="config-files">Config Files</option>
              </select>

              <select
                id="package-page-size-select"
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                aria-label="Packages per page"
                className="bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-xs text-neutral-300 focus:outline-none focus:border-blue-500"
              >
                <option value={25}>25 / page</option>
                <option value={50}>50 / page</option>
                <option value={100}>100 / page</option>
                <option value={200}>200 / page</option>
              </select>
            </div>
          </div>

          {/* Packages Table */}
          <div className="overflow-x-auto rounded-lg border border-neutral-800 bg-neutral-900/60">
            <table className="w-full text-left text-xs text-neutral-300">
              <thead className="bg-neutral-900 border-b border-neutral-800 text-neutral-400 uppercase font-mono text-[11px]">
                <tr>
                  <th
                    className="px-4 py-3 cursor-pointer hover:text-white transition"
                    onClick={() => handleSort('name')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Package Name</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th
                    className="px-4 py-3 cursor-pointer hover:text-white transition"
                    onClick={() => handleSort('version')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Version</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th className="px-4 py-3">Architecture</th>
                  <th className="px-4 py-3">Status</th>
                  <th
                    className="px-4 py-3 cursor-pointer hover:text-white transition"
                    onClick={() => handleSort('installed_size_kb')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Size</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th className="px-4 py-3">Summary</th>
                  <th className="px-4 py-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800/60 font-sans">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-12 text-center text-neutral-400">
                      <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                      Loading package inventory...
                    </td>
                  </tr>
                ) : filteredPackages.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-neutral-400">
                      No packages found matching search criteria.
                    </td>
                  </tr>
                ) : (
                  filteredPackages.map((pkg) => (
                    <tr
                      key={`${pkg.name}-${pkg.version}`}
                      className="hover:bg-neutral-800/40 transition group"
                    >
                      <td className="px-4 py-3 font-mono font-medium text-white flex items-center gap-2">
                        <Package className="w-3.5 h-3.5 text-neutral-500 group-hover:text-blue-400 transition" />
                        <span>{pkg.name}</span>
                      </td>
                      <td className="px-4 py-3 font-mono text-neutral-300">{pkg.version}</td>
                      <td className="px-4 py-3 text-neutral-400">{pkg.architecture}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider ${
                            pkg.status === 'installed'
                              ? 'bg-emerald-950/60 border border-emerald-800/60 text-emerald-300'
                              : 'bg-neutral-800 border border-neutral-700 text-neutral-300'
                          }`}
                        >
                          {pkg.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-neutral-400">{formatSize(pkg.installed_size_kb)}</td>
                      <td className="px-4 py-3 text-neutral-400 max-w-xs truncate" title={pkg.summary}>
                        {pkg.summary || '—'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleInspectPackage(pkg.name)}
                          className="p-1 text-neutral-400 hover:text-blue-400 hover:bg-neutral-800 rounded transition"
                          title="Inspect Package Details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-neutral-400 pt-2">
            <div>
              Showing {filteredPackages.length > 0 ? (page - 1) * pageSize + 1 : 0} to{' '}
              {Math.min(page * pageSize, totalPackages)} of {totalPackages.toLocaleString()} packages
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || loading}
                className="px-3 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 border border-neutral-700 disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center gap-1"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Previous
              </button>

              <span className="px-2 font-mono text-white">
                Page {page} of {totalPages}
              </span>

              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || loading}
                className="px-3 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 border border-neutral-700 disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center gap-1"
              >
                Next
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sub-Tab 2: Repositories */}
      {activeSubTab === 'repositories' && (
        <div className="space-y-4">
          <div className="p-3 bg-neutral-900/80 border border-neutral-800 rounded-md text-xs text-neutral-400 flex items-center gap-2">
            <Info className="w-4 h-4 text-blue-400 shrink-0" />
            <span>
              Configured package repositories and software channels parsed directly from system configuration files.
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {repositories.length === 0 ? (
              <div className="col-span-2 p-8 text-center text-neutral-400 bg-neutral-900/40 border border-neutral-800 rounded-lg">
                No software repositories detected or configured.
              </div>
            ) : (
              repositories.map((repo, idx) => (
                <div
                  key={`${repo.uri}-${idx}`}
                  className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="text-sm font-semibold text-white font-mono flex items-center gap-2">
                        <Layers className="w-4 h-4 text-purple-400" />
                        <span>{repo.name}</span>
                      </h4>
                      <div className="text-[11px] text-neutral-400 font-mono mt-0.5">{repo.uri}</div>
                    </div>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium uppercase ${
                        repo.enabled
                          ? 'bg-emerald-950/60 border border-emerald-800/60 text-emerald-300'
                          : 'bg-neutral-800 border border-neutral-700 text-neutral-400'
                      }`}
                    >
                      {repo.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-neutral-800/60">
                    <div>
                      <span className="text-neutral-500">Type:</span>{' '}
                      <span className="font-mono text-neutral-300 uppercase">{repo.type}</span>
                    </div>
                    {repo.distribution && (
                      <div>
                        <span className="text-neutral-500">Distribution / Suite:</span>{' '}
                        <span className="font-mono text-neutral-300">{repo.distribution}</span>
                      </div>
                    )}
                  </div>

                  {repo.components && repo.components.length > 0 && (
                    <div className="pt-2 border-t border-neutral-800/60">
                      <span className="text-xs text-neutral-500 block mb-1.5">Components:</span>
                      <div className="flex flex-wrap gap-1.5">
                        {repo.components.map((comp) => (
                          <span
                            key={comp}
                            className="px-2 py-0.5 bg-neutral-800 text-neutral-300 font-mono text-[10px] rounded border border-neutral-700"
                          >
                            {comp}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {repo.source_file && (
                    <div className="text-[10px] text-neutral-500 font-mono pt-1">
                      File: {repo.source_file}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Sub-Tab 3: Available Updates */}
      {activeSubTab === 'updates' && (
        <div className="space-y-4">
          <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg space-y-2">
            <div className="flex items-center gap-2 text-amber-400 text-xs font-semibold">
              <Shield className="w-4 h-4" />
              <span>Strict Read-Only Guarantee</span>
            </div>
            <p className="text-xs text-neutral-300 leading-relaxed">
              {overview?.update_status_message ||
                'Package updates are evaluated strictly against cached operating system metadata. Phase 8 will never invoke mutating package refresh commands (such as apt update or dnf makecache).'}
            </p>
          </div>

          {updates.length === 0 ? (
            <div className="p-12 text-center bg-neutral-900/40 border border-neutral-800 rounded-lg text-neutral-400 space-y-2">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
              <div className="text-sm font-medium text-white">No pending package updates in cached metadata</div>
              <p className="text-xs text-neutral-400 max-w-md mx-auto">
                All installed packages match current cached repository candidates.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-neutral-800 bg-neutral-900">
              <table className="w-full text-left text-xs text-neutral-300">
                <thead className="bg-neutral-900 border-b border-neutral-800 text-neutral-400 uppercase font-mono text-[11px]">
                  <tr>
                    <th className="px-4 py-3">Package</th>
                    <th className="px-4 py-3">Installed Version</th>
                    <th className="px-4 py-3">Candidate Version</th>
                    <th className="px-4 py-3">Repository</th>
                    <th className="px-4 py-3">Urgency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800 font-sans">
                  {updates.map((u) => (
                    <tr key={u.name} className="hover:bg-neutral-800/40 transition">
                      <td className="px-4 py-3 font-mono font-medium text-white">{u.name}</td>
                      <td className="px-4 py-3 font-mono text-neutral-400">{u.installed_version}</td>
                      <td className="px-4 py-3 font-mono text-emerald-400 font-semibold">{u.candidate_version}</td>
                      <td className="px-4 py-3 text-neutral-400">{u.repository || '—'}</td>
                      <td className="px-4 py-3">
                        {u.urgency ? (
                          <span className="px-2 py-0.5 bg-amber-950/60 border border-amber-800/60 text-amber-300 rounded text-[10px] uppercase font-mono">
                            {u.urgency}
                          </span>
                        ) : (
                          <span className="text-neutral-500">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Package Detail Modal */}
      {selectedPackage && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-neutral-800">
              <div className="flex items-center gap-2">
                <Package className="w-5 h-5 text-blue-400" />
                <h3 className="text-base font-semibold text-white font-mono">{selectedPackage.name}</h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-neutral-800 text-neutral-300 border border-neutral-700">
                  {selectedPackage.version}
                </span>
              </div>
              <button
                onClick={() => setSelectedPackage(null)}
                className="text-neutral-400 hover:text-white p-1 rounded transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto space-y-4 text-xs">
              {/* Properties Grid */}
              <div className="grid grid-cols-2 gap-3 p-4 bg-neutral-950 rounded border border-neutral-800">
                <div>
                  <span className="text-neutral-500 block">Architecture:</span>
                  <span className="font-mono text-white">{selectedPackage.architecture}</span>
                </div>
                <div>
                  <span className="text-neutral-500 block">Status:</span>
                  <span className="font-mono text-emerald-400 uppercase">{selectedPackage.status}</span>
                </div>
                <div>
                  <span className="text-neutral-500 block">Installed Size:</span>
                  <span className="font-mono text-white">{formatSize(selectedPackage.installed_size_kb)}</span>
                </div>
                <div>
                  <span className="text-neutral-500 block">Section:</span>
                  <span className="font-mono text-neutral-300">{selectedPackage.section || '—'}</span>
                </div>
                {selectedPackage.source && (
                  <div>
                    <span className="text-neutral-500 block">Source Package:</span>
                    <span className="font-mono text-neutral-300">{selectedPackage.source}</span>
                  </div>
                )}
                {selectedPackage.homepage && (
                  <div className="col-span-2 truncate">
                    <span className="text-neutral-500 block">Homepage:</span>
                    <a
                      href={selectedPackage.homepage}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:underline flex items-center gap-1 mt-0.5"
                    >
                      <span>{selectedPackage.homepage}</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                )}
              </div>

              {/* Summary & Description */}
              <div>
                <h4 className="text-neutral-400 font-semibold uppercase tracking-wider text-[11px] mb-1">
                  Summary
                </h4>
                <p className="text-neutral-200">{selectedPackage.summary || 'No summary provided.'}</p>
              </div>

              {selectedPackage.description && (
                <div>
                  <h4 className="text-neutral-400 font-semibold uppercase tracking-wider text-[11px] mb-1">
                    Full Description
                  </h4>
                  <pre className="p-3 bg-neutral-950 rounded border border-neutral-800 text-neutral-300 font-sans text-xs whitespace-pre-wrap leading-relaxed">
                    {selectedPackage.description}
                  </pre>
                </div>
              )}

              {/* Dependencies */}
              {selectedPackage.dependencies && selectedPackage.dependencies.length > 0 && (
                <div>
                  <h4 className="text-neutral-400 font-semibold uppercase tracking-wider text-[11px] mb-2">
                    Dependencies ({selectedPackage.dependencies.length})
                  </h4>
                  <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-2 bg-neutral-950 rounded border border-neutral-800">
                    {selectedPackage.dependencies.map((dep, dIdx) => (
                      <span
                        key={`${dep}-${dIdx}`}
                        className="px-2 py-0.5 bg-neutral-800 border border-neutral-700 text-neutral-300 font-mono text-[10px] rounded"
                      >
                        {dep}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedPackage.maintainer && (
                <div className="text-[11px] text-neutral-500">
                  <span className="text-neutral-400 font-medium">Maintainer:</span> {selectedPackage.maintainer}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-neutral-800 flex justify-end">
              <button
                onClick={() => setSelectedPackage(null)}
                className="px-4 py-2 bg-neutral-800 hover:bg-neutral-700 text-white rounded text-xs font-medium transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
