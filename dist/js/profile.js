/**
 * GEOrank - 个人中心设置页
 */
(function () {
    'use strict';

    const $ = (selector, root = document) => root.querySelector(selector);

    function localeLabel(locale) {
        return locale === 'en-US' ? 'English' : '中文';
    }

    function apiBase() {
        return window.GEOrank?.Auth?.apiBase
            || '';
    }

    function modeLabel(mode) {
        const labels = {
            platform_unlimited: '平台无限',
            daily_quota: '每日额度',
            quota_with_byok: '额度 + 自定义 Key',
            byok_required: '必须自定义 Key',
        };
        return labels[mode] || mode || '未配置';
    }

    function tokenLabel(value) {
        if (value === null || value === undefined) return '不限';
        return Number(value || 0).toLocaleString();
    }

    function t(key, fallback = '') {
        return window.GEOrank?.I18N?.t?.(key) || fallback || key;
    }

    function showPasswordMessage(message, type = 'info') {
        const messageEl = $('[data-profile-password-message]');
        if (!messageEl) return;
        messageEl.textContent = message;
        messageEl.classList.remove('hidden', 'is-error', 'is-success');
        if (type === 'error') messageEl.classList.add('is-error');
        if (type === 'success') messageEl.classList.add('is-success');
    }

    function setPasswordBusy(isBusy) {
        const submit = $('[data-profile-password-submit]');
        if (!submit) return;
        submit.disabled = Boolean(isBusy);
        submit.textContent = isBusy ? t('profile.passwordSubmitting', '保存中...') : t('profile.passwordSubmit', '保存新密码');
    }

    function renderProfile() {
        const Auth = window.GEOrank?.Auth;
        const I18N = window.GEOrank?.I18N;
        if (!Auth || !I18N) return;

        const user = Auth.getUser?.();
        const authenticated = Auth.isAuthenticated?.();
        const accountStatus = $('[data-profile-account-status]');
        const accountCopy = $('[data-profile-account-copy]');
        const accountValue = $('[data-profile-account-value]');
        const loginLink = $('[data-profile-login]');
        const registerLink = $('[data-profile-register]');
        const logoutButton = $('[data-profile-logout]');
        const localeLabelEl = $('[data-current-locale-label]');

        if (accountStatus) {
            accountStatus.textContent = authenticated ? I18N.t('auth.signedIn') : I18N.t('auth.signedOut');
        }
        if (accountCopy) {
            accountCopy.textContent = authenticated ? I18N.t('profile.signedInCopy') : I18N.t('profile.signedOutCopy');
        }
        if (accountValue) {
            const raw = user?.phone || user?.username || I18N.t('auth.signedIn');
            accountValue.textContent = authenticated ? Auth.maskPhone(raw) : I18N.t('auth.signedOut');
        }
        if (loginLink) loginLink.classList.toggle('hidden', authenticated);
        if (registerLink) registerLink.classList.toggle('hidden', authenticated);
        if (logoutButton) logoutButton.classList.toggle('hidden', !authenticated);
        if (localeLabelEl) localeLabelEl.textContent = localeLabel(I18N.getLocale());
        setPasswordBusy(false);
        renderApiKeyForm();
    }

    async function renderUsage() {
        const Auth = window.GEOrank?.Auth;
        const token = Auth?.getToken?.();
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        try {
            const response = await fetch(`${apiBase()}/api/usage/me`, { headers });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'usage failed');
            const modeEl = $('[data-api-usage-mode]');
            const remainingEl = $('[data-api-usage-remaining]');
            const usedEl = $('[data-api-usage-used]');
            if (modeEl) modeEl.textContent = modeLabel(payload.access_mode);
            if (remainingEl) remainingEl.textContent = tokenLabel(payload.remaining_tokens);
            if (usedEl) usedEl.textContent = tokenLabel(payload.used_tokens);
        } catch (error) {
            const modeEl = $('[data-api-usage-mode]');
            const remainingEl = $('[data-api-usage-remaining]');
            const usedEl = $('[data-api-usage-used]');
            if (modeEl) modeEl.textContent = '读取失败';
            if (remainingEl) remainingEl.textContent = '--';
            if (usedEl) usedEl.textContent = '--';
        }
    }

    function renderApiKeyForm() {
        const store = window.GEOrank?.APIKeyStore;
        const form = $('[data-profile-api-form]');
        const statusEl = $('[data-api-key-status]');
        if (!store || !form) return;
        const config = store.read?.() || {};
        form.provider.value = config.provider || 'deepseek';
        form.baseUrl.value = config.baseUrl || 'https://api.deepseek.com/v1';
        form.model.value = config.model || 'deepseek-chat';
        form.apiKey.value = config.apiKey || '';
        form.enabled.checked = Boolean(config.enabled && config.apiKey);
        if (statusEl) {
            statusEl.textContent = store.hasUsableKey?.()
                ? `${config.provider || 'custom'} · ${store.maskKey(config.apiKey)}`
                : '未配置';
        }
    }

    function bindProfile() {
        $('[data-profile-logout]')?.addEventListener('click', () => {
            window.GEOrank?.Auth?.clearSession?.();
            renderProfile();
            void renderUsage();
        });
        $('[data-profile-password-form]')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const Auth = window.GEOrank?.Auth;
            if (!Auth?.isAuthenticated?.()) {
                showPasswordMessage(t('profile.passwordLoginRequired', '请先登录后再修改密码'), 'error');
                return;
            }

            const form = event.currentTarget;
            const currentPassword = form.elements.currentPassword?.value || '';
            const newPassword = form.elements.newPassword?.value || '';
            const confirmPassword = form.elements.confirmPassword?.value || '';

            if (newPassword.length < 6) {
                showPasswordMessage(t('profile.passwordTooShort', '新密码至少 6 位'), 'error');
                return;
            }
            if (newPassword !== confirmPassword) {
                showPasswordMessage(t('profile.passwordMismatch', '两次输入的新密码不一致'), 'error');
                return;
            }

            setPasswordBusy(true);
            try {
                await Auth.request('/api/auth/password', {
                    method: 'PUT',
                    body: JSON.stringify({
                        current_password: currentPassword,
                        new_password: newPassword,
                    }),
                });
                form.reset();
                showPasswordMessage(t('profile.passwordUpdated', '密码已更新，请使用新密码重新登录'), 'success');
                Auth.clearSession?.();
                window.setTimeout(() => {
                    window.location.href = `/login?return=${encodeURIComponent('/profile')}`;
                }, 900);
            } catch (error) {
                showPasswordMessage(error.message || t('profile.passwordFailed', '修改密码失败'), 'error');
                setPasswordBusy(false);
            }
        });
        $('[data-profile-api-form]')?.addEventListener('submit', (event) => {
            event.preventDefault();
            const store = window.GEOrank?.APIKeyStore;
            if (!store) return;
            const form = event.currentTarget;
            const data = new FormData(form);
            store.save({
                enabled: data.get('enabled') === 'on',
                provider: data.get('provider'),
                baseUrl: data.get('baseUrl'),
                model: data.get('model'),
                apiKey: data.get('apiKey'),
            });
            renderApiKeyForm();
            window.GEOrank?.Auth?.showToast?.('API Key 设置已保存在当前浏览器');
        });
        $('[data-profile-api-clear]')?.addEventListener('click', () => {
            window.GEOrank?.APIKeyStore?.clear?.();
            renderApiKeyForm();
            window.GEOrank?.Auth?.showToast?.('本地 API Key 已清除');
        });
        document.addEventListener('georank:auth-changed', renderProfile);
        document.addEventListener('georank:auth-changed', () => void renderUsage());
        document.addEventListener('georank:locale-changed', renderProfile);
        document.addEventListener('georank:api-key-changed', renderApiKeyForm);
    }

    document.addEventListener('DOMContentLoaded', () => {
        bindProfile();
        window.setTimeout(renderProfile, 0);
        window.setTimeout(() => void renderUsage(), 0);
    });
})();
