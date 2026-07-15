'use client';

import { useState } from 'react';
import {useTranslations} from 'next-intl';

import type { KeywordDimension, KeywordExpandResponse } from '@georank/api-sdk';
import { expandKeywords } from '@georank/api-sdk';

import { SessionGuard } from '../auth/session-guard';

type KeywordsWorkbenchProps = {
  locale: string;
};

function parseSeeds(raw: string) {
  return Array.from(
    new Set(
      raw
        .split(/[\n,，]+/)
        .map((item) => item.trim())
        .filter(Boolean)
    )
  );
}

function KeywordsWorkbenchInner({ token }: { token: string }) {
  const t = useTranslations('web.keywords');
  const [rawInput, setRawInput] = useState('');
  const [result, setResult] = useState<KeywordExpandResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleExpand(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const seeds = parseSeeds(rawInput);
    if (!seeds.length) {
      setError(t('missingSeed'));
      return;
    }

    setLoading(true);
    setError('');
    try {
      const nextResult = await expandKeywords({ seeds }, token);
      setResult(nextResult);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('failed'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="tool-main">
      <section className="panel tool-panel">
        <div className="tool-panel__head">
          <div>
            <span className="page-eyebrow">{t('eyebrow')}</span>
            <h1 className="page-title">{t('title')}</h1>
            <p className="page-subtitle">{t('subtitle')}</p>
          </div>
        </div>

        <form className="tool-form" onSubmit={handleExpand}>
          <label className="tool-label" htmlFor="keyword-seeds">
            {t('seedLabel')}
          </label>
          <textarea
            id="keyword-seeds"
            className="tool-textarea"
            placeholder={t('seedPlaceholder')}
            value={rawInput}
            onChange={(event) => setRawInput(event.target.value)}
          />
          <div className="tool-form__row tool-form__row--end">
            <button className="tool-button tool-button--primary" disabled={loading} type="submit">
              {loading ? t('analyzing') : t('generate')}
            </button>
          </div>
          {error ? <p className="tool-error">{error}</p> : null}
        </form>
      </section>

      {result ? (
        <>
          <section className="tool-grid tool-grid--three">
            <div className="panel tool-panel tool-panel--compact">
              <span className="page-eyebrow">Profile</span>
              <h2 className="card-title">{t('profileTitle')}</h2>
              <div className="compact-list">
                <div className="compact-list__item">
                  <span>{t('businessType')}</span>
                  <strong>{result.profile.name}</strong>
                </div>
                <div className="compact-list__item">
                  <span>{t('companyHint')}</span>
                  <strong>{result.profile.company_hint}</strong>
                </div>
                <div className="compact-list__item">
                  <span>{t('businessModel')}</span>
                  <strong>{result.profile.business_model}</strong>
                </div>
                <div className="compact-list__item">
                  <span>{t('targetUsers')}</span>
                  <strong>{result.profile.target_users.join(' / ')}</strong>
                </div>
              </div>
            </div>
            <div className="panel tool-panel tool-panel--compact">
              <span className="page-eyebrow">Summary</span>
              <h2 className="card-title">{t('summaryTitle')}</h2>
              <div className="compact-list">
                <div className="compact-list__item">
                  <span>{t('totalKeywords')}</span>
                  <strong>{result.summary.total_keywords}</strong>
                </div>
                <div className="compact-list__item">
                  <span>{t('averageRecommendation')}</span>
                  <strong>{Math.round(result.summary.average_recommendation_score)}</strong>
                </div>
                <div className="compact-list__item">
                  <span>{t('averageBusiness')}</span>
                  <strong>{Math.round(result.summary.average_business_score)}</strong>
                </div>
                <div className="compact-list__item">
                  <span>{t('highValueRatio')}</span>
                  <strong>{Math.round(result.summary.high_business_ratio)}%</strong>
                </div>
              </div>
            </div>
            <div className="panel tool-panel tool-panel--compact">
              <span className="page-eyebrow">Strategy</span>
              <h2 className="card-title">{t('strategyTitle')}</h2>
              <p className="card-subtitle">{result.profile.keyword_strategy}</p>
            </div>
          </section>

          <section className="tool-grid tool-grid--two">
            {result.dimensions.map((dimension) => (
              <KeywordDimensionPanel dimension={dimension} key={dimension.key} />
            ))}
          </section>
        </>
      ) : (
        <section className="panel tool-panel">
          <div className="tool-empty-state">
            {t('emptyResult')}
          </div>
        </section>
      )}
    </div>
  );
}

function KeywordDimensionPanel({ dimension }: { dimension: KeywordDimension }) {
  const t = useTranslations('web.keywords');
  const units = useTranslations('common.units');
  return (
    <section className="panel tool-panel tool-panel--compact">
      <div className="tool-panel__head">
        <div>
          <span className="page-eyebrow">{dimension.key}</span>
          <h2 className="card-title">{dimension.name}</h2>
          <p className="card-subtitle">{dimension.description}</p>
        </div>
        <span className="pill">{units('wordCount', {count: dimension.count})}</span>
      </div>
      <div className="compact-list">
        {dimension.items.slice(0, 6).map((item) => (
          <div key={`${dimension.key}-${item.keyword}`} className="compact-list__item compact-list__item--stack">
            <div className="tool-inline-copy">
              <strong>{item.keyword}</strong>
              <span>{t('recommendationScore', {score: item.recommendation_score})}</span>
              <span>{t('businessScore', {score: item.business_score})}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function KeywordsWorkbench({ locale }: KeywordsWorkbenchProps) {
  const t = useTranslations('web.keywords');
  return (
    <SessionGuard
      locale={locale}
      title={t('guardTitle')}
      description={t('guardDescription')}
    >
      {({ token }) => <KeywordsWorkbenchInner token={token} />}
    </SessionGuard>
  );
}
