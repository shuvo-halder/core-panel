import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Check,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Cpu,
  HardDrive,
  Info,
  Layers,
  Power,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  Skull,
  Square,
  User,
  XCircle,
} from 'lucide-react';
import { ApiError, apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { ProcessSummary } from '../types/process';

interface ConfirmationModalProps {
  isOpen: boolean;
  pid: number;
  name: string;
  action: 'terminate' | 'kill';
  isLoading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  isOpen,
  pid,
  name,
  action,
  isLoading,
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  const isKill = action === 'kill';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in">
      <div className="w-full max-w-md p-6 bg-neutral-900 border border-neutral-800 rounded-xl shadow-2xl text-neutral-100">
        <div className="flex items-center space-x-3 mb-4">
          <div
            className={`p-2.5 rounded-lg border ${
              isKill
                ? 'bg-red-500/10 text-red-400 border-red-500/20'
                : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
            }`}
          >
            {isKill ? <Skull className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">
              {isKill ? 'Force Kill Process?' : 'Terminate Process?'}
            </h3>
            <span className="text-xs text-neutral-400 font-mono">
              PID: {pid} — {name}
            </span>
          </div>
        </div>

        <p className="text-sm text-neutral-300 mb-6 leading-relaxed">
          {isKill ? (
            <>
              This will send an uncatchable <strong className="text-red-400 font-mono">SIGKILL (signal 9)</strong> to{' '}
              <strong className="text-white font-mono">{name}</strong> (PID {pid}). The process will be immediately
              dropped by the kernel without saving uncommitted state.
            </>
          ) : (
            <>
              This will send a graceful <strong className="text-amber-400 font-mono">SIGTERM (signal 15)</strong> to{' '}
              <strong className="text-white font-mono">{name}</strong> (PID {pid}), requesting clean shutdown and
              resource deallocation.
            </>
          )}
        </p>

        <div className="flex items-center justify-end space-x-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-neutral-400 hover:text-neutral-200 bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isLoading}
            className={`px-4 py-2 text-sm font-medium rounded-lg flex items-center space-x-2 transition-colors disabled:opacity-50 ${
              isKill
                ? 'bg-red-600 hover:bg-red-700 text-white shadow-xs'
                : 'bg-amber-600 hover:bg-amber-700 text-white shadow-xs'
            }`}
          >
            {isLoading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Sending signal...</span>
              </>
            ) : (
              <span>{isKill ? 'Force Kill (SIGKILL)' : 'Terminate (SIGTERM)'}</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export const ProcessManagement: React.FC = () => {
  const { hasPermission } = useAuth();
  const [processes, setProcesses] = useState<ProcessSummary[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('cpu');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [autoRefreshInterval, setAutoRefreshInterval] = useState<number>(0); // 0 = off, 5 = 5s, 10 = 10s
  const [selectedProcess, setSelectedProcess] = useState<ProcessSummary | null>(null);

  // Mutation modal state
  const [modalState, setModalState] = useState<{
    isOpen: boolean;
    pid: number;
    name: string;
    action: 'terminate' | 'kill';
  }>({
    isOpen: false,
    pid: 0,
    name: '',
    action: 'terminate',
  });
  const [isExecutingMutation, setIsExecutingMutation] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const canTerminate = hasPermission('processes.terminate');
  const canKill = hasPermission('processes.kill');

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const fetchProcesses = useCallback(
    async (isSilent: boolean = false) => {
      if (!isSilent) setIsLoading(true);
      setIsRefreshing(true);
      try {
        const data = await apiClient.listProcesses({
          page,
          page_size: pageSize,
          search: debouncedSearch || undefined,
          sort: sortBy,
          order,
        });
        setProcesses(data.items);
        setTotal(data.total);
        setTotalPages(data.total_pages);
      } catch (err: any) {
        if (err instanceof ApiError) {
          setFeedback({ type: 'error', message: err.message });
        } else {
          setFeedback({ type: 'error', message: 'Failed to load process telemetry' });
        }
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [page, pageSize, debouncedSearch, sortBy, order]
  );

  useEffect(() => {
    fetchProcesses();
  }, [fetchProcesses]);

  // Auto-refresh timer
  useEffect(() => {
    if (autoRefreshInterval <= 0) return;
    const interval = setInterval(() => {
      fetchProcesses(true);
    }, autoRefreshInterval * 1000);
    return () => clearInterval(interval);
  }, [autoRefreshInterval, fetchProcesses]);

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setOrder((prev) => (prev === 'desc' ? 'asc' : 'desc'));
    } else {
      setSortBy(field);
      setOrder('desc');
    }
    setPage(1);
  };

  const handleOpenConfirm = (proc: ProcessSummary, action: 'terminate' | 'kill') => {
    setModalState({
      isOpen: true,
      pid: proc.pid,
      name: proc.name,
      action,
    });
  };

  const handleExecuteAction = async () => {
    const { pid, name, action } = modalState;
    setIsExecutingMutation(true);
    setFeedback(null);

    try {
      let result;
      if (action === 'terminate') {
        result = await apiClient.terminateProcess(pid);
      } else {
        result = await apiClient.killProcess(pid);
      }

      setFeedback({
        type: 'success',
        message: result.message || `Signal delivered to process ${name} (PID ${pid})`,
      });
      setModalState((prev) => ({ ...prev, isOpen: false }));
      // Refresh list
      await fetchProcesses(true);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setFeedback({ type: 'error', message: err.message });
      } else {
        setFeedback({
          type: 'error',
          message: `Failed to execute ${action} on process ${name} (PID ${pid})`,
        });
      }
    } finally {
      setIsExecutingMutation(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
  };

  const getStateBadge = (state: string) => {
    switch (state) {
      case 'running':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
            RUNNING
          </span>
        );
      case 'sleeping':
      case 'idle':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400 mr-1.5" />
            {state.toUpperCase()}
          </span>
        );
      case 'disk_sleep':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1.5" />
            DISK SLEEP
          </span>
        );
      case 'stopped':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-orange-500/10 text-orange-400 border border-orange-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-orange-400 mr-1.5" />
            STOPPED
          </span>
        );
      case 'zombie':
      case 'dead':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-red-500/10 text-red-400 border border-red-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-red-400 mr-1.5" />
            {state.toUpperCase()}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-neutral-700/50 text-neutral-400 border border-neutral-700">
            {state.toUpperCase()}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-neutral-900/60 p-5 rounded-xl border border-neutral-800">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Activity className="w-5 h-5 text-emerald-400" />
            Process Management &amp; Monitoring
          </h2>
          <p className="text-xs text-neutral-400 mt-1">
            Real-time inspection of host Linux processes with controlled, audited signal delivery.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Auto Refresh Toggle */}
          <div className="flex items-center space-x-1.5 bg-neutral-800/80 border border-neutral-700/80 rounded-lg p-1 text-xs">
            <span className="text-neutral-400 px-2 text-[11px]">Auto Refresh:</span>
            {[
              { label: 'Off', val: 0 },
              { label: '5s', val: 5 },
              { label: '10s', val: 10 },
            ].map((opt) => (
              <button
                key={opt.val}
                type="button"
                onClick={() => setAutoRefreshInterval(opt.val)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  autoRefreshInterval === opt.val
                    ? 'bg-neutral-700 text-white'
                    : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Manual Refresh Button */}
          <button
            id="refresh-processes-btn"
            type="button"
            onClick={() => fetchProcesses(false)}
            disabled={isRefreshing}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 rounded-lg text-xs font-medium border border-neutral-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-emerald-400' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Feedback Banner */}
      {feedback && (
        <div
          className={`p-4 rounded-xl border flex items-start justify-between space-x-3 text-sm animate-in fade-in ${
            feedback.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-red-500/10 border-red-500/30 text-red-300'
          }`}
        >
          <div className="flex items-center space-x-2">
            {feedback.type === 'success' ? (
              <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            className="text-xs opacity-70 hover:opacity-100 font-mono"
          >
            ✕
          </button>
        </div>
      )}

      {/* Filters Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-neutral-900/40 p-4 rounded-xl border border-neutral-800">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            id="process-search-input"
            type="text"
            placeholder="Search by PID, name, user, or cmd..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-neutral-950 border border-neutral-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-hidden focus:border-neutral-600 font-mono"
          />
        </div>

        <div className="flex items-center space-x-3 text-xs text-neutral-400 w-full sm:w-auto justify-between sm:justify-end">
          <span className="font-mono">
            Total: <strong className="text-white">{total}</strong> processes
          </span>
          <div className="flex items-center space-x-2">
            <span>Per page:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="bg-neutral-950 border border-neutral-800 rounded px-2 py-1 text-xs text-neutral-200 font-mono focus:outline-hidden"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        </div>
      </div>

      {/* Process Table */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-xl shadow-xs overflow-hidden">
        {isLoading && processes.length === 0 ? (
          <div className="py-20 flex flex-col items-center justify-center text-neutral-400 space-y-3">
            <RefreshCw className="w-6 h-6 animate-spin text-neutral-500" />
            <span className="text-xs font-mono">Enumerating host processes from /proc...</span>
          </div>
        ) : processes.length === 0 ? (
          <div className="py-20 text-center text-neutral-500 text-xs font-mono">
            No matching processes found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-neutral-800 bg-neutral-950/60 text-[11px] font-medium text-neutral-400 select-none">
                  <th
                    onClick={() => handleSort('pid')}
                    className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
                  >
                    <div className="flex items-center space-x-1">
                      <span>PID</span>
                      {sortBy === 'pid' && (order === 'desc' ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />)}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('name')}
                    className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
                  >
                    <div className="flex items-center space-x-1">
                      <span>Process Name</span>
                      {sortBy === 'name' && (order === 'desc' ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />)}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('user')}
                    className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
                  >
                    <div className="flex items-center space-x-1">
                      <span>User</span>
                      {sortBy === 'user' && (order === 'desc' ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />)}
                    </div>
                  </th>
                  <th className="py-3 px-4">State</th>
                  <th
                    onClick={() => handleSort('cpu')}
                    className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
                  >
                    <div className="flex items-center space-x-1">
                      <span>CPU %</span>
                      {sortBy === 'cpu' && (order === 'desc' ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />)}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('memory')}
                    className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
                  >
                    <div className="flex items-center space-x-1">
                      <span>Memory (RSS)</span>
                      {sortBy === 'memory' && (order === 'desc' ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />)}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('threads')}
                    className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
                  >
                    <div className="flex items-center space-x-1">
                      <span>Threads</span>
                      {sortBy === 'threads' && (order === 'desc' ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />)}
                    </div>
                  </th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800/60 font-mono">
                {processes.map((proc) => {
                  const isProtected = proc.is_protected || proc.pid === 1;

                  return (
                    <tr
                      key={proc.pid}
                      className={`hover:bg-neutral-850/60 transition-colors ${
                        selectedProcess?.pid === proc.pid ? 'bg-neutral-800/40' : ''
                      }`}
                    >
                      {/* PID */}
                      <td className="py-3 px-4">
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-neutral-200">{proc.pid}</span>
                          {isProtected && (
                            <span
                              title="Protected System Process (Cannot be terminated)"
                              className="p-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            >
                              <Shield className="w-3 h-3" />
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Process Name & Summary */}
                      <td className="py-3 px-4 font-sans max-w-xs">
                        <div className="font-medium text-white truncate" title={proc.name}>
                          {proc.name}
                        </div>
                        <div
                          className="text-[11px] text-neutral-400 font-mono truncate"
                          title={proc.command_summary || ''}
                        >
                          {proc.command_summary || `PPID: ${proc.ppid}`}
                        </div>
                      </td>

                      {/* User */}
                      <td className="py-3 px-4 text-neutral-300">
                        <div className="flex items-center space-x-1.5">
                          <User className="w-3 h-3 text-neutral-500" />
                          <span>{proc.username || `UID ${proc.uid}`}</span>
                        </div>
                      </td>

                      {/* State */}
                      <td className="py-3 px-4">{getStateBadge(proc.state)}</td>

                      {/* CPU */}
                      <td className="py-3 px-4">
                        <div className="flex items-center space-x-2">
                          <span className="w-12 text-neutral-200 font-medium">
                            {proc.cpu_percent.toFixed(1)}%
                          </span>
                          <div className="w-16 h-1.5 bg-neutral-800 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                proc.cpu_percent > 70
                                  ? 'bg-red-500'
                                  : proc.cpu_percent > 30
                                  ? 'bg-amber-500'
                                  : 'bg-emerald-500'
                              }`}
                              style={{ width: `${Math.min(100, proc.cpu_percent)}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Memory */}
                      <td className="py-3 px-4">
                        <div className="flex flex-col">
                          <span className="text-neutral-200 font-medium">
                            {formatBytes(proc.memory_rss_bytes)}
                          </span>
                          <span className="text-[10px] text-neutral-400">
                            {proc.memory_percent.toFixed(1)}% of total
                          </span>
                        </div>
                      </td>

                      {/* Threads */}
                      <td className="py-3 px-4 text-neutral-300">{proc.threads}</td>

                      {/* Actions */}
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end space-x-1.5">
                          {isProtected ? (
                            <span className="text-[11px] text-neutral-500 font-sans italic pr-2">
                              Protected
                            </span>
                          ) : (
                            <>
                              {canTerminate && (
                                <button
                                  type="button"
                                  title="Send SIGTERM (Graceful Terminate)"
                                  onClick={() => handleOpenConfirm(proc, 'terminate')}
                                  className="px-2 py-1 rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 text-[11px] font-sans font-medium transition-colors"
                                >
                                  Terminate
                                </button>
                              )}
                              {canKill && (
                                <button
                                  type="button"
                                  title="Send SIGKILL (Force Kill)"
                                  onClick={() => handleOpenConfirm(proc, 'kill')}
                                  className="px-2 py-1 rounded bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 text-[11px] font-sans font-medium transition-colors"
                                >
                                  Kill
                                </button>
                              )}
                              {!canTerminate && !canKill && (
                                <span className="text-[11px] text-neutral-500 font-sans italic">
                                  Read-only
                                </span>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        <div className="border-t border-neutral-800 bg-neutral-950/60 p-4 flex items-center justify-between text-xs text-neutral-400 font-mono">
          <div>
            Showing Page <strong className="text-neutral-200">{page}</strong> of{' '}
            <strong className="text-neutral-200">{totalPages}</strong> ({total} total processes)
          </div>

          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded border border-neutral-700 transition-colors disabled:opacity-40 disabled:hover:bg-neutral-800 flex items-center space-x-1"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>Prev</span>
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded border border-neutral-700 transition-colors disabled:opacity-40 disabled:hover:bg-neutral-800 flex items-center space-x-1"
            >
              <span>Next</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Action Confirmation Modal */}
      <ConfirmationModal
        isOpen={modalState.isOpen}
        pid={modalState.pid}
        name={modalState.name}
        action={modalState.action}
        isLoading={isExecutingMutation}
        onConfirm={handleExecuteAction}
        onCancel={() => setModalState((prev) => ({ ...prev, isOpen: false }))}
      />
    </div>
  );
};
