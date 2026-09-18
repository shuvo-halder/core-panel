import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  Server,
  Play,
  Square,
  RotateCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Search,
  Check,
  Shield,
  Layers,
  Power,
  PowerOff,
  SlidersHorizontal,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiClient, ApiError } from '../api/client';
import { ServiceSummary } from '../types/service';

interface ConfirmationModalProps {
  isOpen: boolean;
  unit: string;
  action: 'start' | 'stop' | 'restart' | 'enable' | 'disable';
  isLoading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  isOpen,
  unit,
  action,
  isLoading,
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  const getActionDetails = () => {
    switch (action) {
      case 'stop':
        return {
          title: `Stop ${unit}?`,
          description: 'This will immediately shut down the active service processes on the Linux host.',
          badgeColor: 'bg-red-500/10 text-red-400 border-red-500/20',
          confirmText: 'Stop Service',
          confirmButtonClass: 'bg-red-600 hover:bg-red-700 text-white',
          icon: Square,
        };
      case 'restart':
        return {
          title: `Restart ${unit}?`,
          description: 'The service will be temporarily stopped and reinitialized. Active network connections to it may briefly reset.',
          badgeColor: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
          confirmText: 'Restart Service',
          confirmButtonClass: 'bg-amber-600 hover:bg-amber-700 text-white',
          icon: RotateCw,
        };
      case 'disable':
        return {
          title: `Disable ${unit}?`,
          description: 'This will remove the systemd boot symlinks so the service will not automatically start at server boot.',
          badgeColor: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
          confirmText: 'Disable at Boot',
          confirmButtonClass: 'bg-orange-600 hover:bg-orange-700 text-white',
          icon: PowerOff,
        };
      case 'enable':
        return {
          title: `Enable ${unit}?`,
          description: 'This will configure systemd to start this service automatically on subsequent system reboots.',
          badgeColor: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
          confirmText: 'Enable at Boot',
          confirmButtonClass: 'bg-cyan-600 hover:bg-cyan-700 text-white',
          icon: Power,
        };
      case 'start':
      default:
        return {
          title: `Start ${unit}?`,
          description: 'This will launch the service and its configured background processes on the server.',
          badgeColor: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
          confirmText: 'Start Service',
          confirmButtonClass: 'bg-emerald-600 hover:bg-emerald-700 text-white',
          icon: Play,
        };
    }
  };

  const details = getActionDetails();
  const Icon = details.icon;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-md p-6 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl text-slate-100">
        <div className="flex items-center space-x-3 mb-4">
          <div className={`p-2.5 rounded-lg border ${details.badgeColor}`}>
            <Icon className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">{details.title}</h3>
            <span className="text-xs text-slate-400 font-mono">{unit}</span>
          </div>
        </div>

        <p className="text-sm text-slate-300 mb-6 leading-relaxed">
          {details.description}
        </p>

