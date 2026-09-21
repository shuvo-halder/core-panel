import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Calendar,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Clock,
  Edit3,
  Eye,
  FileCode,
  Folder,
  Info,
  Lock,
  Plus,
  Power,
  RefreshCw,
  Search,
  Sliders,
  Trash2,
  User,
  X,
  XCircle,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';
import {
  CronEligibleUser,
  CronJob,
  CronOverview,
  CronSource,
} from '../types/cron';

const PRESETS = [
  { label: 'Every minute (* * * * *)', schedule: '* * * * *' },
  { label: 'Every 5 minutes (*/5 * * * *)', schedule: '*/5 * * * *' },
  { label: 'Every 15 minutes (*/15 * * * *)', schedule: '*/15 * * * *' },
  { label: 'Hourly at minute 0 (0 * * * *)', schedule: '0 * * * *' },
  { label: 'Daily at midnight (0 0 * * *)', schedule: '0 0 * * *' },
  { label: 'Daily at 02:00 (0 2 * * *)', schedule: '0 2 * * *' },
  { label: 'Weekly on Sunday at midnight (0 0 * * 0)', schedule: '0 0 * * 0' },
  { label: 'Monthly on day 1 (0 0 1 * *)', schedule: '0 0 1 * *' },
  { label: 'System reboot (@reboot)', schedule: '@reboot' },
  { label: 'Daily (@daily)', schedule: '@daily' },
  { label: 'Hourly (@hourly)', schedule: '@hourly' },
];

