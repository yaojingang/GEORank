import type { TutorialNavGroup } from '@georank/api-sdk';
import { localizeHref } from '@georank/i18n/routing';
import { getTranslations } from 'next-intl/server';

type TutorialChannelProps = {
  locale: string;
  groups: TutorialNavGroup[];
};

const CATEGORY_ICONS: Record<string, string> = {
  ['GEO\u8ba4\u77e5']: 'travel_explore',
  ['AI\u539f\u7406']: 'neurology',
  ['\u5185\u5bb9\u4f18\u5316']: 'edit_note',
  ['\u9875\u9762\u6280\u672f']: 'code_blocks',
  ['\u7b56\u7565\u6267\u884c']: 'conversion_path',
  ['\u8bc4\u4f30\u6cbb\u7406']: 'query_stats',
  ['\u5b9e\u6218\u6848\u4f8b']: 'folder_managed'
};

export async function TutorialChannel({ locale, groups }: TutorialChannelProps) {
  const t = await getTranslations({locale, namespace: 'web.tutorialChannel'});
  const units = await getTranslations({locale, namespace: 'common.units'});
  const totalArticles = groups.reduce((sum, group) => sum + group.items.length, 0);
  const totalMinutes = groups.reduce(
    (sum, group) => sum + group.items.reduce((inner, item) => inner + Number(item.reading_time_minutes || 0), 0),
    0
  );

  return (
    <main className="page-wrap doc-page">
      <div className="doc-layout doc-layout--tutorial">
        <aside className="doc-sidebar doc-sidebar--left doc-sticky">
          <div className="doc-sidebar__intro">
            <p className="doc-sidebar__eyebrow">{t('sidebarEyebrow')}</p>
            <h2 className="doc-sidebar__title">{t('sidebarTitle')}</h2>
            <p className="doc-sidebar__copy">{t('sidebarCopy')}</p>
          </div>
          <nav className="doc-nav">
            {groups.map((group) => (
              <a key={group.category} className="doc-nav__group-link" href={`#group-${encodeURIComponent(group.category)}`}>
                <span className="material-symbols-outlined doc-nav__icon">
                  {CATEGORY_ICONS[group.category] || 'library_books'}
                </span>
                <span className="doc-nav__group-copy">
                  <strong>{group.category}</strong>
                  <span>{units('articleCount', {count: group.items.length})}</span>
                </span>
              </a>
            ))}
          </nav>
        </aside>

        <div className="doc-main">
          <section className="doc-hero-card">
            <div className="doc-hero-card__main">
              <span className="page-eyebrow">{t('heroEyebrow')}</span>
              <h1 className="page-title">{t('title')}</h1>
              <p className="page-subtitle">{t('subtitle')}</p>
            </div>
            <div className="doc-hero-card__stats">
              <div className="doc-stat-card">
                <span className="material-symbols-outlined">menu_book</span>
                <div>
                  <strong>{totalArticles}</strong>
                  <span>{t('publishedTutorials')}</span>
                </div>
              </div>
              <div className="doc-stat-card">
                <span className="material-symbols-outlined">schedule</span>
                <div>
                  <strong>{totalMinutes || '--'}</strong>
                  <span>{t('totalMinutes')}</span>
                </div>
              </div>
              <div className="doc-stat-card">
                <span className="material-symbols-outlined">layers</span>
                <div>
                  <strong>{groups.length}</strong>
                  <span>{t('chapterStructure')}</span>
                </div>
              </div>
            </div>
          </section>

          <div className="tutorial-group-stack">
            {groups.map((group, groupIndex) => (
              <section
                id={`group-${encodeURIComponent(group.category)}`}
                key={group.category}
                className="doc-panel tutorial-group-panel"
              >
                <div className="tutorial-group-panel__header">
                  <div>
                    <span className="page-eyebrow">{t('chapter', {index: String(groupIndex + 1).padStart(2, '0')})}</span>
                    <h2 className="card-title">{group.category}</h2>
                    <p className="card-subtitle">{t('groupCopy', {category: group.category})}</p>
                  </div>
                  <span className="tutorial-group-panel__count">{units('articleCount', {count: group.items.length})}</span>
                </div>
                <div className="tutorial-card-grid">
                  {group.items.map((item) => (
                    <a
                      key={item.path_key || item.slug}
                      className="tutorial-card"
                      href={localizeHref(locale, `/tutorial/${item.path_key || item.slug}`)}
                    >
                      <div className="tutorial-card__meta">
                        <span>{group.category}</span>
                        <span>{item.reading_time_minutes ? units('minutes', {count: item.reading_time_minutes}) : t('readingDetail')}</span>
                      </div>
                      <h3 className="tutorial-card__title">{item.title}</h3>
                      <p className="tutorial-card__copy">
                        {t('cardCopy', {title: item.title})}
                      </p>
                      <span className="tutorial-card__cta">{t('openDetail')}</span>
                    </a>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </div>

        <aside className="doc-sidebar doc-sidebar--right doc-sticky">
          <div className="doc-sidebar__intro">
            <p className="doc-sidebar__eyebrow">{t('indexEyebrow')}</p>
            <h2 className="doc-sidebar__title">{t('indexTitle')}</h2>
          </div>
          <nav className="doc-toc">
            {groups.map((group, index) => (
              <a key={group.category} className="doc-toc__link" href={`#group-${encodeURIComponent(group.category)}`}>
                <span className="doc-toc__index">{index + 1}</span>
                <span>{group.category}</span>
              </a>
            ))}
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
