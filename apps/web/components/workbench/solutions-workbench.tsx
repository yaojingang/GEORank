'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {useTranslations} from 'next-intl';

import type { SolutionConversationDetail, SolutionConversationSummary, SolutionStreamEvent, UserOut } from '@georank/api-sdk';
import { getSolutionConversation, listSolutionConversations, streamSolutionChat } from '@georank/api-sdk';

import { SessionGuard } from '../auth/session-guard';

type SolutionsWorkbenchProps = {
  locale: string;
  initialConversationId?: string;
};

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
};

function formatDateTime(value?: string, locale = 'zh-CN') {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
}

function buildFollowups(
  lastPrompt: string,
  t: ReturnType<typeof useTranslations>
) {
  const topic = lastPrompt.trim() || t('defaultTopic');
  return [
    {
      label: t('followupChecklist'),
      prompt: t('followupChecklistPrompt', {topic})
    },
    {
      label: t('followupCompanies'),
      prompt: t('followupCompaniesPrompt', {topic})
    }
  ];
}

function toChatMessages(conversation: SolutionConversationDetail | null): ChatMessage[] {
  if (!conversation) return [];
  return conversation.messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    created_at: message.created_at
  }));
}

function SolutionsWorkbenchInner({
  locale,
  token,
  user,
  initialConversationId
}: {
  locale: string;
  token: string;
  user: UserOut;
  initialConversationId?: string;
}) {
  const t = useTranslations('web.solutions');
  const [conversations, setConversations] = useState<SolutionConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState(initialConversationId || '');
  const [activeConversation, setActiveConversation] = useState<SolutionConversationDetail | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState('');
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [recommendedCount, setRecommendedCount] = useState(0);
  const [followups, setFollowups] = useState<Array<{ label: string; prompt: string }>>([]);

  const loadConversations = useCallback(async () => {
    const next = await listSolutionConversations(token);
    setConversations(next);
    if (!activeConversationId && next[0]) {
      setActiveConversationId(next[0].id);
    }
  }, [activeConversationId, token]);

  const loadConversation = useCallback(
    async (conversationId: string) => {
      const next = await getSolutionConversation(token, conversationId);
      setActiveConversation(next);
      setMessages(toChatMessages(next));
      setActiveConversationId(next.id);
      setRecommendedCount(
        next.messages.reduce((count, message) => count + (message.recommended_companies?.length || 0), 0)
      );
      return next;
    },
    [token]
  );

  useEffect(() => {
    loadConversations().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : t('historyLoadFailed'));
    });
  }, [loadConversations, t]);

  useEffect(() => {
    if (!activeConversationId) return;
    loadConversation(activeConversationId).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : t('detailLoadFailed'));
    });
  }, [activeConversationId, loadConversation, t]);

  async function sendMessage(prompt: string) {
    const content = prompt.trim();
    if (!content || streaming) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString()
    };

    const assistantId = `assistant-${Date.now()}`;
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString()
    };

    setInput('');
    setError('');
    setStreaming(true);
    setFollowups([]);
    setMessages((current) => [...current, userMessage, assistantMessage]);

    try {
      await streamSolutionChat(
        token,
        {
          message: content,
          conversation_id: activeConversationId || undefined
        },
        (event: SolutionStreamEvent) => {
          if (event.type === 'text') {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, content: `${message.content}${event.content}` }
                  : message
              )
            );
          }

          if (event.type === 'companies') {
            setRecommendedCount(event.content.length);
          }

          if (event.type === 'done') {
            setActiveConversationId(event.conversation_id);
            setFollowups(buildFollowups(content, t));
            setStreaming(false);
            loadConversations().catch(() => undefined);
          }

          if (event.type === 'error') {
            setError(event.content);
            setStreaming(false);
          }
        }
      );

      if (activeConversationId) {
        loadConversation(activeConversationId).catch(() => undefined);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('sendFailed'));
      setStreaming(false);
    }
  }

  const contextMeta = useMemo(
    () => [
      { label: t('account'), value: user.phone || user.username },
      { label: t('historyCount'), value: String(conversations.length) },
      { label: t('messageCount'), value: String(messages.length) },
      { label: t('recommendedCompanies'), value: String(recommendedCount) }
    ],
    [conversations.length, messages.length, recommendedCount, t, user.phone, user.username]
  );

  return (
    <div className={`tool-layout tool-layout--chat${railCollapsed ? ' is-rail-collapsed' : ''}`}>
      <aside className="panel tool-history">
        <div className="tool-panel__head">
          <div>
            <span className="page-eyebrow">{t('historyEyebrow')}</span>
            <h2 className="card-title">{t('historyTitle')}</h2>
          </div>
        </div>
        <div className="tool-history__list">
          {conversations.length ? (
            conversations.map((conversation) => (
              <button
                key={conversation.id}
                className={`tool-history__item${conversation.id === activeConversationId ? ' is-active' : ''}`}
                type="button"
                onClick={() => setActiveConversationId(conversation.id)}
              >
                <strong>{conversation.title}</strong>
                <span>{formatDateTime(conversation.updated_at, locale)}</span>
              </button>
            ))
          ) : (
            <div className="tool-empty-state">{t('noHistory')}</div>
          )}
        </div>
      </aside>

      <div className="tool-main">
        <section className="panel tool-panel">
          <div className="tool-panel__head">
            <div>
              <span className="page-eyebrow">{t('eyebrow')}</span>
              <h1 className="page-title">{t('title')}</h1>
              <p className="page-subtitle">{t('subtitle')}</p>
            </div>
            <button
              className="tool-button tool-button--ghost"
              type="button"
              onClick={() => setRailCollapsed((current) => !current)}
            >
              {railCollapsed ? t('expandRail') : t('collapseRail')}
            </button>
          </div>
        </section>

        <section className="panel tool-chat">
          <div className="chat-thread">
            {messages.length ? (
              messages.map((message) => (
                <div key={message.id} className={`chat-bubble chat-bubble--${message.role}`}>
                  <div className="chat-bubble__meta">
                    <span>{message.role === 'assistant' ? t('agent') : t('you')}</span>
                    <span>{formatDateTime(message.created_at, locale)}</span>
                  </div>
                  <div className="chat-bubble__content">{message.content || (streaming ? '...' : '')}</div>
                </div>
              ))
            ) : (
              <div className="tool-empty-state">
                {t('emptyThread')}
              </div>
            )}
          </div>

          {followups.length ? (
            <div className="tool-chip-row">
              {followups.map((item) => (
                <button
                  key={item.label}
                  className="tool-chip"
                  type="button"
                  onClick={() => sendMessage(item.prompt)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ) : null}

          <form
            className="tool-form tool-form--chat"
            onSubmit={(event) => {
              event.preventDefault();
              sendMessage(input);
            }}
          >
            <textarea
              className="tool-textarea tool-textarea--compact"
              placeholder={t('inputPlaceholder')}
              value={input}
              onChange={(event) => setInput(event.target.value)}
            />
            <div className="tool-form__row tool-form__row--between">
              <div className="tool-inline-copy">
                <span>{t('streaming')}</span>
                <span>{t('relatedFollowups')}</span>
              </div>
              <button className="tool-button tool-button--primary" disabled={streaming} type="submit">
                {streaming ? t('generating') : t('send')}
              </button>
            </div>
            {error ? <p className="tool-error">{error}</p> : null}
          </form>
        </section>
      </div>

      <aside className={`panel tool-sidebar${railCollapsed ? ' is-hidden' : ''}`}>
        <div className="tool-panel__head">
          <div>
            <span className="page-eyebrow">{t('sidebarEyebrow')}</span>
            <h2 className="card-title">{t('sidebarTitle')}</h2>
          </div>
        </div>
        <div className="compact-list">
          {contextMeta.map((item) => (
            <div key={item.label} className="compact-list__item">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}

export function SolutionsWorkbench({ locale, initialConversationId }: SolutionsWorkbenchProps) {
  const t = useTranslations('web.solutions');
  return (
    <SessionGuard
      locale={locale}
      title={t('guardTitle')}
      description={t('guardDescription')}
    >
      {({ token, user }) => (
        <SolutionsWorkbenchInner
          initialConversationId={initialConversationId}
          locale={locale}
          token={token}
          user={user}
        />
      )}
    </SessionGuard>
  );
}
