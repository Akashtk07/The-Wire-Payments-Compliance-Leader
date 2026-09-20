'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  Plus, Edit2, Trash2, UserCheck, UserX, Shield, User, Lock, Unlock,
  RefreshCw, KeyRound, CheckCircle2, AlertCircle, X, MoreVertical,
} from 'lucide-react';
import { authFetch } from '@/lib/auth';
import { useAuth } from '@/lib/AuthProvider';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface AppUser {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
  role: 'admin' | 'analyst';
  is_active: boolean;
  is_verified: boolean;
  must_change_password: boolean;
  failed_login_attempts: number;
  is_locked: boolean;
  locked_until: string | null;
  lockout_remaining_seconds: number;
  created_at: string | null;
  last_login: string | null;
  last_active: string | null;
  password_changed_at: string | null;
  created_by: string;
}

type ModalType = 'create' | 'lock' | null;

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <div style={{
      width: '8px', height: '8px', borderRadius: '50%', flexShrink: 0,
      background: ok ? 'var(--color-success)' : 'var(--color-danger)',
      boxShadow: ok ? '0 0 6px var(--color-success)' : '0 0 6px var(--color-danger)',
    }} />
  );
}

function fmt(d: string | null) {
  if (!d) return '—';
  const dt = new Date(d);
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export default function AdminUsersPage() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<AppUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<ModalType>(null);
  const [lockTarget, setLockTarget] = useState<AppUser | null>(null);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null); // user id being acted on
  const [expandedUser, setExpandedUser] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  // Create form
  const [form, setForm] = useState({
    username: '', email: '', password: '', full_name: '', role: 'analyst', must_change_password: true,
  });
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState('');

  // Lock form
  const [lockForm, setLockForm] = useState({ duration_minutes: 30, reason: '' });

  const showToast = useCallback((type: 'success' | 'error', msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  }, []);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authFetch(`${API_URL}/api/v1/admin/users`);
      if (res.ok) setUsers(await res.json());
    } catch {
      showToast('error', 'Failed to fetch users');
    }
    setLoading(false);
  }, [showToast]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  // Generic action helper
  const doAction = useCallback(async (
    userId: string,
    endpoint: string,
    method: string,
    body?: object,
    successMsg = 'Done',
  ) => {
    setActionLoading(userId);
    try {
      const res = await authFetch(`${API_URL}/api/v1/admin${endpoint}`, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail?.message ?? err?.detail ?? 'Action failed');
      }
      showToast('success', successMsg);
      await fetchUsers();
    } catch (e) {
      showToast('error', e instanceof Error ? e.message : 'Error occurred');
    } finally {
      setActionLoading(null);
    }
  }, [fetchUsers, showToast]);

  const handleRoleChange = (u: AppUser) => {
    const newRole = u.role === 'admin' ? 'analyst' : 'admin';
    const confirmMsg = newRole === 'admin'
      ? `Grant ADMIN access to ${u.username}? They will have full platform control.`
      : `Revoke ADMIN access from ${u.username}? They'll become an Analyst.`;
    if (!confirm(confirmMsg)) return;
    doAction(u.id, `/users/${u.id}/role`, 'PUT', { role: newRole },
      newRole === 'admin' ? `Admin granted to ${u.username}` : `Admin revoked from ${u.username}`);
  };

  const handleToggleActive = (u: AppUser) => {
    if (!confirm(`${u.is_active ? 'Deactivate' : 'Activate'} account for ${u.username}?`)) return;
    doAction(u.id, `/users/${u.id}/activate`, 'PUT', { is_active: !u.is_active },
      u.is_active ? `${u.username} deactivated` : `${u.username} activated`);
  };

  const handleUnlock = (u: AppUser) => {
    doAction(u.id, `/users/${u.id}/lock`, 'PUT', { lock: false }, `${u.username} unlocked`);
  };

  const openLockModal = (u: AppUser) => {
    setLockTarget(u);
    setLockForm({ duration_minutes: 30, reason: '' });
    setModal('lock');
  };

  const handleLockConfirm = () => {
    if (!lockTarget) return;
    doAction(lockTarget.id, `/users/${lockTarget.id}/lock`, 'PUT', {
      lock: true,
      duration_minutes: lockForm.duration_minutes,
      reason: lockForm.reason || undefined,
    }, `${lockTarget.username} locked for ${lockForm.duration_minutes} min`);
    setModal(null);
  };

  const handleForceReset = (u: AppUser) => {
    if (!confirm(`Force ${u.username} to change password on next login?`)) return;
    doAction(u.id, `/users/${u.id}/force-reset`, 'POST', undefined, `Password reset forced for ${u.username}`);
  };

  const handleManualVerify = (u: AppUser) => {
    if (!confirm(`Manually verify email for ${u.username}?`)) return;
    doAction(u.id, `/users/${u.id}/verify`, 'POST', undefined, `${u.username} manually verified`);
  };

  const handleDelete = (u: AppUser) => {
    if (!confirm(`PERMANENTLY DELETE user "${u.username}"?\n\nThis cannot be undone.`)) return;
    doAction(u.id, `/users/${u.id}`, 'DELETE', undefined, `${u.username} deleted`);
  };

  const handleCreate = async () => {
    setCreateLoading(true);
    setCreateError('');
    try {
      const res = await authFetch(`${API_URL}/api/v1/admin/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const violations = err?.detail?.violations;
        if (violations) throw new Error(violations.join('\n'));
        throw new Error(err?.detail?.message ?? 'Failed to create user');
      }
      showToast('success', `User ${form.username} created`);
      setModal(null);
      setForm({ username: '', email: '', password: '', full_name: '', role: 'analyst', must_change_password: true });
      fetchUsers();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Error');
    } finally {
      setCreateLoading(false);
    }
  };

  const filtered = users.filter((u) =>
    !search ||
    u.username.toLowerCase().includes(search.toLowerCase()) ||
    u.email.toLowerCase().includes(search.toLowerCase()) ||
    (u.full_name ?? '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      {/* Toast */}
      {toast && (
        <div className="animate-slide-down" style={{
          position: 'fixed', top: '80px', right: '24px', zIndex: 9999,
          padding: '12px 18px', borderRadius: '10px', boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          background: toast.type === 'success' ? 'rgba(0,229,160,0.1)' : 'rgba(255,68,68,0.1)',
          border: `1px solid ${toast.type === 'success' ? 'rgba(0,229,160,0.4)' : 'rgba(255,68,68,0.4)'}`,
          color: toast.type === 'success' ? 'var(--color-success)' : 'var(--color-danger)',
          display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 600,
          maxWidth: '360px',
        }}>
          {toast.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
        <div className="section-header" style={{ margin: 0, flex: 1 }}>
          Users ({filtered.length}{search ? ` of ${users.length}` : ''})
        </div>
        <input
          className="input"
          placeholder="Search users..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: '200px', fontSize: '13px', height: '36px' }}
        />
        <button className="btn btn-ghost btn-sm" onClick={fetchUsers} style={{ gap: '6px' }}>
          <RefreshCw size={13} />
        </button>
        <button
          id="create-user-btn"
          className="btn btn-primary btn-sm"
          onClick={() => { setModal('create'); setCreateError(''); }}
          style={{ gap: '6px' }}
        >
          <Plus size={14} /> New User
        </button>
      </div>

      {/* User Table */}
      <div className="glass-panel" style={{ overflow: 'auto', padding: 0 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
              {['User', 'Role', 'Status', 'Verified', 'Last Login', 'Joined', 'Actions'].map((h) => (
                <th key={h} style={{
                  padding: '10px 14px', textAlign: 'left',
                  fontSize: '11px', fontWeight: 700, letterSpacing: '0.06em',
                  textTransform: 'uppercase', color: 'var(--color-text-muted)',
                  whiteSpace: 'nowrap',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 7 }).map((_, j) => (
                    <td key={j} style={{ padding: '12px 14px' }}>
                      <div className="skeleton-text" style={{ height: '14px', borderRadius: '4px' }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : filtered.map((u) => {
              const isSelf = me?.id === u.id;
              const isActing = actionLoading === u.id;

              return (
                <tr key={u.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  {/* User */}
                  <td style={{ padding: '12px 14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{
                        width: '32px', height: '32px', borderRadius: '8px', flexShrink: 0,
                        background: u.role === 'admin'
                          ? 'linear-gradient(135deg,#FFB800,#FF6B35)'
                          : 'linear-gradient(135deg,#00D4FF,#7B2FBE)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        position: 'relative',
                      }}>
                        {u.role === 'admin' ? <Shield size={14} color="#080C14" /> : <User size={14} color="#fff" />}
                        {u.is_locked && (
                          <div style={{
                            position: 'absolute', top: '-4px', right: '-4px',
                            background: 'var(--color-danger)', borderRadius: '50%',
                            width: '14px', height: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center',
                          }}>
                            <Lock size={8} color="white" />
                          </div>
                        )}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>
                          {u.username} {isSelf && <span style={{ fontSize: '10px', color: 'var(--color-primary)' }}>(you)</span>}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {u.email}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Role */}
                  <td style={{ padding: '12px 14px' }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: 700,
                      textTransform: 'uppercase', letterSpacing: '0.06em',
                      background: u.role === 'admin' ? 'rgba(255,184,0,0.1)' : 'rgba(0,212,255,0.1)',
                      color: u.role === 'admin' ? '#FFB800' : 'var(--color-primary)',
                      border: `1px solid ${u.role === 'admin' ? 'rgba(255,184,0,0.3)' : 'rgba(0,212,255,0.3)'}`,
                    }}>
                      {u.role}
                    </span>
                  </td>

                  {/* Status */}
                  <td style={{ padding: '12px 14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 600,
                      color: u.is_locked ? '#FFB800' : u.is_active ? 'var(--color-success)' : 'var(--color-danger)' }}>
                      <StatusDot ok={u.is_active && !u.is_locked} />
                      {u.is_locked ? 'Locked' : u.is_active ? 'Active' : 'Inactive'}
                    </div>
                  </td>

                  {/* Verified */}
                  <td style={{ padding: '12px 14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '12px',
                      color: u.is_verified ? 'var(--color-success)' : 'var(--color-text-muted)' }}>
                      <StatusDot ok={u.is_verified} />
                      {u.is_verified ? 'Yes' : 'No'}
                    </div>
                  </td>

                  <td style={{ padding: '12px 14px', fontSize: '11px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {fmt(u.last_login)}
                  </td>
                  <td style={{ padding: '12px 14px', fontSize: '11px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {fmt(u.created_at)}
                  </td>

                  {/* Actions */}
                  <td style={{ padding: '12px 14px' }}>
                    {isActing ? (
                      <div style={{ width: '16px', height: '16px', borderRadius: '50%',
                        border: '2px solid var(--color-primary)', borderTopColor: 'transparent',
                        animation: 'spin 0.7s linear infinite' }} />
                    ) : (
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                        {/* Promote / Demote */}
                        {!isSelf && (
                          <button
                            onClick={() => handleRoleChange(u)}
                            title={u.role === 'admin' ? 'Revoke admin' : 'Grant admin'}
                            style={{
                              padding: '4px 8px', borderRadius: '6px', cursor: 'pointer',
                              border: `1px solid ${u.role === 'admin' ? 'rgba(255,68,68,0.3)' : 'rgba(255,184,0,0.3)'}`,
                              background: 'transparent',
                              color: u.role === 'admin' ? 'var(--color-danger)' : '#FFB800',
                              fontSize: '11px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '3px',
                            }}
                          >
                            <Shield size={11} />
                            {u.role === 'admin' ? 'Demote' : 'Promote'}
                          </button>
                        )}

                        {/* Lock / Unlock */}
                        {!isSelf && (
                          u.is_locked ? (
                            <button onClick={() => handleUnlock(u)} title="Unlock account"
                              style={{ padding: '4px 8px', borderRadius: '6px', cursor: 'pointer',
                                border: '1px solid rgba(0,229,160,0.3)', background: 'transparent',
                                color: 'var(--color-success)', fontSize: '11px', fontWeight: 600,
                                display: 'flex', alignItems: 'center', gap: '3px' }}>
                              <Unlock size={11} /> Unlock
                            </button>
                          ) : (
                            <button onClick={() => openLockModal(u)} title="Lock account"
                              style={{ padding: '4px 8px', borderRadius: '6px', cursor: 'pointer',
                                border: '1px solid rgba(255,184,0,0.3)', background: 'transparent',
                                color: '#FFB800', fontSize: '11px', fontWeight: 600,
                                display: 'flex', alignItems: 'center', gap: '3px' }}>
                              <Lock size={11} /> Lock
                            </button>
                          )
                        )}

                        {/* Activate / Deactivate */}
                        {!isSelf && (
                          <button onClick={() => handleToggleActive(u)}
                            title={u.is_active ? 'Deactivate' : 'Activate'}
                            style={{ padding: '4px 8px', borderRadius: '6px', cursor: 'pointer',
                              border: `1px solid ${u.is_active ? 'rgba(255,68,68,0.3)' : 'rgba(0,229,160,0.3)'}`,
                              background: 'transparent',
                              color: u.is_active ? 'var(--color-danger)' : 'var(--color-success)',
                              fontSize: '11px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '3px' }}>
                            {u.is_active ? <><UserX size={11} /> Disable</> : <><UserCheck size={11} /> Enable</>}
                          </button>
                        )}

                        {/* Force password reset */}
                        <button onClick={() => handleForceReset(u)} title="Force password reset"
                          style={{ padding: '4px 8px', borderRadius: '6px', cursor: 'pointer',
                            border: '1px solid rgba(0,212,255,0.2)', background: 'transparent',
                            color: 'var(--color-primary)', fontSize: '11px', fontWeight: 600,
                            display: 'flex', alignItems: 'center', gap: '3px' }}>
                          <KeyRound size={11} /> Reset
                        </button>

                        {/* Manual verify */}
                        {!u.is_verified && (
                          <button onClick={() => handleManualVerify(u)} title="Manually verify email"
                            style={{ padding: '4px 8px', borderRadius: '6px', cursor: 'pointer',
                              border: '1px solid rgba(0,229,160,0.3)', background: 'transparent',
                              color: 'var(--color-success)', fontSize: '11px', fontWeight: 600,
                              display: 'flex', alignItems: 'center', gap: '3px' }}>
                            <CheckCircle2 size={11} /> Verify
                          </button>
                        )}

                        {/* Hard delete */}
                        {!isSelf && (
                          <button onClick={() => handleDelete(u)} title="Delete user permanently"
                            style={{ padding: '4px 8px', borderRadius: '6px', cursor: 'pointer',
                              border: '1px solid rgba(255,68,68,0.3)', background: 'transparent',
                              color: 'var(--color-danger)', fontSize: '11px', fontWeight: 600,
                              display: 'flex', alignItems: 'center', gap: '3px' }}>
                            <Trash2 size={11} /> Delete
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {!loading && filtered.length === 0 && (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '14px' }}>
            {search ? 'No users match your search.' : 'No users found.'}
          </div>
        )}
      </div>

      {/* ── CREATE USER MODAL ── */}
      {modal === 'create' && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          backdropFilter: 'blur(6px)',
        }}>
          <div className="animate-scale-in" style={{
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            borderRadius: '16px', padding: '28px', width: '440px',
            boxShadow: '0 32px 80px rgba(0,0,0,0.6)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                Create New User
              </div>
              <button onClick={() => setModal(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}>
                <X size={18} />
              </button>
            </div>

            {createError && (
              <div style={{ padding: '10px 12px', background: 'rgba(255,68,68,0.08)', border: '1px solid rgba(255,68,68,0.3)',
                borderRadius: '8px', fontSize: '12px', color: 'var(--color-danger)', marginBottom: '14px',
                whiteSpace: 'pre-line' }}>
                {createError}
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Full Name (optional)</label>
              <input className="input" value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} placeholder="John Doe" />
            </div>
            <div className="form-group">
              <label className="form-label">Username *</label>
              <input className="input" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} placeholder="john_doe" />
            </div>
            <div className="form-group">
              <label className="form-label">Email *</label>
              <input className="input" type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} placeholder="user@example.com" />
            </div>
            <div className="form-group">
              <label className="form-label">Password * (min 8 chars, upper, lower, digit, special)</label>
              <input className="input" type="password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} placeholder="Strong password" />
            </div>
            <div className="form-group">
              <label className="form-label">Role</label>
              <select className="select" value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
                <option value="analyst">Analyst</option>
                <option value="admin">Administrator</option>
              </select>
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '13px',
              color: 'var(--color-text-secondary)', margin: '8px 0 20px' }}>
              <input type="checkbox" checked={form.must_change_password}
                onChange={(e) => setForm((f) => ({ ...f, must_change_password: e.target.checked }))} />
              Force password change on first login
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button className="btn btn-primary" onClick={handleCreate} disabled={createLoading}
                style={{ flex: 1, justifyContent: 'center' }}>
                {createLoading ? 'Creating...' : 'Create User'}
              </button>
              <button className="btn btn-ghost" onClick={() => setModal(null)} style={{ flex: 1, justifyContent: 'center' }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── LOCK MODAL ── */}
      {modal === 'lock' && lockTarget && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          backdropFilter: 'blur(6px)',
        }}>
          <div className="animate-scale-in" style={{
            background: 'var(--color-surface)', border: '1px solid rgba(255,184,0,0.3)',
            borderRadius: '16px', padding: '28px', width: '380px',
            boxShadow: '0 32px 80px rgba(0,0,0,0.6)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ fontSize: '16px', fontWeight: 700, color: '#FFB800', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Lock size={16} /> Lock Account
              </div>
              <button onClick={() => setModal(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}>
                <X size={18} />
              </button>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
              Lock <strong style={{ color: 'var(--color-text-primary)' }}>{lockTarget.username}</strong> for:
            </div>
            <div className="form-group">
              <label className="form-label">Duration (minutes)</label>
              <input className="input" type="number" min={1} max={43200}
                value={lockForm.duration_minutes}
                onChange={(e) => setLockForm((f) => ({ ...f, duration_minutes: parseInt(e.target.value) || 30 }))} />
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                Common: 30 min · 60 min · 1440 min (24h) · 43200 (30 days)
              </div>
            </div>
            <div className="form-group" style={{ marginBottom: '20px' }}>
              <label className="form-label">Reason (optional)</label>
              <input className="input" placeholder="e.g. Suspicious activity detected"
                value={lockForm.reason}
                onChange={(e) => setLockForm((f) => ({ ...f, reason: e.target.value }))} />
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button className="btn btn-danger" onClick={handleLockConfirm} style={{ flex: 1, justifyContent: 'center' }}>
                <Lock size={14} /> Lock Account
              </button>
              <button className="btn btn-ghost" onClick={() => setModal(null)} style={{ flex: 1, justifyContent: 'center' }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
