'use client';

import {useEffect, useState} from 'react';
import {useTranslations} from 'next-intl';

import {
  changePassword,
  clearByokConfig,
  DEFAULT_BYOK_CONFIG,
  getMyUsage,
  isValidByokBaseUrl,
  readByokConfig,
  saveByokConfig,
  updateCurrentUser,
  type ByokConfig,
  type UserOut,
  type UserUsageSummary
} from '@georank/api-sdk';
import {clearSession, maskPhone, updateStoredUser} from '@georank/auth';
import {localizeHref} from '@georank/i18n/routing';

import {SessionGuard} from '../auth/session-guard';

type AccountSettingsProps = {
  locale: string;
};

type ProfileFormState = {
  username: string;
  email: string;
};

type PasswordFormState = {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
};

const emptyPasswordState: PasswordFormState = {
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
};

function maskApiKey(value: string) {
  if (!value) return '';
  if (value.length <= 10) return '••••••••';
  return `${value.slice(0, 4)}••••${value.slice(-4)}`;
}

function formatTokens(value: number | null | undefined, unlimited: string) {
  if (value === null || value === undefined) return unlimited;
  return value.toLocaleString();
}

export function AccountSettings({locale}: AccountSettingsProps) {
  const t = useTranslations('web.profile');

  return (
    <main className="page-wrap profile-workbench">
      <section className="page-intro profile-page-intro">
        <p className="page-eyebrow">{t('eyebrow')}</p>
        <h1 className="page-title">{t('title')}</h1>
        <p className="page-subtitle">{t('subtitle')}</p>
      </section>

      <SessionGuard
        locale={locale}
        title={t('guardTitle')}
        description={t('guardDescription')}
        redirectUnauthenticated
        returnTo={localizeHref(locale, '/profile')}
      >
        {({token, user}) => <AccountSettingsForm locale={locale} token={token} initialUser={user} />}
      </SessionGuard>
    </main>
  );
}

