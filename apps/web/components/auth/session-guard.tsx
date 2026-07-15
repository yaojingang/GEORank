'use client';

import { useEffect, useState } from 'react';
import {useTranslations} from 'next-intl';

import type { UserOut } from '@georank/api-sdk';
import { getSession, getStoredToken } from '@georank/auth';
import {localizeHref} from '@georank/i18n/routing';

type SessionGuardProps = {
  locale: string;
  title: string;
  description: string;
  children: (props: { token: string; user: UserOut }) => React.ReactNode;
};

export function SessionGuard({ locale, title, description, children }: SessionGuardProps) {
  const t = useTranslations('web.session');
  const [status, setStatus] = useState<'loading' | 'ready' | 'unauthenticated'>('loading');
  const [token, setToken] = useState('');
  const [user, setUser] = useState<UserOut | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const nextToken = getStoredToken();
      if (!nextToken) {
        if (!cancelled) {
          setStatus('unauthenticated');
        }
        return;
      }

      const nextUser = await getSession();
      if (cancelled) return;

      if (!nextUser) {
        setStatus('unauthenticated');
        return;
      }

      setToken(nextToken);
      setUser(nextUser);
      setStatus('ready');
    }

    bootstrap();

    return () => {
      cancelled = true;
    };
  }, []);

  if (status === 'loading') {
    return (
      <section className="panel tool-auth">
        <span className="page-eyebrow">{t('loadingEyebrow')}</span>
        <h2 className="card-title">{title}</h2>
        <p className="card-subtitle">{t('restoring')}</p>
      </section>
    );
  }

  if (status === 'unauthenticated' || !user) {
    return (
      <section className="panel tool-auth">
        <span className="page-eyebrow">{t('authRequiredEyebrow')}</span>
        <h2 className="card-title">{title}</h2>
        <p className="card-subtitle">{description}</p>
        <div className="tool-auth__actions">
          <a className="tool-button tool-button--primary" href={localizeHref(locale, '/login')}>
            {t('loginNow')}
          </a>
          <a className="tool-button tool-button--ghost" href={localizeHref(locale, '/register')}>
            {t('registerAccount')}
          </a>
        </div>
      </section>
    );
  }

  return <>{children({ token, user })}</>;
}
