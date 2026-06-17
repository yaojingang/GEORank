'use client';

import {useMemo, useState} from 'react';
import {useTranslations} from 'next-intl';

import type {KeywordDimension, KeywordExpandResponse} from '@georank/api-sdk';
import {expandKeywords} from '@georank/api-sdk';

type AdminKeywordsProps = {
  token: string;
};

function parseSeeds(input: string) {
  return input
    .split(/[\n,，]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function AdminKeywords({token}: AdminKeywordsProps) {
  const t = useTranslations('admin.keywords');
  const units = useTranslations('common.units');
  const [input, setInput] = useState(t('defaultSeed'));
  const [result, setResult] = useState<KeywordExpandResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const topStats = useMemo(() => {
    if (!result) {
      return [
        {label: t('profileLabel'), value: t('notGenerated'), tone: 'neutral'},
        {label: t('averageRecommendation'), value: '—', tone: 'brand'},
        {label: t('averageBusiness'), value: '—', tone: 'warning'},
        {label: t('dimensionCount'), value: '8', tone: 'success'}
      ];
    }

    return [
      {label: t('profileLabel'), value: result.profile.name, tone: 'brand'},
      {
        label: t('averageRecommendation'),
        value: `${Math.round(result.summary.average_recommendation_score)}`,
        tone: 'brand'
      },
      {
        label: t('averageBusiness'),
        value: `${Math.round(result.summary.average_business_score)}`,
        tone: 'warning'
      },
      {label: t('dimensionCount'), value: `${result.dimensions.length}`, tone: 'success'}
    ];
  }, [result, t]);

  async function handleExpand() {
    const seeds = parseSeeds(input);
    if (seeds.length === 0) {
      setError(t('missingSeed'));
      return;
    }

    setLoading(true);
    setError('');
    try {
      const payload = await expandKeywords({seeds}, token);
      setResult(payload);
    } catch (loadError: unknown) {
      setError(loadError instanceof Error ? loadError.message : t('failed'));
    } finally {
      setLoading(false);
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
        <div className="admin-page__hero-chip">{t('flowChip')}</div>
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
        <div className="admin-panel__header">
          <div>
            <p className="admin-panel__eyebrow">Workbench</p>
            <h2>{t('workbenchTitle')}</h2>
          </div>
        </div>

        <div className="admin-form-stack">
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
              disabled={loading}
              onClick={handleExpand}
              type="button"
            >
              {loading ? t('generating') : t('generate')}
            </button>
          </div>
          {error ? <div className="admin-inline-error">{error}</div> : null}
        </div>
      </section>

      <section className="admin-two-column">
        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Profile</p>
              <h2>{t('profileTitle')}</h2>
            </div>
          </div>
          {!result ? (
            <p className="admin-feed__empty">{t('emptyProfile')}</p>
          ) : (
            <div className="admin-company-detail">
              <div className="admin-detail-grid admin-detail-grid--compact">
                <div className="admin-detail-card">
                  <span>{t('industryProfile')}</span>
                  <strong>{result.profile.name}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('companyHint')}</span>
                  <strong>{result.profile.company_hint}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('businessModel')}</span>
                  <strong>{result.profile.business_model}</strong>
                </div>
                <div className="admin-detail-card">
                  <span>{t('targetUsers')}</span>
                  <strong>{result.profile.target_users.join(' / ')}</strong>
                </div>
              </div>
              <div className="admin-detail-list__item">
                <strong>{t('strategy')}</strong>
                <p>{result.profile.keyword_strategy}</p>
              </div>
            </div>
          )}
        </article>

        <article className="admin-panel">
          <div className="admin-panel__header">
            <div>
              <p className="admin-panel__eyebrow">Summary</p>
              <h2>{t('summaryTitle')}</h2>
            </div>
          </div>
          {!result ? (
            <p className="admin-feed__empty">{t('emptySummary')}</p>
          ) : (
            <div className="admin-score-list">
              <div className="admin-score-row">
                <div className="admin-score-row__meta">
                  <span>{t('totalKeywords')}</span>
                  <strong>{result.summary.total_keywords}</strong>
                </div>
                <div className="admin-score-row__track">
                  <span className="admin-score-row__fill admin-tone--brand" style={{width: '100%'}} />
                </div>
              </div>
              <div className="admin-score-row">
                <div className="admin-score-row__meta">
                  <span>{t('highRecommendationRatio')}</span>
                  <strong>{Math.round(result.summary.high_recommendation_ratio * 100)}%</strong>
                </div>
                <div className="admin-score-row__track">
                  <span
                    className="admin-score-row__fill admin-tone--brand"
                    style={{width: `${Math.max(6, Math.round(result.summary.high_recommendation_ratio * 100))}%`}}
                  />
                </div>
              </div>
              <div className="admin-score-row">
                <div className="admin-score-row__meta">
                  <span>{t('highBusinessRatio')}</span>
                  <strong>{Math.round(result.summary.high_business_ratio * 100)}%</strong>
                </div>
                <div className="admin-score-row__track">
                  <span
                    className="admin-score-row__fill admin-tone--warning"
                    style={{width: `${Math.max(6, Math.round(result.summary.high_business_ratio * 100))}%`}}
                  />
                </div>
              </div>
            </div>
          )}
        </article>
      </section>

      <section className="admin-panel">
        <div className="admin-panel__header">
          <div>
            <p className="admin-panel__eyebrow">Dimensions</p>
            <h2>{t('dimensionsTitle')}</h2>
          </div>
        </div>
        {!result ? (
          <p className="admin-feed__empty">{t('emptyDimensions')}</p>
        ) : (
          <div className="admin-dimension-grid">
            {result.dimensions.map((dimension: KeywordDimension) => (
              <div className="admin-dimension-card" key={dimension.key}>
                <div className="admin-dimension-card__header">
                  <div>
                    <strong>{dimension.name}</strong>
                    <p>{dimension.description}</p>
                  </div>
                  <span className="admin-pill admin-pill--brand">{units('wordCount', {count: dimension.count})}</span>
                </div>
                <div className="admin-detail-list">
                  {dimension.items.slice(0, 6).map((item) => (
                    <div className="admin-dimension-item" key={`${dimension.key}-${item.keyword}`}>
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
        )}
      </section>
    </main>
  );
}
