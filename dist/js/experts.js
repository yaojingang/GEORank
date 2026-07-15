/**
 * GEOrank - 专家频道
 */
(function () {
    'use strict';

    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
    const API_BASE = ['80', '443', ''].includes(window.location.port)
        ? ''
        : `${window.location.protocol}//${window.location.hostname}:8000`;
    const EXPERTS_PAGE_TITLE = 'GEO 专家频道 - GEOrank | 2026 GEO/SEO专家推荐、AI搜索优化顾问、出海SEO与品牌可见性咨询';
    const EXPERTS_PAGE_DESCRIPTION = 'GEOrank 2026 GEO 专家频道，收录 GEO 方法论、SEO 专家、AI 搜索优化顾问、出海 SEO、豆包 GEO、品牌 AI 可见性和企业 GEO 咨询相关专家画像。';
    const EXPERTS_PAGE_KEYWORDS = [
        'GEO专家推荐',
        'SEO专家推荐',
        'AI搜索优化专家',
        '生成式引擎优化顾问',
        '出海SEO专家',
        '豆包GEO顾问',
        '企业GEO咨询',
        '品牌AI可见性优化',
        'GEO方法论专家',
    ];
    const EXPERTS_PAGE_DATE = '2026-06-17';

    const CATEGORY_META = {
        methodology: { label: '方法论', icon: 'psychology', tags: ['GEO 方法论', '开源项目', '行业标准'] },
        'ai-workflow': { label: 'AI 工作流', icon: 'auto_awesome', tags: ['AI 产品', '独立开发', '内容创作'] },
        'seo-practice': { label: 'SEO/GEO', icon: 'travel_explore', tags: ['搜索营销', '出海 SEO', '中小制造'] },
        'traffic-growth': { label: '流量增长', icon: 'monitoring', tags: ['全域优化', '关键词排名', '企业获客'] },
        overseas: { label: '出海 GEO', icon: 'public', tags: ['海外 GEO', '企业培训', 'AI 应用'] },
        strategy: { label: '策略', icon: 'route', tags: ['路线图', '诊断拆解', '增长节奏'] },
        technical: { label: '技术', icon: 'data_object', tags: ['Schema', 'JSON-LD', '抓取检查'] },
        content: { label: '内容', icon: 'article', tags: ['内容结构', 'FAQ', '可引用事实'] },
        reputation: { label: '品牌治理', icon: 'verified', tags: ['可信来源', '案例证据', '实体识别'] },
        industry: { label: '行业', icon: 'cases', tags: ['行业案例', '竞品对标', '转化页'] },
    };

    const state = {
        category: 'all',
        query: '',
        sort: 'recommended',
        experts: [],
        activeExpertKey: '',
        loadError: '',
    };

    function normalize(text) {
        return String(text || '').trim().toLowerCase();
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function compactText(value, maxLength = 260) {
        const text = String(value || '').replace(/\s+/g, ' ').trim();
        if (text.length <= maxLength) return text;
        return `${text.slice(0, maxLength - 1)}…`;
    }

    function absoluteUrl(path) {
        try {
            return new URL(path || '/', window.location.origin).href;
        } catch (_) {
            return path || '';
        }
    }

    function upsertMetaName(name, content) {
        let meta = document.querySelector(`meta[name="${name}"]`);
        if (!meta) {
            meta = document.createElement('meta');
            meta.setAttribute('name', name);
            document.head.appendChild(meta);
        }
        meta.setAttribute('content', content);
    }

    function upsertMetaProperty(property, content) {
        let meta = document.querySelector(`meta[property="${property}"]`);
        if (!meta) {
            meta = document.createElement('meta');
            meta.setAttribute('property', property);
            document.head.appendChild(meta);
        }
        meta.setAttribute('content', content);
    }

    function upsertCanonical(path) {
        let link = document.querySelector('link[rel="canonical"]');
        if (!link) {
            link = document.createElement('link');
            link.setAttribute('rel', 'canonical');
            document.head.appendChild(link);
        }
        link.setAttribute('href', absoluteUrl(path));
    }

    function updateStructuredData(schema) {
        let script = document.getElementById('experts-jsonld');
        if (!script) {
            script = document.createElement('script');
            script.id = 'experts-jsonld';
            script.type = 'application/ld+json';
            document.head.appendChild(script);
        }
        script.textContent = JSON.stringify(schema, null, 2);
    }

    function uniqueList(items) {
        const seen = new Set();
        return (items || [])
            .map(item => String(item || '').trim())
            .filter(item => {
                if (!item || seen.has(item)) return false;
                seen.add(item);
                return true;
            });
    }

    function expertInitials(expert) {
        const explicit = String(expert?.avatar_initials || '').trim();
        if (explicit) return explicit.slice(0, 4).toUpperCase();
        return String(expert?.display_name || 'EX')
            .replace(/[^A-Za-z\u4e00-\u9fa5]/g, '')
            .slice(0, 2)
            .toUpperCase() || 'EX';
    }

    function expertKey(expert) {
        return String(expert?.slug || expert?.id || '').trim();
    }

    function expertHref(expert) {
        const key = expertKey(expert);
        return key ? `/experts/${encodeURIComponent(key)}` : '/experts';
    }

    function expertDescription(expert) {
        return compactText(expert?.summary || expert?.consultation || `${expert?.display_name || 'GEO 专家'} 的专家介绍。`);
    }

    function expertTags(expert) {
        const meta = CATEGORY_META[expert.category] || {};
        return uniqueList([
            expert.specialty_label || meta.label || '',
            ...(Array.isArray(expert.keywords) ? expert.keywords : []),
            ...(Array.isArray(expert.expertise) ? expert.expertise : []),
            ...(Array.isArray(meta.tags) ? meta.tags : []),
            'GEO',
        ]).slice(0, 5);
    }

    function buildExpertPersonSchema(expert) {
        const url = absoluteUrl(expertHref(expert));
        const links = Array.isArray(expert.links)
            ? expert.links.map(link => link?.href).filter(Boolean).map(absoluteUrl)
            : [];

        const schema = {
            '@type': 'Person',
            '@id': `${url}#person`,
            name: expert.display_name || '未命名专家',
            url,
            jobTitle: expert.title || 'GEO 专家',
            description: expertDescription(expert),
            knowsAbout: uniqueList([
                ...expertTags(expert),
                ...(Array.isArray(expert.expertise) ? expert.expertise.slice(0, 3) : []),
                'SEO 专家',
                'AI 搜索优化',
                '生成式引擎优化',
            ]).slice(0, 12),
        };
        if (links.length) schema.sameAs = links;
        return schema;
    }

    function buildExpertsListSchema() {
        const pageUrl = absoluteUrl('/experts');
        return {
            '@context': 'https://schema.org',
            '@graph': [
                {
                    '@type': 'CollectionPage',
                    '@id': `${pageUrl}#webpage`,
                    url: pageUrl,
                    name: EXPERTS_PAGE_TITLE,
                    headline: 'GEO 专家频道',
                    description: EXPERTS_PAGE_DESCRIPTION,
                    inLanguage: 'zh-CN',
                    datePublished: EXPERTS_PAGE_DATE,
                    dateModified: EXPERTS_PAGE_DATE,
                    keywords: EXPERTS_PAGE_KEYWORDS,
                    about: ['GEO 专家', 'SEO 专家', 'AI 搜索优化', '生成式引擎优化', '出海 SEO', '企业 GEO 咨询'],
                    mainEntity: { '@id': `${pageUrl}#expert-list` },
                },
                {
                    '@type': 'ItemList',
                    '@id': `${pageUrl}#expert-list`,
                    name: '2026 GEO/SEO 专家推荐列表',
                    numberOfItems: state.experts.length,
                    itemListElement: state.experts.map((expert, index) => ({
                        '@type': 'ListItem',
                        position: index + 1,
                        url: absoluteUrl(expertHref(expert)),
                        item: buildExpertPersonSchema(expert),
                    })),
                },
            ],
        };
    }

    function buildExpertDetailSchema(expert, pageTitle, pageDescription) {
        const pageUrl = absoluteUrl(expertHref(expert));
        return {
            '@context': 'https://schema.org',
            '@graph': [
                {
                    '@type': 'ProfilePage',
                    '@id': `${pageUrl}#webpage`,
                    url: pageUrl,
                    name: pageTitle,
                    headline: `${expert.display_name || 'GEO 专家'} - ${expert.title || 'GEO 专家'}`,
                    description: pageDescription,
                    inLanguage: 'zh-CN',
                    datePublished: EXPERTS_PAGE_DATE,
                    dateModified: String(expert.updated_at || EXPERTS_PAGE_DATE).slice(0, 10),
                    keywords: uniqueList([expert.display_name, expert.title, ...expertTags(expert), ...EXPERTS_PAGE_KEYWORDS]),
                    mainEntity: { '@id': `${pageUrl}#person` },
                },
                buildExpertPersonSchema(expert),
            ],
        };
    }

    function searchText(expert) {
        return [
            expert.display_name,
            expert.title,
            expert.summary,
            expert.specialty_label,
            expert.consultation,
            ...(Array.isArray(expert.keywords) ? expert.keywords : []),
            ...(Array.isArray(expert.expertise) ? expert.expertise : []),
        ].filter(Boolean).join(' ');
    }

    function renderExpertTags(tags) {
        const normalized = uniqueList(tags).slice(0, 5);
        if (!normalized.length) return '';
        return `
            <div class="expert-keyword-tags" aria-label="专家关键词">
                ${normalized.map(tag => `<span>${escapeHtml(tag)}</span>`).join('')}
            </div>
        `;
    }

    function renderExpertCards() {
        const grid = $('#expert-list');
        if (!grid) return;

        const cards = state.experts.map(expert => {
            const meta = CATEGORY_META[expert.category] || { label: expert.specialty_label || '专家' };
            return `
                <a class="expert-card" href="${expertHref(expert)}" data-category="${escapeHtml(expert.category || '')}" data-updated-at="${escapeHtml(expert.updated_at || '')}" data-sort-order="${Number(expert.sort_order || 100)}" data-keywords="${escapeHtml(searchText(expert))}">
                    <div class="expert-avatar">${escapeHtml(expertInitials(expert))}</div>
                    <div class="expert-card-main">
                        <div class="expert-card-heading">
                            <h2>${escapeHtml(expert.display_name || '未命名专家')}</h2>
                            <span>${escapeHtml(expert.title || `${meta.label || 'GEO'} 专家`)}</span>
                        </div>
                        <p class="expert-summary">${escapeHtml(expert.summary || '暂无专家介绍')}</p>
                        ${renderExpertTags(expertTags(expert))}
                    </div>
                    <span class="material-symbols-outlined expert-card-arrow" aria-hidden="true">arrow_forward</span>
                </a>
            `;
        }).join('');

        const emptyTitle = state.loadError ? '暂时无法加载专家' : '没有匹配的专家';
        const emptyCopy = state.loadError
            ? '请稍后刷新页面后重试。'
            : '可以换一个关键词，或切回“全部”后重新筛选。';
        grid.innerHTML = `
            ${cards}
            <div class="experts-empty-state${cards ? ' is-hidden' : ''}" data-experts-empty role="status" aria-live="polite">
                <h2>${emptyTitle}</h2>
                <p>${emptyCopy}</p>
            </div>
        `;
        sortExpertCards();
        updateDirectionCounts();
        applyFilters();
    }

    function updateDirectionCounts() {
        const counts = { all: state.experts.length };
        state.experts.forEach(expert => {
            const category = expert.category || '';
            if (category) counts[category] = (counts[category] || 0) + 1;
        });
        $$('[data-expert-count]').forEach(item => {
            const key = item.dataset.expertCount || 'all';
            item.textContent = String(counts[key] || 0);
        });
    }

    function sortExpertCards() {
        const grid = $('#expert-list');
        const emptyState = $('[data-experts-empty]');
        if (!grid) return;
        const cards = $$('.expert-card', grid);
        const sorted = [...cards].sort((a, b) => {
            if (state.sort === 'recent') {
                const aTime = Date.parse(a.dataset.updatedAt || '') || 0;
                const bTime = Date.parse(b.dataset.updatedAt || '') || 0;
                if (aTime !== bTime) return bTime - aTime;
            }
            return Number(a.dataset.sortOrder || 100) - Number(b.dataset.sortOrder || 100);
        });
        sorted.forEach(card => grid.insertBefore(card, emptyState || null));
    }

    function applyFilters() {
        const query = normalize(state.query);
        let visibleCount = 0;

        $$('.expert-card').forEach(card => {
            const category = card.dataset.category || '';
            const haystack = normalize([
                card.textContent || '',
                card.dataset.keywords || '',
            ].join(' '));
            const categoryMatched = state.category === 'all' || category === state.category;
            const queryMatched = !query || haystack.includes(query);
            const isVisible = categoryMatched && queryMatched;
            card.classList.toggle('is-hidden', !isVisible);
            if (isVisible) visibleCount += 1;
        });

        const emptyState = $('[data-experts-empty]');
        if (emptyState) emptyState.classList.toggle('is-hidden', visibleCount > 0);
    }

    function findExpertByKey(key) {
        const normalizedKey = decodeURIComponent(String(key || '')).trim();
        if (!normalizedKey) return null;
        return state.experts.find(expert => {
            return expertKey(expert) === normalizedKey || String(expert.id || '') === normalizedKey;
        }) || null;
    }

    function getRequestedExpertKey() {
        const params = new URLSearchParams(window.location.search);
        const fromQuery = params.get('expert') || params.get('slug') || '';
        if (fromQuery) return fromQuery;

        const segments = window.location.pathname.split('/').filter(Boolean);
        const expertIndex = segments.lastIndexOf('experts');
        if (expertIndex >= 0 && segments[expertIndex + 1]) {
            return segments[expertIndex + 1];
        }
        return '';
    }

    function setViewMode(mode) {
        const listView = $('[data-experts-list-view]');
        const detailView = $('[data-expert-detail-view]');
        const page = $('.experts-page');
        if (listView) listView.classList.toggle('is-hidden', mode === 'detail');
        if (detailView) detailView.classList.toggle('is-hidden', mode !== 'detail');
        if (page) page.classList.toggle('is-detail-mode', mode === 'detail');
    }

    function updateDocumentMeta(expert) {
        if (!expert) {
            document.title = EXPERTS_PAGE_TITLE;
            upsertMetaName('description', EXPERTS_PAGE_DESCRIPTION);
            upsertMetaName('keywords', EXPERTS_PAGE_KEYWORDS.join(','));
            upsertMetaProperty('og:type', 'website');
            upsertMetaProperty('og:title', EXPERTS_PAGE_TITLE);
            upsertMetaProperty('og:description', EXPERTS_PAGE_DESCRIPTION);
            upsertMetaProperty('og:url', absoluteUrl('/experts'));
            upsertCanonical('/experts');
            updateStructuredData(buildExpertsListSchema());
            return;
        }

        const detailTitle = `${expert.display_name || 'GEO 专家'} - ${expert.title || 'GEO 专家'} | 2026 GEO/SEO专家介绍 - GEOrank`;
        const detailDescription = expertDescription(expert);
        const detailKeywords = uniqueList([
            expert.display_name,
            expert.title,
            ...expertTags(expert),
            ...EXPERTS_PAGE_KEYWORDS,
        ]).join(',');

        document.title = detailTitle;
        upsertMetaName('description', detailDescription);
        upsertMetaName('keywords', detailKeywords);
        upsertMetaProperty('og:type', 'profile');
        upsertMetaProperty('og:title', detailTitle);
        upsertMetaProperty('og:description', detailDescription);
        upsertMetaProperty('og:url', absoluteUrl(expertHref(expert)));
        upsertCanonical(expertHref(expert));
        updateStructuredData(buildExpertDetailSchema(expert, detailTitle, detailDescription));
    }

    function renderDetailLinks(expert) {
        if (!Array.isArray(expert.links) || !expert.links.length) return '';
        return `
            <div class="expert-detail-links">
                ${expert.links.map(link => `
                    <a href="${escapeHtml(link.href)}" target="_blank" rel="noopener noreferrer">
                        ${escapeHtml(link.label || '查看资料')}
                        <span class="material-symbols-outlined" aria-hidden="true">open_in_new</span>
                    </a>
                `).join('')}
            </div>
        `;
    }

    function renderDetail(expert) {
        const detailView = $('[data-expert-detail-view]');
        if (!detailView) return;

        if (!expert) {
            setViewMode('detail');
            updateDocumentMeta(null);
            detailView.innerHTML = `
                <a class="expert-back-link" href="/experts">
                    <span class="material-symbols-outlined" aria-hidden="true">arrow_back</span>
                    返回专家列表
                </a>
                <div class="expert-not-found">
                    <h1>没有找到这位专家</h1>
                    <p>可以返回专家频道，查看当前已收录的 GEO 与 AI 实践专家。</p>
                </div>
            `;
            return;
        }

        const meta = CATEGORY_META[expert.category] || { label: expert.specialty_label || '专家', icon: 'person_search' };
        const paragraphs = String(expert.consultation || '')
            .split(/\n\s*\n/)
            .map(item => item.trim())
            .filter(Boolean);
        const detailParagraphs = paragraphs.length ? paragraphs : [expert.summary].filter(Boolean);
        const highlights = uniqueList(Array.isArray(expert.expertise) ? expert.expertise : []);

        setViewMode('detail');
        updateDocumentMeta(expert);
        detailView.innerHTML = `
            <a class="expert-back-link" href="/experts">
                <span class="material-symbols-outlined" aria-hidden="true">arrow_back</span>
                返回专家列表
            </a>

            <article class="expert-detail-card">
                <header class="expert-detail-hero">
                    <div class="expert-detail-avatar">${escapeHtml(expertInitials(expert))}</div>
                    <div>
                        <p class="experts-eyebrow">${escapeHtml(meta.label || expert.specialty_label || 'GEO Expert')}</p>
                        <h1>${escapeHtml(expert.display_name || '未命名专家')}</h1>
                        <p class="expert-detail-title">${escapeHtml(expert.title || 'GEO 专家')}</p>
                        ${renderExpertTags(expertTags(expert))}
                    </div>
                </header>

                <section class="expert-detail-section">
                    <h2>专家介绍</h2>
                    <div class="expert-detail-body">
                        ${detailParagraphs.map(item => `<p>${escapeHtml(item)}</p>`).join('')}
                    </div>
                    ${renderDetailLinks(expert)}
                </section>

                ${highlights.length ? `
                    <section class="expert-detail-section">
                        <h2>代表经历与能力</h2>
                        <ul class="expert-highlight-list">
                            ${highlights.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
                        </ul>
                    </section>
                ` : ''}
            </article>
        `;
    }

    function normalizeApiExpert(apiExpert) {
        return {
            id: apiExpert.id || '',
            slug: apiExpert.slug || apiExpert.id || '',
            display_name: apiExpert.display_name || '未命名专家',
            avatar_initials: apiExpert.avatar_initials || '',
            title: apiExpert.title || 'GEO 专家',
            category: apiExpert.category || 'strategy',
            specialty_label: apiExpert.specialty_label || '',
            summary: apiExpert.summary || '',
            expertise: Array.isArray(apiExpert.expertise) ? apiExpert.expertise : [],
            keywords: Array.isArray(apiExpert.keywords) ? apiExpert.keywords : [],
            consultation: apiExpert.consultation || '',
            sort_order: Number(apiExpert.sort_order || 100),
            updated_at: apiExpert.updated_at || '',
        };
    }

    async function loadPublishedExperts() {
        try {
            const response = await fetch(`${API_BASE}/api/experts`, { headers: { Accept: 'application/json' } });
            if (!response.ok) throw new Error(`API ${response.status}`);
            const data = await response.json();
            state.experts = (Array.isArray(data.items) ? data.items : []).map(normalizeApiExpert)
                .sort((a, b) => Number(a.sort_order || 100) - Number(b.sort_order || 100));
            renderPage();
        } catch (_) {
            state.loadError = 'load_failed';
            renderPage();
        }
    }

    function renderPage() {
        if (state.activeExpertKey) {
            updateDirectionCounts();
            const expert = findExpertByKey(state.activeExpertKey);
            renderDetail(expert);
            return;
        }
        setViewMode('list');
        updateDocumentMeta(null);
        renderExpertCards();
    }

    function refreshCurrentMeta() {
        if (state.activeExpertKey) {
            updateDocumentMeta(findExpertByKey(state.activeExpertKey));
            return;
        }
        updateDocumentMeta(null);
    }

    function bindFilters() {
        $$('[data-expert-filter]').forEach(button => {
            button.addEventListener('click', () => {
                state.category = button.dataset.expertFilter || 'all';
                $$('[data-expert-filter]').forEach(item => {
                    const isActive = (item.dataset.expertFilter || 'all') === state.category;
                    item.classList.toggle('is-active', isActive);
                    item.setAttribute('aria-pressed', String(isActive));
                });
                applyFilters();
            });
        });

        $$('[data-expert-sort]').forEach(button => {
            button.addEventListener('click', () => {
                state.sort = button.dataset.expertSort || 'recommended';
                $$('[data-expert-sort]').forEach(item => {
                    const isActive = (item.dataset.expertSort || 'recommended') === state.sort;
                    item.classList.toggle('is-active', isActive);
                    item.setAttribute('aria-pressed', String(isActive));
                });
                sortExpertCards();
                applyFilters();
            });
        });

        $('#expert-search')?.addEventListener('input', event => {
            state.query = event.target.value;
            applyFilters();
        });
    }

    document.addEventListener('georank:site-settings-applied', refreshCurrentMeta);

    document.addEventListener('DOMContentLoaded', () => {
        state.activeExpertKey = getRequestedExpertKey();
        bindFilters();
        loadPublishedExperts();
    });
})();
