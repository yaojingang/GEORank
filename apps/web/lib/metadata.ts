import type { Metadata } from 'next';

import { stripDefaultLocalePrefix } from '@georank/i18n/routing';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3010';

export function buildPageMetadata({
  title,
  description,
  path
}: {
  title: string;
  description: string;
  path: string;
}): Metadata {
  const url = new URL(stripDefaultLocalePrefix(path), SITE_URL).toString();
  return {
    title,
    description,
    alternates: {
      canonical: url
    },
    openGraph: {
      title,
      description,
      url,
      type: 'article'
    }
  };
}
