export const locales = ['zh-CN', 'en-US'] as const;
export const defaultLocale = 'zh-CN';

export type AppLocale = (typeof locales)[number];

function normalizePath(path: string) {
  if (!path) return '/';
  return path.startsWith('/') ? path : `/${path}`;
}

export function isDefaultLocale(locale?: string | null) {
  return !locale || locale === defaultLocale;
}

export function localizeHref(locale: string | null | undefined, path: string) {
  const normalizedPath = normalizePath(path);
  if (isDefaultLocale(locale)) {
    return normalizedPath;
  }
  return normalizedPath === '/' ? `/${locale}` : `/${locale}${normalizedPath}`;
}

export function stripLocalePrefix(path: string) {
  const normalizedPath = normalizePath(path);
  for (const locale of locales) {
    if (normalizedPath === `/${locale}`) {
      return '/';
    }
    if (normalizedPath.startsWith(`/${locale}/`)) {
      return normalizedPath.slice(locale.length + 1);
    }
  }
  return normalizedPath;
}

export function localizePathname(locale: string | null | undefined, path: string) {
  return localizeHref(locale, stripLocalePrefix(path));
}

export function stripDefaultLocalePrefix(path: string) {
  const normalizedPath = normalizePath(path);
  if (normalizedPath === `/${defaultLocale}`) {
    return '/';
  }
  if (normalizedPath.startsWith(`/${defaultLocale}/`)) {
    return normalizedPath.slice(defaultLocale.length + 1);
  }
  return normalizedPath;
}
