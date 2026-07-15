/**
 * Tutorial Page - GEO 教程交互
 */
(function () {
    'use strict';

    const API_BASE = ['80', '443', ''].includes(window.location.port)
        ? ''
        : `${window.location.protocol}//${window.location.hostname}:8000`;
    const Routes = window.GEOrank?.Routes;
    const TUTORIAL_CHAPTER_ORDER = [
        'GEO认知',
        'AI原理',
        '内容优化',
        '页面技术',
        '策略执行',
        '评估治理',
        '实战案例',
    ];
    const TUTORIAL_CHAPTER_ICONS = {
        'GEO认知': 'travel_explore',
        'AI原理': 'neurology',
        '内容优化': 'edit_note',
        '页面技术': 'code_blocks',
        '策略执行': 'conversion_path',
        '评估治理': 'query_stats',
        '实战案例': 'folder_managed',
    };
    const TUTORIAL_ARTICLE_ORDER = {
        'GEO认知': ['GEO是什么', 'GEO与SEO', '商业价值', '行业影响'],
        'AI原理': ['LLM基础', 'RAG流程', '答案生成', 'AI搜索'],
        '内容优化': ['EEAT原则', '答案优先', '结构化写法', '差异化内容'],
        '页面技术': ['产品页优化', 'Schema标记', 'llms协议', '内容分块'],
        '策略执行': ['长尾规划', '官网优先', '信源运营', '推荐逻辑'],
        '评估治理': ['排名指标', '心智指标', '转化归因', '合规治理'],
        '实战案例': ['国内概览', 'SaaS案例', '金融案例', '本地案例'],
    };

    const state = {
        tutorials: [],
        currentSlug: '',
        currentPathKey: '',
        currentDetail: null,
    };

    const elements = {
        sideNav: document.getElementById('side-nav'),
        mobileNav: document.getElementById('tutorial-mobile-nav'),
        mainShell: document.getElementById('tutorial-main-shell'),
        breadcrumbCategory: document.getElementById('tutorial-breadcrumb-category'),
        breadcrumbTitle: document.getElementById('tutorial-breadcrumb-title'),
        title: document.getElementById('tutorial-title'),
        overview: document.getElementById('tutorial-overview'),
        readingTime: document.getElementById('tutorial-reading-time'),
        updatedAt: document.getElementById('tutorial-updated-at'),
        header: document.getElementById('tutorial-header'),
        article: document.getElementById('tutorial-article'),
        toc: document.getElementById('toc-nav'),
        feedback: document.getElementById('tutorial-feedback'),
        secondaryTitle: document.getElementById('tutorial-secondary-title'),
    };

    let progressBar = null;
    let tocScrollHandler = null;

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    function slugify(text) {
        return String(text || '')
            .toLowerCase()
            .trim()
            .replace(/<[^>]*>/g, '')
            .replace(/[\s\W-]+/g, '-')
            .replace(/^-+|-+$/g, '');
    }

    function normalizeText(text) {
        return String(text || '').replace(/\s+/g, ' ').trim();
    }

    function formatDate(value) {
        if (!value) return '--';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '--';
        return new Intl.DateTimeFormat('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        }).format(date);
    }

    function formatReadingTime(minutes) {
        const value = Number(minutes || 0);
        if (!value) return '预计阅读时间：待估算';
        return `预计阅读时间：${value} 分钟`;
    }

    function buildTutorialDetailHref(identifier) {
        if (Routes?.buildTutorialDetail) {
            return Routes.buildTutorialDetail(identifier);
        }
        const url = new URL('/tutorial', window.location.origin);
        if (identifier) url.searchParams.set('slug', identifier);
        return url.toString();
    }

    function getTutorialCategory(item) {
        const tags = Array.isArray(item?.tags) ? item.tags : [];
        return tags[0] || '其他';
    }

    function compareTutorials(a, b) {
        const aCategory = getTutorialCategory(a);
        const bCategory = getTutorialCategory(b);
        const categoryIndexA = TUTORIAL_CHAPTER_ORDER.indexOf(aCategory);
        const categoryIndexB = TUTORIAL_CHAPTER_ORDER.indexOf(bCategory);
        const normalizedCategoryIndexA = categoryIndexA === -1 ? Number.MAX_SAFE_INTEGER : categoryIndexA;
        const normalizedCategoryIndexB = categoryIndexB === -1 ? Number.MAX_SAFE_INTEGER : categoryIndexB;

        if (normalizedCategoryIndexA !== normalizedCategoryIndexB) {
            return normalizedCategoryIndexA - normalizedCategoryIndexB;
        }

        const articleOrder = TUTORIAL_ARTICLE_ORDER[aCategory] || [];
        const articleIndexA = articleOrder.indexOf(a?.title || '');
        const articleIndexB = articleOrder.indexOf(b?.title || '');
        const normalizedArticleIndexA = articleIndexA === -1 ? Number.MAX_SAFE_INTEGER : articleIndexA;
        const normalizedArticleIndexB = articleIndexB === -1 ? Number.MAX_SAFE_INTEGER : articleIndexB;

        if (normalizedArticleIndexA !== normalizedArticleIndexB) {
            return normalizedArticleIndexA - normalizedArticleIndexB;
        }

        const timeA = new Date(a?.updated_at || a?.created_at || 0).getTime();
        const timeB = new Date(b?.updated_at || b?.created_at || 0).getTime();
        return timeA - timeB;
    }

    function getTutorialRouteKey(item) {
        return item?.path_key || item?.slug || '';
    }

    function findTutorialByIdentifier(identifier) {
        return state.tutorials.find(
            (item) => getTutorialRouteKey(item) === identifier || item.slug === identifier
        ) || null;
    }

    function applySiteBrand(text) {
        return window.GEOrank?.SiteSettings?.replaceBrand?.(text) || text;
    }

    function setDocumentMeta(title, description) {
        document.title = applySiteBrand(title);
        const descriptionMeta = document.querySelector('meta[name="description"]');
        if (descriptionMeta) {
            descriptionMeta.setAttribute('content', description);
        }
    }

    function getRouteIdentifier() {
        if (Routes?.readTutorialSlug) {
            return Routes.readTutorialSlug();
        }
        return new URLSearchParams(window.location.search).get('slug');
    }

    function setRouteIdentifier(identifier) {
        if (Routes?.buildTutorialDetail) {
            history.replaceState({ identifier }, '', Routes.buildTutorialDetail(identifier));
            return;
        }
        const url = new URL(window.location.href);
        if (identifier) url.searchParams.set('slug', identifier);
        else url.searchParams.delete('slug');
        history.replaceState({ identifier }, '', url.toString());
    }

    async function fetchJson(path) {
        const response = await fetch(`${API_BASE}${path}`);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = data.detail || `请求失败 (${response.status})`;
            throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
        }
        return data;
    }

    function ensureProgressBar() {
        if (progressBar) return progressBar;
        progressBar = document.createElement('div');
        progressBar.className = 'reading-progress';
        progressBar.style.width = '0%';
        document.body.appendChild(progressBar);
        return progressBar;
    }

    function updateReadingProgress() {
        const bar = ensureProgressBar();
        if (!state.currentDetail) {
            bar.style.width = '0%';
            return;
        }
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const progress = docHeight > 0 ? (window.scrollY / docHeight) * 100 : 0;
        bar.style.width = `${Math.min(progress, 100)}%`;
    }

    function getGroupedTutorials() {
        const tutorials = [...state.tutorials].sort(compareTutorials);
        const groups = new Map();
        tutorials.forEach((tutorial) => {
            const category = getTutorialCategory(tutorial);
            if (!groups.has(category)) groups.set(category, []);
            groups.get(category).push(tutorial);
        });
        return Array.from(groups.entries());
    }

    function renderSideNav() {
        if (!elements.sideNav) return;
        const groups = getGroupedTutorials();
        elements.sideNav.innerHTML = groups.map(([category, items]) => `
            <section class="tutorial-nav-group">
                <div class="tutorial-nav-group-header">
                    <span class="material-symbols-outlined tutorial-nav-group-icon">${escapeHtml(TUTORIAL_CHAPTER_ICONS[category] || 'library_books')}</span>
                    <p class="tutorial-nav-group-title">${escapeHtml(category)}</p>
                </div>
                <div class="tutorial-nav-tree">
                    ${items.map((item) => `
                        <button
                            type="button"
                            class="tutorial-side-link ${getTutorialRouteKey(item) === state.currentPathKey ? 'is-active' : ''}"
                            data-tutorial-key="${escapeHtml(getTutorialRouteKey(item))}"
                        >
                            <span class="tutorial-side-link-main">
                                <span class="material-symbols-outlined tutorial-side-link-icon">article</span>
                                <span class="tutorial-side-link-label">${escapeHtml(item.title)}</span>
                            </span>
                        </button>
                    `).join('')}
                </div>
            </section>
        `).join('');
    }

    function renderMobileNav() {
        if (!elements.mobileNav) return;
        elements.mobileNav.innerHTML = state.tutorials.map((item) => `
            <button
                type="button"
                class="tutorial-mobile-chip ${getTutorialRouteKey(item) === state.currentPathKey ? 'is-active' : ''}"
                data-tutorial-key="${escapeHtml(getTutorialRouteKey(item))}"
            >
                ${escapeHtml(item.title)}
            </button>
        `).join('');
    }

    function renderEmptyState(message) {
        document.body.classList.remove('tutorial-channel-home');
        state.currentDetail = null;
        state.currentPathKey = '';
        const empty = escapeHtml(message || '当前暂无已发布教程');
        if (elements.sideNav) {
            elements.sideNav.innerHTML = `<div class="tutorial-state-card">${empty}</div>`;
        }
        if (elements.mobileNav) {
            elements.mobileNav.innerHTML = `<span class="px-3 py-1.5 text-xs font-medium text-slate-400 whitespace-nowrap">${empty}</span>`;
        }
        if (elements.title) elements.title.textContent = '暂无教程内容';
        if (elements.overview) {
            elements.overview.classList.add('hidden');
            elements.overview.textContent = '';
        }
        if (elements.breadcrumbTitle) elements.breadcrumbTitle.textContent = '暂无内容';
        if (elements.breadcrumbCategory) elements.breadcrumbCategory.textContent = '教程';
        if (elements.readingTime) elements.readingTime.innerHTML = '<span class="material-symbols-outlined text-sm">schedule</span> 预计阅读时间：--';
        if (elements.updatedAt) {
            elements.updatedAt.classList.remove('hidden');
            elements.updatedAt.innerHTML = '<span class="material-symbols-outlined text-sm">update</span> 最后更新：--';
        }
        if (elements.article) {
            elements.article.innerHTML = `<div class="tutorial-state-card">${empty}</div>`;
        }
        if (elements.toc) {
            elements.toc.innerHTML = '<span class="block text-sm text-slate-400 px-3 py-1.5">暂无目录</span>';
        }
        if (elements.feedback) {
            elements.feedback.classList.add('hidden');
        }
        if (elements.secondaryTitle) {
            elements.secondaryTitle.textContent = '栏目索引';
        }
        setDocumentMeta('GEO 教程中心 - GEOrank', 'GEO 生成式引擎优化教程中心 — 科普教程、最佳实践与技术文档。');
        updateReadingProgress();
    }

    function renderLoadingArticle() {
        if (!elements.article) return;
        elements.article.innerHTML = `
            <div class="tutorial-state-card">
                正在加载教程正文...
            </div>
        `;
    }

    function decorateArticle() {
        const articleRoot = elements.article?.querySelector('.tutorial-prose');
        if (!articleRoot) return [];

        const headings = Array.from(articleRoot.querySelectorAll('h2, h3, h4'));
        headings.forEach((heading, index) => {
            if (!heading.id) {
                const baseId = slugify(heading.textContent) || `section-${index + 1}`;
                let candidate = baseId;
                let suffix = 1;
                while (document.getElementById(candidate)) {
                    candidate = `${baseId}-${suffix++}`;
                }
                heading.id = candidate;
            }
        });

        articleRoot.querySelectorAll('pre').forEach((pre) => {
            if (pre.querySelector('.code-copy-btn')) return;
            const copyBtn = document.createElement('button');
            copyBtn.type = 'button';
            copyBtn.className = 'code-copy-btn';
            copyBtn.textContent = '复制';
            pre.style.position = 'relative';
            pre.appendChild(copyBtn);

            copyBtn.addEventListener('click', async () => {
                const code = pre.querySelector('code')?.textContent || '';
                try {
                    if (navigator.clipboard?.writeText) {
                        await navigator.clipboard.writeText(code);
                    } else {
                        const input = document.createElement('textarea');
                        input.value = code;
                        document.body.appendChild(input);
                        input.select();
                        document.execCommand('copy');
                        input.remove();
                    }
                    copyBtn.textContent = '已复制';
                    setTimeout(() => {
                        copyBtn.textContent = '复制';
                    }, 1600);
                } catch (_) {
                    copyBtn.textContent = '失败';
                    setTimeout(() => {
                        copyBtn.textContent = '复制';
                    }, 1600);
                }
            });
        });

        return headings;
    }

    function renderToc(headings) {
        if (!elements.toc) return;
        if (!headings.length) {
            elements.toc.innerHTML = '<span class="block text-sm text-slate-400 px-3 py-1.5">当前文章暂无目录</span>';
            return;
        }

        elements.toc.innerHTML = headings.map((heading) => {
            const level = heading.tagName === 'H2' ? 'pl-3' : heading.tagName === 'H3' ? 'pl-6' : 'pl-9';
            return `
                <a href="#${escapeHtml(heading.id)}" class="tutorial-toc-link ${level}">
                    ${escapeHtml(normalizeText(heading.textContent))}
                </a>
            `;
        }).join('');
    }

    function renderChannelToc() {
        if (!elements.toc) return;
        const groups = getGroupedTutorials();

        elements.toc.innerHTML = `
            <div class="tutorial-channel-sidebar">
                <section class="space-y-2">
                    ${groups.map(([category], index) => `
                        <a href="#tutorial-group-${escapeHtml(slugify(category))}" class="tutorial-channel-sidebar-step-link tutorial-toc-link">
                            <span class="tutorial-channel-sidebar-step-index">${index + 1}</span>
                            <span>${escapeHtml(category)}</span>
                        </a>
                    `).join('')}
                </section>
            </div>
        `;
    }

    function bindTocTracking() {
        if (tocScrollHandler) {
            window.removeEventListener('scroll', tocScrollHandler);
            tocScrollHandler = null;
        }

        const tocLinks = Array.from(elements.toc?.querySelectorAll('a[href^="#"]') || []);
        const tracked = tocLinks.map((link) => {
            const id = link.getAttribute('href')?.slice(1);
            const el = id ? document.getElementById(id) : null;
            return el ? { link, el } : null;
        }).filter(Boolean);

        if (!tracked.length) return;

        tocScrollHandler = () => {
            const scrollPos = window.scrollY + 120;
            let active = tracked[0];
            tracked.forEach((item) => {
                if (item.el.offsetTop <= scrollPos) active = item;
            });

            tracked.forEach(({ link }) => link.classList.remove('active'));
            active?.link.classList.add('active');
        };

        window.addEventListener('scroll', tocScrollHandler, { passive: true });
        tocScrollHandler();
    }

    function initSmoothScroll() {
        document.querySelectorAll('a[href^="#"], button[data-anchor-target]').forEach((element) => {
            if (element.dataset.anchorBound === 'true') return;
            element.dataset.anchorBound = 'true';
            element.addEventListener('click', (event) => {
                const href = element.getAttribute('href');
                const targetId = element.dataset.anchorTarget || (href ? href.slice(1) : '');
                const target = targetId ? document.getElementById(targetId) : null;
                if (!target) return;
                event.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        });
    }

    function renderArticle(detail) {
        document.body.classList.remove('tutorial-channel-home');
        const tags = Array.isArray(detail?.tags) ? detail.tags : [];
        const category = tags[0] || '教程';

        state.currentDetail = detail;
        if (elements.breadcrumbCategory) elements.breadcrumbCategory.textContent = category;
        if (elements.breadcrumbTitle) elements.breadcrumbTitle.textContent = detail.title || '教程详情';
        if (elements.title) elements.title.textContent = detail.title || '未命名教程';
        if (elements.overview) {
            elements.overview.classList.add('hidden');
            elements.overview.textContent = '';
        }
        if (elements.readingTime) {
            elements.readingTime.innerHTML = `
                <span class="material-symbols-outlined text-sm">schedule</span>
                ${escapeHtml(formatReadingTime(detail.reading_time_minutes))}
            `;
        }
        if (elements.updatedAt) {
            elements.updatedAt.classList.remove('hidden');
            elements.updatedAt.innerHTML = `
                <span class="material-symbols-outlined text-sm">update</span>
                最后更新：${escapeHtml(formatDate(detail.updated_at || detail.created_at))}
            `;
        }

        const htmlBody = detail.html_body || '<p>暂无正文内容</p>';
        if (elements.article) {
            elements.article.innerHTML = `
                <div class="prose tutorial-prose max-w-none">
                    ${htmlBody}
                </div>
            `;
        }

        const headings = decorateArticle();
        renderToc(headings);
        bindTocTracking();
        initSmoothScroll();
        if (elements.feedback) {
            elements.feedback.classList.remove('hidden');
        }
        if (elements.secondaryTitle) {
            elements.secondaryTitle.textContent = '目录';
        }
        const articleText = normalizeText(elements.article?.textContent || '');
        setDocumentMeta(
            `${detail.title || 'GEO 教程中心'} - GEOrank`,
            articleText.slice(0, 120) || 'GEO 生成式引擎优化知识库'
        );
        updateReadingProgress();
    }

    function buildChannelStepCopy(category, items) {
        const latest = [...items].sort(
            (a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0)
        )[0];
        return {
            primary: `这个章节收录 ${items.length} 篇围绕「${category}」展开的教程文章，按照执行场景组织，适合从基础理解一路读到落地模板。`,
            secondary: latest
                ? `建议先打开《${latest.title}》，这是当前该章节最近一次更新的内容。`
                : '你可以从下方任一条目开始，逐篇展开阅读。',
        };
    }

    function buildTutorialPanelCopy(category, item) {
        return `围绕「${category}」场景，这篇文章会拆解关键步骤、判断依据与可复用方法，便于你快速进入对应主题。`;
    }

    function renderChannelHome() {
        document.body.classList.add('tutorial-channel-home');
        state.currentSlug = '';
        state.currentPathKey = '';
        state.currentDetail = null;

        const groups = getGroupedTutorials();

        renderSideNav();
        renderMobileNav();

        if (elements.breadcrumbCategory) elements.breadcrumbCategory.textContent = '教程';
        if (elements.breadcrumbTitle) elements.breadcrumbTitle.textContent = '频道首页';
        if (elements.title) elements.title.textContent = 'GEO 教程中心';
        if (elements.overview) {
            elements.overview.textContent = '这里汇总当前频道下全部已发布的 GEO 教程，覆盖认知、AI 原理、内容优化、页面技术、策略执行、评估治理与案例拆解，适合按章节连续阅读，也适合按主题跳读。';
            elements.overview.classList.remove('hidden');
        }
        if (elements.readingTime) {
            elements.readingTime.innerHTML = `
                <span class="material-symbols-outlined text-sm">library_books</span>
                已收录：${escapeHtml(String(state.tutorials.length))} 篇文章
            `;
        }
        if (elements.updatedAt) {
            elements.updatedAt.classList.add('hidden');
        }
        if (elements.feedback) {
            elements.feedback.classList.add('hidden');
        }
        if (elements.secondaryTitle) {
            elements.secondaryTitle.textContent = '栏目索引';
        }
        if (tocScrollHandler) {
            window.removeEventListener('scroll', tocScrollHandler);
            tocScrollHandler = null;
        }

        if (elements.article) {
            elements.article.innerHTML = `
                <div class="tutorial-flow">
                    ${groups.map(([category, items], index) => {
                        const copy = buildChannelStepCopy(category, items);
                        return `
                        <section id="tutorial-group-${escapeHtml(slugify(category))}" class="tutorial-flow-step">
                            <div class="tutorial-flow-step-marker">
                                <span class="tutorial-flow-step-index">${index + 1}</span>
                            </div>
                            <div class="tutorial-flow-step-body">
                                <p class="tutorial-flow-step-kicker">章节 ${String(index + 1).padStart(2, '0')}</p>
                                <h3 class="tutorial-flow-step-title">${escapeHtml(category)}</h3>
                                <p class="tutorial-flow-step-text">${escapeHtml(copy.primary)}</p>
                                <p class="tutorial-flow-step-text tutorial-flow-step-text-muted">${escapeHtml(copy.secondary)}</p>
                                <div class="tutorial-flow-accordion">
                                    ${items.map((item, itemIndex) => `
                                        <details class="tutorial-flow-item" ${itemIndex === 0 ? 'open' : ''}>
                                            <summary class="tutorial-flow-summary">
                                                <span class="tutorial-flow-summary-main">
                                                    <span class="material-symbols-outlined tutorial-flow-summary-icon">chevron_right</span>
                                                    <span class="tutorial-flow-summary-title">${escapeHtml(item.title)}</span>
                                                </span>
                                                <span class="tutorial-flow-summary-meta">${Number(item.reading_time_minutes || 0) || '--'} 分钟</span>
                                            </summary>
                                            <div class="tutorial-flow-panel">
                                                <p class="tutorial-flow-panel-text">${escapeHtml(buildTutorialPanelCopy(category, item))}</p>
                                                <div class="tutorial-flow-panel-meta">
                                                    <span>更新于 ${escapeHtml(formatDate(item.updated_at || item.created_at))}</span>
                                                    <span>${escapeHtml(String(item.view_count || 0))} 次阅读</span>
                                                </div>
                                                <a
                                                    href="${escapeHtml(buildTutorialDetailHref(getTutorialRouteKey(item)))}"
                                                    class="tutorial-flow-panel-link"
                                                    data-tutorial-key="${escapeHtml(getTutorialRouteKey(item))}"
                                                >
                                                    阅读这篇文章
                                                    <span class="material-symbols-outlined text-base">arrow_forward</span>
                                                </a>
                                            </div>
                                        </details>
                                    `).join('')}
                                </div>
                            </div>
                        </section>
                    `;
                    }).join('')}
                </div>
            `;
        }

        renderChannelToc();
        initSmoothScroll();
        setDocumentMeta('GEO 教程中心 - GEOrank', 'GEO 生成式引擎优化教程中心 — 科普教程、最佳实践与技术文档。');
        updateReadingProgress();
    }

    async function loadTutorialDetail(identifier, options = {}) {
        const { pushHistory = true, scrollTop = false } = options;
        const nextIdentifier = identifier || getTutorialRouteKey(state.tutorials[0]);
        if (!nextIdentifier) {
            renderEmptyState('当前暂无已发布教程');
            return;
        }

        state.currentPathKey = nextIdentifier;
        renderSideNav();
        renderMobileNav();
        renderLoadingArticle();

        try {
            const detail = await fetchJson(`/api/content/resolve/${encodeURIComponent(nextIdentifier)}`);
            state.currentSlug = detail.slug;
            state.currentPathKey = getTutorialRouteKey(detail);
            if (pushHistory) setRouteIdentifier(state.currentPathKey);
            renderSideNav();
            renderMobileNav();
            renderArticle(detail);

            if (scrollTop) {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        } catch (error) {
            renderEmptyState(`加载教程失败：${error.message}`);
        }
    }

    function bindTutorialNavigation() {
        const handleClick = async (event) => {
            const trigger = event.target.closest('[data-tutorial-key]');
            if (!trigger) return;
            event.preventDefault();
            const identifier = trigger.dataset.tutorialKey;
            if (!identifier || identifier === state.currentPathKey) return;
            await loadTutorialDetail(identifier, { pushHistory: true, scrollTop: true });
        };

        elements.sideNav?.addEventListener('click', handleClick);
        elements.mobileNav?.addEventListener('click', handleClick);
        elements.article?.addEventListener('click', handleClick);
        elements.toc?.addEventListener('click', handleClick);
    }

    async function loadTutorialDirectory() {
        try {
            state.tutorials = await fetchJson('/api/content/?content_type=tutorial&size=100');
            state.tutorials.sort(compareTutorials);
            if (!state.tutorials.length) {
                renderEmptyState('当前还没有已发布教程');
                return;
            }

            const preferredIdentifier = getRouteIdentifier();
            if (!preferredIdentifier) {
                renderChannelHome();
                return;
            }

            await loadTutorialDetail(preferredIdentifier, {
                pushHistory: true,
                scrollTop: false,
            });
        } catch (error) {
            renderEmptyState(`加载教程目录失败：${error.message}`);
        }
    }

    function bindPopState() {
        window.addEventListener('popstate', async () => {
            const routeIdentifier = getRouteIdentifier();
            if (!routeIdentifier) {
                if (state.currentDetail) {
                    renderChannelHome();
                }
                return;
            }
            if (routeIdentifier === state.currentPathKey || routeIdentifier === state.currentSlug) return;
            if (!findTutorialByIdentifier(routeIdentifier) && !state.tutorials.length) return;
            await loadTutorialDetail(routeIdentifier, { pushHistory: false, scrollTop: false });
        });
    }

    function init() {
        ensureProgressBar();
        bindTutorialNavigation();
        bindPopState();
        window.addEventListener('scroll', updateReadingProgress, { passive: true });
        loadTutorialDirectory();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
