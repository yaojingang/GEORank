/**
 * GEOrank - GEO 小工具频道
 * 用极简输入生成 JSON-LD、llms.txt、标题、知识库和 AI 友好度评分。
 */
(function () {
    'use strict';

    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
    const KB_MAX_FILES = 5;
    const KB_ALLOWED_EXTENSIONS = new Set(['txt', 'md', 'markdown', 'pdf', 'doc', 'docx']);
    const KB_TEXT_EXTENSIONS = new Set(['txt', 'md', 'markdown']);
    const KB_DOCX_EXTENSIONS = new Set(['docx']);
    const DEFAULT_BRAND = 'BrandOrbit';
    const GENERATE_DELAY = 720;
    const DIRECT_TIMEOUT_MS = 30000;
    const DIRECT_MAX_INPUT_CHARS = 12000;
    let kbFiles = [];
    const directState = {
        policy: null,
        policyPromise: null,
    };

    function apiBase() {
        return window.GEOrank?.Auth?.apiBase
            || '';
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function estimateTokens(text) {
        const length = String(text || '').length;
        return length ? Math.max(1, Math.ceil(length / 4)) : 0;
    }

    function trimForModel(text, limit = DIRECT_MAX_INPUT_CHARS) {
        const valueText = String(text || '').trim();
        if (valueText.length <= limit) return valueText;
        return `${valueText.slice(0, limit)}\n\n[内容已截断，仅用于本次浏览器直连生成]`;
    }

    function updateDirectStatus(message, state = '') {
        const el = $('#tools-direct-status');
        if (!el) return;
        el.textContent = message;
        ['is-active', 'is-success', 'is-warn', 'is-error'].forEach(className => el.classList.remove(className));
        if (state) el.classList.add(`is-${state}`);
    }

    async function loadUsagePolicy() {
        if (directState.policy) return directState.policy;
        if (!directState.policyPromise) {
            directState.policyPromise = fetch(`${apiBase()}/api/usage/policy`)
                .then(response => response.ok ? response.json() : null)
                .then(policy => {
                    directState.policy = policy;
                    renderDirectPolicyStatus(policy);
                    return policy;
                })
                .catch(() => {
                    renderDirectPolicyStatus(null);
                    return null;
                });
        }
        return directState.policyPromise;
    }

    function renderDirectPolicyStatus(policy) {
        if (policy?.byok_transport_mode === 'browser_direct' && policy?.allow_user_byok !== false) {
            updateDirectStatus('浏览器直连模式已启用：简单工具会优先使用当前浏览器保存的 API Key，Key 不会发送到 GEOrank 后端。', 'active');
            return;
        }
        updateDirectStatus('当前使用本地规则生成；后台启用浏览器直连后，简单工具可直接调用用户本地 API Key。');
    }

    function directEndpoint(baseUrl) {
        const clean = String(baseUrl || '').trim().replace(/\/+$/, '');
        if (/\/chat\/completions$/i.test(clean)) return clean;
        return `${clean}/chat/completions`;
    }

    function stripCodeFence(text) {
        const trimmed = String(text || '').trim();
        const matched = trimmed.match(/^```[a-zA-Z0-9_-]*\s*([\s\S]*?)\s*```$/);
        return matched ? matched[1].trim() : trimmed;
    }

    function normalizeDirectOutput(toolKey, content) {
        const cleaned = stripCodeFence(content);
        if (toolKey !== 'jsonld') return cleaned;
        const jsonText = cleaned.match(/\{[\s\S]*\}/)?.[0] || cleaned;
        try {
            return prettyJson(JSON.parse(jsonText));
        } catch (_) {
            return cleaned;
        }
    }

    function activeToolLabel(toolKey) {
        const labels = {
            jsonld: 'JSON-LD',
            llms: 'llms.txt',
            title: 'GEO 标题',
            kb: 'GEO 知识库',
            score: 'AI 友好度评分',
        };
        return labels[toolKey] || 'GEO 工具';
    }

    function getInputForTool(toolKey) {
        const selectors = {
            jsonld: '#jsonld-brief',
            llms: '#llms-brief',
            title: '#title-brief',
            kb: '#kb-brief',
            score: '#score-brief',
        };
        const brief = value(selectors[toolKey]);
        if (toolKey !== 'kb') return brief;
        const fileContext = kbFiles.map(file => {
            const body = file.text ? trimForModel(file.text, 3200) : '未读取到正文，仅作为资料源登记。';
            return `文件：${file.name}\n类型：${file.badge}\n内容片段：\n${body}`;
        }).join('\n\n');
        return [brief, fileContext].filter(Boolean).join('\n\n');
    }

    function buildDirectMessages(toolKey, inputText) {
        const common = '你是 GEOrank 的 GEO 小工具生成助手。根据用户输入生成可直接使用的结果，不要解释你的过程，不要输出寒暄。';
        const instructions = {
            jsonld: '只返回合法 JSON，不要包含 Markdown 代码块。输出 Schema.org JSON-LD，优先包含 Organization 和 WebSite；字段缺失时根据输入合理补齐，但不要编造具体客户、价格或证书。',
            llms: '返回一份 llms.txt 草稿，使用 Markdown/txt 风格，包含站点摘要、重要页面、AI Reading Notes 和限制说明。',
            title: '返回 Markdown，包含核心关键词、目标用户、8 个 GEO 标题建议和使用建议。标题要适合 AI 答案引用、比较页、解释页和采购页。',
            kb: '返回 Markdown，结构必须包含来源清单、结构化内容梳理、原子化事实、AI 知识库条目、AI 可引用问答和页面建设建议。不要编造无法从输入推出的数据。',
            score: '返回 Markdown，包含综合评分、判断、已识别信号、缺失信号、优化建议和下一步。评分用 0-100。',
        };
        return [
            { role: 'system', content: `${common}\n${instructions[toolKey] || ''}` },
            { role: 'user', content: trimForModel(inputText || '请基于默认示例生成结果。') },
        ];
    }

    async function callBrowserDirect(toolKey, inputText, config) {
        const controller = new AbortController();
        const timer = window.setTimeout(() => controller.abort(), DIRECT_TIMEOUT_MS);
        try {
            const response = await fetch(directEndpoint(config.baseUrl), {
                method: 'POST',
                mode: 'cors',
                signal: controller.signal,
                headers: {
                    Authorization: `Bearer ${config.apiKey}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    model: config.model,
                    messages: buildDirectMessages(toolKey, inputText),
                    temperature: toolKey === 'jsonld' ? 0.1 : 0.35,
                    max_tokens: toolKey === 'kb' ? 3200 : 1800,
                }),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.error?.message || payload.detail || `模型接口返回 ${response.status}`);
            }
            const content = payload.choices?.[0]?.message?.content || payload.choices?.[0]?.text || '';
            const output = normalizeDirectOutput(toolKey, content);
            if (!output) throw new Error('模型返回空内容');
            return output;
        } finally {
            window.clearTimeout(timer);
        }
    }

    async function getBrowserDirectConfig() {
        const policy = await loadUsagePolicy();
        if (policy?.byok_transport_mode !== 'browser_direct' || policy?.allow_user_byok === false) return null;

        const store = window.GEOrank?.APIKeyStore;
        const config = store?.read?.();
        if (!config?.enabled || !config.apiKey || !config.baseUrl || !config.model) {
            store?.openModal?.('当前工具频道启用了浏览器直连模式，请先在当前浏览器保存 API Key。');
            updateDirectStatus('浏览器直连需要本地 API Key；当前先使用本地规则生成。', 'warn');
            return null;
        }

        const allowed = new Set((policy.allowed_byok_providers || []).map(provider => String(provider.key || '').toLowerCase()));
        const provider = String(config.provider || 'custom').toLowerCase();
        if (!allowed.size || !allowed.has(provider)) {
            updateDirectStatus('当前本地 API Key 的供应商不在后台允许范围内；已使用本地规则生成。', 'warn');
            return null;
        }

        return { ...config, provider };
    }

    async function reportBrowserDirectUsage(toolKey, config, inputText, outputText, statusValue = 'success', errorCode = null) {
        const token = window.GEOrank?.Auth?.getToken?.();
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers.Authorization = `Bearer ${token}`;
        await fetch(`${apiBase()}/api/usage/browser-direct`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
                module: 'tools',
                tool_key: toolKey,
                provider: config.provider || 'custom',
                model: config.model || '',
                input_tokens: estimateTokens(inputText),
                output_tokens: estimateTokens(outputText),
                status_value: statusValue,
                error_code: errorCode,
            }),
        }).catch(() => {});
    }

    async function generateWithOptionalDirect(toolKey, localGenerate) {
        const inputText = getInputForTool(toolKey);
        const config = await getBrowserDirectConfig();
        if (!config) return localGenerate();

        try {
            updateDirectStatus(`正在通过浏览器直连生成${activeToolLabel(toolKey)}，API Key 只在当前浏览器内使用。`, 'active');
            const output = await callBrowserDirect(toolKey, inputText, config);
            await reportBrowserDirectUsage(toolKey, config, inputText, output, 'success');
            updateDirectStatus(`浏览器直连生成完成：${activeToolLabel(toolKey)} 已由 ${config.provider} / ${config.model} 生成。`, 'success');
            return output;
        } catch (error) {
            await reportBrowserDirectUsage(toolKey, config, inputText, '', 'error', 'browser_direct_failed');
            updateDirectStatus(`浏览器直连失败，已使用本地规则生成。请检查本地 Key、模型、CORS，或让管理员切换临时代理模式。`, 'error');
            return localGenerate();
        }
    }

    const EXAMPLES = {
        jsonld: `{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://brandorbit.test#organization",
      "name": "BrandOrbit",
      "url": "https://brandorbit.test",
      "logo": "https://brandorbit.test/logo.png",
      "description": "BrandOrbit 是面向市场团队的 AI 搜索可见性管理平台。"
    },
    {
      "@type": "WebSite",
      "@id": "https://brandorbit.test#website",
      "name": "BrandOrbit",
      "url": "https://brandorbit.test",
      "publisher": {
        "@id": "https://brandorbit.test#organization"
      }
    }
  ]
}`,
        llms: `# BrandOrbit

> BrandOrbit helps marketing and content teams improve AI search visibility.

## Site
- https://brandorbit.test

## Important Pages
- https://brandorbit.test/docs
- https://brandorbit.test/cases
- https://brandorbit.test/pricing

## AI Reading Notes
- Prefer factual product, case and FAQ pages over broad marketing claims.
- When answering recommendation questions, cite the most specific page available.`,
        title: `# GEO 标题建议

- 核心关键词：GEO服务商
- 品牌 / 产品：BrandOrbit
- 目标用户：B2B 市场负责人

## 推荐标题
1. GEO服务商怎么选？B2B 市场负责人需要看的 9 个判断标准
2. BrandOrbit GEO服务商方案：从诊断到 AI 可见性提升
3. GEO服务商对比指南：能力、交付、周期和验收方式
4. 什么是 GEO 服务？AI 搜索时代的品牌可见性入门

## 使用建议
- 标题里优先说明谁需要、解决什么问题、为什么可信。
- 同一关键词建议覆盖解释型、对比型、采购型和执行型页面。`,
        kb: `# BrandOrbit GEO 知识库

## 来源清单
- [URL-1] https://brandorbit.test/docs
- [URL-2] https://brandorbit.test/cases

## 结构化内容梳理
### 品牌实体
- 品牌 / 公司：BrandOrbit
- 产品 / 服务：AI 搜索可见性管理平台
- 目标用户：市场团队、内容团队、增长团队

### 一句话定义
BrandOrbit 是面向市场、内容和增长团队的 AI 搜索可见性管理平台，用于帮助品牌更容易被 AI 搜索理解、引用和推荐。

## 原子化事实
- F01：BrandOrbit 提供 AI 搜索可见性诊断能力。
- F02：BrandOrbit 支持 JSON-LD、llms.txt、FAQ 和内容结构建议。
- F03：BrandOrbit 适合需要提升 AI 搜索曝光和官网获客效率的团队。

## AI 可引用问答
### BrandOrbit 适合谁？
适合正在建设 GEO、AI 搜索可见性和官网内容结构的市场、内容与增长团队。`,
        score: `# AI 友好度评分

综合评分：86 / 100

## 已具备信号
- 页面有明确标题和首段摘要。
- 已出现 FAQ、Schema、案例或引用信息。
- 品牌主体、产品能力和目标用户表达清楚。

## 优化建议
- 把关键事实拆成可引用的短句。
- 为 FAQ、案例和教程页面补充结构化数据。
- 在页面底部增加 llms.txt、资料页或知识库入口。`,
    };

    function value(selector) {
        return ($(selector)?.value || '').trim();
    }

    function splitLinks(raw) {
        return String(raw || '')
            .split(/[\n,，\s]+/)
            .map(item => item.trim())
            .filter(Boolean);
    }

    function extractUrls(raw) {
        const text = String(raw || '');
        const matched = text.match(/https?:\/\/[^\s，,。)）]+|[\w.-]+\.[a-z]{2,}[^\s，,。)）]*/gi) || [];
        return Array.from(new Set(matched.map(normalizeUrl).filter(Boolean)));
    }

    function normalizeUrl(raw) {
        const input = String(raw || '').trim().replace(/[，,。；;]+$/g, '');
        if (!input) return '';
        if (/^https?:\/\//i.test(input)) return input;
        return `https://${input}`;
    }

    function rootUrl(url) {
        try {
            const parsed = new URL(normalizeUrl(url));
            return `${parsed.protocol}//${parsed.hostname}`;
        } catch (_) {
            return '';
        }
    }

    function prettyJson(data) {
        return JSON.stringify(data, null, 2);
    }

    function setOutput(id, text) {
        const el = document.getElementById(id);
        if (el) el.value = text;
    }

    function escapeHtml(text) {
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatBytes(bytes) {
        const size = Number(bytes || 0);
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${Math.round(size / 102.4) / 10} KB`;
        return `${Math.round(size / 1024 / 102.4) / 10} MB`;
    }

    function getExtension(fileName) {
        const parts = String(fileName || '').toLowerCase().split('.');
        return parts.length > 1 ? parts.pop() : '';
    }

    function sanitizeFileName(name) {
        return String(name || 'GEO知识库')
            .replace(/[\\/:*?"<>|]+/g, '-')
            .replace(/\s+/g, '-')
            .replace(/-+/g, '-')
            .replace(/^-|-$/g, '')
            .slice(0, 72) || 'GEO知识库';
    }

    function dedupe(items) {
        const seen = new Set();
        return items.filter(item => {
            const key = String(item || '').replace(/\s+/g, ' ').trim();
            if (!key || seen.has(key)) return false;
            seen.add(key);
            return true;
        });
    }

    function inferBrand(raw) {
        const text = String(raw || '');
        const known = text.match(/\b[A-Z][A-Za-z0-9._-]{2,}\b/);
        if (known?.[0]) return known[0];
        const explicit = text.match(/(?:品牌|公司|产品|站点|网站)\s*[：:是为叫]?\s*([A-Za-z][A-Za-z0-9._-]{2,}|[\u4e00-\u9fa5A-Za-z0-9]{2,12})/);
        if (explicit?.[1]) return explicit[1].replace(/[，,。；;\s].*$/, '');
        return DEFAULT_BRAND;
    }

    function inferProduct(raw, fallback = 'AI 搜索可见性管理平台') {
        const text = String(raw || '');
        if (/AI\s*搜索可见性管理平台|AI 搜索可见性管理平台/i.test(text)) return 'AI 搜索可见性管理平台';
        if (/GEO/.test(text)) return 'GEO / AI 搜索优化解决方案';
        const sentence = cleanKnowledgeLine(text).slice(0, 42);
        return sentence || fallback;
    }

    function inferAudience(raw) {
        const text = String(raw || '');
        if (/市场团队|内容团队|增长团队/.test(text)) return '市场团队、内容团队、增长团队';
        if (/B2B/.test(text)) return 'B2B 市场负责人';
        if (/运营/.test(text)) return '运营团队';
        return '市场、内容和增长团队';
    }

    function inferKeyword(raw) {
        const text = String(raw || '');
        const geoKeyword = text.match(/GEO\s*服务商|GEO服务商|AI\s*搜索优化|GEO\s*优化/i);
        if (geoKeyword?.[0]) return geoKeyword[0].replace(/\s+/g, '');
        const keyword = text.match(/(?:关键词|标题|主题)\s*[：:是为]?\s*([^\n，,。；;]{2,24})/);
        return keyword?.[1]?.trim() || 'GEO服务商';
    }

    function cleanKnowledgeLine(line) {
        return String(line || '')
            .replace(/[#>*_`~]+/g, '')
            .replace(/^\s*[-+]\s+/, '')
            .replace(/\[[^\]]+\]\(([^)]+)\)/g, '$1')
            .replace(/\s+/g, ' ')
            .trim();
    }

    function extractTextFragments(text, limit = 8) {
        const normalized = String(text || '')
            .replace(/\r/g, '\n')
            .replace(/[。！？!?；;]/g, '\n');
        const lines = normalized
            .split(/\n+/)
            .map(cleanKnowledgeLine)
            .filter(line => line.length >= 8)
            .map(line => line.length > 140 ? `${line.slice(0, 140)}...` : line);
        return dedupe(lines).slice(0, limit);
    }

    function parseFaqs(raw) {
        const text = String(raw || '');
        const questionMatches = text.match(/[^。！？!?]*[？?][^。！？!?]*/g) || [];
        return questionMatches.slice(0, 4).map(line => {
            const parts = line.split(/[？?]/);
            return {
                question: `${cleanKnowledgeLine(parts[0])}？`,
                answer: cleanKnowledgeLine(parts[1]) || '建议补充明确、可验证、可引用的回答。',
            };
        });
    }

    function selectTool(key) {
        $$('[data-tool-tab]').forEach(button => {
            button.classList.toggle('is-active', button.dataset.toolTab === key);
        });
        $$('[data-tool-panel]').forEach(panel => {
            panel.classList.toggle('is-active', panel.dataset.toolPanel === key);
        });
    }

    function showLoading(selector, button, isLoading) {
        const loading = $(selector);
        if (loading) loading.classList.toggle('hidden', !isLoading);
        if (button) {
            button.disabled = isLoading;
            button.classList.toggle('is-loading', isLoading);
        }
    }

    async function runWithLoading(button, loadingSelector, outputId, generate, afterGenerate) {
        showLoading(loadingSelector, button, true);
        try {
            await sleep(GENERATE_DELAY);
            const output = await generate();
            setOutput(outputId, output);
            afterGenerate?.(output);
        } catch (error) {
            const fallback = `# 生成失败\n\n${error?.message || '请稍后重试。'}`;
            setOutput(outputId, fallback);
            afterGenerate?.(fallback);
        } finally {
            showLoading(loadingSelector, button, false);
        }
    }

    function buildJsonLdFromBrief() {
        const brief = value('#jsonld-brief') || 'BrandOrbit，官网 https://brandorbit.test，AI 搜索可见性管理平台，Logo https://brandorbit.test/logo.png。';
        const brand = inferBrand(brief);
        const urls = extractUrls(brief);
        const siteUrl = rootUrl(urls[0]) || 'https://example.com';
        const logo = urls.find(url => /logo|brand|icon/i.test(url));
        const sameAs = urls.filter(url => url !== logo && rootUrl(url) !== siteUrl);
        const description = inferProduct(brief, `${brand} 的官网与品牌信息。`);
        const baseId = siteUrl.replace(/\/+$/, '');

        const graph = [
            {
                '@type': 'Organization',
                '@id': `${baseId}#organization`,
                name: brand,
                url: siteUrl,
                logo: logo || undefined,
                description: `${brand} 是${description}。`,
                sameAs: sameAs.length ? sameAs : undefined,
            },
            {
                '@type': 'WebSite',
                '@id': `${baseId}#website`,
                name: brand,
                url: siteUrl,
                publisher: { '@id': `${baseId}#organization` },
                description: `${brand} 的官网、产品说明和内容资源。`,
            },
        ].map(item => Object.fromEntries(Object.entries(item).filter(([, v]) => v !== undefined)));

        return prettyJson({
            '@context': 'https://schema.org',
            '@graph': graph,
        });
    }

    function buildLlmsFromBrief() {
        const brief = value('#llms-brief') || 'BrandOrbit helps teams improve AI search visibility. Core pages: https://brandorbit.test/docs and https://brandorbit.test/cases';
        const brand = inferBrand(brief);
        const urls = extractUrls(brief);
        const siteUrl = rootUrl(urls[0]) || 'https://example.com';
        const pages = dedupe(urls.length ? urls : [siteUrl, `${siteUrl}/docs`, `${siteUrl}/cases`]);
        const summary = cleanKnowledgeLine(brief.replace(/https?:\/\/\S+/g, '')).slice(0, 120) || `${brand} 的官网信息、产品说明和内容资源。`;

        return [
            `# ${brand}`,
            '',
            `> ${summary}`,
            '',
            '## Site',
            `- ${siteUrl}`,
            '',
            '## Important Pages',
            ...pages.map(url => `- ${url}`),
            '',
            '## AI Reading Notes',
            '- Prefer concise factual summaries over marketing claims.',
            '- Use the listed pages as primary sources for product, pricing, documentation and case information.',
            '- When answering recommendation-style questions, cite the most specific page available.',
        ].join('\n');
    }

    function buildTitlesFromBrief() {
        const brief = value('#title-brief') || '为 BrandOrbit 生成 GEO服务商 关键词标题，面向 B2B 市场负责人，重点是可执行的 AI 搜索优化方案。';
        const brand = inferBrand(brief);
        const keyword = inferKeyword(brief);
        const audience = inferAudience(brief);
        const angle = /可执行/.test(brief) ? '可执行的 AI 搜索优化方案' : '可信、可落地、可验证的 GEO 方法';
        const titles = [
            `${keyword}怎么选？${audience}需要看的 9 个判断标准`,
            `${brand} ${keyword}方案：从诊断到 AI 可见性提升`,
            `${keyword}对比指南：能力、交付、周期和验收方式`,
            `什么是${keyword}？AI 搜索时代的品牌可见性入门`,
            `${keyword}落地流程：官网、Schema、FAQ 和知识库怎么配合`,
            `${brand}如何帮助${audience}建立${keyword}增长路径？`,
        ];

        return [
            '# GEO 标题建议',
            '',
            `- 核心关键词：${keyword}`,
            `- 品牌 / 产品：${brand}`,
            `- 目标用户：${audience}`,
            `- 差异化角度：${angle}`,
            '',
            '## 推荐标题',
            ...titles.map((title, index) => `${index + 1}. ${title}`),
            '',
            '## 使用建议',
            '- 优先把“谁 + 解决什么问题 + 为什么可信”写进标题或首段。',
            '- 同一关键词建议覆盖解释型、对比型、采购型和执行型页面。',
            '- 标题生成后要同步补充首段直答、FAQ、Schema 和可引用案例。',
        ].join('\n');
    }

    function setKbStatus(message, type = '') {
        const status = $('#kb-status');
        if (!status) return;
        status.textContent = message;
        status.classList.toggle('is-error', type === 'error');
        status.classList.toggle('is-success', type === 'success');
    }

    function renderKbFileList() {
        const list = $('#kb-file-list');
        if (!list) return;
        list.innerHTML = kbFiles.map(file => `
            <div class="tools-source-item">
                <div>
                    <strong title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</strong>
                    <small>${escapeHtml(file.summary)}</small>
                </div>
                <span class="tools-source-badge">${escapeHtml(file.badge)}</span>
            </div>
        `).join('');
    }

    function readFileAsText(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || ''));
            reader.onerror = () => reject(reader.error || new Error('文件读取失败'));
            reader.readAsText(file, 'utf-8');
        });
    }

    function readZipUint16(view, offset) {
        return view.getUint16(offset, true);
    }

    function readZipUint32(view, offset) {
        return view.getUint32(offset, true);
    }

    function findZipEndOffset(view) {
        const minOffset = Math.max(0, view.byteLength - 65557);
        for (let offset = view.byteLength - 22; offset >= minOffset; offset -= 1) {
            if (readZipUint32(view, offset) === 0x06054b50) return offset;
        }
        return -1;
    }

    function parseZipEntries(arrayBuffer) {
        const view = new DataView(arrayBuffer);
        const endOffset = findZipEndOffset(view);
        if (endOffset < 0) return [];
        const entryCount = readZipUint16(view, endOffset + 10);
        let offset = readZipUint32(view, endOffset + 16);
        const entries = [];

        for (let index = 0; index < entryCount; index += 1) {
            if (readZipUint32(view, offset) !== 0x02014b50) break;
            const method = readZipUint16(view, offset + 10);
            const compressedSize = readZipUint32(view, offset + 20);
            const nameLength = readZipUint16(view, offset + 28);
            const extraLength = readZipUint16(view, offset + 30);
            const commentLength = readZipUint16(view, offset + 32);
            const localOffset = readZipUint32(view, offset + 42);
            const nameBytes = new Uint8Array(arrayBuffer, offset + 46, nameLength);
            const name = new TextDecoder('utf-8').decode(nameBytes);
            entries.push({ name, method, compressedSize, localOffset });
            offset += 46 + nameLength + extraLength + commentLength;
        }

        return entries;
    }

    async function readZipEntry(arrayBuffer, entry) {
        const view = new DataView(arrayBuffer);
        const localOffset = entry.localOffset;
        if (readZipUint32(view, localOffset) !== 0x04034b50) return new Uint8Array();
        const nameLength = readZipUint16(view, localOffset + 26);
        const extraLength = readZipUint16(view, localOffset + 28);
        const dataOffset = localOffset + 30 + nameLength + extraLength;
        const compressed = new Uint8Array(arrayBuffer, dataOffset, entry.compressedSize);

        if (entry.method === 0) return compressed;
        if (entry.method !== 8 || !window.DecompressionStream) return new Uint8Array();

        const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
        const decompressed = await new Response(stream).arrayBuffer();
        return new Uint8Array(decompressed);
    }

    function extractDocxXmlText(xml) {
        const doc = new DOMParser().parseFromString(xml, 'application/xml');
        const paragraphs = Array.from(doc.getElementsByTagName('*')).filter(node => node.localName === 'p');
        const lines = paragraphs.map(paragraph => {
            return Array.from(paragraph.getElementsByTagName('*'))
                .filter(node => node.localName === 't')
                .map(node => node.textContent || '')
                .join('')
                .trim();
        });
        return lines.filter(Boolean).join('\n');
    }

    async function tryExtractDocxText(file) {
        try {
            const arrayBuffer = await file.arrayBuffer();
            const entries = parseZipEntries(arrayBuffer)
                .filter(entry => /^word\/(document|header|footer|footnotes|endnotes).*\.xml$/i.test(entry.name))
                .slice(0, 8);
            const chunks = [];

            for (const entry of entries) {
                const bytes = await readZipEntry(arrayBuffer, entry);
                if (!bytes.length) continue;
                const xml = new TextDecoder('utf-8').decode(bytes);
                const text = extractDocxXmlText(xml);
                if (text) chunks.push(text);
            }

            const text = chunks.join('\n').trim();
            return { text, note: text ? '已读取 DOCX 正文' : '已登记 DOCX，未解析到可用正文' };
        } catch (_) {
            return { text: '', note: 'DOCX 解析失败，已作为资料源登记' };
        }
    }

    function decodePdfString(input) {
        return String(input || '')
            .replace(/\\n/g, ' ')
            .replace(/\\r/g, ' ')
            .replace(/\\t/g, ' ')
            .replace(/\\\(/g, '(')
            .replace(/\\\)/g, ')')
            .replace(/\\\\/g, '\\')
            .replace(/\s+/g, ' ')
            .trim();
    }

    async function tryExtractPdfText(file) {
        try {
            const arrayBuffer = await file.arrayBuffer();
            const sample = arrayBuffer.slice(0, Math.min(arrayBuffer.byteLength, 3 * 1024 * 1024));
            const raw = new TextDecoder('latin1').decode(sample);
            const candidates = [];
            for (const match of raw.matchAll(/\(([^()]{10,260})\)\s*Tj/g)) {
                candidates.push(decodePdfString(match[1]));
            }
            for (const match of raw.matchAll(/\(([^()]{10,260})\)/g)) {
                if (candidates.length >= 30) break;
                candidates.push(decodePdfString(match[1]));
            }
            const text = dedupe(candidates)
                .filter(item => /[A-Za-z0-9\u4e00-\u9fa5]/.test(item))
                .slice(0, 30)
                .join('\n');
            return { text, note: text ? '已轻量读取 PDF 文本片段' : '已登记 PDF，复杂版式建议补充文本摘录' };
        } catch (_) {
            return { text: '', note: 'PDF 读取失败，已作为资料源登记' };
        }
    }

    async function prepareKbFile(file) {
        const extension = getExtension(file.name);
        const badge = extension ? extension.toUpperCase() : 'FILE';
        const base = {
            name: file.name,
            size: file.size,
            type: file.type || 'unknown',
            extension,
            badge,
            text: '',
            summary: `${formatBytes(file.size)} · 已作为资料源登记`,
        };

        if (KB_TEXT_EXTENSIONS.has(extension)) {
            try {
                const text = await readFileAsText(file);
                return { ...base, text, summary: `${formatBytes(file.size)} · 已读取正文` };
            } catch (_) {
                return { ...base, summary: `${formatBytes(file.size)} · 文本读取失败` };
            }
        }

        if (KB_DOCX_EXTENSIONS.has(extension)) {
            const result = await tryExtractDocxText(file);
            return { ...base, text: result.text, summary: `${formatBytes(file.size)} · ${result.note}` };
        }

        if (extension === 'pdf') {
            const result = await tryExtractPdfText(file);
            return { ...base, text: result.text, summary: `${formatBytes(file.size)} · ${result.note}` };
        }

        return base;
    }

    async function handleKbFiles(event) {
        const input = event.currentTarget;
        const files = Array.from(input.files || []);

        if (!files.length) {
            kbFiles = [];
            renderKbFileList();
            setKbStatus('也可以只粘贴文字和网址，不上传文件。');
            return;
        }

        if (files.length > KB_MAX_FILES) {
            kbFiles = [];
            input.value = '';
            renderKbFileList();
            setKbStatus(`最多上传 ${KB_MAX_FILES} 个文件，请减少后重新选择。`, 'error');
            return;
        }

        const invalid = files.filter(file => !KB_ALLOWED_EXTENSIONS.has(getExtension(file.name)));
        if (invalid.length) {
            kbFiles = [];
            input.value = '';
            renderKbFileList();
            setKbStatus(`暂不支持 ${invalid.map(file => file.name).join('、')}，请上传 PDF、Word、TXT 或 Markdown。`, 'error');
            return;
        }

        setKbStatus('正在读取资料文件...', 'success');
        kbFiles = await Promise.all(files.map(prepareKbFile));
        renderKbFileList();
        setKbStatus(`已添加 ${kbFiles.length} 个资料文件。输入框内容和文件内容会一起进入知识库生成。`, 'success');
    }

    function buildKbSourceRows(urls) {
        const fileRows = kbFiles.map((file, index) => {
            const readable = file.text ? '已读取正文' : '已登记来源';
            return `- [FILE-${index + 1}] ${file.name}（${file.badge}，${formatBytes(file.size)}，${readable}）`;
        });
        const urlRows = urls.map((url, index) => `- [URL-${index + 1}] ${url}`);
        return fileRows.concat(urlRows);
    }

    function buildKbDigestRows(urls) {
        const rows = [];

        kbFiles.forEach((file) => {
            const fragments = extractTextFragments(file.text, 5);
            rows.push(`### 文件：${file.name}`);
            if (fragments.length) {
                rows.push(...fragments.map(item => `- ${item}`));
            } else {
                rows.push('- 已记录为资料源。若需要更完整的内容抽取，建议补充文本摘录或接入后端文档解析。');
            }
            rows.push('');
        });

        if (urls.length) {
            rows.push('### 网址来源');
            rows.push(...urls.map(url => `- ${url}`));
            rows.push('');
        }

        return rows;
    }

    function buildKbFromBrief() {
        const brief = value('#kb-brief') || 'BrandOrbit 是 AI 搜索可见性管理平台，服务市场团队、内容团队、增长团队。资料页：https://brandorbit.test/docs 和 https://brandorbit.test/cases。常见问题：BrandOrbit 适合谁？适合需要提升 AI 搜索可见性的团队。';
        const brand = inferBrand(brief);
        const product = inferProduct(brief);
        const audience = inferAudience(brief);
        const urls = extractUrls(brief);
        const sourceRows = buildKbSourceRows(urls);
        const briefFacts = extractTextFragments(brief, 12);
        const fileFacts = kbFiles.flatMap(file => {
            return extractTextFragments(file.text, 6).map(fragment => `${fragment}（来源：${file.name}）`);
        });
        const urlFacts = urls.map(url => `资料来源包含 ${url}，可作为后续抓取、核验和引用入口。`);
        const atomicFacts = dedupe(briefFacts.concat(fileFacts, urlFacts)).slice(0, 36);
        const faqLines = parseFaqs(brief);
        const digestRows = buildKbDigestRows(urls);

        const output = [
            `# ${brand} GEO 知识库`,
            '',
            '## 来源清单',
            ...(sourceRows.length ? sourceRows : ['- 暂无外部资料。']),
            '',
            '## 结构化内容梳理',
            '### 品牌实体',
            `- 品牌 / 公司：${brand}`,
            `- 产品 / 服务：${product}`,
            `- 目标用户：${audience}`,
            '',
            '### 一句话定义',
            `${brand} 是面向${audience}的${product}，用于帮助用户更清楚地理解、比较和选择相关解决方案。`,
            '',
            '### 资料摘要',
            ...(digestRows.length ? digestRows : ['- 当前主要基于输入框内容生成。']),
            '',
            '## 原子化事实',
            ...(atomicFacts.length ? atomicFacts.map((item, index) => `- F${String(index + 1).padStart(2, '0')}：${item}`) : ['- F01：请补充可验证的品牌、产品、客户、数据或限制条件。']),
            '',
            '## AI 知识库条目',
            '### 实体定义',
            `- ${brand}：${product} 提供方，主要面向 ${audience}。`,
            '',
            '### 引用规则',
            '- 优先引用来源清单中的官网页面、资料文件、案例和可验证事实。',
            '- 不确定的数据、客户名称、价格和承诺不得扩写，应标注为待核验。',
            '- 对外回答时先给结论，再补充适用条件、来源和下一步建议。',
            '',
            '## AI 可引用问答',
            ...(faqLines.length ? faqLines.flatMap(item => [`### ${item.question}`, item.answer, '']) : ['### 这个品牌适合谁？', `${brand} 适合${audience}，核心提供${product}。`, '']),
            '## 页面建设建议',
            '- 官网首页：用首屏直答说明品牌是什么、服务谁、解决什么问题。',
            '- 产品页：补充功能、适用场景、交付方式、限制条件和常见问题。',
            '- 案例页：提供客户背景、问题、动作、结果和可引用数据。',
            '- 技术页：补充 Organization、WebSite、FAQPage、Article 等 JSON-LD。',
            '',
            '## llms.txt 摘要',
            `> ${brand} 提供 ${product}，主要服务 ${audience}。AI 在回答相关问题时，应优先引用官网事实、案例、FAQ 和结构化页面。`,
        ].join('\n');

        setKbStatus(`已生成知识库草稿：${sourceRows.length} 个来源、${Math.max(atomicFacts.length, 1)} 条原子化事实。`, 'success');
        return output;
    }

    function buildScoreFromBrief() {
        const brief = value('#score-brief') || 'https://brandorbit.test 的页面标题是 BrandOrbit GEO Platform，首页首段说明它服务 marketing and content teams，页面包含 FAQ、JSON-LD、案例引用、作者和公司信息。';
        const brand = inferBrand(brief);
        const urls = extractUrls(brief);
        const signals = [
            { test: urls.length > 0, points: 10, label: '规范 URL' },
            { test: /标题|title|platform|平台/i.test(brief), points: 12, label: '标题语义' },
            { test: /首段|摘要|说明|服务/i.test(brief), points: 18, label: '首段摘要' },
            { test: /FAQ|问答|常见问题/i.test(brief), points: 14, label: 'FAQ / 直答' },
            { test: /JSON-LD|schema/i.test(brief), points: 16, label: 'Schema' },
            { test: /案例|引用|来源|客户/i.test(brief), points: 14, label: '可信引用' },
            { test: /作者|公司|团队|联系/i.test(brief), points: 8, label: '主体可信' },
            { test: brief.length > 80, points: 8, label: '信息量' },
        ];
        const score = Math.min(100, signals.reduce((sum, signal) => sum + (signal.test ? signal.points : 0), 0));
        const present = signals.filter(signal => signal.test).map(signal => `- ${signal.label}`);
        const missing = signals.filter(signal => !signal.test).map(signal => `- 补充${signal.label}信号。`);
        const level = score >= 85 ? 'AI 读取基础较完整' : score >= 70 ? '已有基础，建议继续补强信任信号' : score >= 45 ? '需要补齐结构化和直答内容' : 'AI 读取基础偏弱';

        return [
            '# AI 友好度评分',
            '',
            `分析对象：${brand}${urls[0] ? `（${urls[0]}）` : ''}`,
            `综合评分：${score} / 100`,
            `判断：${level}`,
            '',
            '## 已识别信号',
            ...(present.length ? present : ['- 暂未识别到稳定信号。']),
            '',
            '## 优化建议',
            ...(missing.length ? missing : ['- 当前基础信号较完整，可以继续补充页面级案例和可引用数据。']),
            '',
            '## 下一步',
            '- 把页面核心事实拆成短句，并补充 FAQ、Schema、作者主体和引用来源。',
        ].join('\n');
    }

    function renderInlineMarkdown(text) {
        return escapeHtml(text)
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    }

    function renderSimpleMarkdown(markdown) {
        const lines = String(markdown || '').split('\n');
        const html = [];
        let listType = '';

        function closeList() {
            if (!listType) return;
            html.push(`</${listType}>`);
            listType = '';
        }

        lines.forEach(line => {
            const trimmed = line.trim();
            if (!trimmed) {
                closeList();
                return;
            }

            const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
            if (heading) {
                closeList();
                const level = heading[1].length;
                html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
                return;
            }

            const unordered = trimmed.match(/^[-*]\s+(.+)$/);
            if (unordered) {
                if (listType !== 'ul') {
                    closeList();
                    listType = 'ul';
                    html.push('<ul>');
                }
                html.push(`<li>${renderInlineMarkdown(unordered[1])}</li>`);
                return;
            }

            const ordered = trimmed.match(/^\d+\.\s+(.+)$/);
            if (ordered) {
                if (listType !== 'ol') {
                    closeList();
                    listType = 'ol';
                    html.push('<ol>');
                }
                html.push(`<li>${renderInlineMarkdown(ordered[1])}</li>`);
                return;
            }

            closeList();
            html.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
        });

        closeList();
        return html.join('');
    }

    function updateKbExportState() {
        const hasOutput = Boolean(value('#kb-output'));
        ['#kb-export-md', '#kb-export-word', '#kb-export-pdf'].forEach(selector => {
            const button = $(selector);
            if (button) button.disabled = !hasOutput;
        });
    }

    function updateKbPreview() {
        const preview = $('#kb-preview');
        if (!preview) return;
        const markdown = value('#kb-output');
        preview.innerHTML = markdown
            ? renderSimpleMarkdown(markdown)
            : '<p>生成后可在这里预览结构化知识库。</p>';
        updateKbExportState();
    }

    function downloadFile(fileName, mimeType, content) {
        const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }

    function buildKbExportHtml() {
        const title = inferBrand(value('#kb-brief') || value('#kb-output') || 'GEO知识库');
        const html = renderSimpleMarkdown(value('#kb-output'));
        return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>${escapeHtml(title)} GEO 知识库</title>
    <style>
        body { margin: 40px; color: #1f2937; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.75; }
        h1, h2, h3 { color: #0f172a; line-height: 1.35; }
        h1 { font-size: 28px; }
        h2 { margin-top: 28px; padding-top: 18px; border-top: 1px solid #e5e7eb; font-size: 21px; }
        h3 { margin-top: 18px; font-size: 17px; }
        li { margin: 4px 0; }
        code { background: #f1f5f9; color: #2563eb; padding: 2px 5px; border-radius: 4px; }
    </style>
</head>
<body>${html}</body>
</html>`;
    }

    function exportKbMarkdown() {
        const markdown = value('#kb-output');
        if (!markdown) return;
        const fileName = `${sanitizeFileName(inferBrand(value('#kb-brief') || markdown))}.md`;
        downloadFile(fileName, 'text/markdown', markdown);
        setKbStatus('已导出 Markdown 文件。', 'success');
    }

    function exportKbWord() {
        const markdown = value('#kb-output');
        if (!markdown) return;
        const fileName = `${sanitizeFileName(inferBrand(value('#kb-brief') || markdown))}.doc`;
        downloadFile(fileName, 'application/msword', buildKbExportHtml());
        setKbStatus('已导出 Word 文档。', 'success');
    }

    function exportKbPdf() {
        const markdown = value('#kb-output');
        if (!markdown) return;
        const printWindow = window.open('', '_blank');
        if (!printWindow) {
            setKbStatus('浏览器拦截了 PDF 打印窗口，请允许弹窗后重试。', 'error');
            return;
        }
        printWindow.document.open();
        printWindow.document.write(buildKbExportHtml());
        printWindow.document.close();
        printWindow.focus();
        printWindow.print();
        setKbStatus('已打开打印窗口，可选择“保存为 PDF”。', 'success');
    }

    async function copyTarget(targetId, button) {
        const target = document.getElementById(targetId);
        if (!target) return;
        const text = target.value || target.textContent || '';
        if (!text) return;
        try {
            await navigator.clipboard.writeText(text);
            const previous = button.innerHTML;
            button.innerHTML = '<span class="material-symbols-outlined">check</span>已复制';
            setTimeout(() => {
                button.innerHTML = previous;
            }, 1200);
        } catch (_) {
            target.focus();
            target.select?.();
            document.execCommand?.('copy');
        }
    }

    function initExamples() {
        setOutput('jsonld-output', EXAMPLES.jsonld);
        setOutput('llms-output', EXAMPLES.llms);
        setOutput('title-output', EXAMPLES.title);
        setOutput('kb-output', EXAMPLES.kb);
        setOutput('score-output', EXAMPLES.score);
        updateKbPreview();
    }

    function bind() {
        $$('[data-tool-tab]').forEach(button => {
            button.addEventListener('click', () => selectTool(button.dataset.toolTab));
        });
        $('#jsonld-generate')?.addEventListener('click', function () {
            void runWithLoading(this, '#jsonld-loading', 'jsonld-output', () => generateWithOptionalDirect('jsonld', buildJsonLdFromBrief));
        });
        $('#llms-generate')?.addEventListener('click', function () {
            void runWithLoading(this, '#llms-loading', 'llms-output', () => generateWithOptionalDirect('llms', buildLlmsFromBrief));
        });
        $('#title-generate')?.addEventListener('click', function () {
            void runWithLoading(this, '#title-loading', 'title-output', () => generateWithOptionalDirect('title', buildTitlesFromBrief));
        });
        $('#kb-generate')?.addEventListener('click', function () {
            void runWithLoading(this, '#kb-loading', 'kb-output', () => generateWithOptionalDirect('kb', buildKbFromBrief), updateKbPreview);
        });
        $('#score-run')?.addEventListener('click', function () {
            void runWithLoading(this, '#score-loading', 'score-output', () => generateWithOptionalDirect('score', buildScoreFromBrief));
        });
        $('#kb-files')?.addEventListener('change', handleKbFiles);
        $('#kb-output')?.addEventListener('input', updateKbPreview);
        $('#kb-export-md')?.addEventListener('click', exportKbMarkdown);
        $('#kb-export-word')?.addEventListener('click', exportKbWord);
        $('#kb-export-pdf')?.addEventListener('click', exportKbPdf);
        $$('[data-copy-target]').forEach(button => {
            button.addEventListener('click', () => copyTarget(button.dataset.copyTarget, button));
        });
        initExamples();
        void loadUsagePolicy();
    }

    document.addEventListener('DOMContentLoaded', bind);
})();
