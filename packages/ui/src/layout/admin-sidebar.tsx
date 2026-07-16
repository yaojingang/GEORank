'use client';

import Link from 'next/link';
import {useTranslations} from 'next-intl';

import {localizeHref} from '@georank/i18n/routing';
import {LanguageSwitcher} from '../components/language-switcher';

type AdminSidebarProps = {
  locale?: string;
};

export function AdminSidebar({ locale = 'zh-CN' }: AdminSidebarProps) {
  const admin = useTranslations('admin');
  const nav = useTranslations('admin.nav');

  return (
    <aside className="admin-sidebar">
      <div className="admin-sidebar__brand">{admin('brand')}</div>
      <nav className="admin-sidebar__nav">
        <Link href={localizeHref(locale, '/')}>{nav('dashboard')}</Link>
        <Link href={localizeHref(locale, '/companies')}>{nav('companies')}</Link>
        <Link href={localizeHref(locale, '/diagnostics')}>{nav('diagnostics')}</Link>
        <Link href={localizeHref(locale, '/solutions')}>{nav('solutions')}</Link>
        <Link href={localizeHref(locale, '/keywords')}>{nav('keywords')}</Link>
        <Link href={localizeHref(locale, '/experts')}>{nav('experts')}</Link>
        <Link href={localizeHref(locale, '/homepage')}>{nav('homepage')}</Link>
        <Link href={localizeHref(locale, '/tutorials')}>{nav('tutorials')}</Link>
        <Link href={localizeHref(locale, '/users')}>{nav('users')}</Link>
        <Link href={localizeHref(locale, '/settings')}>{nav('settings')}</Link>
      </nav>
      <div className="admin-sidebar__footer">
        <LanguageSwitcher locale={locale} variant="admin" />
      </div>
    </aside>
  );
}
