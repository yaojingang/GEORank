import type { TutorialDetail, TutorialNavGroup } from '@georank/api-sdk';
import { localizeHref } from '@georank/i18n/routing';
import { getTranslations } from 'next-intl/server';

import {
  decorateTutorialHtml,
  extractTutorialSummary,
  findTutorialNeighbors,
  flattenTutorialNav,
  formatTutorialDate,
  getTutorialCategory
} from '../../lib/tutorials';

type TutorialDetailProps = {
  locale: string;
  article: TutorialDetail;
  groups: TutorialNavGroup[];
};

export async function TutorialDetailView({ locale, article, groups }: TutorialDetailProps) {
  const t = await getTranslations({locale, namespace: 'web.tutorialDetail'});
  const units = await getTranslations({locale, namespace: 'common.units'});
  const currentIdentifier = article.path_key || article.slug;
  const flatItems = flattenTutorialNav(locale, groups);
  const { previous, next } = findTutorialNeighbors(flatItems, currentIdentifier);
  const category = getTutorialCategory(groups, currentIdentifier, t('categoryFallback'));
  const { html, headings } = decorateTutorialHtml(article.html_body);
  const overview = extractTutorialSummary(article, t('summaryFallback'));

  return (
    <main className="page-wrap doc-page">
      <div className="doc-layout doc-layout--tutorial">
        <aside className="doc-sidebar doc-sidebar--left doc-sticky">
          <div className="doc-sidebar__intro">
            <p className="doc-sidebar__eyebrow">{t('sidebarEyebrow')}</p>
            <h2 className="doc-sidebar__title">{category}</h2>
            <p className="doc-sidebar__copy">{t('sidebarCopy')}</p>
          </div>

          <div className="doc-nav doc-nav--grouped">
            {groups.map((group) => (
              <section key={group.category} className="doc-nav__group">
                <div className="doc-nav__group-title">{group.category}</div>
                <div className="doc-nav__group-items">
                  {group.items.map((item) => {
                    const href = localizeHref(locale, `/tutorial/${item.path_key || item.slug}`);
                    const active = (item.path_key || item.slug) === currentIdentifier;
                    return (
                      <a
                        key={href}
                        className={`doc-nav__item${active ? ' is-active' : ''}`}
                        href={href}
                      >
                        {item.title}
                      </a>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        </aside>

        <div className="doc-main">
          <article className="doc-article-card">
            <nav className="doc-breadcrumb">
              <a href={localizeHref(locale, '/')}>{t('breadcrumbHome')}</a>
              <span>›</span>
              <a href={localizeHref(locale, '/tutorial')}>{t('breadcrumbTutorial')}</a>
              <span>›</span>
              <span>{article.title}</span>
            </nav>

            <header className="doc-article-header">
              <span className="page-eyebrow">{category}</span>
              <h1 className="page-title">{article.title}</h1>
              <p className="page-subtitle">{overview}</p>
              <div className="doc-article-meta">
                <span className="pill">{article.reading_time_minutes ? units('minutes', {count: article.reading_time_minutes}) : t('fallbackType')}</span>
                <span className="pill">{t('updatedAt', {date: formatTutorialDate(article.updated_at || article.created_at, locale)})}</span>
                {(article.tags || []).slice(0, 4).map((tag) => (
                  <span key={String(tag)} className="pill">
                    {String(tag)}
                  </span>
                ))}
              </div>
            </header>

            <div className="article-body article-body--doc" dangerouslySetInnerHTML={{ __html: html || t('emptyBody') }} />

            <nav className="article-nav article-nav--doc">
              {previous ? (
                <a className="article-nav__card" href={previous.href}>
                  <span className="article-nav__label">{t('previous')}</span>
                  {previous.title}
                </a>
              ) : (
                <div className="article-nav__card is-muted">
                  <span className="article-nav__label">{t('previous')}</span>
                  {t('firstArticle')}
                </div>
              )}
              {next ? (
                <a className="article-nav__card" href={next.href}>
                  <span className="article-nav__label">{t('next')}</span>
                  {next.title}
                </a>
              ) : (
                <div className="article-nav__card is-muted">
                  <span className="article-nav__label">{t('next')}</span>
                  {t('lastArticle')}
                </div>
              )}
            </nav>
          </article>
        </div>

        <aside className="doc-sidebar doc-sidebar--right doc-sticky">
          <div className="doc-sidebar__intro">
            <p className="doc-sidebar__eyebrow">{t('tocEyebrow')}</p>
            <h2 className="doc-sidebar__title">{t('tocTitle')}</h2>
          </div>
          <nav className="doc-toc">
            {headings.length ? (
              headings.map((heading) => (
                <a
                  key={heading.id}
                  className={`doc-toc__line${heading.level === 'h3' ? ' is-child' : ''}`}
                  href={`#${heading.id}`}
                >
                  {heading.title}
                </a>
              ))
            ) : (
              <div className="doc-toc__empty">{t('tocEmpty')}</div>
            )}
          </nav>
          <div className="doc-sidebar__cta">
            <h3>{t('ctaTitle')}</h3>
            <p>{t('ctaCopy')}</p>
            <a href={localizeHref(locale, '/solutions')}>{t('ctaLink')}</a>
          </div>
        </aside>
      </div>
    </main>
  );
}
