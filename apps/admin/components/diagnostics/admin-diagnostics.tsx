'use client';

import {useEffect, useMemo, useState} from 'react';
import {useSearchParams} from 'next/navigation';
import {useLocale, useTranslations} from 'next-intl';

import type {
  AdminDiagnosticReportDetail,
  AdminDiagnosticReportSummary,
  AdminDiagnosticRules
} from '@georank/api-sdk';
import {
  deleteAdminDiagnosticReport,
  exportAdminDiagnosticReport,
  getAdminDiagnosticReport,
  getAdminDiagnosticRules,
  listAdminDiagnosticReports,
  retryAdminDiagnosticReport,
  updateAdminDiagnosticRules
} from '@georank/api-sdk';

type AdminDiagnosticsProps = {
  token: string;
};

type DiagnosticListState = {
  items: AdminDiagnosticReportSummary[];
  total: number;
  page: number;
  pages: number;
  summary: {
    completed_count: number;
    failed_count: number;
    average_score?: number | null;
  };
};

type RuleDraft = {
  schema: string;
  content: string;
  meta: string;
  citation: string;
};

const diagnosticAnalysisMeta = [
  {key: 'schema_analysis', label: 'Schema'},
  {key: 'content_analysis', label: 'Content'},
  {key: 'meta_analysis', label: 'Meta'},
  {key: 'citation_analysis', label: 'Citation'}
] as const;

function formatDateTime(value?: string | null, locale = 'zh-CN') {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(locale, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
}

function formatScore(value?: number | null) {
  if (typeof value !== 'number') return '—';
  return value.toFixed(1);
}

function getDiagnosticStatusTone(status: string) {
  if (status === 'completed') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'analyzing' || status === 'pending') return 'warning';
  return 'neutral';
}

