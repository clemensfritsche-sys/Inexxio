'use client';

import { useState, useEffect } from 'react';
import { Search, Users, Loader2, AlertCircle, Shield, User, Truck, ShoppingBag, MoreVertical } from 'lucide-react';
import { api } from '@/lib/api';
import type { UserProfile } from '@/types';

const ROLE_CONFIG = {
  admin: { label: 'Administrator', color: 'bg-purple-50 text-purple-700 border-purple-200', icon: Shield },
  manager: { label: 'Manager', color: 'bg-blue-50 text-blue-700 border-blue-200', icon: User },
  user: { label: 'Benutzer', color: 'bg-slate-50 text-slate-700 border-slate-200', icon: ShoppingBag },
  readonly: { label: 'Lesen', color: 'bg-slate-50 text-slate-500 border-slate-200', icon: Truck },
};

export default function BenutzerPage() {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [activeMenu, setActiveMenu] = useState<string | null>(null);
  const [updatingRole, setUpdatingRole] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.get<UserProfile[]>('/api/v1/admin/users');
        setUsers(data);
      } catch {
        setError('Fehler beim Laden der Benutzer.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function updateRole(userId: string, role: string) {
    setUpdatingRole(userId);
    try {
      await api.updateUserRole(userId, role);
      setUsers((prev) =>
        prev.map((u) => (u.uid === userId ? { ...u, role: role as UserProfile['role'] } : u))
      );
      setActiveMenu(null);
    } catch {
      setError('Fehler beim Aktualisieren der Rolle.');
    } finally {
      setUpdatingRole(null);
    }
  }

  async function deactivateUser(userId: string) {
    if (!confirm('Möchten Sie diesen Benutzer wirklich deaktivieren?')) return;
    try {
      await api.deactivateUser(userId);
      setUsers((prev) =>
        prev.map((u) => (u.uid === userId ? { ...u, is_active: false } : u))
      );
      setActiveMenu(null);
    } catch {
      setError('Fehler beim Deaktivieren des Benutzers.');
    }
  }

  const filtered = users.filter(
    (u) =>
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      (u.display_name || '').toLowerCase().includes(search.toLowerCase())
  );

  const initials = (user: UserProfile) =>
    user.display_name
      ? user.display_name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
      : user.email.slice(0, 2).toUpperCase();

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
            <Users className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Benutzerverwaltung</h1>
            <p className="text-sm text-slate-500">
              {users.length} registrierte Benutzer
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <AlertCircle className="h-4 w-4 text-red-500" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Search */}
      <div className="mb-4 relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <input
          type="text"
          placeholder="Benutzer suchen…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="form-input pl-10 max-w-sm"
        />
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-600">Benutzer</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Rolle</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600 hidden sm:table-cell">Letzter Login</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600 hidden md:table-cell">Status</th>
              <th className="px-4 py-3 text-right font-medium text-slate-600">Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  Keine Benutzer gefunden
                </td>
              </tr>
            ) : (
              filtered.map((user) => {
                const roleConfig = ROLE_CONFIG[user.role] || ROLE_CONFIG.user;
                const RoleIcon = roleConfig.icon;
                return (
                  <tr key={user.uid} className="border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        {user.photo_url ? (
                          <img src={user.photo_url} alt={initials(user)} className="h-8 w-8 rounded-full" />
                        ) : (
                          <div className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${
                            user.is_active ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-400'
                          }`}>
                            {initials(user)}
                          </div>
                        )}
                        <div>
                          <p className="font-medium text-slate-900">
                            {user.display_name || user.email.split('@')[0]}
                          </p>
                          <p className="text-xs text-slate-500">{user.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${roleConfig.color}`}>
                        <RoleIcon className="h-3 w-3" />
                        {roleConfig.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 hidden sm:table-cell text-slate-600">
                      {user.last_login ? new Date(user.last_login).toLocaleDateString('de-CH') : '—'}
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        user.is_active
                          ? 'bg-green-50 text-green-700'
                          : 'bg-slate-50 text-slate-500'
                      }`}>
                        {user.is_active ? 'Aktiv' : 'Inaktiv'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="relative inline-block">
                        <button
                          onClick={() => setActiveMenu(activeMenu === user.uid ? null : user.uid)}
                          className="text-slate-400 hover:text-slate-700 transition-colors"
                          disabled={updatingRole === user.uid}
                        >
                          {updatingRole === user.uid ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <MoreVertical className="h-4 w-4" />
                          )}
                        </button>

                        {activeMenu === user.uid && (
                          <div className="absolute right-0 z-10 mt-1 w-48 rounded-lg border border-slate-200 bg-white shadow-lg">
                            <div className="p-1">
                              <p className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
                                Rolle ändern
                              </p>
                              {Object.entries(ROLE_CONFIG).map(([role, config]) => (
                                <button
                                  key={role}
                                  onClick={() => updateRole(user.uid, role)}
                                  className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-slate-50 ${
                                    user.role === role ? 'font-medium text-blue-600' : 'text-slate-700'
                                  }`}
                                >
                                  <config.icon className="h-4 w-4" />
                                  {config.label}
                                  {user.role === role && <span className="ml-auto text-xs">✓</span>}
                                </button>
                              ))}
                              <div className="my-1 border-t border-slate-100" />
                              <button
                                onClick={() => deactivateUser(user.uid)}
                                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                                disabled={!user.is_active}
                              >
                                Deaktivieren
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Stats */}
      <div className="mt-4 flex flex-wrap gap-3">
        {Object.entries(ROLE_CONFIG).map(([role, config]) => {
          const count = users.filter((u) => u.role === role).length;
          const Icon = config.icon;
          return (
            <div key={role} className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${config.color}`}>
              <Icon className="h-3.5 w-3.5" />
              <span>{config.label}: {count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
