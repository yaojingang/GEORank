import type { TutorialDetail, TutorialNavGroup, TutorialNavItem } from '@georank/api-sdk';
import { localizeHref } from '@georank/i18n/routing';

export type FlattenedTutorialNavItem = TutorialNavItem & {
  category: string;
  href: string;
};

export type TutorialHeading = {
  id: string;
  title: string;
  level: 'h2' | 'h3';
};

function stripHtml(input: string) {
  return input
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')
    .trim();
}

function stripMarkdown(input: string) {
  return input
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^>\s?/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/_([^_]+)_/g, '$1')
    .replace(/~~([^~]+)~~/g, '$1')
    .replace(/\|/g, ' ')
    .replace(/-{3,}/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function slugify(input: string) {
  return stripHtml(input)
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fa5]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function flattenTutorialNav(locale: string, groups: TutorialNavGroup[]): FlattenedTutorialNavItem[] {
  return groups.flatMap((group) =>
    group.items.map((item) => ({
      ...item,
      category: group.category,
      href: localizeHref(locale, `/tutorial/${item.path_key || item.slug}`)
    }))
  );
}

export function findTutorialNeighbors(
  items: FlattenedTutorialNavItem[],
  currentIdentifier: string
): {
  previous: FlattenedTutorialNavItem | null;
  next: FlattenedTutorialNavItem | null;
} {
  const currentIndex = items.findIndex(
    (item) => (item.path_key || item.slug) === currentIdentifier
  );

  return {
    previous: currentIndex > 0 ? items[currentIndex - 1] : null,
    next: currentIndex >= 0 && currentIndex < items.length - 1 ? items[currentIndex + 1] : null
  };
}

export function getTutorialCategory(
  groups: TutorialNavGroup[],
  currentIdentifier: string,
  fallback: string
) {
  for (const group of groups) {
    const hit = group.items.find((item) => (item.path_key || item.slug) === currentIdentifier);
    if (hit) return group.category;
  }
  return fallback;
}

export function extractTutorialSummary(article: TutorialDetail, fallback: string) {
  const markdownSource = stripMarkdown(article.markdown_body || '');
  const htmlSource = stripHtml(article.html_body || '');
  let summary = markdownSource || htmlSource;

  if (summary && article.title) {
    const normalizedTitle = article.title.replace(/\s+/g, '').trim();
    const normalizedSummary = summary.replace(/\s+/g, '');
    if (normalizedSummary.startsWith(normalizedTitle)) {
      summary = summary.slice(article.title.length).trim();
    }
  }

  summary = summary.replace(/^[：:、，。；\-\s]+/, '');
  summary = summary.slice(0, 140).trim();

  return summary || fallback;
}

export function decorateTutorialHtml(htmlBody: string | null | undefined): {
  html: string;
  headings: TutorialHeading[];
} {
  const input = htmlBody || '';
  const headings: TutorialHeading[] = [];
  const usedIds = new Set<string>();

  const withoutNavParagraphs = input.replace(
    new RegExp('<p>\\s*(?:\\u4e0a\\u4e00\\u7bc7|\\u4e0b\\u4e00\\u7bc7)[^<]*<\\/p>', 'gi'),
    ''
  );

  const html = withoutNavParagraphs.replace(
    /<(h2|h3)([^>]*)>([\s\S]*?)<\/\1>/gi,
    (fullMatch, tagName: string, attrs: string, inner: string) => {
      const title = stripHtml(inner);
      const baseId = slugify(title) || `section-${headings.length + 1}`;
      let nextId = baseId;
      let suffix = 2;
      while (usedIds.has(nextId)) {
        nextId = `${baseId}-${suffix}`;
        suffix += 1;
      }
      usedIds.add(nextId);
      headings.push({
        id: nextId,
        title,
        level: tagName.toLowerCase() as 'h2' | 'h3'
      });
      return `<${tagName}${attrs} id="${nextId}">${inner}</${tagName}>`;
    }
  );

  return { html, headings };
}

export function formatTutorialDate(value?: string | null, locale = 'zh-CN') {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(date);
}
