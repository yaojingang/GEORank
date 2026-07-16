/**
 * Diagnostic Page - 真实 GEO 诊断交互
 */
(window.GEOrank?.PageLifecycle?.run?.bind(window.GEOrank.PageLifecycle)
    || ((callback) => callback()))(() => {
    'use strict';

    const API_BASE = ['80', '443', ''].includes(window.location.port)
        ? ''
        : `${window.location.protocol}//${window.location.hostname}:8000`;
    const Routes = window.GEOrank?.Routes;
    const initialRouteState = Routes?.readDiagnosticState
        ? Routes.readDiagnosticState()
        : (() => {
            const params = new URLSearchParams(window.location.search);
            return {
                url: params.get('url') || '',
                companyId: params.get('company_id') || '',
                reportId: params.get('report') || params.get('report_id') || '',
            };
        })();
    const initialUrl = initialRouteState.url || '';
    const initialCompanyId = initialRouteState.companyId || '';
    const initialReportId = initialRouteState.reportId || '';
    const Auth = window.GEOrank?.Auth;

    const urlInput = document.getElementById('url-input');
    const diagnoseBtn = document.getElementById('diagnose-btn');
    const reportShell = document.getElementById('diagnostic-report-shell');
    const resultsGrid = document.getElementById('results-grid');
    const statusNote = document.getElementById('diagnostic-status-note');
    const exportBtn = document.getElementById('diagnostic-export-btn');
    const toSolutionsBtn = document.getElementById('diagnostic-to-solutions-btn');
    const reportModeEyebrow = document.getElementById('diagnostic-report-mode-eyebrow');
    const reportModeTitle = document.getElementById('diagnostic-report-mode-title');
    const reportModeCopy = document.getElementById('diagnostic-report-mode-copy');
    const reportModeChip = document.getElementById('diagnostic-report-mode-chip');
    const reportModeIcon = document.getElementById('diagnostic-report-mode-icon');
    const transitionOverlay = document.getElementById('diagnostic-transition-overlay');
    const transitionCopy = document.getElementById('diagnostic-transition-copy');
    const summaryHeadline = document.getElementById('diagnostic-summary-headline');
    const summaryOverview = document.getElementById('diagnostic-summary-overview');
    const summaryPriority = document.getElementById('diagnostic-summary-priority');
    const strengthList = document.getElementById('diagnostic-strength-list');
    const gapList = document.getElementById('diagnostic-gap-list');

    let pollTimer = null;
    let activeReportId = initialReportId;
    let activeCompanyId = initialCompanyId;
    const DEMO_REPORT = {
        report_id: 'demo-report',
        url: 'https://www.brandorbit.ai',
        company_id: '',
        status: 'completed',
        overall_score: 82,
        schema_analysis: {
            score: 84,
            found_types: ['WebSite', 'Organization', 'Service', 'BreadcrumbList', 'Article'],
            missing_recommended: ['FAQPage'],
            schema_count: 5,
            coverage_ratio: 80,
            has_faq: false,
            has_org: true,
            has_article: true,
            has_breadcrumb: true,
            has_product: false,
            has_website: true,
        },
        meta_analysis: {
            score: 88,
            preview_score: 91,
            checks: {
                title: true,
                title_length: 34,
                meta_description: true,
                meta_description_length: 118,
                canonical: true,
                viewport: true,
                robots: true,
                favicon: true,
                html_lang: true,
                og_title: true,
                og_description: true,
                og_image: true,
                og_type: true,
                og_locale: false,
                twitter_card: true,
            },
            missing: ['og_locale'],
        },
        content_analysis: {
            score: 86,
            h1_count: 1,
            h2_count: 7,
            h3_count: 5,
            paragraph_count: 18,
            word_count: 890,
            character_count: 3240,
            reading_time_minutes: 7,
            has_single_h1: true,
            has_h2_structure: true,
            first_para_quality: true,
            heading_hierarchy_ok: true,
            list_count: 4,
            table_count: 2,
            image_count: 12,
            image_with_alt_count: 11,
            image_alt_ratio: 92,
            faq_like_sections: 2,
            cta_count: 4,
        },
        citation_analysis: {
            score: 79,
            external_link_count: 7,
            authority_link_count: 2,
            internal_link_count: 26,
            social_link_count: 3,
            authority_links: [
                'https://developers.google.com/search/docs/fundamentals/seo-starter-guide',
                'https://www.anthropic.com/engineering/building-effective-agents',
            ],
            social_links: [
                'https://www.linkedin.com/company/brandorbit',
                'https://github.com/brandorbit',
            ],
        },
        recommendations: {
            summary: {
                headline: '这是一份较成熟的企业官网示例报告，已经具备不错的 GEO 基础，但仍有进一步提升引用率的空间。',
                overview: '示例报告以一家 AI 搜索优化服务官网为蓝本，展示从结构化实体、摘要预览到权威背书的完整 GEO 诊断视角。真实诊断完成后，会沿用同一套富报告结构替换这份样例。',
                priority_action: '优先把 FAQPage 与服务页的答案式摘要继续做深，让高价值页面能更稳定地进入生成式答案。'
            },
            strengths: [
                '结构化实体较完整，品牌、服务与文章关系已经能被机器清晰识别。',
                '正文层级、FAQ 和案例表达成熟，适合被 AI 拆成多段引用。',
                '预览信号和外部背书基础不错，具备进一步冲高引用率的条件。',
            ],
            gaps: [
                'FAQ 结构化还不够完整，问答内容和页面可读块之间没有完全一一映射。',
                '多语言与地区语境标记还不充分，跨区域生成式检索场景下会损失可见度。',
                '高价值案例页的权威引用仍有增长空间，品牌可信度还能继续抬高。',
            ],
            urgent: [
                { item: '补齐 FAQPage 结构化问答', action: '将页面中已有 FAQ 问答和服务说明映射成完整 FAQPage，确保 question / acceptedAnswer 成对输出。' },
                { item: '强化服务页首屏摘要', action: '把核心服务页首段改成“适用对象 + 痛点 + 解决路径 + 结果”的答案式摘要，控制在 120-180 字。' },
                { item: '补上地区与语言语义', action: '补充 og:locale、地区语义词和对应服务覆盖范围，增强面向中文市场的 AI 检索命中。' },
            ],
            recommended: [
                { item: '放大案例证据密度', action: '在案例页增加具体数据结果、实施动作和客户原话，让 AI 能直接摘取证据型表达。' },
                { item: '扩充权威来源链接', action: '在关键页面补入搜索官方文档、模型厂商指南和行业研究链接，形成更稳的信任背书。' },
                { item: '统一开放图谱封面模板', action: '为核心页面生成统一风格的 OG 封面图与标题模板，提升摘要展示一致性。' },
            ],
            optional: [
                { item: '整理站内主题集群', action: '将教程、案例、服务和 FAQ 之间建立更紧密的内链集群，形成更强的主题网。' },
                { item: '补充多模态图片说明', action: '继续完善图示类图片的 alt 与 caption，让多模态 AI 更容易理解图文关系。' },
                { item: '增加可下载资产', action: '提供白皮书、清单或模板类资源页，方便在 AI 答案里形成更强的资源锚点。' },
            ],
            phase_plan: [
                { phase: 'P0', title: '问答结构化补齐', goal: '把现有 FAQ 和服务说明升级成机器可读的 FAQPage + Service 实体组合。', success_metric: 'Schema 覆盖率和答案模块得分同时提升到 85+。' },
                { phase: 'P1', title: '高价值页面重写', goal: '围绕首页、服务页和案例页重写首屏答案表达，让 AI 能直接摘取关键段落。', success_metric: '内容表达、预览和 CTA 模块达到优秀。'},
                { phase: 'P2', title: '权威背书扩容', goal: '增加外部研究、客户案例、社交与品牌背书，构建更稳的可引用信任层。', success_metric: '引用与可信维度稳定在 80 分以上。' },
            ],
        },
    };

    if (urlInput && initialUrl) {
        urlInput.value = initialUrl;
    }

    if (diagnoseBtn) {
        diagnoseBtn.addEventListener('click', () => startDiagnosis());
    }

    if (urlInput) {
        urlInput.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                startDiagnosis();
            }
        });
    }

    exportBtn?.addEventListener('click', function () {
        if (exportBtn.disabled) return;
        window.print();
    });

    function getAuthToken() {
        return Auth?.getToken?.()
            || localStorage.getItem('georank_user_token')
            || localStorage.getItem('georank_token')
            || '';
    }

    async function request(path, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...(window.GEOrank?.DeviceIdentity?.getHeaders?.() || {}),
            ...(options.headers || {}),
        };
        const token = getAuthToken();
        if (token) {
            headers.Authorization = `Bearer ${token}`;
        }

        const response = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers,
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = data.detail || `请求失败 (${response.status})`;
            throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
        }
        return data;
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function normalizeInputUrl(raw) {
        const value = String(raw || '').trim();
        if (!value) {
            throw new Error('请输入要诊断的站点地址');
        }

        let candidate = value;
        if (!/^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(candidate)) {
            candidate = `https://${candidate}`;
        }

        let parsed;
        try {
            parsed = new URL(candidate);
        } catch (_) {
            throw new Error('请输入有效的网址，例如 example.com 或 https://example.com');
        }

        if (!['http:', 'https:'].includes(parsed.protocol)) {
            throw new Error('仅支持 http 或 https 网站地址');
        }
        if (!parsed.hostname || !parsed.hostname.includes('.')) {
            throw new Error('请输入有效的网址，例如 example.com');
        }

        const normalizedPath = parsed.pathname === '/' ? '' : parsed.pathname.replace(/\/+$/, '');
        return `${parsed.protocol}//${parsed.host.toLowerCase()}${normalizedPath}`;
    }

    function setStatus(message, tone = 'info') {
        if (!statusNote) return;
        statusNote.classList.remove('hidden', 'text-slate-500', 'text-red-500', 'text-green-600');
        statusNote.classList.add(tone === 'error' ? 'text-red-500' : tone === 'success' ? 'text-green-600' : 'text-slate-500');
        statusNote.textContent = message;
    }

    function setReportMode(mode, context = {}) {
        if (reportShell) {
            reportShell.dataset.mode = mode;
        }
        if (transitionOverlay) {
            transitionOverlay.classList.toggle('hidden', mode !== 'loading');
        }
        if (transitionCopy && mode === 'loading') {
            const statusText = {
                pending: '任务已创建，正在排队准备诊断并替换当前示例报告。',
                crawling: '正在抓取目标页面 HTML、Schema 标记与内容结构，示例报告即将切换。',
                analyzing: '抓取完成，正在进行多维分析与建议生成，马上替换为真实诊断结果。',
            };
            transitionCopy.textContent = statusText[context.step] || '系统正在抓取页面代码、分析结构化标签，并生成你的专属 GEO 报告。';
        }

        const meta = {
            demo: {
                eyebrow: '示例诊断报告',
                title: '先看一份高质量 GEO 诊断样例',
                copy: '下面先展示一份企业服务官网的高质量示例报告，帮助你快速理解完整诊断结构、图表和行动路线。发起真实诊断后，这份样例会通过动画过渡替换成你自己的 GEO 诊断结果。',
                chip: '示例预览',
                icon: 'visibility',
            },
            loading: {
                eyebrow: '真实诊断生成中',
                title: '正在用真实报告替换示例',
                copy: context.url
                    ? `当前正在分析 ${context.url} 的页面结构、Schema 标签与引用信号，完成后会自动替换下方示例报告。`
                    : '系统正在分析你的页面结构、Schema 标签与引用信号，完成后会自动替换下方示例报告。',
                chip: '分析中',
                icon: 'progress_activity',
            },
            live: {
                eyebrow: '你的真实诊断报告',
                title: '已切换为最新 GEO 诊断结果',
                copy: context.url
                    ? `下面展示的是 ${context.url} 的真实诊断结果。你可以继续导出报告，或将该诊断上下文发送到方案生成器生成执行方案。`
                    : '下面展示的是刚刚生成的真实 GEO 诊断结果。你可以继续导出报告，或将该诊断上下文发送到方案生成器。',
                chip: '实时结果',
                icon: 'verified',
            },
        }[mode] || {};

        if (reportModeEyebrow && meta.eyebrow) reportModeEyebrow.textContent = meta.eyebrow;
        if (reportModeTitle && meta.title) reportModeTitle.textContent = meta.title;
        if (reportModeCopy && meta.copy) reportModeCopy.textContent = meta.copy;
        if (reportModeChip && meta.chip) reportModeChip.textContent = meta.chip;
        if (reportModeIcon && meta.icon) reportModeIcon.textContent = meta.icon;

        if (exportBtn) {
            const exportEnabled = mode === 'live';
            exportBtn.disabled = !exportEnabled;
            exportBtn.classList.toggle('opacity-50', !exportEnabled);
            exportBtn.classList.toggle('cursor-not-allowed', !exportEnabled);
        }
        if (toSolutionsBtn && mode !== 'live') {
            toSolutionsBtn.href = '/plans';
        }
    }

    function animateLiveSwap() {
        if (!resultsGrid) return;
        resultsGrid.classList.remove('diagnostic-report-swap-in');
        void resultsGrid.offsetWidth;
        resultsGrid.classList.add('diagnostic-report-swap-in');
    }

    function clearPolling() {
        if (pollTimer) {
            clearTimeout(pollTimer);
            pollTimer = null;
        }
    }

    function setLoading(loading) {
        if (!diagnoseBtn) return;
        diagnoseBtn.disabled = loading;
        diagnoseBtn.innerHTML = loading
            ? '<span class="animate-spin material-symbols-outlined text-lg">progress_activity</span><span class="font-bold text-sm">分析中...</span>'
            : '开始诊断';
    }

    function updateLocation(reportId, url) {
        if (Routes?.buildDiagnosticPath) {
            window.history.replaceState(
                { reportId },
                '',
                Routes.buildDiagnosticPath({
                    reportId,
                    url,
                    companyId: activeCompanyId,
                })
            );
            return;
        }
        const next = new URL(window.location.href);
        if (reportId) next.searchParams.set('report', reportId);
        if (url) next.searchParams.set('url', url);
        if (activeCompanyId) next.searchParams.set('company_id', activeCompanyId);
        window.history.replaceState({ reportId }, '', next.toString());
    }

    function showResults() {
        resultsGrid?.classList.remove('hidden');
    }

    function hideResults() {
        resultsGrid?.classList.add('hidden');
    }

    function scoreTone(score) {
        if (score >= 80) return { label: '优秀', bar: 'bg-green-500' };
        if (score >= 60) return { label: '良好', bar: 'bg-primary' };
        if (score >= 40) return { label: '待优化', bar: 'bg-orange-400' };
        return { label: '偏弱', bar: 'bg-red-400' };
    }

    function average(values) {
        const safeValues = (Array.isArray(values) ? values : [])
            .map((value) => Number(value))
            .filter((value) => Number.isFinite(value));
        if (!safeValues.length) return 0;
        return Math.round(safeValues.reduce((sum, value) => sum + value, 0) / safeValues.length);
    }

    function metricScore(value, thresholds) {
        for (const threshold of thresholds) {
            if (value >= threshold.min) {
                return threshold.score;
            }
        }
        return thresholds[thresholds.length - 1]?.score || 0;
    }

    function boolMetric(title, passed, positiveNote, negativeNote, metricLabel) {
        return {
            title,
            score: passed ? 100 : 35,
            metric: metricLabel || (passed ? '已具备' : '待补齐'),
            note: passed ? positiveNote : negativeNote,
        };
    }

    function buildDiagnosticSections(report) {
        const schema = report.schema_analysis || {};
        const meta = report.meta_analysis || {};
        const metaChecks = meta.checks || {};
        const content = report.content_analysis || {};
        const citation = report.citation_analysis || {};
        const characterCount = Number(content.character_count || 0);

        const sections = [
            {
                key: 'access',
                title: '抓取入口',
                icon: 'travel_explore',
                summary: '确认页面是否具备被搜索引擎与 AI 抓取的基础入口信号。',
                items: [
                    boolMetric('HTTPS 协议', String(report.url || '').startsWith('https://'), '页面入口已使用 HTTPS。', '建议统一使用 HTTPS 规范入口。', String(report.url || '').startsWith('https://') ? 'HTTPS' : 'HTTP'),
                    boolMetric('Canonical 规范', !!metaChecks.canonical, '已声明 canonical，利于统一权重。', '缺少 canonical，可能造成页面权重分散。'),
                    boolMetric('Viewport 适配', !!metaChecks.viewport, '已声明 viewport，移动端抓取语义更稳定。', '缺少 viewport，移动端体验与抓取语义存在风险。'),
                    boolMetric('Lang 声明', !!metaChecks.html_lang, '已声明 HTML lang 语言。', '建议在 html 标签上声明 lang。'),
                ],
            },
            {
                key: 'preview',
                title: '预览元信息',
                icon: 'html',
                summary: '诊断标题、摘要和社交预览是否能支撑生成式摘要展示。',
                items: [
                    {
                        title: 'Title 完整度',
                        score: metaChecks.title ? metricScore(Number(metaChecks.title_length || 0), [{ min: 35, score: 96 }, { min: 20, score: 70 }, { min: 1, score: 45 }, { min: 0, score: 20 }]) : 20,
                        metric: `${metaChecks.title_length || 0} 字符`,
                        note: metaChecks.title ? '标题已存在，可继续压缩到更聚焦的实体表达。' : '缺少页面标题。',
                    },
                    {
                        title: 'Meta Description',
                        score: metaChecks.meta_description ? metricScore(Number(metaChecks.meta_description_length || 0), [{ min: 90, score: 92 }, { min: 50, score: 75 }, { min: 1, score: 45 }, { min: 0, score: 20 }]) : 20,
                        metric: `${metaChecks.meta_description_length || 0} 字符`,
                        note: metaChecks.meta_description ? '描述已存在，可继续强化可摘录摘要。' : '缺少 meta description。',
                    },
                    boolMetric('开放图谱', !!metaChecks.og_title && !!metaChecks.og_description && !!metaChecks.og_type, 'OG 标题、描述与类型基本完整。', 'OG 标题/描述/类型仍不完整。'),
                    boolMetric('社媒卡片', !!metaChecks.twitter_card && !!metaChecks.og_image, '社交预览卡片完整，可支撑摘要传播。', '缺少 twitter:card 或 og:image。'),
                ],
            },
            {
                key: 'schema',
                title: '结构化语义',
                icon: 'code_blocks',
                summary: '判断页面是否把品牌、文章和问答结构显式暴露给机器理解。',
                items: [
                    {
                        title: 'Schema 覆盖率',
                        score: Number(schema.coverage_ratio || schema.score || 0),
                        metric: `${schema.coverage_ratio || schema.score || 0}%`,
                        note: '核心推荐 Schema 类型覆盖情况。',
                    },
                    boolMetric('Organization 实体', !!schema.has_org, '组织实体已具备。', '缺少 Organization / WebSite 实体。'),
                    boolMetric('FAQ 问答', !!schema.has_faq, 'FAQPage 已具备，可提升可引用问答。', '建议加入 FAQPage 结构化问答。'),
                    boolMetric('面包屑导航', !!schema.has_breadcrumb, 'BreadcrumbList 已声明。', '建议补充 BreadcrumbList，增强主题链路。'),
                ],
            },
            {
                key: 'content',
                title: '内容组织',
                icon: 'article',
                summary: '从正文体量、标题层级和内容组件判断页面是否具备可引用结构。',
                items: [
                    boolMetric('H1 唯一性', !!content.has_single_h1, '页面 H1 数量合理。', `当前检测到 ${content.h1_count || 0} 个 H1，建议只保留一个。`, `${content.h1_count || 0} 个 H1`),
                    boolMetric('标题层级', !!content.heading_hierarchy_ok, 'H1/H2 结构已形成清晰层级。', 'H1/H2 层级仍需梳理。'),
                    {
                        title: '正文深度',
                        score: metricScore(characterCount, [{ min: 1800, score: 96 }, { min: 1200, score: 82 }, { min: 700, score: 64 }, { min: 300, score: 42 }, { min: 0, score: 20 }]),
                        metric: `${characterCount} 字`,
                        note: '正文体量越完整，越容易形成可摘录段落。',
                    },
                    {
                        title: '阅读时长',
                        score: metricScore(Number(content.reading_time_minutes || 0), [{ min: 4, score: 88 }, { min: 2, score: 68 }, { min: 1, score: 48 }, { min: 0, score: 24 }]),
                        metric: `${content.reading_time_minutes || 0} 分钟`,
                        note: '中等深度内容更适合生成式搜索引用。',
                    },
                ],
            },
            {
                key: 'answer',
                title: '答案表达',
                icon: 'edit_note',
                summary: '评估页面是否采用问题-回答、列表和组件化表达，便于 AI 摘录。',
                items: [
                    boolMetric('首段直答', !!content.first_para_quality, '首段已经具备较强的信息密度。', '首段仍偏口号式，缺少可直接摘录的答案。'),
                    {
                        title: '列表表达',
                        score: metricScore(Number(content.list_count || 0), [{ min: 3, score: 95 }, { min: 2, score: 82 }, { min: 1, score: 62 }, { min: 0, score: 30 }]),
                        metric: `${content.list_count || 0} 个列表`,
                        note: '列表结构越充分，越容易让 AI 拆分要点。',
                    },
                    {
                        title: 'FAQ 语气',
                        score: metricScore(Number(content.faq_like_sections || 0), [{ min: 2, score: 95 }, { min: 1, score: 78 }, { min: 0, score: 32 }]),
                        metric: `${content.faq_like_sections || 0} 个问答段`,
                        note: 'FAQ / 常见问题板块有助于被问答式结果直接调用。',
                    },
                    {
                        title: 'CTA 清晰度',
                        score: metricScore(Number(content.cta_count || 0), [{ min: 3, score: 90 }, { min: 2, score: 72 }, { min: 1, score: 52 }, { min: 0, score: 24 }]),
                        metric: `${content.cta_count || 0} 个动作点`,
                        note: '明确的行动入口更利于把内容转成下一步方案。',
                    },
                ],
            },
            {
                key: 'trust',
                title: '引用可信',
                icon: 'query_stats',
                summary: '衡量页面通过外链、权威来源与站内支撑建立可信度的能力。',
                items: [
                    {
                        title: '外部链接广度',
                        score: metricScore(Number(citation.external_link_count || 0), [{ min: 8, score: 96 }, { min: 4, score: 78 }, { min: 1, score: 52 }, { min: 0, score: 24 }]),
                        metric: `${citation.external_link_count || 0} 个外链`,
                        note: '外部信号越丰富，AI 越容易建立引用网络。',
                    },
                    {
                        title: '权威引用',
                        score: metricScore(Number(citation.authority_link_count || 0), [{ min: 3, score: 100 }, { min: 2, score: 86 }, { min: 1, score: 66 }, { min: 0, score: 26 }]),
                        metric: `${citation.authority_link_count || 0} 个权威源`,
                        note: '学术、官方或行业权威来源是生成式引擎偏好的信号。',
                    },
                    {
                        title: '站内支撑链接',
                        score: metricScore(Number(citation.internal_link_count || 0), [{ min: 16, score: 92 }, { min: 10, score: 76 }, { min: 5, score: 58 }, { min: 0, score: 28 }]),
                        metric: `${citation.internal_link_count || 0} 个内链`,
                        note: '站内主题链路越完整，越利于 AI 形成上下文理解。',
                    },
                    {
                        title: '社交背书',
                        score: metricScore(Number(citation.social_link_count || 0), [{ min: 3, score: 90 }, { min: 2, score: 74 }, { min: 1, score: 54 }, { min: 0, score: 26 }]),
                        metric: `${citation.social_link_count || 0} 个社交源`,
                        note: '品牌在外部平台的公开存在，有助于提升可信信号。',
                    },
                ],
            },
        ];

        return sections.map((section) => ({
            ...section,
            score: average(section.items.map((item) => item.score)),
        }));
    }

    function buildReadinessStages(sections, overallScore) {
        const sectionMap = Object.fromEntries(sections.map((section) => [section.key, section]));
        return [
            { label: '抓取可达', score: average([sectionMap.access?.score, sectionMap.preview?.score]) },
            { label: '实体理解', score: sectionMap.schema?.score || 0 },
            { label: '答案表达', score: average([sectionMap.content?.score, sectionMap.answer?.score]) },
            { label: '信任构建', score: sectionMap.trust?.score || 0 },
            { label: 'AI 引用准备', score: average([overallScore, sectionMap.schema?.score, sectionMap.answer?.score, sectionMap.trust?.score]) },
        ];
    }

    function buildSignalMix(report) {
        return [
            { label: 'Schema', value: Number(report.schema_analysis?.score || 0), color: '#2563eb' },
            { label: '内容', value: Number(report.content_analysis?.score || 0), color: '#0f766e' },
            { label: 'Meta', value: Number(report.meta_analysis?.score || 0), color: '#7c3aed' },
            { label: '引用', value: Number(report.citation_analysis?.score || 0), color: '#ea580c' },
        ];
    }

    function buildRoadmap(report) {
        const plans = Array.isArray(report?.recommendations?.phase_plan)
            ? report.recommendations.phase_plan.filter(Boolean)
            : [];
        if (plans.length) {
            return plans.slice(0, 3);
        }

        const urgent = Array.isArray(report?.recommendations?.urgent) ? report.recommendations.urgent : [];
        const recommended = Array.isArray(report?.recommendations?.recommended) ? report.recommendations.recommended : [];
        return [
            {
                phase: 'P0',
                title: urgent[0]?.item || '先补结构化信号',
                goal: urgent[0]?.action || '优先修复 Organization、FAQPage 和 canonical 等基础信号。',
                success_metric: '核心机器可读信号完整。',
            },
            {
                phase: 'P1',
                title: recommended[0]?.item || '优化答案表达',
                goal: recommended[0]?.action || '将首屏摘要和问答段落改写成更适合 AI 摘录的内容。',
                success_metric: '答案表达得分提升。',
            },
            {
                phase: 'P2',
                title: '补充证据与案例',
                goal: '扩充外部权威来源、客户案例和站内内容支撑链路。',
                success_metric: '引用与可信维度进入良好以上。',
            },
        ];
    }

    function buildEvidenceCards(report) {
        const schema = report.schema_analysis || {};
        const meta = report.meta_analysis || {};
        const content = report.content_analysis || {};
        const citation = report.citation_analysis || {};

        return [
            {
                title: '已识别 Schema',
                value: `${(schema.found_types || []).length} 项`,
                note: (schema.found_types || []).join('、') || '暂无',
            },
            {
                title: '待补结构化',
                value: `${(schema.missing_recommended || []).length} 项`,
                note: (schema.missing_recommended || []).join('、') || '已覆盖核心推荐类型',
            },
            {
                title: 'Meta 缺口',
                value: `${(meta.missing || []).length} 项`,
                note: (meta.missing || []).join('、') || 'Meta / OG 基本完整',
            },
            {
                title: '内容快照',
                value: `${content.character_count || 0} 字`,
                note: `${content.paragraph_count || 0} 段 · ${content.list_count || 0} 列表 · ${content.image_count || 0} 图片`,
            },
            {
                title: '引用信号',
                value: `${citation.authority_link_count || 0} 权威源`,
                note: `${citation.external_link_count || 0} 外链 · ${citation.internal_link_count || 0} 内链 · ${citation.social_link_count || 0} 社交链接`,
            },
        ];
    }

    function renderScore(score) {
        const scoreValue = document.getElementById('geo-score-value');
        const scoreLabel = document.getElementById('geo-score-label');
        const scoreSummary = document.getElementById('geo-score-summary');
        const scoreRing = document.getElementById('geo-score-ring');
        const safeScore = Math.max(0, Math.min(100, Number(score || 0)));
        const tone = scoreTone(safeScore);
        const circumference = 2 * Math.PI * 80;
        const offset = circumference * (1 - safeScore / 100);

        if (scoreValue) scoreValue.textContent = String(Math.round(safeScore));
        if (scoreLabel) scoreLabel.textContent = `GEO 评分：${tone.label}`;
        if (scoreSummary) {
            scoreSummary.textContent = safeScore >= 80
                ? '页面已经具备较强的 GEO 基础，可继续针对高价值结构化数据和引用策略做增强。'
                : safeScore >= 60
                    ? '页面已有一定 GEO 可见性，但仍有明显结构化和引用优化空间。'
                    : '页面在结构化标签、内容组织或权威引用方面仍较薄弱，建议尽快按报告清单补齐。';
        }
        if (scoreRing) {
            scoreRing.style.strokeDasharray = `${circumference}`;
            scoreRing.style.strokeDashoffset = `${offset}`;
        }
    }

    function renderMetric(name, score, note) {
        const root = document.querySelector(`[data-diagnostic-metric="${name}"]`);
        if (!root) return;
        const scoreEl = root.querySelector('[data-role="score"]');
        const barEl = root.querySelector('[data-role="bar"]');
        const noteEl = root.querySelector('[data-role="note"]');
        const safeScore = Math.max(0, Math.min(100, Number(score || 0)));
        const tone = scoreTone(safeScore);

        if (scoreEl) scoreEl.textContent = `${Math.round(safeScore)}%`;
        if (barEl) {
            barEl.style.width = `${safeScore}%`;
            barEl.className = `${tone.bar} h-full rounded-full`;
        }
        if (noteEl) {
            noteEl.textContent = note;
        }
    }

    function renderSchemaCard(title, body, tone) {
        const colorClass = tone === 'missing' ? 'bg-red-50/50' : 'bg-slate-50';
        const titleClass = tone === 'missing' ? 'text-red-600' : 'text-green-700';
        return `
            <div class="p-3 ${colorClass} rounded-lg">
                <p class="text-xs font-bold font-mono ${titleClass}">${escapeHtml(title)}</p>
                <p class="text-[10px] text-on-surface-variant mt-1">${escapeHtml(body)}</p>
            </div>
        `;
    }

    function renderSchema(schema = {}) {
        const detectedCount = document.getElementById('schema-detected-count');
        const missingCount = document.getElementById('schema-missing-count');
        const detectedList = document.getElementById('schema-detected-list');
        const missingList = document.getElementById('schema-missing-list');
        const foundTypes = Array.isArray(schema.found_types) ? schema.found_types : [];
        const missingTypes = Array.isArray(schema.missing_recommended) ? schema.missing_recommended : [];

        if (detectedCount) detectedCount.innerHTML = '<span class="material-symbols-outlined text-sm filled">check_circle</span>已检测到 (' + foundTypes.length + '项)';
        if (missingCount) missingCount.innerHTML = '<span class="material-symbols-outlined text-sm filled">error</span>建议补充 (' + missingTypes.length + '项)';

        if (detectedList) {
            detectedList.innerHTML = foundTypes.length
                ? foundTypes.map((type) => renderSchemaCard(`@type: "${type}"`, '页面中已存在此结构化类型，可继续补充完整字段。', 'found')).join('')
                : renderSchemaCard('暂无已识别 Schema', '当前页面没有发现可用的 JSON-LD Schema 结构。', 'found');
        }
        if (missingList) {
            missingList.innerHTML = missingTypes.length
                ? missingTypes.map((type) => renderSchemaCard(`@type: "${type}"`, '建议尽快补齐该类型，提升 AI 对页面实体与结构的理解。', 'missing')).join('')
                : renderSchemaCard('结构化类型完整', '当前推荐的核心 Schema 类型已经覆盖。', 'found');
        }
    }

    function recommendationTone(kind) {
        if (kind === 'urgent') {
            return {
                badge: 'text-red-500',
                iconWrap: 'bg-red-50',
                icon: 'text-red-500',
                iconName: 'error',
                label: '紧急',
            };
        }
        if (kind === 'recommended') {
            return {
                badge: 'text-primary',
                iconWrap: 'bg-blue-50',
                icon: 'text-primary',
                iconName: 'bolt',
                label: '建议',
            };
        }
        return {
            badge: 'text-slate-400',
            iconWrap: 'bg-slate-100',
            icon: 'text-slate-400',
            iconName: 'info',
            label: '优化',
        };
    }

    function renderRecommendations(recommendations = {}) {
        const list = document.getElementById('recommendations-list');
        if (!list) return;

        const entries = ['urgent', 'recommended', 'optional']
            .flatMap((kind) => (Array.isArray(recommendations[kind]) ? recommendations[kind].map((item) => ({ kind, item })) : []));

        if (!entries.length) {
            list.innerHTML = `
                <div class="col-span-1 md:col-span-3 p-6 rounded-xl bg-white border border-slate-100 text-sm text-slate-400">
                    当前没有额外优化建议，建议继续补充 FAQ、案例和权威引用以稳步提升 GEO 表现。
                </div>
            `;
            return;
        }

        list.innerHTML = entries.slice(0, 6).map(({ kind, item }) => {
            const tone = recommendationTone(kind);
            return `
                <div class="p-6 rounded-xl bg-white border border-slate-100">
                    <div class="flex items-center gap-2 mb-4">
                        <span class="w-5 h-5 rounded ${tone.iconWrap} flex items-center justify-center"><span class="material-symbols-outlined ${tone.icon} text-xs filled">${tone.iconName}</span></span>
                        <span class="text-xs font-bold ${tone.badge}">${tone.label}</span>
                    </div>
                    <h4 class="text-sm font-bold mb-2">${escapeHtml(item.item || '优化项')}</h4>
                    <p class="text-xs text-on-surface-variant leading-relaxed">${escapeHtml(item.action || '建议按诊断结果补齐相关内容与结构化标记。')}</p>
                </div>
            `;
        }).join('');
    }

    function renderCategoryBars(sections) {
        const root = document.getElementById('diagnostic-category-bars');
        if (!root) return;
        root.innerHTML = sections.map((section) => `
            <div>
                <div class="flex items-center justify-between text-sm mb-2">
                    <span class="font-medium text-slate-700 flex items-center gap-2">
                        <span class="material-symbols-outlined text-base text-primary">${escapeHtml(section.icon)}</span>
                        ${escapeHtml(section.title)}
                    </span>
                    <span class="font-bold text-primary">${Math.round(section.score)}%</span>
                </div>
                <div class="h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div class="${scoreTone(section.score).bar} h-full rounded-full" style="width:${Math.round(section.score)}%"></div>
                </div>
                <p class="mt-2 text-xs leading-6 text-slate-500">${escapeHtml(section.summary)}</p>
            </div>
        `).join('');
    }

    function renderReadinessFunnel(stages) {
        const root = document.getElementById('diagnostic-readiness-funnel');
        if (!root) return;
        root.innerHTML = stages.map((stage, index) => {
            const width = Math.max(24, Math.round(stage.score));
            return `
                <div class="diagnostic-funnel-stage">
                    <div class="flex items-center justify-between text-xs font-bold uppercase tracking-[0.14em] text-slate-400">
                        <span>${escapeHtml(stage.label)}</span>
                        <span>${Math.round(stage.score)}%</span>
                    </div>
                    <div class="mt-2 h-11 rounded-2xl bg-slate-50 overflow-hidden relative">
                        <div class="absolute inset-y-0 left-0 rounded-2xl bg-gradient-to-r from-primary to-blue-400" style="width:${width}%"></div>
                        <div class="relative h-full flex items-center px-4 text-sm font-semibold text-slate-700">
                            <span class="w-6 h-6 mr-3 rounded-full bg-white/80 text-primary flex items-center justify-center text-xs font-black">${index + 1}</span>
                            ${escapeHtml(stage.label)}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    function renderSignalMix(mix, overallScore) {
        const donut = document.getElementById('diagnostic-signal-donut');
        const donutScore = document.getElementById('diagnostic-signal-donut-score');
        const legend = document.getElementById('diagnostic-signal-legend');
        if (!donut || !legend) return;
        const total = mix.reduce((sum, item) => sum + Math.max(0, item.value), 0) || 1;
        let start = 0;
        const segments = mix.map((item) => {
            const share = (Math.max(0, item.value) / total) * 100;
            const segment = `${item.color} ${start}% ${start + share}%`;
            start += share;
            return segment;
        });
        donut.style.background = `conic-gradient(${segments.join(', ')})`;
        if (donutScore) donutScore.textContent = String(Math.round(overallScore || 0));
        legend.innerHTML = mix.map((item) => `
            <div class="flex items-center justify-between rounded-2xl border border-slate-100 px-4 py-3">
                <div class="flex items-center gap-3">
                    <span class="w-3 h-3 rounded-full" style="background:${item.color}"></span>
                    <span class="text-sm font-medium text-slate-700">${escapeHtml(item.label)}</span>
                </div>
                <span class="text-sm font-bold text-slate-900">${Math.round(item.value)}%</span>
            </div>
        `).join('');
    }

    function renderRiskGrid(sections) {
        const root = document.getElementById('diagnostic-risk-grid');
        if (!root) return;
        const risks = sections
            .flatMap((section) => section.items.map((item) => ({ ...item, sectionTitle: section.title })))
            .sort((a, b) => a.score - b.score)
            .slice(0, 6);
        root.innerHTML = risks.map((item) => `
            <div class="rounded-2xl border border-slate-100 bg-slate-50/80 px-4 py-4">
                <div class="flex items-start justify-between gap-3">
                    <div>
                        <p class="text-[11px] font-extrabold uppercase tracking-[0.14em] text-slate-400">${escapeHtml(item.sectionTitle)}</p>
                        <h4 class="mt-2 text-sm font-bold text-slate-900">${escapeHtml(item.title)}</h4>
                    </div>
                    <span class="rounded-full bg-red-50 px-2.5 py-1 text-xs font-bold text-red-500">${Math.round(item.score)}%</span>
                </div>
                <p class="mt-3 text-xs leading-6 text-slate-500">${escapeHtml(item.note)}</p>
            </div>
        `).join('');
    }

    function renderModuleSections(sections) {
        const root = document.getElementById('diagnostic-module-sections');
        const summary = document.getElementById('diagnostic-module-summary');
        if (!root) return;
        const moduleCount = sections.reduce((count, section) => count + section.items.length, 0);
        if (summary) {
            summary.textContent = `覆盖 ${sections.length} 个章节 · ${moduleCount} 个模块`;
        }
        root.innerHTML = sections.map((section) => `
            <section class="rounded-2xl border border-slate-100 bg-white p-5 md:p-6">
                <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div class="max-w-2xl">
                        <div class="flex items-center gap-3">
                            <span class="w-11 h-11 rounded-2xl bg-primary/[0.08] text-primary flex items-center justify-center">
                                <span class="material-symbols-outlined">${escapeHtml(section.icon)}</span>
                            </span>
                            <div>
                                <p class="text-[11px] font-extrabold uppercase tracking-[0.14em] text-slate-400">诊断章节</p>
                                <h4 class="mt-1 text-lg font-bold text-slate-900">${escapeHtml(section.title)}</h4>
                            </div>
                        </div>
                        <p class="mt-4 text-sm leading-7 text-slate-500">${escapeHtml(section.summary)}</p>
                    </div>
                    <div class="self-start rounded-full border border-primary/10 bg-primary/[0.05] px-4 py-2 text-sm font-bold text-primary">${Math.round(section.score)}%</div>
                </div>
                <div class="mt-5 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                    ${section.items.map((item) => `
                        <article class="rounded-2xl border border-slate-100 bg-slate-50/70 px-4 py-4">
                            <div class="flex items-center justify-between gap-3">
                                <h5 class="text-sm font-bold text-slate-900">${escapeHtml(item.title)}</h5>
                                <span class="rounded-full bg-white px-2.5 py-1 text-xs font-bold ${item.score >= 80 ? 'text-green-600' : item.score >= 60 ? 'text-primary' : item.score >= 40 ? 'text-orange-500' : 'text-red-500'}">${Math.round(item.score)}%</span>
                            </div>
                            <p class="mt-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">${escapeHtml(item.metric || '')}</p>
                            <div class="mt-3 h-1.5 rounded-full bg-white overflow-hidden">
                                <div class="${scoreTone(item.score).bar} h-full rounded-full" style="width:${Math.round(item.score)}%"></div>
                            </div>
                            <p class="mt-3 text-xs leading-6 text-slate-500">${escapeHtml(item.note)}</p>
                        </article>
                    `).join('')}
                </div>
            </section>
        `).join('');
    }

    function renderRoadmap(report) {
        const root = document.getElementById('diagnostic-roadmap');
        if (!root) return;
        const plans = buildRoadmap(report);
        root.innerHTML = plans.map((plan, index) => `
            <div class="relative rounded-2xl border border-slate-100 bg-slate-50/80 px-5 py-5">
                <div class="absolute left-5 top-5 bottom-5 ${index === plans.length - 1 ? 'hidden' : 'block'} w-px bg-slate-200"></div>
                <div class="relative pl-12">
                    <span class="absolute left-0 top-0 flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-black text-white">${escapeHtml(plan.phase)}</span>
                    <h4 class="text-sm font-bold text-slate-900">${escapeHtml(plan.title)}</h4>
                    <p class="mt-2 text-sm leading-7 text-slate-600">${escapeHtml(plan.goal)}</p>
                    <div class="mt-3 inline-flex rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-500">
                        成功标记：${escapeHtml(plan.success_metric || '形成可执行的修复闭环')}
                    </div>
                </div>
            </div>
        `).join('');
    }

    function renderEvidence(report) {
        const root = document.getElementById('diagnostic-evidence-grid');
        if (!root) return;
        root.innerHTML = buildEvidenceCards(report).map((card) => `
            <div class="rounded-2xl border border-slate-100 bg-slate-50/70 px-4 py-4">
                <div class="flex items-center justify-between gap-3">
                    <h4 class="text-sm font-bold text-slate-900">${escapeHtml(card.title)}</h4>
                    <span class="text-xs font-bold text-primary">${escapeHtml(card.value)}</span>
                </div>
                <p class="mt-3 text-xs leading-6 text-slate-500">${escapeHtml(card.note)}</p>
            </div>
        `).join('');
    }

    function renderBulletList(root, items, emptyText, iconName, iconClass) {
        if (!root) return;
        const values = Array.isArray(items) ? items.filter(Boolean).slice(0, 3) : [];
        root.innerHTML = values.length
            ? values.map((item) => `
                <li class="flex items-start gap-3 text-sm text-slate-600">
                    <span class="material-symbols-outlined text-base ${iconClass} mt-0.5">${iconName}</span>
                    <span>${escapeHtml(item)}</span>
                </li>
            `).join('')
            : `
                <li class="flex items-start gap-3 text-sm text-slate-500">
                    <span class="material-symbols-outlined text-base ${iconClass} mt-0.5">${iconName}</span>
                    <span>${escapeHtml(emptyText)}</span>
                </li>
            `;
    }

    function fallbackNarrative(report) {
        const schema = report.schema_analysis || {};
        const meta = report.meta_analysis || {};
        const content = report.content_analysis || {};
        const citation = report.citation_analysis || {};
        const overall = Math.round(Number(report.overall_score || 0));

        const strengths = [];
        if ((schema.score || 0) >= 80) strengths.push('结构化标签基础较完整，页面实体和内容关系已经具备较好的 AI 可识别性。');
        if ((meta.score || 0) >= 80) strengths.push('Meta 与 Open Graph 信号较完整，有助于抓取摘要和页面定位。');
        if ((content.score || 0) >= 70) strengths.push('正文结构和标题层级基本成型，适合继续向答案优先写法优化。');

        const gaps = [];
        if (Array.isArray(schema.missing_recommended) && schema.missing_recommended.length) {
            gaps.push(`缺少 ${schema.missing_recommended.slice(0, 3).join('、')} 等关键 Schema 类型。`);
        }
        if ((citation.authority_link_count || 0) < 1) {
            gaps.push('页面缺少权威引用来源，难以提升生成式引擎在回答中调用你的内容。');
        }
        if (!content.first_para_quality) {
            gaps.push('首段缺少直达答案式表达，AI 不容易快速截取可引用摘要。');
        }

        const headline = overall >= 80
            ? '当前页面 GEO 基础较强，适合继续强化高价值引用与结构化细节。'
            : overall >= 60
                ? '当前页面已有一定 GEO 基础，但结构化与引用信号仍有明显优化空间。'
                : '当前页面 GEO 基础偏弱，建议优先补齐结构化和答案型内容。';
        const overview = `综合 GEO 评分为 ${overall} 分。建议优先把结构化标记、首段摘要表达和权威引用补齐，再继续优化开放图谱和内容层级。`;
        const priority = gaps[0] || '继续补充 FAQ、案例与结构化标签，让页面更适合被 AI 检索与引用。';

        return { headline, overview, priority, strengths, gaps };
    }

    function renderNarrative(report) {
        const summary = report?.recommendations?.summary || {};
        const fallback = fallbackNarrative(report || {});
        if (summaryHeadline) summaryHeadline.textContent = summary.headline || fallback.headline;
        if (summaryOverview) summaryOverview.textContent = summary.overview || fallback.overview;
        if (summaryPriority) summaryPriority.textContent = summary.priority_action || fallback.priority;
        renderBulletList(
            strengthList,
            report?.recommendations?.strengths || fallback.strengths,
            '当前页面还缺少明显优势信号，建议优先补齐标题、描述与基础结构化标签。',
            'check_circle',
            'text-green-500'
        );
        renderBulletList(
            gapList,
            report?.recommendations?.gaps || fallback.gaps,
            '当前未检测到额外明显缺口，可继续通过案例、FAQ 与权威引用做增强。',
            'warning',
            'text-orange-400'
        );
    }

    function renderReport(report) {
        const schema = report.schema_analysis || {};
        const content = report.content_analysis || {};
        const meta = report.meta_analysis || {};
        const citation = report.citation_analysis || {};
        const sections = buildDiagnosticSections(report);
        const readinessStages = buildReadinessStages(sections, Number(report.overall_score || 0));
        const signalMix = buildSignalMix(report);

        renderNarrative(report);
        renderScore(report.overall_score || 0);
        renderCategoryBars(sections);
        renderReadinessFunnel(readinessStages);
        renderSignalMix(signalMix, report.overall_score || 0);
        renderRiskGrid(sections);
        renderModuleSections(sections);
        renderRoadmap(report);
        renderEvidence(report);
        renderMetric(
            'schema',
            schema.score,
            Array.isArray(schema.missing_recommended) && schema.missing_recommended.length
                ? `缺少 ${schema.missing_recommended.slice(0, 3).join('、')} 等关键 Schema 类型`
                : '核心 Schema 类型覆盖较完整，可继续补充实体字段细节。'
        );
        renderMetric(
            'content',
            content.score,
            `检测到 ${content.h1_count ?? 0} 个 H1、${content.h2_count ?? 0} 个 H2，正文约 ${content.character_count ?? content.word_count ?? 0} 字。`
        );
        renderMetric(
            'meta',
            meta.score,
            Array.isArray(meta.missing) && meta.missing.length
                ? `待补充 ${meta.missing.slice(0, 3).join('、')} 等 Meta / OG 字段。`
                : 'Meta、Open Graph 与 Twitter Card 信息较完整。'
        );
        renderMetric(
            'citation',
            citation.score,
            `外部链接 ${citation.external_link_count ?? 0} 个，权威引用 ${citation.authority_link_count ?? 0} 个。`
        );
        renderSchema(schema);
        renderRecommendations(report.recommendations || {});

        if (toSolutionsBtn) {
            if (Routes?.buildPlanPath) {
                toSolutionsBtn.href = Routes.buildPlanPath({
                    diagnosticReportId: report.report_id,
                    companyId: report.company_id || '',
                    url: report.url || '',
                });
            } else {
                const next = new URL('/plans', window.location.origin);
                next.searchParams.set('diagnostic_report_id', report.report_id);
                next.searchParams.set('url', report.url);
                if (report.company_id) next.searchParams.set('company_id', report.company_id);
                toSolutionsBtn.href = next.toString();
            }
        }
        showResults();
        setReportMode('live', { url: report.url || '' });
        animateLiveSwap();
    }

    async function pollReport(reportId, attempt = 0) {
        try {
            const report = await request(`/api/diagnostics/${reportId}`);
            activeReportId = report.report_id;
            updateLocation(report.report_id, report.url);

            if (report.status === 'completed') {
                clearPolling();
                setLoading(false);
                setStatus('诊断完成，以下为最新 GEO 报告。', 'success');
                renderReport(report);
                resultsGrid?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                return;
            }

            if (report.status === 'failed') {
                clearPolling();
                setLoading(false);
                showResults();
                setReportMode('demo');
                renderReport(DEMO_REPORT);
                setStatus(report.error_message || '诊断失败，请稍后重试。', 'error');
                return;
            }

            const statusMessages = {
                pending: '任务已创建，正在排队准备诊断。',
                crawling: '正在抓取目标页面的 HTML 内容与结构化数据。',
                analyzing: '已完成抓取，正在进行 GEO 多维分析与建议生成。',
            };
            setStatus(statusMessages[report.status] || '正在同步诊断状态...');
            setReportMode('loading', { url: report.url || '', step: report.status });
        } catch (error) {
            if (attempt >= 10) {
                clearPolling();
                setLoading(false);
                setReportMode('demo');
                setStatus(error.message, 'error');
                return;
            }
            setStatus('状态同步稍有延迟，正在重试获取最新诊断结果...');
        }

        pollTimer = window.setTimeout(() => {
            pollReport(reportId, attempt + 1);
        }, 2000);
    }

    async function startDiagnosis() {
        if (Auth && !Auth.requireAuth({ reasonKey: 'auth.reasonDiagnostic' })) {
            return;
        }

        const rawUrl = urlInput?.value?.trim();
        if (!rawUrl) {
            urlInput?.focus();
            urlInput?.classList.add('ring-2', 'ring-red-300');
            window.setTimeout(() => urlInput?.classList.remove('ring-2', 'ring-red-300'), 2000);
            return;
        }

        let url;
        try {
            url = normalizeInputUrl(rawUrl);
            if (urlInput) {
                urlInput.value = url;
            }
        } catch (error) {
            setStatus(error.message, 'error');
            urlInput?.focus();
            return;
        }

        clearPolling();
        showResults();
        setReportMode('loading', { url });
        setLoading(true);
        setStatus('正在创建诊断任务并同步页面分析进度...');

        try {
            const payload = { url };
            if (activeCompanyId) payload.company_id = activeCompanyId;
            const result = await request('/api/diagnostics/', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            activeReportId = result.report_id;
            updateLocation(result.report_id, url);
            await pollReport(result.report_id);
        } catch (error) {
            setLoading(false);
            setReportMode('demo');
            setStatus(error.message, 'error');
        }
    }

    if (initialReportId) {
        showResults();
        setReportMode('loading', { url: initialUrl });
        setLoading(true);
        setStatus('正在恢复这份 GEO 诊断报告...');
        pollReport(initialReportId);
    } else if (initialUrl) {
        showResults();
        setReportMode('loading', { url: initialUrl });
        setStatus('已从上下文带入目标 URL，正在自动发起诊断...');
        startDiagnosis();
    } else {
        showResults();
        setReportMode('demo');
        renderReport(DEMO_REPORT);
    }
});
