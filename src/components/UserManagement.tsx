import React, { useEffect, useState } from 'react';
import { User, Role } from '../types/auth';
import { apiClient, ApiError } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { UserPlus, CheckCircle, XCircle, Trash2, AlertCircle, RefreshCw, KeyRound, User as UserIcon } from 'lucide-react';

export const UserManagement: React.FC = () => {
  const { user: currentUser, hasPermission } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // New User Form State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [selectedRole, setSelectedRole] = useState('viewer');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canManageUsers = hasPermission('users.manage');

  const fetchData = async () => {
    try {
      setLoading(true);
      setActionError(null);
      const [usersData, rolesData] = await Promise.all([
        apiClient.listUsers(),
        apiClient.listRoles().catch(() => []),
      ]);
      setUsers(usersData);
      setRoles(rolesData);
    } catch (err) {
      if (err instanceof ApiError) {
        setActionError(err.message);
      } else {
        setActionError('Failed to load user accounts.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUsername.trim() || !newPassword) return;

    try {
      setIsSubmitting(true);
      setActionError(null);
      await apiClient.createUser({
        username: newUsername.trim(),
        password: newPassword,
        email: newEmail.trim() || undefined,
        roles: [selectedRole],
        is_active: true,
      });
      setSuccessMessage(`User "${newUsername}" created successfully.`);
      setShowCreateModal(false);
      setNewUsername('');
      setNewPassword('');
      setNewEmail('');
      await fetchData();
    } catch (err) {
      if (err instanceof ApiError) {
        setActionError(err.message);
      } else {
        setActionError('Failed to create user account.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleActive = async (targetUser: User) => {
    if (!canManageUsers) return;
    try {
      setActionError(null);
      await apiClient.updateUser(targetUser.id, {
        is_active: !targetUser.is_active,
      });
      setSuccessMessage(`User "${targetUser.username}" ${targetUser.is_active ? 'deactivated' : 'activated'}.`);
      await fetchData();
    } catch (err) {
      if (err instanceof ApiError) {
        setActionError(err.message);
      } else {
        setActionError('Failed to update user status.');
      }
    }
  };

  const handleDeleteUser = async (targetUser: User) => {
    if (!canManageUsers) return;
    if (!window.confirm(`Are you sure you want to delete user "${targetUser.username}"?`)) {
      return;
    }
    try {
      setActionError(null);
      await apiClient.deleteUser(targetUser.id);
      setSuccessMessage(`User "${targetUser.username}" was deleted.`);
      await fetchData();
    } catch (err) {
      if (err instanceof ApiError) {
        setActionError(err.message);
      } else {
        setActionError('Failed to delete user.');
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-neutral-700/60">
        <div>
          <h2 className="text-lg font-medium text-white flex items-center gap-2">
            <UserIcon className="w-5 h-5 text-neutral-400" />
            User Accounts &amp; RBAC Access
          </h2>
          <p className="text-xs text-neutral-400 mt-0.5">
            Manage control-plane users, role assignments, and active account status
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            id="refresh-users-btn"
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-xs rounded-md border border-neutral-700 flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          {canManageUsers && (
            <button
              id="add-user-modal-btn"
              onClick={() => {
                setShowCreateModal(true);
                setActionError(null);
                setSuccessMessage(null);
              }}
              className="px-3 py-1.5 bg-neutral-100 hover:bg-white text-neutral-900 font-medium text-xs rounded-md shadow-sm flex items-center gap-1.5 transition-colors"
            >
              <UserPlus className="w-3.5 h-3.5" />
              Add User
            </button>
          )}
        </div>
      </div>

      {actionError && (
        <div className="flex items-center space-x-2 p-3 bg-red-950/60 border border-red-800/80 rounded-lg text-red-200 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
          <span>{actionError}</span>
        </div>
      )}

      {successMessage && (
        <div className="flex items-center space-x-2 p-3 bg-emerald-950/60 border border-emerald-800/80 rounded-lg text-emerald-200 text-xs">
          <CheckCircle className="w-4 h-4 shrink-0 text-emerald-400" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Users Table */}
      <div className="border border-neutral-700/80 rounded-lg overflow-hidden bg-neutral-800/50">
        <table className="min-w-full divide-y divide-neutral-700 text-left text-xs">
          <thead className="bg-neutral-800/90 text-neutral-400 uppercase tracking-wider font-medium">
            <tr>
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Roles</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Created</th>
              {canManageUsers && <th className="px-4 py-3 text-right">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-700/60 text-neutral-200">
            {loading ? (
              <tr>
                <td colSpan={canManageUsers ? 5 : 4} className="px-4 py-8 text-center text-neutral-500">
                  Loading user records...
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={canManageUsers ? 5 : 4} className="px-4 py-8 text-center text-neutral-500">
                  No users found.
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="hover:bg-neutral-750/40 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium text-white flex items-center gap-1.5">
                      {u.username}
                      {u.id === currentUser?.id && (
                        <span className="text-[10px] bg-neutral-700 text-neutral-300 px-1.5 py-0.5 rounded font-mono">
                          You
                        </span>
                      )}
                    </div>
                    {u.email && <div className="text-[11px] text-neutral-400">{u.email}</div>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {u.roles.map((r) => (
                        <span
                          key={r}
                          className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase ${
                            r === 'admin'
                              ? 'bg-amber-950/80 text-amber-300 border border-amber-800/80'
                              : 'bg-neutral-700/80 text-neutral-300 border border-neutral-600/80'
                          }`}
                        >
                          {r}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium ${
                        u.is_active
                          ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/80'
                          : 'bg-rose-950/80 text-rose-300 border border-rose-800/80'
                      }`}
                    >
                      {u.is_active ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-neutral-400 font-mono text-[11px]">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  {canManageUsers && (
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {u.id !== currentUser?.id && (
                          <>
                            <button
                              id={`toggle-user-${u.username}-btn`}
                              onClick={() => handleToggleActive(u)}
                              className="text-neutral-400 hover:text-white text-[11px] underline"
                            >
                              {u.is_active ? 'Deactivate' : 'Activate'}
                            </button>
                            <button
                              id={`delete-user-${u.username}-btn`}
                              onClick={() => handleDeleteUser(u)}
                              className="p-1 text-neutral-400 hover:text-rose-400 transition-colors"
                              title="Delete user"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl max-w-md w-full p-6 shadow-2xl">
            <h3 className="text-base font-semibold text-white mb-4 pb-2 border-b border-neutral-700">
              Create New Account
            </h3>
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">Username</label>
                <input
                  id="new-username-input"
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  className="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-sm text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-400"
                  placeholder="e.g. jdoe"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">Email (Optional)</label>
                <input
                  id="new-email-input"
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  className="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-sm text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-400"
                  placeholder="user@example.com"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">Password</label>
                <div className="relative">
                  <input
                    id="new-password-input"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-sm text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-400"
                    placeholder="Minimum 8 characters"
                    minLength={8}
                    required
                  />
                  <KeyRound className="w-4 h-4 text-neutral-500 absolute right-3 top-2.5" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">Assign Role</label>
                <select
                  id="new-role-select"
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value)}
                  className="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-sm text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-400"
                >
                  {roles.map((r) => (
                    <option key={r.name} value={r.name}>
                      {r.name} {r.description ? `— ${r.description}` : ''}
                    </option>
                  ))}
                  {roles.length === 0 && (
                    <>
                      <option value="viewer">viewer</option>
                      <option value="admin">admin</option>
                    </>
                  )}
                </select>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-neutral-700/80">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-xs font-medium text-neutral-300 hover:text-white bg-transparent rounded-lg"
                >
                  Cancel
                </button>
                <button
                  id="confirm-create-user-btn"
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 bg-neutral-100 hover:bg-white text-neutral-900 text-xs font-medium rounded-lg shadow-sm disabled:opacity-50"
                >
                  {isSubmitting ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