export const CronManagement: React.FC = () => {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission('cron.create');
  const canUpdate = hasPermission('cron.update');
  const canDelete = hasPermission('cron.delete');

  // State
  const [overview, setOverview] = useState<CronOverview | null>(null);
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [eligibleUsers, setEligibleUsers] = useState<CronEligibleUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pageSize] = useState(25);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedOwner, setSelectedOwner] = useState<string>('');
  const [selectedSource, setSelectedSource] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>(''); // '', 'active', 'disabled'

  // Modals
  const [detailJob, setDetailJob] = useState<CronJob | null>(null);
  const [deleteJob, setDeleteJob] = useState<CronJob | null>(null);
  const [modalMode, setModalMode] = useState<'create' | 'edit' | null>(null);
  const [editingJob, setEditingJob] = useState<CronJob | null>(null);

  // Form inputs
  const [formOwner, setFormOwner] = useState('root');
  const [formSchedule, setFormSchedule] = useState('0 0 * * *');
  const [formCommand, setFormCommand] = useState('');
  const [formComment, setFormComment] = useState('');
  const [formEnabled, setFormEnabled] = useState(true);
  const [selectedPreset, setSelectedPreset] = useState('');

  // 5-field decomposed inputs
  const [fieldMinute, setFieldMinute] = useState('0');
  const [fieldHour, setFieldHour] = useState('0');
  const [fieldDom, setFieldDom] = useState('*');
  const [fieldMonth, setFieldMonth] = useState('*');
  const [fieldDow, setFieldDow] = useState('*');
  const [useSpecial, setUseSpecial] = useState(false);
  const [specialExpr, setSpecialExpr] = useState('@daily');

  // Fetch overview and jobs
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ovData, usersData, jobsData] = await Promise.all([
        apiClient.getCronOverview(),
        apiClient.getCronUsers(),
        apiClient.getCronJobs({
          page,
          page_size: pageSize,
          owner: selectedOwner || undefined,
          source: selectedSource || undefined,
          enabled: selectedStatus === 'active' ? true : selectedStatus === 'disabled' ? false : undefined,
          search: searchTerm || undefined,
        }),
      ]);
      setOverview(ovData);
      setEligibleUsers(usersData);
      setJobs(jobsData.items);
      setTotal(jobsData.total);
      setTotalPages(jobsData.total_pages);
    } catch (err: any) {
      setError(err.message || 'Failed to load scheduled cron jobs');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, selectedOwner, selectedSource, selectedStatus, searchTerm]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle preset change
  const handlePresetSelect = (presetSched: string) => {
    setSelectedPreset(presetSched);
    if (!presetSched) return;
    setFormSchedule(presetSched);
    if (presetSched.startsWith('@')) {
      setUseSpecial(true);
      setSpecialExpr(presetSched);
    } else {
      setUseSpecial(false);
      const parts = presetSched.split(' ');
      if (parts.length === 5) {
        setFieldMinute(parts[0]);
        setFieldHour(parts[1]);
        setFieldDom(parts[2]);
        setFieldMonth(parts[3]);
        setFieldDow(parts[4]);
      }
    }
  };

  // Sync fields to formSchedule
  const handleFieldChange = (
    newMin: string,
    newHr: string,
    newDom: string,
    newMon: string,
    newDow: string
  ) => {
    setFieldMinute(newMin);
    setFieldHour(newHr);
    setFieldDom(newDom);
    setFieldMonth(newMon);
    setFieldDow(newDow);
    const combined = `${newMin.trim() || '*'} ${newHr.trim() || '*'} ${newDom.trim() || '*'} ${newMon.trim() || '*'} ${newDow.trim() || '*'}`;
    setFormSchedule(combined);
    setSelectedPreset('');
  };

  // Open Create Modal
  const openCreateModal = () => {
    setModalMode('create');
    setEditingJob(null);
    setFormOwner(eligibleUsers[0]?.username || 'root');
    setFormSchedule('0 0 * * *');
    setFieldMinute('0');
    setFieldHour('0');
    setFieldDom('*');
    setFieldMonth('*');
    setFieldDow('*');
    setUseSpecial(false);
    setFormCommand('');
    setFormComment('');
    setFormEnabled(true);
    setSelectedPreset('0 0 * * *');
    setError(null);
  };

  // Open Edit Modal
  const openEditModal = (job: CronJob) => {
    setModalMode('edit');
    setEditingJob(job);
    setFormOwner(job.owner);
    setFormSchedule(job.schedule);
    setFormCommand(job.command);
    setFormComment(job.comment || '');
    setFormEnabled(job.enabled);
    setSelectedPreset('');

    if (job.schedule.startsWith('@')) {
      setUseSpecial(true);
      setSpecialExpr(job.schedule);
    } else {
      setUseSpecial(false);
      const parts = job.schedule.split(' ');
      if (parts.length === 5) {
        setFieldMinute(parts[0]);
        setFieldHour(parts[1]);
        setFieldDom(parts[2]);
        setFieldMonth(parts[3]);
        setFieldDow(parts[4]);
      }
    }
    setError(null);
  };

  // Submit Create or Edit
  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    setError(null);

    const effectiveSchedule = useSpecial ? specialExpr : formSchedule;

    try {
      if (modalMode === 'create') {
        await apiClient.createCronJob({
          owner: formOwner,
          schedule: effectiveSchedule,
          command: formCommand,
          comment: formComment || null,
          enabled: formEnabled,
        });
        setSuccessMessage(`Cron job successfully created for ${formOwner}`);
      } else if (modalMode === 'edit' && editingJob) {
        await apiClient.updateCronJob(editingJob.id, {
          owner: formOwner,
          schedule: effectiveSchedule,
          command: formCommand,
          comment: formComment || null,
          enabled: formEnabled,
          expected_hash: editingJob.original_hash || undefined,
        });
        setSuccessMessage(`Cron job '${editingJob.id}' successfully updated`);
      }
      setModalMode(null);
      fetchData();
    } catch (err: any) {
      setError(err.message || 'Operation failed');
    } finally {
      setActionLoading(false);
    }
  };

  // Toggle Enable / Disable
  const handleToggleEnable = async (job: CronJob) => {
    if (!canUpdate || !job.is_editable) return;
    setActionLoading(true);
    setError(null);
    try {
      await apiClient.updateCronJob(job.id, {
        owner: job.owner,
        schedule: job.schedule,
        command: job.command,
        comment: job.comment || null,
        enabled: !job.enabled,
        expected_hash: job.original_hash || undefined,
      });
      setSuccessMessage(`Job ${job.enabled ? 'disabled' : 'enabled'} successfully`);
      fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to toggle job status');
    } finally {
      setActionLoading(false);
    }
  };

  // Delete Job
  const handleDeleteConfirm = async () => {
    if (!deleteJob) return;
    setActionLoading(true);
    setError(null);
    try {
      await apiClient.deleteCronJob(deleteJob.id, deleteJob.owner, deleteJob.original_hash || undefined);
      setSuccessMessage(`Cron job '${deleteJob.id}' deleted successfully`);
      setDeleteJob(null);
      fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to delete cron job');
    } finally {
      setActionLoading(false);
    }
  };

  // Source styling helper
  const getSourceBadge = (source: string) => {
    switch (source) {
      case 'USER_CRONTAB':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-blue-950/70 text-blue-300 border border-blue-800/60">
            <User className="w-3 h-3" />
            <span>User Crontab</span>
          </span>
        );
      case 'SYSTEM_CRONTAB':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-purple-950/70 text-purple-300 border border-purple-800/60">
            <FileCode className="w-3 h-3" />
            <span>/etc/crontab</span>
          </span>
        );
      case 'CRON_D_DIRECTORY':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-indigo-950/70 text-indigo-300 border border-indigo-800/60">
            <Folder className="w-3 h-3" />
            <span>/etc/cron.d</span>
          </span>
        );
      case 'PERIODIC_DIRECTORY':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-950/70 text-amber-300 border border-amber-800/60">
            <Calendar className="w-3 h-3" />
            <span>Periodic Script</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-neutral-800 text-neutral-300">
            <span>{source}</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6" id="cron-management-view">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-neutral-100 flex items-center gap-2">
            <Clock className="w-5 h-5 text-neutral-400" />
            <span>Scheduled Jobs / Cron Management</span>
          </h1>
          <p className="text-xs text-neutral-400 mt-1">
            Inspect, schedule, and manage automated Linux crontab jobs with safe unprivileged controls and zero arbitrary command execution.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            id="cron-refresh-btn"
            onClick={fetchData}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 hover:text-white rounded-md text-xs font-medium border border-neutral-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          {canCreate && (
            <button
              id="cron-create-btn"
              onClick={openCreateModal}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-md text-xs font-medium transition-colors shadow-xs"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New Cron Job</span>
            </button>
          )}
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-3 bg-red-950/60 border border-red-800/80 rounded-lg text-xs text-red-200 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-200">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {successMessage && (
        <div className="p-3 bg-emerald-950/60 border border-emerald-800/80 rounded-lg text-xs text-emerald-200 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{successMessage}</span>
          </div>
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-400 hover:text-emerald-200">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Overview KPI Cards */}
      {overview && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <div className="p-3.5 bg-neutral-900 border border-neutral-800 rounded-lg">
            <div className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">
              Total Scheduled
            </div>
            <div className="text-2xl font-semibold text-neutral-100 mt-1">
              {overview.total_jobs}
            </div>
            <div className="text-[11px] text-neutral-500 mt-0.5">Across all sources</div>
          </div>

          <div className="p-3.5 bg-neutral-900 border border-neutral-800 rounded-lg">
            <div className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">
              Active Jobs
            </div>
            <div className="text-2xl font-semibold text-emerald-400 mt-1">
              {overview.active_jobs}
            </div>
            <div className="text-[11px] text-neutral-500 mt-0.5">Scheduled to execute</div>
          </div>

          <div className="p-3.5 bg-neutral-900 border border-neutral-800 rounded-lg">
            <div className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">
              Disabled Jobs
            </div>
            <div className="text-2xl font-semibold text-neutral-400 mt-1">
              {overview.disabled_jobs}
            </div>
            <div className="text-[11px] text-neutral-500 mt-0.5">Commented out / paused</div>
          </div>

          <div className="p-3.5 bg-neutral-900 border border-neutral-800 rounded-lg">
            <div className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">
              Users with Crontab
            </div>
            <div className="text-2xl font-semibold text-blue-400 mt-1">
              {overview.users_with_crontabs}
            </div>
            <div className="text-[11px] text-neutral-500 mt-0.5">
              {overview.user_jobs_count} user jobs
            </div>
          </div>

          <div className="p-3.5 bg-neutral-900 border border-neutral-800 rounded-lg col-span-2 sm:col-span-1">
            <div className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">
              System Sources
            </div>
            <div className="text-2xl font-semibold text-purple-400 mt-1">
              {overview.system_jobs_count + overview.cron_d_jobs_count + overview.periodic_jobs_count}
            </div>
            <div className="text-[11px] text-neutral-500 mt-0.5">
              {overview.cron_d_jobs_count} cron.d, {overview.periodic_jobs_count} periodic
            </div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="p-3 bg-neutral-900 border border-neutral-800 rounded-lg flex flex-col md:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            id="cron-search-input"
            type="text"
            placeholder="Search by command, comment, schedule, or owner..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-3 py-1.5 bg-neutral-800 border border-neutral-700 rounded-md text-xs text-neutral-200 placeholder-neutral-500 focus:outline-hidden focus:border-blue-500"
          />
        </div>

        <div className="flex items-center space-x-2 w-full md:w-auto shrink-0">
          <select
            id="cron-owner-filter"
            value={selectedOwner}
            onChange={(e) => {
              setSelectedOwner(e.target.value);
              setPage(1);
            }}
            className="px-2.5 py-1.5 bg-neutral-800 border border-neutral-700 rounded-md text-xs text-neutral-300 focus:outline-hidden focus:border-blue-500"
          >
            <option value="">All Owners</option>
            {eligibleUsers.map((u) => (
              <option key={u.username} value={u.username}>
                {u.username}
              </option>
            ))}
          </select>

          <select
            id="cron-source-filter"
            value={selectedSource}
            onChange={(e) => {
              setSelectedSource(e.target.value);
              setPage(1);
            }}
            className="px-2.5 py-1.5 bg-neutral-800 border border-neutral-700 rounded-md text-xs text-neutral-300 focus:outline-hidden focus:border-blue-500"
          >
            <option value="">All Sources</option>
            <option value="USER_CRONTAB">User Crontab</option>
            <option value="SYSTEM_CRONTAB">/etc/crontab</option>
            <option value="CRON_D_DIRECTORY">/etc/cron.d/*</option>
            <option value="PERIODIC_DIRECTORY">Periodic (/etc/cron.*)</option>
          </select>

          <select
            id="cron-status-filter"
            value={selectedStatus}
            onChange={(e) => {
              setSelectedStatus(e.target.value);
              setPage(1);
            }}
            className="px-2.5 py-1.5 bg-neutral-800 border border-neutral-700 rounded-md text-xs text-neutral-300 focus:outline-hidden focus:border-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="active">Active Only</option>
            <option value="disabled">Disabled Only</option>
          </select>
        </div>
      </div>

      {/* Jobs Table */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse" id="cron-jobs-table">
            <thead>
              <tr className="border-b border-neutral-800 bg-neutral-950/40 text-[11px] font-medium text-neutral-400 uppercase tracking-wider">
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Owner</th>
                <th className="py-2.5 px-3">Schedule</th>
                <th className="py-2.5 px-3">Command</th>
                <th className="py-2.5 px-3">Source</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/60 text-xs">
              {loading && jobs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-neutral-400">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-neutral-500" />
                    <span>Loading scheduled cron jobs...</span>
                  </td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-neutral-400">
                    No scheduled cron jobs found matching your filters.
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr
                    key={job.id}
                    className="hover:bg-neutral-850/50 transition-colors group"
                  >
                    {/* Status */}
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      {job.enabled ? (
                        <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-950/80 text-emerald-300 border border-emerald-800/60">
                          <CheckCircle className="w-2.5 h-2.5" />
                          <span>Active</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-neutral-800 text-neutral-400 border border-neutral-700">
                          <XCircle className="w-2.5 h-2.5" />
                          <span>Disabled</span>
                        </span>
                      )}
                    </td>

                    {/* Owner */}
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span className="inline-flex items-center space-x-1 font-mono text-neutral-200">
                        <User className="w-3 h-3 text-neutral-500" />
                        <span>{job.owner}</span>
                      </span>
                    </td>

                    {/* Schedule */}
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <div>
                        <span className="font-mono text-xs bg-neutral-800 px-1.5 py-0.5 rounded border border-neutral-700 text-blue-300">
                          {job.schedule}
                        </span>
                        {job.description && (
                          <div className="text-[11px] text-neutral-400 mt-0.5">
                            {job.description}
                          </div>
                        )}
                      </div>
                    </td>

                    {/* Command */}
                    <td className="py-2.5 px-3 max-w-xs md:max-w-md truncate">
                      <div>
                        <span className="font-mono text-neutral-200 truncate block text-[11px]">
                          {job.command}
                        </span>
                        {job.comment && (
                          <div className="text-[10px] text-neutral-400 truncate italic">
                            # {job.comment}
                          </div>
                        )}
                      </div>
                    </td>

                    {/* Source */}
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      {getSourceBadge(job.source)}
                    </td>

                    {/* Actions */}
                    <td className="py-2.5 px-3 whitespace-nowrap text-right">
                      <div className="inline-flex items-center space-x-1">
                        <button
                          title="Inspect Details"
                          onClick={() => setDetailJob(job)}
                          className="p-1 text-neutral-400 hover:text-white rounded hover:bg-neutral-800 transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>

                        {canUpdate && job.is_editable && (
                          <>
                            <button
                              title={job.enabled ? 'Pause / Disable' : 'Resume / Enable'}
                              onClick={() => handleToggleEnable(job)}
                              disabled={actionLoading}
                              className="p-1 text-neutral-400 hover:text-amber-300 rounded hover:bg-neutral-800 transition-colors"
                            >
                              <Power className="w-3.5 h-3.5" />
                            </button>
                            <button
                              title="Edit Job"
                              onClick={() => openEditModal(job)}
                              disabled={actionLoading}
                              className="p-1 text-neutral-400 hover:text-blue-300 rounded hover:bg-neutral-800 transition-colors"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}

                        {canDelete && job.is_editable && (
                          <button
                            title="Delete Job"
                            onClick={() => setDeleteJob(job)}
                            disabled={actionLoading}
                            className="p-1 text-neutral-400 hover:text-red-400 rounded hover:bg-neutral-800 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {!job.is_editable && (
                          <span
                            title="System managed source (Read-only)"
                            className="p-1 text-neutral-600 cursor-not-allowed"
                          >
                            <Lock className="w-3.5 h-3.5" />
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="p-3 border-t border-neutral-800 flex items-center justify-between text-xs text-neutral-400">
          <div>
            Showing {jobs.length} of {total} scheduled jobs
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="p-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded border border-neutral-700 disabled:opacity-40 transition-colors"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span>
              Page {page} of {totalPages || 1}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loading}
              className="p-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded border border-neutral-700 disabled:opacity-40 transition-colors"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Create / Edit Modal */}
      {modalMode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 overflow-y-auto">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl max-w-lg w-full p-5 space-y-4 shadow-xl my-8">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <h2 className="text-sm font-semibold text-neutral-100 flex items-center gap-2">
                <Clock className="w-4 h-4 text-blue-400" />
                <span>{modalMode === 'create' ? 'Create Scheduled Cron Job' : 'Edit Scheduled Cron Job'}</span>
              </h2>
              <button
                onClick={() => setModalMode(null)}
                className="text-neutral-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Safety Notice */}
            <div className="p-2.5 bg-blue-950/40 border border-blue-800/60 rounded-lg text-[11px] text-blue-200 flex items-start space-x-2">
              <Info className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" />
              <span>
                Commands are stored securely into the target user crontab and evaluated by the OS cron daemon.
                Commands are never executed or parsed by this web control panel.
              </span>
            </div>

            <form onSubmit={handleFormSubmit} className="space-y-3.5 text-xs">
              {/* Owner */}
              <div>
                <label className="block text-[11px] font-medium text-neutral-300 mb-1">
                  Crontab Owner (OS User)
                </label>
                <select
                  value={formOwner}
                  disabled={modalMode === 'edit'}
                  onChange={(e) => setFormOwner(e.target.value)}
                  className="w-full px-2.5 py-1.5 bg-neutral-800 border border-neutral-700 rounded-md text-neutral-200 focus:outline-hidden focus:border-blue-500 disabled:opacity-60 font-mono"
                >
                  {eligibleUsers.map((u) => (
                    <option key={u.username} value={u.username}>
                      {u.username} (UID: {u.uid})
                    </option>
                  ))}
                </select>
              </div>

              {/* Presets */}
              <div>
                <label className="block text-[11px] font-medium text-neutral-300 mb-1">
                  Schedule Preset
                </label>
                <select
                  value={selectedPreset}
                  onChange={(e) => handlePresetSelect(e.target.value)}
                  className="w-full px-2.5 py-1.5 bg-neutral-800 border border-neutral-700 rounded-md text-neutral-200 focus:outline-hidden focus:border-blue-500"
                >
                  <option value="">-- Custom Schedule --</option>
                  {PRESETS.map((p) => (
                    <option key={p.schedule} value={p.schedule}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Schedule Type Toggle */}
              <div className="flex items-center space-x-4 pt-1">
                <label className="inline-flex items-center space-x-1.5 text-neutral-300 cursor-pointer">
                  <input
                    type="radio"
                    name="schedType"
                    checked={!useSpecial}
                    onChange={() => setUseSpecial(false)}
                    className="text-blue-500"
                  />
                  <span>Standard 5-Field Cron</span>
                </label>
                <label className="inline-flex items-center space-x-1.5 text-neutral-300 cursor-pointer">
                  <input
                    type="radio"
                    name="schedType"
                    checked={useSpecial}
                    onChange={() => setUseSpecial(true)}
                    className="text-blue-500"
                  />
                  <span>Special Expression (@reboot, @daily, etc.)</span>
                </label>
              </div>

              {/* 5-field inputs */}
              {!useSpecial ? (
                <div className="grid grid-cols-5 gap-1.5 p-2.5 bg-neutral-950/50 border border-neutral-800 rounded-lg">
                  <div>
                    <label className="block text-[10px] text-neutral-400 mb-0.5">Min (0-59)</label>
                    <input
                      type="text"
                      value={fieldMinute}
                      onChange={(e) => handleFieldChange(e.target.value, fieldHour, fieldDom, fieldMonth, fieldDow)}
                      className="w-full px-2 py-1 bg-neutral-800 border border-neutral-700 rounded text-center font-mono text-neutral-200"
                      placeholder="*"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-neutral-400 mb-0.5">Hour (0-23)</label>
                    <input
                      type="text"
                      value={fieldHour}
                      onChange={(e) => handleFieldChange(fieldMinute, e.target.value, fieldDom, fieldMonth, fieldDow)}
                      className="w-full px-2 py-1 bg-neutral-800 border border-neutral-700 rounded text-center font-mono text-neutral-200"
                      placeholder="*"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-neutral-400 mb-0.5">DOM (1-31)</label>
                    <input
                      type="text"
                      value={fieldDom}
                      onChange={(e) => handleFieldChange(fieldMinute, fieldHour, e.target.value, fieldMonth, fieldDow)}
                      className="w-full px-2 py-1 bg-neutral-800 border border-neutral-700 rounded text-center font-mono text-neutral-200"
                      placeholder="*"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-neutral-400 mb-0.5">Month (1-12)</label>
                    <input
                      type="text"
                      value={fieldMonth}
                      onChange={(e) => handleFieldChange(fieldMinute, fieldHour, fieldDom, e.target.value, fieldDow)}
                      className="w-full px-2 py-1 bg-neutral-800 border border-neutral-700 rounded text-center font-mono text-neutral-200"
                      placeholder="*"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-neutral-400 mb-0.5">DOW (0-7)</label>
                    <input
                      type="text"
                      value={fieldDow}
                      onChange={(e) => handleFieldChange(fieldMinute, fieldHour, fieldDom, fieldMonth, e.target.value)}
                      className="w-full px-2 py-1 bg-neutral-800 border border-neutral-700 rounded text-center font-mono text-neutral-200"
                      placeholder="*"
                    />
                  </div>
                </div>
              ) : (
                <div>
                  <label className="block text-[11px] font-medium text-neutral-300 mb-1">
                    Special String Expression
                  </label>
                  <select
                    value={specialExpr}
                    onChange={(e) => setSpecialExpr(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-neutral-800 border border-neutral-700 rounded-md text-neutral-200 focus:outline-hidden focus:border-blue-500 font-mono"
                  >
                    <option value="@reboot">@reboot (Run at system startup)</option>
                    <option value="@hourly">@hourly (Every hour at minute 0)</option>
                    <option value="@daily">@daily (Every day at midnight)</option>
                    <option value="@midnight">@midnight (Every day at midnight)</option>
                    <option value="@weekly">@weekly (Every Sunday at midnight)</option>
                    <option value="@monthly">@monthly (First day of month)</option>
                    <option value="@yearly">@yearly (Jan 1 at midnight)</option>
                    <option value="@annually">@annually (Jan 1 at midnight)</option>
                  </select>
                </div>
              )}

              {/* Schedule Preview */}
              <div className="flex items-center space-x-2 text-[11px] text-neutral-400 bg-neutral-950/30 p-2 rounded border border-neutral-800">
                <span className="font-semibold text-neutral-300">Effective Schedule:</span>
                <span className="font-mono text-blue-300">{useSpecial ? specialExpr : formSchedule}</span>
              </div>

              {/* Command */}
              <div>
                <label className="block text-[11px] font-medium text-neutral-300 mb-1">
                  Command or Script Path <span className="text-red-400">*</span>
                </label>
                <textarea
                  rows={2}
                  value={formCommand}
                  onChange={(e) => setFormCommand(e.target.value)}
                  placeholder="/usr/local/bin/backup.sh > /dev/null 2>&1"
                  required
                  className="w-full px-2.5 py-1.5 bg-neutral-800 border border-neutral-700 rounded-md text-neutral-200 font-mono text-xs focus:outline-hidden focus:border-blue-500"
                />
              </div>

              {/* Comment */}
              <div>
                <label className="block text-[11px] font-medium text-neutral-300 mb-1">
                  Descriptive Comment (Optional)
                </label>
                <input
                  type="text"
                  value={formComment}
                  onChange={(e) => setFormComment(e.target.value)}
                  placeholder="Daily database backup and log cleanup"
                  className="w-full px-2.5 py-1.5 bg-neutral-800 border border-neutral-700 rounded-md text-neutral-200 focus:outline-hidden focus:border-blue-500"
                />
              </div>

              {/* Enabled checkbox */}
              <div className="flex items-center space-x-2 pt-1">
                <input
                  id="form-enabled-check"
                  type="checkbox"
                  checked={formEnabled}
                  onChange={(e) => setFormEnabled(e.target.checked)}
                  className="rounded bg-neutral-800 border-neutral-700 text-blue-600 focus:ring-0"
                />
                <label htmlFor="form-enabled-check" className="text-xs text-neutral-300 cursor-pointer">
                  Enable job immediately in crontab (uncheck to comment out / disable)
                </label>
              </div>

              {/* Modal buttons */}
              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-neutral-800">
                <button
                  type="button"
                  onClick={() => setModalMode(null)}
                  className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded-md font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-md font-medium transition-colors disabled:opacity-50 flex items-center space-x-1.5"
                >
                  {actionLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>{modalMode === 'create' ? 'Create Job' : 'Save Changes'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center space-x-2 text-red-400">
              <AlertTriangle className="w-5 h-5" />
              <h3 className="font-semibold text-neutral-100 text-sm">Delete Scheduled Cron Job</h3>
            </div>

            <p className="text-xs text-neutral-300">
              Are you sure you want to delete this cron job from <strong className="text-white">{deleteJob.owner}</strong>&apos;s crontab?
              All other crontab entries and comments will remain completely preserved.
            </p>

            <div className="p-3 bg-neutral-950/60 border border-neutral-800 rounded-lg text-xs space-y-1.5 font-mono">
              <div className="text-neutral-400">Schedule: <span className="text-blue-300">{deleteJob.schedule}</span></div>
              <div className="text-neutral-400 truncate">Command: <span className="text-neutral-200">{deleteJob.command}</span></div>
              {deleteJob.comment && (
                <div className="text-neutral-500 text-[11px] italic"># {deleteJob.comment}</div>
              )}
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setDeleteJob(null)}
                disabled={actionLoading}
                className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded-md text-xs font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                disabled={actionLoading}
                className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-md text-xs font-medium transition-colors flex items-center space-x-1.5"
              >
                {actionLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                <span>Confirm Delete</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Job Details Modal */}
      {detailJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 overflow-y-auto">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl max-w-lg w-full p-5 space-y-4 shadow-xl my-8">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <h2 className="text-sm font-semibold text-neutral-100 flex items-center gap-2">
                <Clock className="w-4 h-4 text-neutral-400" />
                <span>Cron Job Details</span>
              </h2>
              <button
                onClick={() => setDetailJob(null)}
                className="text-neutral-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="text-neutral-400 block text-[11px]">Job Identifier:</span>
                <span className="font-mono text-neutral-200">{detailJob.id}</span>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-neutral-400 block text-[11px]">Owner:</span>
                  <span className="font-medium text-neutral-200">{detailJob.owner}</span>
                </div>
                <div>
                  <span className="text-neutral-400 block text-[11px]">Source:</span>
                  <span className="text-neutral-200">{detailJob.source}</span>
                </div>
              </div>

              <div>
                <span className="text-neutral-400 block text-[11px]">Schedule Expression:</span>
                <div className="flex items-center space-x-2 mt-0.5">
                  <span className="font-mono bg-neutral-800 px-2 py-0.5 rounded text-blue-300">
                    {detailJob.schedule}
                  </span>
                  <span className="text-neutral-400">{detailJob.description}</span>
                </div>
              </div>

              <div>
                <span className="text-neutral-400 block text-[11px]">Full Command:</span>
                <pre className="mt-1 p-2.5 bg-neutral-950/70 border border-neutral-800 rounded-md font-mono text-[11px] text-neutral-200 whitespace-pre-wrap break-all select-all">
                  {detailJob.command}
                </pre>
              </div>

              {detailJob.comment && (
                <div>
                  <span className="text-neutral-400 block text-[11px]">Comment / Note:</span>
                  <div className="text-neutral-300 bg-neutral-800/60 p-2 rounded mt-0.5 italic">
                    {detailJob.comment}
                  </div>
                </div>
              )}

              {detailJob.source_file && (
                <div>
                  <span className="text-neutral-400 block text-[11px]">Source File:</span>
                  <span className="font-mono text-neutral-300 text-[11px]">
                    {detailJob.source_file}
                    {detailJob.line_number && ` (Line ${detailJob.line_number})`}
                  </span>
                </div>
              )}

              {detailJob.original_hash && (
                <div>
                  <span className="text-neutral-400 block text-[11px]">Concurrency Fingerprint:</span>
                  <span className="font-mono text-neutral-500 text-[10px]">
                    {detailJob.original_hash}
                  </span>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-3 border-t border-neutral-800">
              <button
                type="button"
                onClick={() => setDetailJob(null)}
                className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 rounded-md text-xs font-medium transition-colors"
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
