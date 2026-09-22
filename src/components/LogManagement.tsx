import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  FileText,
  Shield,
  RefreshCw,
  Search,
  Filter,
  AlertCircle,
  AlertTriangle,
  Info,
  CheckCircle2,
  Clock,
  HardDrive,
  Terminal,
  ChevronLeft,
  ChevronRight,
  Eye,
  X,
  Copy,
  Check,
} from 'lucide-react';
import { apiClient, ApiError } from '../api/client';
import {
  AuditLogEntry,
  LogEntry,
  LogOverview,
  LogSource,
  LogSeverityLevel,
} from '../types/logs';

interface LogManagementProps {
  permissions: string[];
}

type TabType = 'system_logs' | 'sources' | 'audit_logs';

export const LogManagement: React.FC<LogManagementProps> = ({ permissions }) => {
  const canReadLogs = permissions.includes('logs.read') || permissions.includes('*');
  const canReadAudit = permissions.includes('audit.read') || permissions.includes('*');

  // Default active tab based on permissions
  const [activeTab, setActiveTab] = useState<TabType>(canReadLogs ? 'system_logs' : 'audit_logs');

  // Overview state
  const [overview, setOverview] = useState<LogOverview | null>(null);
  const [sources, setSources] = useState<LogSource[]>([]);
  const [loadingOverview, setLoadingOverview] = useState(false);

  // System logs query state
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [totalLogs, setTotalLogs] = useState(0);
  const [logsPage, setLogsPage] = useState(1);
  const [logsPageSize, setLogsPageSize] = useState(50);
  const [loadingLogs, setLoadingLogs] = useState(false);

  // System logs filters
  const [filterSource, setFilterSource] = useState<string>('');
  const [filterSeverity, setFilterSeverity] = useState<string>('');
  const [filterService, setFilterService] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeSearch, setActiveSearch] = useState<string>('');

  // Audit logs query state
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [totalAuditLogs, setTotalAuditLogs] = useState(0);
  const [auditPage, setAuditPage] = useState(1);
  const [auditPageSize, setAuditPageSize] = useState(50);
  const [loadingAudit, setLoadingAudit] = useState(false);

  // Audit filters
  const [auditSearch, setAuditSearch] = useState<string>('');
  const [auditAction, setAuditAction] = useState<string>('');
  const [auditStatus, setAuditStatus] = useState<string>('');

  // Selected entry for detail modal
  const [selectedEntry, setSelectedEntry] = useState<LogEntry | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch Overview and Sources
  const fetchOverviewAndSources = useCallback(async () => {
    if (!canReadLogs) return;
    setLoadingOverview(true);
    setError(null);
    try {
      const [overviewData, sourcesData] = await Promise.all([
        apiClient.getLogsOverview(),
        apiClient.getLogSources(),
      ]);
      setOverview(overviewData);
      setSources(sourcesData);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr.message || 'Failed to load log overview');
    } finally {
      setLoadingOverview(false);
    }
  }, [canReadLogs]);

  // Fetch System Logs
  const fetchSystemLogs = useCallback(async () => {
    if (!canReadLogs) return;
    setLoadingLogs(true);
    setError(null);
    try {
      const res = await apiClient.getLogs({
        source: filterSource || undefined,
        severity: filterSeverity || undefined,
        service: filterService.trim() || undefined,
        search: activeSearch.trim() || undefined,
        page: logsPage,
        page_size: logsPageSize,
      });
      setLogs(res.items);
      setTotalLogs(res.total);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr.message || 'Failed to fetch system logs');
    } finally {
      setLoadingLogs(false);
    }
  }, [canReadLogs, filterSource, filterSeverity, filterService, activeSearch, logsPage, logsPageSize]);

  // Fetch Audit Logs
  const fetchAuditLogs = useCallback(async () => {
    if (!canReadAudit) return;
    setLoadingAudit(true);
    setError(null);
    try {
      const res = await apiClient.getAuditLogs({
        search: auditSearch.trim() || undefined,
        action: auditAction.trim() || undefined,
        status: auditStatus || undefined,
        page: auditPage,
        page_size: auditPageSize,
      });
      setAuditLogs(res.items);
      setTotalAuditLogs(res.total);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr.message || 'Failed to fetch application audit logs');
    } finally {
      setLoadingAudit(false);
    }
  }, [canReadAudit, auditSearch, auditAction, auditStatus, auditPage, auditPageSize]);

  // Initial load
  useEffect(() => {
    if (canReadLogs) {
      fetchOverviewAndSources();
      fetchSystemLogs();
    }
    if (canReadAudit) {
      fetchAuditLogs();
    }
  }, [canReadLogs, canReadAudit, fetchOverviewAndSources, fetchSystemLogs, fetchAuditLogs]);

  // Refresh active view
  const handleRefresh = () => {
    if (activeTab === 'system_logs') {
      fetchSystemLogs();
      fetchOverviewAndSources();
    } else if (activeTab === 'sources') {
      fetchOverviewAndSources();
    } else if (activeTab === 'audit_logs') {
      fetchAuditLogs();
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLogsPage(1);
    setActiveSearch(searchQuery);
  };

  const handleResetFilters = () => {
    setFilterSource('');
    setFilterSeverity('');
    setFilterService('');
    setSearchQuery('');
    setActiveSearch('');
    setLogsPage(1);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Severity color formatting helper
  const getSeverityBadgeClass = (severity: string) => {
    const s = severity.toUpperCase();
    switch (s) {
      case 'EMERG':
      case 'ALERT':
      case 'CRIT':
        return 'bg-red-950/80 text-red-300 border-red-800';
      case 'ERR':
        return 'bg-rose-950/80 text-rose-300 border-rose-800';
      case 'WARNING':
        return 'bg-amber-950/80 text-amber-300 border-amber-800';
      case 'NOTICE':
      case 'INFO':
        return 'bg-sky-950/80 text-sky-300 border-sky-800';
      case 'DEBUG':
        return 'bg-neutral-800 text-neutral-400 border-neutral-700';
      default:
        return 'bg-neutral-800 text-neutral-300 border-neutral-700';
    }
  };

  const errorCount = useMemo(() => {
    if (!overview) return 0;
    const counts = overview.severity_counts;
    return (
      (counts['EMERG'] || 0) +
      (counts['ALERT'] || 0) +
      (counts['CRIT'] || 0) +
      (counts['ERR'] || 0)
    );
  }, [overview]);

  return (
    <div id="log-management-container" className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-neutral-800 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-white flex items-center gap-2">
            <FileText className="w-5 h-5 text-indigo-400" />
            System &amp; Audit Logs
          </h1>
          <p className="text-xs text-neutral-400 mt-1">
            Read-only, bounded inspection of host journalctl events, allowlisted system logs, and control-plane audit history.
          </p>
        </div>

        <button
          id="btn-refresh-logs"
          onClick={handleRefresh}
          disabled={loadingLogs || loadingOverview || loadingAudit}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-neutral-300 bg-neutral-800 hover:bg-neutral-700 hover:text-white border border-neutral-700 rounded-md transition disabled:opacity-50"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 ${loadingLogs || loadingOverview || loadingAudit ? 'animate-spin' : ''}`}
          />
          Refresh
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="p-3 bg-red-950/60 border border-red-800/80 rounded-lg flex items-start gap-2.5 text-xs text-red-200">
          <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="font-medium">{error}</p>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-red-400 hover:text-red-200 text-xs"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* KPI Overview Cards */}
      {canReadLogs && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-neutral-900 p-4 rounded-lg border border-neutral-800">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400">
                systemd Journal
              </span>
              <Terminal className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="mt-2.5 flex items-center gap-2">
              <span
                className={`inline-block w-2.5 h-2.5 rounded-full ${
                  overview?.journal_available ? 'bg-emerald-400' : 'bg-neutral-500'
                }`}
              />
              <span className="text-base font-semibold text-neutral-100">
                {overview?.journal_available ? 'Active & Ready' : 'Unavailable'}
              </span>
            </div>
            <p className="text-[11px] text-neutral-400 mt-1">
              {overview?.journal_available
                ? 'Central binary journal accessible'
                : 'journalctl binary not detected'}
            </p>
          </div>

          <div className="bg-neutral-900 p-4 rounded-lg border border-neutral-800">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400">
                Active Sources
              </span>
              <HardDrive className="w-4 h-4 text-sky-400" />
            </div>
            <div className="mt-2.5">
              <span className="text-2xl font-bold text-white">
                {overview?.active_sources_count || 0}
              </span>
              <span className="text-xs text-neutral-400 ml-1.5">
                / {overview?.total_sources_count || 0} configured
              </span>
            </div>
            <p className="text-[11px] text-neutral-400 mt-1">Allowlisted file and journal streams</p>
          </div>

          <div className="bg-neutral-900 p-4 rounded-lg border border-neutral-800">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400">
                Recent Critical / Errors
              </span>
              <AlertTriangle className="w-4 h-4 text-rose-400" />
            </div>
            <div className="mt-2.5">
              <span
                className={`text-2xl font-bold ${
                  errorCount > 0 ? 'text-rose-400' : 'text-neutral-100'
                }`}
              >
                {errorCount}
              </span>
              <span className="text-[11px] text-neutral-400 ml-2">in latest window</span>
            </div>
            <p className="text-[11px] text-neutral-400 mt-1">
              ERR, CRIT, ALERT, EMERG events
            </p>
          </div>

          <div className="bg-neutral-900 p-4 rounded-lg border border-neutral-800">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400">
                Latest Activity
              </span>
              <Clock className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="mt-2.5">
              <p className="text-sm font-semibold text-neutral-100 truncate" title={overview?.latest_timestamp || 'No logs recorded'}>
                {overview?.latest_timestamp
                  ? new Date(overview.latest_timestamp).toLocaleTimeString(undefined, {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })
                  : 'None'}
              </p>
            </div>
            <p className="text-[11px] text-neutral-400 mt-1 truncate">
              {overview?.latest_timestamp
                ? new Date(overview.latest_timestamp).toLocaleDateString()
                : 'No entries discovered'}
            </p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-neutral-800">
        <nav className="flex space-x-6" aria-label="Tabs">
          {canReadLogs && (
            <button
              onClick={() => setActiveTab('system_logs')}
              className={`py-2.5 px-1 border-b-2 font-medium text-xs inline-flex items-center gap-2 transition ${
                activeTab === 'system_logs'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-neutral-400 hover:text-neutral-200 hover:border-neutral-700'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              System Logs Stream
            </button>
          )}

          {canReadLogs && (
            <button
              onClick={() => setActiveTab('sources')}
              className={`py-2.5 px-1 border-b-2 font-medium text-xs inline-flex items-center gap-2 transition ${
                activeTab === 'sources'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-neutral-400 hover:text-neutral-200 hover:border-neutral-700'
              }`}
            >
              <HardDrive className="w-3.5 h-3.5" />
              Log Sources ({sources.length})
            </button>
          )}

          {canReadAudit && (
            <button
              onClick={() => setActiveTab('audit_logs')}
              className={`py-2.5 px-1 border-b-2 font-medium text-xs inline-flex items-center gap-2 transition ${
                activeTab === 'audit_logs'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-neutral-400 hover:text-neutral-200 hover:border-neutral-700'
              }`}
            >
              <Shield className="w-3.5 h-3.5" />
              Application Audit Log
            </button>
          )}
        </nav>
      </div>

      {/* TAB 1: SYSTEM LOGS STREAM */}
      {activeTab === 'system_logs' && canReadLogs && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="bg-neutral-900 p-3.5 rounded-lg border border-neutral-800 space-y-3">
            <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row gap-2.5">
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Search logs by message, service, hostname... (press Enter)"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  maxLength={100}
                  className="w-full pl-8 pr-3 py-1.5 text-xs bg-neutral-950 border border-neutral-700 rounded-md text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {/* Source Filter */}
                <select
                  value={filterSource}
                  onChange={(e) => {
                    setFilterSource(e.target.value);
                    setLogsPage(1);
                  }}
                  className="text-xs bg-neutral-950 border border-neutral-700 rounded-md px-2.5 py-1.5 text-neutral-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="">All Sources</option>
                  {sources.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} {s.available ? '' : '(Not Present)'}
                    </option>
                  ))}
                </select>

                {/* Severity Filter */}
                <select
                  value={filterSeverity}
                  onChange={(e) => {
                    setFilterSeverity(e.target.value);
                    setLogsPage(1);
                  }}
                  className="text-xs bg-neutral-950 border border-neutral-700 rounded-md px-2.5 py-1.5 text-neutral-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="">All Severities</option>
                  <option value="EMERG">Emergency (EMERG)</option>
                  <option value="ALERT">Alert (ALERT)</option>
                  <option value="CRIT">Critical (CRIT)</option>
                  <option value="ERR">Error (ERR)</option>
                  <option value="WARNING">Warning (WARNING)</option>
                  <option value="NOTICE">Notice (NOTICE)</option>
                  <option value="INFO">Informational (INFO)</option>
                  <option value="DEBUG">Debug (DEBUG)</option>
                </select>

                {/* Service Filter */}
                <input
                  type="text"
                  placeholder="Service (e.g. sshd)"
                  value={filterService}
                  onChange={(e) => setFilterService(e.target.value)}
                  onBlur={() => {
                    setLogsPage(1);
                    fetchSystemLogs();
                  }}
                  maxLength={64}
                  className="text-xs bg-neutral-950 border border-neutral-700 rounded-md px-2.5 py-1.5 w-32 text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500"
                />

                <button
                  type="submit"
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-md text-xs font-medium transition"
                >
                  Apply
                </button>

                {(filterSource || filterSeverity || filterService || activeSearch) && (
                  <button
                    type="button"
                    onClick={handleResetFilters}
                    className="px-2.5 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 border border-neutral-700 rounded-md hover:bg-neutral-800 transition"
                  >
                    Reset
                  </button>
                )}
              </div>
            </form>
          </div>

          {/* Log Table / List */}
          <div className="bg-neutral-900 rounded-lg border border-neutral-800 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono border-collapse">
                <thead>
                  <tr className="bg-neutral-950 border-b border-neutral-800 text-[11px] font-sans font-semibold text-neutral-400 uppercase tracking-wider">
                    <th className="py-2.5 px-3 w-40">Timestamp</th>
                    <th className="py-2.5 px-2.5 w-20">Severity</th>
                    <th className="py-2.5 px-2.5 w-24">Source</th>
                    <th className="py-2.5 px-2.5 w-32">Service / Unit</th>
                    <th className="py-2.5 px-3">Message</th>
                    <th className="py-2.5 px-2 text-right w-12"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/60">
                  {loadingLogs ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-neutral-400 font-sans">
                        <RefreshCw className="w-5 h-5 animate-spin mx-auto text-indigo-400 mb-2" />
                        Fetching log stream...
                      </td>
                    </tr>
                  ) : logs.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-neutral-400 font-sans">
                        <FileText className="w-8 h-8 text-neutral-600 mx-auto mb-2" />
                        <p className="font-medium text-neutral-300">No log entries matched your query</p>
                        <p className="text-[11px] text-neutral-500 mt-1">
                          Try broadening your search or selecting a different source.
                        </p>
                      </td>
                    </tr>
                  ) : (
                    logs.map((entry) => (
                      <tr
                        key={entry.id}
                        onClick={() => setSelectedEntry(entry)}
                        className="hover:bg-neutral-850 cursor-pointer transition-colors"
                      >
                        <td className="py-2 px-3 text-[11px] text-neutral-400 whitespace-nowrap">
                          {entry.timestamp
                            ? new Date(entry.timestamp).toLocaleString(undefined, {
                                month: 'short',
                                day: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit',
                                hour12: false,
                              })
                            : '-'}
                        </td>
                        <td className="py-2 px-2.5 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-sans font-semibold border ${getSeverityBadgeClass(
                              entry.severity
                            )}`}
                          >
                            {entry.severity}
                          </span>
                        </td>
                        <td className="py-2 px-2.5 text-[11px] text-neutral-400 whitespace-nowrap">
                          <span className="px-1.5 py-0.2 bg-neutral-950 text-neutral-300 rounded border border-neutral-700 text-[10px]">
                            {entry.source}
                          </span>
                        </td>
                        <td className="py-2 px-2.5 text-[11px] text-neutral-300 whitespace-nowrap">
                          <span className="font-semibold text-indigo-400">
                            {entry.service || entry.unit || '-'}
                          </span>
                          {entry.pid && (
                            <span className="text-[10px] text-neutral-500 ml-1">
                              [{entry.pid}]
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-3 text-[11px] text-neutral-200 break-words max-w-xl">
                          <span className="line-clamp-2">{entry.message}</span>
                        </td>
                        <td className="py-2 px-2 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedEntry(entry);
                            }}
                            className="p-1 text-neutral-500 hover:text-indigo-400 rounded transition"
                            title="Inspect structured entry"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="bg-neutral-950 px-3 py-2.5 border-t border-neutral-800 flex flex-col sm:flex-row items-center justify-between gap-2.5 text-xs font-sans text-neutral-400">
              <div>
                Showing{' '}
                <span className="font-semibold text-neutral-200">
                  {logs.length > 0 ? (logsPage - 1) * logsPageSize + 1 : 0}
                </span>{' '}
                to{' '}
                <span className="font-semibold text-neutral-200">
                  {Math.min(logsPage * logsPageSize, totalLogs)}
                </span>{' '}
                of <span className="font-semibold text-neutral-200">{totalLogs}</span> entries
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={logsPageSize}
                  onChange={(e) => {
                    setLogsPageSize(Number(e.target.value));
                    setLogsPage(1);
                  }}
                  className="text-xs bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-neutral-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value={25}>25 per page</option>
                  <option value={50}>50 per page</option>
                  <option value={100}>100 per page</option>
                  <option value={200}>200 per page</option>
                </select>

                <button
                  onClick={() => setLogsPage((p) => Math.max(1, p - 1))}
                  disabled={logsPage <= 1 || loadingLogs}
                  className="p-1 border border-neutral-700 rounded bg-neutral-900 hover:bg-neutral-800 text-neutral-300 disabled:opacity-40 transition"
                  title="Previous page"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>

                <span className="px-1.5 font-medium text-neutral-300">Page {logsPage}</span>

                <button
                  onClick={() => setLogsPage((p) => p + 1)}
                  disabled={logsPage * logsPageSize >= totalLogs || loadingLogs}
                  className="p-1 border border-neutral-700 rounded bg-neutral-900 hover:bg-neutral-800 text-neutral-300 disabled:opacity-40 transition"
                  title="Next page"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: LOG SOURCES */}
      {activeTab === 'sources' && canReadLogs && (
        <div className="space-y-4">
          <div className="bg-neutral-900 rounded-lg border border-neutral-800 overflow-hidden">
            <div className="px-4 py-3.5 border-b border-neutral-800">
              <h2 className="text-sm font-semibold text-neutral-200">Configured Log Sources</h2>
              <p className="text-xs text-neutral-400 mt-0.5">
                Host-level availability, paths, and metadata for allowlisted system log sources.
              </p>
            </div>

            <div className="divide-y divide-neutral-800">
              {sources.map((src) => (
                <div key={src.id} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 hover:bg-neutral-850 transition">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-neutral-100 text-xs">{src.name}</span>
                      <span className="text-[10px] px-1.5 py-0.2 bg-neutral-950 text-neutral-300 rounded border border-neutral-700 font-mono">
                        {src.id}
                      </span>
                      <span
                        className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.2 rounded-full font-medium ${
                          src.available
                            ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                            : 'bg-neutral-800 text-neutral-400 border border-neutral-700'
                        }`}
                      >
                        {src.available ? (
                          <>
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Available
                          </>
                        ) : (
                          <>Not Present on Host</>
                        )}
                      </span>
                    </div>

                    <p className="text-xs text-neutral-400">{src.description}</p>

                    <div className="flex flex-wrap items-center gap-3 text-[11px] text-neutral-400 pt-0.5">
                      {src.path && (
                        <span className="font-mono bg-neutral-950 px-1.5 py-0.5 rounded border border-neutral-700 text-neutral-300">
                          {src.path}
                        </span>
                      )}
                      {src.size_bytes !== null && src.size_bytes !== undefined && (
                        <span>Size: {(src.size_bytes / 1024).toFixed(1)} KB</span>
                      )}
                      {src.last_modified && (
                        <span>
                          Modified: {new Date(src.last_modified).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        setFilterSource(src.id);
                        setActiveTab('system_logs');
                        setLogsPage(1);
                      }}
                      className="px-2.5 py-1 text-xs font-medium text-indigo-300 bg-indigo-950/80 hover:bg-indigo-900 border border-indigo-800 rounded transition"
                    >
                      View Logs
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: APPLICATION AUDIT LOGS */}
      {activeTab === 'audit_logs' && canReadAudit && (
        <div className="space-y-4">
          {/* Audit Filters */}
          <div className="bg-neutral-900 p-3.5 rounded-lg border border-neutral-800 flex flex-wrap items-center gap-2.5">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search audit events by user, action, resource, details..."
                value={auditSearch}
                onChange={(e) => {
                  setAuditSearch(e.target.value);
                  setAuditPage(1);
                }}
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-neutral-950 border border-neutral-700 rounded-md text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <select
              value={auditStatus}
              onChange={(e) => {
                setAuditStatus(e.target.value);
                setAuditPage(1);
              }}
              className="text-xs bg-neutral-950 border border-neutral-700 rounded-md px-2.5 py-1.5 text-neutral-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All Statuses</option>
              <option value="SUCCESS">SUCCESS</option>
              <option value="FAILED">FAILED</option>
            </select>

            <button
              onClick={() => {
                setAuditSearch('');
                setAuditAction('');
                setAuditStatus('');
                setAuditPage(1);
              }}
              className="px-2.5 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 border border-neutral-700 rounded-md hover:bg-neutral-800 transition"
            >
              Reset
            </button>
          </div>

          {/* Audit Table */}
          <div className="bg-neutral-900 rounded-lg border border-neutral-800 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-neutral-950 border-b border-neutral-800 text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
                    <th className="py-2.5 px-3 w-40">Timestamp</th>
                    <th className="py-2.5 px-2.5 w-28">User</th>
                    <th className="py-2.5 px-2.5 w-36">Action</th>
                    <th className="py-2.5 px-2.5 w-32">Resource</th>
                    <th className="py-2.5 px-2.5 w-20">Status</th>
                    <th className="py-2.5 px-3">Details</th>
                    <th className="py-2.5 px-2.5 w-28">IP Address</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/60">
                  {loadingAudit ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-neutral-400">
                        <RefreshCw className="w-5 h-5 animate-spin mx-auto text-indigo-400 mb-2" />
                        Loading audit logs...
                      </td>
                    </tr>
                  ) : auditLogs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-neutral-400">
                        <Shield className="w-8 h-8 text-neutral-600 mx-auto mb-2" />
                        <p className="font-medium text-neutral-300">No audit records found</p>
                        <p className="text-[11px] text-neutral-500 mt-1">
                          Security and mutation events will be logged here.
                        </p>
                      </td>
                    </tr>
                  ) : (
                    auditLogs.map((ev) => (
                      <tr key={ev.id} className="hover:bg-neutral-850 transition-colors">
                        <td className="py-2 px-3 text-[11px] text-neutral-400 font-mono whitespace-nowrap">
                          {new Date(ev.created_at).toLocaleString()}
                        </td>
                        <td className="py-2 px-2.5 text-xs font-semibold text-neutral-200">
                          {ev.username}
                        </td>
                        <td className="py-2 px-2.5 text-[11px] font-mono text-indigo-400">
                          {ev.action}
                        </td>
                        <td className="py-2 px-2.5 text-[11px] text-neutral-300">
                          <span className="font-mono">{ev.resource_type}</span>
                          {ev.resource_id && (
                            <span className="text-neutral-500 text-[10px] block truncate" title={ev.resource_id}>
                              {ev.resource_id}
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-2.5">
                          <span
                            className={`inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-semibold border ${
                              ev.status === 'SUCCESS'
                                ? 'bg-emerald-950/80 text-emerald-300 border-emerald-800'
                                : 'bg-rose-950/80 text-rose-300 border-rose-800'
                            }`}
                          >
                            {ev.status}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-[11px] text-neutral-300 break-words max-w-md font-mono">
                          {ev.details || '-'}
                        </td>
                        <td className="py-2 px-2.5 text-[11px] text-neutral-400 font-mono whitespace-nowrap">
                          {ev.ip_address || '-'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="bg-neutral-950 px-3 py-2.5 border-t border-neutral-800 flex flex-col sm:flex-row items-center justify-between gap-2.5 text-xs text-neutral-400">
              <div>
                Showing{' '}
                <span className="font-semibold text-neutral-200">
                  {auditLogs.length > 0 ? (auditPage - 1) * auditPageSize + 1 : 0}
                </span>{' '}
                to{' '}
                <span className="font-semibold text-neutral-200">
                  {Math.min(auditPage * auditPageSize, totalAuditLogs)}
                </span>{' '}
                of <span className="font-semibold text-neutral-200">{totalAuditLogs}</span> audit records
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setAuditPage((p) => Math.max(1, p - 1))}
                  disabled={auditPage <= 1 || loadingAudit}
                  className="p-1 border border-neutral-700 rounded bg-neutral-900 hover:bg-neutral-800 text-neutral-300 disabled:opacity-40 transition"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>

                <span className="px-1.5 font-medium text-neutral-300">Page {auditPage}</span>

                <button
                  onClick={() => setAuditPage((p) => p + 1)}
                  disabled={auditPage * auditPageSize >= totalAuditLogs || loadingAudit}
                  className="p-1 border border-neutral-700 rounded bg-neutral-900 hover:bg-neutral-800 text-neutral-300 disabled:opacity-40 transition"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* DETAIL MODAL FOR SYSTEM LOG ENTRY */}
      {selectedEntry && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-neutral-900 rounded-xl max-w-2xl w-full border border-neutral-800 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="px-5 py-3.5 border-b border-neutral-800 flex items-center justify-between bg-neutral-950">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-400" />
                <h3 className="text-sm font-semibold text-neutral-100">Log Entry Inspector</h3>
              </div>
              <button
                onClick={() => setSelectedEntry(null)}
                className="text-neutral-400 hover:text-neutral-200 p-1 rounded transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 overflow-y-auto">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">
                <div className="p-2.5 bg-neutral-950 rounded border border-neutral-800">
                  <span className="text-neutral-500 block text-[10px]">Severity</span>
                  <span className={`inline-block mt-1 font-semibold px-1.5 py-0.2 rounded text-[10px] border ${getSeverityBadgeClass(selectedEntry.severity)}`}>
                    {selectedEntry.severity}
                  </span>
                </div>

                <div className="p-2.5 bg-neutral-950 rounded border border-neutral-800">
                  <span className="text-neutral-500 block text-[10px]">Source</span>
                  <span className="font-semibold text-neutral-200 mt-1 block">
                    {selectedEntry.source}
                  </span>
                </div>

                <div className="p-2.5 bg-neutral-950 rounded border border-neutral-800">
                  <span className="text-neutral-500 block text-[10px]">Service / Unit</span>
                  <span className="font-semibold text-indigo-400 mt-1 block font-mono">
                    {selectedEntry.service || selectedEntry.unit || '-'}
                  </span>
                </div>

                <div className="p-2.5 bg-neutral-950 rounded border border-neutral-800">
                  <span className="text-neutral-500 block text-[10px]">PID / UID</span>
                  <span className="font-mono text-neutral-300 mt-1 block">
                    PID: {selectedEntry.pid ?? '-'} | UID: {selectedEntry.uid ?? '-'}
                  </span>
                </div>

                <div className="p-2.5 bg-neutral-950 rounded border border-neutral-800">
                  <span className="text-neutral-500 block text-[10px]">Hostname</span>
                  <span className="font-mono text-neutral-300 mt-1 block truncate">
                    {selectedEntry.hostname || '-'}
                  </span>
                </div>

                <div className="p-2.5 bg-neutral-950 rounded border border-neutral-800">
                  <span className="text-neutral-500 block text-[10px]">Timestamp</span>
                  <span className="font-mono text-neutral-300 mt-1 block text-[11px]">
                    {new Date(selectedEntry.timestamp).toLocaleString()}
                  </span>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
                    Full Log Message
                  </span>
                  <button
                    onClick={() => copyToClipboard(selectedEntry.message)}
                    className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                  >
                    {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <div className="p-3.5 bg-neutral-950 text-neutral-200 rounded-lg font-mono text-xs overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-60 border border-neutral-800 selection:bg-indigo-600">
                  {selectedEntry.message}
                </div>
              </div>

              <div className="text-[10px] text-neutral-500 font-mono">
                Entry ID: {selectedEntry.id}
              </div>
            </div>

            <div className="px-5 py-3 border-t border-neutral-800 bg-neutral-950 flex justify-end">
              <button
                onClick={() => setSelectedEntry(null)}
                className="px-3.5 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 rounded text-xs font-medium transition"
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
