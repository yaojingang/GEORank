'use client';

import {useEffect, useState} from 'react';
import {useTranslations} from 'next-intl';

import {getSession, maskPhone} from '@georank/auth';
import {localizeHref, stripLocalePrefix} from '@georank/i18n/routing';

import {LanguageSwitcher} from '../components/language-switcher';

type SiteHeaderProps = {
  locale?: string;
};

function safeAccountReturnTo(value: string) {
  if (!value.startsWith('/') || value.startsWith('//')) return '';
  try {
    const target = new URL(value, window.location.origin);
    if (target.origin !== window.location.origin) return '';
    const currentPath = stripLocalePrefix(target.pathname);
    if (currentPath === '/login' || currentPath === '/register') return '';
    return `${target.pathname}${target.search}${target.hash}`;
  } catch {
    return '';
  }
}

function AccountIcon() {
  return (
    <svg aria-hidden="true" fill="none" height="20" viewBox="0 0 24 24" width="20">
      <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" stroke="currentColor" strokeWidth="1.8" />
      <path d="M4.8 20a7.2 7.2 0 0 1 14.4 0" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}

export function SiteHeader({locale = 'zh-CN'}: SiteHeaderProps) {
  const [userLabel, setUserLabel] = useState('');
  const [accountHref, setAccountHref] = useState(localizeHref(locale, '/login'));
  const nav = useTranslations('nav');
  const auth = useTranslations('auth');

  useEffect(() => {
    let mounted = true;
    const syncAccount = async () => {
      const user = await getSession();
      if (!mounted) return;
      const label = user ? maskPhone(user.phone || user.username) : '';
      setUserLabel(label);
      if (user) {
        setAccountHref(localizeHref(locale, '/profile'));
        return;
      }
      const currentPath = stripLocalePrefix(window.location.pathname);
      const isAuthPage = currentPath === '/login' || currentPath === '/register';
      const rawReturnTo = isAuthPage
        ? new URLSearchParams(window.location.search).get('return') || ''
        : `${window.location.pathname}${window.location.search}`;
      const returnTo = safeAccountReturnTo(rawReturnTo);
      const loginHref = localizeHref(locale, '/login');
      setAccountHref(returnTo ? `${loginHref}?return=${encodeURIComponent(returnTo)}` : loginHref);
    };
    const handleAuthChange = () => {
      void syncAccount();
    };

    void syncAccount();
    window.addEventListener('georank:auth-changed', handleAuthChange);
    return () => {
      mounted = false;
      window.removeEventListener('georank:auth-changed', handleAuthChange);
    };
  }, [locale]);

  const isAuthenticated = Boolean(userLabel);

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <a className="site-header__brand" href={localizeHref(locale, '/')}>GEOrank</a>
        <nav className="site-header__nav">
          <a href={localizeHref(locale, '/companies')}>{nav('companies')}</a>
          <a href={localizeHref(locale, '/diagnostic')}>{nav('diagnostic')}</a>
          <a href={localizeHref(locale, '/solutions')}>{nav('solutions')}</a>
          <a href={localizeHref(locale, '/keywords')}>{nav('keywords')}</a>
          <a href={localizeHref(locale, '/tools')}>{nav('tools')}</a>
          <a href={localizeHref(locale, '/experts')}>{nav('experts')}</a>
          <a href={localizeHref(locale, '/tutorial')}>{nav('tutorial')}</a>
        </nav>
        <div className="site-header__actions">
          <LanguageSwitcher locale={locale} variant="site" />
          <a
            aria-label={isAuthenticated ? auth('accountMenu') : auth('loginOrRegister')}
            className="site-header__account-link"
            href={accountHref}
          >
            <AccountIcon />
            {isAuthenticated ? <span>{userLabel}</span> : null}
          </a>
        </div>
      </div>
    </header>
  );
}
