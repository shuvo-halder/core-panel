import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  Globe,
  Server,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
  Plus,
  Trash2,
  Power,
  ExternalLink,
  Shield,
  ShieldCheck,
  ShieldAlert,
  Search,
  Code,
  Check,
  X,
  FileText,
  Lock,
} from 'lucide-react';
import { apiClient, ApiError } from '../api/client';
import {
  NginxOverview,
  SiteConfig,
  SiteCreateInput,
  SiteUpdateInput,
} from '../types/webserver';

interface WebServerManagementProps {
  permissions: string[];
  onNavigateLogs?: (source: string) => void;
}

export const WebServerManagement: React.FC<WebServerManagementProps> = ({
  permissions,
  onNavigateLogs,
}) => {
  const [overview, setOverview] = useState<NginxOverview | null>(null);
  const [sites, setSites] = useState<SiteConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<'ALL' | 'PROXY' | 'STATIC' | 'MANAGED' | 'UNMANAGED'>('ALL');

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingSite, setEditingSite] = useState<SiteConfig | null>(null);
  const [inspectingSite, setInspectingSite] = useState<SiteConfig | null>(null);
  const [deletingSite, setDeletingSite] = useState<SiteConfig | null>(null);
  const [showReloadConfirm, setShowReloadConfirm] = useState(false);

  // Form State
  const [formName, setFormName] = useState('');
  const [formServerNames, setFormServerNames] = useState('');
  const [formListen, setFormListen] = useState(80);
  const [formListenIPv6, setFormListenIPv6] = useState(false);
  const [formIsProxy, setFormIsProxy] = useState(false);
  const [formProxyTarget, setFormProxyTarget] = useState('http://127.0.0.1:3000');
  const [formProxyPreserveHost, setFormProxyPreserveHost] = useState(true);
  const [formRoot, setFormRoot] = useState('/var/www/html');
  const [formClientMaxBodySize, setFormClientMaxBodySize] = useState('10m');
  const [formSslEnabled, setFormSslEnabled] = useState(false);
  const [formSslCert, setFormSslCert] = useState('');
  const [formSslKey, setFormSslKey] = useState('');
  const [formAccessLog, setFormAccessLog] = useState(true);
  const [formErrorLog, setFormErrorLog] = useState(true);
  const [formEnabled, setFormEnabled] = useState(true);

  // Form validation preview
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{ valid: boolean; error?: string | null } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Permission Checks
  const canCreate = permissions.includes('webserver.create') || permissions.includes('*');
  const canUpdate = permissions.includes('webserver.update') || permissions.includes('*');
  const canDelete = permissions.includes('webserver.delete') || permissions.includes('*');
  const canEnable = permissions.includes('webserver.enable') || permissions.includes('*');
  const canDisable = permissions.includes('webserver.disable') || permissions.includes('*');
  const canReload = permissions.includes('webserver.reload') || permissions.includes('*');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [overviewData, sitesData] = await Promise.all([
        apiClient.getWebserverOverview(),
        apiClient.listWebserverSites(),
      ]);
      setOverview(overviewData);
      setSites(sitesData);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load web server details.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Success message auto-dismiss
  useEffect(() => {
    if (actionSuccess) {
      const timer = setTimeout(() => setActionSuccess(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [actionSuccess]);

  // Open Create Modal
  const handleOpenCreate = () => {
    setFormName('');
    setFormServerNames('');
    setFormListen(80);
    setFormListenIPv6(false);
    setFormIsProxy(false);
    setFormProxyTarget('http://127.0.0.1:3000');
    setFormProxyPreserveHost(true);
    setFormRoot('/var/www/html');
    setFormClientMaxBodySize('10m');
    setFormSslEnabled(false);
    setFormSslCert('');
    setFormSslKey('');
    setFormAccessLog(true);
    setFormErrorLog(true);
    setFormEnabled(true);
    setValidationResult(null);
    setFormError(null);
    setShowCreateModal(true);
  };

  // Open Edit Modal
  const handleOpenEdit = (site: SiteConfig) => {
    setEditingSite(site);
    setFormName(site.name);
    setFormServerNames(site.server_names.join(' '));
    setFormListen(site.listen);
    setFormListenIPv6(site.listen_ipv6);
    setFormIsProxy(site.proxy.enabled);
    setFormProxyTarget(site.proxy.target || 'http://127.0.0.1:3000');
    setFormProxyPreserveHost(site.proxy.preserve_host);
    setFormRoot(site.root || '/var/www/html');
    setFormClientMaxBodySize(site.client_max_body_size || '10m');
    setFormSslEnabled(site.ssl.enabled);
    setFormSslCert(site.ssl.certificate || '');
    setFormSslKey(''); // Never expose existing key path
    setFormAccessLog(site.access_log);
    setFormErrorLog(site.error_log);
    setFormEnabled(site.enabled);
    setValidationResult(null);
    setFormError(null);
  };

  // Validate Candidate Config
  const handleValidateForm = async () => {
    setIsValidating(true);
    setFormError(null);
    try {
      const serverNamesList = formServerNames
        .split(/[,\s]+/)
        .map((s) => s.trim())
        .filter(Boolean);

      const candidate: SiteCreateInput = {
        name: formName || 'test-preview',
        server_names: serverNamesList.length > 0 ? serverNamesList : [formName || 'localhost'],
        listen: Number(formListen),
        listen_ipv6: formListenIPv6,
        proxy_enabled: formIsProxy,
        proxy_target: formIsProxy ? formProxyTarget : undefined,
        proxy_preserve_host: formProxyPreserveHost,
        root: !formIsProxy ? formRoot : undefined,
        ssl_enabled: formSslEnabled,
        ssl_certificate: formSslEnabled && formSslCert ? formSslCert : undefined,
        ssl_certificate_key: formSslEnabled && formSslKey ? formSslKey : undefined,
        access_log: formAccessLog,
        error_log: formErrorLog,
        index: ['index.html', 'index.htm'],
        client_max_body_size: formClientMaxBodySize,
        enabled: formEnabled,
      };

      const res = await apiClient.validateWebserverCandidate(candidate);
      setValidationResult(res);
      if (!res.valid) {
        setFormError(res.error || 'Nginx configuration syntax check failed.');
      }
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Validation request failed.';
      setValidationResult({ valid: false, error: msg });
      setFormError(msg);
    } finally {
      setIsValidating(false);
    }
  };

  // Submit Create or Update
  const handleSubmitForm = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);

    const serverNamesList = formServerNames
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);

    if (serverNamesList.length === 0) {
      setFormError('Please enter at least one server domain name.');
      setIsSubmitting(false);
      return;
    }

    try {
      if (editingSite) {
        // Update existing site
        const updatePayload: SiteUpdateInput = {
          server_names: serverNamesList,
          listen: Number(formListen),
          listen_ipv6: formListenIPv6,
          proxy_enabled: formIsProxy,
          proxy_target: formIsProxy ? formProxyTarget : undefined,
          proxy_preserve_host: formProxyPreserveHost,
          root: !formIsProxy ? formRoot : undefined,
          ssl_enabled: formSslEnabled,
          ssl_certificate: formSslEnabled && formSslCert ? formSslCert : undefined,
          ssl_certificate_key: formSslEnabled && formSslKey ? formSslKey : undefined,
          access_log: formAccessLog,
          error_log: formErrorLog,
          index: ['index.html', 'index.htm'],
          client_max_body_size: formClientMaxBodySize,
          enabled: formEnabled,
        };
        await apiClient.updateWebserverSite(editingSite.name, updatePayload);
        setActionSuccess(`Site '${editingSite.name}' updated and deployed successfully.`);
        setEditingSite(null);
      } else {
        // Create new site
        const createPayload: SiteCreateInput = {
          name: formName.trim().toLowerCase(),
          server_names: serverNamesList,
          listen: Number(formListen),
          listen_ipv6: formListenIPv6,
          proxy_enabled: formIsProxy,
          proxy_target: formIsProxy ? formProxyTarget : undefined,
          proxy_preserve_host: formProxyPreserveHost,
          root: !formIsProxy ? formRoot : undefined,
          ssl_enabled: formSslEnabled,
          ssl_certificate: formSslEnabled && formSslCert ? formSslCert : undefined,
          ssl_certificate_key: formSslEnabled && formSslKey ? formSslKey : undefined,
          access_log: formAccessLog,
          error_log: formErrorLog,
          index: ['index.html', 'index.htm'],
          client_max_body_size: formClientMaxBodySize,
          enabled: formEnabled,
        };
        await apiClient.createWebserverSite(createPayload);
        setActionSuccess(`Site '${createPayload.name}' created and deployed successfully.`);
        setShowCreateModal(false);
      }
      await loadData();
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError('Failed to deploy site configuration.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Toggle Enable / Disable
  const handleToggleEnable = async (site: SiteConfig) => {
    try {
      if (site.enabled) {
        await apiClient.disableWebserverSite(site.name);
        setActionSuccess(`Site '${site.name}' disabled.`);
      } else {
        await apiClient.enableWebserverSite(site.name);
        setActionSuccess(`Site '${site.name}' enabled.`);
      }
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Operation failed.';
      setError(msg);
    }
  };

  // Delete Site
  const handleConfirmDelete = async () => {
    if (!deletingSite) return;
    try {
      await apiClient.deleteWebserverSite(deletingSite.name);
      setActionSuccess(`Site '${deletingSite.name}' removed successfully.`);
      setDeletingSite(null);
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Delete failed.';
      setError(msg);
    }
  };

  // Reload Nginx
  const handleConfirmReload = async () => {
    setShowReloadConfirm(false);
    setLoading(true);
    try {
      const res = await apiClient.reloadWebserver();
      if (res.success) {
        setActionSuccess('Nginx service successfully reloaded.');
      } else {
        setError(`Reload failed: ${res.error}`);
      }
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Reload failed.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Filtered Sites
  const filteredSites = useMemo(() => {
    return sites.filter((site) => {
      const q = searchQuery.toLowerCase();
      const matchSearch =
        site.name.toLowerCase().includes(q) ||
        site.server_names.some((sn) => sn.toLowerCase().includes(q)) ||
        (site.proxy.target && site.proxy.target.toLowerCase().includes(q)) ||
        (site.root && site.root.toLowerCase().includes(q));

      if (!matchSearch) return false;

      if (typeFilter === 'PROXY') return site.proxy.enabled;
      if (typeFilter === 'STATIC') return !site.proxy.enabled;
      if (typeFilter === 'MANAGED') return site.managed;
      if (typeFilter === 'UNMANAGED') return !site.managed;
      return true;
    });
  }, [sites, searchQuery, typeFilter]);

  return (
    <div className="space-y-6">
      {/* Top Header & Quick Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Globe className="w-5 h-5 text-indigo-400" />
            <span>Web Server &amp; Reverse Proxy</span>
          </h1>
          <p className="text-xs text-neutral-400 mt-1">
            Nginx virtual hosts, reverse proxy routing, atomic deployments, and log inspection.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {canReload && (
            <button
              onClick={() => setShowReloadConfirm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-neutral-700 bg-neutral-800/80 hover:bg-neutral-800 text-neutral-200 text-xs font-medium transition-colors"
              title="Safely reload Nginx configuration (nginx.reload)"
            >
              <Power className="w-3.5 h-3.5 text-amber-400" />
              <span>Reload Nginx</span>
            </button>
          )}

          <button
            onClick={loadData}
            disabled={loading}
            className="p-1.5 rounded-lg border border-neutral-700 bg-neutral-800/80 hover:bg-neutral-800 text-neutral-300 transition-colors"
            title="Refresh Sites"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
          </button>

          {canCreate && (
            <button
              onClick={handleOpenCreate}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors shadow-xs"
            >
              <Plus className="w-4 h-4" />
              <span>New Site</span>
            </button>
          )}
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-200">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {actionSuccess && (
        <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-xs flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{actionSuccess}</span>
          </div>
          <button onClick={() => setActionSuccess(null)} className="text-emerald-400 hover:text-emerald-200">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl border border-neutral-800 bg-neutral-900/60 flex flex-col justify-between">
          <div className="flex items-center justify-between text-neutral-400 text-xs font-medium">
            <span>Nginx Daemon</span>
            <Server className="w-4 h-4 text-neutral-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-lg font-semibold text-white">
              {overview?.installed ? overview.version || 'Installed' : 'Not Detected'}
            </span>
            <span
              className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                overview?.service_active
                  ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/60'
                  : 'bg-neutral-800 text-neutral-400 border border-neutral-700'
              }`}
            >
              {overview?.service_active ? 'ACTIVE' : 'INACTIVE'}
            </span>
          </div>
        </div>

        <div className="p-3.5 rounded-xl border border-neutral-800 bg-neutral-900/60 flex flex-col justify-between">
          <div className="flex items-center justify-between text-neutral-400 text-xs font-medium">
            <span>Config Syntax</span>
            {overview?.config_valid ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-400" />
            )}
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span
              className={`text-lg font-semibold ${
                overview?.config_valid ? 'text-emerald-400' : 'text-rose-400'
              }`}
            >
              {overview?.config_valid ? 'Syntax OK' : 'Syntax Error'}
            </span>
            <span className="text-[10px] text-neutral-500 font-mono">nginx -t</span>
          </div>
        </div>

        <div className="p-3.5 rounded-xl border border-neutral-800 bg-neutral-900/60 flex flex-col justify-between">
          <div className="flex items-center justify-between text-neutral-400 text-xs font-medium">
            <span>Sites Enabled</span>
            <Globe className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-lg font-semibold text-white">
              {overview?.sites_enabled_count ?? sites.filter((s) => s.enabled).length}
            </span>
            <span className="text-xs text-neutral-400">
              of {overview?.sites_available_count ?? sites.length} available
            </span>
          </div>
        </div>

        <div className="p-3.5 rounded-xl border border-neutral-800 bg-neutral-900/60 flex flex-col justify-between">
          <div className="flex items-center justify-between text-neutral-400 text-xs font-medium">
            <span>Nginx Logs</span>
            <FileText className="w-4 h-4 text-neutral-500" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <button
              onClick={() => onNavigateLogs && onNavigateLogs('NGINX_ACCESS')}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium underline flex items-center gap-1"
            >
              Access <ExternalLink className="w-2.5 h-2.5" />
            </button>
            <span className="text-neutral-600">·</span>
            <button
              onClick={() => onNavigateLogs && onNavigateLogs('NGINX_ERROR')}
              className="text-xs text-rose-400 hover:text-rose-300 font-medium underline flex items-center gap-1"
            >
              Error <ExternalLink className="w-2.5 h-2.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 rounded-xl border border-neutral-800 bg-neutral-900/40">
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-neutral-500 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search domain, site, or root..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-neutral-700/80 bg-neutral-950 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-hidden focus:border-indigo-500 transition-colors"
          />
        </div>

        <div className="flex items-center gap-1.5 w-full sm:w-auto overflow-x-auto">
          {(['ALL', 'PROXY', 'STATIC', 'MANAGED', 'UNMANAGED'] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setTypeFilter(filter)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors shrink-0 ${
                typeFilter === filter
                  ? 'bg-neutral-700 text-white'
                  : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800'
              }`}
            >
              {filter === 'ALL'
                ? 'All Sites'
                : filter === 'PROXY'
                ? 'Reverse Proxy'
                : filter === 'STATIC'
                ? 'Static Web'
                : filter === 'MANAGED'
                ? 'Managed'
                : 'Unmanaged'}
            </button>
          ))}
        </div>
      </div>

      {/* Sites Table */}
      <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-neutral-800 bg-neutral-900/80 text-neutral-400 font-medium">
                <th className="py-3 px-4">Site Identity / Domain</th>
                <th className="py-3 px-4">Type &amp; Routing</th>
                <th className="py-3 px-4">Port</th>
                <th className="py-3 px-4">SSL / TLS</th>
                <th className="py-3 px-4">Managed</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/60">
              {filteredSites.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-10 text-center text-neutral-500">
                    {loading ? (
                      <span className="flex items-center justify-center gap-2">
                        <RefreshCw className="w-4 h-4 animate-spin text-neutral-400" />
                        Loading virtual hosts...
                      </span>
                    ) : (
                      <span>No virtual hosts found matching your criteria.</span>
                    )}
                  </td>
                </tr>
              ) : (
                filteredSites.map((site) => (
                  <tr key={site.name} className="hover:bg-neutral-850/50 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-neutral-200">{site.name}</div>
                      <div className="text-[11px] text-neutral-400 mt-0.5 truncate max-w-xs">
                        {site.server_names.join(', ')}
                      </div>
                    </td>

                    <td className="py-3 px-4">
                      {site.proxy.enabled ? (
                        <div>
                          <span className="font-medium text-indigo-400">Reverse Proxy</span>
                          <div className="text-[11px] text-neutral-400 font-mono mt-0.5 truncate max-w-xs">
                            {site.proxy.target}
                          </div>
                        </div>
                      ) : (
                        <div>
                          <span className="font-medium text-emerald-400">Static Web Root</span>
                          <div className="text-[11px] text-neutral-400 font-mono mt-0.5 truncate max-w-xs">
                            {site.root || '/var/www/html'}
                          </div>
                        </div>
                      )}
                    </td>

                    <td className="py-3 px-4 font-mono text-neutral-300">
                      {site.listen}
                      {site.listen_ipv6 && <span className="text-neutral-500 ml-1">(IPv6)</span>}
                    </td>

                    <td className="py-3 px-4">
                      {site.ssl.enabled ? (
                        <div className="flex items-center gap-1.5 text-emerald-400">
                          <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
                          <span className="text-[11px]">
                            {site.ssl.days_remaining !== null && site.ssl.days_remaining !== undefined
                              ? `${site.ssl.days_remaining}d remaining`
                              : site.ssl.cert_exists
                              ? 'Certificate Bound'
                              : 'Path missing'}
                          </span>
                        </div>
                      ) : (
                        <span className="text-[11px] text-neutral-500">Disabled</span>
                      )}
                    </td>

                    <td className="py-3 px-4">
                      {site.managed ? (
                        <span className="text-[11px] font-medium text-neutral-300 flex items-center gap-1">
                          <Check className="w-3 h-3 text-indigo-400" /> Managed
                        </span>
                      ) : (
                        <span
                          className="text-[11px] font-medium text-amber-400/90 flex items-center gap-1"
                          title="Configuration exists outside CorePanel template. Read-only."
                        >
                          <Lock className="w-3 h-3" /> Unmanaged
                        </span>
                      )}
                    </td>

                    <td className="py-3 px-4">
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                          site.enabled
                            ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50'
                            : 'bg-neutral-800 text-neutral-400 border border-neutral-700'
                        }`}
                      >
                        {site.enabled ? 'ENABLED' : 'DISABLED'}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => setInspectingSite(site)}
                          className="p-1 rounded text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition-colors"
                          title="Inspect Configuration"
                        >
                          <Code className="w-3.5 h-3.5" />
                        </button>

                        {(canEnable || canDisable) && (
                          <button
                            onClick={() => handleToggleEnable(site)}
                            className={`p-1 rounded transition-colors ${
                              site.enabled
                                ? 'text-amber-400 hover:bg-amber-950/40'
                                : 'text-emerald-400 hover:bg-emerald-950/40'
                            }`}
                            title={site.enabled ? 'Disable virtual host' : 'Enable virtual host'}
                          >
                            <Power className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {site.managed && canUpdate && (
                          <button
                            onClick={() => handleOpenEdit(site)}
                            className="p-1 rounded text-neutral-400 hover:text-indigo-400 hover:bg-neutral-800 transition-colors"
                            title="Edit Virtual Host"
                          >
                            <span className="text-[11px] font-medium px-1">Edit</span>
                          </button>
                        )}

                        {site.managed && canDelete && (
                          <button
                            onClick={() => setDeletingSite(site)}
                            className="p-1 rounded text-neutral-400 hover:text-rose-400 hover:bg-neutral-800 transition-colors"
                            title="Delete Virtual Host"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Inspect Site Details Modal */}
      {inspectingSite && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl max-w-lg w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Globe className="w-4 h-4 text-indigo-400" />
                <span>Site Details: {inspectingSite.name}</span>
              </h3>
              <button
                onClick={() => setInspectingSite(null)}
                className="text-neutral-400 hover:text-neutral-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2 bg-neutral-950 p-3 rounded-lg border border-neutral-800/80">
                <div>
                  <span className="text-neutral-500">Config Path:</span>
                  <p className="font-mono text-neutral-300 break-all mt-0.5">{inspectingSite.config_path}</p>
                </div>
                <div>
                  <span className="text-neutral-500">Managed by CorePanel:</span>
                  <p className="text-neutral-300 mt-0.5">{inspectingSite.managed ? 'Yes' : 'No (Read-Only)'}</p>
                </div>
                <div>
                  <span className="text-neutral-500">Domains:</span>
                  <p className="text-neutral-300 mt-0.5">{inspectingSite.server_names.join(', ')}</p>
                </div>
                <div>
                  <span className="text-neutral-500">Port / IPv6:</span>
                  <p className="text-neutral-300 mt-0.5 font-mono">
                    {inspectingSite.listen} {inspectingSite.listen_ipv6 ? '(IPv6 active)' : ''}
                  </p>
                </div>
              </div>

              {inspectingSite.ssl.enabled && (
                <div className="bg-neutral-950 p-3 rounded-lg border border-neutral-800/80 space-y-1">
                  <div className="font-medium text-emerald-400 flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5" /> SSL / TLS Certificate Info
                  </div>
                  <p className="text-neutral-400">Subject: {inspectingSite.ssl.subject || 'Unknown'}</p>
                  <p className="text-neutral-400">Issuer: {inspectingSite.ssl.issuer || 'Unknown'}</p>
                  <p className="text-neutral-400">Expires: {inspectingSite.ssl.not_after || 'Unknown'}</p>
                  <p className="text-neutral-400 font-mono text-[11px]">Cert Path: {inspectingSite.ssl.certificate}</p>
                </div>
              )}

              <div className="flex items-center justify-between pt-2">
                <span className="text-neutral-500 text-[11px]">
                  {inspectingSite.managed
                    ? 'Safe for atomic update and reload.'
                    : 'Unmanaged file. Edit disabled to prevent loss of admin configuration.'}
                </span>
                <button
                  onClick={() => setInspectingSite(null)}
                  className="px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-xs font-medium"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit Modal */}
      {(showCreateModal || editingSite) && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl max-w-xl w-full p-5 space-y-4 shadow-xl my-8">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Globe className="w-4 h-4 text-indigo-400" />
                <span>{editingSite ? `Edit Site: ${editingSite.name}` : 'Create New Virtual Host'}</span>
              </h3>
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setEditingSite(null);
                }}
                className="text-neutral-400 hover:text-neutral-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {formError && (
              <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            {validationResult && validationResult.valid && (
              <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Nginx candidate configuration syntax is valid (nginx -t ok).</span>
              </div>
            )}

            <form onSubmit={handleSubmitForm} className="space-y-4 text-xs">
              {/* Site Name */}
              <div>
                <label className="block text-neutral-300 font-medium mb-1">
                  Site Identity / Slug <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  disabled={Boolean(editingSite)}
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="example.com or api-server"
                  className="w-full px-3 py-2 rounded-lg border border-neutral-700 bg-neutral-950 text-neutral-200 focus:outline-hidden focus:border-indigo-500 disabled:opacity-50"
                />
                <p className="text-[11px] text-neutral-500 mt-1">
                  Alphanumeric identifier used for config filenames in /etc/nginx/sites-available/.
                </p>
              </div>

              {/* Server Names */}
              <div>
                <label className="block text-neutral-300 font-medium mb-1">
                  Server Names (Domains) <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={formServerNames}
                  onChange={(e) => setFormServerNames(e.target.value)}
                  placeholder="example.com www.example.com"
                  className="w-full px-3 py-2 rounded-lg border border-neutral-700 bg-neutral-950 text-neutral-200 focus:outline-hidden focus:border-indigo-500"
                />
                <p className="text-[11px] text-neutral-500 mt-1">
                  Space-separated list of hostnames (e.g. &quot;example.com www.example.com&quot;).
                </p>
              </div>

              {/* Port & IPv6 */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-neutral-300 font-medium mb-1">HTTP Listen Port</label>
                  <input
                    type="number"
                    min={1}
                    max={65535}
                    value={formListen}
                    onChange={(e) => setFormListen(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-700 bg-neutral-950 text-neutral-200 focus:outline-hidden focus:border-indigo-500 font-mono"
                  />
                </div>
                <div className="flex items-center gap-2 pt-6">
                  <input
                    type="checkbox"
                    id="listen-ipv6"
                    checked={formListenIPv6}
                    onChange={(e) => setFormListenIPv6(e.target.checked)}
                    className="rounded border-neutral-700 bg-neutral-950 text-indigo-600 focus:ring-indigo-500"
                  />
                  <label htmlFor="listen-ipv6" className="text-neutral-300 select-none">
                    Listen on IPv6 ([::])
                  </label>
                </div>
              </div>

              {/* Routing Mode Toggle */}
              <div className="pt-2 border-t border-neutral-800">
                <label className="block text-neutral-300 font-medium mb-2">Virtual Host Routing Type</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setFormIsProxy(false)}
                    className={`py-2 px-3 rounded-lg border text-center transition-colors ${
                      !formIsProxy
                        ? 'border-indigo-500 bg-indigo-950/30 text-indigo-300 font-medium'
                        : 'border-neutral-700 bg-neutral-950 text-neutral-400 hover:text-neutral-200'
                    }`}
                  >
                    Static Web Root
                  </button>
                  <button
                    type="button"
                    onClick={() => setFormIsProxy(true)}
                    className={`py-2 px-3 rounded-lg border text-center transition-colors ${
                      formIsProxy
                        ? 'border-indigo-500 bg-indigo-950/30 text-indigo-300 font-medium'
                        : 'border-neutral-700 bg-neutral-950 text-neutral-400 hover:text-neutral-200'
                    }`}
                  >
                    Reverse Proxy Upstream
                  </button>
                </div>
              </div>

              {/* Static Root Configuration */}
              {!formIsProxy ? (
                <div>
                  <label className="block text-neutral-300 font-medium mb-1">
                    Document Root <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    required={!formIsProxy}
                    value={formRoot}
                    onChange={(e) => setFormRoot(e.target.value)}
                    placeholder="/var/www/example.com/html"
                    className="w-full px-3 py-2 rounded-lg border border-neutral-700 bg-neutral-950 text-neutral-200 font-mono focus:outline-hidden focus:border-indigo-500"
                  />
                  <p className="text-[11px] text-neutral-500 mt-1">
                    Must reside in approved web directory (/var/www, /srv/www, or /home).
                  </p>
                </div>
              ) : (
                /* Reverse Proxy Configuration */
                <div className="space-y-3">
                  <div>
                    <label className="block text-neutral-300 font-medium mb-1">
                      Upstream Target URL <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      required={formIsProxy}
                      value={formProxyTarget}
                      onChange={(e) => setFormProxyTarget(e.target.value)}
                      placeholder="http://127.0.0.1:3000"
                      className="w-full px-3 py-2 rounded-lg border border-neutral-700 bg-neutral-950 text-neutral-200 font-mono focus:outline-hidden focus:border-indigo-500"
                    />
                    <p className="text-[11px] text-neutral-500 mt-1">
                      HTTP or HTTPS upstream target URL (e.g. http://127.0.0.1:3000).
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="preserve-host"
                      checked={formProxyPreserveHost}
                      onChange={(e) => setFormProxyPreserveHost(e.target.checked)}
                      className="rounded border-neutral-700 bg-neutral-950 text-indigo-600 focus:ring-indigo-500"
                    />
                    <label htmlFor="preserve-host" className="text-neutral-300 select-none">
                      Forward original Host header to upstream ($host)
                    </label>
                  </div>
                </div>
              )}

              {/* Max Body Size */}
              <div>
                <label className="block text-neutral-300 font-medium mb-1">Max Upload Body Size</label>
                <input
                  type="text"
                  value={formClientMaxBodySize}
                  onChange={(e) => setFormClientMaxBodySize(e.target.value)}
                  placeholder="10m, 50m, 100m"
                  className="w-full px-3 py-2 rounded-lg border border-neutral-700 bg-neutral-950 text-neutral-200 font-mono focus:outline-hidden focus:border-indigo-500"
                />
              </div>

              {/* SSL Configuration */}
              <div className="pt-2 border-t border-neutral-800 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-neutral-200 flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-indigo-400" /> SSL / TLS Configuration
                  </span>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="ssl-enable-toggle"
                      checked={formSslEnabled}
                      onChange={(e) => setFormSslEnabled(e.target.checked)}
                      className="rounded border-neutral-700 bg-neutral-950 text-indigo-600 focus:ring-indigo-500"
                    />
                    <label htmlFor="ssl-enable-toggle" className="text-neutral-300 select-none">
                      Enable SSL (port 443)
                    </label>
                  </div>
                </div>

                {formSslEnabled && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 bg-neutral-950 p-3 rounded-lg border border-neutral-800">
                    <div>
                      <label className="block text-neutral-400 mb-1">
                        Certificate Path <span className="text-rose-400">*</span>
                      </label>
                      <input
                        type="text"
                        required={formSslEnabled}
                        value={formSslCert}
                        onChange={(e) => setFormSslCert(e.target.value)}
                        placeholder="/etc/ssl/certs/example.crt"
                        className="w-full px-2.5 py-1.5 rounded border border-neutral-700 bg-neutral-900 text-neutral-200 font-mono focus:outline-hidden focus:border-indigo-500"
                      />
                    </div>
                    <div>
                      <label className="block text-neutral-400 mb-1">
                        Private Key Path {editingSite ? '(leave blank to keep)' : '*'}
                      </label>
                      <input
                        type="text"
                        required={formSslEnabled && !editingSite}
                        value={formSslKey}
                        onChange={(e) => setFormSslKey(e.target.value)}
                        placeholder="/etc/ssl/private/example.key"
                        className="w-full px-2.5 py-1.5 rounded border border-neutral-700 bg-neutral-900 text-neutral-200 font-mono focus:outline-hidden focus:border-indigo-500"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Logging & Enablement */}
              <div className="pt-2 border-t border-neutral-800 grid grid-cols-2 sm:grid-cols-3 gap-2">
                <label className="flex items-center gap-2 text-neutral-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formAccessLog}
                    onChange={(e) => setFormAccessLog(e.target.checked)}
                    className="rounded border-neutral-700 bg-neutral-950 text-indigo-600"
                  />
                  <span>Access Log</span>
                </label>
                <label className="flex items-center gap-2 text-neutral-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formErrorLog}
                    onChange={(e) => setFormErrorLog(e.target.checked)}
                    className="rounded border-neutral-700 bg-neutral-950 text-indigo-600"
                  />
                  <span>Error Log</span>
                </label>
                <label className="flex items-center gap-2 text-neutral-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formEnabled}
                    onChange={(e) => setFormEnabled(e.target.checked)}
                    className="rounded border-neutral-700 bg-neutral-950 text-indigo-600"
                  />
                  <span>Enable Immediately</span>
                </label>
              </div>

              {/* Modal Footer */}
              <div className="flex items-center justify-between pt-4 border-t border-neutral-800">
                <button
                  type="button"
                  onClick={handleValidateForm}
                  disabled={isValidating}
                  className="px-3 py-1.5 rounded-lg border border-neutral-700 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 font-medium transition-colors flex items-center gap-1.5"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isValidating ? 'animate-spin' : ''}`} />
                  <span>Test Syntax (nginx -t)</span>
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setShowCreateModal(false);
                      setEditingSite(null);
                    }}
                    className="px-3 py-1.5 rounded-lg text-neutral-400 hover:text-neutral-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors shadow-xs flex items-center gap-1.5"
                  >
                    {isSubmitting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                    <span>{editingSite ? 'Save & Deploy' : 'Deploy Virtual Host'}</span>
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingSite && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl max-w-sm w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center gap-3 text-rose-400">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <h3 className="text-sm font-bold text-white">Delete Virtual Host</h3>
            </div>
            <p className="text-xs text-neutral-300 leading-relaxed">
              Are you sure you want to remove the virtual host configuration for{' '}
              <span className="font-mono text-white font-semibold">{deletingSite.name}</span>?
              The active symlink and configuration will be deleted and Nginx reloaded atomically.
            </p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setDeletingSite(null)}
                className="px-3 py-1.5 rounded-lg text-neutral-400 hover:text-neutral-200 text-xs"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDelete}
                className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-medium"
              >
                Delete Site
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Safe Reload Confirmation Modal */}
      {showReloadConfirm && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl max-w-sm w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center gap-3 text-amber-400">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <h3 className="text-sm font-bold text-white">Reload Nginx Service</h3>
            </div>
            <div className="text-xs text-neutral-300 space-y-2 leading-relaxed">
              <p>
                This will trigger a graceful configuration reload:
              </p>
              <div className="bg-neutral-950 p-2.5 rounded font-mono text-[11px] text-neutral-400 border border-neutral-800/80">
                nginx -t → systemctl reload nginx.service
              </div>
              <p className="text-[11px] text-neutral-400">
                If syntax validation fails, reload will be aborted without disruption to existing connections.
              </p>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setShowReloadConfirm(false)}
                className="px-3 py-1.5 rounded-lg text-neutral-400 hover:text-neutral-200 text-xs"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReload}
                className="px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium"
              >
                Proceed with Reload
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
