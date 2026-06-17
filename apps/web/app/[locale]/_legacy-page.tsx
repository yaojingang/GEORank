import {readFileSync} from 'node:fs';
import {join, resolve} from 'node:path';
import type {Metadata} from 'next';

export type LegacyPageId =
  | 'index'
  | 'company'
  | 'company-submit'
  | 'diagnostic'
  | 'solutions'
  | 'plans'
  | 'keywords'
  | 'tools'
  | 'experts'
  | 'profile'
  | 'tutorial'
  | 'login'
  | 'register';

type ParsedLegacyHtml = {
  bodyClass: string;
  html: string;
};

function getDistFilePath(page: LegacyPageId) {
  return join(resolve(process.cwd(), '../..'), 'dist', `${page}.html`);
}

function readLegacySource(page: LegacyPageId) {
  return readFileSync(getDistFilePath(page), 'utf8');
}

function extractBodyClass(bodyAttrs = '') {
  const match = bodyAttrs.match(/\sclass="([^"]*)"/i);
  return match?.[1] || '';
}

function extractHeadAssets(headHtml = '') {
  const assets = headHtml.match(/<style\b[\s\S]*?<\/style>|<script\b[\s\S]*?<\/script>|<link\b[^>]*>/gi);
  return assets?.join('\n') || '';
}

function parseLegacyHtml(page: LegacyPageId): ParsedLegacyHtml {
  const source = readLegacySource(page);
  const headMatch = source.match(/<head[^>]*>([\s\S]*?)<\/head>/i);
  const bodyMatch = source.match(/<body([^>]*)>([\s\S]*?)<\/body>/i);
  const headAssets = extractHeadAssets(headMatch?.[1] || '');
  const bodyClass = extractBodyClass(bodyMatch?.[1] || '');
  const bodyHtml = bodyMatch?.[2] || source;
  const bodySetup = `<script>document.body.className=${JSON.stringify(bodyClass)};</script>`;

  return {
    bodyClass,
    html: `${headAssets}\n${bodySetup}\n${bodyHtml}`
  };
}

export function getLegacyMetadata(page: LegacyPageId): Metadata {
  const source = readLegacySource(page);
  const title = source.match(/<title>([^<]*)<\/title>/i)?.[1] || 'GEOrank';
  const description = source.match(/<meta\s+name="description"\s+content="([^"]*)"/i)?.[1] || title;
  return {title, description};
}

export function LegacyStaticPage({page}: {page: LegacyPageId}) {
  const parsed = parseLegacyHtml(page);

  return (
    <div
      className={parsed.bodyClass}
      data-legacy-static-page={page}
      dangerouslySetInnerHTML={{__html: parsed.html}}
      suppressHydrationWarning
    />
  );
}
