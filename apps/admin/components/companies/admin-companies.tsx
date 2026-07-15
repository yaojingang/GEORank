'use client';

import type {Dispatch, FormEvent, SetStateAction} from 'react';
import {useEffect, useMemo, useState} from 'react';
import {useSearchParams} from 'next/navigation';
import {useTranslations} from 'next-intl';

import type {
  AdminCompanyCreatePayload,
  AdminCompanyDetail,
  AdminCompanySummary
} from '@georank/api-sdk';
import {
  approveAdminCompany,
  createAdminCompany,
  deleteAdminCompany,
  getAdminCompanyDetail,
  listAdminCompanies,
  rejectAdminCompany,
  retryAdminCompanyPipeline,
  updateAdminCompany
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

type CompanyDraft = {
  name: string;
  url: string;
  logo_url: string;
  short_description: string;
  description: string;
  category: string;
  tags: string;
  tech_stack: string;
  is_geo_certified: boolean;
  geo_score: string;
  publish_status: string;
  pipeline_status: string;
  founded_date: string;
  headquarters: string;
  employee_count: string;
  funding_stage: string;
  tech_level: string;
};

const emptyCompanyDraft: CompanyDraft = {
  name: '',
  url: '',
  logo_url: '',
  short_description: '',
  description: '',
  category: '',
  tags: '',
  tech_stack: '',
  is_geo_certified: false,
  geo_score: '',
  publish_status: 'draft',
  pipeline_status: 'completed',
  founded_date: '',
  headquarters: '',
  employee_count: '',
  funding_stage: '',
  tech_level: ''
};

function parseList(value: string) {
  return value
    .split(/[\n,，]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function companyToDraft(company: AdminCompanyDetail): CompanyDraft {
  return {
    name: company.name || '',
    url: company.url || '',
    logo_url: company.logo_url || '',
    short_description: company.short_description || '',
    description: company.description || '',
    category: company.category || '',
    tags: (company.tags || []).join(', '),
    tech_stack: (company.tech_stack || []).join(', '),
    is_geo_certified: Boolean(company.is_geo_certified),
    geo_score: typeof company.geo_score === 'number' ? String(company.geo_score) : '',
    publish_status: company.publish_status || 'draft',
    pipeline_status: company.pipeline_status || 'completed',
    founded_date: company.founded_date || '',
    headquarters: company.headquarters || '',
    employee_count: company.employee_count || '',
    funding_stage: company.funding_stage || '',
    tech_level: company.tech_level || ''
  };
}

function draftToPayload(draft: CompanyDraft): AdminCompanyCreatePayload {
  return {
    name: draft.name.trim(),
    url: draft.url.trim(),
    logo_url: draft.logo_url.trim() || null,
    short_description: draft.short_description.trim() || null,
    description: draft.description.trim() || null,
    category: draft.category.trim() || null,
    tags: parseList(draft.tags),
    tech_stack: parseList(draft.tech_stack),
    is_geo_certified: draft.is_geo_certified,
    geo_score: draft.geo_score.trim() ? Number(draft.geo_score) : null,
    publish_status: draft.publish_status,
    pipeline_status: draft.pipeline_status,
    founded_date: draft.founded_date.trim() || null,
    headquarters: draft.headquarters.trim() || null,
    employee_count: draft.employee_count.trim() || null,
    funding_stage: draft.funding_stage.trim() || null,
    tech_level: draft.tech_level.trim() || null
  };
}

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
  const [editDraft, setEditDraft] = useState<CompanyDraft>(emptyCompanyDraft);
  const [createDraft, setCreateDraft] = useState<CompanyDraft>(emptyCompanyDraft);
  const [showCreate, setShowCreate] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionMessage, setActionMessage] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');

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
        setSelectedCompanyId((current) => {
          if (current && payload.items.some((item) => item.id === current)) return current;
          return (
            searchParams.get('company') ||
            payload.items.find((item) => item.publish_status === 'pending_review')?.id ||
            payload.items[0]?.id ||
            ''
          );
        });
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
  }, [token, page, query, publishStatus, pipelineStatus, refreshKey, searchParams, t]);

  useEffect(() => {
    if (!selectedCompanyId || showCreate) {
      if (!selectedCompanyId) setDetail(null);
      return;
    }

    let active = true;
    setDetailLoading(true);
    getAdminCompanyDetail(token, selectedCompanyId)
      .then((payload) => {
        if (!active) return;
        setDetail(payload);
        setEditDraft(companyToDraft(payload));
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
  }, [token, selectedCompanyId, showCreate, t]);

  const stats = useMemo(() => {
    return {
      pendingReview: listState.items.filter((item) => item.publish_status === 'pending_review').length,
      failed: listState.items.filter((item) => item.pipeline_status === 'failed').length,
      published: listState.items.filter((item) => item.publish_status === 'published').length
    };
  }, [listState.items]);

  async function refreshDetail(companyId = selectedCompanyId) {
    setRefreshKey((current) => current + 1);
    if (companyId) {
      const refreshed = await getAdminCompanyDetail(token, companyId);
      setDetail(refreshed);
      setEditDraft(companyToDraft(refreshed));
    }
  }

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
        if (!window.confirm(t('deleteConfirm'))) return;
        await deleteAdminCompany(token, companyId);
        setActionMessage(t('deletedMessage'));
        if (selectedCompanyId === companyId) {
          setSelectedCompanyId('');
          setDetail(null);
        }
      }
      await refreshDetail(action === 'delete' ? '' : companyId);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('actionFailed'));
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionMessage('');
    try {
      const created = await createAdminCompany(token, draftToPayload(createDraft));
      setActionMessage(t('createdMessage'));
      setCreateDraft(emptyCompanyDraft);
      setShowCreate(false);
      setSelectedCompanyId(created.id);
      setDetail(created);
      setEditDraft(companyToDraft(created));
      setRefreshKey((current) => current + 1);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('createFailed'));
    }
  }

  async function handleUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail) return;
    setActionMessage('');
    try {
      const updated = await updateAdminCompany(token, detail.id, draftToPayload(editDraft));
      setActionMessage(t('updatedMessage'));
      setDetail(updated);
      setEditDraft(companyToDraft(updated));
      setRefreshKey((current) => current + 1);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('updateFailed'));
    }
  }

  function getPublishStatusLabel(value: string) {
    if (value === 'pending_review') return status('pendingReview');
    if (value === 'published') return status('published');
    if (value === 'archived') return status('archived');
    return status('draft');
  }

  function renderCompanyForm(
    draft: CompanyDraft,
    setDraft: Dispatch<SetStateAction<CompanyDraft>>,
    onSubmit: (event: FormEvent<HTMLFormElement>) => void,
    submitLabel: string
  ) {
    return (
      <form className="admin-form-stack" onSubmit={onSubmit}>
        <div className="admin-form-grid admin-form-grid--two">
          <label className="admin-field">
            <span>{t('nameField')}</span>
            <input
              className="admin-input"
              required
              value={draft.name}
              onChange={(event) => setDraft((current) => ({...current, name: event.target.value}))}
            />
          </label>
          <label className="admin-field">
            <span>{t('urlField')}</span>
            <input
              className="admin-input"
              required
              value={draft.url}
              onChange={(event) => setDraft((current) => ({...current, url: event.target.value}))}
            />
          </label>
          <label className="admin-field">
            <span>{t('category')}</span>
            <input
              className="admin-input"
              value={draft.category}
              onChange={(event) => setDraft((current) => ({...current, category: event.target.value}))}
            />
          </label>
          <label className="admin-field">
            <span>{t('logoUrl')}</span>
            <input
              className="admin-input"
              value={draft.logo_url}
              onChange={(event) => setDraft((current) => ({...current, logo_url: event.target.value}))}
            />
          </label>
          <label className="admin-field">
            <span>{t('publishStatus')}</span>
            <select
              className="admin-select"
              value={draft.publish_status}
              onChange={(event) => setDraft((current) => ({...current, publish_status: event.target.value}))}
            >
              <option value="draft">{status('draft')}</option>
              <option value="pending_review">{status('pendingReview')}</option>
              <option value="published">{status('published')}</option>
              <option value="archived">{status('archived')}</option>
            </select>
          </label>
          <label className="admin-field">
            <span>{t('pipelineStatus')}</span>
            <select
              className="admin-select"
              value={draft.pipeline_status}
              onChange={(event) => setDraft((current) => ({...current, pipeline_status: event.target.value}))}
            >
              <option value="pending">{status('pending')}</option>
              <option value="crawling">{status('crawling')}</option>
              <option value="cleaning">{status('cleaning')}</option>
              <option value="graph_building">{status('graphBuilding')}</option>
              <option value="vectorizing">{status('vectorizing')}</option>
              <option value="completed">{status('completed')}</option>
              <option value="failed">{status('failed')}</option>
            </select>
          </label>
          <label className="admin-field">
            <span>{t('geoScore')}</span>
            <input
              className="admin-input"
              max="100"
              min="0"
              type="number"
              value={draft.geo_score}
              onChange={(event) => setDraft((current) => ({...current, geo_score: event.target.value}))}
            />
          </label>
          <label className="admin-field">
            <span>{t('foundedDate')}</span>
            <input
              className="admin-input"
              type="date"
              value={draft.founded_date}
              onChange={(event) => setDraft((current) => ({...current, founded_date: event.target.value}))}
            />
          </label>
        </div>

        <label className="admin-field">
          <span>{t('shortDescription')}</span>
          <input
            className="admin-input"
            value={draft.short_description}
            onChange={(event) => setDraft((current) => ({...current, short_description: event.target.value}))}
          />
        </label>
        <label className="admin-field">
          <span>{t('descriptionField')}</span>
          <textarea
            className="admin-textarea"
            value={draft.description}
            onChange={(event) => setDraft((current) => ({...current, description: event.target.value}))}
          />
        </label>
        <div className="admin-form-grid admin-form-grid--two">
          <label className="admin-field">
            <span>{t('tags')}</span>
            <input
              className="admin-input"
              value={draft.tags}
              onChange={(event) => setDraft((current) => ({...current, tags: event.target.value}))}
              placeholder={t('commaSeparated')}
            />
          </label>
          <label className="admin-field">
            <span>{t('techStack')}</span>
            <input
              className="admin-input"
              value={draft.tech_stack}
              onChange={(event) => setDraft((current) => ({...current, tech_stack: event.target.value}))}
              placeholder={t('commaSeparated')}
            />
          </label>
          <label className="admin-field">
            <span>{t('headquarters')}</span>
            <input
              className="admin-input"
              value={draft.headquarters}
              onChange={(event) => setDraft((current) => ({...current, headquarters: event.target.value}))}
            />
          </label>
          <label className="admin-field">
            <span>{t('employeeCount')}</span>
            <input
              className="admin-input"
              value={draft.employee_count}
              onChange={(event) => setDraft((current) => ({...current, employee_count: event.target.value}))}
            />
          </label>
          <label className="admin-field">
            <span>{t('fundingStage')}</span>
            <input
              className="admin-input"
              value={draft.funding_stage}
              onChange={(event) => setDraft((current) => ({...current, funding_stage: event.target.value}))}
            />
          </label>
          <label className="admin-field">
            <span>{t('techLevel')}</span>
            <input
              className="admin-input"
              value={draft.tech_level}
              onChange={(event) => setDraft((current) => ({...current, tech_level: event.target.value}))}
            />
          </label>
        </div>

        <label className="admin-checkbox-row">
          <span>{t('geoCertified')}</span>
          <input
            checked={draft.is_geo_certified}
            type="checkbox"
            onChange={(event) => setDraft((current) => ({...current, is_geo_certified: event.target.checked}))}
          />
        </label>

        <div className="admin-company-detail__actions">
          <button className="admin-button admin-button--primary" type="submit">
            {submitLabel}
          </button>
          {showCreate ? (
            <button
              className="admin-button admin-button--ghost"
              type="button"
              onClick={() => {
                setShowCreate(false);
                setCreateDraft(emptyCompanyDraft);
              }}
            >
              {actions('cancel')}
            </button>
          ) : null}
        </div>
      </form>
    );
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
            <option value="archived">{status('archived')}</option>
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

      {error ? <div className="admin-inline-error">{error}</div> : null}

      <section className="admin-two-column">
        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">List</p>
              <h2>{t('listTitle')}</h2>
            </div>
            <div className="admin-detail-list__actions">
              <span className="admin-pill admin-pill--neutral">{units('itemCount', {count: listState.total})}</span>
              <button
                className="admin-button admin-button--primary admin-button--small"
                type="button"
                onClick={() => {
                  setShowCreate(true);
                  setDetail(null);
                  setSelectedCompanyId('');
                }}
              >
                {t('newCompany')}
              </button>
            </div>
          </div>

          {loading ? (
            <p className="admin-feed__empty">{t('loadingList')}</p>
          ) : listState.items.length === 0 ? (
            <p className="admin-feed__empty">{t('emptyList')}</p>
          ) : (
            <div className="admin-company-list">
              {listState.items.map((item) => {
                const isActive = item.id === selectedCompanyId;
                return (
                  <button
                    className={`admin-company-row${isActive ? ' is-active' : ''}`}
                    key={item.id}
                    onClick={() => {
                      setShowCreate(false);
                      setSelectedCompanyId(item.id);
                    }}
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
            <span>{units('pageCounter', {page: listState.page, pages: listState.pages})}</span>
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
              <p className="admin-panel__eyebrow">{showCreate ? 'Create' : 'Detail'}</p>
              <h2>{showCreate ? t('createTitle') : t('detailTitle')}</h2>
            </div>
            {detail?.publish_status && !showCreate ? (
              <span className={`admin-pill admin-pill--status admin-pill--${detail.publish_status}`}>
                {getPublishStatusLabel(detail.publish_status)}
              </span>
            ) : null}
          </div>

          {showCreate ? (
            renderCompanyForm(createDraft, setCreateDraft, handleCreate, t('createSubmit'))
          ) : detailLoading ? (
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
                    className="admin-button admin-button--primary admin-button--small"
                    onClick={() => void runAction('approve', detail.id)}
                    type="button"
                  >
                    {actions('approve')}
                  </button>
                  <button
                    className="admin-button admin-button--ghost admin-button--small"
                    onClick={() => void runAction('reject', detail.id)}
                    type="button"
                  >
                    {actions('reject')}
                  </button>
                  <button
                    className="admin-button admin-button--ghost admin-button--small"
                    onClick={() => void runAction('retry', detail.id)}
                    type="button"
                  >
                    {actions('retry')}
                  </button>
                  <button
                    className="admin-button admin-button--danger admin-button--small"
                    onClick={() => void runAction('delete', detail.id)}
                    type="button"
                  >
                    {actions('delete')}
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

              {renderCompanyForm(editDraft, setEditDraft, handleUpdate, t('saveCompany'))}

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
