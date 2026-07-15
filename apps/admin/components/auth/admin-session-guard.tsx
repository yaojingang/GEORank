'use client';

import type {ReactNode} from 'react';
import {useEffect, useMemo, useState} from 'react';
import {useLocale, useTranslations} from 'next-intl';

import {getSession, getStoredToken, maskPhone} from '@georank/auth';
import {localizeHref} from '@georank/i18n/routing';

type AdminSessionGuardProps = {
  children: (context: {token: string; userLabel: string}) => ReactNode;
};

export function AdminSessionGuard({children}: AdminSessionGuardProps) {
  const locale = useLocale();
  const t = useTranslations('admin.session');
  const [status, setStatus] = useState<'loading' | 'ready' | 'unauthenticated' | 'forbidden'>(
    'loading'
  );
  const [userLabel, setUserLabel] = useState('');
  const token = useMemo(() => getStoredToken(), []);

  useEffect(() => {
    let active = true;

    getSession()
      .then((user) => {
        if (!active) return;
        if (!user) {
          setStatus('unauthenticated');
          return;
        }
        if (user.role !== 'admin') {
          setUserLabel(maskPhone(user.phone || user.username));
          setStatus('forbidden');
          return;
        }
        setUserLabel(maskPhone(user.phone || user.username));
        setStatus(token ? 'ready' : 'unauthenticated');
      })
      .catch(() => {
        if (!active) return;
        setStatus('unauthenticated');
      });

    return () => {
      active = false;
    };
  }, [token]);

  if (status === 'loading') {
    return (
      <main className="admin-page">
        <div className="admin-empty-state">
          <p className="admin-eyebrow">Admin Session</p>
          <h1>{t('checkingTitle')}</h1>
          <p>{t('checkingCopy')}</p>
        </div>
      </main>
    );
  }

  if (status === 'unauthenticated') {
    return (
      <main className="admin-page">
        <div className="admin-empty-state">
          <p className="admin-eyebrow">Admin Session</p>
          <h1>{t('loginTitle')}</h1>
          <p>{t('loginCopy')}</p>
          <div className="admin-empty-actions">
            <a className="admin-primary-link" href={`http://localhost:3010${localizeHref(locale, '/login')}`}>
              {t('loginLink')}
            </a>
          </div>
        </div>
      </main>
    );
  }

  if (status === 'forbidden') {
    return (
      <main className="admin-page">
        <div className="admin-empty-state">
          <p className="admin-eyebrow">Admin Session</p>
          <h1>{t('forbiddenTitle')}</h1>
          <p>{t('forbiddenCopy', {userLabel: userLabel || t('unknownAccount')})}</p>
        </div>
      </main>
    );
  }

  return <>{children({token, userLabel})}</>;
}
