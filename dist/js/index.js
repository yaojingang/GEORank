/**
 * Index Page - 公司目录动态加载
 */
(function () {
    'use strict';

    const API_BASE = ['80', '443', ''].includes(window.location.port)
        ? ''
        : `${window.location.protocol}//${window.location.hostname}:8000`;
    const Routes = window.GEOrank?.Routes;

    const state = {
        sort: 'newest',
        page: 1,
        pages: 1,
        items: [],
        tutorials: [],
        popularCompanies: [],
    };

    const elements = {
        companyList: document.getElementById('company-list'),
        loadMore: document.getElementById('company-load-more'),
        sortNewest: document.getElementById('company-sort-newest'),
        sortUpvotes: document.getElementById('company-sort-upvotes'),
        featuredTipTitle: document.getElementById('featured-tip-title'),
        featuredTipCopy: document.getElementById('featured-tip-copy'),
        featuredTipLink: document.getElementById('featured-tip-link'),
        hotGuidesList: document.getElementById('hot-guides-list'),
        hotCompaniesList: document.getElementById('hot-companies-list'),
        resourceLinks: document.getElementById('resource-links'),
    };

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    function request(path) {
        return fetch(`${API_BASE}${path}`).then(async (response) => {
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                const message = data.detail || `请求失败 (${response.status})`;
                throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
            }
            return data;
        });
    }

    function buildCompanyLink(company) {
        if (Routes?.buildCompanyDetail) {
            return Routes.buildCompanyDetail(company?.path_key || company?.id || '');
        }
        const url = new URL('/company', window.location.origin);
        url.searchParams.set('id', company?.id || '');
        return url.toString();
    }

    function buildTutorialLink(pathKey, slug = '') {
        if (Routes?.buildTutorialDetail) {
            return Routes.buildTutorialDetail(pathKey || slug);
        }
        const url = new URL('/tutorial', window.location.origin);
        if (slug) url.searchParams.set('slug', slug);
        return url.toString();
    }

    function tutorialCategory(item) {
        return Array.isArray(item?.tags) && item.tags.length ? item.tags[0] : '教程';
    }

    function renderCompanyLogo(company) {
        if (company.logo_url) {
            return `<img alt="${escapeHtml(company.name)} Logo" class="w-full h-full object-cover" src="${escapeHtml(company.logo_url)}">`;
        }
        const initials = String(company.name || '?')
            .split(/\s+/)
            .map((part) => part.slice(0, 1))
            .join('')
            .slice(0, 2)
            .toUpperCase();
        return `<div class="w-full h-full flex items-center justify-center text-sm font-extrabold text-primary">${escapeHtml(initials || '?')}</div>`;
    }

    function renderCompanyCard(company) {
        const tags = Array.isArray(company.tags) ? company.tags.slice(0, 3) : [];
        const metaTags = [company.category, company.funding_stage, company.headquarters].filter(Boolean);
        return `
            <div class="group flex items-start gap-4 md:gap-6 p-3 md:p-4 rounded-xl hover:bg-slate-50 transition-colors duration-300">
                <div class="w-14 h-14 md:w-20 md:h-20 rounded-xl overflow-hidden flex-shrink-0 bg-neutral-100 border border-slate-100">
                    ${renderCompanyLogo(company)}
                </div>
                <div class="flex-grow min-w-0">
                    <a href="${buildCompanyLink(company)}" class="block">
                        <div class="flex items-center gap-2 mb-1">
                            <h3 class="text-base md:text-lg font-bold font-headline truncate group-hover:text-primary transition-colors">${escapeHtml(company.name)}</h3>
                            ${company.is_geo_certified ? '<span class="material-symbols-outlined text-primary text-sm filled">verified</span>' : ''}
                        </div>
                    </a>
                    <p class="text-on-surface-variant text-sm mb-3 line-clamp-2">${escapeHtml(company.short_description || '该公司暂未补充简介')}</p>
                    <div class="flex flex-wrap gap-2">
                        ${tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                        ${!tags.length && metaTags.length ? metaTags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join('') : ''}
                    </div>
                </div>
                <button type="button" disabled title="用户投票功能即将开放" class="flex flex-col items-center justify-center border border-slate-100 rounded-lg px-3 py-2 bg-white/80 text-slate-400 min-w-[52px] cursor-not-allowed">
                    <span class="material-symbols-outlined text-sm">arrow_drop_up</span>
                    <span class="text-xs md:text-sm font-bold mt-1">${Number(company.upvotes || 0).toLocaleString('zh-CN')}</span>
                </button>
            </div>
        `;
    }

    function updateSortButtons() {
        [
            [elements.sortNewest, 'newest'],
            [elements.sortUpvotes, 'upvotes'],
        ].forEach(([button, value]) => {
            if (!button) return;
            const isActive = state.sort === value;
            button.className = isActive
                ? 'text-sm font-semibold text-primary flex items-center gap-1'
                : 'text-sm font-semibold text-neutral-400 hover:text-neutral-900 transition-colors';
        });
    }

    function renderCompanyList(append = false) {
        if (!elements.companyList) return;
        if (!state.items.length) {
            elements.companyList.innerHTML = `
                <div class="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-8 text-sm text-slate-400">
                    当前没有可展示的已发布公司，稍后再来查看。
                </div>
            `;
            return;
        }

        if (append) {
            elements.companyList.insertAdjacentHTML('beforeend', state.items.slice(-6).map(renderCompanyCard).join(''));
        } else {
            elements.companyList.innerHTML = state.items.map(renderCompanyCard).join('');
        }
    }

    function renderHotGuides() {
        if (!elements.hotGuidesList) return;
        const guides = [...state.tutorials]
            .sort((a, b) => {
                const byViews = Number(b.view_count || 0) - Number(a.view_count || 0);
                if (byViews) return byViews;
                return new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime();
            })
            .slice(0, 3);

        if (!guides.length) {
            elements.hotGuidesList.innerHTML = '<span class="px-3 py-4 text-sm text-slate-400 border border-dashed border-slate-200 rounded-xl block">暂无热门指南</span>';
            return;
        }

        elements.hotGuidesList.innerHTML = guides.map((item) => `
            <a href="${buildTutorialLink(item.path_key, item.slug)}" class="block rounded-2xl border border-slate-100 bg-white px-4 py-4 transition-all hover:border-primary/20 hover:bg-slate-50">
                <div class="flex items-center justify-between gap-3">
                    <span class="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">${escapeHtml(tutorialCategory(item))}</span>
                    <span class="text-[11px] font-semibold text-slate-400">${Number(item.reading_time_minutes || 3)} 分钟</span>
                </div>
                <p class="mt-3 text-sm font-bold leading-6 text-slate-800">${escapeHtml(item.title)}</p>
                <p class="mt-2 text-xs leading-6 text-slate-500">适合快速补齐 ${escapeHtml(tutorialCategory(item))} 里的核心知识点与执行思路。</p>
            </a>
        `).join('');
    }

    function renderHotCompanies() {
        if (!elements.hotCompaniesList) return;
        const companies = state.popularCompanies.slice(0, 3);
        if (!companies.length) {
            elements.hotCompaniesList.innerHTML = '<span class="px-3 py-4 text-sm text-slate-400 border border-dashed border-slate-200 rounded-xl block">暂无热门公司</span>';
            return;
        }

        elements.hotCompaniesList.innerHTML = companies.map((company) => {
            const tags = Array.isArray(company.tags) ? company.tags.slice(0, 2) : [];
            return `
                <a href="${buildCompanyLink(company)}" class="flex items-start gap-3 rounded-2xl border border-slate-100 bg-white px-4 py-4 transition-all hover:border-primary/20 hover:bg-slate-50">
                    <div class="w-11 h-11 rounded-xl overflow-hidden flex-shrink-0 bg-slate-50 border border-slate-100">
                        ${renderCompanyLogo(company)}
                    </div>
                    <div class="min-w-0 flex-1">
                        <div class="flex items-center gap-2">
                            <p class="text-sm font-bold leading-6 text-slate-800 truncate">${escapeHtml(company.name)}</p>
                            ${company.is_geo_certified ? '<span class="material-symbols-outlined text-primary text-sm filled">verified</span>' : ''}
                        </div>
                        <p class="mt-1 text-xs leading-6 text-slate-500 line-clamp-2">${escapeHtml(company.short_description || '正在构建生成式搜索时代的 GEO 能力与内容分发体系。')}</p>
                        <div class="mt-2 flex flex-wrap gap-2">
                            ${(tags.length ? tags : [company.category || 'GEO']).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                        </div>
                    </div>
                </a>
            `;
        }).join('');
    }

    function renderTutorialSidebar() {
        const orderedTutorials = [...state.tutorials].sort((a, b) => {
            const byViews = Number(b.view_count || 0) - Number(a.view_count || 0);
            if (byViews) return byViews;
            return new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime();
        });
        const [featured, ...rest] = orderedTutorials;
        if (featured && elements.featuredTipTitle && elements.featuredTipLink) {
            elements.featuredTipTitle.textContent = featured.title;
            elements.featuredTipLink.href = buildTutorialLink(featured.path_key, featured.slug);
            if (elements.featuredTipCopy) {
                elements.featuredTipCopy.textContent = `来自教程频道「${tutorialCategory(featured)}」章节，预计 ${Number(featured.reading_time_minutes || 3)} 分钟读完，适合作为今天的 GEO 学习起点。`;
            }
        }
        renderHotGuides();
        renderHotCompanies();

        if (!elements.resourceLinks) return;
        if (!state.tutorials.length) {
            elements.resourceLinks.innerHTML = '<span class="px-3 py-4 text-sm text-slate-400 border border-dashed border-slate-200 rounded-xl">暂无教程资源</span>';
            return;
        }

        const resourceItems = (rest.length ? rest : state.tutorials).slice(0, 3);
        elements.resourceLinks.innerHTML = resourceItems.map((item, index) => `
            <a href="${buildTutorialLink(item.path_key, item.slug)}" class="flex items-center gap-3 p-3 rounded-xl border border-slate-50 hover:bg-slate-50 hover:shadow-sm transition-all group">
                <div class="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center text-primary">
                    <span class="material-symbols-outlined text-sm">${index === 0 ? 'library_books' : index === 1 ? 'menu_book' : 'auto_stories'}</span>
                </div>
                <span class="text-sm font-semibold text-slate-700 group-hover:text-primary">${escapeHtml(item.title)}</span>
            </a>
        `).join('');
    }

    async function loadTutorialResources() {
        try {
            state.tutorials = await request('/api/content/?content_type=tutorial&size=8');
            renderTutorialSidebar();
        } catch (_) {
            renderTutorialSidebar();
        }
    }

    async function loadPopularCompanies() {
        try {
            const payload = await request('/api/companies/?page=1&size=3&sort=upvotes');
            state.popularCompanies = Array.isArray(payload.items) ? payload.items : [];
            renderHotCompanies();
        } catch (_) {
            renderHotCompanies();
        }
    }

    async function loadCompanies(options = {}) {
        const { append = false } = options;
        if (!elements.companyList) return;

        if (!append) {
            elements.companyList.innerHTML = `
                <div class="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-8 text-sm text-slate-400">
                    正在加载公司目录...
                </div>
            `;
        }

        const size = 6;
        try {
            const payload = await request(`/api/companies/?page=${state.page}&size=${size}&sort=${state.sort}`);
            state.pages = Number(payload.pages || 1);
            const incoming = Array.isArray(payload.items) ? payload.items : [];
            state.items = append ? state.items.concat(incoming) : incoming;
            renderCompanyList(append);
            renderHotCompanies();

            if (elements.loadMore) {
                const hasMore = state.page < state.pages;
                elements.loadMore.disabled = !hasMore;
                elements.loadMore.classList.toggle('hidden', !state.items.length);
                elements.loadMore.textContent = hasMore ? '加载更多发现' : '已经到底了';
            }
        } catch (error) {
            elements.companyList.innerHTML = `
                <div class="rounded-2xl border border-dashed border-red-200 bg-red-50/60 p-8 text-sm text-red-500">
                    加载公司目录失败：${escapeHtml(error.message)}
                </div>
            `;
            if (elements.loadMore) elements.loadMore.disabled = true;
        }
    }

    function bindEvents() {
        document.querySelectorAll('[data-company-sort]').forEach((button) => {
            button.addEventListener('click', async () => {
                const nextSort = button.dataset.companySort;
                if (!nextSort || nextSort === state.sort) return;
                state.sort = nextSort;
                state.page = 1;
                updateSortButtons();
                await loadCompanies();
            });
        });

        elements.loadMore?.addEventListener('click', async () => {
            if (state.page >= state.pages) return;
            state.page += 1;
            await loadCompanies({ append: true });
        });
    }

    async function init() {
        updateSortButtons();
        bindEvents();
        await Promise.all([
            loadCompanies(),
            loadTutorialResources(),
            loadPopularCompanies(),
        ]);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
