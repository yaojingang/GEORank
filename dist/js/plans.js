/**
 * Plans Page - GEO 方案生成器
 */
(window.GEOrank?.PageLifecycle?.run?.bind(window.GEOrank.PageLifecycle)
    || ((callback) => callback()))(() => {
    'use strict';

    const API_BASE = '';
    const Routes = window.GEOrank?.Routes;
    const Auth = window.GEOrank?.Auth;
    const initialRouteState = Routes?.readPlanState
        ? Routes.readPlanState()
        : (() => {
            const params = new URLSearchParams(window.location.search);
            return {
                diagnosticReportId: params.get('report') || params.get('report_id') || params.get('diagnostic_report_id') || '',
                companyId: params.get('company_id') || '',
                sourceUrl: params.get('url') || '',
                prompt: params.get('prompt') || '',
            };
        })();

    const elements = {
        form: document.getElementById('geo-plan-form'),
        goal: document.getElementById('plan-goal'),
        brand: document.getElementById('plan-brand'),
        url: document.getElementById('plan-url'),
        industry: document.getElementById('plan-industry'),
        audience: document.getElementById('plan-audience'),
        stage: document.getElementById('plan-stage'),
        timeline: document.getElementById('plan-timeline'),
        resources: document.getElementById('plan-resources'),
        market: document.getElementById('plan-market'),
        competitors: document.getElementById('plan-competitors'),
        constraints: document.getElementById('plan-constraints'),
        context: document.getElementById('plan-context'),
        contextNote: document.getElementById('plan-context-note'),
        status: document.getElementById('plan-status'),
        generateBtn: document.getElementById('plan-generate-btn'),
        resetBtn: document.getElementById('plan-reset-btn'),
        completenessBar: document.getElementById('plan-completeness-bar'),
        completenessText: document.getElementById('plan-completeness-text'),
        checklist: document.getElementById('plan-checklist'),
        resultPanel: document.getElementById('plan-result-panel'),
        resultMeta: document.getElementById('plan-result-meta'),
        output: document.getElementById('plan-output'),
        resultActions: document.getElementById('plan-result-actions'),
        copyBtn: document.getElementById('plan-copy-btn'),
        exportBtn: document.getElementById('plan-export-btn'),
        openChat: document.getElementById('plan-open-chat'),
        companySection: document.getElementById('plan-company-section'),
        companyList: document.getElementById('plan-company-list'),
    };

    const state = {
        loading: false,
        diagnosticReportId: initialRouteState.diagnosticReportId || '',
        companyId: initialRouteState.companyId || '',
        lastReply: '',
        lastConversationId: '',
        lastRecommendedCompanies: [],
        loadingTimer: null,
        loadingStepIndex: 0,
        loadingTick: 0,
    };

    const LOADING_STEPS = [
        '识别目标与业务约束',
        '拆解页面与内容机会',
        '规划 Schema 和技术标记',
        '组织 30/60/90 天执行节奏',
        '整理交付物与验收指标',
    ];

    const LOADING_MODULES = [
        {
            icon: 'flag',
            title: '目标判断与优先级',
            text: '正在把核心问题拆成可执行目标。',
            width: '84%',
        },
        {
            icon: 'article',
            title: '内容结构与问答页',
            text: '正在生成页面结构、FAQ 和答案式内容建议。',
            width: '72%',
        },
        {
            icon: 'data_object',
            title: 'Schema 与技术标记',
            text: '正在匹配适合的结构化数据和技术动作。',
            width: '64%',
        },
        {
            icon: 'calendar_month',
            title: '30/60/90 天路线图',
            text: '正在安排节奏、负责人、交付物和验收标准。',
            width: '78%',
        },
    ];

    init();

    function init() {
        hydrateFromRoute();
        bindEvents();
        updateCompleteness();
    }

    function hydrateFromRoute() {
        if (initialRouteState.sourceUrl && elements.url) {
            elements.url.value = initialRouteState.sourceUrl;
        }
        if (initialRouteState.prompt && elements.goal) {
            elements.goal.value = initialRouteState.prompt;
        }
        if (state.diagnosticReportId && elements.contextNote) {
            elements.contextNote.classList.remove('hidden');
            elements.contextNote.innerHTML = `
                <div class="flex items-start gap-2">
                    <span class="material-symbols-outlined text-base text-primary">monitoring</span>
                    <div>
                        <p class="font-semibold">已接入诊断上下文</p>
                        <p class="mt-1">方案生成时会携带诊断报告 ${escapeHtml(state.diagnosticReportId.slice(0, 8))}，并结合页面问题拆解执行动作。</p>
                    </div>
                </div>
            `;
        }
    }

    function bindEvents() {
        elements.form?.addEventListener('submit', function (event) {
            event.preventDefault();
            void generatePlan();
        });

        elements.form?.addEventListener('input', updateCompleteness);
        elements.form?.addEventListener('change', updateCompleteness);

        elements.resetBtn?.addEventListener('click', function () {
            elements.form?.reset();
            if (initialRouteState.sourceUrl && elements.url) {
                elements.url.value = initialRouteState.sourceUrl;
            }
            state.lastReply = '';
            state.lastConversationId = '';
            state.lastRecommendedCompanies = [];
            elements.resultPanel?.classList.add('hidden');
            setStatus('');
            updateCompleteness();
        });

        elements.copyBtn?.addEventListener('click', function () {
            void copyPlan();
        });

        elements.exportBtn?.addEventListener('click', function () {
            exportPlanHtml();
        });
    }

    async function generatePlan() {
        if (state.loading) return;
        const values = readFormValues();
        const missing = validateRequired(values);
        if (missing.length) {
            setStatus(`请先补充：${missing.join('、')}`, 'error');
            return;
        }

        state.loading = true;
        state.lastReply = '';
        state.lastConversationId = '';
        state.lastRecommendedCompanies = [];
        setLoading(true);
        setStatus('正在整理上下文并生成 GEO 方案...');
        renderResultPlaceholder(values);

        try {
            const payload = {
                message: buildPlanPrompt(values),
                diagnostic_report_id: state.diagnosticReportId || undefined,
                channel_key: 'action-plan',
            };
            const data = await request('/api/solutions/chat', {
                method: 'POST',
                body: JSON.stringify(payload),
            });

            state.lastReply = data.reply || '';
            state.lastConversationId = data.conversation_id || '';
            state.lastRecommendedCompanies = normalizeCompanies(data.recommended_companies);
            renderPlanResult(values);
            setStatus('GEO 方案已生成。', 'success');
        } catch (error) {
            console.error('[plans] generate failed', error);
            stopLoadingPreview();
            setStatus(error.message || '生成方案失败，请稍后重试。', 'error');
            if (window.GEOrank?.APIKeyStore?.shouldPromptForError?.(error)) {
                window.GEOrank.APIKeyStore.openModal(error.message);
            }
            elements.resultPanel?.classList.remove('is-loading');
            elements.resultActions?.classList.add('hidden');
            elements.companySection?.classList.add('hidden');
            if (elements.output) {
                elements.output.innerHTML = '<p class="text-rose-500">生成失败，请检查 API 服务或稍后重试。</p>';
            }
        } finally {
            state.loading = false;
            setLoading(false);
        }
    }

    async function request(path, options = {}) {
        const headers = {
            ...(options.body ? { 'Content-Type': 'application/json' } : {}),
            ...(options.headers || {}),
        };
        const token = getAuthToken();
        if (token) {
            headers.Authorization = `Bearer ${token}`;
        }
        Object.assign(headers, window.GEOrank?.APIKeyStore?.getHeaders?.() || {});

        const response = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers,
        });
        const raw = await response.text();
        let data = {};
        if (raw) {
            try {
                data = JSON.parse(raw);
            } catch (_) {
                throw new Error('方案接口返回了非 JSON 响应，请检查 /api 代理配置。');
            }
        }
        if (!response.ok) {
            const message = formatApiError(data.detail, response.status);
            throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
        }
        return data;
    }

    function formatApiError(detail, status) {
        if (detail && typeof detail === 'object') {
            return detail.message || JSON.stringify(detail);
        }
        return detail || `请求失败 (${status})`;
    }

    function getAuthToken() {
        return Auth?.getToken?.()
            || localStorage.getItem('georank_user_token')
            || localStorage.getItem('georank_token')
            || '';
    }

    function readFormValues() {
        const focus = Array.from(document.querySelectorAll('input[name="focus"]:checked'))
            .map((input) => input.value);
        return {
            goal: valueOf(elements.goal),
            brand: valueOf(elements.brand),
            url: valueOf(elements.url),
            industry: valueOf(elements.industry),
            audience: valueOf(elements.audience),
            stage: valueOf(elements.stage),
            timeline: valueOf(elements.timeline),
            resources: valueOf(elements.resources),
            market: valueOf(elements.market),
            competitors: valueOf(elements.competitors),
            constraints: valueOf(elements.constraints),
            context: valueOf(elements.context),
            focus,
        };
    }

    function valueOf(element) {
        return String(element?.value || '').trim();
    }

    function validateRequired(values) {
        const missing = [];
        if (!values.goal) missing.push('核心问题 / 目标');
        if (!values.brand && !values.url) missing.push('品牌或目标网站');
        if (!values.industry) missing.push('行业 / 产品类型');
        if (!values.audience) missing.push('目标用户');
        if (!values.focus.length) missing.push('本次重点');
        return missing;
    }

    function updateCompleteness() {
        const values = readFormValues();
        const checks = {
            goal: Boolean(values.goal),
            brand: Boolean(values.brand || values.url),
            industry: Boolean(values.industry),
            audience: Boolean(values.audience),
            focus: Boolean(values.focus.length),
        };
        const done = Object.values(checks).filter(Boolean).length;
        const percent = Math.round((done / Object.keys(checks).length) * 100);

        if (elements.completenessBar) {
            elements.completenessBar.style.width = `${Math.max(percent, 8)}%`;
        }
        if (elements.completenessText) {
            elements.completenessText.textContent = percent >= 100
                ? '必要信息已完整，可以生成 GEO 方案。'
                : `已完成 ${done}/5 项必要信息，补齐后方案会更具体。`;
        }

        Object.entries(checks).forEach(([key, passed]) => {
            const item = elements.checklist?.querySelector(`[data-check="${key}"]`);
            const icon = item?.querySelector('.material-symbols-outlined');
            item?.classList.toggle('is-done', passed);
            if (icon) icon.textContent = passed ? 'check_circle' : 'radio_button_unchecked';
        });
    }

    function buildPlanPrompt(values) {
        return `请基于以下信息，生成一份面向 GEO（生成式引擎优化）的可执行方案。

输出要求：
1. 先判断目标和当前优先级，不要泛泛而谈。
2. 给出 30/60/90 天执行计划，包含负责人建议、交付物和验收指标。
3. 覆盖页面结构、答案式内容、FAQ、Schema、权威引用、AI 搜索可见性、关键词/问答长尾和转化路径。
4. 标出信息缺口，如果我提供的信息不足，请说明需要补充什么。
5. 输出结构清晰，优先用小标题、清单和表格。

用户核心问题/目标：
${values.goal}

业务与网站信息：
- 品牌/产品：${values.brand || '未提供'}
- 目标网站/页面：${values.url || '未提供'}
- 行业/产品类型：${values.industry || '未提供'}
- 目标用户：${values.audience || '未提供'}
- 主要市场/语言：${values.market || '未提供'}
- 当前阶段：${values.stage || '未提供'}

执行条件：
- 执行周期：${values.timeline || '未提供'}
- 团队资源：${values.resources || '未提供'}
- 本次重点：${values.focus.join('、') || '未提供'}
- 竞品/对标：${values.competitors || '未提供'}
- 限制条件/已知问题：${values.constraints || '未提供'}

补充背景：
${values.context || '未提供'}

${state.diagnosticReportId ? `已关联诊断报告 ID：${state.diagnosticReportId}` : ''}
${state.companyId ? `已关联公司 ID：${state.companyId}` : ''}`;
    }

    function renderResultPlaceholder(values) {
        stopLoadingPreview();
        elements.resultPanel?.classList.remove('hidden');
        elements.resultPanel?.classList.add('is-loading');
        elements.resultActions?.classList.add('hidden');
        elements.companySection?.classList.add('hidden');
        if (elements.resultMeta) {
            elements.resultMeta.textContent = '正在生成方案骨架，结果完成后会自动替换为正式内容。';
        }
        if (elements.output) {
            const subject = values.brand || values.url || values.industry || '当前目标';
            elements.output.innerHTML = `
                <div class="plan-loading-shell" aria-live="polite">
                    <div class="plan-loading-header">
                        <div class="plan-loading-spinner">
                            <span class="material-symbols-outlined">auto_awesome</span>
                        </div>
                        <div>
                            <p class="plan-loading-eyebrow">GEO 方案生成中</p>
                            <h3 id="plan-loading-step-title">${escapeHtml(LOADING_STEPS[0])}</h3>
                            <p id="plan-loading-step-copy">正在围绕「${escapeHtml(subject)}」组装可落地的方案模块。</p>
                        </div>
                    </div>
                    <div class="plan-loading-progress">
                        ${LOADING_STEPS.map((step, index) => `
                            <div class="plan-loading-step" data-loading-step="${index}">
                                <span>${String(index + 1).padStart(2, '0')}</span>
                                <p>${escapeHtml(step)}</p>
                            </div>
                        `).join('')}
                    </div>
                    <div class="plan-loading-grid">
                        ${LOADING_MODULES.map((module, index) => `
                            <div class="plan-loading-card" data-loading-card="${index}">
                                <div class="plan-loading-card-head">
                                    <span class="material-symbols-outlined">${module.icon}</span>
                                    <div>
                                        <h4>${escapeHtml(module.title)}</h4>
                                        <p>${escapeHtml(module.text)}</p>
                                    </div>
                                </div>
                                <div class="plan-loading-lines">
                                    <span class="plan-shimmer" style="width:${module.width}"></span>
                                    <span class="plan-shimmer" style="width:92%"></span>
                                    <span class="plan-shimmer" style="width:58%"></span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        startLoadingPreview();
        elements.resultPanel?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function renderPlanResult(values) {
        stopLoadingPreview();
        elements.resultPanel?.classList.remove('is-loading');
        elements.resultActions?.classList.remove('hidden');
        if (elements.resultMeta) {
            const subject = values.brand || values.url || values.industry || '当前目标';
            elements.resultMeta.textContent = `${subject} · ${values.timeline || '执行方案'} · ${new Date().toLocaleString('zh-CN')}`;
        }
        if (elements.output) {
            elements.output.innerHTML = renderMarkdown(state.lastReply || '本次没有生成正文内容。');
        }
        renderCompanies(state.lastRecommendedCompanies);
        updateChatLink(values);
        elements.resultPanel?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function startLoadingPreview() {
        state.loadingStepIndex = 0;
        state.loadingTick = 0;
        updateLoadingPreview();
        state.loadingTimer = window.setInterval(function () {
            state.loadingTick += 1;
            state.loadingStepIndex = Math.min(state.loadingTick, LOADING_STEPS.length - 1);
            updateLoadingPreview();
        }, 1350);
    }

    function stopLoadingPreview() {
        if (state.loadingTimer) {
            window.clearInterval(state.loadingTimer);
            state.loadingTimer = null;
        }
    }

    function updateLoadingPreview() {
        const activeIndex = state.loadingStepIndex;
        const activeCardIndex = state.loadingTick % LOADING_MODULES.length;
        const title = elements.output?.querySelector('#plan-loading-step-title');
        if (title) title.textContent = LOADING_STEPS[activeIndex] || LOADING_STEPS[0];

        elements.output?.querySelectorAll('[data-loading-step]').forEach((item) => {
            const index = Number(item.getAttribute('data-loading-step'));
            item.classList.toggle('is-active', index === activeIndex);
            item.classList.toggle('is-done', index < activeIndex);
        });

        elements.output?.querySelectorAll('[data-loading-card]').forEach((item) => {
            const index = Number(item.getAttribute('data-loading-card'));
            item.classList.toggle('is-active', index === activeCardIndex);
            item.classList.toggle('is-done', index < activeIndex && index !== activeCardIndex);
        });
    }

    function renderCompanies(companies) {
        if (!elements.companySection || !elements.companyList) return;
        if (!companies.length) {
            elements.companySection.classList.add('hidden');
            elements.companyList.innerHTML = '';
            return;
        }
        elements.companySection.classList.remove('hidden');
        elements.companyList.innerHTML = companies.slice(0, 4).map((company) => {
            const companyId = company.id || company.company_id || '';
            const href = companyId ? buildCompanyLink(company.path_key || companyId) : '#';
            return `
                <a class="plan-company-card" href="${escapeHtml(href)}">
                    <p class="text-sm font-bold text-slate-900">${escapeHtml(company.name || '相关公司')}</p>
                    <p class="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">${escapeHtml(company.short_description || '可作为 GEO 执行和能力对标参考。')}</p>
                    <div class="mt-2 flex flex-wrap gap-2 text-[11px] text-blue-700">
                        ${company.category ? `<span>${escapeHtml(company.category)}</span>` : ''}
                        ${company.geo_score != null ? `<span>GEO ${escapeHtml(Math.round(Number(company.geo_score)))}</span>` : ''}
                    </div>
                </a>
            `;
        }).join('');
    }

    function updateChatLink(values) {
        if (!elements.openChat) return;
        const prompt = `请基于刚才生成的 GEO 方案，继续帮我细化「${(values.goal || '当前目标').slice(0, 60)}」的下一步执行细节。`;
        if (Routes?.buildSolutionPath) {
            elements.openChat.href = Routes.buildSolutionPath({
                conversationId: state.lastConversationId || '',
                diagnosticReportId: state.diagnosticReportId || '',
                companyId: state.companyId || '',
                url: values.url || '',
                prompt: state.lastConversationId ? '' : prompt,
                channelKey: 'action-plan',
            });
            return;
        }
        const next = new URL('/solutions', window.location.origin);
        next.searchParams.set('channel', 'action-plan');
        if (state.lastConversationId) next.searchParams.set('conversation', state.lastConversationId);
        else next.searchParams.set('prompt', prompt);
        elements.openChat.href = next.toString();
    }

    async function copyPlan() {
        if (!state.lastReply) return;
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(state.lastReply);
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = state.lastReply;
                textarea.setAttribute('readonly', 'readonly');
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                textarea.remove();
            }
            setStatus('方案内容已复制。', 'success');
        } catch (_) {
            setStatus('复制失败，请手动选择方案内容。', 'error');
        }
    }

    function exportPlanHtml() {
        if (!state.lastReply) return;
        const values = readFormValues();
        const title = (values.brand || values.url || 'GEO方案').replace(/[\\/:*?"<>|]+/g, '-');
        const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>${escapeHtml(title)} - GEO 方案</title>
    <style>
        body { max-width: 920px; margin: 40px auto; font-family: Inter, -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif; color: #0f172a; line-height: 1.8; }
        h1, h2, h3 { line-height: 1.35; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border-bottom: 1px solid #e2e8f0; padding: 10px; text-align: left; vertical-align: top; }
        blockquote { border-left: 3px solid #2563eb; background: #eff6ff; padding: 10px 14px; }
        code { background: #eff6ff; color: #1d4ed8; padding: 2px 5px; border-radius: 5px; }
    </style>
</head>
<body>
    <p style="font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#2563eb;font-weight:800;">GEOrank GEO Plan</p>
    ${renderMarkdown(state.lastReply)}
</body>
</html>`;
        const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${title}.html`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        setStatus('HTML 方案已导出。', 'success');
    }

    function renderMarkdown(text) {
        const source = String(text || '').trim();
        const markedApi = window.marked;
        const purifier = window.DOMPurify;
        if (!markedApi?.parse || !purifier?.sanitize) {
            return `<p>${escapeHtml(source).replace(/\n/g, '<br>')}</p>`;
        }
        markedApi.setOptions({
            gfm: true,
            breaks: true,
            headerIds: false,
            mangle: false,
        });
        return purifier.sanitize(markedApi.parse(source), {
            USE_PROFILES: { html: true },
        });
    }

    function normalizeCompanies(value) {
        if (Array.isArray(value)) return value;
        if (value && Array.isArray(value.items)) return value.items;
        return [];
    }

    function buildCompanyLink(companyIdentifier) {
        if (Routes?.buildCompanyDetail) {
            return Routes.buildCompanyDetail(companyIdentifier);
        }
        const url = new URL('/company', window.location.origin);
        if (companyIdentifier) url.searchParams.set('id', companyIdentifier);
        return url.toString();
    }

    function setLoading(loading) {
        if (!elements.generateBtn) return;
        elements.generateBtn.disabled = loading;
        if (elements.resetBtn) {
            elements.resetBtn.disabled = loading;
        }
        elements.generateBtn.innerHTML = loading
            ? '<span class="material-symbols-outlined animate-spin text-sm">progress_activity</span><span>生成中</span>'
            : '<span class="material-symbols-outlined text-sm">auto_awesome</span><span>生成 GEO 方案</span>';
    }

    function setStatus(message, tone = 'info') {
        if (!elements.status) return;
        if (!message) {
            elements.status.classList.add('hidden');
            elements.status.textContent = '';
            return;
        }
        elements.status.classList.remove('hidden', 'text-slate-500', 'text-red-500', 'text-green-600');
        elements.status.classList.add(
            tone === 'error'
                ? 'text-red-500'
                : tone === 'success'
                    ? 'text-green-600'
                    : 'text-slate-500'
        );
        elements.status.textContent = message;
    }

    function escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = value == null ? '' : String(value);
        return div.innerHTML;
    }
});
