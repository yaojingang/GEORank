'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {useTranslations} from 'next-intl';

import type { DiagnosticHistoryItem, DiagnosticReportResponse } from '@georank/api-sdk';
import { getDiagnosticReport, listDiagnosticHistory, startDiagnosis } from '@georank/api-sdk';

import { SessionGuard } from '../auth/session-guard';

type DiagnosticWorkbenchProps = {
  locale: string;
  initialReportId?: string;
};

function normalizeUrlInput(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

function formatDateTime(value?: string | null, locale = 'zh-CN') {
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

function toScore(value: unknown) {
  if (typeof value === 'number') return Math.round(value);
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if (typeof record.score === 'number') return Math.round(record.score);
    const candidate = Object.values(record).find(
      (item) => typeof item === 'number' && item >= 0 && item <= 100
    );
    if (typeof candidate === 'number') return Math.round(candidate);
  }
  return null;
}

function extractHighlights(block: unknown) {
  if (!block || typeof block !== 'object') return [];
  const record = block as Record<string, unknown>;
  return Object.entries(record)
    .filter(([, value]) => typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean')
    .slice(0, 4)
    .map(([key, value]) => ({
      label: key,
      value: String(value)
    }));
}

function buildRecommendationGroups(
  recommendations: Record<string, unknown> | null | undefined,
  titles: Record<'urgent' | 'recommended' | 'optional', string>
) {
  if (!recommendations) return [];
  const groups = [
    { key: 'urgent', title: titles.urgent },
    { key: 'recommended', title: titles.recommended },
    { key: 'optional', title: titles.optional }
  ];

  return groups
    .map((group) => ({
      ...group,
      items: Array.isArray(recommendations[group.key]) ? (recommendations[group.key] as Array<Record<string, unknown>>) : []
    }))
    .filter((group) => group.items.length);
}

function DiagnosticWorkbenchInner({
  locale,
  token,
  initialReportId
}: {
  locale: string;
  token: string;
  initialReportId?: string;
}) {
  const t = useTranslations('web.diagnostic');
  const [url, setUrl] = useState('');
  const [history, setHistory] = useState<DiagnosticHistoryItem[]>([]);
  const [activeReport, setActiveReport] = useState<DiagnosticReportResponse | null>(null);
  const [activeReportId, setActiveReportId] = useState(initialReportId || '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const loadHistory = useCallback(async () => {
    const nextHistory = await listDiagnosticHistory(token);
    setHistory(nextHistory);
    if (!activeReportId && nextHistory[0]) {
      setActiveReportId(nextHistory[0].report_id);
    }
  }, [activeReportId, token]);

  const loadReport = useCallback(
    async (reportId: string) => {
      const report = await getDiagnosticReport(token, reportId);
      setActiveReport(report);
      setActiveReportId(reportId);
      return report;
    },
    [token]
  );

  useEffect(() => {
    loadHistory().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : t('historyLoadFailed'));
    });
  }, [loadHistory, t]);

  useEffect(() => {
    if (!activeReportId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function refresh() {
      try {
        const report = await loadReport(activeReportId);
        if (cancelled) return;
        if (report.status === 'pending' || report.status === 'analyzing') {
          timer = setTimeout(refresh, 3000);
        } else {
          loadHistory().catch(() => undefined);
        }
      } catch (reason) {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : t('reportLoadFailed'));
        }
      }
    }

    refresh();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [activeReportId, loadHistory, loadReport, t]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedUrl = normalizeUrlInput(url);
    if (!normalizedUrl) {
      setError(t('missingUrl'));
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      const response = await startDiagnosis(token, { url: normalizedUrl });
      setUrl(normalizedUrl);
      setActiveReportId(response.report_id);
      await loadHistory();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('startFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  const scoreCards = useMemo(
    () => [
      { label: t('totalScore'), value: activeReport?.overall_score ? Math.round(activeReport.overall_score) : '--' },
      { label: 'Schema', value: toScore(activeReport?.schema_analysis) ?? '--' },
      { label: t('content'), value: toScore(activeReport?.content_analysis) ?? '--' },
      { label: 'Meta', value: toScore(activeReport?.meta_analysis) ?? '--' },
      { label: t('citation'), value: toScore(activeReport?.citation_analysis) ?? '--' }
    ],
    [activeReport, t]
  );

  const recommendationGroups = buildRecommendationGroups(activeReport?.recommendations, {
    urgent: t('groupUrgent'),
    recommended: t('groupRecommended'),
    optional: t('groupOptional')
  });
  const recommendationSummary =
    activeReport?.recommendations &&
    typeof activeReport.recommendations.summary === 'object' &&
    activeReport.recommendations.summary
      ? (activeReport.recommendations.summary as Record<string, unknown>)
      : null;

  return (
    <div className="tool-layout">
      <aside className="panel tool-history">
        <div className="tool-panel__head">
          <div>
            <span className="page-eyebrow">{t('historyEyebrow')}</span>
            <h2 className="card-title">{t('historyTitle')}</h2>
          </div>
        </div>
        <div className="tool-history__list">
          {history.length ? (
            history.map((item) => (
              <button
                key={item.report_id}
                className={`tool-history__item${item.report_id === activeReportId ? ' is-active' : ''}`}
                type="button"
                onClick={() => setActiveReportId(item.report_id)}
              >
                <strong>{item.url.replace(/^https?:\/\//, '')}</strong>
                <span>{item.status}</span>
                <small>{formatDateTime(item.created_at, locale)}</small>
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
          </div>

          <form className="tool-form" onSubmit={handleSubmit}>
            <label className="tool-label" htmlFor="diagnostic-url">
              {t('urlLabel')}
            </label>
            <div className="tool-form__row">
              <input
                id="diagnostic-url"
                className="tool-input"
                placeholder={t('urlPlaceholder')}
                value={url}
                onChange={(event) => setUrl(event.target.value)}
              />
              <button className="tool-button tool-button--primary" disabled={submitting} type="submit">
                {submitting ? t('submitting') : t('submit')}
              </button>
            </div>
            {error ? <p className="tool-error">{error}</p> : null}
          </form>
        </section>

        <section className="panel tool-panel">
          <div className="tool-panel__head">
            <div>
              <span className="page-eyebrow">{t('reportEyebrow')}</span>
              <h2 className="card-title">{activeReport ? activeReport.url : t('waitingReport')}</h2>
            </div>
            <span className="pill">{activeReport?.status || t('notLoaded')}</span>
          </div>

          {activeReport ? (
            <>
              <div className="tool-grid tool-grid--five">
                {scoreCards.map((card) => (
                  <div key={card.label} className="tool-data-card">
                    <div className="tool-data-card__label">{card.label}</div>
                    <div className="tool-data-card__value">{card.value}</div>
                  </div>
                ))}
              </div>

              {recommendationSummary ? (
                <div className="tool-grid tool-grid--three">
                  <div className="tool-data-card">
                    <div className="tool-data-card__label">{t('summaryLabel')}</div>
                    <strong>{String(recommendationSummary.headline || t('generatedSummary'))}</strong>
                    <p>{String(recommendationSummary.overview || '')}</p>
                  </div>
                  <div className="tool-data-card">
                    <div className="tool-data-card__label">{t('priorityAction')}</div>
                    <strong>{String(recommendationSummary.priority_action || t('notLoaded'))}</strong>
                  </div>
                  <div className="tool-data-card">
                    <div className="tool-data-card__label">{t('generatedAt')}</div>
                    <strong>{formatDateTime(activeReport.created_at, locale)}</strong>
                  </div>
                </div>
              ) : null}

              <div className="tool-grid tool-grid--two">
                <div className="tool-stack">
                  <section className="tool-card-surface">
                    <h3 className="tool-card-surface__title">{t('schemaSignals')}</h3>
                    <div className="compact-list">
                      {extractHighlights(activeReport.schema_analysis).map((item) => (
                        <div key={item.label} className="compact-list__item">
                          <span>{item.label}</span>
                          <strong>{item.value}</strong>
                        </div>
                      ))}
                    </div>
                  </section>
                  <section className="tool-card-surface">
                    <h3 className="tool-card-surface__title">{t('contentSignals')}</h3>
                    <div className="compact-list">
                      {extractHighlights(activeReport.content_analysis).map((item) => (
                        <div key={item.label} className="compact-list__item">
                          <span>{item.label}</span>
                          <strong>{item.value}</strong>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>

                <div className="tool-stack">
                  <section className="tool-card-surface">
                    <h3 className="tool-card-surface__title">{t('metaCitation')}</h3>
                    <div className="compact-list">
                      {[...extractHighlights(activeReport.meta_analysis), ...extractHighlights(activeReport.citation_analysis)]
                        .slice(0, 6)
                        .map((item) => (
                          <div key={item.label} className="compact-list__item">
                            <span>{item.label}</span>
                            <strong>{item.value}</strong>
                          </div>
                        ))}
                    </div>
                  </section>
                  <section className="tool-card-surface">
                    <h3 className="tool-card-surface__title">{t('recommendations')}</h3>
                    {recommendationGroups.length ? (
                      <div className="tool-stack tool-stack--tight">
                        {recommendationGroups.map((group) => (
                          <div key={group.key} className="tool-checklist">
                            <strong>{group.title}</strong>
                            <ul>
                              {group.items.map((item, index) => (
                                <li key={`${group.key}-${index}`}>
                                  {String(item.item || '')}
                                  {item.action ? `：${String(item.action)}` : ''}
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="tool-empty-state">{t('noRecommendations')}</div>
                    )}
                  </section>
                </div>
              </div>
            </>
          ) : (
            <div className="tool-empty-state">{t('emptyReport')}</div>
          )}
        </section>
      </div>
    </div>
  );
}

export function DiagnosticWorkbench({ locale, initialReportId }: DiagnosticWorkbenchProps) {
  const t = useTranslations('web.diagnostic');
  return (
    <SessionGuard
      locale={locale}
      title={t('guardTitle')}
      description={t('guardDescription')}
    >
      {({ token }) => <DiagnosticWorkbenchInner initialReportId={initialReportId} locale={locale} token={token} />}
    </SessionGuard>
  );
}
