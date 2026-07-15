'use client';

import {useEffect, useMemo, useState} from 'react';
import {useLocale, useTranslations} from 'next-intl';

import {getAdminDashboard, getAdminRecentFailures} from '@georank/api-sdk';
import {localizeHref} from '@georank/i18n/routing';
import {
  mergeDashboardLoadResults,
  type DashboardLoadState
} from './dashboard-load-state';

type AdminDashboardProps = {
  token: string;
  userLabel: string;
};

const pipelineMeta: Array<{key: string; labelKey: string; tone: string}> = [
  {key: 'pending_review', labelKey: 'pendingReviewCompanies', tone: 'success'},
  {key: 'failed', labelKey: 'failedCompanies', tone: 'danger'},
  {key: 'completed', labelKey: 'completedCompanies', tone: 'neutral'},
  {key: 'pending', labelKey: 'pendingPipeline', tone: 'brand'}
];

const scoreMeta: Array<{key: string; labelKey: string; tone: string}> = [
  {key: 'excellent', labelKey: 'excellent', tone: 'success'},
  {key: 'good', labelKey: 'good', tone: 'brand'},
  {key: 'average', labelKey: 'average', tone: 'warning'},
  {key: 'low', labelKey: 'low', tone: 'danger'}
];

export function AdminDashboard({token, userLabel}: AdminDashboardProps) {
  const locale = useLocale();
  const t = useTranslations('admin.dashboard');
  const actions = useTranslations('common.actions');
  const [reloadKey, setReloadKey] = useState(0);
  const [state, setState] = useState<DashboardLoadState>({
    dashboard: null,
    failures: null,
    error: '',
    loading: true
  });

  useEffect(() => {
    let active = true;

    Promise.allSettled([getAdminDashboard(token), getAdminRecentFailures(token, 6)])
      .then(([dashboardResult, failuresResult]) => {
        if (!active) return;
        setState((current) =>
          mergeDashboardLoadResults(current, dashboardResult, failuresResult, t('loadFailed'))
        );
      });

    return () => {
      active = false;
    };
  }, [token, t, reloadKey]);

  const topStats = useMemo(() => {
    if (!state.dashboard) return [];
    return [
      {label: t('totalCompanies'), value: state.dashboard.total_companies, tone: 'brand'},
      {label: t('totalDiagnostics'), value: state.dashboard.total_diagnostics, tone: 'warning'},
      {label: t('totalSolutions'), value: state.dashboard.total_solutions, tone: 'success'},
      {label: t('keywordDimensions'), value: 8, tone: 'brand'},
      {label: t('totalContents'), value: state.dashboard.total_contents, tone: 'warning'}
    ];
  }, [state.dashboard, t]);

  if (state.loading) {
    return (
      <main className="admin-page">
        <section className="admin-page__hero">
          <div>
            <p className="admin-page__eyebrow">Dashboard</p>
            <h1>{t('loadingTitle')}</h1>
            <p>{t('loadingCopy')}</p>
          </div>
        </section>
      </main>
    );
  }

  if (!state.dashboard) {
    return (
      <main className="admin-page">
        <div className="admin-empty-state">
          <p className="admin-eyebrow">Dashboard</p>
          <h1>{t('errorTitle')}</h1>
          <p>{state.error || t('noData')}</p>
          <button
            className="admin-button admin-button--primary"
            onClick={() => setReloadKey((current) => current + 1)}
            type="button"
          >
            {actions('retry')}
          </button>
        </div>
      </main>
    );
  }

  const dashboard = state.dashboard;
  const failures = state.failures;

  return (
    <main className="admin-page">
      <section className="admin-page__hero">
        <div>
          <p className="admin-page__eyebrow">Dashboard</p>
          <h1>{t('title')}</h1>
          <p>{t('subtitle')}</p>
        </div>
        <div className="admin-page__hero-chip">{t('currentAdmin', {userLabel})}</div>
      </section>

      <section className="admin-stat-grid">
        {topStats.map((stat) => (
          <article className="admin-stat-card" key={stat.label}>
            <p className="admin-stat-card__label">{stat.label}</p>
            <div className={`admin-stat-card__value admin-tone--${stat.tone}`}>{stat.value}</div>
          </article>
        ))}
      </section>

      {state.error ? (
        <div className="admin-inline-error">
          <span>{state.error}</span>{' '}
          <button
            className="admin-button admin-button--ghost admin-button--small"
            onClick={() => setReloadKey((current) => current + 1)}
            type="button"
          >
            {actions('retry')}
          </button>
        </div>
      ) : null}

      <section className="admin-content-grid admin-content-grid--dashboard">
        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Priority</p>
              <h2>{t('priorityTitle')}</h2>
            </div>
            <span className="admin-pill admin-pill--brand">{t('liveData')}</span>
          </div>
          <div className="admin-queue-grid">
            <a className="admin-queue-card" href={localizeHref(locale, '/companies')}>
              <span className="admin-queue-card__title">{t('companiesTitle')}</span>
              <strong>{dashboard.pipeline_stats.pending_review || 0}</strong>
              <p>{t('companiesCopy')}</p>
            </a>
            <a className="admin-queue-card" href={localizeHref(locale, '/diagnostics')}>
              <span className="admin-queue-card__title">{t('diagnosticsTitle')}</span>
              <strong>{dashboard.failure_stats.failed_diagnostics || 0}</strong>
              <p>{t('diagnosticsCopy')}</p>
            </a>
            <a className="admin-queue-card" href={localizeHref(locale, '/solutions')}>
              <span className="admin-queue-card__title">{t('solutionsTitle')}</span>
              <strong>{dashboard.total_solutions || 0}</strong>
              <p>{t('solutionsCopy')}</p>
            </a>
            <a className="admin-queue-card" href={localizeHref(locale, '/keywords')}>
              <span className="admin-queue-card__title">{t('keywordsTitle')}</span>
              <strong>8</strong>
              <p>{t('keywordsCopy')}</p>
            </a>
            <a className="admin-queue-card" href={localizeHref(locale, '/tutorials')}>
              <span className="admin-queue-card__title">{t('tutorialsTitle')}</span>
              <strong>{dashboard.total_contents || 0}</strong>
              <p>{t('tutorialsCopy')}</p>
            </a>
          </div>
        </article>

        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Distribution</p>
              <h2>{t('geoDistribution')}</h2>
            </div>
          </div>
          <div className="admin-score-list">
            {scoreMeta.map((item) => {
              const value = dashboard.geo_distribution?.[item.key] || 0;
              return (
                <div className="admin-score-row" key={item.key}>
                  <div className="admin-score-row__meta">
                    <span>{t(item.labelKey)}</span>
                    <strong>{value}%</strong>
                  </div>
                  <div className="admin-score-row__track">
                    <span
                      className={`admin-score-row__fill admin-tone--${item.tone}`}
                      style={{width: `${Math.max(4, value)}%`}}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </article>
      </section>

      <section className="admin-content-grid admin-content-grid--dashboard">
        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Pipeline</p>
              <h2>{t('pipelineTitle')}</h2>
            </div>
          </div>
          <div className="admin-kpi-list">
            {pipelineMeta.map((item) => (
              <div className="admin-kpi-card" key={item.key}>
                <div className="admin-kpi-card__label">{t(item.labelKey)}</div>
                <div className={`admin-kpi-card__value admin-tone--${item.tone}`}>
                  {dashboard.pipeline_stats[item.key] || 0}
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Ops</p>
              <h2>{t('failuresTitle')}</h2>
            </div>
          </div>
          <div className="admin-feed">
            {!failures ? (
              <p className="admin-feed__empty">{t('loadFailed')}</p>
            ) : failures.companies.length === 0 && failures.diagnostics.length === 0 ? (
              <p className="admin-feed__empty">{t('noFailures')}</p>
            ) : (
              <>
                {failures.companies.map((item) => (
                  <div className="admin-feed__item" key={`company-${item.id}`}>
                    <div>
                      <strong>{item.name || t('unnamedCompany')}</strong>
                      <p>{item.pipeline_error || t('companyFailure')}</p>
                    </div>
                    <span className="admin-pill admin-pill--danger">{t('companyBadge')}</span>
                  </div>
                ))}
                {failures.diagnostics.map((item) => (
                  <div className="admin-feed__item" key={`diagnostic-${item.id}`}>
                    <div>
                      <strong>{item.url}</strong>
                      <p>{item.error_message || t('diagnosticFailure')}</p>
                    </div>
                    <span className="admin-pill admin-pill--warning">{t('diagnosticBadge')}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        </article>
      </section>
    </main>
  );
}
