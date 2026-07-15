'use client';

import {useEffect, useState} from 'react';
import {useTranslations} from 'next-intl';

import {changePassword, updateCurrentUser} from '@georank/api-sdk';
import {clearSession, normalizePhone, setSession} from '@georank/auth';
import {localizeHref} from '@georank/i18n/routing';

import {SessionGuard} from '../auth/session-guard';

type AccountSettingsProps = {
  locale: string;
};

type ProfileFormState = {
  username: string;
  email: string;
  phone: string;
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

export function AccountSettings({locale}: AccountSettingsProps) {
  const t = useTranslations('web.profile');

  return (
    <main className="page-wrap profile-workbench">
      <section className="page-intro">
        <p className="page-eyebrow">{t('eyebrow')}</p>
        <h1 className="page-title">{t('title')}</h1>
        <p className="page-subtitle">{t('subtitle')}</p>
      </section>

      <SessionGuard locale={locale} title={t('guardTitle')} description={t('guardDescription')}>
        {({token, user}) => <AccountSettingsForm locale={locale} token={token} user={user} />}
      </SessionGuard>
    </main>
  );
}

function AccountSettingsForm({
  locale,
  token,
  user
}: {
  locale: string;
  token: string;
  user: {
    id: string;
    email: string;
    username: string;
    phone?: string | null;
    role: string;
    is_active: boolean;
    is_verified: boolean;
  };
}) {
  const t = useTranslations('web.profile');
  const [profile, setProfile] = useState<ProfileFormState>({
    username: user.username || '',
    email: user.email || '',
    phone: user.phone || ''
  });
  const [passwords, setPasswords] = useState<PasswordFormState>(emptyPasswordState);
  const [profileMessage, setProfileMessage] = useState('');
  const [profileError, setProfileError] = useState('');
  const [passwordMessage, setPasswordMessage] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    setProfile({
      username: user.username || '',
      email: user.email || '',
      phone: user.phone || ''
    });
  }, [user.email, user.phone, user.username]);

  async function handleProfileSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const phone = normalizePhone(profile.phone);
    const hasPhoneInput = Boolean(profile.phone.trim());

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
    if (hasPhoneInput && !/^1\d{10}$/.test(phone)) {
      setProfileError(t('invalidPhone'));
      setProfileMessage('');
      return;
    }

    setSavingProfile(true);
    setProfileError('');
    setProfileMessage('');
    try {
      const nextUser = await updateCurrentUser(token, {
        username: profile.username.trim(),
        email: profile.email.trim(),
        phone: hasPhoneInput ? phone : null
      });
      setSession(token, nextUser, true);
      setProfile({
        username: nextUser.username || '',
        email: nextUser.email || '',
        phone: nextUser.phone || ''
      });
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
      setPasswordMessage('');
      return;
    }
    if (passwords.newPassword !== passwords.confirmPassword) {
      setPasswordError(t('passwordMismatch'));
      setPasswordMessage('');
      return;
    }

    setSavingPassword(true);
    setPasswordError('');
    setPasswordMessage('');
    try {
      await changePassword(token, {
        currentPassword: passwords.currentPassword,
        newPassword: passwords.newPassword
      });
      setPasswordMessage(t('passwordSaved'));
      setPasswords(emptyPasswordState);
      window.setTimeout(() => {
        clearSession();
        window.location.href = `${localizeHref(locale, '/login')}?return=${encodeURIComponent(
          localizeHref(locale, '/profile')
        )}`;
      }, 900);
    } catch (error) {
      setPasswordError(error instanceof Error ? error.message : t('passwordFailed'));
    } finally {
      setSavingPassword(false);
    }
  }

  return (
    <section className="profile-grid">
      <form className="panel tool-panel profile-panel" onSubmit={handleProfileSubmit}>
        <div className="tool-panel__head">
          <div>
            <p className="page-eyebrow">{t('accountEyebrow')}</p>
            <h2 className="card-title">{t('accountTitle')}</h2>
          </div>
          <span className={`profile-status profile-status--${user.is_active ? 'active' : 'inactive'}`}>
            {user.is_active ? t('active') : t('inactive')}
          </span>
        </div>

        <div className="profile-form-grid">
          <label className="profile-field">
            <span>{t('username')}</span>
            <input
              className="tool-input"
              maxLength={100}
              minLength={2}
              name="username"
              value={profile.username}
              onChange={(event) => setProfile((current) => ({...current, username: event.target.value}))}
            />
          </label>
          <label className="profile-field">
            <span>{t('email')}</span>
            <input
              className="tool-input"
              maxLength={200}
              name="email"
              type="email"
              value={profile.email}
              onChange={(event) => setProfile((current) => ({...current, email: event.target.value}))}
            />
          </label>
          <label className="profile-field">
            <span>{t('phone')}</span>
            <input
              className="tool-input"
              inputMode="numeric"
              maxLength={20}
              name="phone"
              type="tel"
              value={profile.phone}
              onChange={(event) => setProfile((current) => ({...current, phone: event.target.value}))}
            />
          </label>
        </div>

        <div className="profile-meta-list">
          <div>
            <span>{t('role')}</span>
            <strong>{user.role}</strong>
          </div>
          <div>
            <span>{t('verified')}</span>
            <strong>{user.is_verified ? t('yes') : t('no')}</strong>
          </div>
        </div>

        {profileError ? <p className="tool-error">{profileError}</p> : null}
        {profileMessage ? <p className="profile-message">{profileMessage}</p> : null}

        <div className="profile-actions">
          <button className="tool-button tool-button--primary" disabled={savingProfile} type="submit">
            {savingProfile ? t('saving') : t('saveProfile')}
          </button>
        </div>
      </form>

      <form className="panel tool-panel profile-panel" onSubmit={handlePasswordSubmit}>
        <div className="tool-panel__head">
          <div>
            <p className="page-eyebrow">{t('securityEyebrow')}</p>
            <h2 className="card-title">{t('passwordTitle')}</h2>
          </div>
        </div>

        <div className="profile-form-grid">
          <label className="profile-field">
            <span>{t('currentPassword')}</span>
            <input
              autoComplete="current-password"
              className="tool-input"
              maxLength={128}
              minLength={6}
              name="currentPassword"
              type="password"
              value={passwords.currentPassword}
              onChange={(event) =>
                setPasswords((current) => ({...current, currentPassword: event.target.value}))
              }
            />
          </label>
          <label className="profile-field">
            <span>{t('newPassword')}</span>
            <input
              autoComplete="new-password"
              className="tool-input"
              maxLength={128}
              minLength={6}
              name="newPassword"
              type="password"
              value={passwords.newPassword}
              onChange={(event) =>
                setPasswords((current) => ({...current, newPassword: event.target.value}))
              }
            />
          </label>
          <label className="profile-field">
            <span>{t('confirmPassword')}</span>
            <input
              autoComplete="new-password"
              className="tool-input"
              maxLength={128}
              minLength={6}
              name="confirmPassword"
              type="password"
              value={passwords.confirmPassword}
              onChange={(event) =>
                setPasswords((current) => ({...current, confirmPassword: event.target.value}))
              }
            />
          </label>
        </div>

        {passwordError ? <p className="tool-error">{passwordError}</p> : null}
        {passwordMessage ? <p className="profile-message">{passwordMessage}</p> : null}

        <div className="profile-actions">
          <button className="tool-button tool-button--primary" disabled={savingPassword} type="submit">
            {savingPassword ? t('saving') : t('savePassword')}
          </button>
          <button className="tool-button tool-button--ghost" type="button" onClick={clearSessionAndRedirect(locale)}>
            {t('logout')}
          </button>
        </div>
      </form>
    </section>
  );
}

function clearSessionAndRedirect(locale: string) {
  return () => {
    clearSession();
    window.location.href = localizeHref(locale, '/login');
  };
}
