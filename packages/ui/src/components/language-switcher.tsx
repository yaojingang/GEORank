'use client';

import Link from 'next/link';
import {usePathname} from 'next/navigation';
import {useTranslations} from 'next-intl';
import clsx from 'clsx';

import {
  defaultLocale,
  locales,
  localizePathname,
  type AppLocale
} from '@georank/i18n/routing';

type LanguageSwitcherProps = {
  locale?: string;
  variant?: 'site' | 'admin';
  className?: string;
};

function resolveLocale(locale?: string): AppLocale {
  return locales.includes(locale as AppLocale) ? (locale as AppLocale) : defaultLocale;
}

export function LanguageSwitcher({
  locale = defaultLocale,
  variant = 'site',
  className
}: LanguageSwitcherProps) {
  const pathname = usePathname() || '/';
  const t = useTranslations('language');
  const currentLocale = resolveLocale(locale);

  return (
    <nav
      className={clsx('language-switcher', `language-switcher--${variant}`, className)}
      aria-label={t('label')}
    >
      {locales.map((targetLocale) => {
        const isActive = targetLocale === currentLocale;
        const label = targetLocale === 'zh-CN' ? t('zh') : t('en');
        return (
          <Link
            key={targetLocale}
            className={clsx('language-switcher__option', isActive && 'is-active')}
            href={localizePathname(targetLocale, pathname)}
            aria-current={isActive ? 'true' : undefined}
            aria-label={`${isActive ? t('current') : t('switchTo')} ${label}`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
