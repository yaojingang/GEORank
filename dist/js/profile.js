/**
 * GEOrank user center.
 */
(function () {
    'use strict';

    const $ = (selector, root = document) => root.querySelector(selector);
    let usagePolicy = null;

    function apiBase() {
        return window.GEOrank?.Auth?.apiBase
            || (['80', '443', ''].includes(window.location.port)
                ? ''
                : `${window.location.protocol}//${window.location.hostname}:8000`);
    }

    function profilePath() {
        return window.GEOrank?.Routes?.buildUrl?.('/profile') || '/profile';
    }

    function loginPath() {
        const login = window.GEOrank?.Routes?.buildUrl?.('/login') || '/login';
        return `${login}?return=${encodeURIComponent(profilePath())}`;
    }

    function modeLabel(mode) {
        const labels = {
            platform_unlimited: ['profile.modePlatformUnlimited', '平台无限'],
            daily_quota: ['profile.modeDailyQuota', '每日额度'],
            quota_with_byok: ['profile.modeQuotaWithByok', '额度 + 自定义 Key'],
            lifetime_quota_with_byok: ['profile.modeLifetimeQuotaWithByok', '终身赠送额度 + 自备 API'],
            byok_required: ['profile.modeByokRequired', '必须自定义 Key'],
        };
        const label = labels[mode];
        return label ? t(label[0], label[1]) : (mode || t('profile.deviceNotConfigured', '未配置'));
    }

    function tokenLabel(value) {
        if (value === null || value === undefined) return t('profile.unlimited', '不限');
        return Number(value || 0).toLocaleString();
    }

    function t(key, fallback = '') {
        return window.GEOrank?.I18N?.t?.(key) || fallback || key;
    }

    function isValidBaseUrl(value) {
        try {
            const url = new URL(String(value || '').trim());
            return url.protocol === 'https:' || url.protocol === 'http:';
        } catch (_) {
            return false;
        }
    }

    function showMessage(selector, message, type = 'info') {
        const messageEl = $(selector);
        if (!messageEl) return;
        messageEl.textContent = message;
        messageEl.classList.remove('hidden', 'is-error', 'is-success');
        if (type === 'error') messageEl.classList.add('is-error');
        if (type === 'success') messageEl.classList.add('is-success');
    }

    function setBusy(selector, isBusy, idleLabel) {
        const submit = $(selector);
        if (!submit) return;
        submit.disabled = Boolean(isBusy);
        submit.textContent = isBusy ? t('profile.passwordSubmitting', '保存中...') : idleLabel;
    }

    function persistUser(user) {
        const Auth = window.GEOrank?.Auth;
        if (!Auth || !user) return;
        localStorage.setItem(Auth.USER_KEY, JSON.stringify(user));
        Auth.state.user = user;
        document.dispatchEvent(new CustomEvent('georank:auth-changed', {
            detail: { authenticated: true, user },
        }));
    }

    function renderProfile() {
        const Auth = window.GEOrank?.Auth;
        if (!Auth?.isAuthenticated?.()) {
            window.location.replace(loginPath());
            return;
        }

        const user = Auth.getUser?.();
        if (!user) return;

        const accountValue = $('[data-profile-account-value]');
        const userName = $('[data-profile-user-name]');
        const status = $('[data-profile-account-status]');
        const summary = $('[data-profile-account-summary]');
        const accountForm = $('[data-profile-account-form]');

        if (userName) userName.textContent = user.username || t('profile.signedInUser', '已登录用户');
        if (accountValue) accountValue.textContent = Auth.maskPhone(user.phone || user.username || '');
        if (status) status.textContent = t('profile.active', '启用中');
        if (summary) summary.textContent = [user.username, user.email].filter(Boolean).join(' · ') || t('profile.profileSummary', '用户名、邮箱');
        if (accountForm) {
            accountForm.elements.username.value = user.username || '';
            accountForm.elements.email.value = user.email || '';
            accountForm.elements.phone.value = user.phone || '';
        }
        setBusy('[data-profile-account-submit]', false, t('profile.saveProfile', '保存资料'));
        setBusy('[data-profile-password-submit]', false, t('profile.passwordSubmit', '保存新密码'));
        renderApiKeyForm();
    }

    async function renderUsage() {
        const Auth = window.GEOrank?.Auth;
        const token = Auth?.getToken?.();
        const headers = {
            ...(window.GEOrank?.DeviceIdentity?.getHeaders?.() || {}),
            ...(token ? {Authorization: `Bearer ${token}`} : {}),
        };
        try {
            const response = await fetch(`${apiBase()}/api/usage/me`, {headers});
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'usage failed');
            $('[data-api-usage-mode]').textContent = modeLabel(payload.access_mode);
            $('[data-api-usage-remaining]').textContent = tokenLabel(payload.remaining_tokens);
            $('[data-api-usage-used]').textContent = tokenLabel(payload.used_tokens);
            $('[data-api-usage-reserved]').textContent = tokenLabel(payload.reserved_tokens);
            $('[data-api-usage-global]').textContent = payload.global_budget
                ? `${tokenLabel(payload.global_budget.used_tokens)} / ${tokenLabel(payload.global_budget.limit_tokens)}`
                : '--';
            usagePolicy = payload;
            window.GEOrank?.APIKeyStore?.applyPolicy?.(payload);
            if (!payload.allow_user_byok) {
                window.GEOrank?.APIKeyStore?.clear?.();
            }
            renderApiKeyForm();

            const guidance = payload.byok_guidance || {};
            const guidancePanel = $('[data-api-guidance-panel]');
            if (guidancePanel) {
                guidancePanel.classList.toggle('hidden', Boolean(payload.platform_available));
                $('[data-api-guidance-title]').textContent = guidance.title || '使用自己的 API Key 继续';
                $('[data-api-guidance-message]').textContent = guidance.message || '平台额度当前不可用，请绑定自己的 API Key。';
                const guidanceLink = $('[data-api-guidance-link]');
                if (guidanceLink) {
                    guidanceLink.textContent = guidance.cta_label || '前往 DeepSeek 获取 API Key';
                    guidanceLink.href = guidance.official_url || 'https://platform.deepseek.com/api_keys';
                }
            }
        } catch (_) {
            $('[data-api-usage-mode]').textContent = t('profile.usageUnavailable', '读取失败');
            $('[data-api-usage-remaining]').textContent = '--';
            $('[data-api-usage-used]').textContent = '--';
            $('[data-api-usage-reserved]').textContent = '--';
            $('[data-api-usage-global]').textContent = '--';
        }
    }

    function renderApiKeyForm() {
        const store = window.GEOrank?.APIKeyStore;
        const form = $('[data-profile-api-form]');
        const statusEl = $('[data-api-key-status]');
        if (!store || !form) return;
        const config = store.read?.() || {};
        const providers = usagePolicy?.provider_presets || [];
        if (providers.length) {
            form.provider.innerHTML = providers.map(provider => (
                `<option value="${String(provider.key || '').replace(/["<>]/g, '')}">${String(provider.name || provider.key || '').replace(/[<>]/g, '')}</option>`
            )).join('');
        }
        const guidance = usagePolicy?.byok_guidance || {};
        const selectedProvider = providers.find(provider => provider.key === config.provider) || providers[0] || {};
        form.provider.value = config.provider || guidance.provider || selectedProvider.key || 'deepseek';
        form.baseUrl.value = config.baseUrl || selectedProvider.base_url || guidance.base_url || 'https://api.deepseek.com';
        form.model.value = config.model || selectedProvider.default_model || guidance.model || 'deepseek-chat';
        form.apiKey.value = config.apiKey || '';
        form.enabled.checked = Boolean(config.enabled && config.apiKey);
        const byokAllowed = usagePolicy?.allow_user_byok !== false;
        Array.from(form.elements).forEach(control => {
            control.disabled = !byokAllowed;
        });
        const configured = store.hasUsableKey?.();
        if (statusEl) {
            statusEl.textContent = configured
                ? `${t('profile.deviceConfigured', '此设备已配置')} · ${store.maskKey(config.apiKey)}`
                : t('profile.deviceNotConfigured', '此设备未配置');
            statusEl.classList.toggle('is-configured', Boolean(configured));
        }
    }

    function bindProfile() {
        $('[data-profile-logout]')?.addEventListener('click', () => {
            window.GEOrank?.Auth?.clearSession?.();
            window.location.href = loginPath();
        });

        $('[data-profile-account-form]')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const Auth = window.GEOrank?.Auth;
            const form = event.currentTarget;
            const username = form.elements.username?.value.trim() || '';
            const email = form.elements.email?.value.trim() || '';
            if (!username) {
                showMessage('[data-profile-account-message]', t('profile.usernameRequired', '请输入用户名'), 'error');
                return;
            }
            if (!email) {
                showMessage('[data-profile-account-message]', t('profile.emailRequired', '请输入邮箱'), 'error');
                return;
            }

            setBusy('[data-profile-account-submit]', true, t('profile.saveProfile', '保存资料'));
            try {
                const user = await Auth.request('/api/auth/me', {
                    method: 'PUT',
                    body: JSON.stringify({username, email}),
                });
                persistUser(user);
                showMessage('[data-profile-account-message]', t('profile.profileSaved', '账号资料已更新'), 'success');
                renderProfile();
            } catch (error) {
                showMessage('[data-profile-account-message]', error.message || t('profile.profileFailed', '账号资料更新失败'), 'error');
            } finally {
                setBusy('[data-profile-account-submit]', false, t('profile.saveProfile', '保存资料'));
            }
        });

        $('[data-profile-password-form]')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const Auth = window.GEOrank?.Auth;
            const form = event.currentTarget;
            const currentPassword = form.elements.currentPassword?.value || '';
            const newPassword = form.elements.newPassword?.value || '';
            const confirmPassword = form.elements.confirmPassword?.value || '';

            if (newPassword.length < 6) {
                showMessage('[data-profile-password-message]', t('profile.passwordTooShort', '新密码至少 6 位'), 'error');
                return;
            }
            if (newPassword !== confirmPassword) {
                showMessage('[data-profile-password-message]', t('profile.passwordMismatch', '两次输入的新密码不一致'), 'error');
                return;
            }

            setBusy('[data-profile-password-submit]', true, t('profile.passwordSubmit', '保存新密码'));
            try {
                await Auth.request('/api/auth/password', {
                    method: 'PUT',
                    body: JSON.stringify({
                        current_password: currentPassword,
                        new_password: newPassword,
                    }),
                });
                form.reset();
                Auth.clearSession?.();
                window.location.href = loginPath();
            } catch (error) {
                showMessage('[data-profile-password-message]', error.message || t('profile.passwordFailed', '修改密码失败'), 'error');
                setBusy('[data-profile-password-submit]', false, t('profile.passwordSubmit', '保存新密码'));
            }
        });

        $('[data-profile-api-form]')?.addEventListener('submit', (event) => {
            event.preventDefault();
            const store = window.GEOrank?.APIKeyStore;
            if (!store) return;
            if (usagePolicy?.allow_user_byok === false) {
                window.GEOrank?.Auth?.showToast?.('管理员当前已关闭用户自备 API。');
                return;
            }
            const data = new FormData(event.currentTarget);
            const config = {
                enabled: data.get('enabled') === 'on',
                provider: data.get('provider'),
                baseUrl: data.get('baseUrl'),
                model: data.get('model'),
                apiKey: data.get('apiKey'),
            };
            if (config.enabled && (!config.baseUrl || !config.model || !config.apiKey)) {
                window.GEOrank?.Auth?.showToast?.(t('profile.apiRequired', '启用 API Key 时，请完整填写 Base URL、Model 和 API Key'));
                return;
            }
            if (config.enabled && !isValidBaseUrl(config.baseUrl)) {
                window.GEOrank?.Auth?.showToast?.(t('profile.apiInvalidBaseUrl', 'Base URL 必须是有效的 HTTP 或 HTTPS 地址'));
                return;
            }
            try {
                store.save(config);
                renderApiKeyForm();
                window.GEOrank?.Auth?.showToast?.(t('profile.apiSaved', 'API Key 设置已保存在当前浏览器'));
            } catch (error) {
                window.GEOrank?.Auth?.showToast?.(error?.message || 'API Key 设置保存失败');
            }
        });

        $('[data-profile-api-clear]')?.addEventListener('click', () => {
            if (!window.confirm(t('profile.removeApiConfirm', '移除此设备保存的 API Key？'))) return;
            window.GEOrank?.APIKeyStore?.clear?.();
            renderApiKeyForm();
            window.GEOrank?.Auth?.showToast?.(t('profile.apiRemoved', '此设备的 API Key 已移除'));
        });

        document.addEventListener('georank:auth-changed', renderProfile);
        document.addEventListener('georank:api-key-changed', renderApiKeyForm);
        document.addEventListener('georank:locale-changed', () => {
            renderProfile();
            renderApiKeyForm();
            void renderUsage();
        });
    }

    async function initProfile() {
        const Auth = window.GEOrank?.Auth;
        if (!Auth?.isAuthenticated?.()) {
            window.location.replace(loginPath());
            return;
        }
        try {
            await Auth.fetchMe();
        } catch (_) {
            Auth.clearSession?.();
            window.location.replace(loginPath());
            return;
        }
        bindProfile();
        renderProfile();
        void renderUsage();
    }

    if (document.body) {
        void initProfile();
    } else {
        document.addEventListener('DOMContentLoaded', () => void initProfile(), { once: true });
    }
})();
