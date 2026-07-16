/**
 * GEOrank 自定义首页菜单栏运行时。
 * 自定义首页经过安全清洗后只允许加载这段同源平台脚本。
 */
(function() {
    'use strict';

    function apiBase() {
        return ['80', '443', ''].includes(window.location.port)
            ? ''
            : `${window.location.protocol}//${window.location.hostname}:8000`;
    }

    function normalizeUrl(value) {
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
    }

    function normalizeMenu(value) {
        if (!Array.isArray(value?.items)) return [];
        return value.items.slice(0, 12).map((item, index) => ({
            id: String(item?.id || `menu-${index + 1}`),
            label: String(item?.label || '').trim().slice(0, 40),
            url: normalizeUrl(item?.url),
            target: item?.target === '_self' ? '_self' : '_blank',
            enabled: item?.enabled !== false,
        })).filter(item => item.enabled && item.label && item.url);
    }

    function createLink(item) {
        const link = document.createElement('a');
        link.href = item.url;
        link.textContent = item.label;
        link.dataset.navigationItem = item.id;
        link.target = item.target;
        if (item.target === '_blank') link.rel = 'noopener noreferrer';
        return link;
    }

    function renderMenu(items) {
        if (!items.length) return;
        const containers = new Set([
            ...document.querySelectorAll('[data-site-navigation]'),
            ...document.querySelectorAll('#navMenu'),
        ]);
        containers.forEach(container => {
            const isList = ['UL', 'OL'].includes(container.tagName);
            const fragment = document.createDocumentFragment();
            items.forEach(item => {
                const link = createLink(item);
                if (isList) {
                    const listItem = document.createElement('li');
                    listItem.appendChild(link);
                    fragment.appendChild(listItem);
                } else {
                    fragment.appendChild(link);
                }
            });
            container.replaceChildren(fragment);
        });
    }

    fetch(`${apiBase()}/api/settings/public`, {cache: 'no-store'})
        .then(response => response.ok ? response.json() : null)
        .then(settings => renderMenu(normalizeMenu(settings?.navigation_menu)))
        .catch(() => {});
})();
