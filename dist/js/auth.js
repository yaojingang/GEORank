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
            window.location.replace(auth.safeReturnTo(params.get('return'), '/profile'));
            return;
        }

        const currentPath = window.GEOrank?.Routes?.normalizePath?.(window.location.pathname)
            || window.location.pathname.replace(/\.html$/, '');
        const mode = currentPath === '/register' ? 'register' : 'login';
        auth.mountStandalone(root, mode);
        document.addEventListener('georank:locale-changed', () => {
            auth.mountStandalone(root, mode);
        });
    });
})();