        <div className="flex items-center justify-end space-x-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700/80 rounded-lg transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isLoading}
            className={`px-4 py-2 text-sm font-medium rounded-lg flex items-center space-x-2 transition-colors disabled:opacity-50 ${details.confirmButtonClass}`}
          >
            {isLoading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Executing...</span>
              </>
            ) : (
              <span>{details.confirmText}</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export const ServiceManagement: React.FC = () => {
  const { hasPermission } = useAuth();
  const [services, setServices] = useState<ServiceSummary[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Mutation modal state
  const [modalState, setModalState] = useState<{
    isOpen: boolean;
    unit: string;
    action: 'start' | 'stop' | 'restart' | 'enable' | 'disable';
  }>({
    isOpen: false,
    unit: '',
    action: 'start',
  });
  const [isExecutingMutation, setIsExecutingMutation] = useState<boolean>(false);

  const fetchServices = useCallback(async (isSilent: boolean = false) => {
    if (!isSilent) setIsLoading(true);
    setIsRefreshing(true);
    try {
      const data = await apiClient.listServices();
      setServices(data);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setFeedback({ type: 'error', message: err.message });
      } else {
        setFeedback({ type: 'error', message: 'Failed to load systemd services' });
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchServices();
  }, [fetchServices]);

  const handleOpenConfirm = (unit: string, action: 'start' | 'stop' | 'restart' | 'enable' | 'disable') => {
    setModalState({
      isOpen: true,
      unit,
      action,
    });
  };

  const handleExecuteAction = async () => {
    const { unit, action } = modalState;
    setIsExecutingMutation(true);
    setFeedback(null);

    try {
      let result;
      switch (action) {
        case 'start':
          result = await apiClient.startService(unit);
          break;
        case 'stop':
          result = await apiClient.stopService(unit);
          break;
        case 'restart':
          result = await apiClient.restartService(unit);
          break;
        case 'enable':
          result = await apiClient.enableService(unit);
          break;
        case 'disable':
          result = await apiClient.disableService(unit);
          break;
      }

      setFeedback({
        type: 'success',
        message: result.message || `Service ${unit} ${action} completed successfully`,
      });

      // Update unit state in local state if service details returned, then do background fetch
      if (result.service) {
        const updatedService = result.service;
        setServices(prev =>
          prev.map(s => (s.unit === unit ? updatedService : s))
        );
      }
      setModalState({ isOpen: false, unit: '', action: 'start' });
      await fetchServices(true);
    } catch (err: any) {
      const msg = err instanceof ApiError ? err.message : `Failed to ${action} ${unit}`;
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsExecutingMutation(false);
    }
  };

  const filteredServices = useMemo(() => {
    return services.filter(service => {
      const matchesSearch =
        service.unit.toLowerCase().includes(searchTerm.toLowerCase()) ||
        service.description.toLowerCase().includes(searchTerm.toLowerCase());

      if (!matchesSearch) return false;

      if (statusFilter === 'all') return true;
      if (statusFilter === 'active') return service.active_state === 'active';
      if (statusFilter === 'inactive') return service.active_state === 'inactive';
      if (statusFilter === 'failed') return service.active_state === 'failed';
      if (statusFilter === 'enabled') return service.enabled === 'enabled';
      if (statusFilter === 'disabled') return service.enabled === 'disabled';

      return true;
    });
  }, [services, searchTerm, statusFilter]);

  const canStart = hasPermission('services.start');
  const canStop = hasPermission('services.stop');
  const canRestart = hasPermission('services.restart');
  const canEnable = hasPermission('services.enable');
  const canDisable = hasPermission('services.disable');

  const getActiveBadge = (state: string, subState: string) => {
    switch (state) {
      case 'active':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
            active ({subState})
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertTriangle className="w-3 h-3 mr-1" />
            failed
          </span>
        );
      case 'activating':
      case 'deactivating':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
            {state}
          </span>
        );
      case 'inactive':
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
            inactive ({subState})
          </span>
        );
    }
  };

  const getEnabledBadge = (enabled: string) => {
    switch (enabled) {
      case 'enabled':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            enabled
          </span>
        );
      case 'disabled':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
            disabled
          </span>
        );
      case 'static':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-800/60 text-slate-500 border border-slate-700/60">
            static
          </span>
        );
      case 'masked':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-900/20 text-red-400 border border-red-800/30">
            masked
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-800 text-slate-400">
            {enabled || 'unknown'}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-slate-900/60 p-6 rounded-2xl border border-slate-800 backdrop-blur-md">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-500/10 text-blue-400 rounded-xl border border-blue-500/20">
            <Server className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">Systemd Services</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Controlled daemon supervision, runtime status inspection, and lifecycle operations
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            type="button"
            onClick={() => fetchServices(false)}
            disabled={isRefreshing}
            className="flex items-center space-x-2 px-3.5 py-2 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700/80 border border-slate-700 rounded-lg transition-all disabled:opacity-50 cursor-pointer shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-blue-400' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Feedback banner */}
      {feedback && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between text-sm animate-in fade-in ${
            feedback.type === 'success'
              ? 'bg-emerald-950/40 border-emerald-800/50 text-emerald-200'
              : 'bg-rose-950/40 border-rose-800/50 text-rose-200'
          }`}
        >
          <div className="flex items-center space-x-2">
            {feedback.type === 'success' ? (
              <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            className="text-xs opacity-60 hover:opacity-100 underline ml-4 cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Controls / Filter Bar */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-slate-900/40 p-4 rounded-xl border border-slate-800">
        <div className="md:col-span-2 relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search services by unit name or description (e.g. nginx, ssh)..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-lg pl-10 pr-4 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/50 transition-colors"
          />
        </div>

        <div className="flex items-center space-x-2">
          <SlidersHorizontal className="w-4 h-4 text-slate-500 shrink-0" />
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-blue-500/50 cursor-pointer"
          >
            <option value="all">All States ({services.length})</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
            <option value="failed">Failed only</option>
            <option value="enabled">Enabled at boot</option>
            <option value="disabled">Disabled at boot</option>
          </select>
        </div>
      </div>

      {/* Services Table */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden backdrop-blur-md">
        {isLoading ? (
          <div className="p-12 flex flex-col items-center justify-center space-y-3 text-slate-400">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
            <p className="text-sm font-medium">Discovering systemd service units...</p>
          </div>
        ) : filteredServices.length === 0 ? (
          <div className="p-12 text-center text-slate-400 space-y-2">
            <Layers className="w-8 h-8 mx-auto text-slate-600 mb-2" />
            <p className="text-base font-semibold text-slate-300">No matching services found</p>
            <p className="text-xs text-slate-500">
              {services.length === 0
                ? 'No systemd services are currently active or systemd is not running on this host.'
                : 'Try adjusting your search query or filter.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/40 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  <th className="py-3 px-4">Unit Name</th>
                  <th className="py-3 px-4">State</th>
                  <th className="py-3 px-4">Boot State</th>
                  <th className="py-3 px-4">PID</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-sm text-slate-300">
                {filteredServices.map(service => {
                  const isActive = service.active_state === 'active';
                  const isEnabled = service.enabled === 'enabled';

                  return (
                    <tr key={service.unit} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3.5 px-4 font-mono text-xs">
                        <div className="font-semibold text-slate-200">{service.unit}</div>
                        {service.description && (
                          <div className="text-xs text-slate-500 font-sans truncate max-w-xs md:max-w-md mt-0.5">
                            {service.description}
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        {getActiveBadge(service.active_state, service.sub_state)}
                      </td>
                      <td className="py-3.5 px-4">
                        {getEnabledBadge(service.enabled)}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-xs text-slate-400">
                        {service.main_pid ? service.main_pid : '—'}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end space-x-1.5">
                          {/* Start / Stop Toggle */}
                          {isActive ? (
                            canStop && (
                              <button
                                type="button"
                                onClick={() => handleOpenConfirm(service.unit, 'stop')}
                                title="Stop service"
                                className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-md transition-colors cursor-pointer"
                              >
                                <Square className="w-4 h-4" />
                              </button>
                            )
                          ) : (
                            canStart && (
                              <button
                                type="button"
                                onClick={() => handleOpenConfirm(service.unit, 'start')}
                                title="Start service"
                                className="p-1.5 text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10 rounded-md transition-colors cursor-pointer"
                              >
                                <Play className="w-4 h-4" />
                              </button>
                            )
                          )}

                          {/* Restart */}
                          {canRestart && (
                            <button
                              type="button"
                              onClick={() => handleOpenConfirm(service.unit, 'restart')}
                              title="Restart service"
                              className="p-1.5 text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 rounded-md transition-colors cursor-pointer"
                            >
                              <RotateCw className="w-4 h-4" />
                            </button>
                          )}

                          {/* Enable / Disable */}
                          {isEnabled ? (
                            canDisable && (
                              <button
                                type="button"
                                onClick={() => handleOpenConfirm(service.unit, 'disable')}
                                title="Disable boot startup"
                                className="p-1.5 text-slate-400 hover:text-orange-400 hover:bg-orange-500/10 rounded-md transition-colors cursor-pointer"
                              >
                                <PowerOff className="w-4 h-4" />
                              </button>
                            )
                          ) : (
                            canEnable && (
                              <button
                                type="button"
                                onClick={() => handleOpenConfirm(service.unit, 'enable')}
                                title="Enable boot startup"
                                className="p-1.5 text-slate-400 hover:text-cyan-400 hover:bg-cyan-500/10 rounded-md transition-colors cursor-pointer"
                              >
                                <Power className="w-4 h-4" />
                              </button>
                            )
                          )}

                          {!canStart && !canStop && !canRestart && !canEnable && !canDisable && (
                            <span className="text-xs text-slate-500 italic flex items-center space-x-1">
                              <Shield className="w-3 h-3 inline" />
                              <span>View Only</span>
                            </span>
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
      </div>

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={modalState.isOpen}
        unit={modalState.unit}
        action={modalState.action}
        isLoading={isExecutingMutation}
        onConfirm={handleExecuteAction}
        onCancel={() => setModalState({ isOpen: false, unit: '', action: 'start' })}
      />
    </div>
  );
};
