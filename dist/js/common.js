/**
 * GEOrank - 公共 JavaScript
 * GEO 智搜优化引擎 前端系统
 * 版本: 1.0.0
 */

(function() {
    'use strict';

    // ===== 全局命名空间 =====
    window.GEOrank = window.GEOrank || {};

    // ===== DOM 工具函数 =====
    const DOM = {
        /**
         * 获取元素
         * @param {string} selector - CSS选择器
         * @param {HTMLElement} context - 上下文元素
         * @returns {HTMLElement}
         */
        get(selector, context = document) {
            return context.querySelector(selector);
        },

        /**
         * 获取所有元素
         * @param {string} selector - CSS选择器
         * @param {HTMLElement} context - 上下文元素
         * @returns {NodeList}
         */
        getAll(selector, context = document) {
            return context.querySelectorAll(selector);
        },

        /**
         * 添加事件监听
         * @param {HTMLElement} element - 目标元素
         * @param {string} event - 事件名
         * @param {Function} handler - 处理函数
         */
        on(element, event, handler) {
            if (element) {
                element.addEventListener(event, handler);
            }
        },

        /**
         * 切换类名
         * @param {HTMLElement} element - 目标元素
         * @param {string} className - 类名
         */
        toggleClass(element, className) {
            if (element) {
                element.classList.toggle(className);
            }
        }
    };

    function apiBase() {
        return ['80', '443', ''].includes(window.location.port)
            ? ''
            : `${window.location.protocol}//${window.location.hostname}:8000`;
    }

    // ===== 公开站点设置 =====
    const SiteSettings = {
        defaults: {
            site_name: 'GEOrank',
            site_description: 'GEO 智搜优化引擎',
            analytics_tracking_code: '',
            navigation_menu: {
                items: [
                    { id: 'companies', label: '公司', url: '/companies', target: '_blank', enabled: true },
                    { id: 'diagnostic', label: '诊断', url: '/diagnostic', target: '_blank', enabled: true },
                    { id: 'solutions', label: '问答', url: '/solutions', target: '_blank', enabled: true },
                    { id: 'plans', label: '方案', url: '/plans', target: '_blank', enabled: true },
                    { id: 'keywords', label: '拓词', url: '/keywords', target: '_blank', enabled: true },
                    { id: 'tools', label: '工具', url: '/tools', target: '_blank', enabled: true },
                    { id: 'experts', label: '专家', url: '/experts', target: '_blank', enabled: true },
                    { id: 'tutorial', label: '教程', url: '/tutorial', target: '_blank', enabled: true },
                    { id: 'github', label: 'GitHub', url: 'https://github.com/yaojingang/GEORank', target: '_blank', enabled: true },
                ],
            },
        },
        state: {
            loaded: false,
            settings: null,
            promise: null,
        },

        async load() {
            if (this.state.loaded) return this.state.settings;
            if (!this.state.promise) {
                const controller = new AbortController();
                const timeout = window.setTimeout(() => controller.abort(), 2500);
                this.state.promise = fetch(`${apiBase()}/api/settings/public`, {
                    cache: 'no-store',
                    signal: controller.signal,
                })
                    .then(response => response.ok ? response.json() : null)
                    .then(payload => {
                        this.state.settings = this.normalize(payload);
                        this.state.loaded = true;
                        return this.state.settings;
                    })
                    .catch(() => {
                        this.state.settings = this.normalize(null);
                        this.state.loaded = true;
                        return this.state.settings;
                    })
                    .finally(() => {
                        window.clearTimeout(timeout);
                    });
            }
            return this.state.promise;
        },

        normalize(payload) {
            const cleanName = String(payload?.site_name || '').trim();
            const cleanDescription = String(payload?.site_description || '').trim();
            const analyticsCode = String(payload?.analytics_tracking_code || '').trim();
            return {
                site_name: cleanName || this.defaults.site_name,
                site_description: cleanDescription || this.defaults.site_description,
                analytics_tracking_code: analyticsCode,
                navigation_menu: this.normalizeNavigationMenu(payload?.navigation_menu),
            };
        },

        normalizeNavigationUrl(value) {
            const url = String(value || '').trim();
            if (!url) return '';
            if (url.startsWith('/') && !url.startsWith('//')) return url;
            if (url.startsWith('#') && url.length > 1) return url;
            try {
                const parsed = new URL(url);
                return ['http:', 'https:'].includes(parsed.protocol) && parsed.hostname ? url : '';
            } catch (_) {
                return '';
            }
        },

        normalizeNavigationMenu(value) {
            const source = Array.isArray(value?.items) && value.items.length
                ? value.items
                : this.defaults.navigation_menu.items;
            const items = source.slice(0, 12).map((item, index) => ({
                id: String(item?.id || `menu-${index + 1}`),
                label: String(item?.label || '').trim().slice(0, 40),
                url: this.normalizeNavigationUrl(item?.url),
                target: item?.target === '_self' ? '_self' : '_blank',
                enabled: item?.enabled !== false,
            })).filter(item => item.enabled && item.label && item.url);
            return {items: items.length ? items : this.defaults.navigation_menu.items.map(item => ({...item}))};
        },

        applyNavigation(root = document) {
            let replaced = false;
            root.querySelectorAll?.('[data-site-navigation]').forEach(container => {
                const mobile = container.dataset.navigationVariant === 'mobile';
                const currentLinks = Array.from(container.children).filter(node => node.matches?.('a[data-nav-link]'));
                const alreadyMatches = currentLinks.length === this.settings.navigation_menu.items.length
                    && currentLinks.every((link, index) => {
                        const item = this.settings.navigation_menu.items[index];
                        const currentTarget = link.getAttribute('target') || '_self';
                        return link.textContent.trim() === item.label
                            && link.getAttribute('href') === item.url
                            && currentTarget === item.target;
                    });
                if (alreadyMatches) return;

                const fragment = document.createDocumentFragment();
                this.settings.navigation_menu.items.forEach(item => {
                    const link = document.createElement('a');
                    link.href = item.url;
                    link.textContent = item.label;
                    link.dataset.navLink = '';
                    link.dataset.navigationItem = item.id;
                    link.className = mobile
                        ? 'font-manrope font-medium py-2 text-slate-600 dark:text-slate-400 hover:text-blue-500 transition-colors'
                        : 'font-manrope font-medium tracking-tight text-slate-600 dark:text-slate-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors';
                    link.setAttribute('target', item.target);
                    if (item.target === '_blank') {
                        link.setAttribute('rel', 'noopener noreferrer');
                    }
                    fragment.appendChild(link);
                });
                container.replaceChildren(fragment);
                replaced = true;
            });
            if (replaced) Navigation.highlightCurrentPage();
        },

        get settings() {
            return this.state.settings || this.defaults;
        },

        replaceBrand(text) {
            const name = this.settings.site_name;
            return String(text || '').replace(/\bgeo\s*rank\b/gi, name);
        },

        apply(root = document) {
            // 保留 HTML 自带的首屏文案，等待接口返回后再覆盖。
            if (!this.state.loaded) return;
            const settings = this.settings;
            const siteName = settings.site_name;
            const siteDescription = settings.site_description;
            if (!siteName) return;

            document.querySelectorAll('[data-logo-link]').forEach(link => {
                link.textContent = siteName;
                link.setAttribute('aria-label', siteName);
            });
            this.applyNavigation(root);

            root.querySelectorAll?.('[data-site-name]').forEach(element => {
                element.textContent = siteName;
            });
            root.querySelectorAll?.('[data-site-description]').forEach(element => {
                element.textContent = siteDescription;
            });

            const originalTitle = document.documentElement.dataset.georankOriginalTitle || document.title || '';
            if (!document.documentElement.dataset.georankOriginalTitle) {
                document.documentElement.dataset.georankOriginalTitle = originalTitle;
            }
            document.title = /\bgeo\s*rank\b/i.test(originalTitle)
                ? this.replaceBrand(originalTitle)
                : `${siteName} - ${siteDescription}`;

            const descriptionMeta = document.querySelector('meta[name="description"]');
            if (descriptionMeta && siteDescription) {
                descriptionMeta.setAttribute('content', siteDescription);
            }

            document.dispatchEvent(new CustomEvent('georank:site-settings-applied', {
                detail: { siteName, siteDescription },
            }));
        },

        init() {
            void this.load().then(() => this.apply());
            document.addEventListener('componentLoaded', () => this.apply());
            document.addEventListener('georank:locale-changed', () => this.apply());
        },
    };

    // ===== 网站统计代码注入 =====
    const AnalyticsInjector = {
        ROOT_ID: 'georank-analytics-code',

        isSensitiveContext() {
            const path = String(window.location.pathname || '').replace(/\.html$/, '');
            const sensitivePaths = [
                '/profile',
                '/solutions',
                '/keywords',
                '/plans',
                '/tools',
                '/diagnostic',
                '/submit-company',
            ];
            if (sensitivePaths.some(prefix => path === prefix || path.startsWith(`${prefix}/`))) {
                return true;
            }
            try {
                const config = JSON.parse(localStorage.getItem('georank_byok_config_v1') || 'null');
                return Boolean(config?.apiKey);
            } catch (_) {
                return true;
            }
        },

        clear() {
            const oldRoot = document.getElementById(this.ROOT_ID);
            if (oldRoot) oldRoot.remove();
        },

        appendNode(target, node) {
            if (node.nodeType === Node.TEXT_NODE && !node.textContent.trim()) return;
            if (node.nodeName.toLowerCase() === 'script') {
                const script = document.createElement('script');
                Array.from(node.attributes || []).forEach(attr => {
                    script.setAttribute(attr.name, attr.value);
                });
                script.text = node.textContent || '';
                target.appendChild(script);
                return;
            }
            target.appendChild(node.cloneNode(true));
        },

        inject(code) {
            this.clear();
            if (this.isSensitiveContext()) return;
            const html = String(code || '').trim();
            if (!html) return;
            const root = document.createElement('div');
            root.id = this.ROOT_ID;
            root.hidden = true;
            const template = document.createElement('template');
            template.innerHTML = html;
            (document.body || document.documentElement).appendChild(root);
            Array.from(template.content.childNodes).forEach(node => this.appendNode(root, node));
        },

        init() {
            SiteSettings.load().then(settings => {
                this.inject(settings.analytics_tracking_code);
            });
            document.addEventListener('georank:api-key-changed', event => {
                if (event.detail?.configured) this.clear();
            });
        },
    };

    // ===== 前台多语言 =====
    const I18N = {
        STORAGE_KEY: 'georank_locale',
        defaultLocale: 'zh-CN',
        supportedLocales: ['zh-CN', 'en-US'],
        state: {
            initialized: false,
            locale: 'zh-CN',
        },
        dictionaries: {
            'zh-CN': {
                'nav.companies': '公司',
                'nav.diagnostic': '诊断',
                'nav.solutions': '问答',
                'nav.plans': '方案',
                'nav.keywords': '拓词',
                'nav.tools': '工具',
                'nav.experts': '专家',
                'nav.tutorial': '教程',
                'header.submitCompany': '提交公司',
                'header.mobileMenu': '打开菜单',
                'home.submitCompany': '提交公司',
                'language.label': '语言切换',
                'language.zh': '中文',
                'language.en': 'English',
                'language.switchToZh': '切换到中文',
                'language.switchToEn': 'Switch to English',
                'auth.triggerSignedOut': '登录 / 个人中心',
                'auth.triggerSignedIn': '个人中心',
                'auth.accountCenter': '个人中心',
                'auth.login': '登录',
                'auth.register': '注册',
                'auth.loginOrRegister': '登录 / 注册',
                'auth.logout': '退出登录',
                'auth.currentAccount': '当前账号',
                'auth.signedOut': '未登录',
                'auth.signedIn': '已登录',
                'auth.close': '关闭',
                'auth.loginTitle': '手机号登录',
                'auth.registerTitle': '手机号注册',
                'auth.loginSubtitle': '输入手机号和密码即可继续使用功能页面。',
                'auth.registerSubtitle': '首次使用只需手机号和密码，提交后会自动注册并登录。',
                'auth.defaultSubtitle': '输入手机号和密码即可完成登录或注册。',
                'auth.browserHint': '当前浏览器仅绑定一个手机号，用于持续保存会话。',
                'auth.phone': '手机号',
                'auth.phonePlaceholder': '请输入手机号',
                'auth.password': '密码',
                'auth.passwordPlaceholder': '请输入密码',
                'auth.confirmPassword': '确认密码',
                'auth.confirmPasswordPlaceholder': '再次输入密码',
                'auth.passwordMismatch': '两次输入的密码不一致',
                'auth.remember': '保持登录',
                'auth.submitLogin': '登录',
                'auth.submitRegister': '注册并登录',
                'auth.submittingLogin': '登录中...',
                'auth.submittingRegister': '注册中...',
                'auth.openLoginPage': '打开登录页',
                'auth.openRegisterPage': '打开注册页',
                'auth.invalidBoundPhone': '当前浏览器已绑定手机号 {phone}，请使用该手机号继续登录或注册',
                'auth.invalidPhone': '请输入有效的手机号',
                'auth.invalidPassword': '密码至少 6 位',
                'auth.failed': '登录失败，请稍后重试',
                'auth.requireReason': '请先登录后继续使用该功能。',
                'auth.firstVisitReason': '注册或登录后可使用诊断、问答、方案、拓词等功能页面。',
                'auth.reasonSolutions': '登录后才可提问、保存和继续追问。',
                'auth.reasonKeywords': '登录后才可生成并保存拓词结果。',
                'auth.reasonDiagnostic': '登录后才可发起官网诊断并保存诊断报告。',
                'auth.toastSignedIn': '{phone} 已登录',
                'auth.standaloneLoginEyebrow': 'ACCOUNT ACCESS',
                'auth.standaloneRegisterEyebrow': 'CREATE ACCOUNT',
                'auth.standaloneLoginTitle': '登录 GEOrank',
                'auth.standaloneRegisterTitle': '注册并开始使用 GEOrank',
                'auth.standaloneLoginCopy': '使用手机号和密码即可完成登录，会话会长期保留在当前浏览器中。',
                'auth.standaloneRegisterCopy': '使用手机号和密码即可完成注册，会话会长期保留在当前浏览器中。',
                'auth.standaloneHint': '每个浏览器默认绑定一个手机号，用于稳定保存登录状态。',
                'auth.goLogin': '已有账号？去登录',
                'auth.goRegister': '没有账号？去注册',
                'profile.eyebrow': 'ACCOUNT SETTINGS',
                'profile.title': '个人中心',
                'profile.copy': '管理账户与模型调用设置。',
                'profile.accountTitle': '账号状态',
                'profile.accountSubtitle': '当前浏览器会保存你的登录状态，用于继续诊断、问答、方案和拓词流程。',
                'profile.statusLabel': '当前账号',
                'profile.signedOutCopy': '当前未登录。登录后可以保存诊断、问答和方案记录。',
                'profile.signedInCopy': '当前已登录，可以继续使用需要账号的功能页面。',
                'profile.login': '登录账号',
                'profile.register': '注册账号',
                'profile.logout': '退出登录',
                'profile.preferenceTitle': '偏好设置',
                'profile.languageTitle': '界面语言',
                'profile.languageCopy': '语言设置会保存在当前浏览器，并立即应用到前台公共导航和账号界面。',
                'profile.languageCurrent': '当前语言',
                'profile.languageZh': '中文',
                'profile.languageEn': 'English',
                'profile.securityTitle': '账号安全',
                'profile.passwordTitle': '修改密码',
                'profile.passwordCopy': '需要先输入当前密码。修改成功后会退出登录，请使用新密码重新登录。',
                'profile.currentPassword': '当前密码',
                'profile.newPassword': '新密码',
                'profile.confirmPassword': '确认新密码',
                'profile.currentPasswordPlaceholder': '请输入当前密码',
                'profile.newPasswordPlaceholder': '至少 6 位',
                'profile.confirmPasswordPlaceholder': '再次输入新密码',
                'profile.passwordSubmit': '保存新密码',
                'profile.passwordSubmitting': '保存中...',
                'profile.passwordLoginRequired': '请先登录后再修改密码',
                'profile.passwordMismatch': '两次输入的新密码不一致',
                'profile.passwordTooShort': '新密码至少 6 位',
                'profile.passwordUpdated': '密码已更新，请使用新密码重新登录',
                'profile.passwordFailed': '修改密码失败',
                'profile.stackLabel': '个人中心设置',
                'profile.signedInUser': '已登录用户',
                'profile.active': '启用中',
                'profile.modelApiEyebrow': 'MODEL API',
                'profile.modelApiTitle': '我的模型 API',
                'profile.modelApiCopy': '配置自己的模型服务，用于额度不足或自托管场景。密钥仅保存在当前浏览器。',
                'profile.deviceConfigured': '此设备已配置',
                'profile.deviceNotConfigured': '此设备未配置',
                'profile.currentMode': '当前模式',
                'profile.remainingTokens': '终身剩余额度',
                'profile.usedTokens': '终身已用',
                'profile.provider': '供应商',
                'profile.customProvider': '自定义 OpenAI-compatible',
                'profile.baseUrl': 'Base URL',
                'profile.model': 'Model',
                'profile.apiKey': 'API Key',
                'profile.apiKeyPlaceholder': '只保存在当前浏览器',
                'profile.enableApiKey': '启用我的 API Key',
                'profile.apiNote': '代理模式会在单次生成请求中临时发送密钥，服务端不会保存到数据库或写入日志。',
                'profile.saveApi': '保存设置',
                'profile.removeApi': '移除密钥',
                'profile.accountSecurity': '账户与安全',
                'profile.profileTitle': '个人资料',
                'profile.profileSummary': '用户名、邮箱',
                'profile.edit': '编辑',
                'profile.username': '用户名',
                'profile.email': '邮箱',
                'profile.phone': '手机号',
                'profile.saveProfile': '保存资料',
                'profile.passwordSummary': '修改后需要重新登录',
                'profile.change': '修改',
                'profile.loading': '读取中',
                'profile.unlimited': '不限',
                'profile.usageUnavailable': '读取失败',
                'profile.modePlatformUnlimited': '平台无限',
                'profile.modeDailyQuota': '每日额度',
                'profile.modeQuotaWithByok': '额度 + 自定义 Key',
                'profile.modeByokRequired': '必须自定义 Key',
                'profile.usernameRequired': '请输入用户名',
                'profile.emailRequired': '请输入邮箱',
                'profile.profileSaved': '账号资料已更新',
                'profile.profileFailed': '账号资料更新失败',
                'profile.apiSaved': 'API Key 设置已保存在当前浏览器',
                'profile.apiRemoved': '此设备的 API Key 已移除',
                'profile.removeApiConfirm': '移除此设备保存的 API Key？',
                'profile.apiRequired': '启用 API Key 时，请完整填写 Base URL、Model 和 API Key',
                'profile.apiInvalidBaseUrl': 'Base URL 必须是有效的 HTTP 或 HTTPS 地址',
                'profile.quickTitle': '快捷入口',
                'profile.quickSubmit': '提交公司',
                'profile.quickDiagnostic': 'GEO 诊断',
                'profile.quickPlans': '生成方案',
            },
            'en-US': {
                'nav.companies': 'Companies',
                'nav.diagnostic': 'Diagnostic',
                'nav.solutions': 'Q&A',
                'nav.plans': 'Plans',
                'nav.keywords': 'Keywords',
                'nav.tools': 'Tools',
                'nav.experts': 'Experts',
                'nav.tutorial': 'Tutorials',
                'header.submitCompany': 'Submit company',
                'header.mobileMenu': 'Open menu',
                'home.submitCompany': 'Submit company',
                'language.label': 'Language switcher',
                'language.zh': '中文',
                'language.en': 'English',
                'language.switchToZh': 'Switch to Chinese',
                'language.switchToEn': 'Switch to English',
                'auth.triggerSignedOut': 'Log in / Account',
                'auth.triggerSignedIn': 'Account center',
                'auth.accountCenter': 'Account center',
                'auth.login': 'Log in',
                'auth.register': 'Register',
                'auth.loginOrRegister': 'Log in / Register',
                'auth.logout': 'Log out',
                'auth.currentAccount': 'Current account',
                'auth.signedOut': 'Not signed in',
                'auth.signedIn': 'Signed in',
                'auth.close': 'Close',
                'auth.loginTitle': 'Phone login',
                'auth.registerTitle': 'Create account',
                'auth.loginSubtitle': 'Enter your phone number and password to continue.',
                'auth.registerSubtitle': 'Use a phone number and password. You will be registered and signed in automatically.',
                'auth.defaultSubtitle': 'Enter your phone number and password to log in or register.',
                'auth.browserHint': 'This browser is bound to one phone number to keep your session stable.',
                'auth.phone': 'Phone number',
                'auth.phonePlaceholder': 'Enter phone number',
                'auth.password': 'Password',
                'auth.passwordPlaceholder': 'Enter password',
                'auth.confirmPassword': 'Confirm password',
                'auth.confirmPasswordPlaceholder': 'Enter the password again',
                'auth.passwordMismatch': 'The two passwords do not match',
                'auth.remember': 'Keep me signed in',
                'auth.submitLogin': 'Log in',
                'auth.submitRegister': 'Register and log in',
                'auth.submittingLogin': 'Logging in...',
                'auth.submittingRegister': 'Registering...',
                'auth.openLoginPage': 'Open login page',
                'auth.openRegisterPage': 'Open register page',
                'auth.invalidBoundPhone': 'This browser is already bound to {phone}. Please continue with that phone number.',
                'auth.invalidPhone': 'Enter a valid phone number',
                'auth.invalidPassword': 'Password must be at least 6 characters',
                'auth.failed': 'Login failed. Please try again later.',
                'auth.requireReason': 'Please log in before using this feature.',
                'auth.firstVisitReason': 'Register or log in to use diagnostic, Q&A, plan, and keyword tools.',
                'auth.reasonSolutions': 'Log in to ask questions, save answers, and continue follow-ups.',
                'auth.reasonKeywords': 'Log in to generate and save keyword expansion results.',
                'auth.reasonDiagnostic': 'Log in to start website diagnostics and save reports.',
                'auth.toastSignedIn': '{phone} signed in',
                'auth.standaloneLoginEyebrow': 'ACCOUNT ACCESS',
                'auth.standaloneRegisterEyebrow': 'CREATE ACCOUNT',
                'auth.standaloneLoginTitle': 'Log in to GEOrank',
                'auth.standaloneRegisterTitle': 'Create your GEOrank account',
                'auth.standaloneLoginCopy': 'Use your phone number and password to log in. Your session stays on this browser.',
                'auth.standaloneRegisterCopy': 'Use your phone number and password to register. Your session stays on this browser.',
                'auth.standaloneHint': 'Each browser is bound to one phone number to keep the login state stable.',
                'auth.goLogin': 'Already have an account? Log in',
                'auth.goRegister': 'No account yet? Register',
                'profile.eyebrow': 'ACCOUNT SETTINGS',
                'profile.title': 'Account center',
                'profile.copy': 'Manage your account and model API settings.',
                'profile.accountTitle': 'Account status',
                'profile.accountSubtitle': 'This browser keeps your session for diagnostics, Q&A, plans, and keyword workflows.',
                'profile.statusLabel': 'Current account',
                'profile.signedOutCopy': 'You are not signed in. Sign in to save diagnostics, Q&A, and plan records.',
                'profile.signedInCopy': 'You are signed in and can continue using account-based workflows.',
                'profile.login': 'Log in',
                'profile.register': 'Register',
                'profile.logout': 'Log out',
                'profile.preferenceTitle': 'Preferences',
                'profile.languageTitle': 'Interface language',
                'profile.languageCopy': 'Language is saved in this browser and applies immediately to the public navigation and account UI.',
                'profile.languageCurrent': 'Current language',
                'profile.languageZh': '中文',
                'profile.languageEn': 'English',
                'profile.securityTitle': 'Account security',
                'profile.passwordTitle': 'Change password',
                'profile.passwordCopy': 'Enter your current password first. After the update, you will be signed out and should sign in again with the new password.',
                'profile.currentPassword': 'Current password',
                'profile.newPassword': 'New password',
                'profile.confirmPassword': 'Confirm new password',
                'profile.currentPasswordPlaceholder': 'Enter current password',
                'profile.newPasswordPlaceholder': 'At least 6 characters',
                'profile.confirmPasswordPlaceholder': 'Enter new password again',
                'profile.passwordSubmit': 'Save new password',
                'profile.passwordSubmitting': 'Saving...',
                'profile.passwordLoginRequired': 'Please sign in before changing your password',
                'profile.passwordMismatch': 'The two new passwords do not match',
                'profile.passwordTooShort': 'New password must be at least 6 characters',
                'profile.passwordUpdated': 'Password updated. Please sign in again with the new password',
                'profile.passwordFailed': 'Failed to change password',
                'profile.stackLabel': 'Account center settings',
                'profile.signedInUser': 'Signed-in user',
                'profile.active': 'Active',
                'profile.modelApiEyebrow': 'MODEL API',
                'profile.modelApiTitle': 'My model API',
                'profile.modelApiCopy': 'Configure your own model service for quota limits or self-hosted use. The key stays in this browser.',
                'profile.deviceConfigured': 'Configured on this device',
                'profile.deviceNotConfigured': 'Not configured on this device',
                'profile.currentMode': 'Current mode',
                'profile.remainingTokens': 'Lifetime remaining',
                'profile.usedTokens': 'Lifetime used',
                'profile.provider': 'Provider',
                'profile.customProvider': 'Custom OpenAI-compatible',
                'profile.baseUrl': 'Base URL',
                'profile.model': 'Model',
                'profile.apiKey': 'API Key',
                'profile.apiKeyPlaceholder': 'Stored in this browser only',
                'profile.enableApiKey': 'Use my API Key',
                'profile.apiNote': 'Proxy mode sends the key with a single generation request. The server does not persist it or write it to logs.',
                'profile.saveApi': 'Save settings',
                'profile.removeApi': 'Remove key',
                'profile.accountSecurity': 'Account and security',
                'profile.profileTitle': 'Account profile',
                'profile.profileSummary': 'Username and email',
                'profile.edit': 'Edit',
                'profile.username': 'Username',
                'profile.email': 'Email',
                'profile.phone': 'Phone',
                'profile.saveProfile': 'Save profile',
                'profile.passwordSummary': 'You will need to log in again after changing it',
                'profile.change': 'Change',
                'profile.loading': 'Loading',
                'profile.unlimited': 'Unlimited',
                'profile.usageUnavailable': 'Unavailable',
                'profile.modePlatformUnlimited': 'Platform unlimited',
                'profile.modeDailyQuota': 'Daily quota',
                'profile.modeQuotaWithByok': 'Quota + custom key',
                'profile.modeByokRequired': 'Custom key required',
                'profile.usernameRequired': 'Enter a username',
                'profile.emailRequired': 'Enter an email address',
                'profile.profileSaved': 'Account profile updated',
                'profile.profileFailed': 'Failed to update account profile',
                'profile.apiSaved': 'API Key settings saved in this browser',
                'profile.apiRemoved': 'The API Key was removed from this device',
                'profile.removeApiConfirm': 'Remove the API Key stored on this device?',
                'profile.apiRequired': 'Enter a Base URL, model, and API Key before enabling your key',
                'profile.apiInvalidBaseUrl': 'Base URL must be a valid HTTP or HTTPS address',
                'profile.quickTitle': 'Shortcuts',
                'profile.quickSubmit': 'Submit company',
                'profile.quickDiagnostic': 'GEO diagnostic',
                'profile.quickPlans': 'Generate plan',
            },
        },

        normalizeLocale(locale) {
            return this.supportedLocales.includes(locale) ? locale : this.defaultLocale;
        },

        getLocale() {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            return this.normalizeLocale(stored || this.defaultLocale);
        },

        setLocale(locale) {
            this.state.locale = this.normalizeLocale(locale);
            localStorage.setItem(this.STORAGE_KEY, this.state.locale);
            this.apply();
            document.dispatchEvent(new CustomEvent('georank:locale-changed', {
                detail: { locale: this.state.locale },
            }));
        },

        t(key, values = {}, fallback = '') {
            this.state.locale = this.getLocale();
            const dictionary = this.dictionaries[this.state.locale] || this.dictionaries[this.defaultLocale];
            const defaultDictionary = this.dictionaries[this.defaultLocale] || {};
            let text = dictionary[key] || defaultDictionary[key] || fallback || key;
            Object.entries(values || {}).forEach(([name, value]) => {
                text = text.replaceAll(`{${name}}`, String(value));
            });
            return SiteSettings.replaceBrand(text);
        },

        apply(root = document) {
            this.state.locale = this.getLocale();
            document.documentElement.lang = this.state.locale;
            document.documentElement.dataset.locale = this.state.locale;

            root.querySelectorAll?.('[data-i18n]').forEach((element) => {
                element.textContent = this.t(element.getAttribute('data-i18n') || '', {}, element.textContent || '');
            });
            root.querySelectorAll?.('[data-i18n-placeholder]').forEach((element) => {
                element.setAttribute('placeholder', this.t(element.getAttribute('data-i18n-placeholder') || '', {}, element.getAttribute('placeholder') || ''));
            });
            root.querySelectorAll?.('[data-i18n-aria-label]').forEach((element) => {
                element.setAttribute('aria-label', this.t(element.getAttribute('data-i18n-aria-label') || '', {}, element.getAttribute('aria-label') || ''));
            });
        },

        init() {
            if (this.state.initialized) return;
            this.state.initialized = true;
            this.state.locale = this.getLocale();
            this.apply();
            document.addEventListener('componentLoaded', () => {
                this.apply();
            });
        },
    };

    // ===== 首屏结构壳层（组件加载期间不暴露未绑定的交互控件） =====
    const HEADER_SHELL_HTML = `
<nav id="main-nav" class="fixed top-0 w-full z-50 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-b border-slate-100 dark:border-slate-800 shadow-[0_10px_40px_rgba(25,27,35,0.04)]" aria-hidden="true">
    <div class="flex justify-between items-center px-6 md:px-8 h-16 w-full max-w-7xl mx-auto">
        <div class="flex items-center gap-8">
            <span class="text-xl font-bold tracking-tighter text-blue-700 dark:text-blue-500 font-headline">GEOrank</span>
            <div class="hidden md:flex items-center gap-5" data-site-navigation data-navigation-variant="desktop">
                <span class="block h-4 w-12 rounded-full bg-slate-100 dark:bg-slate-800"></span>
                <span class="block h-4 w-12 rounded-full bg-slate-100 dark:bg-slate-800"></span>
                <span class="block h-4 w-12 rounded-full bg-slate-100 dark:bg-slate-800"></span>
                <span class="block h-4 w-12 rounded-full bg-slate-100 dark:bg-slate-800"></span>
            </div>
        </div>
        <span class="block h-10 w-10 rounded-full bg-slate-100 dark:bg-slate-800"></span>
    </div>
</nav>`;

    // ===== 内联模板（file:// 协议 fallback） =====
    const HEADER_HTML = `
<nav id="main-nav" class="fixed top-0 w-full z-50 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-b border-slate-100 dark:border-slate-800 shadow-[0_10px_40px_rgba(25,27,35,0.04)]">
    <div class="flex justify-between items-center px-6 md:px-8 h-16 w-full max-w-7xl mx-auto">
        <div class="flex items-center gap-8">
            <a href="/" data-logo-link class="text-xl font-bold tracking-tighter text-blue-700 dark:text-blue-500 font-headline hover:opacity-90 transition-opacity">
                GEOrank
            </a>
            <div class="hidden md:flex items-center gap-5" data-site-navigation data-navigation-variant="desktop">
                <a href="/companies" data-nav-link data-i18n="nav.companies" class="font-manrope font-medium tracking-tight text-slate-600 dark:text-slate-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors">公司</a>
                <a href="/diagnostic" data-nav-link data-i18n="nav.diagnostic" class="font-manrope font-medium tracking-tight text-slate-600 dark:text-slate-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors">诊断</a>
                <a href="/solutions" data-nav-link data-i18n="nav.solutions" class="font-manrope font-medium tracking-tight text-slate-600 dark:text-slate-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors">问答</a>
                <a href="/plans" data-nav-link data-i18n="nav.plans" class="font-manrope font-medium tracking-tight text-slate-600 dark:text-slate-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors">方案</a>
                <a href="/keywords" data-nav-link data-i18n="nav.keywords" class="font-manrope font-medium tracking-tight text-slate-600 dark:text-slate-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors">拓词</a>
                <a href="/tools" data-nav-link data-i18n="nav.tools" class="font-manrope font-medium tracking-tight text-slate-600 dark:text-slate-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors">工具</a>
                <a href="/experts" data-nav-link data-i18n="nav.experts" class="font-manrope font-medium tracking-tight text-slate-600 dark:text-slate-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors">专家</a>
                <a href="/tutorial" data-nav-link data-i18n="nav.tutorial" class="font-manrope font-medium tracking-tight text-slate-600 dark:text-slate-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors">教程</a>
            </div>
        </div>
        <div class="header-actions flex items-center gap-2 md:gap-3">
            <a href="/login" data-auth-trigger data-profile-link class="auth-trigger header-profile-button" aria-label="登录 / 个人中心" data-i18n-aria-label="auth.triggerSignedOut">
                <span class="header-profile-button__icon" aria-hidden="true">
                    <span class="material-symbols-outlined">person</span>
                </span>
                <span class="sr-only" data-auth-trigger-label data-i18n="auth.login">登录</span>
            </a>
            <button id="mobile-menu-toggle" class="md:hidden w-10 h-10 flex items-center justify-center rounded-full hover:bg-slate-50 dark:hover:bg-slate-800" aria-label="打开菜单" data-i18n-aria-label="header.mobileMenu">
                <span class="material-symbols-outlined text-slate-600 dark:text-slate-400">menu</span>
            </button>
        </div>
    </div>
    <div id="mobile-menu" class="hidden md:hidden bg-white dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800">
        <div class="flex flex-col px-6 py-4 space-y-3" data-site-navigation data-navigation-variant="mobile">
            <a href="/companies" data-nav-link data-i18n="nav.companies" class="font-manrope font-medium py-2 text-slate-600 dark:text-slate-400 hover:text-blue-500 transition-colors">公司</a>
            <a href="/diagnostic" data-nav-link data-i18n="nav.diagnostic" class="font-manrope font-medium py-2 text-slate-600 dark:text-slate-400 hover:text-blue-500 transition-colors">诊断</a>
            <a href="/solutions" data-nav-link data-i18n="nav.solutions" class="font-manrope font-medium py-2 text-slate-600 dark:text-slate-400 hover:text-blue-500 transition-colors">问答</a>
            <a href="/plans" data-nav-link data-i18n="nav.plans" class="font-manrope font-medium py-2 text-slate-600 dark:text-slate-400 hover:text-blue-500 transition-colors">方案</a>
            <a href="/keywords" data-nav-link data-i18n="nav.keywords" class="font-manrope font-medium py-2 text-slate-600 dark:text-slate-400 hover:text-blue-500 transition-colors">拓词</a>
            <a href="/tools" data-nav-link data-i18n="nav.tools" class="font-manrope font-medium py-2 text-slate-600 dark:text-slate-400 hover:text-blue-500 transition-colors">工具</a>
            <a href="/experts" data-nav-link data-i18n="nav.experts" class="font-manrope font-medium py-2 text-slate-600 dark:text-slate-400 hover:text-blue-500 transition-colors">专家</a>
            <a href="/tutorial" data-nav-link data-i18n="nav.tutorial" class="font-manrope font-medium py-2 text-slate-600 dark:text-slate-400 hover:text-blue-500 transition-colors">教程</a>
        </div>
    </div>
</nav>`;

const FOOTER_HTML = `
<footer class="w-full mt-auto border-t border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-950">
    <div class="max-w-7xl mx-auto px-6 md:px-8 py-6">
        <p class="font-inter text-sm text-slate-400 dark:text-slate-500 text-center" data-footer-rights>© 2026 GEORankHub · 公益性 GEO 研究平台 · 独立第三方 · <strong><a href="https://github.com/yaojingang/GEORank" target="_blank" rel="noopener noreferrer">GitHub</a>开源</strong></p>
    </div>
</footer>`;

    const COMPONENT_LOAD_TIMEOUT_MS = 2500;

    // ===== 组件加载器 =====
    const ComponentLoader = {
        /** 立即挂载内联壳层，避免远程组件加载期间出现空白区域 */
        mountFallbacks() {
            const header = DOM.get('#header-container');
            const footer = DOM.get('#footer-container');
            if (header && !header.innerHTML.trim()) header.innerHTML = HEADER_SHELL_HTML;
            if (footer && !footer.innerHTML.trim()) footer.innerHTML = FOOTER_HTML;
        },

        /** 兼容旧 HTML 与旧 CSS 缓存，避免新版脚本不再恢复透明度后永久白屏 */
        revealLegacyDocument() {
            const body = document.body;
            if (!body || getComputedStyle(body).opacity !== '0') return;
            body.style.opacity = '1';
            body.style.transition = 'none';
        },

        /**
         * 加载HTML组件 — 先尝试 fetch，失败则用内联模板
         */
        async load(url, targetSelector, fallbackHTML) {
            const target = DOM.get(targetSelector);
            if (!target) return null;
            const controller = new AbortController();
            const timeout = window.setTimeout(() => controller.abort(), COMPONENT_LOAD_TIMEOUT_MS);

            try {
                const response = await fetch(url, {
                    cache: 'no-store',
                    signal: controller.signal,
                });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const html = await response.text();
                target.innerHTML = html;
            } catch (error) {
                console.warn('[GEOrank] component load failed; using fallback', {
                    url,
                    error: error?.name || 'Error',
                });
                // file:// 协议或网络错误，使用内联模板
                if (fallbackHTML) {
                    target.innerHTML = fallbackHTML;
                }
            } finally {
                window.clearTimeout(timeout);
            }
            document.dispatchEvent(new CustomEvent('componentLoaded', {
                detail: { url, targetSelector }
            }));
            return target.innerHTML;
        },

        /** 加载头部组件 */
        async loadHeader() {
            const header = DOM.get('#header-container');
            if (header?.dataset.prerendered !== 'true') {
                await this.load('/components/header.html', '#header-container', HEADER_HTML);
            }
            Navigation.init();
            I18N.apply();
            SiteSettings.apply();
            await ModuleGate.load();
            ModuleGate.applyHeader();
        },

        /** 加载底部组件 */
        async loadFooter() {
            await this.load('/components/footer.html', '#footer-container', FOOTER_HTML);
            I18N.apply();
            SiteSettings.apply();
        },

        /** 初始化所有公共组件 */
        async initAll() {
            await Promise.all([
                this.loadHeader(),
                this.loadFooter()
            ]);
        }
    };

    // ===== 公共路由规则 =====
    const Routes = {
        normalizePath(pathname = window.location.pathname) {
            const path = String(pathname || '').replace(/\.html$/, '').replace(/\/+$/, '');
            return path || '/';
        },

        getSegments(pathname = window.location.pathname) {
            const normalized = this.normalizePath(pathname);
            return normalized.split('/').filter(Boolean);
        },

        buildUrl(path, query = {}) {
            const url = new URL(path || '/', window.location.origin);
            Object.entries(query || {}).forEach(([key, value]) => {
                if (value == null || value === '') return;
                url.searchParams.set(key, value);
            });
            return url.toString();
        },

        getModulePath(pathname = window.location.pathname) {
            const normalized = this.normalizePath(pathname);
            if (normalized === '/' || normalized === '/index') return '/';
            if (normalized === '/company' || normalized === '/companies' || normalized.startsWith('/companies/') || normalized === '/c' || normalized.startsWith('/c/')) return '/companies';
            if (normalized === '/submit-company' || normalized === '/company-submit') return '/companies';
            if (normalized === '/diagnostic' || normalized.startsWith('/diagnostic/')) return '/diagnostic';
            if (normalized === '/solutions' || normalized.startsWith('/solutions/')) return '/solutions';
            if (normalized === '/plans' || normalized.startsWith('/plans/')) return '/plans';
            if (normalized === '/keywords' || normalized.startsWith('/keywords/')) return '/keywords';
            if (normalized === '/tools' || normalized.startsWith('/tools/')) return '/tools';
            if (normalized === '/experts' || normalized.startsWith('/experts/')) return '/experts';
            if (normalized === '/profile') return '/profile';
            if (normalized === '/tutorial' || normalized.startsWith('/tutorial/')) return '/tutorial';
            return normalized;
        },

        buildCompanyDetail(companyIdentifier, query = {}) {
            if (!companyIdentifier) return this.buildUrl('/companies', query);
            return this.buildUrl(`/c/${encodeURIComponent(companyIdentifier)}`, query);
        },

        buildCompanySubmission({ url = '', companyId = '' } = {}) {
            return this.buildUrl('/submit-company', {
                url,
                company: companyId,
            });
        },

        readCompanySubmissionState() {
            const params = new URLSearchParams(window.location.search);
            return {
                url: params.get('url') || '',
                companyId: params.get('company') || '',
            };
        },

        readCompanyId() {
            const segments = this.getSegments();
            if (segments[0] === 'c' && segments[1]) {
                return decodeURIComponent(segments[1]);
            }
            if (segments[0] === 'companies' && segments[1]) {
                return decodeURIComponent(segments[1]);
            }
            return new URLSearchParams(window.location.search).get('id') || '';
        },

        buildTutorialDetail(slug, query = {}) {
            if (!slug) return this.buildUrl('/tutorial', query);
            return this.buildUrl(`/tutorial/${encodeURIComponent(slug)}`, query);
        },

        readTutorialSlug() {
            const segments = this.getSegments();
            if (segments[0] === 'tutorial' && segments[1]) {
                return decodeURIComponent(segments[1]);
            }
            return new URLSearchParams(window.location.search).get('slug') || '';
        },

        buildDiagnosticPath({ reportId = '', url = '', companyId = '' } = {}) {
            const base = reportId
                ? `/diagnostic/reports/${encodeURIComponent(reportId)}`
                : '/diagnostic';
            return this.buildUrl(base, {
                url,
                company_id: companyId,
            });
        },

        readDiagnosticState() {
            const params = new URLSearchParams(window.location.search);
            const segments = this.getSegments();
            let reportId = '';
            if (segments[0] === 'diagnostic' && segments[1] === 'reports' && segments[2]) {
                reportId = decodeURIComponent(segments[2]);
            }
            return {
                reportId: reportId || params.get('report') || params.get('report_id') || '',
                url: params.get('url') || '',
                companyId: params.get('company_id') || '',
            };
        },

        buildSolutionPath({
            conversationId = '',
            diagnosticReportId = '',
            companyId = '',
            url = '',
            prompt = '',
            channelKey = '',
        } = {}) {
            const base = conversationId
                ? `/solutions/conversations/${encodeURIComponent(conversationId)}`
                : '/solutions';
            return this.buildUrl(base, {
                report: diagnosticReportId,
                company_id: companyId,
                url,
                prompt,
                channel: channelKey,
            });
        },

        readSolutionState() {
            const params = new URLSearchParams(window.location.search);
            const segments = this.getSegments();
            let conversationId = '';
            if (segments[0] === 'solutions' && segments[1] === 'conversations' && segments[2]) {
                conversationId = decodeURIComponent(segments[2]);
            }
            return {
                conversationId: conversationId || params.get('conversation') || params.get('conversation_id') || '',
                diagnosticReportId: params.get('report') || params.get('report_id') || params.get('diagnostic_report_id') || '',
                companyId: params.get('company_id') || '',
                sourceUrl: params.get('url') || '',
                prompt: params.get('prompt') || '',
                channelKey: params.get('channel') || params.get('channel_key') || '',
            };
        },

        buildPlanPath({
            diagnosticReportId = '',
            companyId = '',
            url = '',
            prompt = '',
        } = {}) {
            return this.buildUrl('/plans', {
                report: diagnosticReportId,
                company_id: companyId,
                url,
                prompt,
            });
        },

        readPlanState() {
            const params = new URLSearchParams(window.location.search);
            return {
                diagnosticReportId: params.get('report') || params.get('report_id') || params.get('diagnostic_report_id') || '',
                companyId: params.get('company_id') || '',
                sourceUrl: params.get('url') || '',
                prompt: params.get('prompt') || '',
            };
        },
    };

    window.GEOrank.Routes = Routes;

    const Canonicalizer = {
        getCanonicalUrl() {
            const current = new URL(window.location.href);
            const rawPath = String(current.pathname || '');
            const normalizedPath = Routes.normalizePath(rawPath);
            const params = current.searchParams;

            if (rawPath === '/index.html' || normalizedPath === '/index') {
                return Routes.buildUrl('/companies');
            }

            if (rawPath === '/company.html') {
                return params.get('id')
                    ? Routes.buildCompanyDetail(params.get('id'))
                    : Routes.buildUrl('/companies');
            }

            if (normalizedPath === '/company') {
                return params.get('id')
                    ? Routes.buildCompanyDetail(params.get('id'))
                    : Routes.buildUrl('/companies');
            }

            if (rawPath === '/tutorial.html') {
                return params.get('slug')
                    ? Routes.buildTutorialDetail(params.get('slug'))
                    : Routes.buildUrl('/tutorial');
            }

            if (normalizedPath === '/tutorial' && params.get('slug')) {
                return Routes.buildTutorialDetail(params.get('slug'));
            }

            if (rawPath === '/diagnostic.html') {
                return Routes.buildDiagnosticPath({
                    reportId: params.get('report') || params.get('report_id') || '',
                    url: params.get('url') || '',
                    companyId: params.get('company_id') || '',
                });
            }

            if (normalizedPath === '/diagnostic' && (params.get('report') || params.get('report_id'))) {
                return Routes.buildDiagnosticPath({
                    reportId: params.get('report') || params.get('report_id') || '',
                    url: params.get('url') || '',
                    companyId: params.get('company_id') || '',
                });
            }

            if (rawPath === '/solutions.html') {
                return Routes.buildSolutionPath({
                    conversationId: params.get('conversation') || params.get('conversation_id') || '',
                    diagnosticReportId: params.get('report') || params.get('report_id') || params.get('diagnostic_report_id') || '',
                    companyId: params.get('company_id') || '',
                    url: params.get('url') || '',
                    prompt: params.get('prompt') || '',
                    channelKey: params.get('channel') || params.get('channel_key') || '',
                });
            }

            if (rawPath === '/plans.html') {
                return Routes.buildPlanPath({
                    diagnosticReportId: params.get('report') || params.get('report_id') || params.get('diagnostic_report_id') || '',
                    companyId: params.get('company_id') || '',
                    url: params.get('url') || '',
                    prompt: params.get('prompt') || '',
                });
            }

            if (normalizedPath === '/solutions' && (params.get('conversation') || params.get('conversation_id'))) {
                return Routes.buildSolutionPath({
                    conversationId: params.get('conversation') || params.get('conversation_id') || '',
                    diagnosticReportId: params.get('report') || params.get('report_id') || params.get('diagnostic_report_id') || '',
                    companyId: params.get('company_id') || '',
                    url: params.get('url') || '',
                    prompt: params.get('prompt') || '',
                    channelKey: params.get('channel') || params.get('channel_key') || '',
                });
            }

            if (rawPath === '/keywords.html') {
                return Routes.buildUrl('/keywords');
            }

            if (rawPath === '/tools.html') {
                return Routes.buildUrl('/tools');
            }

            if (rawPath === '/experts.html') {
                return Routes.buildUrl('/experts');
            }

            if (rawPath === '/profile.html') {
                return Routes.buildUrl('/profile');
            }

            if (
                rawPath === '/diagnostic.html' ||
                rawPath === '/solutions.html' ||
                rawPath === '/plans.html' ||
                rawPath === '/tools.html' ||
                rawPath === '/experts.html' ||
                rawPath === '/profile.html' ||
                rawPath === '/tutorial.html' ||
                rawPath === '/keywords.html'
            ) {
                return Routes.buildUrl(normalizedPath || '/');
            }

            return '';
        },

        apply() {
            const canonicalUrl = this.getCanonicalUrl();
            if (!canonicalUrl) return;

            const currentUrl = window.location.href;
            if (canonicalUrl === currentUrl) return;

            window.history.replaceState(window.history.state || null, '', canonicalUrl);
        },
    };

    window.GEOrank.Canonicalizer = Canonicalizer;
    Canonicalizer.apply();

    // ===== 前台模块开关 =====
    const ModuleGate = {
        defaults: {
            default_module: 'companies',
            modules: [
                { key: 'companies', name: '公司', path: '/companies', enabled: true, protected_paths: ['/company', '/companies', '/c', '/submit-company'] },
                { key: 'diagnostic', name: '诊断', path: '/diagnostic', enabled: true, protected_paths: ['/diagnostic'] },
                { key: 'solutions', name: '问答', path: '/solutions', enabled: true, protected_paths: ['/solutions'] },
                { key: 'plans', name: '方案', path: '/plans', enabled: true, protected_paths: ['/plans'] },
                { key: 'keywords', name: '拓词', path: '/keywords', enabled: true, protected_paths: ['/keywords'] },
                { key: 'tools', name: '工具', path: '/tools', enabled: true, protected_paths: ['/tools'] },
                { key: 'experts', name: '专家', path: '/experts', enabled: true, protected_paths: ['/experts'] },
                { key: 'tutorial', name: '教程', path: '/tutorial', enabled: true, protected_paths: ['/tutorial'] },
            ],
        },
        state: {
            config: null,
            homepage: null,
            promise: null,
        },
        modulePathToKey: {
            '/companies': 'companies',
            '/diagnostic': 'diagnostic',
            '/solutions': 'solutions',
            '/plans': 'plans',
            '/keywords': 'keywords',
            '/tools': 'tools',
            '/experts': 'experts',
            '/tutorial': 'tutorial',
        },

        async load() {
            if (this.state.config) return this.state.config;
            if (!this.state.promise) {
                const controller = new AbortController();
                const timeout = window.setTimeout(() => controller.abort(), 2500);
                this.state.promise = Promise.all([
                    fetch(`${apiBase()}/api/settings/frontend-modules`, {
                        cache: 'no-store',
                        signal: controller.signal,
                    }).then(response => response.ok ? response.json() : null),
                    fetch(`${apiBase()}/api/settings/homepage`, {
                        cache: 'no-store',
                        signal: controller.signal,
                    }).then(response => response.ok ? response.json() : null),
                ])
                    .then(([modulePayload, homepagePayload]) => {
                        this.state.homepage = this.normalizeHomepage(homepagePayload);
                        this.state.config = this.normalizeConfig(modulePayload);
                        return this.state.config;
                    })
                    .catch(() => {
                        this.state.homepage = this.normalizeHomepage(null);
                        this.state.config = this.normalizeConfig(null);
                        return this.state.config;
                    })
                    .finally(() => {
                        window.clearTimeout(timeout);
                    });
            }
            return this.state.promise;
        },

        normalizeHomepage(payload) {
            const companyListPath = Routes.normalizePath(payload?.company_list_path || '/companies');
            return {
                mode: payload?.mode === 'custom' ? 'custom' : 'default',
                active: Boolean(payload?.active && payload?.mode === 'custom'),
                active_release_id: payload?.active_release_id || null,
                company_list_path: companyListPath === '/' ? '/companies' : companyListPath,
                fallback_enabled: payload?.fallback_enabled !== false,
            };
        },

        homepageActive() {
            return Boolean(this.state.homepage?.active);
        },

        companyListPath() {
            return this.state.homepage?.company_list_path || '/companies';
        },

        normalizeConfig(payload) {
            const defaults = this.defaults;
            const rawModules = Array.isArray(payload?.modules) ? payload.modules : [];
            const rawByKey = new Map(rawModules.map(item => [String(item.key || '').toLowerCase(), item]));
            const modules = defaults.modules.map(item => {
                const raw = rawByKey.get(item.key) || {};
                return {
                    ...item,
                    name: raw.name || item.name,
                    path: item.key === 'companies' ? this.companyListPath() : (raw.path || item.path),
                    protected_paths: item.key === 'companies'
                        ? item.protected_paths
                        : (Array.isArray(raw.protected_paths) ? raw.protected_paths : item.protected_paths),
                    enabled: raw.enabled !== false,
                };
            });
            if (!modules.some(item => item.enabled)) {
                modules.forEach(item => {
                    item.enabled = item.key === defaults.default_module;
                });
            }
            let defaultModule = String(payload?.default_module || defaults.default_module).toLowerCase();
            if (!modules.some(item => item.key === defaultModule && item.enabled)) {
                defaultModule = modules.find(item => item.enabled)?.key || defaults.default_module;
            }
            return { default_module: defaultModule, modules };
        },

        get modules() {
            return this.state.config?.modules || this.defaults.modules;
        },

        getModule(key) {
            return this.modules.find(item => item.key === key) || null;
        },

        defaultPath() {
            const module = this.getModule(this.state.config?.default_module || this.defaults.default_module)
                || this.modules.find(item => item.enabled);
            return module?.path || '/';
        },

        moduleKeyForPath(pathname = window.location.pathname) {
            const normalized = Routes.normalizePath(pathname);
            if (normalized.startsWith('/admin') || normalized === '/profile' || normalized === '/login' || normalized === '/register') {
                return null;
            }
            const modulePath = Routes.getModulePath(normalized);
            return this.modulePathToKey[modulePath] || null;
        },

        moduleKeyForHref(href) {
            if (!href || href.startsWith('#') || /^(mailto|tel|javascript):/i.test(href)) return null;
            try {
                const url = new URL(href, window.location.origin);
                if (url.origin !== window.location.origin) return null;
                return this.moduleKeyForPath(url.pathname);
            } catch (_) {
                return null;
            }
        },

        isEnabled(key) {
            if (!key) return true;
            const module = this.getModule(key);
            return !module || module.enabled !== false;
        },

        applyHeader() {
            document.querySelectorAll('[data-logo-link]').forEach(link => {
                link.setAttribute('href', '/');
            });
            document.querySelectorAll('[data-nav-link][data-i18n="nav.companies"]').forEach(link => {
                link.setAttribute('href', this.companyListPath());
            });
            document.querySelectorAll('[data-nav-link]').forEach(link => {
                const key = this.moduleKeyForHref(link.getAttribute('href') || '');
                link.classList.toggle('hidden', Boolean(key && !this.isEnabled(key)));
            });
        },

        applyLinks(root = document) {
            root.querySelectorAll('a[href]').forEach(link => {
                if (link.closest('#main-nav') || link.hasAttribute('data-logo-link')) return;
                const key = this.moduleKeyForHref(link.getAttribute('href') || '');
                if (!key || this.isEnabled(key)) return;
                link.classList.add('frontend-module-link-disabled');
                link.setAttribute('aria-disabled', 'true');
                link.setAttribute('tabindex', '-1');
                link.addEventListener('click', event => event.preventDefault());
            });
        },

        guardCurrentPage() {
            const key = this.moduleKeyForPath(window.location.pathname);
            if (!key || this.isEnabled(key)) return true;
            if (Routes.normalizePath(window.location.pathname) === '/') {
                window.location.replace(this.defaultPath());
                return false;
            }
            this.renderUnavailable(key);
            return false;
        },

        renderUnavailable(key) {
            const module = this.getModule(key);
            const siteName = window.GEOrank?.SiteSettings?.settings?.site_name || 'GEOrank';
            document.title = `${module?.name || '模块'}暂未开放 - ${siteName}`;
            const main = document.querySelector('main') || document.createElement('main');
            main.className = 'frontend-module-unavailable';
            main.innerHTML = `
                <section class="frontend-module-unavailable__card">
                    <p class="frontend-module-unavailable__eyebrow">MODULE CLOSED</p>
                    <h1>该模块暂未开放</h1>
                    <p>管理员已关闭“${this.escape(module?.name || '该')}”频道。你可以返回当前默认开放模块继续使用 ${this.escape(siteName)}。</p>
                    <a href="${this.defaultPath()}" class="frontend-module-unavailable__button">返回默认模块</a>
                </section>
            `;
            if (!main.parentElement) {
                const footer = document.getElementById('footer-container');
                document.body.insertBefore(main, footer || null);
            }
        },

        escape(text) {
            return String(text || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        },
    };

    window.GEOrank.ModuleGate = ModuleGate;

    // ===== 页面可用性生命周期 =====
    const PageLifecycle = {
        state: {
            promise: null,
        },

        whenDomReady() {
            if (document.body && document.querySelector('main')) return Promise.resolve();
            return new Promise(resolve => {
                document.addEventListener('DOMContentLoaded', resolve, { once: true });
            });
        },

        setPending(pending) {
            const main = document.querySelector('main');
            if (!main) return;
            if (pending) {
                main.setAttribute('inert', '');
                main.setAttribute('aria-busy', 'true');
                return;
            }
            main.removeAttribute('inert');
            main.removeAttribute('aria-busy');
        },

        whenAvailable() {
            if (!this.state.promise) {
                this.setPending(true);
                this.state.promise = Promise.all([
                    this.whenDomReady(),
                    ModuleGate.load(),
                ]).then(() => {
                    ModuleGate.applyHeader();
                    const available = ModuleGate.guardCurrentPage();
                    if (available) ModuleGate.applyLinks();
                    this.setPending(false);
                    if (available) {
                        document.dispatchEvent(new CustomEvent('georank:page-available', {
                            detail: { path: window.location.pathname },
                        }));
                    }
                    return available;
                });
            }
            return this.state.promise;
        },

        run(callback) {
            return this.whenAvailable()
                .then(available => available ? callback() : undefined)
                .catch(error => {
                    this.setPending(false);
                    console.error('[GEOrank] page initialization failed', {
                        error: error?.name || 'Error',
                    });
                });
        },
    };

    window.GEOrank.PageLifecycle = PageLifecycle;

    // ===== 风控设备身份 =====
    // 随机 ID 保持同一浏览器稳定。
    // 服务端只保存 SHA-256 摘要，前端原始值不会写入业务数据。
    const DeviceIdentity = {
        STORAGE_KEY: 'georank_device_id_v1',

        createId() {
            if (window.crypto?.randomUUID) return window.crypto.randomUUID();
            return `device-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
        },

        getOrCreateId() {
            const stored = localStorage.getItem(this.STORAGE_KEY)?.trim() || '';
            if (stored.length >= 16) return stored;
            const deviceId = this.createId();
            localStorage.setItem(this.STORAGE_KEY, deviceId);
            return deviceId;
        },

        getHeaders() {
            const deviceId = this.getOrCreateId();
            return { 'X-GEOrank-Device-ID': deviceId };
        },
    };

    window.GEOrank.DeviceIdentity = DeviceIdentity;

    // ===== 公共认证 =====
    const Auth = {
        TOKEN_KEY: 'georank_user_token',
        USER_KEY: 'georank_user_profile',
        BOUND_PHONE_KEY: 'georank_browser_phone',
        PROMPTED_KEY: 'georank_auth_prompted_v1',
        MODAL_ID: 'georank-auth-modal',
        state: {
            mode: 'login',
            token: null,
            user: null,
            initialized: false,
        },

        get apiBase() {
            return ['80', '443', ''].includes(window.location.port)
                ? ''
                : `${window.location.protocol}//${window.location.hostname}:8000`;
        },

        getCookie(name) {
            const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
            return match ? decodeURIComponent(match[1]) : '';
        },

        setCookie(name, value, days = 365) {
            const maxAge = Math.max(0, Math.floor(days * 24 * 60 * 60));
            document.cookie = `${name}=${encodeURIComponent(value)}; Max-Age=${maxAge}; Path=/; SameSite=Lax`;
        },

        clearCookie(name) {
            document.cookie = `${name}=; Max-Age=0; Path=/; SameSite=Lax`;
        },

        normalizePhone(phone) {
            const digits = String(phone || '').replace(/\D+/g, '');
            if (digits.startsWith('86') && digits.length === 13) {
                return digits.slice(2);
            }
            return digits;
        },

        maskPhone(phone) {
            const normalized = this.normalizePhone(phone);
            if (normalized.length !== 11) return phone || '已登录';
            return `${normalized.slice(0, 3)}****${normalized.slice(-4)}`;
        },

        getBoundPhone() {
            const stored = localStorage.getItem(this.BOUND_PHONE_KEY) || this.getCookie(this.BOUND_PHONE_KEY);
            return this.normalizePhone(stored || '');
        },

        bindPhone(phone) {
            const normalized = this.normalizePhone(phone);
            if (!normalized) return;
            localStorage.setItem(this.BOUND_PHONE_KEY, normalized);
            this.setCookie(this.BOUND_PHONE_KEY, normalized, 365);
        },

        parseUser(raw) {
            if (!raw) return null;
            try {
                return typeof raw === 'string' ? JSON.parse(raw) : raw;
            } catch (_) {
                return null;
            }
        },

        syncState() {
            this.state.token = localStorage.getItem(this.TOKEN_KEY)
                || this.getCookie(this.TOKEN_KEY)
                || localStorage.getItem('georank_token')
                || '';
            this.state.user = this.parseUser(localStorage.getItem(this.USER_KEY));
            if (this.state.user?.phone && !this.getBoundPhone()) {
                this.bindPhone(this.state.user.phone);
            }
            if (!this.state.token) {
                localStorage.removeItem(this.TOKEN_KEY);
                localStorage.removeItem(this.USER_KEY);
            }
        },

        getToken() {
            this.syncState();
            return this.state.token || '';
        },

        getUser() {
            this.syncState();
            return this.state.user;
        },

        isAuthenticated() {
            return Boolean(this.getToken());
        },

        async request(path, options = {}) {
            const headers = {
                'Content-Type': 'application/json',
                ...DeviceIdentity.getHeaders(),
                ...(options.headers || {}),
            };
            const token = this.getToken();
            if (token) {
                headers.Authorization = `Bearer ${token}`;
            }
            const response = await fetch(`${this.apiBase}${path}`, {
                ...options,
                headers,
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.detail || `请求失败 (${response.status})`);
            }
            return payload;
        },

        async fetchMe() {
            if (!this.getToken()) return null;
            const user = await this.request('/api/auth/me', { method: 'GET' });
            this.state.user = user;
            localStorage.setItem(this.USER_KEY, JSON.stringify(user));
            if (user?.phone) {
                this.bindPhone(user.phone);
            }
            document.dispatchEvent(new CustomEvent('georank:auth-changed', {
                detail: { authenticated: true, user },
            }));
            this.renderHeader();
            return user;
        },

        async login({ phone, password, remember = true }) {
            const normalizedPhone = this.normalizePhone(phone);
            const tokenResponse = await this.request('/api/auth/login', {
                method: 'POST',
                body: JSON.stringify({
                    phone: normalizedPhone,
                    password,
                    remember_me: remember,
                }),
            });
            const user = await this.request('/api/auth/me', {
                method: 'GET',
                headers: { Authorization: `Bearer ${tokenResponse.access_token}` },
            });
            this.setSession(tokenResponse.access_token, user, remember);
            return user;
        },

        async register({ phone, password, remember = true }) {
            const normalizedPhone = this.normalizePhone(phone);
            const tokenResponse = await this.request('/api/auth/register', {
                method: 'POST',
                body: JSON.stringify({
                    phone: normalizedPhone,
                    password,
                    remember_me: remember,
                }),
            });
            const user = await this.request('/api/auth/me', {
                method: 'GET',
                headers: { Authorization: `Bearer ${tokenResponse.access_token}` },
            });
            this.setSession(tokenResponse.access_token, user, remember);
            return user;
        },

        setSession(token, user, remember = true) {
            const previousUser = this.getUser();
            if (previousUser?.id && user?.id && previousUser.id !== user.id) {
                window.GEOrank.APIKeyStore?.clear?.();
            }
            localStorage.setItem(this.TOKEN_KEY, token);
            localStorage.setItem(this.USER_KEY, JSON.stringify(user));
            this.state.token = token;
            this.state.user = user;
            if (user?.phone) {
                this.bindPhone(user.phone);
            }
            if (remember) {
                this.setCookie(this.TOKEN_KEY, token, 365);
            } else {
                document.cookie = `${this.TOKEN_KEY}=${encodeURIComponent(token)}; Path=/; SameSite=Lax`;
            }
            document.dispatchEvent(new CustomEvent('georank:auth-changed', {
                detail: { authenticated: true, user },
            }));
            this.renderHeader();
        },

        clearSession() {
            window.GEOrank.APIKeyStore?.clear?.();
            localStorage.removeItem(this.TOKEN_KEY);
            localStorage.removeItem(this.USER_KEY);
            localStorage.removeItem('georank_token');
            this.clearCookie(this.TOKEN_KEY);
            this.clearCookie('georank_token');
            this.state.token = '';
            this.state.user = null;
            document.dispatchEvent(new CustomEvent('georank:auth-changed', {
                detail: { authenticated: false, user: null },
            }));
            this.renderHeader();
        },

        ensureModal() {
            if (document.getElementById(this.MODAL_ID)) return;
            const wrapper = document.createElement('div');
            wrapper.id = this.MODAL_ID;
            wrapper.className = 'auth-modal hidden';
            wrapper.innerHTML = `
                <div class="auth-modal__backdrop" data-auth-close></div>
                <div class="auth-modal__panel" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title">
                    <button type="button" class="auth-modal__close" data-auth-close aria-label="关闭" data-i18n-aria-label="auth.close">
                        <span class="material-symbols-outlined">close</span>
                    </button>
                    <div class="auth-modal__tabs">
                        <button type="button" class="auth-modal__tab is-active" data-auth-mode="login" data-i18n="auth.login">登录</button>
                        <button type="button" class="auth-modal__tab" data-auth-mode="register" data-i18n="auth.register">注册</button>
                    </div>
                    <p class="auth-modal__reason" data-auth-reason></p>
                    <form class="auth-form" data-auth-form>
                        <h2 id="auth-modal-title" class="auth-form__title" data-auth-title data-i18n="auth.loginTitle">手机号登录</h2>
                        <p class="auth-form__subtitle" data-auth-subtitle data-i18n="auth.defaultSubtitle">输入手机号和密码即可完成登录或注册。</p>
                        <p class="auth-form__hint" data-i18n="auth.browserHint">当前浏览器仅绑定一个手机号，用于持续保存会话。</p>
                        <label class="auth-form__label">
                            <span data-i18n="auth.phone">手机号</span>
                            <input type="tel" inputmode="numeric" autocomplete="tel" name="phone" placeholder="请输入手机号" data-i18n-placeholder="auth.phonePlaceholder" maxlength="20" required />
                        </label>
                        <label class="auth-form__label">
                            <span data-i18n="auth.password">密码</span>
                            <input type="password" autocomplete="current-password" name="password" placeholder="请输入密码" data-i18n-placeholder="auth.passwordPlaceholder" minlength="6" maxlength="128" required />
                        </label>
                        <label class="auth-form__checkbox">
                            <input type="checkbox" name="remember" checked />
                            <span data-i18n="auth.remember">保持登录</span>
                        </label>
                        <p class="auth-form__error hidden" data-auth-error></p>
                        <button type="submit" class="auth-form__submit" data-auth-submit data-i18n="auth.submitLogin">登录</button>
                        <div class="auth-form__links">
                            <a href="/login" data-auth-standalone="login" data-i18n="auth.openLoginPage">打开登录页</a>
                            <a href="/register" data-auth-standalone="register" data-i18n="auth.openRegisterPage">打开注册页</a>
                        </div>
                    </form>
                </div>
            `;
            document.body.appendChild(wrapper);
            I18N.apply(wrapper);
            wrapper.querySelectorAll('[data-auth-close]').forEach((el) => {
                el.addEventListener('click', () => this.closeModal());
            });
            wrapper.querySelectorAll('[data-auth-mode]').forEach((button) => {
                button.addEventListener('click', () => this.setMode(button.getAttribute('data-auth-mode') || 'login'));
            });
            wrapper.querySelector('[data-auth-form]')?.addEventListener('submit', (event) => {
                event.preventDefault();
                void this.handleFormSubmit(wrapper.querySelector('[data-auth-form]'));
            });
        },

        setMode(mode = 'login') {
            this.state.mode = mode === 'register' ? 'register' : 'login';
            const modal = document.getElementById(this.MODAL_ID);
            if (!modal) return;
            modal.querySelectorAll('[data-auth-mode]').forEach((tab) => {
                tab.classList.toggle('is-active', tab.getAttribute('data-auth-mode') === this.state.mode);
            });
            const title = modal.querySelector('.auth-form__title');
            const subtitle = modal.querySelector('.auth-form__subtitle');
            const submit = modal.querySelector('.auth-form__submit');
            if (title) {
                title.dataset.i18n = this.state.mode === 'login' ? 'auth.loginTitle' : 'auth.registerTitle';
                title.textContent = I18N.t(title.dataset.i18n);
            }
            if (subtitle) {
                subtitle.dataset.i18n = this.state.mode === 'login' ? 'auth.loginSubtitle' : 'auth.registerSubtitle';
                subtitle.textContent = I18N.t(subtitle.dataset.i18n);
            }
            if (submit) {
                submit.dataset.i18n = this.state.mode === 'login' ? 'auth.submitLogin' : 'auth.submitRegister';
                submit.textContent = I18N.t(submit.dataset.i18n);
            }
        },

        showError(message = '', root = null) {
            const modal = document.getElementById(this.MODAL_ID);
            const errorEl = root?.querySelector?.('[data-auth-error]') || modal?.querySelector('[data-auth-error]');
            if (!errorEl) return;
            errorEl.textContent = message;
            errorEl.classList.toggle('hidden', !message);
        },

        safeReturnTo(value, fallback = '/') {
            const candidate = String(value || '');
            if (!candidate) return fallback;
            try {
                const target = new URL(candidate, window.location.origin);
                if (target.origin !== window.location.origin) return fallback;
                const currentPath = Routes.normalizePath(target.pathname);
                if (currentPath === '/login' || currentPath === '/register') return fallback;
                return `${target.pathname}${target.search}${target.hash}`;
            } catch (_) {
                return fallback;
            }
        },

        openModal(mode = 'login', options = {}) {
            this.ensureModal();
            this.setMode(mode);
            const modal = document.getElementById(this.MODAL_ID);
            if (!modal) return;
            const reasonEl = modal.querySelector('[data-auth-reason]');
            const reason = options.reason || '';
            reasonEl.textContent = reason;
            reasonEl.classList.toggle('hidden', !reason);
            modal.classList.remove('hidden');
            document.body.classList.add('auth-modal-open');
            this.showError('');
            const boundPhone = this.getBoundPhone();
            const phoneInput = modal.querySelector('input[name="phone"]');
            if (boundPhone && phoneInput && !phoneInput.value) {
                phoneInput.value = boundPhone;
            }
            phoneInput?.focus();
        },

        closeModal() {
            const modal = document.getElementById(this.MODAL_ID);
            if (!modal) return;
            modal.classList.add('hidden');
            document.body.classList.remove('auth-modal-open');
        },

        async handleFormSubmit(form) {
            if (!form) return;
            const submitBtn = form.querySelector('.auth-form__submit');
            const phone = form.elements.phone?.value || '';
            const password = form.elements.password?.value || '';
            const remember = Boolean(form.elements.remember?.checked);
            const normalizedPhone = this.normalizePhone(phone);
            const boundPhone = this.getBoundPhone();
            if (boundPhone && boundPhone !== normalizedPhone) {
                this.showError(I18N.t('auth.invalidBoundPhone', { phone: this.maskPhone(boundPhone) }), form);
                return;
            }
            if (!/^1\d{10}$/.test(normalizedPhone)) {
                this.showError(I18N.t('auth.invalidPhone'), form);
                return;
            }
            if (String(password).length < 6) {
                this.showError(I18N.t('auth.invalidPassword'), form);
                return;
            }
            const confirmPassword = form.elements.confirmPassword?.value || '';
            if (this.state.mode === 'register' && password !== confirmPassword) {
                this.showError(I18N.t('auth.passwordMismatch'), form);
                return;
            }
            submitBtn?.setAttribute('disabled', 'disabled');
            submitBtn && (submitBtn.textContent = this.state.mode === 'login' ? I18N.t('auth.submittingLogin') : I18N.t('auth.submittingRegister'));
            try {
                const user = this.state.mode === 'register'
                    ? await this.register({ phone: normalizedPhone, password, remember })
                    : await this.login({ phone: normalizedPhone, password, remember });
                this.closeModal();
                const currentPath = Routes.normalizePath(window.location.pathname);
                if (currentPath === '/login' || currentPath === '/register') {
                    const params = new URLSearchParams(window.location.search);
                    const returnTo = this.safeReturnTo(params.get('return'), '/');
                    window.location.href = returnTo;
                    return;
                }
                this.showToast?.(I18N.t('auth.toastSignedIn', { phone: this.maskPhone(user.phone) }));
            } catch (error) {
                this.showError(error.message || I18N.t('auth.failed'), form);
            } finally {
                submitBtn?.removeAttribute('disabled');
                submitBtn && (submitBtn.textContent = this.state.mode === 'login' ? I18N.t('auth.submitLogin') : I18N.t('auth.submitRegister'));
            }
        },

        requireAuth(options = {}) {
            if (this.isAuthenticated()) return true;
            const translatedReason = options.reasonKey ? I18N.t(options.reasonKey) : '';
            this.openModal(options.mode || 'login', {
                reason: translatedReason || options.reason || I18N.t('auth.requireReason'),
            });
            return false;
        },

        bindHeader() {
            const trigger = document.querySelector('[data-auth-trigger]');
            const menu = document.querySelector('[data-auth-menu]');
            if (!trigger || trigger.dataset.bound === '1') {
                this.renderHeader();
                return;
            }
            trigger.dataset.bound = '1';
            trigger.addEventListener('click', (event) => {
                if (trigger.matches('[data-profile-link]')) return;
                event.preventDefault();
                if (!this.isAuthenticated()) {
                    this.openModal('login');
                    return;
                }
                menu?.classList.toggle('hidden');
            });
            menu?.addEventListener('click', (event) => {
                const logoutButton = event.target.closest('[data-auth-logout]');
                if (!logoutButton) return;
                event.preventDefault();
                this.clearSession();
                menu.classList.add('hidden');
            });
            document.addEventListener('click', (event) => {
                if (!menu || menu.classList.contains('hidden')) return;
                if (menu.contains(event.target) || trigger.contains(event.target)) return;
                menu.classList.add('hidden');
            });
            this.renderHeader();
        },

        renderHeader() {
            const label = document.querySelector('[data-auth-trigger-label]');
            const trigger = document.querySelector('[data-auth-trigger]');
            const menu = document.querySelector('[data-auth-menu]');
            const phone = document.querySelector('[data-auth-menu-phone]');
            const logout = document.querySelector('[data-auth-logout]');
            const loginLink = document.querySelector('[data-auth-menu-login]');
            const user = this.getUser();
            const authenticated = this.isAuthenticated();
            const triggerLabel = authenticated ? I18N.t('auth.triggerSignedIn') : I18N.t('auth.triggerSignedOut');
            if (label) {
                label.textContent = authenticated ? this.maskPhone(user?.phone || user?.username || I18N.t('auth.signedIn')) : I18N.t('auth.login');
            }
            if (trigger) {
                trigger.setAttribute('aria-label', triggerLabel);
                const currentPath = Routes.normalizePath(window.location.pathname);
                const isAuthPage = currentPath === '/login' || currentPath === '/register';
                const rawReturnTo = isAuthPage
                    ? new URLSearchParams(window.location.search).get('return')
                    : `${window.location.pathname}${window.location.search}`;
                const returnTo = isAuthPage ? this.safeReturnTo(rawReturnTo, '') : rawReturnTo;
                const loginHref = Routes.buildUrl('/login');
                trigger.href = authenticated
                    ? Routes.buildUrl('/profile')
                    : returnTo
                        ? `${loginHref}?return=${encodeURIComponent(returnTo)}`
                        : loginHref;
            }
            if (phone) {
                phone.textContent = authenticated ? this.maskPhone(user?.phone || user?.username || I18N.t('auth.signedIn')) : I18N.t('auth.signedOut');
            }
            if (logout) logout.classList.toggle('hidden', !authenticated);
            if (loginLink) loginLink.classList.toggle('hidden', authenticated);
            if (menu && !authenticated) {
                menu.classList.add('hidden');
            }
        },

        maybePromptFirstVisit() {
            const path = Routes.normalizePath(window.location.pathname);
            if (this.isAuthenticated()) return;
            if (path.startsWith('/admin') || path === '/login' || path === '/register') return;
            if (path === '/profile') return;
            const moduleKey = ModuleGate.moduleKeyForPath(path);
            if (moduleKey && !ModuleGate.isEnabled(moduleKey)) return;
            if (
                path === '/company'
                || path === '/companies'
                || path.startsWith('/companies/')
                || path === '/c'
                || path.startsWith('/c/')
            ) return;
            if (path === '/experts' || path.startsWith('/experts/')) return;
            let submitAutoOpenFlag = false;
            try {
                submitAutoOpenFlag = sessionStorage.getItem('georank_open_submit_company') === '1';
            } catch (_) {
                submitAutoOpenFlag = false;
            }
            const submitRouteRequested = new URLSearchParams(window.location.search).get('submit') === 'company'
                || window.location.hash === '#submit-company'
                || submitAutoOpenFlag;
            if (submitRouteRequested) {
                try {
                    sessionStorage.removeItem('georank_open_submit_company');
                } catch (_) {
                    // Storage can be unavailable in restricted browsing modes.
                }
                return;
            }
            if (localStorage.getItem(this.PROMPTED_KEY)) return;
            localStorage.setItem(this.PROMPTED_KEY, '1');
            this.openModal('register', {
                reason: I18N.t('auth.firstVisitReason'),
            });
        },

        authLinkWithReturn(path) {
            const rawReturnTo = new URLSearchParams(window.location.search).get('return');
            const returnTo = rawReturnTo ? this.safeReturnTo(rawReturnTo, '') : '';
            const href = Routes.buildUrl(path);
            return returnTo ? `${href}?return=${encodeURIComponent(returnTo)}` : href;
        },

        mountStandalone(root, mode = 'login') {
            if (!root) return;
            root.innerHTML = `
                <div class="auth-standalone">
                    <div class="auth-standalone__card">
                        <p class="auth-standalone__eyebrow">${mode === 'register' ? I18N.t('auth.standaloneRegisterEyebrow') : I18N.t('auth.standaloneLoginEyebrow')}</p>
                        <h1 class="auth-standalone__title">${mode === 'register' ? I18N.t('auth.standaloneRegisterTitle') : I18N.t('auth.standaloneLoginTitle')}</h1>
                        <p class="auth-standalone__copy">${mode === 'register' ? I18N.t('auth.standaloneRegisterCopy') : I18N.t('auth.standaloneLoginCopy')}</p>
                        <form class="auth-form auth-form--standalone" data-auth-standalone-form>
                            <label class="auth-form__label">
                                <span>${I18N.t('auth.phone')}</span>
                                <input type="tel" inputmode="numeric" autocomplete="tel" name="phone" placeholder="${I18N.t('auth.phonePlaceholder')}" maxlength="20" required />
                            </label>
                            <label class="auth-form__label">
                                <span>${I18N.t('auth.password')}</span>
                                <input type="password" autocomplete="${mode === 'register' ? 'new-password' : 'current-password'}" name="password" placeholder="${I18N.t('auth.passwordPlaceholder')}" minlength="6" maxlength="128" required />
                            </label>
                            ${mode === 'register' ? `
                            <label class="auth-form__label">
                                <span>${I18N.t('auth.confirmPassword')}</span>
                                <input type="password" autocomplete="new-password" name="confirmPassword" placeholder="${I18N.t('auth.confirmPasswordPlaceholder')}" minlength="6" maxlength="128" required />
                            </label>` : ''}
                            <label class="auth-form__checkbox">
                                <input type="checkbox" name="remember" checked />
                                <span>${I18N.t('auth.remember')}</span>
                            </label>
                            <p class="auth-form__error hidden" data-auth-error></p>
                            <button type="submit" class="auth-form__submit">${mode === 'register' ? I18N.t('auth.submitRegister') : I18N.t('auth.submitLogin')}</button>
                            <div class="auth-form__links">
                                ${mode === 'register'
                                    ? `<a href="${this.authLinkWithReturn('/login')}">${I18N.t('auth.goLogin')}</a>`
                                    : `<a href="${this.authLinkWithReturn('/register')}">${I18N.t('auth.goRegister')}</a>`}
                            </div>
                        </form>
                    </div>
                </div>
            `;
            this.state.mode = mode;
            const boundPhone = this.getBoundPhone();
            root.querySelector('[data-auth-standalone-form]')?.addEventListener('submit', (event) => {
                event.preventDefault();
                void this.handleFormSubmit(root.querySelector('[data-auth-standalone-form]'));
            });
            const phoneInput = root.querySelector('input[name="phone"]');
            if (boundPhone && phoneInput && !phoneInput.value) {
                phoneInput.value = boundPhone;
            }
        },

        showToast(message) {
            if (!message) return;
            const toast = document.createElement('div');
            toast.className = 'auth-toast';
            toast.textContent = message;
            document.body.appendChild(toast);
            window.setTimeout(() => toast.classList.add('is-visible'), 10);
            window.setTimeout(() => {
                toast.classList.remove('is-visible');
                window.setTimeout(() => toast.remove(), 220);
            }, 1800);
        },

        init() {
            if (this.state.initialized) return;
            this.state.initialized = true;
            this.syncState();
            this.ensureModal();
            this.bindHeader();
            if (this.state.token && !this.state.user) {
                void this.fetchMe().catch(() => this.clearSession());
            }
            document.addEventListener('componentLoaded', (event) => {
                if (event.detail?.targetSelector === '#header-container') {
                    this.bindHeader();
                }
            });
            document.addEventListener('georank:auth-changed', () => this.renderHeader());
            this.maybePromptFirstVisit();
        },
    };

    window.GEOrank.Auth = Auth;

    // ===== 用户自定义 API Key（仅浏览器本地保存）=====
    const APIKeyStore = {
        STORAGE_KEY: 'georank_byok_config_v1',
        COOKIE_KEY: 'georank_byok_config_v1',
        MODAL_ID: 'georank-api-key-modal',
        policy: null,
        policyPromise: null,

        apiBase() {
            return Auth.apiBase
                || (['80', '443', ''].includes(window.location.port)
                    ? ''
                    : `${window.location.protocol}//${window.location.hostname}:8000`);
        },

        applyPolicy(policy) {
            if (!policy || typeof policy !== 'object') return this.policy;
            this.policy = policy;
            if (policy.allow_user_byok === false) this.clear();
            return this.policy;
        },

        async loadPolicy({force = false} = {}) {
            if (this.policy && !force) return this.policy;
            if (this.policyPromise && !force) return this.policyPromise;
            this.policyPromise = fetch(`${this.apiBase()}/api/usage/policy`, {
                headers: DeviceIdentity.getHeaders(),
            })
                .then(async response => {
                    const payload = await response.json().catch(() => ({}));
                    if (!response.ok) throw new Error(payload.detail || '读取 API 策略失败');
                    return this.applyPolicy(payload);
                })
                .finally(() => {
                    this.policyPromise = null;
                });
            return this.policyPromise;
        },

        providerPresets() {
            return (this.policy?.allowed_byok_providers || [])
                .filter(provider => provider?.key && provider?.base_url);
        },

        providerPreset(providerKey) {
            const key = String(providerKey || '').trim().toLowerCase();
            return this.providerPresets().find(provider => String(provider.key).toLowerCase() === key) || null;
        },

        isAllowedProviderConfig(config) {
            const preset = this.providerPreset(config?.provider);
            if (!preset) return false;
            try {
                return new URL(config.baseUrl).origin === new URL(preset.base_url).origin;
            } catch (_) {
                return false;
            }
        },

        read() {
            if (Auth.getCookie(this.COOKIE_KEY)) {
                Auth.clearCookie(this.COOKIE_KEY);
            }
            const raw = localStorage.getItem(this.STORAGE_KEY);
            if (!raw) return null;
            try {
                const parsed = JSON.parse(raw);
                return parsed && typeof parsed === 'object' ? parsed : null;
            } catch (_) {
                return null;
            }
        },

        save(config = {}) {
            if (this.policy?.allow_user_byok === false) {
                throw new Error('后台当前未开放用户自备 API');
            }
            if (this.policy && !this.isAllowedProviderConfig(config)) {
                throw new Error('API Base URL 必须使用后台允许的供应商地址');
            }
            const payload = {
                enabled: Boolean(config.enabled),
                provider: String(config.provider || 'deepseek').trim() || 'deepseek',
                baseUrl: String(config.baseUrl || 'https://api.deepseek.com/v1').trim(),
                model: String(config.model || 'deepseek-chat').trim(),
                apiKey: String(config.apiKey || '').trim(),
                updatedAt: new Date().toISOString(),
            };
            const raw = JSON.stringify(payload);
            localStorage.setItem(this.STORAGE_KEY, raw);
            Auth.clearCookie(this.COOKIE_KEY);
            document.dispatchEvent(new CustomEvent('georank:api-key-changed', {
                detail: { configured: this.hasUsableKey() },
            }));
            return payload;
        },

        clear() {
            localStorage.removeItem(this.STORAGE_KEY);
            Auth.clearCookie(this.COOKIE_KEY);
            document.dispatchEvent(new CustomEvent('georank:api-key-changed', {
                detail: { configured: false },
            }));
        },

        hasUsableKey() {
            const config = this.read();
            if (this.policy?.allow_user_byok === false) return false;
            return Boolean(
                config?.enabled
                && config?.apiKey
                && config?.baseUrl
                && config?.model
                && (!this.policy || this.isAllowedProviderConfig(config))
            );
        },

        maskKey(value) {
            const text = String(value || '');
            if (!text) return '';
            if (text.length <= 10) return '••••••••';
            return `${text.slice(0, 4)}••••${text.slice(-4)}`;
        },

        getHeaders() {
            const deviceHeaders = DeviceIdentity.getHeaders();
            const config = this.read();
            if (
                this.policy?.allow_user_byok === false
                || !config?.enabled
                || !config.apiKey
                || (this.policy && !this.isAllowedProviderConfig(config))
            ) return deviceHeaders;
            return {
                ...deviceHeaders,
                'X-GEOrank-BYOK-Provider': config.provider || 'custom',
                'X-GEOrank-BYOK-Base-URL': config.baseUrl || '',
                'X-GEOrank-BYOK-Model': config.model || '',
                'X-GEOrank-BYOK-Key': config.apiKey || '',
            };
        },

        shouldPromptForError(error) {
            if (this.policy?.allow_user_byok === false) return false;
            const message = String(error?.message || error || '');
            return /额度|自定义 API|API Key|Payment Required|Too Many Requests/i.test(message);
        },

        ensureModal() {
            if (document.getElementById(this.MODAL_ID)) return;
            const wrapper = document.createElement('div');
            wrapper.id = this.MODAL_ID;
            wrapper.className = 'api-key-modal hidden';
            wrapper.innerHTML = `
                <div class="api-key-modal__backdrop" data-api-key-close></div>
                <div class="api-key-modal__panel" role="dialog" aria-modal="true" aria-labelledby="api-key-modal-title">
                    <button type="button" class="api-key-modal__close" data-api-key-close aria-label="关闭">
                        <span class="material-symbols-outlined">close</span>
                    </button>
                    <p class="api-key-modal__eyebrow">BYOK SETTINGS</p>
                    <h2 id="api-key-modal-title" data-api-key-title>使用自己的 API Key 继续生成</h2>
                    <p class="api-key-modal__copy" data-api-key-reason>你的 Key 只保存在当前浏览器。若使用代理模式，会在本次生成请求中临时发送到服务端调用模型，但不会入库或写入日志。</p>
                    <a data-api-key-official class="api-key-form__official" href="https://platform.deepseek.com/api_keys" target="_blank" rel="noopener noreferrer">前往 DeepSeek 获取 API Key</a>
                    <form class="api-key-form" data-api-key-form>
                        <label>
                            <span>供应商</span>
                            <select name="provider"></select>
                        </label>
                        <label>
                            <span>Base URL</span>
                            <input name="baseUrl" placeholder="https://api.deepseek.com/v1" autocomplete="off" />
                        </label>
                        <label>
                            <span>Model</span>
                            <input name="model" placeholder="deepseek-chat" autocomplete="off" />
                        </label>
                        <label>
                            <span>API Key</span>
                            <input name="apiKey" type="password" placeholder="只保存在当前浏览器" autocomplete="off" />
                        </label>
                        <label class="api-key-form__check">
                            <input type="checkbox" name="enabled" checked />
                            <span>启用自定义 API Key</span>
                        </label>
                        <div class="api-key-form__actions">
                            <button type="button" class="api-key-form__ghost" data-api-key-clear>清除</button>
                            <button type="submit" class="api-key-form__primary">保存设置</button>
                        </div>
                    </form>
                </div>
            `;
            document.body.appendChild(wrapper);
            wrapper.querySelectorAll('[data-api-key-close]').forEach((el) => {
                el.addEventListener('click', () => this.closeModal());
            });
            wrapper.querySelector('[data-api-key-clear]')?.addEventListener('click', () => {
                this.clear();
                this.closeModal();
            });
            wrapper.querySelector('[data-api-key-form]')?.addEventListener('submit', (event) => {
                event.preventDefault();
                const form = event.currentTarget;
                const data = new FormData(form);
                try {
                    this.save({
                        enabled: data.get('enabled') === 'on',
                        provider: data.get('provider'),
                        baseUrl: data.get('baseUrl'),
                        model: data.get('model'),
                        apiKey: data.get('apiKey'),
                    });
                    this.closeModal();
                    Auth.showToast('API Key 设置已保存在当前浏览器');
                } catch (error) {
                    Auth.showToast(error?.message || 'API Key 设置保存失败');
                }
            });
            wrapper.querySelector('select[name="provider"]')?.addEventListener('change', event => {
                const preset = this.providerPreset(event.currentTarget.value);
                const form = wrapper.querySelector('[data-api-key-form]');
                if (!preset || !form) return;
                form.baseUrl.value = preset.base_url || '';
                form.model.value = preset.default_model || '';
            });
        },

        async openModal(reason = '') {
            try {
                await this.loadPolicy();
            } catch (_) {
                Auth.showToast('暂时无法读取 API 配置，请稍后重试');
                return;
            }
            if (this.policy?.allow_user_byok === false) {
                this.clear();
                Auth.showToast('后台当前未开放用户自备 API');
                return;
            }
            this.ensureModal();
            const modal = document.getElementById(this.MODAL_ID);
            const config = this.read() || {};
            const guidance = this.policy?.byok_guidance || {};
            const presets = this.providerPresets();
            const form = modal?.querySelector('[data-api-key-form]');
            if (form) {
                form.provider.innerHTML = presets.map(provider => {
                    const value = String(provider.key || '').replace(/["<>]/g, '');
                    const label = String(provider.name || provider.key || '').replace(/[<>]/g, '');
                    return `<option value="${value}">${label}</option>`;
                }).join('');
                const preferredKey = config.provider || guidance.provider || presets[0]?.key || '';
                form.provider.value = this.providerPreset(preferredKey)?.key || presets[0]?.key || '';
                const selected = this.providerPreset(form.provider.value) || presets[0] || {};
                form.baseUrl.value = config.baseUrl || selected.base_url || guidance.base_url || '';
                form.model.value = config.model || selected.default_model || guidance.model || '';
                form.apiKey.value = config.apiKey || '';
                form.enabled.checked = config.enabled !== false;
            }
            const titleEl = modal?.querySelector('[data-api-key-title]');
            if (titleEl) titleEl.textContent = guidance.title || '使用自己的 API Key 继续生成';
            const officialEl = modal?.querySelector('[data-api-key-official]');
            if (officialEl) {
                officialEl.textContent = guidance.cta_label || '前往 DeepSeek 获取 API Key';
                officialEl.href = guidance.official_url || 'https://platform.deepseek.com/api_keys';
            }
            const reasonEl = modal?.querySelector('[data-api-key-reason]');
            if (reasonEl) {
                const message = reason || guidance.message || '平台额度当前不可用，请绑定自己的 API Key。';
                reasonEl.textContent = SiteSettings.replaceBrand(`${message} Key 只保存在当前浏览器，不会保存到 GEOrank 数据库。`);
            }
            modal?.classList.remove('hidden');
            document.body.classList.add('auth-modal-open');
        },

        closeModal() {
            document.getElementById(this.MODAL_ID)?.classList.add('hidden');
            if (!document.querySelector('.auth-modal:not(.hidden)')) {
                document.body.classList.remove('auth-modal-open');
            }
        },
    };

    window.GEOrank.APIKeyStore = APIKeyStore;

    // ===== 导航功能 =====
    const Navigation = {
        /**
         * 初始化导航
         */
        init() {
            this.highlightCurrentPage();
            this.setupMobileMenu();
            this.setupScrollBehavior();
        },

        /**
         * 高亮当前页面导航项
         */
        highlightCurrentPage() {
            const currentPath = Routes.getModulePath(window.location.pathname);
            const navLinks = DOM.getAll('[data-nav-link]');

            navLinks.forEach(link => {
                const href = link.getAttribute('href');
                const target = Routes.getModulePath(href || '/');
                if (currentPath === target) {
                    link.classList.add('text-blue-600', 'border-b-2', 'border-blue-600', 'font-bold');
                    link.classList.remove('text-slate-600');
                }
            });
        },

        /**
         * 设置移动端菜单
         */
        setupMobileMenu() {
            const menuToggle = DOM.get('#mobile-menu-toggle');
            const mobileMenu = DOM.get('#mobile-menu');

            DOM.on(menuToggle, 'click', () => {
                DOM.toggleClass(mobileMenu, 'hidden');
            });
        },

        /**
         * 设置滚动行为
         */
        setupScrollBehavior() {
            const nav = DOM.get('#main-nav');
            let lastScroll = 0;

            window.addEventListener('scroll', () => {
                const currentScroll = window.pageYOffset;

                if (nav) {
                    if (currentScroll > 50) {
                        nav.classList.add('shadow-nav');
                    } else {
                        nav.classList.remove('shadow-nav');
                    }
                }

                lastScroll = currentScroll;
            }, { passive: true });
        }
    };

    // ===== 投票功能 =====
    const Voting = {
        /**
         * 初始化投票按钮
         */
        init() {
            const voteButtons = DOM.getAll('[data-vote]');
            voteButtons.forEach(button => {
                DOM.on(button, 'click', (e) => this.handleVote(e));
            });
        },

        /**
         * 处理投票
         * @param {Event} e - 事件对象
         */
        handleVote(e) {
            const button = e.currentTarget;
            const countEl = button.querySelector('[data-vote-count]');

            if (countEl) {
                let count = parseInt(countEl.textContent, 10);
                if (button.classList.contains('voted')) {
                    count--;
                    button.classList.remove('voted', 'border-primary');
                } else {
                    count++;
                    button.classList.add('voted', 'border-primary');
                }
                countEl.textContent = count;
            }
        }
    };

    // ===== 搜索功能 =====
    const Search = {
        /**
         * 初始化搜索
         */
        init() {
            const searchInput = DOM.get('#search-input');
            const searchBtn = DOM.get('#search-btn');

            DOM.on(searchInput, 'input', (e) => this.handleSearch(e.target.value));
            DOM.on(searchBtn, 'click', () => this.submitSearch());

            // Enter键提交搜索
            DOM.on(searchInput, 'keypress', (e) => {
                if (e.key === 'Enter') {
                    this.submitSearch();
                }
            });
        },

        /**
         * 处理搜索输入
         * @param {string} query - 搜索关键词
         */
        handleSearch(query) {
            // 实时搜索逻辑
            console.log('搜索关键词:', query);
        },

        /**
         * 提交搜索
         */
        submitSearch() {
            const searchInput = DOM.get('#search-input');
            if (searchInput && searchInput.value.trim()) {
                console.log('提交搜索:', searchInput.value);
                // 这里可以实现跳转或其他逻辑
            }
        }
    };

    // ===== 工具函数 =====
    const Utils = {
        /**
         * 防抖函数
         * @param {Function} func - 要执行的函数
         * @param {number} wait - 等待时间
         * @returns {Function}
         */
        debounce(func, wait = 300) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },

        /**
         * 节流函数
         * @param {Function} func - 要执行的函数
         * @param {number} limit - 限制时间
         * @returns {Function}
         */
        throttle(func, limit = 300) {
            let inThrottle;
            return function executedFunction(...args) {
                if (!inThrottle) {
                    func(...args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            };
        },

        /**
         * 格式化日期
         * @param {Date|string} date - 日期
         * @param {string} format - 格式
         * @returns {string}
         */
        formatDate(date, format = 'YYYY年MM月DD日') {
            const d = new Date(date);
            const map = {
                'YYYY': d.getFullYear(),
                'MM': String(d.getMonth() + 1).padStart(2, '0'),
                'DD': String(d.getDate()).padStart(2, '0'),
                'HH': String(d.getHours()).padStart(2, '0'),
                'mm': String(d.getMinutes()).padStart(2, '0'),
                'ss': String(d.getSeconds()).padStart(2, '0')
            };

            return format.replace(/YYYY|MM|DD|HH|mm|ss/g, matched => map[matched]);
        }
    };

    // ===== 暴露全局接口 =====
    Object.assign(window.GEOrank, {
        DOM,
        ComponentLoader,
        Navigation,
        Voting,
        Search,
        Utils,
        I18N,
        Routes,
        Canonicalizer,
        Auth,
        DeviceIdentity,
        APIKeyStore,
        SiteSettings,
        AnalyticsInjector,
        PageLifecycle
    });

    // ===== 初始化 =====
    ComponentLoader.mountFallbacks();
    ComponentLoader.revealLegacyDocument();

    let frontendInitialized = false;

    function initializeFrontend() {
        if (frontendInitialized) return;
        frontendInitialized = true;

        // 后台刷新公共组件；单个组件失败不影响正文与模块可用性判断
        const shellLoads = [];
        if (DOM.get('#header-container')) shellLoads.push(ComponentLoader.loadHeader());
        if (DOM.get('#footer-container')) shellLoads.push(ComponentLoader.loadFooter());
        void Promise.allSettled(shellLoads).then(results => {
            results.forEach(result => {
                if (result.status !== 'rejected') return;
                const error = result.reason?.message || result.reason?.name || 'Error';
                console.warn('[GEOrank] shell hydration failed', error);
            });
        });

        // 模块可用性独立判断，页面控制器复用同一启动契约
        void PageLifecycle.run(() => {
            Voting.init();
            Search.init();
        });

        // 初始化语言切换
        I18N.init();

        // 初始化公开站点设置
        SiteSettings.init();
        SiteSettings.apply();
        AnalyticsInjector.init();

        // 初始化认证
        Auth.init();
        void APIKeyStore.loadPolicy().catch(() => {});
    }

    if (document.body) {
        initializeFrontend();
    } else {
        document.addEventListener('DOMContentLoaded', initializeFrontend, { once: true });
    }

})();
