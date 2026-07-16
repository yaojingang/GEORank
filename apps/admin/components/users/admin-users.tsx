'use client';

import {useEffect, useMemo, useRef, useState} from 'react';
import {useLocale, useTranslations} from 'next-intl';

import type {AdminUserQuota, AdminUserSummary} from '@georank/api-sdk';
import {
  createAdminUser,
  deleteAdminUser,
  getAdminDashboard,
  getAdminUserQuota,
  listAdminUsers,
  resetAdminUserPassword,
  toggleAdminUserActive,
  updateAdminUser,
  updateAdminUserQuota
} from '@georank/api-sdk';

type AdminUsersProps = {
  token: string;
};

type UserListState = {
  items: AdminUserSummary[];
  total: number;
  page: number;
  pages: number;
};

type UserDraft = {
  username: string;
  email: string;
  phone: string;
  role: string;
  is_active: boolean;
  is_verified: boolean;
};

type UserCreateDraft = {
  username: string;
  email: string;
  phone: string;
  role: string;
  password: string;
};

const emptyCreateDraft: UserCreateDraft = {
  username: '',
  email: '',
  phone: '',
  role: 'user',
  password: ''
};

function formatDateTime(value?: string | null, locale = 'zh-CN') {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(date);
}

function userToDraft(user: AdminUserSummary): UserDraft {
  return {
    username: user.username || '',
    email: user.email || '',
    phone: user.phone || '',
    role: user.role || 'user',
    is_active: Boolean(user.is_active),
    is_verified: Boolean(user.is_verified)
  };
}

