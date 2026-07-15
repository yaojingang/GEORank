/**
 * 提交公司完整分析页
 * - 新标签页展示完整 AI 分析过程
 * - 分析完成后由用户确认提交审核
 */
(function () {
    'use strict';

    const API_BASE = ['80', '443', ''].includes(window.location.port)
        ? ''
        : `${window.location.protocol}//${window.location.hostname}:8000`;

    const stepOrder = ['crawl', 'clean', 'graph', 'vector'];
    const statusMap = {
        pending: { active: 0, completed: -1, note: '已创建任务，等待进入官网解析队列。', activity: '正在创建分析任务并加入处理队列...' },
        crawling: { active: 0, completed: -1, note: '正在抓取官网首页和一级目录，AI 将锁定最值得深入的页面。', activity: '正在解析官网首页并识别一级目录链接...' },
        cleaning: { active: 1, completed: 0, note: '关键页面已锁定，正在抽取企业介绍、产品与团队信息。', activity: '正在整合关键页面内容并结构化抽取企业信息...' },
        graph_building: { active: 2, completed: 1, note: '结构化数据准备就绪，正在构建知识图谱。', activity: '正在构建实体关系与企业知识图谱...' },
        vectorizing: { active: 3, completed: 2, note: '知识图谱已生成，正在写入向量知识库。', activity: '正在将企业知识写入语义检索索引...' },
        completed: { active: -1, completed: 3, note: 'AI 分析完成，结果当前仍为草稿，点击提交审核后才会进入后台审核。', activity: '企业知识库构建完成，等待你确认提交审核。' },
        failed: { active: -1, completed: -1, note: '本次分析失败，可重新发起分析。', activity: '分析未成功完成。' },
    };

    const analysisUrl = document.getElementById('analysis-url');
    const analysisBadge = document.getElementById('analysis-badge');
    const analysisNote = document.getElementById('analysis-note');
    const analysisActivity = document.getElementById('analysis-activity');
    const analysisFeed = document.getElementById('analysis-feed');
    const selectedPagesPanel = document.getElementById('selected-pages-panel');
    const selectedPagesList = document.getElementById('selected-pages-list');
    const selectedPagesCount = document.getElementById('selected-pages-count');
    const companyPreviewCard = document.getElementById('company-preview-card');
    const previewCompanyName = document.getElementById('preview-company-name');
    const previewCompanySummary = document.getElementById('preview-company-summary');
    const reviewStatusTitle = document.getElementById('review-status-title');
    const reviewStatusCopy = document.getElementById('review-status-copy');
    const submitReviewBtn = document.getElementById('submit-review-btn');
    const openAdminReviewBtn = document.getElementById('open-admin-review-btn');
    const refreshAnalysisBtn = document.getElementById('refresh-analysis-btn');

    let pollTimer = null;
    let seenFeedKeys = new Set();
    let currentCompanyId = '';
    let currentNormalizedUrl = '';

    function getAuthToken() {
        return localStorage.getItem('georank_user_token')
            || localStorage.getItem('georank_token')
            || '';
    }

    async function request(path, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
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

    function normalizeUrlInput(raw) {
        const value = (raw || '').trim();
        if (!value) return '';
        const withProtocol = value.includes('://')
            ? value
            : value.startsWith('//')
                ? `https:${value}`
                : `https://${value}`;
        try {
            const parsed = new URL(withProtocol);
            if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname) {
                return '';
            }
            parsed.hash = '';
            parsed.search = '';
            if (parsed.pathname === '/') {
                parsed.pathname = '';
            }
            return parsed.toString().replace(/\/$/, '');
        } catch (_) {
            return '';
        }
    }

    function clearPolling() {
        if (pollTimer) {
            clearTimeout(pollTimer);
            pollTimer = null;
        }
    }

    function setStepState(stepName, state) {
        const stepEl = document.querySelector(`#analysis-steps [data-step="${stepName}"]`);
        if (!stepEl) return;
        const iconBg = stepEl.querySelector('.w-10');
        const iconEl = iconBg?.querySelector('.material-symbols-outlined');
        const statusIcon = stepEl.querySelector('.step-icon');

        if (!iconBg || !iconEl || !statusIcon) return;

        if (state === 'done') {
            iconBg.className = 'w-10 h-10 rounded-2xl bg-green-50 flex items-center justify-center shrink-0';
            iconEl.className = 'material-symbols-outlined text-green-600 text-lg';
            statusIcon.textContent = 'check_circle';
            statusIcon.className = 'material-symbols-outlined text-green-600 text-lg step-icon';
            return;
        }
        if (state === 'active') {
            iconBg.className = 'w-10 h-10 rounded-2xl bg-primary/10 flex items-center justify-center shrink-0';
            iconEl.className = 'material-symbols-outlined text-primary text-lg';
            statusIcon.textContent = 'progress_activity';
            statusIcon.className = 'material-symbols-outlined text-primary text-lg step-icon animate-spin';
            return;
        }
        if (state === 'failed') {
            iconBg.className = 'w-10 h-10 rounded-2xl bg-red-50 flex items-center justify-center shrink-0';
            iconEl.className = 'material-symbols-outlined text-red-500 text-lg';
            statusIcon.textContent = 'error';
            statusIcon.className = 'material-symbols-outlined text-red-500 text-lg step-icon';
            return;
        }

        iconBg.className = 'w-10 h-10 rounded-2xl bg-slate-100 flex items-center justify-center shrink-0';
        iconEl.className = 'material-symbols-outlined text-slate-400 text-lg';
        statusIcon.textContent = 'circle';
        statusIcon.className = 'material-symbols-outlined text-slate-300 text-lg step-icon';
    }

    function updateBadge(label, tone = 'idle') {
        const tones = {
            idle: ['bg-slate-100', 'text-slate-500', 'bg-slate-300'],
            active: ['bg-primary/10', 'text-primary', 'bg-primary'],
            success: ['bg-green-50', 'text-green-700', 'bg-green-500'],
            warning: ['bg-amber-50', 'text-amber-700', 'bg-amber-500'],
            error: ['bg-red-50', 'text-red-700', 'bg-red-500'],
        };
        const [badgeBg, badgeText, dotBg] = tones[tone] || tones.idle;
        analysisBadge.className = `inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold ${badgeBg} ${badgeText}`;
        analysisBadge.innerHTML = `<span class="w-2 h-2 rounded-full ${dotBg}"></span>${label}`;
    }

    function appendFeedItem(key, icon, text) {
        if (!analysisFeed || seenFeedKeys.has(key)) return;
        seenFeedKeys.add(key);
        const item = document.createElement('div');
        item.className = 'flex items-start gap-3 text-sm text-slate-500';
        item.innerHTML = `
            <span class="material-symbols-outlined text-base text-primary mt-0.5">${icon}</span>
            <span class="leading-6">${text}</span>
        `;
        analysisFeed.appendChild(item);
    }

    function updateReviewState(status, publishStatus) {
        if (openAdminReviewBtn) {
            openAdminReviewBtn.classList.add('hidden');
            if (currentCompanyId) {
                openAdminReviewBtn.href = `/admin/companies?company=${encodeURIComponent(currentCompanyId)}`;
            }
        }

        if (status === 'failed') {
            reviewStatusTitle.textContent = '分析失败';
            reviewStatusCopy.textContent = '本次官网解析未成功完成。你可以返回首页重新发起一轮分析。';
            submitReviewBtn.classList.add('hidden');
            return;
        }

        if (publishStatus === 'pending_review') {
            reviewStatusTitle.textContent = '已提交审核';
            reviewStatusCopy.textContent = '分析结果已经进入后台审核队列，审核通过后前台公司目录会自动展示。';
            submitReviewBtn.classList.add('hidden');
            openAdminReviewBtn?.classList.remove('hidden');
            updateBadge('审核中', 'warning');
            return;
        }

        if (publishStatus === 'published') {
            reviewStatusTitle.textContent = '已发布';
            reviewStatusCopy.textContent = '该公司已通过审核并在前台目录中展示。';
            submitReviewBtn.classList.add('hidden');
            openAdminReviewBtn?.classList.remove('hidden');
            updateBadge('已发布', 'success');
            return;
        }

        if (status === 'completed') {
            reviewStatusTitle.textContent = '等待你确认提交';
            reviewStatusCopy.textContent = 'AI 分析已经完成，但结果仍停留在草稿状态。点击下方按钮后才会进入后台审核。';
            submitReviewBtn.classList.remove('hidden');
            updateBadge('待提交', 'active');
            return;
        }

        reviewStatusTitle.textContent = '分析进行中';
        reviewStatusCopy.textContent = '系统正在处理官网内容并构建企业知识库，完成后你可以在这里一键提交审核。';
        submitReviewBtn.classList.add('hidden');
        updateBadge('分析中', 'active');
    }

    function renderSelectedPages(pages) {
        const selectedPages = Array.isArray(pages) ? pages.filter(Boolean) : [];
        if (!selectedPages.length) {
            selectedPagesPanel.classList.add('hidden');
            selectedPagesList.innerHTML = '';
            selectedPagesCount.textContent = '0 页';
            return;
        }

        selectedPagesPanel.classList.remove('hidden');
        selectedPagesCount.textContent = `${selectedPages.length} 页`;
        const roleMap = {
            homepage: '主页',
            about: '公司介绍',
            team: '团队页',
            product: '产品页',
            supporting: '补充页',
        };
        selectedPagesList.innerHTML = selectedPages.map((page, index) => {
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
                <article class="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                    <div class="flex items-start justify-between gap-4">
                        <div class="min-w-0">
                            <div class="flex items-center gap-2 mb-2">
                                <span class="inline-flex w-7 h-7 rounded-full bg-primary/10 text-primary text-xs font-bold items-center justify-center">${index + 1}</span>
                                <span class="text-xs font-semibold text-slate-400">${roleMap[page.role] || '关键页'}</span>
                            </div>
                            <h3 class="text-lg font-bold text-slate-900 break-all">${page.title || page.url}</h3>
                            <p class="mt-2 text-sm leading-6 text-slate-500">${page.reason || '该页面将参与企业知识库构建。'}</p>
                            <p class="mt-3 text-xs text-slate-400 break-all">${page.url}</p>
                        </div>
                        <span class="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${statusClass}">${statusText}</span>
                    </div>
                </article>
            `;
        }).join('');
    }

    function updateDynamicPanels(status, currentActivity, selectedPages) {
        const config = statusMap[status] || statusMap.pending;
        analysisActivity.textContent = currentActivity || config.activity || config.note;
        analysisNote.textContent = config.note;

        const statusFeed = {
            pending: ['queue', 'hourglass_empty', '已创建任务，等待进入官网解析队列。'],
            crawling: ['crawl', 'travel_explore', selectedPages?.length
                ? `AI 已锁定 ${selectedPages.length} 个关键页面，正在抓取内容。`
                : '已抓取官网首页，正在分析一级目录链接与标题。'],
            cleaning: ['clean', 'data_object', '已完成关键页抓取，正在提取企业信息与结构化摘要。'],
            graph_building: ['graph', 'hub', '正在梳理企业实体、产品能力与关系图谱。'],
            vectorizing: ['vector', 'neurology', '正在将知识内容写入语义索引，支持后续检索与推荐。'],
            completed: ['done', 'check_circle', '企业知识库构建完成，等待你确认提交审核。'],
            failed: ['failed', 'error', '本次分析失败，可重新发起分析。'],
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

    function applyPipelineStatus(payload) {
        const status = payload.status || 'pending';
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

        updateDynamicPanels(status, payload.current_activity || null, payload.selected_pages || []);
        updateReviewState(status, payload.publish_status);
    }

    async function loadCompanyPreview(companyId) {
        try {
            const data = await request(`/api/companies/${companyId}`);
            if (data.url) {
                analysisUrl.textContent = data.url;
            }
            companyPreviewCard.classList.remove('hidden');
            previewCompanyName.textContent = data.name || '企业名称待生成';
            previewCompanySummary.textContent = data.short_description
                || data.description
                || 'AI 已提炼出企业基础信息，可在提交审核后进入后台进一步检查与发布。';
        } catch (_) {
            // 忽略详情加载失败，不影响审核提交流程
        }
    }

    async function pollPipeline(companyId, attempt = 0) {
        try {
            const status = await request(`/api/companies/${companyId}/pipeline-status`);
            applyPipelineStatus(status);
            if (status.status === 'completed') {
                clearPolling();
                await loadCompanyPreview(companyId);
                return;
            }
            if (status.status === 'failed') {
                clearPolling();
                return;
            }
        } catch (error) {
            if (attempt >= 10) {
                applyPipelineStatus({
                    status: 'failed',
                    current_activity: error.message,
                    publish_status: 'draft',
                    selected_pages: [],
                });
                return;
            }
        }

        pollTimer = window.setTimeout(() => {
            pollPipeline(companyId, attempt + 1);
        }, 2000);
    }

    async function startOrResumeAnalysis() {
        const routeState = window.GEOrank?.Routes?.readCompanySubmissionState?.() || {};
        const incomingCompanyId = routeState.companyId || '';
        const incomingUrl = normalizeUrlInput(routeState.url || '');

        currentCompanyId = incomingCompanyId;
        currentNormalizedUrl = incomingUrl;

        if (incomingCompanyId) {
            if (analysisUrl) {
                analysisUrl.textContent = incomingUrl || '正在恢复分析记录...';
            }
            updateBadge('恢复中', 'active');
            if (!incomingUrl) {
                loadCompanyPreview(incomingCompanyId);
            }
            await pollPipeline(incomingCompanyId);
            return;
        }

        if (!incomingUrl) {
            analysisUrl.textContent = '未提供有效网址';
            updateBadge('参数缺失', 'error');
            analysisNote.textContent = '请从首页重新输入公司官网地址，再开启分析。';
            analysisActivity.textContent = '当前页面缺少可分析的官网地址。';
            reviewStatusTitle.textContent = '等待开始';
            reviewStatusCopy.textContent = '请返回首页，通过“提交公司”入口输入官网地址后开始分析。';
            return;
        }

        analysisUrl.textContent = incomingUrl;
        updateBadge('创建任务', 'active');
        appendFeedItem('startup', 'language', '正在创建官网分析任务。');

        const result = await request('/api/companies/submit', {
            method: 'POST',
            body: JSON.stringify({ url: incomingUrl }),
        });

        currentCompanyId = result.company_id;
        currentNormalizedUrl = result.normalized_url || incomingUrl;
        analysisUrl.textContent = currentNormalizedUrl;
        history.replaceState(
            {},
            '',
            window.GEOrank.Routes.buildCompanySubmission({
                url: currentNormalizedUrl,
                companyId: currentCompanyId,
            })
        );
        if (result.resumed) {
            appendFeedItem('resume', 'history', '检测到已有分析草稿，已为你恢复当前进度。');
        } else {
            appendFeedItem('created', 'hourglass_empty', '分析任务创建成功，正在同步实时进度。');
        }
        await pollPipeline(currentCompanyId);
    }

    async function submitForReview() {
        if (!currentCompanyId) return;
        submitReviewBtn.disabled = true;
        submitReviewBtn.textContent = '提交中...';
        try {
            await request(`/api/companies/${currentCompanyId}/submit-review`, {
                method: 'POST',
            });
            appendFeedItem('review-submitted', 'task_alt', '分析结果已提交后台审核，审核通过后将在前台目录中展示。');
            updateReviewState('completed', 'pending_review');
        } catch (error) {
            reviewStatusTitle.textContent = '提交审核失败';
            reviewStatusCopy.textContent = error.message || '请稍后重试。';
            submitReviewBtn.disabled = false;
            submitReviewBtn.textContent = '提交审核';
            updateBadge('提交失败', 'error');
        }
    }

    refreshAnalysisBtn?.addEventListener('click', () => {
        if (currentCompanyId) {
            pollPipeline(currentCompanyId);
        }
    });

    submitReviewBtn?.addEventListener('click', submitForReview);

    startOrResumeAnalysis().catch((error) => {
        analysisNote.textContent = error.message || '初始化分析页失败。';
        analysisActivity.textContent = '无法启动公司分析，请返回首页重试。';
        updateBadge('启动失败', 'error');
        reviewStatusTitle.textContent = '无法启动分析';
        reviewStatusCopy.textContent = error.message || '请返回首页重新发起分析。';
    });
})();
