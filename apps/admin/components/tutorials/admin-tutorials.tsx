'use client';

import {useEffect, useMemo, useState} from 'react';
import {useSearchParams} from 'next/navigation';
import {useLocale, useTranslations} from 'next-intl';

import type {
  AdminTutorialDetail,
  AdminTutorialPayload,
  AdminTutorialSummary
} from '@georank/api-sdk';
import {
  createAdminTutorial,
  deleteAdminTutorial,
  getAdminTutorial,
  listAdminTutorials,
  publishAdminTutorial,
  updateAdminTutorial
} from '@georank/api-sdk';

type AdminTutorialsProps = {
  token: string;
};

type TutorialListState = {
  items: AdminTutorialSummary[];
  total: number;
  page: number;
  pages: number;
  summary: {
    tutorial_total: number;
    tutorial_published: number;
    draft_assets: number;
    template_total: number;
    total_views: number;
  };
};

type TutorialDraft = {
  title: string;
  content_type: string;
  status: string;
  cover_image: string;
  reading_time_minutes: string;
  tags: string;
  markdown_body: string;
};

const emptyDraft: TutorialDraft = {
  title: '',
  content_type: 'tutorial',
  status: 'draft',
  cover_image: '',
  reading_time_minutes: '',
  tags: '',
  markdown_body: ''
};

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

function toDraft(detail: AdminTutorialDetail): TutorialDraft {
  return {
    title: detail.title,
    content_type: detail.content_type,
    status: detail.status,
    cover_image: detail.cover_image || '',
    reading_time_minutes:
      typeof detail.reading_time_minutes === 'number' ? String(detail.reading_time_minutes) : '',
    tags: detail.tags.join(', '),
    markdown_body: detail.markdown_body
  };
}

function toPayload(draft: TutorialDraft): AdminTutorialPayload {
  return {
    title: draft.title.trim(),
    content_type: draft.content_type,
    status: draft.status || undefined,
    cover_image: draft.cover_image.trim() || null,
    reading_time_minutes: draft.reading_time_minutes ? Number(draft.reading_time_minutes) : null,
    tags: draft.tags
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean),
    markdown_body: draft.markdown_body
  };
}

function getContentTypeLabel(value: string, translate: (key: string) => string) {
  if (value === 'tutorial') return translate('contentTypeTutorial');
  if (value === 'template') return translate('contentTypeTemplate');
  if (value === 'whitepaper') return translate('contentTypeWhitepaper');
  if (value === 'announcement') return translate('contentTypeAnnouncement');
  return value;
}

