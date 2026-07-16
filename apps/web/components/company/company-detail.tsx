import type { CompanyDetail, SimilarCompanyItem } from '@georank/api-sdk';
import { localizeHref } from '@georank/i18n/routing';
import { getTranslations } from 'next-intl/server';

import {
  asStringList,
  deriveCompanySignals,
  formatCompanyDate,
  getCompanyOverview,
  normalizeGeoDetails
} from '../../lib/companies';

type CompanyDetailProps = {
  locale: string;
  company: CompanyDetail;
  similarCompanies: SimilarCompanyItem[];
};

export async function CompanyDetailView({ locale, company, similarCompanies }: CompanyDetailProps) {
  const t = await getTranslations({locale, namespace: 'web.companyDetail'});
  const fallback = await getTranslations({locale, namespace: 'common.fallback'});
  const tags = asStringList(company.tags).slice(0, 8);
  const techStack = asStringList(company.tech_stack);
  const teamMembers = asStringList(company.team_members);
  const details = normalizeGeoDetails(company);
  const averageScore = Math.round(
    details.reduce((sum, item) => sum + item.value, 0) / Math.max(details.length, 1)
  );
  const strongest = [...details].sort((a, b) => b.value - a.value)[0];
  const weakest = [...details].sort((a, b) => a.value - b.value)[0];
  const overview = getCompanyOverview(company, t('overviewFallback'));
  const signals = deriveCompanySignals(company, {
    technicalSemantic: t('signalTechnical'),
    regionalSignal: t('signalRegional'),
    teamSignal: t('signalTeam'),
    topicCoverage: t('signalTopic'),
    notProvided: fallback('notProvided'),
    needsEnhancement: t('needsEnhancement'),
    publicEntities: (count) => t('publicEntities', {count}),
    semanticTagCount: (count) => t('semanticTagCount', {count})
  });

  return (
    <main className="page-wrap company-page">
      <nav className="doc-breadcrumb doc-breadcrumb--company">
        <a href={localizeHref(locale, '/')}>{t('breadcrumbHome')}</a>
        <span>›</span>
        <a href={localizeHref(locale, '/companies')}>{t('breadcrumbCompanies')}</a>
        <span>›</span>
        <span>{company.name}</span>
      </nav>

      <section className="company-hero-grid">
        <article className="company-hero-card">
          <div className="company-hero-card__top">
            <div className="company-logo-box">
              {/* Company logos use arbitrary audited domains; next/image requires an enumerated allowlist. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {company.logo_url ? <img alt={company.name} src={company.logo_url} /> : <span>{company.name.slice(0, 1)}</span>}
            </div>
            <div className="company-hero-copy">
              <span className="page-eyebrow">{company.category || 'Company Profile'}</span>
              <h1 className="page-title company-hero-title">{company.name}</h1>
              <p className="company-hero-domain">{company.url}</p>
              <p className="company-hero-description">{overview}</p>
            </div>
          </div>

          <div className="company-hero-facts">
            <div className="company-fact-card">
              <span>{t('location')}</span>
              <strong>{company.headquarters || fallback('notProvided')}</strong>
            </div>
            <div className="company-fact-card">
              <span>{t('founded')}</span>
              <strong>{formatCompanyDate(company.founded_date)}</strong>
            </div>
            <div className="company-fact-card">
              <span>{t('employees')}</span>
              <strong>{company.employee_count || fallback('unknown')}</strong>
            </div>
            <div className="company-fact-card">
              <span>{t('techLevel')}</span>
              <strong>{company.tech_level || fallback('notEvaluated')}</strong>
            </div>
          </div>

          <div className="company-tag-row">
            {tags.length ? (
              tags.map((tag) => (
                <span key={tag} className="pill">
                  {tag}
                </span>
              ))
            ) : (
              <span className="pill">{t('noTags')}</span>
            )}
          </div>

          <div className="company-cta-row">
            <a className="company-cta company-cta--primary" href={company.url} rel="noreferrer" target="_blank">
              {t('visitWebsite')}
            </a>
            <a className="company-cta company-cta--secondary" href={localizeHref(locale, '/diagnostic')}>
              {t('startDiagnostic')}
            </a>
          </div>
        </article>

        <aside className="company-snapshot-card">
          <div className="company-snapshot-card__head">
            <div>
              <span className="page-eyebrow">Snapshot</span>
              <h2 className="card-title">{t('snapshotTitle')}</h2>
            </div>
            <div className="company-score-ring">
              <strong>{Number(company.geo_score || 0).toFixed(1)}</strong>
              <span>GEO SCORE</span>
            </div>
          </div>

          <div className="company-snapshot-grid">
            <div className="compact-list__item"><span>{t('knowledgeStatus')}</span><strong>{company.pipeline_status}</strong></div>
            <div className="compact-list__item"><span>{t('publishStatus')}</span><strong>{company.publish_status}</strong></div>
            <div className="compact-list__item"><span>{t('fundingStage')}</span><strong>{company.funding_stage || fallback('notProvided')}</strong></div>
            <div className="compact-list__item"><span>{t('geoCertification')}</span><strong>{company.is_geo_certified ? t('certified') : t('notCertified')}</strong></div>
          </div>
        </aside>
      </section>

      <div className="company-section-grid">
        <section className="doc-panel company-section-card">
          <div className="company-section-card__head">
            <div>
              <span className="page-eyebrow">Executive Summary</span>
              <h2 className="card-title">{t('summaryTitle')}</h2>
            </div>
          </div>
          <div className="company-summary-layout">
            <div className="company-summary-copy">
              <p>{overview}</p>
              <p>{t('summaryNote')}</p>
            </div>
            <div className="company-summary-metrics">
              <div className="company-mini-card"><span>{t('crawledPages')}</span><strong>{company.pipeline_status === 'completed' ? '3' : '--'}</strong></div>
              <div className="company-mini-card"><span>{t('semanticTags')}</span><strong>{tags.length || 0}</strong></div>
              <div className="company-mini-card"><span>{t('technicalTopics')}</span><strong>{techStack.length || 0}</strong></div>
              <div className="company-mini-card"><span>{t('teamNodes')}</span><strong>{teamMembers.length || 0}</strong></div>
            </div>
          </div>
        </section>

        <section className="doc-panel company-section-card">
          <div className="company-section-card__head">
            <div>
              <span className="page-eyebrow">Readability</span>
              <h2 className="card-title">{t('readabilityTitle')}</h2>
            </div>
          </div>
          <div className="company-readability-list">
            <div className="compact-list__item"><span>{t('brandName')}</span><strong>{company.name}</strong></div>
            <div className="compact-list__item"><span>{t('descriptionCoverage')}</span><strong>{company.description ? t('complete') : fallback('notProvided')}</strong></div>
            <div className="compact-list__item"><span>{t('technicalSemantics')}</span><strong>{techStack.length ? t('outputToPage') : t('needsEnhancement')}</strong></div>
            <div className="compact-list__item"><span>{t('structuredGeo')}</span><strong>{company.geo_score != null ? t('output') : fallback('notProvided')}</strong></div>
          </div>
        </section>

        <section className="doc-panel company-section-card">
          <div className="company-section-card__head">
            <div>
              <span className="page-eyebrow">Score Dashboard</span>
              <h2 className="card-title">{t('scoreTitle')}</h2>
            </div>
          </div>
          <div className="company-score-dashboard">
            <div className="company-score-bars">
              {details.map((detail) => (
                <div key={detail.key} className="company-score-bar">
                  <div className="company-score-bar__head">
                    <span>{detail.label}</span>
                    <strong>{detail.value}</strong>
                  </div>
                  <div className="company-score-bar__track">
                    <span className="company-score-bar__fill" style={{ width: `${detail.value}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <div className="company-score-insights">
              <div className="company-mini-card"><span>{t('averageScore')}</span><strong>{averageScore}</strong></div>
              <div className="company-mini-card"><span>{t('strongest')}</span><strong>{strongest.label}</strong></div>
              <div className="company-mini-card"><span>{t('weakest')}</span><strong>{weakest.label}</strong></div>
              <div className="company-insight-card">
                <span>{t('priorityAction')}</span>
                <p>{t('priorityActionText', {label: weakest.label})}</p>
              </div>
            </div>
          </div>
        </section>

        <section className="doc-panel company-section-card">
          <div className="company-section-card__head">
            <div>
              <span className="page-eyebrow">Signals</span>
              <h2 className="card-title">{t('signalsTitle')}</h2>
            </div>
          </div>
          <div className="company-signal-grid">
            {signals.map((signal) => (
              <div key={signal.label} className={`company-signal-card ${signal.accent}`}>
                <span>{signal.label}</span>
                <strong>{signal.value}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="doc-panel company-section-card">
          <div className="company-section-card__head">
            <div>
              <span className="page-eyebrow">Organization</span>
              <h2 className="card-title">{t('organizationTitle')}</h2>
            </div>
          </div>
          <div className="company-team-layout">
            <div className="company-insight-card">
              <span>{t('organizationInfo')}</span>
              <p>
                {teamMembers.length
                  ? t('organizationFound', {count: teamMembers.length})
                  : t('organizationMissing')}
              </p>
            </div>
            <div className="company-insight-card">
              <span>{t('recommendedAction')}</span>
              <p>{t('recommendedActionText')}</p>
            </div>
          </div>
        </section>

        <section className="doc-panel company-section-card">
          <div className="company-section-card__head">
            <div>
              <span className="page-eyebrow">Recommended</span>
              <h2 className="card-title">{t('similarTitle')}</h2>
            </div>
          </div>
          <div className="company-related-list">
            {similarCompanies.length ? (
              similarCompanies.map((item) => (
                <a
                  key={item.id}
                  className="company-related-card"
                  href={localizeHref(locale, `/companies/${item.path_key || item.id}`)}
                >
                  <div>
                    <strong>{item.name}</strong>
                    <p>{item.short_description || t('similarFallback')}</p>
                  </div>
                  <span>{item.geo_score ? `GEO ${item.geo_score}` : item.category || t('similarFallback')}</span>
                </a>
              ))
            ) : (
              <div className="doc-empty-state">{t('similarEmpty')}</div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
