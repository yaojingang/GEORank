'use client';

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
        <a href={localizeHref(locale, '/')}>{nav('dashboard')}</a>
        <a href={localizeHref(locale, '/companies')}>{nav('companies')}</a>
        <a href={localizeHref(locale, '/diagnostics')}>{nav('diagnostics')}</a>
        <a href={localizeHref(locale, '/solutions')}>{nav('solutions')}</a>
        <a href={localizeHref(locale, '/keywords')}>{nav('keywords')}</a>
        <a href={localizeHref(locale, '/experts')}>{nav('experts')}</a>
        <a href={localizeHref(locale, '/homepage')}>{nav('homepage')}</a>
        <a href={localizeHref(locale, '/tutorials')}>{nav('tutorials')}</a>
        <a href={localizeHref(locale, '/users')}>{nav('users')}</a>
        <a href={localizeHref(locale, '/settings')}>{nav('settings')}</a>
      </nav>
      <div className="admin-sidebar__footer">
        <LanguageSwitcher locale={locale} variant="admin" />
      </div>
    </aside>
  );
}
