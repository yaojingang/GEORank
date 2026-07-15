/**
 * GEOrank - 登录 / 注册页
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        const root = document.getElementById('auth-page-root');
        const auth = window.GEOrank?.Auth;
        if (!root || !auth) return;

        if (auth.isAuthenticated()) {
            const params = new URLSearchParams(window.location.search);
            window.location.replace(params.get('return') || '/');
            return;
        }

        const mode = window.location.pathname === '/register' ? 'register' : 'login';
        auth.mountStandalone(root, mode);
        document.addEventListener('georank:locale-changed', () => {
            auth.mountStandalone(root, mode);
        });
        document.addEventListener('georank:site-settings-applied', () => {
            auth.mountStandalone(root, mode);
        });
    });
})();