export function AdminUsers({token}: AdminUsersProps) {
  const locale = useLocale();
  const t = useTranslations('admin.users');
  const actions = useTranslations('common.actions');
  const status = useTranslations('common.status');
  const units = useTranslations('common.units');
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [role, setRole] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [listState, setListState] = useState<UserListState>({
    items: [],
    total: 0,
    page: 1,
    pages: 1
  });
  const [selectedUserId, setSelectedUserId] = useState('');
  const [detail, setDetail] = useState<AdminUserSummary | null>(null);
  const [editDraft, setEditDraft] = useState<UserDraft | null>(null);
  const [createDraft, setCreateDraft] = useState<UserCreateDraft>(emptyCreateDraft);
  const [passwordDraft, setPasswordDraft] = useState('');
  const [quota, setQuota] = useState<AdminUserQuota | null>(null);
  const [quotaDraft, setQuotaDraft] = useState({
    grantedTokens: 10000,
    consumedTokens: 0,
    frozen: false,
    reason: ''
  });
  const [showCreate, setShowCreate] = useState(false);
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    admin: 0,
    new_today: 0
  });
  const [loading, setLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState('');
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const selectedUserIdRef = useRef(selectedUserId);

  useEffect(() => {
    selectedUserIdRef.current = selectedUserId;
  }, [selectedUserId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');

    Promise.allSettled([
      listAdminUsers(token, {
        page,
        size: 16,
        role: role || undefined,
        isActive: statusFilter === '' ? undefined : statusFilter === 'true',
        search: query || undefined
      }),
      getAdminDashboard(token)
    ])
      .then(([usersResult, dashboardResult]) => {
        if (!active) return;
        const errors: string[] = [];
        if (usersResult.status === 'fulfilled') {
          const users = usersResult.value;
          setListState({
            items: users.items,
            total: users.total,
            page: users.page,
            pages: users.pages
          });
          const preferredUser = users.items.find((item) => item.id === selectedUserIdRef.current) || users.items[0] || null;
          setSelectedUserId(preferredUser?.id || '');
          setDetail(preferredUser);
          setEditDraft(preferredUser ? userToDraft(preferredUser) : null);
        } else {
          errors.push(usersResult.reason instanceof Error ? usersResult.reason.message : t('listLoadFailed'));
        }
        if (dashboardResult.status === 'fulfilled') {
          setStats(dashboardResult.value.user_stats);
        } else {
          errors.push(dashboardResult.reason instanceof Error ? dashboardResult.reason.message : t('listLoadFailed'));
        }
        setError(errors.join(' · '));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [token, page, query, role, statusFilter, t, reloadKey]);

  useEffect(() => {
    if (!selectedUserId || showCreate) {
      setQuota(null);
      return;
    }
    let active = true;
    getAdminUserQuota(token, selectedUserId)
      .then((payload) => {
        if (!active) return;
        setQuota(payload);
        setQuotaDraft({
          grantedTokens: payload.granted_tokens,
          consumedTokens: payload.consumed_tokens,
          frozen: payload.frozen,
          reason: ''
        });
      })
      .catch((quotaError: unknown) => {
        if (active) setActionMessage(quotaError instanceof Error ? quotaError.message : t('quotaLoadFailed'));
      });
    return () => {
      active = false;
    };
  }, [token, selectedUserId, showCreate, t]);

  const topStats = useMemo(() => {
    return [
      {label: t('totalUsers'), value: stats.total, tone: 'brand'},
      {label: t('activeUsers'), value: stats.active, tone: 'success'},
      {label: t('admins'), value: stats.admin, tone: 'warning'},
      {label: t('newToday'), value: stats.new_today, tone: 'brand'}
    ];
  }, [stats, t]);

  function selectUser(user: AdminUserSummary | null) {
    setSelectedUserId(user?.id || '');
    setDetail(user);
    setEditDraft(user ? userToDraft(user) : null);
    setPasswordDraft('');
    setShowCreate(false);
  }
  async function refreshUsers(nextUserId?: string) {
    const [usersResult, dashboardResult] = await Promise.allSettled([
      listAdminUsers(token, {
        page,
        size: 16,
        role: role || undefined,
        isActive: statusFilter === '' ? undefined : statusFilter === 'true',
        search: query || undefined
      }),
      getAdminDashboard(token)
    ]);
    const errors: string[] = [];
    if (usersResult.status === 'fulfilled') {
      const payload = usersResult.value;
      setListState({
        items: payload.items,
        total: payload.total,
        page: payload.page,
        pages: payload.pages
      });
      const preferredUser = payload.items.find((item) => item.id === (nextUserId || selectedUserId)) || payload.items[0] || null;
      selectUser(preferredUser);
    } else {
      errors.push(usersResult.reason instanceof Error ? usersResult.reason.message : t('listLoadFailed'));
    }
    if (dashboardResult.status === 'fulfilled') {
      setStats(dashboardResult.value.user_stats);
    } else {
      errors.push(dashboardResult.reason instanceof Error ? dashboardResult.reason.message : t('listLoadFailed'));
    }
    setError(errors.join(' · '));
    if (usersResult.status === 'rejected') throw usersResult.reason;
  }

  async function handleCreateUser(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const created = await createAdminUser(token, {
        username: createDraft.username.trim(),
        email: createDraft.email.trim(),
        phone: createDraft.phone.trim() || null,
        role: createDraft.role,
        password: createDraft.password
      });
      setActionMessage(t('createdMessage'));
      setCreateDraft(emptyCreateDraft);
      setShowCreate(false);
      await refreshUsers(created.id);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('createFailed'));
    }
  }

  async function handleProfileSave() {
    if (!detail || !editDraft) return;
    try {
      const updated = await updateAdminUser(token, detail.id, {
        username: editDraft.username.trim(),
        email: editDraft.email.trim(),
        phone: editDraft.phone.trim() || null,
        role: editDraft.role,
        is_active: editDraft.is_active,
        is_verified: editDraft.is_verified
      });
      setActionMessage(t('profileSaved'));
      setDetail(updated);
      setEditDraft(userToDraft(updated));
      await refreshUsers(updated.id);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('profileFailed'));
    }
  }

  async function handleToggleActive() {
    if (!detail) return;
    try {
      await toggleAdminUserActive(token, detail.id);
      setActionMessage(detail.is_active ? t('disabledMessage') : t('enabledMessage'));
      await refreshUsers(detail.id);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('statusFailed'));
    }
  }

  async function handlePasswordReset() {
    if (!detail) return;
    if (passwordDraft.length < 6) {
      setActionMessage(t('passwordTooShort'));
      return;
    }
    try {
      await resetAdminUserPassword(token, detail.id, {password: passwordDraft});
      setActionMessage(t('passwordResetMessage'));
      setPasswordDraft('');
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('passwordResetFailed'));
    }
  }

  async function handleQuotaSave() {
    if (!detail) return;
    if (quotaDraft.reason.trim().length < 2) {
      setActionMessage(t('quotaReasonRequired'));
      return;
    }
    try {
      const updated = await updateAdminUserQuota(token, detail.id, {
        granted_tokens: Math.max(0, quotaDraft.grantedTokens),
        consumed_tokens: Math.max(0, quotaDraft.consumedTokens),
        frozen: quotaDraft.frozen,
        reason: quotaDraft.reason.trim()
      });
      setQuota(updated);
      setQuotaDraft({
        grantedTokens: updated.granted_tokens,
        consumedTokens: updated.consumed_tokens,
        frozen: updated.frozen,
        reason: ''
      });
      setActionMessage(t('quotaSaved'));
    } catch (quotaError: unknown) {
      setActionMessage(quotaError instanceof Error ? quotaError.message : t('quotaSaveFailed'));
    }
  }

  async function handleDeleteUser() {
    if (!detail) return;
    if (!window.confirm(t('deleteConfirm', {username: detail.username}))) return;
    try {
      await deleteAdminUser(token, detail.id);
      setActionMessage(t('deleteMessage'));
      await refreshUsers('');
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('deleteFailed'));
    }
  }

  return (
    <main className="admin-page">
      <section className="admin-page__hero">
        <div>
          <p className="admin-page__eyebrow">Users</p>
          <h1>{t('title')}</h1>
          <p>{t('subtitle')}</p>
        </div>
        {actionMessage ? <div className="admin-page__hero-chip">{actionMessage}</div> : null}
      </section>

      <section className="admin-stat-grid admin-stat-grid--compact">
        {topStats.map((stat) => (
          <article className="admin-stat-card" key={stat.label}>
            <p className="admin-stat-card__label">{stat.label}</p>
            <div className={`admin-stat-card__value admin-tone--${stat.tone}`}>{stat.value}</div>
          </article>
        ))}
      </section>

      {error ? (
        <div className="admin-inline-error">
          <span>{error}</span>{' '}
          <button
            className="admin-button admin-button--ghost admin-button--small"
            onClick={() => setReloadKey((current) => current + 1)}
            type="button"
          >
            {actions('retry')}
          </button>
        </div>
      ) : null}

      <section className="admin-two-column">
        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Directory</p>
              <h2>{t('directoryTitle')}</h2>
            </div>
            <button
              className="admin-button admin-button--primary admin-button--small"
              type="button"
              onClick={() => {
                setShowCreate(true);
                setSelectedUserId('');
                setDetail(null);
                setEditDraft(null);
              }}
            >
              {t('createUser')}
            </button>
          </div>

          <div className="admin-toolbar">
            <input
              className="admin-input"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('searchPlaceholder')}
            />
            <select
              className="admin-select"
              value={role}
              onChange={(event) => {
                setRole(event.target.value);
                setPage(1);
              }}
            >
              <option value="">{t('allRoles')}</option>
              <option value="admin">{t('adminRole')}</option>
              <option value="enterprise">{t('enterpriseRole')}</option>
              <option value="user">{t('userRole')}</option>
            </select>
            <select
              className="admin-select"
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value);
                setPage(1);
              }}
            >
              <option value="">{t('allStatus')}</option>
              <option value="true">{status('active')}</option>
              <option value="false">{status('inactive')}</option>
            </select>
            <button
              className="admin-button admin-button--ghost"
              onClick={() => {
                setQuery(search.trim());
                setPage(1);
              }}
            >
              {actions('search')}
            </button>
          </div>

          <div className="admin-record-list">
            {loading ? (
              <div className="admin-detail-card">{t('loadingList')}</div>
            ) : listState.items.length === 0 ? (
              <div className="admin-detail-card">{t('emptyList')}</div>
            ) : (
              listState.items.map((item) => (
                <button
                  key={item.id}
                  className={`admin-record-row ${item.id === selectedUserId ? 'is-active' : ''}`}
                  type="button"
                  onClick={() => selectUser(item)}
                >
                  <div className="admin-record-row__body">
                    <div className="admin-record-row__title">
                      <strong>{item.username}</strong>
                      <span className={`admin-pill admin-pill--${item.is_active ? 'success' : 'draft'}`}>
                        {item.is_active ? status('active') : status('inactive')}
                      </span>
                      <span className="admin-pill admin-pill--neutral">{item.role}</span>
                    </div>
                    <div className="admin-record-row__meta">
                      <span>{item.phone || item.email}</span>
                      <span>{item.email}</span>
                      <span>{formatDateTime(item.created_at, locale)}</span>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="admin-pagination">
            <span>
              {units('totalUserPage', {total: listState.total, page: listState.page, pages: listState.pages})}
            </span>
            <div className="admin-detail-list__actions">
              <button
                className="admin-button admin-button--ghost admin-button--small"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                {actions('previousPage')}
              </button>
              <button
                className="admin-button admin-button--ghost admin-button--small"
                disabled={page >= listState.pages}
                onClick={() => setPage((current) => Math.min(listState.pages, current + 1))}
              >
                {actions('nextPage')}
              </button>
            </div>
          </div>
        </article>

        <article className="admin-panel">
          {showCreate ? (
            <form className="admin-stack" onSubmit={handleCreateUser}>
              <div className="admin-panel__header">
                <div>
                  <p className="admin-panel__eyebrow">Create</p>
                  <h2>{t('createTitle')}</h2>
                </div>
              </div>

              <div className="admin-form-grid admin-form-grid--two">
                <label className="admin-field">
                  <span>{t('username')}</span>
                  <input
                    className="admin-input"
                    maxLength={100}
                    minLength={2}
                    required
                    value={createDraft.username}
                    onChange={(event) =>
                      setCreateDraft((current) => ({...current, username: event.target.value}))
                    }
                  />
                </label>
                <label className="admin-field">
                  <span>{t('email')}</span>
                  <input
                    className="admin-input"
                    maxLength={200}
                    required
                    type="email"
                    value={createDraft.email}
                    onChange={(event) =>
                      setCreateDraft((current) => ({...current, email: event.target.value}))
                    }
                  />
                </label>
                <label className="admin-field">
                  <span>{t('phone')}</span>
                  <input
                    className="admin-input"
                    inputMode="numeric"
                    maxLength={30}
                    type="tel"
                    value={createDraft.phone}
                    onChange={(event) =>
                      setCreateDraft((current) => ({...current, phone: event.target.value}))
                    }
                  />
                </label>
                <label className="admin-field">
                  <span>{t('password')}</span>
                  <input
                    className="admin-input"
                    maxLength={128}
                    minLength={6}
                    required
                    type="password"
                    value={createDraft.password}
                    onChange={(event) =>
                      setCreateDraft((current) => ({...current, password: event.target.value}))
                    }
                  />
                </label>
                <label className="admin-field">
                  <span>{t('roleChange')}</span>
                  <select
                    className="admin-select"
                    value={createDraft.role}
                    onChange={(event) => setCreateDraft((current) => ({...current, role: event.target.value}))}
                  >
                    <option value="admin">{t('adminRole')}</option>
                    <option value="enterprise">{t('enterpriseRole')}</option>
                    <option value="user">{t('userRole')}</option>
                  </select>
                </label>
              </div>

              <div className="admin-detail-list__actions">
                <button className="admin-button admin-button--ghost admin-button--small" type="button" onClick={() => setShowCreate(false)}>
                  {actions('cancel')}
                </button>
                <button className="admin-button admin-button--primary admin-button--small" type="submit">
                  {t('createSubmit')}
                </button>
              </div>
            </form>
          ) : detail && editDraft ? (
            <div className="admin-stack">
              <div className="admin-panel__header">
                <div>
                  <p className="admin-panel__eyebrow">Profile</p>
                  <h2>{t('profileTitle')}</h2>
                </div>
              </div>

              <div className="admin-detail-grid admin-detail-grid--compact">
                <div className="admin-detail-card">
                  <span>{t('createdAt')}</span>
                  <strong>{formatDateTime(detail.created_at, locale)}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('currentRole')}</span>
                  <strong>{detail.role}</strong>
                </div>
              </div>

              <section className="admin-detail-list__item">
                <div className="admin-panel__header">
                  <div>
                    <p className="admin-panel__eyebrow">AI quota</p>
                    <h3>{t('aiQuotaTitle')}</h3>
                  </div>
                  {quota ? (
                    <span className={`admin-pill admin-pill--${quota.frozen ? 'warning' : 'success'}`}>
                      {quota.frozen ? t('quotaFrozen') : t('quotaAvailable')}
                    </span>
                  ) : null}
                </div>

                {quota ? (
                  <div className="admin-stack">
                    <div className="admin-detail-grid admin-detail-grid--compact" style={{fontVariantNumeric: 'tabular-nums'}}>
                      <div className="admin-detail-card"><span>{t('quotaGranted')}</span><strong>{quota.granted_tokens.toLocaleString()}</strong></div>
                      <div className="admin-detail-card"><span>{t('quotaConsumed')}</span><strong>{quota.consumed_tokens.toLocaleString()}</strong></div>
                      <div className="admin-detail-card"><span>{t('quotaReserved')}</span><strong>{quota.reserved_tokens.toLocaleString()}</strong></div>
                      <div className="admin-detail-card"><span>{t('quotaRemaining')}</span><strong>{quota.remaining_tokens.toLocaleString()}</strong></div>
                    </div>
                    <div className="admin-inline-notes">
                      <span>{t('linkedAccounts', {count: quota.linked_user_count})}</span>
                      <span>{t('linkedDevices', {count: quota.linked_device_count})}</span>
                    </div>
                    <div className="admin-form-grid admin-form-grid--two">
                      <label className="admin-field">
                        <span>{t('quotaGranted')}</span>
                        <input className="admin-input" min={0} type="number" value={quotaDraft.grantedTokens} onChange={(event) => setQuotaDraft((current) => ({...current, grantedTokens: Number(event.target.value || 0)}))} />
                      </label>
                      <label className="admin-field">
                        <span>{t('quotaConsumed')}</span>
                        <input className="admin-input" min={0} type="number" value={quotaDraft.consumedTokens} onChange={(event) => setQuotaDraft((current) => ({...current, consumedTokens: Number(event.target.value || 0)}))} />
                      </label>
                      <label className="admin-field admin-field--wide">
                        <span>{t('quotaReason')}</span>
                        <input className="admin-input" maxLength={500} value={quotaDraft.reason} onChange={(event) => setQuotaDraft((current) => ({...current, reason: event.target.value}))} placeholder={t('quotaReasonPlaceholder')} />
                      </label>
                    </div>
                    <label className="admin-checkbox-row">
                      <span>{t('freezeQuota')}</span>
                      <input checked={quotaDraft.frozen} type="checkbox" onChange={(event) => setQuotaDraft((current) => ({...current, frozen: event.target.checked}))} />
                    </label>
                    <div className="admin-detail-list__actions">
                      <button className="admin-button admin-button--primary admin-button--small" type="button" onClick={handleQuotaSave}>{t('saveQuota')}</button>
                    </div>
                  </div>
                ) : (
                  <div className="admin-detail-card">{t('quotaLoading')}</div>
                )}
              </section>

              <div className="admin-form-grid admin-form-grid--two">
                <label className="admin-field">
                  <span>{t('username')}</span>
                  <input
                    className="admin-input"
                    maxLength={100}
                    minLength={2}
                    value={editDraft.username}
                    onChange={(event) => setEditDraft((current) => current && {...current, username: event.target.value})}
                  />
                </label>
                <label className="admin-field">
                  <span>{t('email')}</span>
                  <input
                    className="admin-input"
                    maxLength={200}
                    type="email"
                    value={editDraft.email}
                    onChange={(event) => setEditDraft((current) => current && {...current, email: event.target.value})}
                  />
                </label>
                <label className="admin-field">
                  <span>{t('phone')}</span>
                  <input
                    className="admin-input"
                    inputMode="numeric"
                    maxLength={30}
                    type="tel"
                    value={editDraft.phone}
                    onChange={(event) => setEditDraft((current) => current && {...current, phone: event.target.value})}
                  />
                </label>
                <label className="admin-field">
                  <span>{t('roleChange')}</span>
                  <select
                    className="admin-select"
                    value={editDraft.role}
                    onChange={(event) => setEditDraft((current) => current && {...current, role: event.target.value})}
                  >
                    <option value="admin">{t('adminRole')}</option>
                    <option value="enterprise">{t('enterpriseRole')}</option>
                    <option value="user">{t('userRole')}</option>
                  </select>
                </label>
              </div>

              <div className="admin-section-grid">
                <label className="admin-checkbox-row">
                  <span>{t('currentlyActive')}</span>
                  <input
                    checked={editDraft.is_active}
                    type="checkbox"
                    onChange={(event) => setEditDraft((current) => current && {...current, is_active: event.target.checked})}
                  />
                </label>
                <label className="admin-checkbox-row">
                  <span>{status('verified')}</span>
                  <input
                    checked={editDraft.is_verified}
                    type="checkbox"
                    onChange={(event) => setEditDraft((current) => current && {...current, is_verified: event.target.checked})}
                  />
                </label>
              </div>

              <div className="admin-detail-list__actions">
                <button className="admin-button admin-button--ghost admin-button--small" type="button" onClick={handleProfileSave}>
                  {t('saveProfile')}
                </button>
                <button className="admin-button admin-button--primary admin-button--small" type="button" onClick={handleToggleActive}>
                  {detail.is_active ? t('disableAccount') : t('enableAccount')}
                </button>
              </div>

              <div className="admin-detail-list">
                <div className="admin-detail-list__item">
                  <label className="admin-field">
                    <span>{t('newPassword')}</span>
                    <input
                      className="admin-input"
                      maxLength={128}
                      minLength={6}
                      type="password"
                      value={passwordDraft}
                      onChange={(event) => setPasswordDraft(event.target.value)}
                    />
                  </label>
                  <div className="admin-detail-list__actions">
                    <button className="admin-button admin-button--ghost admin-button--small" type="button" onClick={handlePasswordReset}>
                      {t('resetPassword')}
                    </button>
                  </div>
                </div>
                <div className="admin-detail-list__item admin-detail-list__item--danger">
                  <p>{t('dangerZone')}</p>
                  <div className="admin-detail-list__actions">
                    <button className="admin-button admin-button--danger admin-button--small" type="button" onClick={handleDeleteUser}>
                      {t('deleteUser')}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="admin-detail-card">{t('selectUser')}</div>
          )}
        </article>
      </section>
    </main>
  );
}
