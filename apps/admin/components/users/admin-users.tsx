'use client';

import {useEffect, useMemo, useState} from 'react';
import {useLocale, useTranslations} from 'next-intl';

import type {AdminUserSummary} from '@georank/api-sdk';
import {
  getAdminDashboard,
  listAdminUsers,
  toggleAdminUserActive,
  updateAdminUserRole
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
  const [roleDraft, setRoleDraft] = useState('user');
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    admin: 0,
    new_today: 0
  });
  const [loading, setLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');

    Promise.all([
      listAdminUsers(token, {
        page,
        size: 16,
        role: role || undefined,
        isActive: statusFilter === '' ? undefined : statusFilter === 'true',
        search: query || undefined
      }),
      getAdminDashboard(token)
    ])
      .then(([users, dashboard]) => {
        if (!active) return;
        setListState({
          items: users.items,
          total: users.total,
          page: users.page,
          pages: users.pages
        });
        setStats(dashboard.user_stats);
        const preferredUser = users.items.find((item) => item.id === selectedUserId) || users.items[0] || null;
        setSelectedUserId(preferredUser?.id || '');
        setDetail(preferredUser);
        setRoleDraft(preferredUser?.role || 'user');
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : t('listLoadFailed'));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [token, page, query, role, statusFilter, selectedUserId, t]);

  const topStats = useMemo(() => {
    return [
      {label: t('totalUsers'), value: stats.total, tone: 'brand'},
      {label: t('activeUsers'), value: stats.active, tone: 'success'},
      {label: t('admins'), value: stats.admin, tone: 'warning'},
      {label: t('newToday'), value: stats.new_today, tone: 'brand'}
    ];
  }, [stats, t]);

  async function refreshUsers(nextUserId?: string) {
    const payload = await listAdminUsers(token, {
      page,
      size: 16,
      role: role || undefined,
      isActive: statusFilter === '' ? undefined : statusFilter === 'true',
      search: query || undefined
    });

    setListState({
      items: payload.items,
      total: payload.total,
      page: payload.page,
      pages: payload.pages
    });
    const preferredUser = payload.items.find((item) => item.id === (nextUserId || selectedUserId)) || payload.items[0] || null;
    setSelectedUserId(preferredUser?.id || '');
    setDetail(preferredUser);
    setRoleDraft(preferredUser?.role || 'user');
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

  async function handleRoleSave() {
    if (!detail || roleDraft === detail.role) return;
    try {
      await updateAdminUserRole(token, detail.id, roleDraft);
      setActionMessage(t('roleSaved'));
      await refreshUsers(detail.id);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('roleFailed'));
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

      {error ? <div className="admin-inline-error">{error}</div> : null}

      <section className="admin-two-column">
        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Directory</p>
              <h2>{t('directoryTitle')}</h2>
            </div>
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
                  onClick={() => {
                    setSelectedUserId(item.id);
                    setDetail(item);
                    setRoleDraft(item.role);
                  }}
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
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Profile</p>
              <h2>{t('profileTitle')}</h2>
            </div>
          </div>

          {detail ? (
            <div className="admin-stack">
              <div className="admin-detail-grid admin-detail-grid--compact">
                <div className="admin-detail-card">
                  <span>{t('phone')}</span>
                  <strong>{detail.phone || t('notBound')}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('email')}</span>
                  <strong>{detail.email}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('currentRole')}</span>
                  <strong>{detail.role}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('createdAt')}</span>
                  <strong>{formatDateTime(detail.created_at, locale)}</strong>
                </div>
              </div>

              <div className="admin-form-grid admin-form-grid--two">
                <label className="admin-field">
                  <span>{t('roleChange')}</span>
                  <select
                    className="admin-select"
                    value={roleDraft}
                    onChange={(event) => setRoleDraft(event.target.value)}
                  >
                    <option value="admin">{t('adminRole')}</option>
                    <option value="enterprise">{t('enterpriseRole')}</option>
                    <option value="user">{t('userRole')}</option>
                  </select>
                </label>
                <div className="admin-field">
                  <span>{t('accountStatus')}</span>
                  <div className="admin-inline-notes">
                    <span className={`admin-pill admin-pill--${detail.is_active ? 'success' : 'draft'}`}>
                      {detail.is_active ? t('currentlyActive') : t('currentlyInactive')}
                    </span>
                    <span className={`admin-pill admin-pill--${detail.is_verified ? 'brand' : 'neutral'}`}>
                      {detail.is_verified ? status('verified') : status('unverified')}
                    </span>
                  </div>
                </div>
              </div>

              <div className="admin-detail-list__actions">
                <button className="admin-button admin-button--ghost admin-button--small" onClick={handleRoleSave}>
                  {t('saveRole')}
                </button>
                <button className="admin-button admin-button--primary admin-button--small" onClick={handleToggleActive}>
                  {detail.is_active ? t('disableAccount') : t('enableAccount')}
                </button>
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