export function AdminTutorials({token}: AdminTutorialsProps) {
  const locale = useLocale();
  const t = useTranslations('admin.tutorials');
  const actions = useTranslations('common.actions');
  const status = useTranslations('common.status');
  const units = useTranslations('common.units');
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [query, setQuery] = useState(searchParams.get('search') || '');
  const [statusFilter, setStatusFilter] = useState('');
  const [contentType, setContentType] = useState('');
  const [page, setPage] = useState(1);
  const [listState, setListState] = useState<TutorialListState>({
    items: [],
    total: 0,
    page: 1,
    pages: 1,
    summary: {
      tutorial_total: 0,
      tutorial_published: 0,
      draft_assets: 0,
      template_total: 0,
      total_views: 0
    }
  });
  const [selectedTutorialId, setSelectedTutorialId] = useState(searchParams.get('article') || '');
  const [detail, setDetail] = useState<AdminTutorialDetail | null>(null);
  const [draft, setDraft] = useState<TutorialDraft>(emptyDraft);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');

    listAdminTutorials(token, {
      page,
      size: 12,
      search: query || undefined,
      statusFilter: statusFilter || undefined,
      contentType: contentType || undefined
    })
      .then((payload) => {
        if (!active) return;
        setListState(payload);
        const preferredId =
          searchParams.get('article') || selectedTutorialId || payload.items[0]?.id || '';
        setSelectedTutorialId(preferredId);
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
  }, [token, page, query, statusFilter, contentType, searchParams, selectedTutorialId, t]);

  useEffect(() => {
    if (!selectedTutorialId) {
      setDetail(null);
      return;
    }

    let active = true;
    setDetailLoading(true);
    getAdminTutorial(token, selectedTutorialId)
      .then((payload) => {
        if (!active) return;
        setDetail(payload);
        setDraft(toDraft(payload));
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
  }, [token, selectedTutorialId, t]);

  const topStats = useMemo(() => {
    return [
      {label: t('totalTutorials'), value: listState.summary.tutorial_total, tone: 'brand'},
      {label: t('publishedTutorials'), value: listState.summary.tutorial_published, tone: 'success'},
      {label: t('draftAssets'), value: listState.summary.draft_assets, tone: 'warning'},
      {label: t('totalViews'), value: listState.summary.total_views, tone: 'brand'}
    ];
  }, [listState.summary, t]);

  function resetToNewTutorial() {
    setSelectedTutorialId('');
    setDetail(null);
    setDraft(emptyDraft);
    setActionMessage(t('newDraftMessage'));
  }

  async function refreshList(nextSelectedId?: string) {
    const payload = await listAdminTutorials(token, {
      page,
      size: 12,
      search: query || undefined,
      statusFilter: statusFilter || undefined,
      contentType: contentType || undefined
    });
    setListState(payload);
    if (typeof nextSelectedId === 'string') {
      setSelectedTutorialId(nextSelectedId);
    }
  }

  async function handleSave() {
    if (!draft.title.trim()) {
      setActionMessage(t('titleRequired'));
      return;
    }

    setActionMessage('');
    try {
      if (selectedTutorialId) {
        await updateAdminTutorial(token, selectedTutorialId, toPayload(draft));
        const refreshed = await getAdminTutorial(token, selectedTutorialId);
        setDetail(refreshed);
        setDraft(toDraft(refreshed));
        await refreshList(selectedTutorialId);
        setActionMessage(t('updatedMessage'));
      } else {
        const created = await createAdminTutorial(token, toPayload(draft));
        await refreshList(created.id);
        setActionMessage(t('createdMessage'));
      }
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('saveFailed'));
    }
  }

  async function handlePublish() {
    if (!selectedTutorialId) {
      setActionMessage(t('saveBeforePublish'));
      return;
    }
    try {
      await publishAdminTutorial(token, selectedTutorialId);
      const refreshed = await getAdminTutorial(token, selectedTutorialId);
      setDetail(refreshed);
      setDraft(toDraft(refreshed));
      await refreshList(selectedTutorialId);
      setActionMessage(t('publishedMessage'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('publishFailed'));
    }
  }

  async function handleDelete() {
    if (!selectedTutorialId) return;
    const shouldDelete = window.confirm(t('deleteConfirm'));
    if (!shouldDelete) return;

    try {
      await deleteAdminTutorial(token, selectedTutorialId);
      const nextList = await listAdminTutorials(token, {
        page,
        size: 12,
        search: query || undefined,
        statusFilter: statusFilter || undefined,
        contentType: contentType || undefined
      });
      setListState(nextList);
      const nextId = nextList.items[0]?.id || '';
      setSelectedTutorialId(nextId);
      if (!nextId) {
        setDetail(null);
        setDraft(emptyDraft);
      }
      setActionMessage(t('deletedMessage'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('deleteFailed'));
    }
  }

  return (
    <main className="admin-page">
      <section className="admin-page__hero">
        <div>
          <p className="admin-page__eyebrow">Tutorials</p>
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
              <p className="admin-panel__eyebrow">Library</p>
              <h2>{t('libraryTitle')}</h2>
            </div>
            <button className="admin-button admin-button--primary admin-button--small" onClick={resetToNewTutorial}>
              {t('newTutorial')}
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
              value={contentType}
              onChange={(event) => {
                setContentType(event.target.value);
                setPage(1);
              }}
            >
              <option value="">{t('allTypes')}</option>
              <option value="tutorial">{t('contentTypeTutorial')}</option>
              <option value="template">{t('contentTypeTemplate')}</option>
              <option value="whitepaper">{t('contentTypeWhitepaper')}</option>
              <option value="announcement">{t('contentTypeAnnouncement')}</option>
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
              <option value="draft">{status('draft')}</option>
              <option value="published">{status('published')}</option>
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
                  className={`admin-record-row ${item.id === selectedTutorialId ? 'is-active' : ''}`}
                  onClick={() => setSelectedTutorialId(item.id)}
                  type="button"
                >
                  <div className="admin-record-row__body">
                    <div className="admin-record-row__title">
                      <strong>{item.title}</strong>
                      <span className={`admin-pill admin-pill--${item.status}`}>{item.status}</span>
                      <span className="admin-pill admin-pill--neutral">
                        {getContentTypeLabel(item.content_type, t)}
                      </span>
                    </div>
                    <div className="admin-record-row__meta">
                      <span>{item.path_key || item.slug}</span>
                      <span>{t('reads', {count: item.view_count.toLocaleString(locale)})}</span>
                      <span>{units('minutes', {count: item.reading_time_minutes || 0})}</span>
                      <span>{formatDateTime(item.updated_at, locale)}</span>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="admin-pagination">
            <span>
              {units('totalArticlePage', {total: listState.total, page: listState.page, pages: listState.pages})}
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

        <div className="admin-stack">
          <article className="admin-panel">
            <div className="admin-panel__header">
              <div>
                <p className="admin-panel__eyebrow">Editor</p>
                <h2>{selectedTutorialId ? t('editorEdit') : t('editorNew')}</h2>
              </div>
              <div className="admin-detail-list__actions">
                <button className="admin-button admin-button--ghost admin-button--small" onClick={handleSave}>
                  {actions('save')}
                </button>
                <button
                  className="admin-button admin-button--primary admin-button--small"
                  disabled={!selectedTutorialId}
                  onClick={handlePublish}
                >
                  {actions('publish')}
                </button>
                <button
                  className="admin-button admin-button--ghost admin-button--small"
                  disabled={!selectedTutorialId}
                  onClick={handleDelete}
                >
                  {actions('delete')}
                </button>
              </div>
            </div>

            <div className="admin-form-stack">
              <div className="admin-form-grid">
                <label className="admin-field">
                  <span>{t('titleField')}</span>
                  <input
                    className="admin-input"
                    value={draft.title}
                    onChange={(event) => setDraft((current) => ({...current, title: event.target.value}))}
                  />
                </label>
                <label className="admin-field">
                  <span>{t('typeField')}</span>
                  <select
                    className="admin-select"
                    value={draft.content_type}
                    onChange={(event) =>
                      setDraft((current) => ({...current, content_type: event.target.value}))
                    }
                  >
                    <option value="tutorial">{t('contentTypeTutorial')}</option>
                    <option value="template">{t('contentTypeTemplate')}</option>
                    <option value="whitepaper">{t('contentTypeWhitepaper')}</option>
                    <option value="announcement">{t('contentTypeAnnouncement')}</option>
                  </select>
                </label>
                <label className="admin-field">
                  <span>{t('statusField')}</span>
                  <select
                    className="admin-select"
                    value={draft.status}
                    onChange={(event) => setDraft((current) => ({...current, status: event.target.value}))}
                  >
                    <option value="draft">{status('draft')}</option>
                    <option value="published">{status('published')}</option>
                  </select>
                </label>
                <label className="admin-field">
                  <span>{t('readingMinutes')}</span>
                  <input
                    className="admin-input"
                    value={draft.reading_time_minutes}
                    onChange={(event) =>
                      setDraft((current) => ({...current, reading_time_minutes: event.target.value}))
                    }
                    inputMode="numeric"
                  />
                </label>
              </div>

              <label className="admin-field">
                <span>{t('coverImage')}</span>
                <input
                  className="admin-input"
                  value={draft.cover_image}
                  onChange={(event) => setDraft((current) => ({...current, cover_image: event.target.value}))}
                />
              </label>

              <label className="admin-field">
                <span>{t('tags')}</span>
                <input
                  className="admin-input"
                  value={draft.tags}
                  onChange={(event) => setDraft((current) => ({...current, tags: event.target.value}))}
                  placeholder={t('tagsPlaceholder')}
                />
              </label>

              <label className="admin-field">
                <span>{t('markdownBody')}</span>
                <textarea
                  className="admin-textarea admin-textarea--large"
                  value={draft.markdown_body}
                  onChange={(event) =>
                    setDraft((current) => ({...current, markdown_body: event.target.value}))
                  }
                />
              </label>
            </div>
          </article>

          <article className="admin-panel">
            <div className="admin-panel__header">
              <div>
                <p className="admin-panel__eyebrow">Preview</p>
                <h2>{t('previewTitle')}</h2>
              </div>
            </div>

            {detailLoading ? (
              <div className="admin-detail-card">{t('loadingDetail')}</div>
            ) : detail ? (
              <div className="admin-stack">
                <div className="admin-detail-grid admin-detail-grid--compact">
                  <div className="admin-detail-card">
                    <span>{t('shortLink')}</span>
                    <strong>{detail.path_key || detail.slug}</strong>
                  </div>
                  <div className="admin-detail-card">
                    <span>{t('updatedAt')}</span>
                    <strong>{formatDateTime(detail.updated_at, locale)}</strong>
                  </div>
                </div>
                <div className="admin-preview">
                  <div
                    className="admin-preview__body"
                    dangerouslySetInnerHTML={{__html: detail.html_body || `<p>${t('newDraftPreview')}</p>`}}
                  />
                </div>
              </div>
            ) : (
              <div className="admin-detail-card">{t('newDraftPreview')}</div>
            )}
          </article>
        </div>
      </section>
    </main>
  );
}