export function AdminDiagnostics({token}: AdminDiagnosticsProps) {
  const locale = useLocale();
  const t = useTranslations('admin.diagnostics');
  const actions = useTranslations('common.actions');
  const status = useTranslations('common.status');
  const fallback = useTranslations('common.fallback');
  const units = useTranslations('common.units');
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [query, setQuery] = useState(searchParams.get('search') || '');
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '');
  const [page, setPage] = useState(1);
  const [listState, setListState] = useState<DiagnosticListState>({
    items: [],
    total: 0,
    page: 1,
    pages: 1,
    summary: {
      completed_count: 0,
      failed_count: 0,
      average_score: null
    }
  });
  const [selectedReportId, setSelectedReportId] = useState(searchParams.get('report') || '');
  const [detail, setDetail] = useState<AdminDiagnosticReportDetail | null>(null);
  const [rules, setRules] = useState<AdminDiagnosticRules | null>(null);
  const [ruleDraft, setRuleDraft] = useState<RuleDraft>({
    schema: '25',
    content: '35',
    meta: '20',
    citation: '20'
  });
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [rulesLoading, setRulesLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');

    listAdminDiagnosticReports(token, {
      page,
      size: 12,
      search: query || undefined,
      statusFilter: statusFilter || undefined
    })
      .then((payload) => {
        if (!active) return;
        setListState(payload);
        const preferredId =
          searchParams.get('report') ||
          selectedReportId ||
          payload.items.find((item) => item.status === 'failed')?.id ||
          payload.items[0]?.id ||
          '';
        setSelectedReportId(preferredId);
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
  }, [token, page, query, statusFilter, searchParams, selectedReportId, t]);

  useEffect(() => {
    let active = true;
    setRulesLoading(true);
    getAdminDiagnosticRules(token)
      .then((payload) => {
        if (!active) return;
        setRules(payload);
        setRuleDraft({
          schema: String(payload.weights.schema),
          content: String(payload.weights.content),
          meta: String(payload.weights.meta),
          citation: String(payload.weights.citation)
        });
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : t('rulesLoadFailed'));
      })
      .finally(() => {
        if (active) setRulesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, t]);

  useEffect(() => {
    if (!selectedReportId) {
      setDetail(null);
      return;
    }

    let active = true;
    setDetailLoading(true);
    getAdminDiagnosticReport(token, selectedReportId)
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
  }, [token, selectedReportId, t]);

  const topStats = useMemo(() => {
    return [
      {label: t('failedReports'), value: listState.summary.failed_count, tone: 'danger'},
      {label: t('completedReports'), value: listState.summary.completed_count, tone: 'success'},
      {label: t('averageScore'), value: formatScore(listState.summary.average_score), tone: 'brand'},
      {label: t('currentPage'), value: listState.items.length, tone: 'warning'}
    ];
  }, [listState, t]);

  async function handleRetry(reportId: string) {
    setActionMessage('');
    try {
      await retryAdminDiagnosticReport(token, reportId);
      setActionMessage(t('retryMessage'));
      const [nextList, nextDetail] = await Promise.all([
        listAdminDiagnosticReports(token, {
          page,
          size: 12,
          search: query || undefined,
          statusFilter: statusFilter || undefined
        }),
        getAdminDiagnosticReport(token, reportId)
      ]);
      setListState(nextList);
      setDetail(nextDetail);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('retryFailed'));
    }
  }

  async function handleDelete(reportId: string) {
    if (!window.confirm(t('deleteConfirm'))) return;
    setActionMessage('');
    try {
      await deleteAdminDiagnosticReport(token, reportId);
      setActionMessage(t('deletedMessage'));
      const nextList = await listAdminDiagnosticReports(token, {
        page,
        size: 12,
        search: query || undefined,
        statusFilter: statusFilter || undefined
      });
      setListState(nextList);
      const nextId = nextList.items[0]?.id || '';
      setSelectedReportId(nextId);
      if (!nextId) {
        setDetail(null);
      }
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('deleteFailed'));
    }
  }

  async function handleRuleSave() {
    setActionMessage('');
    try {
      const payload = {
        schema: Number(ruleDraft.schema),
        content: Number(ruleDraft.content),
        meta: Number(ruleDraft.meta),
        citation: Number(ruleDraft.citation)
      };
      const nextRules = await updateAdminDiagnosticRules(token, payload);
      setRules(nextRules);
      setRuleDraft({
        schema: String(nextRules.weights.schema),
        content: String(nextRules.weights.content),
        meta: String(nextRules.weights.meta),
        citation: String(nextRules.weights.citation)
      });
      setActionMessage(t('saveRulesMessage'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('saveRulesFailed'));
    }
  }

  async function handleExport(format: 'markdown' | 'json') {
    if (!selectedReportId) return;
    setActionMessage('');
    try {
      const blob = await exportAdminDiagnosticReport(token, selectedReportId, format);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = `diagnostic-${selectedReportId}.${format === 'json' ? 'json' : 'md'}`;
      link.click();
      URL.revokeObjectURL(objectUrl);
      setActionMessage(t('exported', {format: format.toUpperCase()}));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('exportFailed'));
    }
  }

  const recommendationSections = Object.entries(detail?.recommendations || {}).filter(
    ([, items]) => Array.isArray(items) && items.length > 0
  );

  return (
    <main className="admin-page">
      <section className="admin-page__hero">
        <div>
          <p className="admin-page__eyebrow">Diagnostics</p>
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
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              setPage(1);
            }}
          >
            <option value="">{t('allStatus')}</option>
            <option value="pending">{status('pending')}</option>
            <option value="analyzing">{status('analyzing')}</option>
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
              <p className="admin-panel__eyebrow">Queue</p>
              <h2>{t('queueTitle')}</h2>
            </div>
            <span className="admin-pill admin-pill--neutral">{units('reportCount', {count: listState.total})}</span>
          </div>

          <div className="admin-record-list">
            {loading ? (
              <p className="admin-feed__empty">{t('loadingList')}</p>
            ) : listState.items.length === 0 ? (
              <p className="admin-feed__empty">{t('emptyList')}</p>
            ) : (
              listState.items.map((item) => (
                <button
                  className={`admin-record-row ${item.id === selectedReportId ? 'is-active' : ''}`}
                  key={item.id}
                  onClick={() => setSelectedReportId(item.id)}
                  type="button"
                >
                  <div className="admin-record-row__body">
                    <div className="admin-record-row__title">
                      <strong>{item.company_name || item.url}</strong>
                      <span className={`admin-pill admin-pill--${getDiagnosticStatusTone(item.status)}`}>
                        {item.status}
                      </span>
                    </div>
                    <p>{item.url}</p>
                    <div className="admin-record-row__meta">
                      <span>{t('scoreLabel', {score: formatScore(item.overall_score)})}</span>
                      <span>{item.username || item.user_email || fallback('anonymousUser')}</span>
                      <span>{formatDateTime(item.created_at, locale)}</span>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="admin-pagination">
            <span>
              {units('pageCounter', {page: listState.page, pages: Math.max(1, listState.pages)})}
            </span>
            <div className="admin-company-detail__actions">
              <button
                className="admin-button admin-button--ghost admin-button--small"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                type="button"
              >
                {actions('previousPage')}
              </button>
              <button
                className="admin-button admin-button--ghost admin-button--small"
                disabled={page >= listState.pages}
                onClick={() => setPage((current) => Math.min(listState.pages, current + 1))}
                type="button"
              >
                {actions('nextPage')}
              </button>
            </div>
          </div>
        </article>

        <div className="admin-stack">
          <article className="admin-panel">
            <div className="admin-panel__header">
              <div>
                <p className="admin-panel__eyebrow">Report</p>
                <h2>{t('reportTitle')}</h2>
              </div>
              {detail ? (
                <div className="admin-company-detail__actions">
                  <button
                    className="admin-button admin-button--ghost admin-button--small"
                    onClick={() => handleExport('markdown')}
                    type="button"
                  >
                    {actions('exportMarkdown')}
                  </button>
                  <button
                    className="admin-button admin-button--ghost admin-button--small"
                    onClick={() => handleExport('json')}
                    type="button"
                  >
                    {actions('exportJson')}
                  </button>
                  <button
                    className="admin-button admin-button--primary admin-button--small"
                    onClick={() => handleRetry(detail.id)}
                    type="button"
                  >
                    {actions('retry')}
                  </button>
                  <button
                    className="admin-button admin-button--danger admin-button--small"
                    onClick={() => handleDelete(detail.id)}
                    type="button"
                  >
                    {actions('delete')}
                  </button>
                </div>
              ) : null}
            </div>

            {detailLoading ? (
              <p className="admin-feed__empty">{t('loadingDetail')}</p>
            ) : !detail ? (
              <p className="admin-feed__empty">{t('selectReport')}</p>
            ) : (
              <div className="admin-company-detail">
                <div className="admin-detail-grid admin-detail-grid--compact">
                  <div className="admin-detail-card">
                    <span>URL</span>
                    <strong>{detail.url}</strong>
                  </div>
                  <div className="admin-detail-card">
                    <span>{t('status')}</span>
                    <strong>{detail.status}</strong>
                  </div>
                  <div className="admin-detail-card">
                    <span>{t('overallScore')}</span>
                    <strong>{formatScore(detail.overall_score)}</strong>
                  </div>
                  <div className="admin-detail-card">
                    <span>{t('relatedCompany')}</span>
                    <strong>{detail.company_name || t('unlinked')}</strong>
                  </div>
                </div>

                <div className="admin-detail-grid admin-detail-grid--compact">
                  {diagnosticAnalysisMeta.map((analysisItem) => {
                    const section = detail[analysisItem.key];
                    return (
                      <div className="admin-detail-card" key={analysisItem.key}>
                        <span>{analysisItem.label}</span>
                        <strong>{formatScore(typeof section?.score === 'number' ? section.score : null)}</strong>
                        <p>{section?.summary || t('noSummary')}</p>
                      </div>
                    );
                  })}
                </div>

                <div className="admin-detail-section">
                  <h4>{t('recommendedActions')}</h4>
                  {recommendationSections.length === 0 ? (
                    <p className="admin-feed__empty">{t('noActions')}</p>
                  ) : (
                    <div className="admin-section-grid">
                      {recommendationSections.map(([sectionKey, items]) => (
                        <div className="admin-detail-list__item" key={sectionKey}>
                          <strong>{sectionKey}</strong>
                          <ul className="admin-bullet-list">
                            {items.map((item, index) => {
                              const content =
                                typeof item === 'string'
                                  ? item
                                  : `${item.item || t('recommendationItem')}: ${item.action || t('pendingAction')}`;
                              return <li key={`${sectionKey}-${index}`}>{content}</li>;
                            })}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="admin-detail-section">
                  <h4>{t('relatedSolutions')}</h4>
                  {detail.related_solutions.length === 0 ? (
                    <p className="admin-feed__empty">{t('noRelatedSolutions')}</p>
                  ) : (
                    <div className="admin-detail-list">
                      {detail.related_solutions.map((solution) => (
                        <div className="admin-detail-list__item" key={solution.id}>
                          <strong>{solution.title}</strong>
                          <p>{solution.latest_message_excerpt || fallback('noExcerpt')}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </article>

          <article className="admin-panel">
            <div className="admin-panel__header">
              <div>
                <p className="admin-panel__eyebrow">Rules</p>
                <h2>{t('rulesTitle')}</h2>
              </div>
              <span className="admin-pill admin-pill--brand">
                {rulesLoading ? t('loading') : t('totalWeight', {weight: rules?.weights ? Object.values(rules.weights).reduce((sum, item) => sum + item, 0) : 0})}
              </span>
            </div>

            <div className="admin-form-grid">
              {(['schema', 'content', 'meta', 'citation'] as Array<keyof RuleDraft>).map((field) => (
                <label className="admin-field" key={field}>
                  <span>{field.toUpperCase()}</span>
                  <input
                    className="admin-input"
                    inputMode="decimal"
                    onChange={(event) =>
                      setRuleDraft((current) => ({...current, [field]: event.target.value}))
                    }
                    value={ruleDraft[field]}
                  />
                </label>
              ))}
            </div>

            <div className="admin-company-detail__actions">
              <button
                className="admin-button admin-button--primary"
                onClick={handleRuleSave}
                type="button"
              >
                {t('saveWeights')}
              </button>
            </div>
          </article>
        </div>
      </section>
    </main>
  );
}