function AccountSettingsForm({
  locale,
  token,
  initialUser
}: {
  locale: string;
  token: string;
  initialUser: UserOut;
}) {
  const t = useTranslations('web.profile');
  const [user, setUser] = useState(initialUser);
  const [profile, setProfile] = useState<ProfileFormState>({
    username: initialUser.username || '',
    email: initialUser.email || ''
  });
  const [passwords, setPasswords] = useState<PasswordFormState>(emptyPasswordState);
  const [apiKey, setApiKey] = useState<ByokConfig>(DEFAULT_BYOK_CONFIG);
  const [usage, setUsage] = useState<UserUsageSummary | null>(null);
  const [usageFailed, setUsageFailed] = useState(false);
  const [profileMessage, setProfileMessage] = useState('');
  const [profileError, setProfileError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [apiMessage, setApiMessage] = useState('');
  const [apiError, setApiError] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) setApiKey(readByokConfig() || DEFAULT_BYOK_CONFIG);
    });
    getMyUsage(token)
      .then((summary) => {
        if (cancelled) return;
        setUsage(summary);
        const stored = readByokConfig();
        if (!summary.allow_user_byok) {
          clearByokConfig();
          setApiKey(DEFAULT_BYOK_CONFIG);
          return;
        }
        const providerAllowed = summary.provider_presets.some((item) => item.key === stored?.provider);
        if (stored?.apiKey && !providerAllowed) {
          clearByokConfig();
          setApiKey({
            ...DEFAULT_BYOK_CONFIG,
            provider: summary.byok_guidance.provider || DEFAULT_BYOK_CONFIG.provider,
            baseUrl: summary.byok_guidance.base_url || DEFAULT_BYOK_CONFIG.baseUrl,
            model: summary.byok_guidance.model || DEFAULT_BYOK_CONFIG.model
          });
          return;
        }
        if (!stored?.apiKey) {
          setApiKey((current) => ({
            ...current,
            provider: summary.byok_guidance.provider || current.provider,
            baseUrl: summary.byok_guidance.base_url || current.baseUrl,
            model: summary.byok_guidance.model || current.model
          }));
        }
      })
      .catch(() => {
        if (!cancelled) setUsageFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleProfileSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile.username.trim()) {
      setProfileError(t('usernameRequired'));
      setProfileMessage('');
      return;
    }
    if (!profile.email.trim()) {
      setProfileError(t('emailRequired'));
      setProfileMessage('');
      return;
    }

    setSavingProfile(true);
    setProfileError('');
    setProfileMessage('');
    try {
      const nextUser = await updateCurrentUser(token, {
        username: profile.username.trim(),
        email: profile.email.trim()
      });
      updateStoredUser(nextUser);
      setUser(nextUser);
      setProfile({username: nextUser.username || '', email: nextUser.email || ''});
      setProfileMessage(t('profileSaved'));
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : t('profileFailed'));
    } finally {
      setSavingProfile(false);
    }
  }

  async function handlePasswordSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (passwords.newPassword.length < 6) {
      setPasswordError(t('passwordTooShort'));
      return;
    }
    if (passwords.newPassword !== passwords.confirmPassword) {
      setPasswordError(t('passwordMismatch'));
      return;
    }

    setSavingPassword(true);
    setPasswordError('');
    try {
      await changePassword(token, {
        currentPassword: passwords.currentPassword,
        newPassword: passwords.newPassword
      });
      clearSession();
      window.location.href = `${localizeHref(locale, '/login')}?return=${encodeURIComponent(
        localizeHref(locale, '/profile')
      )}`;
    } catch (error) {
      setPasswordError(error instanceof Error ? error.message : t('passwordFailed'));
    } finally {
      setSavingPassword(false);
    }
  }

  function handleApiSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (apiKey.enabled && (!apiKey.apiKey.trim() || !apiKey.baseUrl.trim() || !apiKey.model.trim())) {
      setApiError(t('apiRequired'));
      setApiMessage('');
      return;
    }
    if (apiKey.enabled && !isValidByokBaseUrl(apiKey.baseUrl.trim())) {
      setApiError(t('apiInvalidBaseUrl'));
      setApiMessage('');
      return;
    }
    const nextConfig = saveByokConfig(apiKey);
    setApiKey(nextConfig);
    setApiError('');
    setApiMessage(t('apiSaved'));
  }

  function removeApiKey() {
    if (!window.confirm(t('removeApiConfirm'))) return;
    clearByokConfig();
    setApiKey(DEFAULT_BYOK_CONFIG);
    setApiError('');
    setApiMessage(t('apiRemoved'));
  }

  const configured = Boolean(apiKey.enabled && apiKey.apiKey && apiKey.baseUrl && apiKey.model);
  const usageMode = (() => {
    if (usageFailed) return t('usageUnavailable');
    if (!usage) return t('loading');
    if (usage.access_mode === 'lifetime_quota_with_byok') return t('mode_lifetime_quota');
    if (usage.access_mode === 'daily_quota') return t('mode_daily_quota');
    if (usage.access_mode === 'quota_with_byok') return t('mode_quota_with_byok');
    if (usage.access_mode === 'byok_required') return t('mode_byok_required');
    return t('mode_platform_unlimited');
  })();

  return (
    <section className="profile-stack">
      <div className="profile-account-summary">
        <span className="profile-account-summary__avatar" aria-hidden="true">{(user.username || 'G').slice(0, 1).toUpperCase()}</span>
        <span className="profile-account-summary__identity">
          <strong>{user.username || t('signedInUser')}</strong>
          <small>{maskPhone(user.phone || user.username || '')}</small>
        </span>
        <span className={`profile-status profile-status--${user.is_active ? 'active' : 'inactive'}`}>
          {user.is_active ? t('active') : t('inactive')}
        </span>
      </div>

      <section className="profile-surface profile-api-panel" id="model-api">
        <header className="profile-section-head">
          <div>
            <p className="page-eyebrow">{t('modelApiEyebrow')}</p>
            <h2>{t('modelApiTitle')}</h2>
          </div>
          <span className={`profile-key-status${configured ? ' is-configured' : ''}`}>
            {configured ? `${t('deviceConfigured')} · ${maskApiKey(apiKey.apiKey)}` : t('deviceNotConfigured')}
          </span>
        </header>
        <p className="profile-section-copy">{t('modelApiCopy')}</p>

        <div className="profile-usage-row">
          <div><span>{t('currentMode')}</span><strong>{usageMode}</strong></div>
          <div><span>{t('remainingTokens')}</span><strong>{usageFailed ? '--' : formatTokens(usage?.remaining_tokens, t('unlimited'))}</strong></div>
          <div><span>{t('usedTokens')}</span><strong>{usageFailed ? '--' : formatTokens(usage?.used_tokens, t('unlimited'))}</strong></div>
          <div><span>{t('grantedTokens')}</span><strong>{usageFailed ? '--' : formatTokens(usage?.grant_tokens, t('unlimited'))}</strong></div>
        </div>

        {usage && !usage.platform_available ? (
          <div className="profile-message profile-form-feedback">
            <strong>{usage.byok_guidance.title || t('quotaUnavailableTitle')}</strong>
            <p>{usage.byok_guidance.message || t('quotaUnavailableCopy')}</p>
            {usage.byok_guidance.official_url ? (
              <a href={usage.byok_guidance.official_url} rel="noreferrer" target="_blank">
                {usage.byok_guidance.cta_label || t('openApiConsole')}
              </a>
            ) : null}
          </div>
        ) : null}

        {usage?.global_budget ? (
          <p className="profile-api-note">
            {t('globalBudgetStatus', {
              used: usage.global_budget.used_tokens.toLocaleString(),
              limit: usage.global_budget.limit_tokens.toLocaleString()
            })}
          </p>
        ) : null}

        {usage?.allow_user_byok === false ? (
          <p className="profile-api-note">{t('byokDisabled')}</p>
        ) : (
        <form className="profile-api-form" onSubmit={handleApiSubmit}>
          <label className="profile-field"><span>{t('provider')}</span><select className="tool-input" value={apiKey.provider} onChange={(event) => {
            const provider = usage?.provider_presets.find((item) => item.key === event.target.value);
            setApiKey((current) => ({
              ...current,
              provider: event.target.value,
              baseUrl: provider?.base_url || current.baseUrl,
              model: provider?.default_model || current.model
            }));
          }}>{(usage?.provider_presets?.length ? usage.provider_presets : [
            {key: 'deepseek', name: 'DeepSeek', base_url: DEFAULT_BYOK_CONFIG.baseUrl, default_model: DEFAULT_BYOK_CONFIG.model},
            {key: 'openai', name: 'OpenAI', base_url: 'https://api.openai.com/v1', default_model: 'gpt-4o-mini'}
          ]).map((provider) => <option key={provider.key} value={provider.key}>{provider.name}</option>)}</select></label>
          <label className="profile-field"><span>{t('baseUrl')}</span><input className="tool-input" value={apiKey.baseUrl} onChange={(event) => setApiKey((current) => ({...current, baseUrl: event.target.value}))} /></label>
          <label className="profile-field"><span>{t('model')}</span><input className="tool-input" value={apiKey.model} onChange={(event) => setApiKey((current) => ({...current, model: event.target.value}))} /></label>
          <label className="profile-field"><span>{t('apiKey')}</span><input autoComplete="off" className="tool-input" type="password" value={apiKey.apiKey} onChange={(event) => setApiKey((current) => ({...current, apiKey: event.target.value}))} /></label>
          <label className="profile-api-toggle"><input checked={apiKey.enabled} type="checkbox" onChange={(event) => setApiKey((current) => ({...current, enabled: event.target.checked}))} /><span>{t('enableApiKey')}</span></label>
          <p className="profile-api-note">{t('apiNote')}</p>
          {apiError ? <p className="tool-error profile-form-feedback">{apiError}</p> : null}
          {apiMessage ? <p className="profile-message profile-form-feedback">{apiMessage}</p> : null}
          <div className="profile-actions">
            <button className="tool-button tool-button--primary" type="submit">{t('saveApi')}</button>
            <button className="tool-button tool-button--quiet" type="button" onClick={removeApiKey}>{t('removeApi')}</button>
          </div>
        </form>
        )}
      </section>

      <section className="profile-surface profile-settings-panel">
        <header className="profile-section-head">
          <div><p className="page-eyebrow">{t('securityEyebrow')}</p><h2>{t('accountSecurity')}</h2></div>
        </header>

        <details className="profile-setting-disclosure">
          <summary><span><strong>{t('accountTitle')}</strong><small>{user.username} · {user.email}</small></span><span>{t('edit')} ›</span></summary>
          <form className="profile-inline-form" onSubmit={handleProfileSubmit}>
            <div className="profile-form-grid">
              <label className="profile-field"><span>{t('username')}</span><input className="tool-input" maxLength={100} minLength={2} required value={profile.username} onChange={(event) => setProfile((current) => ({...current, username: event.target.value}))} /></label>
              <label className="profile-field"><span>{t('email')}</span><input className="tool-input" maxLength={200} required type="email" value={profile.email} onChange={(event) => setProfile((current) => ({...current, email: event.target.value}))} /></label>
              <label className="profile-field"><span>{t('phone')}</span><input className="tool-input" readOnly value={user.phone || ''} /></label>
            </div>
            {profileError ? <p className="tool-error profile-form-feedback">{profileError}</p> : null}
            {profileMessage ? <p className="profile-message profile-form-feedback">{profileMessage}</p> : null}
            <div className="profile-actions"><button className="tool-button tool-button--primary" disabled={savingProfile} type="submit">{savingProfile ? t('saving') : t('saveProfile')}</button></div>
          </form>
        </details>

        <details className="profile-setting-disclosure">
          <summary><span><strong>{t('passwordTitle')}</strong><small>{t('passwordSummary')}</small></span><span>{t('change')} ›</span></summary>
          <form className="profile-inline-form" onSubmit={handlePasswordSubmit}>
            <div className="profile-form-grid">
              <label className="profile-field"><span>{t('currentPassword')}</span><input autoComplete="current-password" className="tool-input" maxLength={128} minLength={6} required type="password" value={passwords.currentPassword} onChange={(event) => setPasswords((current) => ({...current, currentPassword: event.target.value}))} /></label>
              <label className="profile-field"><span>{t('newPassword')}</span><input autoComplete="new-password" className="tool-input" maxLength={128} minLength={6} required type="password" value={passwords.newPassword} onChange={(event) => setPasswords((current) => ({...current, newPassword: event.target.value}))} /></label>
              <label className="profile-field"><span>{t('confirmPassword')}</span><input autoComplete="new-password" className="tool-input" maxLength={128} minLength={6} required type="password" value={passwords.confirmPassword} onChange={(event) => setPasswords((current) => ({...current, confirmPassword: event.target.value}))} /></label>
            </div>
            {passwordError ? <p className="tool-error profile-form-feedback">{passwordError}</p> : null}
            <div className="profile-actions"><button className="tool-button tool-button--primary" disabled={savingPassword} type="submit">{savingPassword ? t('saving') : t('savePassword')}</button></div>
          </form>
        </details>

        <button className="profile-logout-button" type="button" onClick={clearSessionAndRedirect(locale)}>{t('logout')}</button>
      </section>
    </section>
  );
}

function clearSessionAndRedirect(locale: string) {
  return () => {
    clearSession();
    window.location.href = localizeHref(locale, '/login');
  };
}
