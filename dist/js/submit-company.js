/**
 * 提交公司 - 真实入库流水线交互
 */
(window.GEOrank?.PageLifecycle?.run?.bind(window.GEOrank.PageLifecycle)
    || ((callback) => callback()))(() => {
    'use strict';

    const API_BASE = '';

    const modal = document.getElementById('submit-modal');
    const overlay = document.getElementById('submit-modal-overlay');
    const closeBtn = document.getElementById('submit-modal-close');
    const urlInput = document.getElementById('submit-url-input');
    const startBtn = document.getElementById('submit-start-btn');
    const stepInput = document.getElementById('submit-step-input');
    const stepPipeline = document.getElementById('submit-step-pipeline');
    const pipelineUrl = document.getElementById('pipeline-url');
    const pipelineNote = document.getElementById('pipeline-status-note');
    const pipelineActivity = document.getElementById('pipeline-activity');
    const pipelineFeed = document.getElementById('pipeline-feed');
    const pipelinePagesPanel = document.getElementById('pipeline-pages-panel');
    const pipelinePagesList = document.getElementById('pipeline-pages-list');
    const pipelineComplete = document.getElementById('pipeline-complete');
    const pipelineCompleteTitle = document.getElementById('pipeline-complete-title');
    const pipelineCompleteDesc = document.getElementById('pipeline-complete-desc');
    const doneBtn = document.getElementById('pipeline-done-btn');

    const stepOrder = ['crawl', 'clean', 'graph', 'vector'];
    const statusMap = {
        pending: { active: 0, completed: -1, note: '已加入处理队列，正在等待系统开始分析。', activity: '正在创建公司任务并加入处理队列...' },
        crawling: { active: 0, completed: -1, note: '正在抓取官网首页和一级目录，AI 将锁定最值得深入的页面。', activity: '正在解析官网首页并识别一级目录链接...' },
        cleaning: { active: 1, completed: 0, note: '关键页面已锁定，正在抽取企业介绍、产品与团队信息。', activity: '正在整合关键页面内容并结构化抽取企业信息...' },
        graph_building: { active: 2, completed: 1, note: '结构化数据准备就绪，正在构建知识图谱。', activity: '正在构建实体关系与企业知识图谱...' },
        vectorizing: { active: 3, completed: 2, note: '知识图谱已生成，正在写入向量知识库。', activity: '正在将企业知识写入语义检索索引...' },
        completed: { active: -1, completed: 3, note: '知识库构建完成，已进入审核队列。', activity: '企业知识库构建完成，等待管理员审核。' },
    };

    let pollTimer = null;
    let seenFeedKeys = new Set();
    const AUTO_OPEN_FLAG = 'georank_open_submit_company';

    document.addEventListener('click', function (event) {
        const btn = event.target.closest('[data-submit-company-trigger]');
        if (btn) {
            openModal();
        }
    });

    overlay?.addEventListener('click', closeModal);
    closeBtn?.addEventListener('click', closeModal);
    doneBtn?.addEventListener('click', closeModal);
    startBtn?.addEventListener('click', startPipeline);
    urlInput?.addEventListener('blur', () => {
        const normalized = normalizeUrlInput(urlInput.value);
        if (normalized) {
            urlInput.value = normalized;
        }
    });

    function getAuthToken() {
        return localStorage.getItem('georank_user_token')
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

    function clearPolling() {
        if (pollTimer) {
            clearTimeout(pollTimer);
            pollTimer = null;
        }
    }

    function normalizeUrlInput(raw) {
        const value = (raw || '').trim();
        if (!value) return null;
        const withProtocol = value.includes('://')
            ? value
            : value.startsWith('//')
                ? `https:${value}`
                : `https://${value}`;
        try {
            const parsed = new URL(withProtocol);
            if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname) {
                return null;
            }
            parsed.hash = '';
            parsed.search = '';
            if (parsed.pathname === '/') {
                parsed.pathname = '';
            }
            return parsed.toString().replace(/\/$/, '');
        } catch (_) {
            return null;
        }
    }

    function appendFeedItem(key, icon, text) {
        if (!pipelineFeed || seenFeedKeys.has(key)) return;
        seenFeedKeys.add(key);
        const item = document.createElement('div');
        item.className = 'flex items-start gap-3 text-xs text-slate-500';
        item.innerHTML = `
            <span class="material-symbols-outlined text-sm text-primary mt-0.5">${icon}</span>
            <span>${text}</span>
        `;
        pipelineFeed.appendChild(item);
    }

    function renderSelectedPages(pages) {
        if (!pipelinePagesPanel || !pipelinePagesList) return;
        const selectedPages = Array.isArray(pages) ? pages.filter(Boolean) : [];
        if (!selectedPages.length) {
            pipelinePagesPanel.classList.add('hidden');
            pipelinePagesList.innerHTML = '';
            return;
        }

        pipelinePagesPanel.classList.remove('hidden');
        pipelinePagesList.innerHTML = selectedPages.map((page, index) => {
            const roleMap = {
                homepage: '主页',
                about: '公司介绍',
                team: '团队页',
                product: '产品页',
                supporting: '补充页',
            };
            const statusText = page.status === 'captured'
                ? '已锁定'
                : page.status === 'failed'
                    ? '抓取失败'
                    : '待抓取';
            const statusClass = page.status === 'failed'
                ? 'text-red-500 bg-red-50'
                : page.status === 'captured'
                    ? 'text-primary bg-primary/10'
                    : 'text-slate-500 bg-slate-100';
            return `
                <div class="rounded-xl border border-slate-200 bg-slate-50/60 p-3">
                    <div class="flex items-start justify-between gap-3">
                        <div class="min-w-0">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="inline-flex w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold items-center justify-center">${index + 1}</span>
                                <span class="text-xs font-semibold text-slate-400">${roleMap[page.role] || '关键页'}</span>
                            </div>
                            <p class="text-sm font-semibold text-slate-900 break-all">${page.title || page.url}</p>
                            <p class="text-[11px] text-slate-500 mt-1 leading-5">${page.reason || '该页面将参与企业知识库构建。'}</p>
                        </div>
                        <span class="shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold ${statusClass}">${statusText}</span>
                    </div>
                    <p class="text-[11px] text-slate-400 mt-2 break-all">${page.url}</p>
                </div>
            `;
        }).join('');
    }

    function updateDynamicPanels(status, currentActivity, selectedPages) {
        const config = statusMap[status] || statusMap.pending;
        if (pipelineActivity) {
            pipelineActivity.textContent = currentActivity || config.activity || config.note;
        }

        const statusFeed = {
            pending: ['queue', 'hourglass_empty', '已创建任务，等待进入官网解析队列。'],
            crawling: ['crawl', 'travel_explore', selectedPages?.length
                ? `已从首页一级目录中锁定 ${selectedPages.length} 个关键页面，正在抓取内容。`
                : '已抓取官网首页，正在分析一级目录链接与标题。'],
            cleaning: ['clean', 'data_object', '已完成关键页抓取，正在提取企业信息与结构化摘要。'],
            graph_building: ['graph', 'hub', '正在梳理企业实体、产品能力与关系图谱。'],
            vectorizing: ['vector', 'neurology', '正在将知识内容写入语义索引，支持后续检索与推荐。'],
            completed: ['done', 'check_circle', '企业知识库构建完成，已进入审核队列。'],
            failed: ['failed', 'error', '本次分析失败，可稍后重试。'],
        };
        const entry = statusFeed[status];
        if (entry) {
            appendFeedItem(entry[0], entry[1], entry[2]);
        }

        if (selectedPages?.length) {
            appendFeedItem('selected-pages', 'scan', `AI 已从首页一级目录中选择 ${selectedPages.length} 个高优先级页面进入最终分析。`);
        }

        renderSelectedPages(selectedPages);
    }

    function setStepState(stepName, state) {
        const stepEl = document.querySelector(`#pipeline-steps [data-step="${stepName}"]`);
        if (!stepEl) return;
        const iconBg = stepEl.querySelector('.w-8');
        const iconEl = iconBg?.querySelector('.material-symbols-outlined');
        const statusIcon = stepEl.querySelector('.step-icon');

        if (!iconBg || !iconEl || !statusIcon) return;

        if (state === 'done') {
            iconBg.className = 'w-8 h-8 rounded-full bg-green-50 flex items-center justify-center shrink-0';
            iconEl.className = 'material-symbols-outlined text-green-600 text-base';
            statusIcon.textContent = 'check_circle';
            statusIcon.className = 'material-symbols-outlined text-green-600 text-lg step-icon filled';
            return;
        }

        if (state === 'active') {
            iconBg.className = 'w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0';
            iconEl.className = 'material-symbols-outlined text-primary text-base';
            statusIcon.textContent = 'progress_activity';
            statusIcon.className = 'material-symbols-outlined text-primary text-lg step-icon animate-spin';
            return;
        }

        if (state === 'failed') {
            iconBg.className = 'w-8 h-8 rounded-full bg-red-50 flex items-center justify-center shrink-0';
            iconEl.className = 'material-symbols-outlined text-red-500 text-base';
            statusIcon.textContent = 'error';
            statusIcon.className = 'material-symbols-outlined text-red-500 text-lg step-icon filled';
            return;
        }

        iconBg.className = 'w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center shrink-0';
        iconEl.className = 'material-symbols-outlined text-slate-400 text-base';
        statusIcon.textContent = 'circle';
        statusIcon.className = 'material-symbols-outlined text-slate-300 text-lg step-icon';
    }

    function resetPipelineState() {
        clearPolling();
        seenFeedKeys = new Set();
        stepOrder.forEach((stepName) => setStepState(stepName, 'idle'));
        pipelineComplete?.classList.add('hidden');
        if (pipelineNote) {
            pipelineNote.className = 'mb-4 text-xs text-slate-500';
            pipelineNote.textContent = '已加入处理队列，正在等待系统开始分析。';
        }
        if (pipelineActivity) {
            pipelineActivity.textContent = '正在创建公司任务并加入处理队列...';
        }
        if (pipelineFeed) {
            pipelineFeed.innerHTML = `
                <div class="flex items-start gap-3 text-xs text-slate-500">
                    <span class="material-symbols-outlined text-sm text-primary mt-0.5">travel_explore</span>
                    <span>准备抓取官网首页并识别一级目录链接。</span>
                </div>
            `;
        }
        pipelinePagesPanel?.classList.add('hidden');
        if (pipelinePagesList) {
            pipelinePagesList.innerHTML = '';
        }
        if (pipelineCompleteTitle) pipelineCompleteTitle.textContent = '知识库构建完成';
        if (pipelineCompleteDesc) pipelineCompleteDesc.textContent = '公司资料已提交审核，管理员审核后将在目录中展示';
        if (doneBtn) doneBtn.textContent = '完成';
        if (startBtn) {
            startBtn.disabled = false;
            startBtn.textContent = '开始 AI 分析';
        }
    }

    function openModal(prefillUrl = '') {
        if (!modal) return;
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        stepInput?.classList.remove('hidden');
        stepPipeline?.classList.add('hidden');
        if (urlInput) urlInput.value = prefillUrl || '';
        resetPipelineState();
    }

    function closeModal() {
        if (!modal) return;
        clearPolling();
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }

    function showPipeline() {
        stepInput?.classList.add('hidden');
        stepPipeline?.classList.remove('hidden');
        pipelineComplete?.classList.add('hidden');
    }

    function showCompletion(title, description, tone) {
        const isError = tone === 'error';
        if (pipelineCompleteTitle) pipelineCompleteTitle.textContent = title;
        if (pipelineCompleteDesc) pipelineCompleteDesc.textContent = description;
        if (doneBtn) doneBtn.textContent = isError ? '关闭' : '完成';

        const card = pipelineComplete?.querySelector('div');
        const icon = pipelineComplete?.querySelector('.material-symbols-outlined');
        if (card) {
            card.className = isError
                ? 'p-4 bg-red-50 rounded-lg flex items-center gap-3'
                : 'p-4 bg-green-50 rounded-lg flex items-center gap-3';
        }
        if (icon) {
            icon.textContent = isError ? 'error' : 'check_circle';
            icon.className = isError
                ? 'material-symbols-outlined text-red-600 filled'
                : 'material-symbols-outlined text-green-600 filled';
        }
        if (pipelineCompleteTitle) {
            pipelineCompleteTitle.className = isError ? 'text-sm font-semibold text-red-800' : 'text-sm font-semibold text-green-800';
        }
        if (pipelineCompleteDesc) {
            pipelineCompleteDesc.className = isError ? 'text-xs text-red-600' : 'text-xs text-green-600';
        }
        pipelineComplete?.classList.remove('hidden');
    }

    function applyPipelineStatus(status, errorMessage, currentActivity, selectedPages) {
        const config = statusMap[status] || statusMap.pending;
        stepOrder.forEach((stepName, index) => {
            if (status === 'failed') {
                setStepState(stepName, index === stepOrder.length - 1 ? 'failed' : 'done');
                return;
            }
            if (index <= config.completed) {
                setStepState(stepName, 'done');
            } else if (index === config.active) {
                setStepState(stepName, 'active');
            } else {
                setStepState(stepName, 'idle');
            }
        });

        if (pipelineNote) {
            pipelineNote.className = status === 'failed' ? 'mb-4 text-xs text-red-500' : 'mb-4 text-xs text-slate-500';
            pipelineNote.textContent = errorMessage || config.note;
        }

        updateDynamicPanels(status, currentActivity, selectedPages);

        if (status === 'completed') {
            showCompletion('知识库构建完成', '公司资料已提交审核，管理员审核后将在目录中展示。', 'success');
            return true;
        }
        if (status === 'failed') {
            showCompletion('知识库构建失败', errorMessage || '本次分析未成功完成，请稍后重试。', 'error');
            return true;
        }
        return false;
    }

    async function pollPipeline(companyId, attempt = 0) {
        try {
            const status = await request(`/api/companies/${companyId}/pipeline-status`);
            const normalizedStatus = status.status || status.pipeline_status || 'pending';
            const normalizedError = status.error || status.pipeline_error || null;
            const done = applyPipelineStatus(
                normalizedStatus,
                normalizedError,
                status.current_activity || null,
                status.selected_pages || []
            );
            if (done) {
                clearPolling();
                if (startBtn) startBtn.disabled = false;
                return;
            }
        } catch (error) {
            if (attempt >= 10) {
                applyPipelineStatus('failed', error.message);
                if (startBtn) startBtn.disabled = false;
                return;
            }
            if (pipelineNote) {
                pipelineNote.className = 'mb-4 text-xs text-slate-500';
                pipelineNote.textContent = '状态同步稍有延迟，正在重试获取最新进度...';
            }
        }

        pollTimer = window.setTimeout(() => {
            pollPipeline(companyId, attempt + 1);
        }, 2000);
    }

    async function startPipeline() {
        const rawUrl = urlInput?.value?.trim();
        const url = normalizeUrlInput(rawUrl);
        if (!url) {
            urlInput?.focus();
            return;
        }
        if (urlInput) urlInput.value = url;

        if (startBtn) {
            startBtn.disabled = true;
            startBtn.textContent = '正在打开...';
        }

        const targetUrl = window.GEOrank?.Routes?.buildCompanySubmission
            ? window.GEOrank.Routes.buildCompanySubmission({ url })
            : `/submit-company?url=${encodeURIComponent(url)}`;

        const nextWindow = window.open(targetUrl, '_blank', 'noopener');
        if (!nextWindow) {
            window.location.href = targetUrl;
        }

        closeModal();
        if (startBtn) {
            startBtn.disabled = false;
            startBtn.textContent = '打开完整分析页';
        }
    }

    function markSubmitModalAutoOpen() {
        try {
            sessionStorage.setItem(AUTO_OPEN_FLAG, '1');
        } catch (_) {
            // Storage can be unavailable in restricted browsing modes.
        }
    }

    function consumeSubmitRouteSignal() {
        const current = new URL(window.location.href);
        const shouldOpen = current.searchParams.get('submit') === 'company'
            || current.hash === '#submit-company';
        if (!shouldOpen) return;

        markSubmitModalAutoOpen();
        const prefillUrl = normalizeUrlInput(current.searchParams.get('url') || '') || '';
        openModal(prefillUrl);

        current.searchParams.delete('submit');
        current.searchParams.delete('url');
        if (current.hash === '#submit-company') current.hash = '';
        window.history.replaceState(window.history.state, '', `${current.pathname}${current.search}${current.hash}`);
    }

    consumeSubmitRouteSignal();
});
