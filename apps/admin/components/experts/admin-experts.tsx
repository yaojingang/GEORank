'use client';

import type {Dispatch, FormEvent, SetStateAction} from 'react';
import {useEffect, useMemo, useState} from 'react';
import {useTranslations} from 'next-intl';

import type {AdminExpert, AdminExpertPayload} from '@georank/api-sdk';
import {
  createAdminExpert,
  deleteAdminExpert,
  getAdminExpert,
  listAdminExperts,
  updateAdminExpert
} from '@georank/api-sdk';

type AdminExpertsProps = {
  token: string;
};

type ExpertDraft = {
  slug: string;
  display_name: string;
  avatar_initials: string;
  title: string;
  category: string;
  specialty_label: string;
  summary: string;
  expertise: string;
  consultation: string;
  keywords: string;
  sort_order: string;
  is_featured: boolean;
  is_published: boolean;
};

type ListState = {
  items: AdminExpert[];
  total: number;
  page: number;
  pages: number;
  summary: {
    total: number;
    published: number;
    draft: number;
    featured: number;
  };
};

const emptyDraft: ExpertDraft = {
  slug: '',
  display_name: '',
  avatar_initials: '',
  title: '',
  category: 'strategy',
  specialty_label: '',
  summary: '',
  expertise: '',
  consultation: '',
  keywords: '',
  sort_order: '100',
  is_featured: true,
  is_published: false
};

