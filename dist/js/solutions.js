/**
 * Solutions Page - GEO AI 问答交互
 */
(window.GEOrank?.PageLifecycle?.run?.bind(window.GEOrank.PageLifecycle)
    || ((callback) => callback()))(() => {
    'use strict';

    const API_BASE = '';
    const Routes = window.GEOrank?.Routes;
    const initialRouteState = Routes?.readSolutionState
        ? Routes.readSolutionState()
        : (() => {
            const params = new URLSearchParams(window.location.search);
            return {
                conversationId: params.get('conversation') || params.get('conversation_id') || '',
                diagnosticReportId: params.get('report') || params.get('report_id') || params.get('diagnostic_report_id') || '',
                companyId: params.get('company_id') || '',
                sourceUrl: params.get('url') || '',
                prompt: params.get('prompt') || '',
                channelKey: params.get('channel') || params.get('channel_key') || '',
            };
        })();
    const initialConversationId = initialRouteState.conversationId || '';
    const initialDiagnosticReportId = initialRouteState.diagnosticReportId || '';
    const initialCompanyId = initialRouteState.companyId || '';
    const initialUrl = initialRouteState.sourceUrl || '';
    const initialPrompt = initialRouteState.prompt || '';
    const initialChannelKey = initialRouteState.channelKey || '';
    const Auth = window.GEOrank?.Auth;

    const DEFAULT_QA_CHANNELS = {
        default_channel_key: 'geo-basics',
        channels: [
            {
                key: 'geo-basics',
                name: 'GEO 入门科普',
                description: '解释 GEO、AI 搜索、生成式答案引擎和品牌可见性的基础概念。',
                icon: 'school',
                enabled: true,
                sample_questions: [
                    'GEO 和 SEO 到底有什么区别？',
                    '为什么 AI 搜索会影响品牌获客？',
                    '一个新品牌应该先做哪些 GEO 基础动作？',
                ],
            },
            {
                key: 'diagnostic-explain',
                name: '诊断报告解读',
                description: '把 GEO 诊断分数、Schema、内容结构、Meta 和引用问题解释成可理解的行动建议。',
                icon: 'monitoring',
                enabled: true,
                sample_questions: [
                    '帮我解释这份 GEO 诊断报告里最重要的三个问题。',
                    'Schema 分低会怎样影响 AI 引用？',
                    '如果只能先修一个问题，应该先修什么？',
                ],
            },
            {
                key: 'content-structure',
                name: '内容结构优化',
                description: '围绕官网页面、教程、FAQ、案例和结构化答案，生成适合 AI 读取的内容建议。',
                icon: 'article',
                enabled: true,
                sample_questions: [
                    '一个 SaaS 官网首页怎样写更容易被 AI 摘要？',
                    '帮我设计一组适合 AI 搜索的 FAQ。',
                    '产品页应该如何增加可被引用的内容块？',
                ],
            },
            {
                key: 'brand-visibility',
                name: '品牌可见性问答',
                description: '回答品牌在 ChatGPT、Perplexity、Gemini 等 AI 答案中被理解、引用和推荐的问题。',
                icon: 'travel_explore',
                enabled: true,
                sample_questions: [
                    'AI 为什么没有推荐我的品牌？',
                    '如何让 AI 更准确理解我们的公司定位？',
                    '品牌引用和第三方提及应该怎么建设？',
                ],
            },
            {
                key: 'action-plan',
                name: '行动方案拆解',
                description: '把问答结论进一步拆成 30/60/90 天计划、任务优先级和团队分工。',
                icon: 'checklist',
                enabled: true,
                sample_questions: [
                    '给我一份 30/60/90 天 GEO 执行计划。',
                    '市场团队和内容团队应该如何分工做 GEO？',
                    '把上面的建议拆成下周可以开始做的任务。',
                ],
            },
        ],
    };

    const elements = {
        workspace: document.getElementById('solutions-workspace'),
        chatInput: document.getElementById('chat-input'),
        sendBtn: document.getElementById('send-btn'),
        chatMessages: document.getElementById('chat-messages'),
        newConversationBtn: document.getElementById('new-conversation-btn'),
        historyList: document.getElementById('history-list'),
        historyFooter: document.getElementById('history-footer'),
        historyEmpty: document.getElementById('history-empty'),
        statusNote: document.getElementById('chat-status-note'),
        contextBadge: document.getElementById('chat-context-badge'),
        inputHelper: document.getElementById('chat-input-helper'),
        exportWordBtn: document.getElementById('export-word-btn'),
        exportPdfBtn: document.getElementById('export-pdf-btn'),
        exportHtmlBtn: document.getElementById('export-html-btn'),
        feedbackHelpfulBtn: document.getElementById('feedback-helpful-btn'),
        feedbackRefineBtn: document.getElementById('feedback-refine-btn'),
        feedbackNote: document.getElementById('feedback-note'),
        channelList: document.getElementById('solution-channel-list'),
        promptGrid: document.getElementById('solution-prompt-grid'),
        channelBanner: document.getElementById('solution-channel-banner'),
        channelIcon: document.getElementById('solution-active-channel-icon'),
        channelEyebrow: document.getElementById('solution-active-channel-eyebrow'),
        channelTitle: document.getElementById('solution-active-channel-title'),
        channelCopy: document.getElementById('solution-active-channel-copy'),
        rightSidebar: document.getElementById('solutions-right-sidebar'),
        rightSidebarToggle: document.getElementById('right-sidebar-toggle'),
        rightSidebarToggleLabel: document.getElementById('right-sidebar-toggle-label'),
        metricPrimary: document.getElementById('solutions-metric-primary'),
        metricBar: document.getElementById('solutions-metric-bar'),
        metricPercent: document.getElementById('solutions-metric-percent'),
        metricSecondary: document.getElementById('solutions-metric-secondary'),
        metricTertiary: document.getElementById('solutions-metric-tertiary'),
    };

    const emptyStateTemplate = elements.chatMessages ? elements.chatMessages.innerHTML : '';

    const state = {
        token: getAuthToken(),
        isAuthenticated: Boolean(getAuthToken()),
        currentConversationId: initialConversationId,
        currentConversationOwnerId: null,
        diagnosticReportId: initialDiagnosticReportId,
        companyId: initialCompanyId,
        sourceUrl: initialUrl,
        prompt: initialPrompt,
        selectedChannelKey: initialChannelKey || DEFAULT_QA_CHANNELS.default_channel_key,
        defaultChannelKey: DEFAULT_QA_CHANNELS.default_channel_key,
        channels: DEFAULT_QA_CHANNELS.channels.slice(),
        contextReport: null,
        conversations: [],
        messages: [],
        conversationTitle: '',
        sending: false,
        sidebarCollapsed: localStorage.getItem('georank_solutions_sidebar_collapsed') === '1',
    };

    init()
        .catch((error) => {
            console.error('[solutions] init failed', error);
            setStatus(error.message || '问答页初始化失败，请稍后重试。', 'error');
        })
        .finally(finishInitialPresentation);

    async function init() {
        bindStaticEvents();
        document.addEventListener('georank:auth-changed', function (event) {
            state.token = getAuthToken();
            state.isAuthenticated = Boolean(state.token);
            if (state.isAuthenticated) {
                void loadHistory();
            } else {
                state.conversations = [];
                renderHistory();
            }
            updateInputHelper();
        });
        window.addEventListener('popstate', function () {
            void syncStateFromLocation({ announce: true });
        });
        if (state.prompt && elements.chatInput) {
            elements.chatInput.value = state.prompt;
            autoResizeInput();
        }

        const channelsChanged = await loadChannels();
        const reusePrerenderedFrame = canReusePrerenderedFrame(
            state,
            channelsChanged,
            DEFAULT_QA_CHANNELS.default_channel_key
        );
        if (!reusePrerenderedFrame) {
            renderChannels();
            renderHistory();
            renderMessages();
            updateContextBadge();
            updateMetrics();
            updateExportState();
            updateInputHelper();
        }
        applySidebarState();

        if (state.diagnosticReportId) {
            await loadDiagnosticContext();
        } else {
            renderContextBanner();
        }

        if (state.isAuthenticated) {
            await loadHistory();
        }

        if (state.currentConversationId) {
            await loadConversation(state.currentConversationId, { keepStatus: false });
        } else if (state.prompt) {
            setStatus('已载入预设提问，可直接发送给 AI 问答。');
        }
    }

    function bindStaticEvents() {
        if (elements.chatInput) {
            elements.chatInput.addEventListener('input', autoResizeInput);
            elements.chatInput.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void sendMessage();
                }
            });
        }

        elements.sendBtn?.addEventListener('click', function () {
            void sendMessage();
        });

        elements.newConversationBtn?.addEventListener('click', function () {
            resetConversation();
        });

        elements.historyList?.addEventListener('click', function (event) {
            const item = event.target.closest('[data-conversation-id]');
            if (!item) return;
            const conversationId = item.getAttribute('data-conversation-id');
            if (!conversationId || conversationId === state.currentConversationId) return;
            void loadConversation(conversationId);
        });

        elements.channelList?.addEventListener('click', function (event) {
            const item = event.target.closest('[data-solution-channel]');
            if (!item) return;
            const key = item.getAttribute('data-solution-channel');
            if (!key || key === state.selectedChannelKey) return;
            state.selectedChannelKey = key;
            localStorage.setItem('georank_solution_channel', key);
            renderChannels();
            renderMessages();
            updateContextBadge();
            updateLocation();
            setStatus(`已切换到「${getActiveChannel().name}」频道。`, 'success');
        });

        elements.chatMessages?.addEventListener('click', function (event) {
            const button = event.target.closest('[data-followup-prompt]');
            if (!button) return;
            const prompt = button.getAttribute('data-followup-prompt');
            if (!prompt) return;
            if (elements.chatInput) {
                elements.chatInput.value = prompt;
                autoResizeInput();
            }
            void sendMessage(prompt);
        });

        elements.historyFooter?.addEventListener('click', function (event) {
            const claimButton = event.target.closest('[data-solution-action="claim"]');
            if (claimButton) {
                void claimCurrentConversation();
                return;
            }

            const copyButton = event.target.closest('[data-solution-action="copy-link"]');
            if (copyButton) {
                void copyCurrentConversationLink();
            }
        });

        elements.exportPdfBtn?.addEventListener('click', function () {
            if (elements.exportPdfBtn.disabled) return;
            window.print();
        });

        elements.exportWordBtn?.addEventListener('click', function () {
            if (elements.exportWordBtn.disabled) return;
            downloadConversationDocument('word');
        });

        elements.exportHtmlBtn?.addEventListener('click', function () {
            if (elements.exportHtmlBtn.disabled) return;
            downloadConversationDocument('html');
        });

        elements.feedbackHelpfulBtn?.addEventListener('click', function () {
            if (elements.feedbackHelpfulBtn.disabled) return;
            setFeedback('已记录：当前回答有帮助，可继续深入追问执行动作。', 'success');
        });

        elements.feedbackRefineBtn?.addEventListener('click', function () {
            if (elements.feedbackRefineBtn.disabled) return;
            setFeedback('已记录：当前回答需要进一步细化，可继续追问补充行业、周期或目标。', 'info');
        });

        elements.rightSidebarToggle?.addEventListener('click', function () {
            state.sidebarCollapsed = !state.sidebarCollapsed;
            localStorage.setItem('georank_solutions_sidebar_collapsed', state.sidebarCollapsed ? '1' : '0');
            applySidebarState();
        });

        bindPromptCards();
    }

    function channelConfigSignature(channels, defaultChannelKey) {
        return JSON.stringify({
            defaultChannelKey,
            channels: channels.map((channel) => ({
                key: channel.key || '',
                name: channel.name || '',
                description: channel.description || '',
                icon: channel.icon || '',
                enabled: channel.enabled !== false,
                sampleQuestions: Array.isArray(channel.sample_questions) ? channel.sample_questions : [],
            })),
        });
    }

    function canReusePrerenderedFrame(currentState, channelsChanged, defaultChannelKey) {
        return !currentState.isAuthenticated
            && !currentState.currentConversationId
            && !currentState.diagnosticReportId
            && !currentState.companyId
            && !currentState.sourceUrl
            && !currentState.prompt
            && currentState.selectedChannelKey === defaultChannelKey
            && !channelsChanged;
    }

    async function loadChannels() {
        const previousSignature = channelConfigSignature(state.channels, state.defaultChannelKey);
        try {
            const data = await request('/api/solutions/channels');
            const channels = Array.isArray(data.channels) ? data.channels.filter((item) => item.enabled !== false) : [];
            state.channels = channels.length ? channels : DEFAULT_QA_CHANNELS.channels.slice();
            state.defaultChannelKey = data.default_channel_key || DEFAULT_QA_CHANNELS.default_channel_key;
        } catch (error) {
            console.warn('[solutions] load channels failed', error);
            state.channels = DEFAULT_QA_CHANNELS.channels.slice();
            state.defaultChannelKey = DEFAULT_QA_CHANNELS.default_channel_key;
        }

        if (!state.selectedChannelKey || !state.channels.some((channel) => channel.key === state.selectedChannelKey)) {
            state.selectedChannelKey = state.channels.some((channel) => channel.key === state.defaultChannelKey)
                ? state.defaultChannelKey
                : state.channels[0]?.key || 'geo-basics';
        }
        return channelConfigSignature(state.channels, state.defaultChannelKey) !== previousSignature;
    }

    function finishInitialPresentation() {
        const root = document.documentElement;
        root.classList.remove('solutions-sidebar-pref-collapsed');
        window.requestAnimationFrame(() => root.classList.remove('solutions-initializing'));
    }

    function getActiveChannel() {
        return state.channels.find((channel) => channel.key === state.selectedChannelKey)
            || state.channels.find((channel) => channel.key === state.defaultChannelKey)
            || state.channels[0]
            || DEFAULT_QA_CHANNELS.channels[0];
    }

    function renderChannels() {
        const active = getActiveChannel();
        if (elements.channelList) {
            elements.channelList.innerHTML = state.channels.map((channel) => {
                const isActive = channel.key === active.key;
                return `
                    <button
                        type="button"
                        data-solution-channel="${escapeHtml(channel.key)}"
                        class="${isActive ? 'border-primary/25 bg-primary/[0.04] text-primary shadow-sm' : 'border-slate-100 bg-white text-slate-600 hover:border-slate-200 hover:bg-slate-50'} w-full rounded-2xl border px-3 py-3 text-left transition-all"
                    >
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-base">${escapeHtml(channel.icon || 'forum')}</span>
                            <span class="text-sm font-bold">${escapeHtml(channel.name || '问答频道')}</span>
                        </div>
                        <p class="mt-1 line-clamp-2 text-[11px] leading-5 ${isActive ? 'text-primary/75' : 'text-slate-400'}">${escapeHtml(channel.description || '围绕 GEO 与 AI 搜索进行问答。')}</p>
                    </button>
                `;
            }).join('');
        }
        renderActiveChannelIntro();
    }

    function renderActiveChannelIntro() {
        elements.channelIcon = document.getElementById('solution-active-channel-icon') || elements.channelIcon;
        elements.channelEyebrow = document.getElementById('solution-active-channel-eyebrow') || elements.channelEyebrow;
        elements.channelTitle = document.getElementById('solution-active-channel-title') || elements.channelTitle;
        elements.channelCopy = document.getElementById('solution-active-channel-copy') || elements.channelCopy;
        elements.channelBanner = document.getElementById('solution-channel-banner') || elements.channelBanner;
        const channel = getActiveChannel();
        if (elements.channelIcon) elements.channelIcon.textContent = channel.icon || 'forum';
        if (elements.channelEyebrow) elements.channelEyebrow.textContent = 'GEO AI Q&A Channel';
        if (elements.channelTitle) elements.channelTitle.textContent = channel.name || 'AI 问答';
        if (elements.channelCopy) elements.channelCopy.textContent = channel.description || '围绕 GEO、AI 搜索和品牌可见性进行问答。';
        if (elements.channelBanner) {
            elements.channelBanner.innerHTML = `
                <div class="flex items-start gap-2">
                    <span class="material-symbols-outlined text-base text-primary">${escapeHtml(channel.icon || 'forum')}</span>
                    <div>
                        <p class="font-semibold">${escapeHtml(channel.name || 'AI 问答')}</p>
                        <p class="mt-1">${escapeHtml(channel.description || '当前频道会决定 AI 的回答范围、语气和推荐问题。')}</p>
                    </div>
                </div>
            `;
        }
        renderPromptCards();
    }

    function renderPromptCards() {
        elements.promptGrid = document.getElementById('solution-prompt-grid') || elements.promptGrid;
        if (!elements.promptGrid) return;
        const channel = getActiveChannel();
        const questions = Array.isArray(channel.sample_questions) && channel.sample_questions.length
            ? channel.sample_questions.slice(0, 3)
            : DEFAULT_QA_CHANNELS.channels[0].sample_questions;
        elements.promptGrid.innerHTML = questions.map((question, index) => `
            <button data-solution-prompt="${escapeHtml(question)}" class="solution-prompt-card rounded-2xl border border-slate-200 bg-white px-4 py-4 text-left transition-colors hover:border-primary/30 hover:bg-primary/[0.03]">
                <p class="text-[11px] font-extrabold uppercase tracking-[0.12em] text-slate-400">${escapeHtml(channel.name || '推荐问题')} ${index + 1}</p>
                <p class="mt-2 text-sm font-semibold text-slate-900">${escapeHtml(question)}</p>
            </button>
        `).join('');
        bindPromptCards();
    }

    function bindPromptCards() {
        document.querySelectorAll('[data-solution-prompt]').forEach((button) => {
            button.addEventListener('click', function () {
                const prompt = button.getAttribute('data-solution-prompt');
                if (!prompt) return;
                if (elements.chatInput) {
                    elements.chatInput.value = prompt;
                    autoResizeInput();
                    elements.chatInput.focus();
                }
                void sendMessage(prompt);
            });
        });
    }

    function autoResizeInput() {
        if (!elements.chatInput) return;
        elements.chatInput.style.height = 'auto';
        elements.chatInput.style.height = `${Math.min(elements.chatInput.scrollHeight, 156)}px`;
    }

    function getAuthToken() {
        return Auth?.getToken?.()
            || localStorage.getItem('georank_user_token')
            || localStorage.getItem('georank_token')
            || '';
    }

    async function request(path, options = {}) {
        const headers = {
            ...(options.body ? { 'Content-Type': 'application/json' } : {}),
            ...(window.GEOrank?.DeviceIdentity?.getHeaders?.() || {}),
            ...(options.headers || {}),
        };

        if (state.token) {
            headers.Authorization = `Bearer ${state.token}`;
        }

        const response = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers,
        });

        const raw = await response.text();
        let data = {};
        if (raw) {
            try {
                data = JSON.parse(raw);
            } catch (error) {
                throw new Error('问答接口返回了非 JSON 响应，请检查 /api 代理配置。');
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

    async function loadHistory() {
        try {
            const conversations = await request('/api/solutions/conversations');
            state.conversations = Array.isArray(conversations) ? conversations : [];
            renderHistory();
        } catch (error) {
            console.warn('[solutions] load history failed', error);
            state.token = '';
            state.isAuthenticated = false;
            state.conversations = [];
            renderHistory();
            setStatus('登录态不可用，当前以公开会话模式继续。');
        }
    }

    async function loadDiagnosticContext() {
        try {
            const report = await request(`/api/diagnostics/${encodeURIComponent(state.diagnosticReportId)}`);
            state.contextReport = report;
        } catch (error) {
            console.warn('[solutions] load diagnostic context failed', error);
            state.contextReport = null;
        }
        renderContextBanner();
        updateContextBadge();
        updateMetrics();
    }

    function whenDeferredDependenciesReady() {
        if (document.readyState === 'complete') return Promise.resolve();
        return new Promise((resolve) => {
            window.addEventListener('load', resolve, { once: true });
        });
    }

    async function loadConversation(conversationId, options = {}) {
        const { keepStatus = true } = options;
        try {
            await whenDeferredDependenciesReady();
            if (keepStatus) {
                setStatus('正在恢复问答会话...');
            }
            const detail = await request(`/api/solutions/conversations/${encodeURIComponent(conversationId)}`);
            state.currentConversationId = detail.id;
            state.conversationTitle = detail.title || '未命名对话';
            state.currentConversationOwnerId = detail.user_id || null;
            state.messages = Array.isArray(detail.messages) ? detail.messages : [];
            updateLocation();
            renderMessages();
            renderHistory();
            updateContextBadge();
            updateMetrics();
            updateExportState();
            updateInputHelper();
            if (keepStatus) {
                setStatus(`已恢复问答：${state.conversationTitle}`, 'success');
            }
        } catch (error) {
            console.error('[solutions] load conversation failed', error);
            resetConversation({ preserveInput: true, preserveStatus: false });
            setStatus(error.message || '当前问答会话不存在或无法访问。', 'error');
        }
    }

    async function sendMessage(overrideText) {
        if (Auth && !Auth.requireAuth({ reasonKey: 'auth.reasonSolutions' })) {
            return;
        }
        if (state.sending) return;
        const text = String(overrideText || elements.chatInput?.value || '').trim();
        if (!text) return;
        const hadConversationId = Boolean(state.currentConversationId);

        const previousMessages = state.messages.slice();
        const optimisticUserMessage = {
            id: `temp-user-${Date.now()}`,
            role: 'user',
            content: text,
            created_at: new Date().toISOString(),
            recommended_companies: [],
        };
        const optimisticAssistantMessage = {
            id: `temp-assistant-${Date.now()}`,
            role: 'assistant',
            content: '',
            created_at: new Date().toISOString(),
            recommended_companies: [],
            streaming: true,
        };

        state.sending = true;
        state.messages = previousMessages.concat(optimisticUserMessage, optimisticAssistantMessage);
        renderMessages();
        updateMetrics();
        updateExportState();
        updateInputHelper();
        setComposerLoading(true);
        setStatus('AI 正在回答，请稍候...');

        if (elements.chatInput) {
            elements.chatInput.value = '';
            autoResizeInput();
        }

        try {
            const payload = {
                message: text,
                conversation_id: state.currentConversationId || undefined,
                diagnostic_report_id: state.diagnosticReportId || undefined,
                channel_key: state.selectedChannelKey || undefined,
            };
            const streamResult = await streamChat(payload, optimisticAssistantMessage);

            optimisticAssistantMessage.streaming = false;
            optimisticAssistantMessage.created_at = new Date().toISOString();
            state.currentConversationId = streamResult.conversationId || state.currentConversationId;
            if (!hadConversationId && state.isAuthenticated) {
                state.currentConversationOwnerId = 'self';
            }
            state.messages = previousMessages.concat(optimisticUserMessage, optimisticAssistantMessage);
            state.conversationTitle = state.conversationTitle || text.slice(0, 30) || '未命名对话';
            state.prompt = '';
            updateLocation();
            renderMessages();
            updateContextBadge();
            updateMetrics();
            updateExportState();
            updateInputHelper();
            setFeedback('回答已生成，可导出、继续追问，或快速记录反馈。', 'info');
            setStatus('回答已更新。', 'success');

            if (state.isAuthenticated) {
                await loadHistory();
            } else {
                renderHistory();
            }
        } catch (error) {
            console.error('[solutions] send failed', error);
            state.messages = previousMessages;
            renderMessages();
            updateMetrics();
            updateExportState();
            updateInputHelper();
            setStatus(error.message || '生成回答失败，请稍后重试。', 'error');
            if (window.GEOrank?.APIKeyStore?.shouldPromptForError?.(error)) {
                window.GEOrank.APIKeyStore.openModal(error.message);
            }
        } finally {
            state.sending = false;
            setComposerLoading(false);
            updateInputHelper();
        }
    }

    async function streamChat(payload, assistantMessage) {
        const headers = {
            'Content-Type': 'application/json',
        };
        if (state.token) {
            headers.Authorization = `Bearer ${state.token}`;
        }
        Object.assign(headers, window.GEOrank?.APIKeyStore?.getHeaders?.() || {});

        const response = await fetch(`${API_BASE}/api/solutions/chat/stream`, {
            method: 'POST',
            headers,
            body: JSON.stringify(payload),
        });

        if (!response.ok || !response.body) {
            const raw = await response.text();
            let detail = `请求失败 (${response.status})`;
            if (raw) {
                try {
                    const parsed = JSON.parse(raw);
                    detail = formatApiError(parsed.detail, response.status) || detail;
                } catch (error) {
                    detail = raw;
                }
            }
            throw new Error(detail);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let conversationId = state.currentConversationId;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split('\n\n');
            buffer = events.pop() || '';

            for (const eventChunk of events) {
                const payloads = eventChunk
                    .split('\n')
                    .map((line) => line.trim())
                    .filter((line) => line.startsWith('data:'))
                    .map((line) => line.replace(/^data:\s*/, ''))
                    .filter(Boolean);

                for (const rawPayload of payloads) {
                    let event;
                    try {
                        event = JSON.parse(rawPayload);
                    } catch (error) {
                        continue;
                    }

                    if (event.type === 'text') {
                        assistantMessage.content += String(event.content || '');
                        renderMessages();
                        updateMetrics();
                        updateExportState();
                        continue;
                    }

                    if (event.type === 'companies') {
                        assistantMessage.recommended_companies = normalizeCompanies(event.content);
                        updateMetrics();
                        continue;
                    }

                    if (event.type === 'done') {
                        conversationId = event.conversation_id || conversationId;
                        continue;
                    }

                    if (event.type === 'error') {
                        throw new Error(event.content || '流式回答失败，请稍后重试。');
                    }
                }
            }
        }

        if (buffer.trim()) {
            const trailing = buffer
                .split('\n')
                .map((line) => line.trim())
                .find((line) => line.startsWith('data:'));
            if (trailing) {
                try {
                    const event = JSON.parse(trailing.replace(/^data:\s*/, ''));
                    if (event.type === 'done') {
                        conversationId = event.conversation_id || conversationId;
                    } else if (event.type === 'error') {
                        throw new Error(event.content || '流式回答失败，请稍后重试。');
                    }
                } catch (error) {
                    if (error instanceof Error) throw error;
                }
            }
        }

        if (!assistantMessage.content.trim()) {
            throw new Error('模型返回为空，请稍后重试。');
        }

        return { conversationId };
    }

    function resetConversation(options = {}) {
        const { preserveInput = false, preserveStatus = true } = options;
        state.currentConversationId = '';
        state.currentConversationOwnerId = null;
        state.messages = [];
        state.conversationTitle = '';
        updateLocation();
        renderMessages();
        renderHistory();
        updateContextBadge();
        updateMetrics();
        updateExportState();
        updateInputHelper();
        setFeedback('生成回答后可快速记录反馈。');

        if (!preserveInput && elements.chatInput) {
            elements.chatInput.value = '';
            autoResizeInput();
        }

        if (preserveStatus) {
            setStatus('已切换到新问答，可继续输入新的问题。', 'success');
        }
    }

    function renderHistory() {
        if (!elements.historyList) return;

        const items = [];
        if (state.isAuthenticated) {
            const needsSyntheticCurrent = state.currentConversationId
                && !state.conversations.some((conversation) => conversation.id === state.currentConversationId);

            if (needsSyntheticCurrent) {
                items.push(renderHistoryItem({
                    id: state.currentConversationId,
                    title: state.conversationTitle || '当前公开问答',
                    updated_at: new Date().toISOString(),
                }, true));
            }

            if (!state.conversations.length) {
                items.push(`
                    <div id="history-empty" class="rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 p-4 text-xs leading-relaxed text-slate-500">
                        暂无历史问答。发送一个问题后，会自动沉淀到你的会话历史中。
                    </div>
                `);
            } else {
                items.push(...state.conversations.map((conversation) => renderHistoryItem(conversation, conversation.id === state.currentConversationId)));
            }
        } else if (state.currentConversationId) {
            items.push(renderHistoryItem({
                id: state.currentConversationId,
                title: state.conversationTitle || '当前公开问答',
                updated_at: new Date().toISOString(),
            }, true));
            items.push(`
                <div class="rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 p-4 text-xs leading-relaxed text-slate-500">
                    当前会话已写入公开链接。复制当前页面地址即可继续这次问答。
                </div>
            `);
        } else {
            items.push(`
                <div id="history-empty" class="rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 p-4 text-xs leading-relaxed text-slate-500">
                    登录后可查看完整历史问答。未登录时，当前问答会通过地址栏链接保留。
                </div>
            `);
        }

        elements.historyList.innerHTML = items.join('');

        if (elements.historyFooter) {
            elements.historyFooter.innerHTML = buildHistoryFooter();
        }
    }

    function buildHistoryFooter() {
        const shouldShowClaim = canClaimCurrentConversation();
        const shouldShowCopy = Boolean(state.currentConversationId);
        const infoCopy = state.isAuthenticated
            ? (
                shouldShowClaim
                    ? '当前正在查看公开问答。认领后会进入你的历史，后续追问也会继续沉淀。'
                    : state.currentConversationId
                        ? '历史会话会自动按最近更新时间排序。当前问答已经可以继续追问，也可以复制公开链接分享给团队。'
                        : '登录后生成的问答会自动沉淀到你的历史。点击任一记录可恢复完整上下文。'
            )
            : (
                state.currentConversationId
                    ? '当前问答已生成公开链接。复制当前页面地址即可继续对话，登录后也可以把它保存到个人历史。'
                    : '当前支持公开问答会话。生成后会自动写入可分享的公开链接。'
            );

        const actions = [];
        if (shouldShowClaim) {
            actions.push(`
                <button
                    type="button"
                    data-solution-action="claim"
                    class="flex w-full items-center justify-center gap-2 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-xs font-semibold text-blue-700 transition-colors hover:border-blue-200 hover:bg-blue-100"
                >
                    <span class="material-symbols-outlined text-sm">bookmark_add</span>
                    保存当前公开问答到我的历史
                </button>
            `);
        }
        if (shouldShowCopy) {
            actions.push(`
                <button
                    type="button"
                    data-solution-action="copy-link"
                    class="flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs font-semibold text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50"
                >
                    <span class="material-symbols-outlined text-sm">content_copy</span>
                    复制当前公开链接
                </button>
            `);
        }

        return `
            <div class="space-y-3">
                <div class="rounded-2xl bg-slate-50 px-4 py-3 text-[11px] leading-relaxed text-slate-500">
                    ${escapeHtml(infoCopy)}
                </div>
                ${actions.join('')}
            </div>
        `;
    }

    function renderHistoryItem(conversation, active) {
        const dateLabel = formatHistoryTime(conversation.updated_at || conversation.created_at);
        return `
            <button
                type="button"
                data-conversation-id="${escapeHtml(conversation.id)}"
                class="${active ? 'active border border-primary/20 bg-primary/[0.03] shadow-sm' : 'border border-transparent hover:border-slate-200 hover:bg-slate-50'} block w-full rounded-2xl px-4 py-4 text-left transition-all"
            >
                <div class="flex items-start justify-between gap-3">
                    <p class="line-clamp-2 text-sm font-semibold text-slate-900">${escapeHtml(conversation.title || '未命名对话')}</p>
                    <span class="shrink-0 text-[11px] font-medium text-slate-400">${escapeHtml(dateLabel)}</span>
                </div>
                <p class="mt-2 text-[11px] leading-5 text-slate-500">
                    ${active ? '当前会话' : '点击恢复此问答上下文'}
                </p>
            </button>
        `;
    }

    function renderMessages() {
        if (!elements.chatMessages) return;

        if (!state.messages.length) {
            elements.chatMessages.innerHTML = emptyStateTemplate;
            bindPromptCards();
            renderActiveChannelIntro();
            renderContextBanner();
            scrollMessagesToTop();
            return;
        }

        const contextPanel = buildContextPanel();
        const messageHtml = state.messages.map((message, index) => renderMessageBubble(message, index)).join('');
        elements.chatMessages.innerHTML = `${contextPanel}${messageHtml}`;
        scrollMessagesToBottom();
    }

    function renderMessageBubble(message, index) {
        const role = String(message.role || '').toLowerCase();
        if (role === 'assistant') {
            const followUps = buildFollowUpPrompts(message, index);
            return `
                <div class="flex justify-start">
                <div class="w-full rounded-[1.75rem] rounded-tl-none border border-slate-100 bg-white p-5 shadow-[0_16px_48px_rgba(15,23,42,0.05)]">
                        <div class="mb-3 flex items-center gap-2">
                            <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-white">
                                <span class="material-symbols-outlined filled text-sm">psychology</span>
                            </div>
                            <span class="text-[11px] font-extrabold uppercase tracking-[0.14em] text-primary">GEO AI</span>
                            ${message.streaming ? '<span class="solution-stream-badge" aria-label="AI 正在回答"><span></span><span></span><span></span></span>' : ''}
                            <span class="text-[11px] text-slate-400">${escapeHtml(formatMessageTime(message.created_at))}</span>
                        </div>
                        <div class="solution-markdown${message.streaming ? ' solution-markdown--streaming' : ''}">
                            ${message.content ? renderMarkdown(message.content) : renderStreamingPlaceholder()}
                        </div>
                        ${!message.streaming && followUps.length ? renderFollowUpQuestions(followUps) : ''}
                    </div>
                </div>
            `;
        }

        return `
            <div class="flex justify-end">
                <div class="w-full md:w-[98%] rounded-[1.75rem] rounded-tr-none border border-slate-100 bg-white p-4 shadow-[0_16px_40px_rgba(15,23,42,0.04)]">
                    <p class="text-sm leading-7 text-slate-800">${renderInlineBreaks(message.content)}</p>
                    <p class="mt-2 text-right text-[11px] text-slate-400">${escapeHtml(formatMessageTime(message.created_at))}</p>
                </div>
            </div>
        `;
    }

    function buildFollowUpPrompts(message, index) {
        const prompts = [];
        const sourceMessages = state.messages.slice(0, typeof index === 'number' ? index : state.messages.length);
        const latestUserMessage = [...sourceMessages]
            .reverse()
            .find((item) => String(item.role || '').toLowerCase() === 'user');
        const latestUserText = String(latestUserMessage?.content || '').trim();
        const baseTopic = latestUserText ? latestUserText.slice(0, 28) : '当前目标';
        const companies = normalizeCompanies(message.recommended_companies);

        prompts.push({
            label: '拆成执行清单',
            prompt: `基于刚才关于“${baseTopic}”的回答，拆成 30/60/90 天执行清单，并标注优先级和负责人建议。`,
            icon: 'checklist',
        });

        prompts.push({
            label: companies.length ? '推荐相关公司' : '匹配合作公司',
            prompt: `基于前面的对话语义和当前目标，推荐 2-3 家相关公司，并说明各自更适合负责什么环节。`,
            icon: 'hub',
        });

        return prompts;
    }

    function renderFollowUpQuestions(items) {
        return `
            <div class="solution-followups">
                ${items.map((item) => `
                    <button
                        type="button"
                        data-followup-prompt="${escapeHtml(item.prompt)}"
                        class="solution-followup-chip"
                    >
                        <span class="material-symbols-outlined">${escapeHtml(item.icon || 'help')}</span>
                        <span>${escapeHtml(item.label)}</span>
                    </button>
                `).join('')}
            </div>
        `;
    }

    function renderStreamingPlaceholder() {
        return `
            <div class="solution-stream-skeleton" aria-label="AI 正在回答中">
                <span class="solution-stream-skeleton__line solution-stream-skeleton__line--long"></span>
                <span class="solution-stream-skeleton__line solution-stream-skeleton__line--mid"></span>
                <span class="solution-stream-skeleton__line solution-stream-skeleton__line--short"></span>
            </div>
        `;
    }

    function buildContextPanel() {
        const lines = [];
        if (state.contextReport?.url) {
            const scoreText = state.contextReport.overall_score != null
                ? `，当前评分 ${Math.round(Number(state.contextReport.overall_score))}/100`
                : '';
            lines.push(`已接入诊断报告：${state.contextReport.url}${scoreText}`);
        } else if (state.diagnosticReportId) {
            lines.push(`已附加诊断上下文：报告 ${state.diagnosticReportId.slice(0, 8)}`);
        }

        if (state.companyId) {
            lines.push(`关联公司：${state.companyId.slice(0, 8)}`);
        }

        if (state.sourceUrl && !state.contextReport?.url) {
            lines.push(`来源页面：${state.sourceUrl}`);
        }

        if (!lines.length) return '';

        return `
            <div class="mb-6 rounded-[1.5rem] border border-blue-100 bg-blue-50/70 px-5 py-4 text-sm leading-6 text-blue-900">
                <div class="flex items-center gap-2 text-[11px] font-extrabold uppercase tracking-[0.14em] text-blue-700">
                    <span class="material-symbols-outlined filled text-base">approval_delegation</span>
                    问答上下文
                </div>
                <div class="mt-2 space-y-1">
                    ${lines.map((line) => `<p>${escapeHtml(line)}</p>`).join('')}
                </div>
            </div>
        `;
    }

    function renderContextBanner() {
        const banner = document.getElementById('solution-context-banner');
        if (!banner) return;

        const lines = [];
        if (state.contextReport?.url) {
            const score = state.contextReport.overall_score != null
                ? `，当前 GEO 评分 ${Math.round(Number(state.contextReport.overall_score))}/100`
                : '';
            lines.push(`已附加诊断报告：${state.contextReport.url}${score}`);
        } else if (state.diagnosticReportId) {
            lines.push(`当前链接已携带诊断报告 ${state.diagnosticReportId.slice(0, 8)}，发送后会自动作为问答上下文。`);
        }

        if (state.companyId) {
            lines.push(`当前链接已关联公司 ${state.companyId.slice(0, 8)}。`);
        }

        if (state.sourceUrl && !state.contextReport?.url) {
            lines.push(`来源页面：${state.sourceUrl}`);
        }

        if (!lines.length) {
            banner.classList.add('hidden');
            banner.textContent = '';
            return;
        }

        banner.classList.remove('hidden');
        banner.innerHTML = lines.map((line) => `<p>${escapeHtml(line)}</p>`).join('');
    }

    function renderRecommendedCompanies(companies) {
        return `
            <div class="mt-5 rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
                <div class="mb-3 flex items-center justify-between gap-3">
                    <p class="text-[11px] font-extrabold uppercase tracking-[0.12em] text-slate-500">关联公司</p>
                    <p class="text-[11px] text-slate-400">${companies.length} 家匹配</p>
                </div>
                <div class="grid gap-3 md:grid-cols-2">
                    ${companies.map(renderCompanyCard).join('')}
                </div>
            </div>
        `;
    }

    function applySidebarState() {
        if (!elements.workspace || !elements.rightSidebarToggleLabel || !elements.rightSidebarToggle) return;
        elements.workspace.classList.toggle('solutions-workspace--sidebar-collapsed', state.sidebarCollapsed);
        elements.rightSidebarToggleLabel.textContent = state.sidebarCollapsed ? '展开侧栏' : '收起侧栏';
        const icon = elements.rightSidebarToggle.querySelector('.material-symbols-outlined');
        if (icon) {
            icon.textContent = state.sidebarCollapsed ? 'right_panel_open' : 'right_panel_close';
        }
    }

    function renderCompanyCard(company) {
        const companyId = company.id || company.company_id || '';
        const href = buildCompanyLink(company.path_key || companyId);
        const score = toFiniteNumber(company.geo_score);
        const matchScore = toFiniteNumber(company.match_score);
        const logo = company.logo_url
            ? `<img alt="${escapeHtml(company.name || 'Company')} logo" src="${escapeHtml(company.logo_url)}" class="h-10 w-10 rounded-xl border border-slate-100 object-cover bg-white">`
            : `
                <div class="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-100 bg-white text-sm font-extrabold text-primary">
                    ${escapeHtml((company.name || '?').slice(0, 1).toUpperCase())}
                </div>
            `;

        const detailChips = [];
        if (score != null) detailChips.push(`GEO ${Math.round(score)}`);
        if (matchScore != null) detailChips.push(`匹配度 ${Math.round(matchScore * 100)}%`);
        if (company.category) detailChips.push(company.category);

        return `
            <a href="${escapeHtml(href)}" class="group rounded-2xl border border-slate-200 bg-white p-4 transition-all hover:border-primary/30 hover:bg-white hover:shadow-[0_18px_40px_rgba(37,99,235,0.12)]">
                <div class="flex items-start gap-3">
                    ${logo}
                    <div class="min-w-0 flex-1">
                        <div class="flex items-center gap-2">
                            <p class="truncate text-sm font-semibold text-slate-900 group-hover:text-primary">${escapeHtml(company.name || '未命名公司')}</p>
                            <span class="material-symbols-outlined text-sm text-slate-300 group-hover:text-primary">north_east</span>
                        </div>
                        <p class="mt-1 line-clamp-2 text-[12px] leading-5 text-slate-500">${escapeHtml(company.short_description || '查看该公司详情与 GEO 能力画像。')}</p>
                    </div>
                </div>
                ${detailChips.length ? `
                    <div class="mt-3 flex flex-wrap gap-2">
                        ${detailChips.map((chip) => `<span class="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-500">${escapeHtml(chip)}</span>`).join('')}
                    </div>
                ` : ''}
            </a>
        `;
    }

    function normalizeCompanies(value) {
        if (Array.isArray(value)) return value;
        if (value && Array.isArray(value.items)) return value.items;
        return [];
    }

    function renderMarkdown(text) {
        const source = String(text || '').trim();
        if (!source) {
            return '<p class="text-slate-500">本次返回没有正文内容，建议继续追问以补充执行细节。</p>';
        }

        const normalized = source.replace(/\r\n/g, '\n');
        const markedApi = window.marked;
        const purifier = window.DOMPurify;

        if (!markedApi?.parse || !purifier?.sanitize) {
            return `<p>${renderInlineBreaks(normalized)}</p>`;
        }

        markedApi.setOptions({
            gfm: true,
            breaks: true,
            headerIds: false,
            mangle: false,
        });

        const rawHtml = markedApi.parse(normalized);
        return purifier.sanitize(rawHtml, {
            USE_PROFILES: { html: true },
        });
    }

    function renderInlineBreaks(text) {
        return escapeHtml(text).replace(/\n/g, '<br>');
    }

    function updateContextBadge() {
        if (!elements.contextBadge) return;

        const labels = [];
        labels.push(state.isAuthenticated ? '已登录' : '公开会话');
        if (state.diagnosticReportId) labels.push('诊断上下文');
        if (state.currentConversationId) {
            labels.push(canClaimCurrentConversation() ? '公开链接' : '会话已保存');
        }
        if (canClaimCurrentConversation()) labels.push('待认领');
        elements.contextBadge.textContent = labels.join(' · ');
    }

    function updateInputHelper() {
        if (!elements.inputHelper) return;
        elements.inputHelper.textContent = '';
    }

    function updateMetrics() {
        const latestAssistant = [...state.messages].reverse().find((message) => String(message.role).toLowerCase() === 'assistant');
        const recommendedCompanies = latestAssistant ? normalizeCompanies(latestAssistant.recommended_companies) : [];
        const scores = recommendedCompanies
            .map((company) => toFiniteNumber(company.geo_score))
            .filter((score) => score != null);
        const averageScore = scores.length
            ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length)
            : null;
        const strength = latestAssistant
            ? Math.min(
                96,
                18
                    + Math.min(Math.round(String(latestAssistant.content || '').length / 12), 30)
                    + Math.min(recommendedCompanies.length * 14, 36)
                    + (state.diagnosticReportId ? 18 : 0)
            )
            : (state.diagnosticReportId ? 20 : 8);

        if (elements.metricPrimary) {
            elements.metricPrimary.textContent = latestAssistant ? `${strength} / 100` : '待回答';
        }
        if (elements.metricBar) {
            elements.metricBar.style.width = `${strength}%`;
        }
        if (elements.metricPercent) {
            elements.metricPercent.textContent = `${strength}%`;
        }
        if (elements.metricSecondary) {
            elements.metricSecondary.textContent = `关联公司：${recommendedCompanies.length} 家`;
        }
        if (elements.metricTertiary) {
            if (averageScore != null) {
                elements.metricTertiary.textContent = `平均 GEO 评分：${averageScore}`;
            } else {
                elements.metricTertiary.textContent = `诊断上下文：${state.diagnosticReportId ? '已接入' : '未接入'}`;
            }
        }
    }

    function updateExportState() {
        const hasAssistant = state.messages.some((message) => String(message.role).toLowerCase() === 'assistant');
        [elements.exportWordBtn, elements.exportPdfBtn, elements.exportHtmlBtn, elements.feedbackHelpfulBtn, elements.feedbackRefineBtn]
            .forEach((button) => {
                if (button) button.disabled = !hasAssistant;
            });
    }

    function setComposerLoading(loading) {
        if (!elements.sendBtn) return;
        elements.sendBtn.disabled = loading;
        elements.sendBtn.innerHTML = loading
            ? '<span class="material-symbols-outlined animate-spin text-sm">progress_activity</span><span class="text-sm font-bold hidden sm:inline">回答中</span>'
            : '<span class="text-sm font-bold hidden sm:inline">发送</span><span class="material-symbols-outlined text-sm">send</span>';
    }

    function setStatus(message, tone = 'info') {
        if (!elements.statusNote) return;
        if (!message) {
            elements.statusNote.classList.add('hidden');
            elements.statusNote.textContent = '';
            return;
        }
        elements.statusNote.classList.remove('hidden', 'text-slate-500', 'text-red-500', 'text-green-600');
        elements.statusNote.classList.add(
            tone === 'error'
                ? 'text-red-500'
                : tone === 'success'
                    ? 'text-green-600'
                    : 'text-slate-500'
        );
        elements.statusNote.textContent = message;
    }

    function setFeedback(message, tone = 'idle') {
        if (!elements.feedbackNote) return;
        elements.feedbackNote.classList.remove('text-slate-400', 'text-green-600', 'text-primary');
        elements.feedbackNote.classList.add(
            tone === 'success'
                ? 'text-green-600'
                : tone === 'info'
                    ? 'text-primary'
                    : 'text-slate-400'
        );
        elements.feedbackNote.textContent = message;
    }

    function updateLocation() {
        if (Routes?.buildSolutionPath) {
            window.history.replaceState(
                { conversationId: state.currentConversationId },
                '',
                Routes.buildSolutionPath({
                    conversationId: state.currentConversationId,
                    diagnosticReportId: state.diagnosticReportId,
                    companyId: state.companyId,
                    url: state.sourceUrl,
                    prompt: state.prompt && !state.currentConversationId && !state.messages.length ? state.prompt : '',
                    channelKey: state.selectedChannelKey,
                })
            );
            return;
        }

        const next = new URL(window.location.href);
        if (state.currentConversationId) {
            next.searchParams.set('conversation', state.currentConversationId);
        } else {
            next.searchParams.delete('conversation');
            next.searchParams.delete('conversation_id');
        }
        if (state.diagnosticReportId) {
            next.searchParams.set('report', state.diagnosticReportId);
        }
        if (state.companyId) {
            next.searchParams.set('company_id', state.companyId);
        }
        if (state.sourceUrl) {
            next.searchParams.set('url', state.sourceUrl);
        }
        if (state.prompt && !state.currentConversationId && !state.messages.length) {
            next.searchParams.set('prompt', state.prompt);
        } else {
            next.searchParams.delete('prompt');
        }
        if (state.selectedChannelKey) {
            next.searchParams.set('channel', state.selectedChannelKey);
        } else {
            next.searchParams.delete('channel');
            next.searchParams.delete('channel_key');
        }
        window.history.replaceState({ conversationId: state.currentConversationId }, '', next.toString());
    }

    function canClaimCurrentConversation() {
        return Boolean(
            state.isAuthenticated
            && state.currentConversationId
            && !state.currentConversationOwnerId
        );
    }

    async function claimCurrentConversation() {
        if (!canClaimCurrentConversation()) return;
        try {
            const payload = await request(`/api/solutions/conversations/${encodeURIComponent(state.currentConversationId)}/claim`, {
                method: 'POST',
            });
            state.currentConversationOwnerId = state.currentConversationOwnerId || 'claimed';
            await loadHistory();
            renderHistory();
            updateContextBadge();
            setStatus(
                payload.status === 'already_owned'
                    ? '当前问答已经在你的历史记录中。'
                    : '已将当前公开问答保存到你的历史记录。',
                'success'
            );
        } catch (error) {
            console.error('[solutions] claim failed', error);
            setStatus(error.message || '保存当前问答失败，请稍后重试。', 'error');
        }
    }

    function readLocationState() {
        if (Routes?.readSolutionState) {
            return Routes.readSolutionState();
        }
        const nextParams = new URLSearchParams(window.location.search);
        return {
            conversationId: nextParams.get('conversation') || nextParams.get('conversation_id') || '',
            diagnosticReportId: nextParams.get('report') || nextParams.get('report_id') || nextParams.get('diagnostic_report_id') || '',
            companyId: nextParams.get('company_id') || '',
            sourceUrl: nextParams.get('url') || '',
            prompt: nextParams.get('prompt') || '',
            channelKey: nextParams.get('channel') || nextParams.get('channel_key') || '',
        };
    }

    async function syncStateFromLocation(options = {}) {
        const { announce = false } = options;
        const nextState = readLocationState();
        const previousConversationId = state.currentConversationId;
        const previousReportId = state.diagnosticReportId;

        state.diagnosticReportId = nextState.diagnosticReportId;
        state.companyId = nextState.companyId;
        state.sourceUrl = nextState.sourceUrl;
        state.prompt = nextState.prompt;
        if (nextState.channelKey && state.channels.some((channel) => channel.key === nextState.channelKey)) {
            state.selectedChannelKey = nextState.channelKey;
            localStorage.setItem('georank_solution_channel', nextState.channelKey);
            renderChannels();
        }

        if (elements.chatInput && !nextState.conversationId) {
            elements.chatInput.value = state.prompt || '';
            autoResizeInput();
        }

        if (previousReportId !== state.diagnosticReportId) {
            if (state.diagnosticReportId) {
                await loadDiagnosticContext();
            } else {
                state.contextReport = null;
                renderContextBanner();
                updateContextBadge();
                updateMetrics();
            }
        } else {
            renderContextBanner();
        }

        if (nextState.conversationId !== previousConversationId) {
            if (nextState.conversationId) {
                await loadConversation(nextState.conversationId, { keepStatus: false });
            } else {
                resetConversation({ preserveInput: true, preserveStatus: false });
            }
        } else {
            renderHistory();
            updateContextBadge();
            updateMetrics();
            updateExportState();
            updateInputHelper();
        }

        if (announce) {
            setStatus('已根据页面地址恢复问答上下文。', 'success');
        }
    }

    async function copyCurrentConversationLink() {
        const href = window.location.href;
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(href);
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = href;
                textarea.setAttribute('readonly', 'readonly');
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                textarea.remove();
            }
            setStatus('当前问答链接已复制。', 'success');
            setFeedback('已复制当前公开链接，可直接发给团队继续查看。', 'success');
        } catch (error) {
            console.error('[solutions] copy link failed', error);
            setStatus('复制链接失败，请手动复制当前地址。', 'error');
        }
    }

    function formatHistoryTime(value) {
        const date = value ? new Date(value) : null;
        if (!date || Number.isNaN(date.getTime())) return '--';

        const now = new Date();
        const diff = now.getTime() - date.getTime();
        if (diff < 60 * 60 * 1000) {
            const minutes = Math.max(1, Math.round(diff / (60 * 1000)));
            return `${minutes} 分钟前`;
        }
        if (diff < 24 * 60 * 60 * 1000) {
            return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(date);
        }
        return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' }).format(date);
    }

    function formatMessageTime(value) {
        const date = value ? new Date(value) : null;
        if (!date || Number.isNaN(date.getTime())) return '刚刚';
        return new Intl.DateTimeFormat('zh-CN', {
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        }).format(date);
    }

    function buildCompanyLink(companyIdentifier) {
        if (Routes?.buildCompanyDetail) {
            return Routes.buildCompanyDetail(companyIdentifier);
        }
        const url = new URL('/company', window.location.origin);
        if (companyIdentifier) url.searchParams.set('id', companyIdentifier);
        return url.toString();
    }

    function downloadConversationDocument(format) {
        const html = buildExportHtml();
        const safeTitle = (state.conversationTitle || 'GEO问答').replace(/[\\/:*?"<>|]+/g, '-');
        const mimeType = format === 'word' ? 'application/msword' : 'text/html';
        const extension = format === 'word' ? 'doc' : 'html';
        const blob = new Blob([html], { type: `${mimeType};charset=utf-8` });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${safeTitle}.${extension}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        setFeedback(format === 'word' ? '已导出 Word 文档。' : '已导出 HTML 问答摘要。', 'success');
    }

    function buildExportHtml() {
        const assistantMessages = state.messages.filter((message) => String(message.role).toLowerCase() === 'assistant');
        const latestAssistant = assistantMessages[assistantMessages.length - 1];
        const recommendedCompanies = latestAssistant ? normalizeCompanies(latestAssistant.recommended_companies) : [];
        const transcript = state.messages.map((message) => `
            <section style="margin: 0 0 24px;">
                <h3 style="margin: 0 0 8px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.12em; color: ${String(message.role).toLowerCase() === 'assistant' ? '#2563eb' : '#0f172a'};">
                    ${String(message.role).toLowerCase() === 'assistant' ? 'GEO AI' : '用户'}
                </h3>
                <div class="solution-export-markdown" style="font-size: 15px; line-height: 1.9; color: #334155;">
                    ${String(message.role).toLowerCase() === 'assistant' ? renderMarkdown(message.content || '') : renderInlineBreaks(message.content || '')}
                </div>
            </section>
        `).join('');

        const companySection = recommendedCompanies.length
            ? `
                <section style="margin-top: 28px;">
                    <h2 style="font-size: 18px; margin: 0 0 14px;">关联公司</h2>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px;">
                        ${recommendedCompanies.map((company) => `
                            <article style="padding: 16px; border: 1px solid #e2e8f0; border-radius: 18px; background: #ffffff;">
                                <h3 style="margin: 0 0 6px; font-size: 16px; color: #0f172a;">${escapeHtml(company.name || '未命名公司')}</h3>
                                <p style="margin: 0 0 8px; font-size: 13px; line-height: 1.7; color: #64748b;">${escapeHtml(company.short_description || '查看公司详情以获取更多 GEO 能力信息。')}</p>
                                <p style="margin: 0; font-size: 12px; color: #2563eb;">${escapeHtml(company.category || '')}${company.geo_score != null ? ` · GEO ${Math.round(Number(company.geo_score))}` : ''}</p>
                            </article>
                        `).join('')}
                    </div>
                </section>
            `
            : '';

        return `
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="utf-8">
                <title>${escapeHtml(state.conversationTitle || 'GEO问答')}</title>
                <style>
                    body { margin: 40px auto; max-width: 960px; font-family: Inter, -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif; color: #0f172a; }
                    .solution-export-markdown h1, .solution-export-markdown h2, .solution-export-markdown h3, .solution-export-markdown h4 {
                        margin: 1.5em 0 0.7em;
                        color: #0f172a;
                        font-family: Manrope, Inter, sans-serif;
                        font-weight: 800;
                        letter-spacing: -0.02em;
                        line-height: 1.3;
                    }
                    .solution-export-markdown h1 { font-size: 1.7rem; }
                    .solution-export-markdown h2 { font-size: 1.35rem; }
                    .solution-export-markdown h3 { font-size: 1.08rem; }
                    .solution-export-markdown p,
                    .solution-export-markdown ul,
                    .solution-export-markdown ol,
                    .solution-export-markdown blockquote,
                    .solution-export-markdown pre,
                    .solution-export-markdown table { margin: 0.9em 0; }
                    .solution-export-markdown ul,
                    .solution-export-markdown ol { padding-left: 1.3rem; }
                    .solution-export-markdown li { margin: 0.4em 0; }
                    .solution-export-markdown strong { color: #0f172a; }
                    .solution-export-markdown blockquote {
                        padding: 0.95rem 1rem;
                        border-left: 3px solid #2563eb;
                        background: #eff6ff;
                        color: #1e3a8a;
                        border-radius: 0 1rem 1rem 0;
                    }
                    .solution-export-markdown hr {
                        border: 0;
                        border-top: 1px solid #e2e8f0;
                        margin: 1.5rem 0;
                    }
                    .solution-export-markdown code {
                        font-family: 'SFMono-Regular', Consolas, monospace;
                        font-size: 0.92em;
                        padding: 0.14rem 0.3rem;
                        border-radius: 0.35rem;
                        background: #eff6ff;
                        color: #1d4ed8;
                    }
                    .solution-export-markdown pre {
                        overflow-x: auto;
                        padding: 1rem 1.1rem;
                        border-radius: 1rem;
                        background: #0f172a;
                        color: #e2e8f0;
                    }
                    .solution-export-markdown pre code {
                        padding: 0;
                        background: transparent;
                        color: inherit;
                    }
                    .solution-export-markdown table {
                        width: 100%;
                        border-collapse: collapse;
                        border: 1px solid #e2e8f0;
                    }
                    .solution-export-markdown th,
                    .solution-export-markdown td {
                        padding: 0.75rem 0.9rem;
                        border-bottom: 1px solid #e2e8f0;
                        text-align: left;
                        vertical-align: top;
                    }
                    .solution-export-markdown thead { background: #f8fafc; }
                    .solution-export-markdown a { color: #2563eb; text-decoration: none; }
                </style>
            </head>
            <body>
                <header style="margin-bottom: 32px; padding-bottom: 20px; border-bottom: 1px solid #e2e8f0;">
                    <p style="margin: 0 0 8px; font-size: 12px; letter-spacing: 0.16em; text-transform: uppercase; color: #2563eb;">GEOrank AI Q&A Workspace</p>
                    <h1 style="margin: 0 0 12px; font-size: 32px;">${escapeHtml(state.conversationTitle || 'GEO问答')}</h1>
                    <p style="margin: 0; font-size: 14px; line-height: 1.7; color: #64748b;">
                        ${escapeHtml(state.contextReport?.url || state.sourceUrl || '基于当前对话上下文导出的 GEO 问答摘要')}
                    </p>
                </header>
                ${transcript}
                ${companySection}
            </body>
            </html>
        `;
    }

    function toFiniteNumber(value) {
        const numeric = Number(value);
        return Number.isFinite(numeric) ? numeric : null;
    }

    function scrollMessagesToBottom() {
        elements.chatMessages?.scrollTo({ top: elements.chatMessages.scrollHeight, behavior: 'smooth' });
    }

    function scrollMessagesToTop() {
        elements.chatMessages?.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = value == null ? '' : String(value);
        return div.innerHTML;
    }
});
