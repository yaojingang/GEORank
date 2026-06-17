'use client';

import {useEffect, useState} from 'react';
import {useTranslations} from 'next-intl';

import {clearSession, getSession, maskPhone} from '@georank/auth';
import {localizeHref} from '@georank/i18n/routing';
import {LanguageSwitcher} from '../components/language-switcher';

type SiteHeaderProps = {
  locale?: string;
};

export function SiteHeader({ locale = 'zh-CN' }: SiteHeaderProps) {
  const [userLabel, setUserLabel] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const nav = useTranslations('nav');
  const auth = useTranslations('auth');

  useEffect(() => {
    let mounted = true;
    getSession().then((user) => {
      if (!mounted) return;
      setUserLabel(user ? maskPhone(user.phone || user.username) : '');
    });
    return () => {
      mounted = false;
    };
  }, []);

  const isAuthenticated = Boolean(userLabel);

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <a className="site-header__brand" href={localizeHref(locale, '/')}>
          GEOrank
        </a>
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
          {isAuthenticated ? (
            <div className="site-header__menu-wrap">
              <button
                className="site-header__auth-button"
                type="button"
                aria-label={auth('accountMenu')}
                aria-expanded={menuOpen}
                aria-haspopup="menu"
                onClick={() => setMenuOpen((open) => !open)}
              >
                {userLabel}
              </button>
              {menuOpen ? (
                <div className="site-header__menu">
                  <a className="site-header__menu-item" href={localizeHref(locale, '/solutions')}>
                    {auth('continueSolutions')}
                  </a>
                  <button
                    className="site-header__menu-item site-header__menu-item--button"
                    type="button"
                    onClick={() => {
                      clearSession();
                      setMenuOpen(false);
                      setUserLabel('');
                    }}
                  >
                    {auth('logout')}
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <>
              <a className="site-header__ghost-link" href={localizeHref(locale, '/login')}>
                {auth('login')}
              </a>
              <a className="site-header__auth-button" href={localizeHref(locale, '/register')}>
                {auth('register')}
              </a>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