function parseList(value: string) {
  return value
    .split(/[\n,，]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function expertToDraft(expert: AdminExpert): ExpertDraft {
  return {
    slug: expert.slug || '',
    display_name: expert.display_name || '',
    avatar_initials: expert.avatar_initials || '',
    title: expert.title || '',
    category: expert.category || 'strategy',
    specialty_label: expert.specialty_label || '',
    summary: expert.summary || '',
    expertise: (expert.expertise || []).join(', '),
    consultation: expert.consultation || '',
    keywords: (expert.keywords || []).join(', '),
    sort_order: String(expert.sort_order ?? 100),
    is_featured: Boolean(expert.is_featured),
    is_published: Boolean(expert.is_published)
  };
}

function draftToPayload(draft: ExpertDraft): AdminExpertPayload {
  return {
    slug: draft.slug.trim() || null,
    display_name: draft.display_name.trim(),
    avatar_initials: draft.avatar_initials.trim() || null,
    title: draft.title.trim(),
    category: draft.category.trim() || 'strategy',
    specialty_label: draft.specialty_label.trim() || draft.category.trim() || 'strategy',
    summary: draft.summary.trim(),
    expertise: parseList(draft.expertise),
    consultation: draft.consultation.trim(),
    keywords: parseList(draft.keywords),
    sort_order: Number(draft.sort_order || 100),
    is_featured: draft.is_featured,
    is_published: draft.is_published
  };
}

export function AdminExperts({token}: AdminExpertsProps) {
  const t = useTranslations('admin.experts');
  const actions = useTranslations('common.actions');
  const fallback = useTranslations('common.fallback');
  const units = useTranslations('common.units');
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [listState, setListState] = useState<ListState>({
    items: [],
    total: 0,
    page: 1,
    pages: 1,
    summary: {
      total: 0,
      published: 0,
      draft: 0,
      featured: 0
    }
  });
  const [selectedExpertId, setSelectedExpertId] = useState('');
  const [detail, setDetail] = useState<AdminExpert | null>(null);
  const [draft, setDraft] = useState<ExpertDraft>(emptyDraft);
  const [createDraft, setCreateDraft] = useState<ExpertDraft>(emptyDraft);
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
    listAdminExperts(token, {
      page,
      size: 16,
      search: query || undefined,
      category: category || undefined,
      statusFilter: statusFilter || undefined
    })
      .then((payload) => {
        if (!active) return;
        setListState(payload);
        setSelectedExpertId((current) => {
          if (current && payload.items.some((item) => item.id === current)) return current;
          return payload.items[0]?.id || '';
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
  }, [token, page, query, category, statusFilter, refreshKey, t]);

  useEffect(() => {
    if (!selectedExpertId || showCreate) {
      if (!selectedExpertId) setDetail(null);
      return;
    }

    let active = true;
    setDetailLoading(true);
    getAdminExpert(token, selectedExpertId)
      .then((payload) => {
        if (!active) return;
        setDetail(payload);
        setDraft(expertToDraft(payload));
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
  }, [token, selectedExpertId, showCreate, t]);

  const topStats = useMemo(
    () => [
      {label: t('totalExperts'), value: listState.summary.total, tone: 'brand'},
      {label: t('publishedExperts'), value: listState.summary.published, tone: 'success'},
      {label: t('draftExperts'), value: listState.summary.draft, tone: 'warning'},
      {label: t('featuredExperts'), value: listState.summary.featured, tone: 'brand'}
    ],
    [listState.summary, t]
  );

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionMessage('');
    try {
      const created = await createAdminExpert(token, draftToPayload(createDraft));
      setActionMessage(t('createdMessage'));
      setCreateDraft(emptyDraft);
      setShowCreate(false);
      setSelectedExpertId(created.id);
      setDetail(created);
      setDraft(expertToDraft(created));
      setRefreshKey((current) => current + 1);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('createFailed'));
    }
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail) return;
    setActionMessage('');
    try {
      const updated = await updateAdminExpert(token, detail.id, draftToPayload(draft));
      setActionMessage(t('updatedMessage'));
      setDetail(updated);
      setDraft(expertToDraft(updated));
      setRefreshKey((current) => current + 1);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('updateFailed'));
    }
  }

  async function handleDelete() {
    if (!detail) return;
    if (!window.confirm(t('deleteConfirm', {name: detail.display_name}))) return;
    setActionMessage('');
    try {
      await deleteAdminExpert(token, detail.id);
      setActionMessage(t('deletedMessage'));
      setDetail(null);
      setSelectedExpertId('');
      setRefreshKey((current) => current + 1);
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('deleteFailed'));
    }
  }

  function renderForm(
    currentDraft: ExpertDraft,
    setCurrentDraft: Dispatch<SetStateAction<ExpertDraft>>,
    onSubmit: (event: FormEvent<HTMLFormElement>) => void,
    submitLabel: string
  ) {
    return (
      <form className="admin-form-stack" onSubmit={onSubmit}>
        <div className="admin-form-grid admin-form-grid--two">
          <label className="admin-field">
            <span>{t('slug')}</span>
            <input
              className="admin-input"
              value={currentDraft.slug}
              pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
              onChange={(event) => setCurrentDraft((value) => ({...value, slug: event.target.value}))}
            />
          </label>
          <label className="admin-field">
            <span>{t('displayName')}</span>
            <input
              className="admin-input"
              required
              value={currentDraft.display_name}
              onChange={(event) =>
                setCurrentDraft((value) => ({...value, display_name: event.target.value}))
              }
            />
          </label>
          <label className="admin-field">
            <span>{t('titleField')}</span>
            <input
              className="admin-input"
              required
              value={currentDraft.title}
              onChange={(event) => setCurrentDraft((value) => ({...value, title: event.target.value}))}
            />
          </label>
          <label className="admin-field">
            <span>{t('category')}</span>
            <input
              className="admin-input"
              value={currentDraft.category}
              onChange={(event) => setCurrentDraft((value) => ({...value, category: event.target.value}))}
            />
          </label>
          <label className="admin-field">
            <span>{t('specialtyLabel')}</span>
            <input
              className="admin-input"
              value={currentDraft.specialty_label}
              onChange={(event) =>
                setCurrentDraft((value) => ({...value, specialty_label: event.target.value}))
              }
            />
          </label>
          <label className="admin-field">
            <span>{t('avatarInitials')}</span>
            <input
              className="admin-input"
              value={currentDraft.avatar_initials}
              onChange={(event) =>
                setCurrentDraft((value) => ({...value, avatar_initials: event.target.value}))
              }
            />
          </label>
          <label className="admin-field">
            <span>{t('sortOrder')}</span>
            <input
              className="admin-input"
              type="number"
              value={currentDraft.sort_order}
              onChange={(event) =>
                setCurrentDraft((value) => ({...value, sort_order: event.target.value}))
              }
            />
          </label>
        </div>
        <label className="admin-field">
          <span>{t('summary')}</span>
          <textarea
            className="admin-textarea"
            value={currentDraft.summary}
            onChange={(event) => setCurrentDraft((value) => ({...value, summary: event.target.value}))}
          />
        </label>
        <label className="admin-field">
          <span>{t('consultation')}</span>
          <textarea
            className="admin-textarea"
            value={currentDraft.consultation}
            onChange={(event) =>
              setCurrentDraft((value) => ({...value, consultation: event.target.value}))
            }
          />
        </label>
        <div className="admin-form-grid admin-form-grid--two">
          <label className="admin-field">
            <span>{t('expertise')}</span>
            <input
              className="admin-input"
              value={currentDraft.expertise}
              onChange={(event) => setCurrentDraft((value) => ({...value, expertise: event.target.value}))}
              placeholder={t('commaSeparated')}
            />
          </label>
          <label className="admin-field">
            <span>{t('keywords')}</span>
            <input
              className="admin-input"
              value={currentDraft.keywords}
              onChange={(event) => setCurrentDraft((value) => ({...value, keywords: event.target.value}))}
              placeholder={t('commaSeparated')}
            />
          </label>
        </div>
        <label className="admin-checkbox-row">
          <span>{t('featured')}</span>
          <input
            checked={currentDraft.is_featured}
            type="checkbox"
            onChange={(event) =>
              setCurrentDraft((value) => ({...value, is_featured: event.target.checked}))
            }
          />
        </label>
        <label className="admin-checkbox-row">
          <span>{t('published')}</span>
          <input
            checked={currentDraft.is_published}
            type="checkbox"
            onChange={(event) =>
              setCurrentDraft((value) => ({...value, is_published: event.target.checked}))
            }
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
                setCreateDraft(emptyDraft);
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
          <p className="admin-page__eyebrow">Experts</p>
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
            <button
              className="admin-button admin-button--primary admin-button--small"
              type="button"
              onClick={() => {
                setShowCreate(true);
                setSelectedExpertId('');
                setDetail(null);
              }}
            >
              {t('newExpert')}
            </button>
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
              value={category}
              onChange={(event) => {
                setCategory(event.target.value);
                setPage(1);
              }}
              placeholder={t('categoryPlaceholder')}
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
              <option value="published">{t('published')}</option>
              <option value="draft">{t('draft')}</option>
              <option value="featured">{t('featured')}</option>
            </select>
            <button
              className="admin-button admin-button--primary"
              type="button"
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
              <p className="admin-feed__empty">{t('loadingList')}</p>
            ) : listState.items.length === 0 ? (
              <p className="admin-feed__empty">{t('emptyList')}</p>
            ) : (
              listState.items.map((item) => (
                <button
                  className={`admin-record-row ${item.id === selectedExpertId ? 'is-active' : ''}`}
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setShowCreate(false);
                    setSelectedExpertId(item.id);
                  }}
                >
                  <div className="admin-record-row__body">
                    <div className="admin-record-row__title">
                      <strong>{item.display_name}</strong>
                      <span className={`admin-pill admin-pill--${item.is_published ? 'success' : 'neutral'}`}>
                        {item.is_published ? t('published') : t('draft')}
                      </span>
                      {item.is_featured ? (
                        <span className="admin-pill admin-pill--brand">{t('featured')}</span>
                      ) : null}
                    </div>
                    <p>{item.summary || item.title || fallback('noDescription')}</p>
                    <div className="admin-record-row__meta">
                      <span>{item.category}</span>
                      <span>{item.specialty_label}</span>
                      <span>{units('itemCount', {count: item.expertise.length})}</span>
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
                type="button"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                {actions('previousPage')}
              </button>
              <button
                className="admin-button admin-button--ghost admin-button--small"
                disabled={page >= listState.pages}
                type="button"
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
              <p className="admin-panel__eyebrow">{showCreate ? 'Create' : 'Profile'}</p>
              <h2>{showCreate ? t('createTitle') : t('detailTitle')}</h2>
            </div>
            {detail && !showCreate ? (
              <button
                className="admin-button admin-button--danger admin-button--small"
                type="button"
                onClick={handleDelete}
              >
                {actions('delete')}
              </button>
            ) : null}
          </div>

          {showCreate ? (
            renderForm(createDraft, setCreateDraft, handleCreate, t('createSubmit'))
          ) : detailLoading ? (
            <p className="admin-feed__empty">{t('loadingDetail')}</p>
          ) : detail ? (
            <div className="admin-company-detail">
              <div className="admin-detail-grid admin-detail-grid--compact">
                <div className="admin-detail-card">
                  <span>{t('displayName')}</span>
                  <strong>{detail.display_name}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('titleField')}</span>
                  <strong>{detail.title}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('category')}</span>
                  <strong>{detail.category}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('specialtyLabel')}</span>
                  <strong>{detail.specialty_label}</strong>
                </div>
              </div>
              {renderForm(draft, setDraft, handleSave, t('saveExpert'))}
            </div>
          ) : (
            <p className="admin-feed__empty">{t('selectExpert')}</p>
          )}
        </article>
      </section>
    </main>
  );
}
