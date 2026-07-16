/**
 * GEOrank - 拓词工具 JavaScript
 * 调用后端 AI API 生成 8 维拓词结果
 */
(window.GEOrank?.PageLifecycle?.run?.bind(window.GEOrank.PageLifecycle)
    || ((callback) => callback()))(() => {
    'use strict';

    const API_BASE = ['80', '443', ''].includes(window.location.port)
        ? ''
        : `${window.location.protocol}//${window.location.hostname}:8000`;
    const Auth = window.GEOrank?.Auth;
    const PREVIEW_COUNT = 8;
    const SAMPLE_PAYLOAD = {
        seeds: ['GEO服务商'],
        profile: {
            name: '企业服务',
            company_hint: '提供“GEO服务商”相关软件、咨询或服务的企业',
            business_model: '偏 B2B / 企业服务 / 解决方案导向',
            target_users: ['企业负责人', '市场团队', '增长团队', '内容团队'],
            keyword_strategy: '优先覆盖服务采购、方案对比、团队场景和实施决策。',
        },
        summary: {
            total_keywords: 64,
            average_recommendation_score: 77,
            average_business_score: 73,
            high_recommendation_ratio: 34,
            high_business_ratio: 27,
        },
        dimensions: [
            {
                key: 'semantic',
                name: '语义拓展',
                icon: 'hub',
                description: '同义词、相关术语、长尾变体',
                count: 8,
                items: [
                    { keyword: 'GEO服务', recommendation_score: 81, business_score: 72 },
                    { keyword: 'GEO优化公司', recommendation_score: 83, business_score: 75 },
                    { keyword: 'AI搜索优化服务', recommendation_score: 79, business_score: 73 },
                    { keyword: '生成式搜索优化', recommendation_score: 77, business_score: 71 },
                    { keyword: '品牌GEO优化', recommendation_score: 76, business_score: 74 },
                    { keyword: 'GEO咨询服务', recommendation_score: 74, business_score: 78 },
                    { keyword: '企业GEO方案', recommendation_score: 73, business_score: 76 },
                    { keyword: '官网GEO优化', recommendation_score: 75, business_score: 72 },
                ],
            },
            {
                key: 'scenario',
                name: '场景覆盖',
                icon: 'category',
                description: '使用场景、上下文、应用情境',
                count: 8,
                items: [
                    { keyword: '企业官网GEO优化', recommendation_score: 81, business_score: 73 },
                    { keyword: '品牌出海AI搜索优化', recommendation_score: 79, business_score: 72 },
                    { keyword: 'B2B企业GEO方案', recommendation_score: 77, business_score: 75 },
                    { keyword: '内容团队GEO执行', recommendation_score: 74, business_score: 70 },
                    { keyword: 'SaaS公司AI搜索优化', recommendation_score: 78, business_score: 76 },
                    { keyword: '官网改版GEO升级', recommendation_score: 73, business_score: 71 },
                    { keyword: '企业知识库GEO治理', recommendation_score: 76, business_score: 74 },
                    { keyword: '品牌问答页GEO优化', recommendation_score: 75, business_score: 73 },
                ],
            },
            {
                key: 'commercial',
                name: '商业意图',
                icon: 'shopping_cart',
                description: '购买信号、比较、定价查询',
                count: 8,
                items: [
                    { keyword: 'GEO服务商推荐', recommendation_score: 82, business_score: 84 },
                    { keyword: 'GEO服务商报价', recommendation_score: 74, business_score: 86 },
                    { keyword: 'GEO优化公司哪家好', recommendation_score: 85, business_score: 82 },
                    { keyword: 'GEO咨询费用', recommendation_score: 69, business_score: 80 },
                    { keyword: 'GEO实施预算', recommendation_score: 71, business_score: 78 },
                    { keyword: 'AI搜索优化服务价格', recommendation_score: 73, business_score: 85 },
                    { keyword: 'GEO顾问服务', recommendation_score: 76, business_score: 77 },
                    { keyword: 'GEO项目采购', recommendation_score: 68, business_score: 81 },
                ],
            },
            {
                key: 'ranking',
                name: '推荐榜单',
                icon: 'emoji_events',
                description: '最佳、推荐、Top 类查询',
                count: 8,
                items: [
                    { keyword: 'GEO服务商排名', recommendation_score: 84, business_score: 80 },
                    { keyword: 'GEO优化公司推荐', recommendation_score: 82, business_score: 79 },
                    { keyword: 'AI搜索优化Top10', recommendation_score: 80, business_score: 77 },
                    { keyword: '中国GEO咨询公司榜单', recommendation_score: 79, business_score: 76 },
                    { keyword: '品牌GEO服务商推荐', recommendation_score: 78, business_score: 75 },
                    { keyword: '企业GEO平台哪家好', recommendation_score: 81, business_score: 78 },
                    { keyword: 'GEO优化工具推荐', recommendation_score: 77, business_score: 72 },
                    { keyword: 'AI搜索服务商优选', recommendation_score: 76, business_score: 74 },
                ],
            },
            {
                key: 'review',
                name: '产品评测',
                icon: 'rate_review',
                description: '评测、对比、优缺点查询',
                count: 8,
                items: [
                    { keyword: 'GEO服务商评测', recommendation_score: 80, business_score: 74 },
                    { keyword: 'GEO优化公司对比', recommendation_score: 82, business_score: 78 },
                    { keyword: 'AI搜索优化服务测评', recommendation_score: 78, business_score: 73 },
                    { keyword: 'GEO咨询优缺点', recommendation_score: 71, business_score: 69 },
                    { keyword: '官网GEO服务体验', recommendation_score: 74, business_score: 70 },
                    { keyword: 'GEO方案案例分析', recommendation_score: 79, business_score: 76 },
                    { keyword: 'GEO优化工具实测', recommendation_score: 76, business_score: 71 },
                    { keyword: 'GEO服务口碑', recommendation_score: 72, business_score: 75 },
                ],
            },
            {
                key: 'brand',
                name: '品牌关联',
                icon: 'business',
                description: '品牌名、产品名、替代方案',
                count: 8,
                items: [
                    { keyword: '移山科技 GEO服务', recommendation_score: 77, business_score: 72 },
                    { keyword: 'GEOrank 服务商', recommendation_score: 76, business_score: 73 },
                    { keyword: 'GEO服务商官网', recommendation_score: 74, business_score: 70 },
                    { keyword: 'GEO服务商竞品', recommendation_score: 78, business_score: 74 },
                    { keyword: 'GEO优化替代方案', recommendation_score: 75, business_score: 68 },
                    { keyword: '品牌AI可见度服务商', recommendation_score: 79, business_score: 72 },
                    { keyword: '生成式搜索优化公司', recommendation_score: 80, business_score: 75 },
                    { keyword: 'AI搜索咨询品牌', recommendation_score: 73, business_score: 71 },
                ],
            },
            {
                key: 'question',
                name: '问答长尾',
                icon: 'help',
                description: '如何、怎么、为什么类查询',
                count: 8,
                items: [
                    { keyword: '什么是GEO服务商', recommendation_score: 80, business_score: 62 },
                    { keyword: '企业为什么要做GEO', recommendation_score: 78, business_score: 66 },
                    { keyword: 'GEO服务商怎么选', recommendation_score: 84, business_score: 79 },
                    { keyword: '官网如何做AI搜索优化', recommendation_score: 77, business_score: 70 },
                    { keyword: 'GEO适合哪些企业', recommendation_score: 75, business_score: 69 },
                    { keyword: 'GEO咨询包含什么内容', recommendation_score: 73, business_score: 72 },
                    { keyword: 'GEO项目周期多长', recommendation_score: 70, business_score: 75 },
                    { keyword: 'AI搜索优化有哪些步骤', recommendation_score: 79, business_score: 68 },
                ],
            },
            {
                key: 'technical',
                name: '技术方案',
                icon: 'engineering',
                description: '部署、集成、API、架构类查询',
                count: 8,
                items: [
                    { keyword: 'GEO监测 API', recommendation_score: 73, business_score: 66 },
                    { keyword: 'AI搜索优化工作流', recommendation_score: 77, business_score: 70 },
                    { keyword: '企业GEO系统设计', recommendation_score: 75, business_score: 69 },
                    { keyword: '官网GEO数据结构', recommendation_score: 72, business_score: 67 },
                    { keyword: 'GEO自动化方案', recommendation_score: 74, business_score: 71 },
                    { keyword: 'Schema与FAQ集成', recommendation_score: 76, business_score: 68 },
                    { keyword: 'GEO知识库搭建', recommendation_score: 79, business_score: 73 },
                    { keyword: 'AI搜索优化部署', recommendation_score: 71, business_score: 69 },
                ],
            },
        ],
    };

    const DIM_MAP = {
        semantic: { key: 'semantic', name: '语义拓展', icon: 'hub', desc: '同义词、相关术语、长尾变体' },
        scenario: { key: 'scenario', name: '场景覆盖', icon: 'category', desc: '使用场景、上下文、应用情境' },
        commercial: { key: 'commercial', name: '商业意图', icon: 'shopping_cart', desc: '购买信号、比较、定价查询' },
        ranking: { key: 'ranking', name: '推荐榜单', icon: 'emoji_events', desc: '最佳、推荐、Top 类查询' },
        review: { key: 'review', name: '产品评测', icon: 'rate_review', desc: '评测、对比、优缺点查询' },
        brand: { key: 'brand', name: '品牌关联', icon: 'business', desc: '品牌名、产品名、替代方案' },
        question: { key: 'question', name: '问答长尾', icon: 'help', desc: '如何、怎么、为什么类查询' },
        technical: { key: 'technical', name: '技术方案', icon: 'engineering', desc: '部署、集成、API、架构类查询' },
    };

    const inputEl = document.getElementById('keyword-input');
    const wrapperEl = document.getElementById('tag-input-wrapper');
    const generateBtn = document.getElementById('generate-btn');
    const resultsPanel = document.getElementById('results-panel');
    const skeletonEl = document.getElementById('skeleton-loading');
    const dimGrid = document.getElementById('dim-grid');
    const downloadBtn = document.getElementById('download-csv-btn');
    const refineBtn = document.getElementById('refine-btn');
    const feedbackEl = document.getElementById('keyword-feedback');
    const totalCountEl = document.getElementById('total-kw-count');
    const seedDisplayEl = document.getElementById('seed-kw-display');
    const profileCardEl = document.getElementById('keyword-profile-card');
    const profileNameEl = document.getElementById('keyword-profile-name');
    const profileHintEl = document.getElementById('keyword-profile-hint');
    const profileStrategyEl = document.getElementById('keyword-profile-strategy');
    const profileModelEl = document.getElementById('keyword-profile-model');
    const profileAudienceEl = document.getElementById('keyword-profile-audience');
    const statTotalEl = document.getElementById('stat-total');
    const statAvgRecEl = document.getElementById('stat-avg-rec');
    const statAvgBizEl = document.getElementById('stat-avg-biz');
    const statHighRecEl = document.getElementById('stat-high-rec');
    const statHighBizEl = document.getElementById('stat-high-biz');

    let tags = [];
    let currentDimensions = [];
    let flatList = [];
    let composing = false;
    let loading = false;

    function esc(str) {
        const d = document.createElement('div');
        d.textContent = String(str ?? '');
        return d.innerHTML;
    }

    function setLoading(next) {
        loading = next;
        generateBtn.disabled = next;
        refineBtn.disabled = next;
        downloadBtn.disabled = next || !flatList.length;
        if (next) {
            generateBtn.innerHTML = '<span class="material-symbols-outlined animate-spin text-sm">progress_activity</span><span>生成中...</span>';
            skeletonEl.classList.remove('hidden');
            resultsPanel.classList.add('hidden');
        } else {
            generateBtn.textContent = '生成词包';
            skeletonEl.classList.add('hidden');
        }
    }

    function setFeedback(message = '', type = 'error') {
        if (!feedbackEl) return;
        feedbackEl.textContent = message;
        feedbackEl.classList.toggle('hidden', !message);
        feedbackEl.classList.toggle('text-rose-500', type !== 'success');
        feedbackEl.classList.toggle('text-emerald-600', type === 'success');
        wrapperEl.classList.toggle('is-invalid', Boolean(message && type !== 'success'));
    }

    function clonePayload(payload) {
        return JSON.parse(JSON.stringify(payload));
    }

    async function request(path, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        };
        const token = Auth?.getToken?.()
            || localStorage.getItem('georank_user_token')
            || localStorage.getItem('georank_token')
            || '';
        if (token) {
            headers.Authorization = `Bearer ${token}`;
        }
        Object.assign(headers, window.GEOrank?.APIKeyStore?.getHeaders?.() || {});
        const response = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers,
        });
        const data = await response.json().catch(() => ({}));
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

    function addTag(text) {
        const value = String(text || '').trim();
        if (!value || tags.includes(value)) return;
        tags.push(value.slice(0, 40));
        renderTags();
        setFeedback('');
    }

    function removeTag(text) {
        tags = tags.filter((item) => item !== text);
        renderTags();
    }

    function renderTags() {
        wrapperEl.querySelectorAll('.keyword-tag').forEach((el) => el.remove());
        tags.forEach((tag) => {
            const span = document.createElement('span');
            span.className = 'keyword-tag';
            span.innerHTML = `${esc(tag)}<button type="button" aria-label="删除">&times;</button>`;
            span.querySelector('button').addEventListener('click', () => removeTag(tag));
            wrapperEl.insertBefore(span, inputEl);
        });
    }

    function consumeDraftInput() {
        const draft = String(inputEl.value || '').trim();
        if (!draft) return;
        draft
            .split(/[,，\n\r\t]+/)
            .forEach((item) => addTag(item));
        inputEl.value = '';
    }

    function rebuildFlatList() {
        flatList = [];
        currentDimensions.forEach((dimension) => {
            (dimension.items || []).forEach((item) => {
                flatList.push({
                    dim: dimension.key,
                    kw: item.keyword,
                    rec: item.recommendation_score,
                    biz: item.business_score,
                });
            });
        });
    }

    function renderProfile(profile) {
        if (!profileCardEl) return;
        if (!profile) {
            profileCardEl.classList.add('hidden');
            return;
        }
        profileNameEl.textContent = profile.name || '业务画像';
        profileHintEl.textContent = profile.company_hint || '';
        profileStrategyEl.textContent = profile.keyword_strategy || '';
        profileModelEl.textContent = profile.business_model || '';
        profileAudienceEl.innerHTML = '';
        (profile.target_users || []).forEach((user) => {
            const chip = document.createElement('span');
            chip.className = 'inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600';
            chip.textContent = user;
            profileAudienceEl.appendChild(chip);
        });
        profileCardEl.classList.remove('hidden');
    }

    function updateStats(summary, options = {}) {
        statTotalEl.textContent = summary.total_keywords || 0;
        statAvgRecEl.textContent = summary.average_recommendation_score || 0;
        statAvgBizEl.textContent = summary.average_business_score || 0;
        statHighRecEl.textContent = summary.high_recommendation_ratio || 0;
        statHighBizEl.textContent = summary.high_business_ratio || 0;
        totalCountEl.textContent = summary.total_keywords || 0;
        seedDisplayEl.textContent = options.seedLabel || tags.join('、');
    }

    function renderGrid() {
        dimGrid.innerHTML = '';

        currentDimensions.forEach((dimension) => {
            const meta = DIM_MAP[dimension.key] || {};
            const items = Array.isArray(dimension.items) ? dimension.items : [];
            const card = document.createElement('div');
            card.className = 'dim-card';

            const renderRows = (rows) => rows.map((item) => `
                <div class="dim-table-row">
                    <div class="kw-name">
                        <div>${esc(item.keyword)}</div>
                    </div>
                    <div class="score-cell"><div class="score-bar"><div class="score-bar-fill rec" style="width:${item.recommendation_score}%"></div></div><span class="score-num rec">${item.recommendation_score}</span></div>
                    <div class="score-cell"><div class="score-bar"><div class="score-bar-fill biz" style="width:${item.business_score}%"></div></div><span class="score-num biz">${item.business_score}</span></div>
                </div>
            `).join('');

            const preview = items.slice(0, PREVIEW_COUNT);
            card.innerHTML = `
                <div class="dim-card-header">
                    <div class="flex items-center gap-2">
                        <span class="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center"><span class="material-symbols-outlined text-slate-500 text-base">${esc(meta.icon || dimension.icon || 'category')}</span></span>
                        <div><span class="text-sm font-bold">${esc(meta.name || dimension.name)}</span><span class="text-xs text-on-surface-variant ml-2">${items.length} 词</span></div>
                    </div>
                    <span class="text-[10px] text-on-surface-variant">${esc(meta.desc || dimension.description || '')}</span>
                </div>
                <div class="dim-table-header"><div>关键词</div><div>推荐</div><div>商业</div></div>
                <div class="dim-table-body">${renderRows(preview)}</div>
            `;

            if (items.length > PREVIEW_COUNT) {
                const btn = document.createElement('button');
                btn.className = 'dim-show-more';
                btn.textContent = `展开全部 ${items.length} 条`;
                let expanded = false;
                btn.addEventListener('click', () => {
                    expanded = !expanded;
                    card.querySelector('.dim-table-body').innerHTML = renderRows(expanded ? items : preview);
                    btn.textContent = expanded ? '收起' : `展开全部 ${items.length} 条`;
                });
                card.appendChild(btn);
            }

            dimGrid.appendChild(card);
        });
    }

    function renderResults(payload, options = {}) {
        currentDimensions = Array.isArray(payload.dimensions) ? payload.dimensions : [];
        rebuildFlatList();
        renderProfile(payload.profile);
        updateStats(payload.summary || {}, {
            seedLabel: options.seedLabel || tags.join('、'),
        });
        renderGrid();
        resultsPanel.classList.remove('hidden');
        refineBtn.disabled = Boolean(options.disableRefine);
    }

    async function generate() {
        if (loading) return;
        consumeDraftInput();
        if (!tags.length) {
            setFeedback('请输入至少一个关键词，再生成词包。');
            inputEl.focus();
            return;
        }
        if (Auth && !Auth.requireAuth({ reasonKey: 'auth.reasonKeywords' })) {
            return;
        }

        setFeedback('');
        setLoading(true);
        try {
            const payload = await request('/api/keywords/expand', {
                method: 'POST',
                body: JSON.stringify({ seeds: tags }),
            });
            renderResults(payload, {
                isExample: false,
                seedLabel: tags.join('、'),
                disableRefine: false,
            });
        } catch (error) {
            setFeedback(error.message || '生成词包失败，请稍后重试。');
            if (window.GEOrank?.APIKeyStore?.shouldPromptForError?.(error)) {
                window.GEOrank.APIKeyStore.openModal(error.message);
            }
        } finally {
            setLoading(false);
        }
    }

    function downloadCSV() {
        if (!flatList.length) return;
        const BOM = '\uFEFF';
        const rows = ['维度,关键词,推荐指数,商业指数'];
        flatList.forEach((item) => {
            const dim = DIM_MAP[item.dim];
            rows.push(`${dim ? dim.name : ''},${item.kw},${item.rec},${item.biz}`);
        });
        const blob = new Blob([BOM + rows.join('\n')], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `GEOrank_词包_${tags.join('_')}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }

    inputEl.addEventListener('compositionstart', () => { composing = true; });
    inputEl.addEventListener('compositionend', () => { composing = false; });
    inputEl.addEventListener('keydown', (event) => {
        if (composing) return;
        if (event.key === 'Enter' || event.key === ',') {
            event.preventDefault();
            addTag(inputEl.value);
            inputEl.value = '';
            return;
        }
        if (event.key === 'Backspace' && !inputEl.value && tags.length) {
            removeTag(tags[tags.length - 1]);
        }
    });
    inputEl.addEventListener('paste', (event) => {
        event.preventDefault();
        (event.clipboardData || window.clipboardData).getData('text')
            .split(/[,，\n\r\t]+/)
            .forEach((item) => addTag(item));
        inputEl.value = '';
    });
    inputEl.addEventListener('input', () => {
        if (inputEl.value.trim()) {
            setFeedback('');
        }
    });

    generateBtn.addEventListener('click', generate);
    inputEl.addEventListener('keydown', (event) => {
        if (!composing && event.key === 'Enter' && !inputEl.value && tags.length) {
            generate();
        }
    });
    downloadBtn.addEventListener('click', downloadCSV);
    refineBtn.addEventListener('click', generate);

    renderResults(clonePayload(SAMPLE_PAYLOAD), {
        isExample: true,
        seedLabel: '示例词包',
        disableRefine: true,
    });
});
