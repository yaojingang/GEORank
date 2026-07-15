'use client';

import {useEffect, useMemo, useState} from 'react';
import {useSearchParams} from 'next/navigation';
import {useLocale, useTranslations} from 'next-intl';

import type {
  AdminSolutionConversationDetail,
  AdminSolutionConversationSummary,
  AdminSolutionTemplates
} from '@georank/api-sdk';
import {
  deleteAdminSolutionConversation,
  getAdminSolutionConversation,
  getAdminSolutionTemplates,
  listAdminSolutionConversations,
  resetAdminSolutionTemplates,
  updateAdminSolutionTemplates
} from '@georank/api-sdk';

type AdminSolutionsProps = {
  token: string;
};

type SolutionListState = {
  items: AdminSolutionConversationSummary[];
  total: number;
  page: number;
  pages: number;
  summary: {
    message_count: number;
    assistant_message_count: number;
    conversations_with_recommendations: number;
    conversations_with_diagnostics: number;
    public_conversation_count: number;
    owned_conversation_count: number;
    average_message_count: number;
  };
};

type TemplateDraft = {
  system_prompt: string;
  response_instruction: string;
  streaming_system_prompt: string;
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

export function AdminSolutions({token}: AdminSolutionsProps) {
  const locale = useLocale();
  const t = useTranslations('admin.solutions');
  const actions = useTranslations('common.actions');
  const fallback = useTranslations('common.fallback');
  const units = useTranslations('common.units');
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [query, setQuery] = useState(searchParams.get('search') || '');
  const [visibility, setVisibility] = useState<'public' | 'owned' | ''>('');
  const [linkage, setLinkage] = useState<'recommendations' | 'diagnostics' | ''>('');
  const [page, setPage] = useState(1);
  const [listState, setListState] = useState<SolutionListState>({
    items: [],
    total: 0,
    page: 1,
    pages: 1,
    summary: {
      message_count: 0,
      assistant_message_count: 0,
      conversations_with_recommendations: 0,
      conversations_with_diagnostics: 0,
      public_conversation_count: 0,
      owned_conversation_count: 0,
      average_message_count: 0
    }
  });
  const [selectedConversationId, setSelectedConversationId] = useState(
    searchParams.get('conversation') || ''
  );
  const [detail, setDetail] = useState<AdminSolutionConversationDetail | null>(null);
  const [templates, setTemplates] = useState<AdminSolutionTemplates | null>(null);
  const [templateDraft, setTemplateDraft] = useState<TemplateDraft>({
    system_prompt: '',
    response_instruction: '',
    streaming_system_prompt: ''
  });
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');

    listAdminSolutionConversations(token, {
      page,
      size: 12,
      search: query || undefined,
      visibility: visibility || undefined,
      linkage: linkage || undefined
    })
      .then((payload) => {
        if (!active) return;
        setListState(payload);
        const preferredId =
          searchParams.get('conversation') ||
          selectedConversationId ||
          payload.items.find((item) => item.has_recommendations)?.id ||
          payload.items[0]?.id ||
          '';
        setSelectedConversationId(preferredId);
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
  }, [token, page, query, visibility, linkage, searchParams, selectedConversationId, t]);

  useEffect(() => {
    let active = true;
    setTemplatesLoading(true);
    getAdminSolutionTemplates(token)
      .then((payload) => {
        if (!active) return;
        setTemplates(payload);
        setTemplateDraft({
          system_prompt: payload.system_prompt,
          response_instruction: payload.response_instruction,
          streaming_system_prompt: payload.streaming_system_prompt
        });
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : t('templatesLoadFailed'));
      })
      .finally(() => {
        if (active) setTemplatesLoading(false);
      });

    return () => {
      active = false;
    };
  }, [token, t]);

  useEffect(() => {
    if (!selectedConversationId) {
      setDetail(null);
      return;
    }

    let active = true;
    setDetailLoading(true);
    getAdminSolutionConversation(token, selectedConversationId)
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
  }, [token, selectedConversationId, t]);

  const topStats = useMemo(() => {
    return [
      {label: t('currentPageConversations'), value: listState.items.length, tone: 'brand'},
      {
        label: t('withRecommendations'),
        value: listState.summary.conversations_with_recommendations,
        tone: 'success'
      },
      {
        label: t('withDiagnostics'),
        value: listState.summary.conversations_with_diagnostics,
        tone: 'warning'
      },
      {
        label: t('averageMessages'),
        value: listState.summary.average_message_count,
        tone: 'brand'
      }
    ];
  }, [listState, t]);

  async function handleDelete(conversationId: string) {
    const shouldDelete = window.confirm(t('deleteConfirm'));
    if (!shouldDelete) return;

    setActionMessage('');
    try {
      await deleteAdminSolutionConversation(token, conversationId);
      setActionMessage(t('deletedMessage'));
      const nextList = await listAdminSolutionConversations(token, {
        page,
        size: 12,
        search: query || undefined,
        visibility: visibility || undefined,
        linkage: linkage || undefined
      });
      setListState(nextList);
      const nextId = nextList.items[0]?.id || '';
      setSelectedConversationId(nextId);
      if (!nextId) {
        setDetail(null);
      }
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('deleteFailed'));
    }
  }

  async function handleTemplateSave() {
    setActionMessage('');
    try {
      const payload = await updateAdminSolutionTemplates(token, templateDraft);
      setTemplates(payload);
      setTemplateDraft({
        system_prompt: payload.system_prompt,
        response_instruction: payload.response_instruction,
        streaming_system_prompt: payload.streaming_system_prompt
      });
      setActionMessage(t('saveMessage'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('saveFailed'));
    }
  }

  async function handleTemplateReset() {
    setActionMessage('');
    try {
      const payload = await resetAdminSolutionTemplates(token);
      setTemplates(payload);
      setTemplateDraft({
        system_prompt: payload.system_prompt,
        response_instruction: payload.response_instruction,
        streaming_system_prompt: payload.streaming_system_prompt
      });
      setActionMessage(t('resetMessage'));
    } catch (actionError: unknown) {
      setActionMessage(actionError instanceof Error ? actionError.message : t('resetFailed'));
    }
  }

  return (
    <main className="admin-page">
      <section className="admin-page__hero">
        <div>
          <p className="admin-page__eyebrow">Solutions</p>
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
            onChange={(event) => {
              setVisibility(event.target.value as 'public' | 'owned' | '');
              setPage(1);
            }}
            value={visibility}
          >
            <option value="">{t('allVisibility')}</option>
            <option value="public">{t('publicConversation')}</option>
            <option value="owned">{t('ownedConversation')}</option>
          </select>
          <select
            className="admin-select"
            onChange={(event) => {
              setLinkage(event.target.value as 'recommendations' | 'diagnostics' | '');
              setPage(1);
            }}
            value={linkage}
          >
            <option value="">{t('allContext')}</option>
            <option value="recommendations">{t('hasRecommendations')}</option>
            <option value="diagnostics">{t('linkedDiagnostics')}</option>
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
              <p className="admin-panel__eyebrow">Conversations</p>
              <h2>{t('listTitle')}</h2>
            </div>
            <span className="admin-pill admin-pill--neutral">{units('itemCount', {count: listState.total})}</span>
          </div>

          <div className="admin-record-list">
            {loading ? (
              <p className="admin-feed__empty">{t('loadingList')}</p>
            ) : listState.items.length === 0 ? (
              <p className="admin-feed__empty">{t('emptyList')}</p>
            ) : (
              listState.items.map((item) => (
                <button
                  className={`admin-record-row ${item.id === selectedConversationId ? 'is-active' : ''}`}
                  key={item.id}
                  onClick={() => setSelectedConversationId(item.id)}
                  type="button"
                >
                  <div className="admin-record-row__body">
                    <div className="admin-record-row__title">
                      <strong>{item.title}</strong>
                      <span className={`admin-pill admin-pill--${item.is_public ? 'warning' : 'brand'}`}>
                        {item.is_public ? t('publicConversation') : t('ownedConversation')}
                      </span>
                    </div>
                    <p>{item.latest_message_excerpt || fallback('noExcerpt')}</p>
                    <div className="admin-record-row__meta">
                      <span>{item.username || item.user_email || fallback('anonymousSession')}</span>
                      <span>{units('messageCount', {count: item.message_count})}</span>
                      <span>{formatDateTime(item.updated_at, locale)}</span>
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
                <p className="admin-panel__eyebrow">Conversation</p>
                <h2>{t('conversationTitle')}</h2>
              </div>
              {detail ? (
                <button
                  className="admin-button admin-button--ghost admin-button--small"
                  onClick={() => handleDelete(detail.id)}
                  type="button"
                >
                  {t('deleteConversation')}
                </button>
              ) : null}
            </div>

            {detailLoading ? (
              <p className="admin-feed__empty">{t('loadingDetail')}</p>
            ) : !detail ? (
              <p className="admin-feed__empty">{t('selectConversation')}</p>
            ) : (
              <div className="admin-company-detail">
                <div className="admin-detail-grid admin-detail-grid--compact">
                  <div className="admin-detail-card">
                    <span>{t('titleField')}</span>
                    <strong>{detail.title}</strong>
                  </div>
                  <div className="admin-detail-card">
                    <span>{t('visibility')}</span>
                    <strong>{detail.is_public ? t('publicConversation') : t('ownedConversation')}</strong>
                  </div>
                  <div className="admin-detail-card">
                    <span>{t('messageCount')}</span>
                    <strong>{detail.message_count}</strong>
                  </div>
                  <div className="admin-detail-card">
                    <span>{t('recommendedCompanies')}</span>
                    <strong>{detail.recommended_company_count}</strong>
                  </div>
                </div>

                <div className="admin-detail-list">
                  {detail.messages.map((message) => (
                    <div
                      className={`admin-message-card admin-message-card--${message.role}`}
                      key={message.id}
                    >
                      <div className="admin-message-card__meta">
                        <strong>{message.role === 'assistant' ? t('assistantReply') : t('userInput')}</strong>
                        <span>{formatDateTime(message.created_at, locale)}</span>
                      </div>
                      <div className="admin-message-card__content">{message.content}</div>
                      {message.diagnostic_context ? (
                        <div className="admin-message-card__context">
                          {t('diagnosticContext', {
                            url: message.diagnostic_context.url,
                            status: message.diagnostic_context.status
                          })}
                        </div>
                      ) : null}
                      {message.recommended_companies.length > 0 ? (
                        <div className="admin-tag-cloud">
                          {message.recommended_companies.slice(0, 6).map((company, index) => (
                            <span className="admin-tag" key={`${message.id}-company-${index}`}>
                              {String(company.name || company.company_name || t('companyFallback', {index: index + 1}))}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </article>

          <article className="admin-panel">
            <div className="admin-panel__header">
              <div>
                <p className="admin-panel__eyebrow">Templates</p>
                <h2>{t('templatesTitle')}</h2>
              </div>
              <span className={`admin-pill admin-pill--${templates?.uses_default ? 'neutral' : 'brand'}`}>
                {templatesLoading ? t('loading') : templates?.uses_default ? t('defaultTemplate') : t('customTemplate')}
              </span>
            </div>

            <div className="admin-form-stack">
              <label className="admin-field">
                <span>System Prompt</span>
                <textarea
                  className="admin-textarea"
                  onChange={(event) =>
                    setTemplateDraft((current) => ({...current, system_prompt: event.target.value}))
                  }
                  value={templateDraft.system_prompt}
                />
              </label>
              <label className="admin-field">
                <span>Response Instruction</span>
                <textarea
                  className="admin-textarea"
                  onChange={(event) =>
                    setTemplateDraft((current) => ({
                      ...current,
                      response_instruction: event.target.value
                    }))
                  }
                  value={templateDraft.response_instruction}
                />
              </label>
              <label className="admin-field">
                <span>Streaming Prompt</span>
                <textarea
                  className="admin-textarea"
                  onChange={(event) =>
                    setTemplateDraft((current) => ({
                      ...current,
                      streaming_system_prompt: event.target.value
                    }))
                  }
                  value={templateDraft.streaming_system_prompt}
                />
              </label>
            </div>

            <div className="admin-company-detail__actions">
              <button
                className="admin-button admin-button--primary"
                onClick={handleTemplateSave}
                type="button"
              >
                {t('saveTemplate')}
              </button>
              <button
                className="admin-button admin-button--ghost"
                onClick={handleTemplateReset}
                type="button"
              >
                {actions('reset')}
              </button>
            </div>

            {templates ? (
              <div className="admin-inline-notes">
                <span>{t('customFields', {fields: templates.customized_fields.join(', ') || t('noCustomFields')})}</span>
                <span>{t('updatedBy', {user: templates.updated_by_username || t('systemDefault')})}</span>
              </div>
            ) : null}
          </article>
        </div>
      </section>
    </main>
  );
}
