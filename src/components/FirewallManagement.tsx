import React, { useState, useEffect, useCallback } from 'react';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  Plus,
  Trash2,
  RefreshCw,
  Power,
  AlertTriangle,
  Info,
  CheckCircle2,
  XCircle,
  Lock,
} from 'lucide-react';
import {
  FirewallRule,
  FirewallStatus,
  FirewallRuleCreateInput,
} from '../types/firewall';

interface FirewallManagementProps {
  permissions: string[];
}

export const FirewallManagement: React.FC<FirewallManagementProps> = ({ permissions }) => {
  const canManage = permissions.includes('firewall.manage');

  const [status, setStatus] = useState<FirewallStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modal states
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [showToggleModal, setShowToggleModal] = useState<boolean>(false);
  const [ruleToDelete, setRuleToDelete] = useState<FirewallRule | null>(null);

  // Form states
  const [port, setPort] = useState<string>('');
  const [protocol, setProtocol] = useState<'tcp' | 'udp' | 'any'>('tcp');
  const [action, setAction] = useState<'allow' | 'deny'>('allow');
  const [direction, setDirection] = useState<'in' | 'out'>('in');
  const [sourceIp, setSourceIp] = useState<string>('any');
  const [comment, setComment] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch('/api/v1/firewall/status');
      const data = await resp.json();
      if (!resp.ok || !data.success) {
        throw new Error(data.message || 'Failed to fetch firewall status');
      }
      setStatus(data.data);
    } catch (err: any) {
      setError(err.message || 'Failed to communicate with firewall service');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleAddRule = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setSubmitting(true);

    const payload: FirewallRuleCreateInput = {
      port: port.trim(),
      protocol,
      action,
      direction,
      source_ip: sourceIp.trim() || 'any',
      comment: comment.trim() || undefined,
    };

    try {
      const resp = await fetch('/api/v1/firewall/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok || !data.success) {
        throw new Error(data.message || 'Failed to create firewall rule');
      }
      setSuccessMsg(`Firewall rule created: ${payload.action.toUpperCase()} ${payload.port}/${payload.protocol}`);
      setShowAddModal(false);
      // Reset fields
      setPort('');
      setComment('');
      setSourceIp('any');
      await fetchStatus();
    } catch (err: any) {
      setError(err.message || 'Error creating rule');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteRule = async () => {
    if (!ruleToDelete) return;
    setError(null);
    setSuccessMsg(null);
    setSubmitting(true);

    try {
      const url = `/api/v1/firewall/rules/${ruleToDelete.rule_index}?expected_rule_signature=${encodeURIComponent(
        ruleToDelete.signature || ''
      )}`;
      const resp = await fetch(url, { method: 'DELETE' });
      const data = await resp.json();
      if (!resp.ok || !data.success) {
        throw new Error(data.message || 'Failed to delete rule');
      }
      setSuccessMsg(`Rule #${ruleToDelete.rule_index} deleted successfully.`);
      setRuleToDelete(null);
      await fetchStatus();
    } catch (err: any) {
      setError(err.message || 'Error deleting rule');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleFirewall = async () => {
    if (!status) return;
    setError(null);
    setSuccessMsg(null);
    setSubmitting(true);

    const targetState = !status.active;
    try {
      const resp = await fetch('/api/v1/firewall/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enable: targetState }),
      });
      const data = await resp.json();
      if (!resp.ok || !data.success) {
        throw new Error(data.message || 'Failed to toggle firewall');
      }
      setSuccessMsg(`Firewall ${targetState ? 'enabled' : 'disabled'} successfully.`);
      setShowToggleModal(false);
      await fetchStatus();
    } catch (err: any) {
      setError(err.message || 'Error toggling firewall');
    } finally {
      setSubmitting(false);
    }
  };

  const isLockoutRisk =
    action === 'deny' &&
    direction === 'in' &&
    (port === '22' || (status?.management_ports && status.management_ports.includes(Number(port))));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-neutral-800">
        <div>
          <h2 className="text-lg font-medium text-white flex items-center gap-2">
            <Shield className="w-5 h-5 text-neutral-400" />
            Firewall Management (UFW)
          </h2>
          <p className="text-xs text-neutral-400 mt-0.5">
            Configure packet filtering rules, inspect active policies, and manage server ingress/egress with anti-lockout protection
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            id="firewall-refresh-btn"
            onClick={fetchStatus}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-neutral-900 border border-neutral-800 hover:border-neutral-700 text-neutral-300 rounded text-xs font-medium transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          {canManage && status && (
            <>
              <button
                id="firewall-toggle-btn"
                onClick={() => setShowToggleModal(true)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium border transition ${
                  status.active
                    ? 'bg-red-950/40 border-red-800/80 text-red-300 hover:bg-red-900/50'
                    : 'bg-emerald-950/40 border-emerald-800/80 text-emerald-300 hover:bg-emerald-900/50'
                }`}
              >
                <Power className="w-3.5 h-3.5" />
                {status.active ? 'Disable Firewall' : 'Enable Firewall'}
              </button>
              <button
                id="firewall-add-rule-btn"
                onClick={() => setShowAddModal(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-neutral-100 hover:bg-white text-neutral-950 rounded text-xs font-medium transition shadow-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Rule
              </button>
            </>
          )}
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="p-3 bg-red-950/50 border border-red-800 rounded-md text-red-200 text-xs flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <div className="flex-1 font-mono">{error}</div>
          <button onClick={() => setError(null)} className="text-neutral-400 hover:text-white">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="p-3 bg-emerald-950/50 border border-emerald-800 rounded-md text-emerald-200 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-neutral-400 hover:text-white">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Overview Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        {/* State Card */}
        <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
          <div className="text-[11px] text-neutral-400 uppercase tracking-wider mb-1">Firewall State</div>
          <div className="flex items-center gap-2">
            {status?.active ? (
              <span className="text-sm font-semibold text-emerald-400 flex items-center gap-1.5 font-mono">
                <ShieldCheck className="w-4 h-4 text-emerald-400" /> Active (Enforcing)
              </span>
            ) : (
              <span className="text-sm font-semibold text-amber-400 flex items-center gap-1.5 font-mono">
                <ShieldAlert className="w-4 h-4 text-amber-400" /> Inactive (Disabled)
              </span>
            )}
          </div>
          <div className="text-[10px] text-neutral-500 font-mono mt-1">Backend: UFW Daemon</div>
        </div>

        {/* Incoming Policy */}
        <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
          <div className="text-[11px] text-neutral-400 uppercase tracking-wider mb-1">Incoming Policy</div>
          <div className="text-sm font-semibold text-neutral-200 font-mono uppercase">
            {status?.default_incoming || 'DENY'}
          </div>
          <div className="text-[10px] text-neutral-500 font-mono mt-1">Default ingress rule</div>
        </div>

        {/* Outgoing Policy */}
        <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
          <div className="text-[11px] text-neutral-400 uppercase tracking-wider mb-1">Outgoing Policy</div>
          <div className="text-sm font-semibold text-neutral-200 font-mono uppercase">
            {status?.default_outgoing || 'ALLOW'}
          </div>
          <div className="text-[10px] text-neutral-500 font-mono mt-1">Default egress rule</div>
        </div>

        {/* Management Protection */}
        <div className="p-4 bg-neutral-900 border border-neutral-800 rounded-lg">
          <div className="text-[11px] text-neutral-400 uppercase tracking-wider mb-1">Lockout Protection</div>
          <div className="text-xs font-semibold text-blue-400 flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5" /> SSH &amp; Panel Protected
          </div>
          <div className="text-[10px] text-neutral-400 font-mono mt-1">
            Ports: {status?.management_ports?.join(', ') || '22'}
          </div>
        </div>
      </div>

      {/* Rules Table */}
      <div className="border border-neutral-800 bg-neutral-900/60 rounded-lg overflow-hidden">
        <div className="p-4 border-b border-neutral-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Active Rules</h3>
            <span className="text-[10px] font-mono px-1.5 py-0.5 bg-neutral-800 text-neutral-400 rounded border border-neutral-700">
              {status?.rules.length || 0}
            </span>
          </div>
          <span className="text-[11px] text-neutral-500 font-mono">Source of Truth: Linux Kernel / UFW</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-neutral-900/90 text-neutral-400 text-[11px] font-mono uppercase border-b border-neutral-800">
              <tr>
                <th className="py-2.5 px-4">#</th>
                <th className="py-2.5 px-4">Action</th>
                <th className="py-2.5 px-4">Direction</th>
                <th className="py-2.5 px-4">Port / Range</th>
                <th className="py-2.5 px-4">Protocol</th>
                <th className="py-2.5 px-4">Source</th>
                <th className="py-2.5 px-4">Family</th>
                <th className="py-2.5 px-4">Comment</th>
                {canManage && <th className="py-2.5 px-4 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800 font-mono">
              {loading && !status ? (
                <tr>
                  <td colSpan={canManage ? 9 : 8} className="py-8 text-center text-neutral-500">
                    Loading firewall rules...
                  </td>
                </tr>
              ) : status && status.rules.length === 0 ? (
                <tr>
                  <td colSpan={canManage ? 9 : 8} className="py-8 text-center text-neutral-500">
                    No custom firewall rules defined. Default policies are applied.
                  </td>
                </tr>
              ) : (
                status?.rules.map((rule) => {
                  const isManagementPort =
                    status.management_ports &&
                    (status.management_ports.includes(Number(rule.port)) || rule.port === '22');

                  return (
                    <tr key={`${rule.rule_index}-${rule.signature}`} className="hover:bg-neutral-850/50 transition">
                      <td className="py-2.5 px-4 text-neutral-500">{rule.rule_index}</td>
                      <td className="py-2.5 px-4">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                            rule.action.toUpperCase() === 'ALLOW'
                              ? 'bg-emerald-950/60 text-emerald-400 border-emerald-800/80'
                              : 'bg-red-950/60 text-red-400 border-red-800/80'
                          }`}
                        >
                          {rule.action.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-neutral-300 uppercase">{rule.direction}</td>
                      <td className="py-2.5 px-4 text-white font-semibold flex items-center gap-1.5">
                        {rule.port}
                        {isManagementPort && (
                          <span title="Management port" className="text-blue-400">
                            <Lock className="w-3 h-3 inline" />
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-4 text-neutral-300 uppercase">{rule.protocol}</td>
                      <td className="py-2.5 px-4 text-neutral-300">{rule.source}</td>
                      <td className="py-2.5 px-4 text-neutral-400 text-[11px] uppercase">{rule.family}</td>
                      <td className="py-2.5 px-4 text-neutral-400 truncate max-w-xs font-sans text-xs">
                        {rule.comment || '—'}
                      </td>
                      {canManage && (
                        <td className="py-2.5 px-4 text-right">
                          <button
                            onClick={() => setRuleToDelete(rule)}
                            className="p-1 text-neutral-400 hover:text-red-400 hover:bg-neutral-800 rounded transition"
                            title="Delete Rule"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Rule Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-neutral-800">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Plus className="w-4 h-4 text-neutral-400" />
                Add Firewall Rule
              </h3>
              <button onClick={() => setShowAddModal(false)} className="text-neutral-400 hover:text-white">
                <XCircle className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleAddRule} className="space-y-4">
              {/* Port */}
              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">
                  Port or Range <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 80, 443, or 3000:3010"
                  value={port}
                  onChange={(e) => setPort(e.target.value)}
                  className="w-full px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded text-xs font-mono text-white focus:outline-none focus:border-neutral-600"
                />
                <p className="text-[10px] text-neutral-500 mt-1">Single port (1-65535) or colon-delimited range</p>
              </div>

              {/* Protocol & Action */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-300 mb-1">Protocol</label>
                  <select
                    value={protocol}
                    onChange={(e: any) => setProtocol(e.target.value)}
                    className="w-full px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded text-xs font-mono text-white focus:outline-none focus:border-neutral-600"
                  >
                    <option value="tcp">TCP</option>
                    <option value="udp">UDP</option>
                    <option value="any">ANY</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-300 mb-1">Action</label>
                  <select
                    value={action}
                    onChange={(e: any) => setAction(e.target.value)}
                    className="w-full px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded text-xs font-mono text-white focus:outline-none focus:border-neutral-600"
                  >
                    <option value="allow">ALLOW</option>
                    <option value="deny">DENY</option>
                  </select>
                </div>
              </div>

              {/* Direction & Source */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-300 mb-1">Direction</label>
                  <select
                    value={direction}
                    onChange={(e: any) => setDirection(e.target.value)}
                    className="w-full px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded text-xs font-mono text-white focus:outline-none focus:border-neutral-600"
                  >
                    <option value="in">IN (Ingress)</option>
                    <option value="out">OUT (Egress)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-300 mb-1">Source IP / Subnet</label>
                  <input
                    type="text"
                    placeholder="any or 192.168.1.0/24"
                    value={sourceIp}
                    onChange={(e) => setSourceIp(e.target.value)}
                    className="w-full px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded text-xs font-mono text-white focus:outline-none focus:border-neutral-600"
                  />
                </div>
              </div>

              {/* Comment */}
              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">Comment (Optional)</label>
                <input
                  type="text"
                  maxLength={64}
                  placeholder="e.g. Web ingress rule"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  className="w-full px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded text-xs text-white focus:outline-none focus:border-neutral-600"
                />
              </div>

              {/* Lockout Warning */}
              {isLockoutRisk && (
                <div className="p-3 bg-red-950/60 border border-red-800 rounded text-red-200 text-xs flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold block">Lockout Hazard Detected</span>
                    Targeting a protected management/SSH port with a DENY rule is prohibited by the CorePanel security boundary.
                  </div>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-neutral-800">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded text-xs font-medium transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || isLockoutRisk}
                  className="px-4 py-1.5 bg-neutral-100 hover:bg-white disabled:opacity-50 text-neutral-950 rounded text-xs font-medium transition"
                >
                  {submitting ? 'Creating...' : 'Create Rule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Rule Confirmation Modal */}
      {ruleToDelete && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg max-w-sm w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-5 h-5" />
              <h3 className="text-sm font-semibold text-white">Delete Firewall Rule</h3>
            </div>
            <p className="text-xs text-neutral-300">
              Are you sure you want to delete rule <span className="font-mono font-bold text-white">#{ruleToDelete.rule_index}</span> (
              <span className="font-mono text-neutral-200">
                {ruleToDelete.action} {ruleToDelete.direction} {ruleToDelete.port}/{ruleToDelete.protocol}
              </span>
              )?
            </p>
            <div className="p-2.5 bg-neutral-950 border border-neutral-800 rounded text-[11px] font-mono text-neutral-400">
              Signature: {ruleToDelete.signature || 'N/A'}
            </div>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-neutral-800">
              <button
                type="button"
                onClick={() => setRuleToDelete(null)}
                className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded text-xs font-medium transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteRule}
                disabled={submitting}
                className="px-4 py-1.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded text-xs font-medium transition"
              >
                {submitting ? 'Deleting...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toggle Firewall Confirmation Modal */}
      {showToggleModal && status && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg max-w-sm w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center gap-2 text-amber-400">
              <AlertTriangle className="w-5 h-5" />
              <h3 className="text-sm font-semibold text-white">
                {status.active ? 'Disable Firewall' : 'Enable Firewall'}
              </h3>
            </div>
            <p className="text-xs text-neutral-300">
              {status.active
                ? 'Disabling packet filtering allows all inbound and outbound traffic according to the kernel defaults. Are you sure you want to disable the firewall?'
                : 'Enabling packet filtering will enforce default drop policies. CorePanel will verify an active SSH allow rule exists before enabling.'}
            </p>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-neutral-800">
              <button
                type="button"
                onClick={() => setShowToggleModal(false)}
                className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded text-xs font-medium transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleToggleFirewall}
                disabled={submitting}
                className={`px-4 py-1.5 rounded text-xs font-medium transition ${
                  status.active
                    ? 'bg-red-600 hover:bg-red-500 text-white'
                    : 'bg-emerald-600 hover:bg-emerald-500 text-white'
                }`}
              >
                {submitting ? 'Processing...' : status.active ? 'Disable' : 'Enable'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
