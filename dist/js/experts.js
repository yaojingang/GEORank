/**
 * GEOrank - 专家频道筛选
 */
(function () {
    'use strict';

    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
    const API_BASE = ['80', '443', ''].includes(window.location.port)
        ? ''
        : `${window.location.protocol}//${window.location.hostname}:8000`;

    const state = {
        category: 'all',
        query: '',
        sort: 'recommended',
    };

    const CATEGORY_META = {
        strategy: { label: '策略', icon: 'route', tags: ['路线图', '诊断拆解', '增长节奏'] },
        technical: { label: '技术', icon: 'data_object', tags: ['Schema', 'JSON-LD', '抓取检查'] },
        content: { label: '内容', icon: 'article', tags: ['内容结构', 'FAQ', '可引用事实'] },
        reputation: { label: '品牌治理', icon: 'verified', tags: ['可信来源', '案例证据', '实体识别'] },
        industry: { label: '行业', icon: 'cases', tags: ['行业案例', '竞品对标', '转化页'] },
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

    function expertInitials(expert) {
        const explicit = String(expert?.avatar_initials || '').trim();
        if (explicit) return explicit.slice(0, 4).toUpperCase();
        return String(expert?.display_name || 'EX')
            .replace(/[^A-Za-z\u4e00-\u9fa5]/g, '')
            .slice(0, 2)
            .toUpperCase() || 'EX';
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

    function expertTags(expert, meta) {
        const keywords = Array.isArray(expert.keywords) ? expert.keywords : [];
        const expertise = Array.isArray(expert.expertise) ? expert.expertise : [];
        return uniqueList([
            expert.specialty_label || meta?.label || '',
            ...keywords,
            ...expertise,
            ...(Array.isArray(meta?.tags) ? meta.tags : []),
            'GEO',
        ]).slice(0, 5);
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

    function updateDirectionCounts() {
        const counts = { all: 0 };
        $$('.expert-card').forEach(card => {
            const category = card.dataset.category || '';
            counts.all += 1;
            if (category) counts[category] = (counts[category] || 0) + 1;
        });
        $$('[data-expert-count]').forEach(item => {
            const key = item.dataset.expertCount || 'all';
            item.textContent = String(counts[key] || 0);
        });
    }

    function indexExpertCards() {
        $$('.expert-card').forEach((card, index) => {
            if (!card.dataset.originalIndex) {
                card.dataset.originalIndex = String(index);
            }
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
                return Number(b.dataset.originalIndex || 0) - Number(a.dataset.originalIndex || 0);
            }
            return Number(a.dataset.originalIndex || 0) - Number(b.dataset.originalIndex || 0);
        });
        sorted.forEach(card => grid.insertBefore(card, emptyState || null));
    }

    function renderExpertCards(items) {
        const grid = $('#expert-list');
        const emptyState = $('[data-experts-empty]');
        if (!grid || !Array.isArray(items) || !items.length) return;

        $$('.expert-card', grid).forEach(card => card.remove());
        const fragment = document.createDocumentFragment();
        items.forEach(expert => {
            const expertise = Array.isArray(expert.expertise) ? expert.expertise : [];
            const keywords = Array.isArray(expert.keywords) ? expert.keywords : [];
            const meta = CATEGORY_META[expert.category] || {
                label: expert.specialty_label || '专家',
                icon: 'person_search',
                tags: ['GEO', '专家', 'AI 搜索'],
            };
            const article = document.createElement('article');
            article.className = 'expert-card';
            article.dataset.category = expert.category || '';
            article.dataset.updatedAt = expert.updated_at || expert.created_at || '';
            article.dataset.keywords = [
                expert.display_name,
                expert.title,
                expert.summary,
                expert.consultation,
                expert.specialty_label,
                ...expertise,
                ...keywords,
            ].filter(Boolean).join(' ');
            article.innerHTML = `
                <div class="expert-avatar">${escapeHtml(expertInitials(expert))}</div>
                <div class="expert-card-main">
                    <div class="expert-card-heading">
                        <h2>${escapeHtml(expert.display_name || '未命名专家')}</h2>
                        <span>${escapeHtml(expert.title || 'GEO 专家')}</span>
                    </div>
                    <p class="expert-summary">${escapeHtml(expert.summary || '暂无专家介绍')}</p>
                    ${renderExpertTags(expertTags(expert, meta))}
                </div>
            `;
            fragment.appendChild(article);
        });

        grid.insertBefore(fragment, emptyState || null);
        indexExpertCards();
        sortExpertCards();
        updateDirectionCounts();
    }

    async function loadPublishedExperts() {
        try {
            const response = await fetch(`${API_BASE}/api/experts?size=100`, { headers: { Accept: 'application/json' } });
            if (!response.ok) return;
            const data = await response.json();
            if (Array.isArray(data.items) && data.items.length) {
                renderExpertCards(data.items);
                applyFilters();
            }
        } catch (_) {
            // 静态示例会继续作为前台兜底，不打断用户浏览。
        }
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
            if (isVisible) {
                visibleCount += 1;
            }
        });

        const emptyState = $('[data-experts-empty]');
        if (emptyState) {
            emptyState.classList.toggle('is-hidden', visibleCount > 0);
        }
    }

    function bindFilters() {
        indexExpertCards();
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

    document.addEventListener('DOMContentLoaded', () => {
        bindFilters();
        updateDirectionCounts();
        applyFilters();
        loadPublishedExperts();
    });
})();
