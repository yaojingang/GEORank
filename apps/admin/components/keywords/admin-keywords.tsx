'use client';

import {useEffect, useMemo, useState} from 'react';
import {useTranslations} from 'next-intl';

import type {
  AdminKeywordPackDetail,
  AdminKeywordPackSummary,
  AdminKeywordSummary
} from '@georank/api-sdk';
import {
  createAdminKeywordPack,
  deleteAdminKeywordPack,
  exportAdminKeywordPack,
  getAdminKeywordPack,
  getAdminKeywordSummary,
  listAdminKeywordPacks
} from '@georank/api-sdk';

type AdminKeywordsProps = {
  token: string;
};

type ListState = {
  items: AdminKeywordPackSummary[];
  total: number;
  page: number;
  pages: number;
};

function parseSeeds(input: string) {
  return input
    .split(/[\n,，]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function downloadBlob(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(objectUrl);
}

export function AdminKeywords({token}: AdminKeywordsProps) {
  const t = useTranslations('admin.keywords');
  const actions = useTranslations('common.actions');
  const units = useTranslations('common.units');
  const [input, setInput] = useState(t('defaultSeed'));
  const [title, setTitle] = useState('');
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [sourceType, setSourceType] = useState('');
  const [page, setPage] = useState(1);
  const [summary, setSummary] = useState<AdminKeywordSummary | null>(null);
  const [listState, setListState] = useState<ListState>({
    items: [],
    total: 0,
    page: 1,
    pages: 1
  });
  const [selectedPackId, setSelectedPackId] = useState('');
  const [detail, setDetail] = useState<AdminKeywordPackDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState('');
  const [actionMessage, setActionMessage] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');

    Promise.all([
      getAdminKeywordSummary(token),
      listAdminKeywordPacks(token, {
        page,
        size: 12,
        search: query || undefined,
        sourceType: sourceType || undefined
      })
    ])
      .then(([summaryPayload, listPayload]) => {
        if (!active) return;
        setSummary(summaryPayload);
        setListState(listPayload);
        setSelectedPackId((current) => {
          if (current && listPayload.items.some((item) => item.id === current)) return current;
          return listPayload.items[0]?.id || '';
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
  }, [token, page, query, sourceType, refreshKey, t]);

  useEffect(() => {
    if (!selectedPackId) {
      setDetail(null);
      return;
    }

    let active = true;
    setDetailLoading(true);
    getAdminKeywordPack(token, selectedPackId)
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
  }, [token, selectedPackId, t]);

  const topStats = useMemo(
    () => [
      {label: t('totalPacks'), value: summary?.total_packs ?? 0, tone: 'brand'},
      {label: t('totalKeywords'), value: summary?.total_keywords ?? 0, tone: 'success'},
      {
        label: t('averageRecommendation'),
        value: Math.round(summary?.avg_recommendation_score ?? 0),
        tone: 'brand'
      },
      {label: t('averageBusiness'), value: Math.round(summary?.avg_business_score ?? 0), tone: 'warning'}
    ],
    [summary, t]
  );

  async function handleGenerate() {
    const seeds = parseSeeds(input);
    if (seeds.length === 0) {
      setActionMessage(t('missingSeed'));
      return;
    }

    setGenerating(true);
    setActionMessage('');
    try {
      const created = await createAdminKeywordPack(token, {
        title: title.trim() || undefined,
        seeds,
        source_type: 'manual'
      });
      setActionMessage(t('createdMessage'));
      setTitle('');
      setSelectedPackId(created.id);
      setDetail(created);
      setRefreshKey((current) => current + 1);
    } catch (loadError: unknown) {
      setActionMessage(loadError instanceof Error ? loadError.message : t('failed'));
    } finally {
      setGenerating(false);
    }
  }

  async function handleExport() {
    if (!detail) return;
    setActionMessage('');
    try {
      const blob = await exportAdminKeywordPack(token, detail.id);
      downloadBlob(blob, `keyword-pack-${detail.id}.csv`);
      setActionMessage(t('exportedMessage'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('exportFailed'));
    }
  }

  async function handleDelete() {
    if (!detail) return;
    if (!window.confirm(t('deleteConfirm', {title: detail.title}))) return;
    setActionMessage('');
    try {
      await deleteAdminKeywordPack(token, detail.id);
      setActionMessage(t('deletedMessage'));
      setDetail(null);
      setSelectedPackId('');
      setRefreshKey((current) => current + 1);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('deleteFailed'));
    }
  }

  return (
    <main className="admin-page">
      <section className="admin-page__hero">
        <div>
          <p className="admin-page__eyebrow">Keywords</p>
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

      <section className="admin-panel">
        <div className="admin-panel__header">
          <div>
            <p className="admin-panel__eyebrow">Workbench</p>
            <h2>{t('workbenchTitle')}</h2>
          </div>
        </div>

        <div className="admin-form-stack">
          <label className="admin-field">
            <span>{t('packTitle')}</span>
            <input
              className="admin-input"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={t('packTitlePlaceholder')}
            />
          </label>
          <label className="admin-field">
            <span>{t('seedLabel')}</span>
            <textarea
              className="admin-textarea admin-textarea--large"
              onChange={(event) => setInput(event.target.value)}
              placeholder={t('seedPlaceholder')}
              value={input}
            />
          </label>
          <div className="admin-company-detail__actions">
            <button
              className="admin-button admin-button--primary"
              disabled={generating}
              onClick={handleGenerate}
              type="button"
            >
              {generating ? t('generating') : t('generateAndSave')}
            </button>
          </div>
        </div>
      </section>

      <section className="admin-two-column">
        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Packs</p>
              <h2>{t('packsTitle')}</h2>
            </div>
            <span className="admin-pill admin-pill--neutral">{units('itemCount', {count: listState.total})}</span>
          </div>

          <div className="admin-toolbar">
            <input
              className="admin-input"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('searchPlaceholder')}
            />
            <input
              className="admin-input"
              value={sourceType}
              onChange={(event) => {
                setSourceType(event.target.value);
                setPage(1);
              }}
              placeholder={t('sourcePlaceholder')}
            />
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

          <div className="admin-record-list">
            {loading ? (
              <p className="admin-feed__empty">{t('loadingList')}</p>
            ) : listState.items.length === 0 ? (
              <p className="admin-feed__empty">{t('emptyList')}</p>
            ) : (
              listState.items.map((item) => (
                <button
                  className={`admin-record-row ${item.id === selectedPackId ? 'is-active' : ''}`}
                  key={item.id}
                  onClick={() => setSelectedPackId(item.id)}
                  type="button"
                >
                  <div className="admin-record-row__body">
                    <div className="admin-record-row__title">
                      <strong>{item.title}</strong>
                      <span className="admin-pill admin-pill--brand">{item.source_type}</span>
                    </div>
                    <p>{item.summary || item.seed_keywords.join(' / ')}</p>
                    <div className="admin-record-row__meta">
                      <span>{units('wordCount', {count: item.total_keywords})}</span>
                      <span>{t('dimensionCountValue', {count: item.dimension_count})}</span>
                      <span>{item.status}</span>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="admin-pagination">
            <span>{units('pageCounter', {page: listState.page, pages: listState.pages})}</span>
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

        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Detail</p>
              <h2>{t('detailTitle')}</h2>
            </div>
            {detail ? (
              <div className="admin-company-detail__actions">
                <button className="admin-button admin-button--ghost admin-button--small" onClick={handleExport}>
                  {t('exportCsv')}
                </button>
                <button className="admin-button admin-button--danger admin-button--small" onClick={handleDelete}>
                  {actions('delete')}
                </button>
              </div>
            ) : null}
          </div>

          {detailLoading ? (
            <p className="admin-feed__empty">{t('loadingDetail')}</p>
          ) : !detail ? (
            <p className="admin-feed__empty">{t('selectPack')}</p>
          ) : (
            <div className="admin-company-detail">
              <div className="admin-detail-grid admin-detail-grid--compact">
                <div className="admin-detail-card">
                  <span>{t('totalKeywords')}</span>
                  <strong>{detail.total_keywords}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('averageRecommendation')}</span>
                  <strong>{Math.round(detail.avg_recommendation_score || 0)}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('averageBusiness')}</span>
                  <strong>{Math.round(detail.avg_business_score || 0)}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('profileLabel')}</span>
                  <strong>{String(detail.profile?.name || detail.profile?.business_model || '—')}</strong>
                </div>
              </div>

              <div className="admin-dimension-grid">
                {detail.dimensions.map((dimension) => (
                  <div className="admin-dimension-card" key={dimension.key}>
                    <div className="admin-dimension-card__header">
                      <div>
                        <strong>{dimension.name}</strong>
                        <p>{dimension.description}</p>
                      </div>
                      <span className="admin-pill admin-pill--brand">{units('wordCount', {count: dimension.count})}</span>
                    </div>
                    <div className="admin-detail-list">
                      {dimension.items.slice(0, 8).map((item) => (
                        <div className="admin-dimension-item" key={item.id}>
                          <div>
                            <strong>{item.keyword}</strong>
                            {item.reason ? <p>{item.reason}</p> : null}
                          </div>
                          <div className="admin-dimension-item__scores">
                            <span>{t('recommendationShort', {score: item.recommendation_score})}</span>
                            <span>{t('businessShort', {score: item.business_score})}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </article>
      </section>
    </main>
  );
}
