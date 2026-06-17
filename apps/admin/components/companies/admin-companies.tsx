'use client';

import {useEffect, useMemo, useState} from 'react';
import {useSearchParams} from 'next/navigation';
import {useTranslations} from 'next-intl';

import type {AdminCompanyDetail, AdminCompanySummary} from '@georank/api-sdk';
import {
  approveAdminCompany,
  deleteAdminCompany,
  getAdminCompanyDetail,
  listAdminCompanies,
  rejectAdminCompany,
  retryAdminCompanyPipeline
} from '@georank/api-sdk';

type AdminCompaniesProps = {
  token: string;
};

type ListState = {
  items: AdminCompanySummary[];
  total: number;
  page: number;
  pages: number;
};

export function AdminCompanies({token}: AdminCompaniesProps) {
  const t = useTranslations('admin.companies');
  const actions = useTranslations('common.actions');
  const status = useTranslations('common.status');
  const fallback = useTranslations('common.fallback');
  const units = useTranslations('common.units');
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [query, setQuery] = useState(searchParams.get('search') || '');
  const [publishStatus, setPublishStatus] = useState('');
  const [pipelineStatus, setPipelineStatus] = useState('');
  const [page, setPage] = useState(1);
  const [listState, setListState] = useState<ListState>({
    items: [],
    total: 0,
    page: 1,
    pages: 1
  });
  const [selectedCompanyId, setSelectedCompanyId] = useState(searchParams.get('company') || '');
  const [detail, setDetail] = useState<AdminCompanyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionMessage, setActionMessage] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    setActionMessage('');

    listAdminCompanies(token, {
      page,
      size: 12,
      search: query || undefined,
      publishStatus: publishStatus || undefined,
      pipelineStatus: pipelineStatus || undefined
    })
      .then((payload) => {
        if (!active) return;
        setListState({
          items: payload.items,
          total: payload.total,
          page: payload.page,
          pages: payload.pages
        });

        const preferredId =
          searchParams.get('company') ||
          selectedCompanyId ||
          payload.items.find((item) => item.publish_status === 'pending_review')?.id ||
          payload.items[0]?.id ||
          '';
        setSelectedCompanyId(preferredId);
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
  }, [token, page, query, publishStatus, pipelineStatus, searchParams, selectedCompanyId, t]);

  useEffect(() => {
    if (!selectedCompanyId) {
      setDetail(null);
      return;
    }

    let active = true;
    setDetailLoading(true);
    getAdminCompanyDetail(token, selectedCompanyId)
      .then((payload) => {
        if (!active) return;
        setDetail(payload);
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : t('detailLoadFailed'));
      })
      .finally(() => {
        if (active) setDetailLoading(false);
      });

    return () => {
      active = false;
    };
  }, [token, selectedCompanyId, t]);

  const stats = useMemo(() => {
    return {
      pendingReview: listState.items.filter((item) => item.publish_status === 'pending_review').length,
      failed: listState.items.filter((item) => item.pipeline_status === 'failed').length,
      published: listState.items.filter((item) => item.publish_status === 'published').length
    };
  }, [listState.items]);

  async function runAction(
    action: 'approve' | 'reject' | 'retry' | 'delete',
    companyId: string
  ) {
    setActionMessage('');
    try {
      if (action === 'approve') {
        await approveAdminCompany(token, companyId);
        setActionMessage(t('publishedMessage'));
      } else if (action === 'reject') {
        await rejectAdminCompany(token, companyId, t('rejectedMessage'));
        setActionMessage(t('rejectedMessage'));
      } else if (action === 'retry') {
        await retryAdminCompanyPipeline(token, companyId);
        setActionMessage(t('retryMessage'));
      } else if (action === 'delete') {
        const shouldDelete = window.confirm(t('deleteConfirm'));
        if (!shouldDelete) return;
        await deleteAdminCompany(token, companyId);
        setActionMessage(t('deletedMessage'));
      }

      const payload = await listAdminCompanies(token, {
        page,
        size: 12,
        search: query || undefined,
        publishStatus: publishStatus || undefined,
        pipelineStatus: pipelineStatus || undefined
      });
      setListState({
        items: payload.items,
        total: payload.total,
        page: payload.page,
        pages: payload.pages
      });

      if (action === 'delete' && selectedCompanyId === companyId) {
        setSelectedCompanyId(payload.items[0]?.id || '');
        if (payload.items.length === 0) {
          setDetail(null);
        }
      } else if (selectedCompanyId) {
        const refreshed = await getAdminCompanyDetail(token, selectedCompanyId);
        setDetail(refreshed);
      }
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('actionFailed'));
    }
  }

  function getPublishStatusLabel(value: string) {
    if (value === 'pending_review') return status('pendingReview');
    if (value === 'published') return status('published');
    return status('draft');
  }

  return (
    <main className="admin-page">
      <section className="admin-page__hero">
        <div>
          <p className="admin-page__eyebrow">Companies</p>
          <h1>{t('title')}</h1>
          <p>{t('subtitle')}</p>
        </div>
        {actionMessage ? <div className="admin-page__hero-chip">{actionMessage}</div> : null}
      </section>

      <section className="admin-stat-grid admin-stat-grid--compact">
        <article className="admin-stat-card">
          <p className="admin-stat-card__label">{t('pendingReview')}</p>
          <div className="admin-stat-card__value admin-tone--success">{stats.pendingReview}</div>
        </article>
        <article className="admin-stat-card">
          <p className="admin-stat-card__label">{t('failedPipeline')}</p>
          <div className="admin-stat-card__value admin-tone--danger">{stats.failed}</div>
        </article>
        <article className="admin-stat-card">
          <p className="admin-stat-card__label">{t('published')}</p>
          <div className="admin-stat-card__value admin-tone--brand">{stats.published}</div>
        </article>
        <article className="admin-stat-card">
          <p className="admin-stat-card__label">{t('currentPageCompanies')}</p>
          <div className="admin-stat-card__value admin-tone--warning">{listState.items.length}</div>
        </article>
      </section>

      <section className="admin-panel">
        <div className="admin-toolbar">
          <input
            className="admin-input"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t('searchPlaceholder')}
          />
          <select
            className="admin-select"
            value={publishStatus}
            onChange={(event) => {
              setPublishStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">{t('allPublishStatus')}</option>
            <option value="pending_review">{status('pendingReview')}</option>
            <option value="published">{status('published')}</option>
            <option value="draft">{status('draft')}</option>
          </select>
          <select
            className="admin-select"
            value={pipelineStatus}
            onChange={(event) => {
              setPipelineStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">{t('allPipelineStatus')}</option>
            <option value="pending">{status('pending')}</option>
            <option value="completed">{status('completed')}</option>
            <option value="failed">{status('failed')}</option>
          </select>
          <button
            className="admin-button admin-button--primary"
            onClick={() => {
              setQuery(search.trim());
              setPage(1);
            }}
            type="button"
          >
            {actions('search')}
          </button>
        </div>
      </section>

      <section className="admin-two-column">
        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">List</p>
              <h2>{t('listTitle')}</h2>
            </div>
            <span className="admin-pill admin-pill--neutral">{units('itemCount', {count: listState.total})}</span>
          </div>

          {loading ? (
            <p className="admin-feed__empty">{t('loadingList')}</p>
          ) : error ? (
            <p className="admin-feed__empty">{error}</p>
          ) : (
            <div className="admin-company-list">
              {listState.items.map((item) => {
                const isActive = item.id === selectedCompanyId;
                return (
                  <button
                    className={`admin-company-row${isActive ? ' is-active' : ''}`}
                    key={item.id}
                    onClick={() => setSelectedCompanyId(item.id)}
                    type="button"
                  >
                    <div className="admin-company-row__main">
                      <div className="admin-company-row__title">
                        <strong>{item.name}</strong>
                        <span className={`admin-pill admin-pill--status admin-pill--${item.publish_status}`}>
                          {getPublishStatusLabel(item.publish_status)}
                        </span>
                      </div>
                      <p>{item.short_description || item.url}</p>
                      <div className="admin-company-row__meta">
                        <span>{item.category || fallback('noCategory')}</span>
                        <span>GEO {item.geo_score ?? '--'}</span>
                        <span>{item.pipeline_status}</span>
                      </div>
                    </div>
                    <div className="admin-company-row__side">
                      <button
                        className="admin-button admin-button--ghost admin-button--small"
                        onClick={(event) => {
                          event.stopPropagation();
                          void runAction('delete', item.id);
                        }}
                        type="button"
                      >
                        {actions('delete')}
                      </button>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          <div className="admin-pagination">
            <button
              className="admin-button admin-button--ghost admin-button--small"
              disabled={page <= 1}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              type="button"
            >
              {actions('previousPage')}
            </button>
            <span>
              {units('pageCounter', {page: listState.page, pages: listState.pages})}
            </span>
            <button
              className="admin-button admin-button--ghost admin-button--small"
              disabled={page >= listState.pages}
              onClick={() => setPage((current) => Math.min(listState.pages, current + 1))}
              type="button"
            >
              {actions('nextPage')}
            </button>
          </div>
        </article>

        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Detail</p>
              <h2>{t('detailTitle')}</h2>
            </div>
            {detail?.publish_status ? (
              <span className={`admin-pill admin-pill--status admin-pill--${detail.publish_status}`}>
                {getPublishStatusLabel(detail.publish_status)}
              </span>
            ) : null}
          </div>

          {detailLoading ? (
            <p className="admin-feed__empty">{t('loadingDetail')}</p>
          ) : detail ? (
            <div className="admin-company-detail">
              <div className="admin-company-detail__hero">
                <div>
                  <h3>{detail.name}</h3>
                  <p>{detail.short_description || detail.description || detail.url}</p>
                </div>
                <div className="admin-company-detail__actions">
                  <button
                    className="admin-button admin-button--primary"
                    onClick={() => void runAction('approve', detail.id)}
                    type="button"
                  >
                    {actions('approve')}
                  </button>
                  <button
                    className="admin-button admin-button--ghost"
                    onClick={() => void runAction('reject', detail.id)}
                    type="button"
                  >
                    {actions('reject')}
                  </button>
                  <button
                    className="admin-button admin-button--ghost"
                    onClick={() => void runAction('retry', detail.id)}
                    type="button"
                  >
                    {actions('retry')}
                  </button>
                </div>
              </div>

              <div className="admin-detail-grid">
                <div className="admin-detail-card">
                  <span>{t('website')}</span>
                  <strong>{detail.url}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('category')}</span>
                  <strong>{detail.category || fallback('noCategory')}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('geoScore')}</span>
                  <strong>{detail.geo_score ?? '--'}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('diagnosticsCount')}</span>
                  <strong>{detail.diagnostic_report_count}</strong>
                </div>
              </div>

              <div className="admin-detail-section">
                <h4>{t('tagsTech')}</h4>
                <div className="admin-tag-cloud">
                  {[...(detail.tags || []), ...(detail.tech_stack || [])].slice(0, 12).map((tag) => (
                    <span className="admin-tag" key={tag}>
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              <div className="admin-detail-section">
                <h4>{t('latestDiagnosticSolutions')}</h4>
                <div className="admin-detail-list">
                  {detail.latest_diagnostic ? (
                    <div className="admin-detail-list__item">
                      <strong>{t('latestDiagnostic')}</strong>
                      <p>
                        {detail.latest_diagnostic.url} · {detail.latest_diagnostic.status} · GEO{' '}
                        {detail.latest_diagnostic.overall_score ?? '--'}
                      </p>
                    </div>
                  ) : (
                    <div className="admin-detail-list__item">
                      <strong>{t('latestDiagnostic')}</strong>
                      <p>{t('noDiagnostics')}</p>
                    </div>
                  )}
                  <div className="admin-detail-list__item">
                    <strong>{t('relatedSolutions')}</strong>
                    <p>{t('relatedSolutionsCount', {count: detail.related_solutions?.length || 0})}</p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <p className="admin-feed__empty">{t('selectCompany')}</p>
          )}
        </article>
      </section>
    </main>
  );
}
