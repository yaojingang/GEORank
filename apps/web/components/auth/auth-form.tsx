'use client';

import { useMemo, useState } from 'react';
import {useTranslations} from 'next-intl';

import { getCurrentUser, login, register } from '@georank/api-sdk';
import { getBoundPhone, maskPhone, normalizePhone } from '@georank/auth';
import { setSession } from '@georank/auth';
import { localizeHref } from '@georank/i18n/routing';

type AuthFormProps = {
  locale: string;
  mode: 'login' | 'register';
  returnTo?: string;
};

export function AuthForm({ locale, mode, returnTo }: AuthFormProps) {
  const t = useTranslations('web.authForm');
  const boundPhone = useMemo(() => getBoundPhone(), []);
  const [phone, setPhone] = useState(boundPhone);
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedPhone = normalizePhone(phone);

    if (boundPhone && boundPhone !== normalizedPhone) {
      setError(t('boundPhone', {phone: maskPhone(boundPhone)}));
      return;
    }
    if (!/^1\d{10}$/.test(normalizedPhone)) {
      setError(t('invalidPhone'));
      return;
    }
    if (password.length < 6) {
      setError(t('shortPassword'));
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      const tokenResponse =
        mode === 'register'
          ? await register({ phone: normalizedPhone, password, remember_me: remember })
          : await login({ phone: normalizedPhone, password, remember_me: remember });
      const user = await getCurrentUser(tokenResponse.access_token);
      setSession(tokenResponse.access_token, user, remember);
      window.location.href = returnTo || localizeHref(locale, '/');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : t('authFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <p className="page-eyebrow">{mode === 'register' ? 'Create Account' : 'Account Access'}</p>
        <h1 className="card-title">{mode === 'register' ? t('registerTitle') : t('loginTitle')}</h1>
        <p className="card-subtitle">
          {t('subtitle', {mode: mode === 'register' ? t('registerMode') : t('loginMode')})}
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="auth-form__label">
            <span>{t('phone')}</span>
            <input
              autoComplete="tel"
              inputMode="numeric"
              maxLength={20}
              name="phone"
              placeholder={t('phonePlaceholder')}
              type="tel"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
            />
          </label>

          <label className="auth-form__label">
            <span>{t('password')}</span>
            <input
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              maxLength={128}
              minLength={6}
              name="password"
              placeholder={t('passwordPlaceholder')}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>

          <label className="auth-form__checkbox">
            <input checked={remember} type="checkbox" onChange={(event) => setRemember(event.target.checked)} />
            <span>{t('remember')}</span>
          </label>

          {error ? <p className="auth-form__error">{error}</p> : null}

          <button className="auth-form__submit" disabled={submitting} type="submit">
            {submitting
              ? mode === 'register'
                ? t('registering')
                : t('loggingIn')
              : mode === 'register'
                ? t('registerSubmit')
                : t('loginSubmit')}
          </button>
        </form>

        <div className="auth-form__links">
          {mode === 'register' ? (
            <a href={`${localizeHref(locale, '/login')}${returnTo ? `?return=${encodeURIComponent(returnTo)}` : ''}`}>
              {t('hasAccount')}
            </a>
          ) : (
            <a href={`${localizeHref(locale, '/register')}${returnTo ? `?return=${encodeURIComponent(returnTo)}` : ''}`}>
              {t('noAccount')}
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
