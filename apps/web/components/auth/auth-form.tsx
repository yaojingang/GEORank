'use client';

import {useEffect, useMemo, useState} from 'react';
import {useTranslations} from 'next-intl';

import {getCurrentUser, login, register} from '@georank/api-sdk';
import {getBoundPhone, getVerifiedSession, maskPhone, normalizePhone, setSession} from '@georank/auth';
import {localizeHref, stripLocalePrefix} from '@georank/i18n/routing';

type AuthFormProps = {
  locale: string;
  mode: 'login' | 'register';
  returnTo?: string;
};

const RETURN_ORIGIN = 'https://return.georank.local';

function safeReturnTo(value: unknown, fallback: string) {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return fallback;
  try {
    const target = new URL(value, RETURN_ORIGIN);
    if (target.origin !== RETURN_ORIGIN) return fallback;
    const currentPath = stripLocalePrefix(target.pathname);
    if (currentPath === '/login' || currentPath === '/register') return fallback;
    return `${target.pathname}${target.search}${target.hash}`;
  } catch {
    return fallback;
  }
}

export function AuthForm({locale, mode, returnTo}: AuthFormProps) {
  const t = useTranslations('web.authForm');
  const boundPhone = useMemo(() => getBoundPhone(), []);
  const profileHref = localizeHref(locale, '/profile');
  const destination = safeReturnTo(returnTo, profileHref);
  const [phone, setPhone] = useState(boundPhone);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    getVerifiedSession().then((user) => {
      if (!cancelled && user) window.location.replace(destination);
    });
    return () => {
      cancelled = true;
    };
  }, [destination]);

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
    if (mode === 'register' && password !== confirmPassword) {
      setError(t('passwordMismatch'));
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      const tokenResponse =
        mode === 'register'
          ? await register({phone: normalizedPhone, password, remember_me: remember})
          : await login({phone: normalizedPhone, password, remember_me: remember});
      const user = await getCurrentUser(tokenResponse.access_token);
      setSession(tokenResponse.access_token, user, remember);
      window.location.href = destination;
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : t('authFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  const alternateHref = `${localizeHref(locale, mode === 'register' ? '/login' : '/register')}?return=${encodeURIComponent(
    destination
  )}`;

  return (
    <main className="auth-page auth-page--account">
      <section className="auth-card auth-card--account" aria-labelledby="auth-page-title">
        <p className="page-eyebrow">{mode === 'register' ? t('registerEyebrow') : t('loginEyebrow')}</p>
        <h1 className="auth-card__title" id="auth-page-title">
          {mode === 'register' ? t('registerTitle') : t('loginTitle')}
        </h1>
        <p className="auth-card__copy">{mode === 'register' ? t('registerCopy') : t('loginCopy')}</p>

        {boundPhone ? <p className="auth-form__notice">{t('boundPhone', {phone: maskPhone(boundPhone)})}</p> : null}

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

          {mode === 'register' ? (
            <label className="auth-form__label">
              <span>{t('confirmPassword')}</span>
              <input
                autoComplete="new-password"
                maxLength={128}
                minLength={6}
                name="confirmPassword"
                placeholder={t('confirmPasswordPlaceholder')}
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
              />
            </label>
          ) : null}

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
          <span>{mode === 'register' ? t('hasAccountPrompt') : t('noAccountPrompt')}</span>
          <a href={alternateHref}>{mode === 'register' ? t('goLogin') : t('goRegister')}</a>
        </div>
      </section>
    </main>
  );
}
