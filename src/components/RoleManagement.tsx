import React, { useEffect, useState } from 'react';
import { Role, Permission } from '../types/auth';
import { apiClient, ApiError } from '../api/client';
import { ShieldCheck, Lock, AlertCircle, RefreshCw } from 'lucide-react';

export const RoleManagement: React.FC = () => {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [rolesData, permsData] = await Promise.all([
        apiClient.listRoles(),
        apiClient.listPermissions(),
      ]);
      setRoles(rolesData);
      setPermissions(permsData);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to fetch roles and permissions.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-neutral-700/60">
        <div>
          <h2 className="text-lg font-medium text-white flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-neutral-400" />
            Roles &amp; Permission Mappings
          </h2>
          <p className="text-xs text-neutral-400 mt-0.5">
            View system roles and their explicit permission grants
          </p>
        </div>

        <button
          id="refresh-roles-btn"
          onClick={fetchData}
          disabled={loading}
          className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-xs rounded-md border border-neutral-700 flex items-center gap-1.5 transition-colors self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="flex items-center space-x-2 p-3 bg-red-950/60 border border-red-800/80 rounded-lg text-red-200 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {roles.map((role) => (
          <div
            key={role.id}
            className="border border-neutral-700/80 rounded-lg p-5 bg-neutral-800/50 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-white font-mono">{role.name}</h3>
                  {role.is_system && (
                    <span className="px-1.5 py-0.5 bg-neutral-700 text-neutral-300 rounded text-[10px] font-mono">
                      System
                    </span>
                  )}
                </div>
                <Lock className="w-4 h-4 text-neutral-500" />
              </div>

              <p className="text-xs text-neutral-400 mb-4">{role.description || 'No description provided.'}</p>

              <div>
                <div className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider mb-2">
                  Granted Permissions ({role.permissions.length})
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {role.permissions.map((perm) => (
                    <span
                      key={perm}
                      className="px-2 py-0.5 bg-neutral-900 border border-neutral-700 text-neutral-300 rounded text-[11px] font-mono"
                    >
                      {perm}
                    </span>
                  ))}
                  {role.permissions.length === 0 && (
                    <span className="text-xs text-neutral-500 italic">No permissions assigned.</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 pt-6 border-t border-neutral-700/60">
        <h3 className="text-sm font-medium text-white mb-3">All System Permissions Registry ({permissions.length})</h3>
        <div className="border border-neutral-700/80 rounded-lg overflow-hidden bg-neutral-800/40">
          <table className="min-w-full divide-y divide-neutral-700 text-left text-xs">
            <thead className="bg-neutral-800/80 text-neutral-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-2.5">Identifier</th>
                <th className="px-4 py-2.5">Resource</th>
                <th className="px-4 py-2.5">Action</th>
                <th className="px-4 py-2.5">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-700/50 text-neutral-300">
              {permissions.map((p) => (
                <tr key={p.id}>
                  <td className="px-4 py-2 font-mono font-medium text-white">{p.name}</td>
                  <td className="px-4 py-2 text-neutral-400">{p.resource}</td>
                  <td className="px-4 py-2 text-neutral-400">{p.action}</td>
                  <td className="px-4 py-2 text-neutral-400">{p.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
