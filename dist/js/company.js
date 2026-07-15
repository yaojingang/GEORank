/**
 * Company Detail Page - 动态公司详情
 */
(function () {
    'use strict';

    const API_BASE = ['80', '443', ''].includes(window.location.port)
        ? ''
        : `${window.location.protocol}//${window.location.hostname}:8000`;
    const Routes = window.GEOrank?.Routes;

    const elements = {
        heroLeft: document.getElementById('company-hero-left'),
        heroRight: document.getElementById('company-hero-right'),
        description: document.getElementById('company-description-section'),
        team: document.getElementById('company-team-section'),
        insightGrid: document.getElementById('company-insight-grid'),
        vectorStatus: document.getElementById('company-vector-status'),
        similarCompanies: document.getElementById('similar-companies'),
        diagnosticLink: document.getElementById('company-diagnostic-link'),
    };

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    function normalizeCompanyName(name) {
        const raw = String(name || '').trim();
        if (!raw) return '';
        const parts = raw.split(/\s*[|｜丨]\s*|\s+[—–-]\s+/).map((item) => item.trim()).filter(Boolean);
        const candidates = (parts.length ? parts : [raw]).map((item) => item.replace(/(官方网站|官网首页|官网|首页|主页)$/u, '').trim());
        return candidates.find((item) => item && !['官网', '官方网站', '首页', '主页'].includes(item)) || raw;
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

    function buildCompanyLink(companyOrId) {
        const identifier = typeof companyOrId === 'object'
            ? (companyOrId?.path_key || companyOrId?.id || '')
            : companyOrId;
        if (Routes?.buildCompanyDetail) {
            return Routes.buildCompanyDetail(identifier);
        }
        const url = new URL('/company', window.location.origin);
        if (typeof companyOrId === 'object' ? companyOrId?.id : companyOrId) {
            url.searchParams.set('id', typeof companyOrId === 'object' ? companyOrId.id : companyOrId);
        }
        return url.toString();
    }

    function buildDiagnosticLink(company) {
        if (Routes?.buildDiagnosticPath) {
            return Routes.buildDiagnosticPath({
                url: company?.url || '',
                companyId: company?.id || '',
            });
        }
        const url = new URL('/diagnostic', window.location.origin);
        if (company?.id) url.searchParams.set('company_id', company.id);
        if (company?.url) url.searchParams.set('url', company.url);
        return url.toString();
    }

    function getQueryCompanyId() {
        if (Routes?.readCompanyId) {
            return Routes.readCompanyId();
        }
        return new URLSearchParams(window.location.search).get('id');
    }

    function formatDate(value) {
        if (!value) return '--';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return new Intl.DateTimeFormat('zh-CN', {
            year: 'numeric',
            month: 'long',
        }).format(date);
    }

    function renderLogo(company) {
        const displayName = normalizeCompanyName(company.name) || company.name;
        if (company.logo_url) {
            return `<img alt="${escapeHtml(displayName)} Logo" class="w-16 h-16 object-contain" src="${escapeHtml(company.logo_url)}">`;
        }
        const initials = String(displayName || '?')
            .split(/\s+/)
            .map((part) => part.slice(0, 1))
            .join('')
            .slice(0, 2)
            .toUpperCase();
        return `<div class="w-16 h-16 flex items-center justify-center text-2xl font-extrabold text-primary">${escapeHtml(initials || '?')}</div>`;
    }

    function renderHero(company) {
        const displayName = normalizeCompanyName(company.name) || company.name;
        const tags = Array.isArray(company.tags) ? company.tags : [];
        const techLevel = company.tech_level || '技术等级待补充';
        const metaTags = [
            company.category,
            company.funding_stage,
            company.is_geo_certified ? 'GEO 认证合作伙伴' : null,
        ].filter(Boolean);

        if (elements.heroLeft) {
            elements.heroLeft.innerHTML = `
                <div class="flex flex-col justify-between gap-6">
                    <div class="flex items-center gap-6">
                        <div class="w-24 h-24 rounded-xl bg-slate-50 flex items-center justify-center overflow-hidden border border-slate-100">
                            ${renderLogo(company)}
                        </div>
                        <div class="min-w-0">
                            <h1 class="text-4xl md:text-5xl font-extrabold tracking-tight font-headline">${escapeHtml(displayName)}</h1>
                            <p class="text-on-surface-variant text-lg mt-2 font-medium">${escapeHtml(company.short_description || company.category || 'GEO 公司档案')}</p>
                        </div>
                    </div>
                    <div class="flex items-center justify-between gap-4 flex-wrap">
                        <div class="flex flex-wrap gap-2">
                            ${metaTags.map((tag, index) => `
                                <span class="${index === metaTags.length - 1 && company.is_geo_certified ? 'tag-primary px-3 py-1 rounded-full text-xs font-semibold' : 'tag'}">${escapeHtml(tag)}</span>
                            `).join('')}
                            ${tags.filter((tag) => !metaTags.includes(tag)).slice(0, 3).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                        </div>
                        <div class="flex items-center gap-2 shrink-0 flex-wrap">
                            <a href="${escapeHtml(company.url)}" target="_blank" rel="noreferrer" class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-white border border-slate-200 text-xs font-semibold text-slate-600 hover:border-primary hover:text-primary transition-colors">
                                <span class="material-symbols-outlined text-sm">language</span>
                                访问官网
                            </a>
                            <a href="${buildDiagnosticLink(company)}" class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-white border border-slate-200 text-xs font-semibold text-slate-600 hover:border-primary hover:text-primary transition-colors">
                                <span class="material-symbols-outlined text-sm">analytics</span>
                                申请深度诊断
                            </a>
                        </div>
                    </div>
                </div>
            `;
        }

        if (elements.heroRight) {
            elements.heroRight.innerHTML = `
                <div class="p-6 border border-slate-100 rounded-2xl space-y-4 h-full">
                    <div class="flex justify-between items-center text-sm">
                        <span class="text-on-surface-variant">总部</span>
                        <span class="font-semibold">${escapeHtml(company.headquarters || '--')}</span>
                    </div>
                    <div class="flex justify-between items-center text-sm">
                        <span class="text-on-surface-variant">成立日期</span>
                        <span class="font-semibold">${escapeHtml(company.founded_date ? formatDate(company.founded_date) : '--')}</span>
                    </div>
                    <div class="flex justify-between items-center text-sm">
                        <span class="text-on-surface-variant">员工规模</span>
                        <span class="font-semibold">${escapeHtml(company.employee_count || '--')}</span>
                    </div>
                    <div class="flex justify-between items-center text-sm">
                        <span class="text-on-surface-variant">技术等级</span>
                        <span class="font-semibold text-primary">${escapeHtml(techLevel)}</span>
                    </div>
                    <div class="flex justify-between items-center text-sm">
                        <span class="text-on-surface-variant">GEO 评分</span>
                        <span class="font-semibold">${company.geo_score != null ? `${Number(company.geo_score).toFixed(1)} / 100` : '--'}</span>
                    </div>
                    <div class="flex justify-between items-center text-sm">
                        <span class="text-on-surface-variant">人气热度</span>
                        <span class="font-semibold">${Number(company.upvotes || 0).toLocaleString('zh-CN')} 票</span>
                    </div>
                </div>
            `;
        }

        if (elements.diagnosticLink) {
            elements.diagnosticLink.href = buildDiagnosticLink(company);
        }
    }

    function renderDescription(company) {
        const sections = [];
        const description = company.description || company.short_description;
        if (description) {
            const paragraphs = String(description)
                .split(/\n{2,}/)
                .map((paragraph) => paragraph.trim())
                .filter(Boolean);
            sections.push(...paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`));
        } else {
            sections.push('<p>该公司暂未补充详细介绍。</p>');
        }

        if (Array.isArray(company.tech_stack) && company.tech_stack.length) {
            sections.push(`
                <h3 class="text-xl font-semibold pt-4">核心技术栈</h3>
                <ul class="list-disc pl-5 space-y-2">
                    ${company.tech_stack.map((item) => `<li><strong class="text-primary">${escapeHtml(item)}</strong></li>`).join('')}
                </ul>
            `);
        }

        if (elements.description) {
            elements.description.innerHTML = `
                <h2 class="!mt-0 text-2xl font-bold mb-6 flex items-center gap-2">
                    <span class="w-1.5 h-6 bg-primary rounded-full"></span>
                    深度介绍
                </h2>
                <div class="space-y-4 text-on-surface-variant leading-relaxed">
                    ${sections.join('')}
                </div>
            `;
        }
    }

    function renderTeam(company) {
        const members = Array.isArray(company.team_members) ? company.team_members : [];
        if (!elements.team) return;

        if (!members.length) {
            elements.team.innerHTML = `
                <h2 class="text-2xl font-bold mb-8 flex items-center gap-2">
                    <span class="w-1.5 h-6 bg-primary rounded-full"></span>
                    团队信息
                </h2>
                <div class="company-state-card">该公司暂未公开团队信息。</div>
            `;
            return;
        }

        elements.team.innerHTML = `
            <h2 class="text-2xl font-bold mb-8 flex items-center gap-2">
                <span class="w-1.5 h-6 bg-primary rounded-full"></span>
                创始团队
            </h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                ${members.map((member, index) => `
                    <div class="team-card flex items-center gap-4 p-6 bg-white border border-slate-100 rounded-xl hover:shadow-xl hover:shadow-slate-200/50 transition-all">
                        <div class="w-16 h-16 rounded-full bg-slate-100 overflow-hidden flex items-center justify-center text-lg font-extrabold text-primary">
                            ${escapeHtml((member.name || '?').slice(0, 1))}
                        </div>
                        <div>
                            <h4 class="font-bold">${escapeHtml(member.name || `成员 ${index + 1}`)}</h4>
                            <p class="text-xs text-on-surface-variant">${escapeHtml(member.role || '核心成员')}</p>
                            ${member.bg ? `<p class="text-[11px] text-slate-400 mt-1">${escapeHtml(member.bg)}</p>` : ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    function renderInsights(company) {
        if (!elements.insightGrid) return;
        const scores = company.geo_details || {};
        const scoreEntries = [
            ['Schema', scores.schema],
            ['Content', scores.content],
            ['Meta', scores.meta],
            ['Citation', scores.citation],
        ];
        const techStack = Array.isArray(company.tech_stack) ? company.tech_stack : [];

        elements.insightGrid.innerHTML = `
            <div class="bg-slate-50 rounded-2xl p-8 border border-slate-100">
                <div class="flex justify-between items-start mb-6">
                    <div>
                        <h3 class="font-bold text-lg">GEO 评分拆解</h3>
                        <p class="text-xs text-on-surface-variant">四大维度表现概览</p>
                    </div>
                    <span class="material-symbols-outlined text-primary">analytics</span>
                </div>
                <div class="space-y-4">
                    ${scoreEntries.map(([label, value]) => `
                        <div>
                            <div class="flex justify-between text-sm mb-1.5">
                                <span class="font-medium">${label}</span>
                                <span class="font-bold text-primary">${value != null ? Number(value).toFixed(0) : '--'}</span>
                            </div>
                            <div class="w-full h-2 bg-white rounded-full overflow-hidden">
                                <div class="h-full bg-primary rounded-full" style="width:${Math.max(0, Math.min(Number(value || 0), 100))}%"></div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="bg-white rounded-2xl p-8 border border-slate-100 flex flex-col">
                <div class="flex justify-between items-start mb-8">
                    <div>
                        <h3 class="font-bold text-lg">核心语义关键词</h3>
                        <p class="text-xs text-on-surface-variant">技术栈与品牌语义标签</p>
                    </div>
                    <span class="material-symbols-outlined text-primary">cloud</span>
                </div>
                <div class="flex flex-wrap gap-3 items-center">
                    ${(techStack.length ? techStack : company.tags || []).slice(0, 10).map((item, index) => `
                        <span class="${index % 3 === 0 ? 'text-2xl font-bold' : index % 3 === 1 ? 'text-lg font-semibold text-primary' : 'text-sm font-medium text-on-surface-variant'}">${escapeHtml(item)}</span>
                    `).join('') || '<span class="text-sm text-slate-400">暂无技术栈数据</span>'}
                </div>
            </div>
        `;
    }

    function renderVectorStatus(company) {
        if (!elements.vectorStatus) return;
        const progressMap = {
            pending: 10,
            crawling: 25,
            cleaning: 45,
            graph_building: 65,
            vectorizing: 85,
            completed: 100,
            failed: 0,
        };
        const progress = progressMap[String(company.pipeline_status || '').toLowerCase()] ?? 0;
        elements.vectorStatus.innerHTML = `
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                        <span class="material-symbols-outlined text-primary filled">data_check</span>
                    </div>
                    <div>
                        <h3 class="font-bold">知识库状态</h3>
                        <p class="text-xs text-on-surface-variant">入库流水线与语义化准备度</p>
                    </div>
                </div>
                <span class="text-2xl font-black text-primary">${progress}%</span>
            </div>
            <div class="w-full h-2 bg-white rounded-full overflow-hidden">
                <div class="h-full bg-primary rounded-full" style="width:${progress}%"></div>
            </div>
            <div class="mt-4 flex flex-wrap gap-4 text-xs text-on-surface-variant font-medium">
                <span>流水线状态：${escapeHtml(company.pipeline_status || '--')}</span>
                <span>发布状态：${escapeHtml(company.publish_status || '--')}</span>
                <span>GEO 评分：${company.geo_score != null ? Number(company.geo_score).toFixed(1) : '--'}</span>
            </div>
            ${company.pipeline_error ? `<p class="mt-3 text-xs text-red-500">${escapeHtml(company.pipeline_error)}</p>` : ''}
        `;
    }

    function renderSimilarCompanies(items) {
        if (!elements.similarCompanies) return;
        if (!Array.isArray(items) || !items.length) {
            elements.similarCompanies.innerHTML = '<div class="company-state-card">暂无相似公司推荐。</div>';
            return;
        }

        elements.similarCompanies.innerHTML = items.map((company) => `
            <a href="${buildCompanyLink(company)}" class="group flex items-center gap-4 p-4 rounded-xl border border-transparent hover:border-slate-100 hover:bg-slate-50 transition-all">
                <div class="w-12 h-12 bg-slate-100 rounded-lg shrink-0 overflow-hidden flex items-center justify-center text-sm font-extrabold text-primary">
                    ${company.logo_url ? `<img class="w-full h-full object-cover" src="${escapeHtml(company.logo_url)}" alt="${escapeHtml(company.name)}">` : escapeHtml(String(company.name || '?').slice(0, 1))}
                </div>
                <div class="min-w-0">
                    <h4 class="font-bold text-sm group-hover:text-primary transition-colors truncate">${escapeHtml(company.name)}</h4>
                    <p class="text-xs text-on-surface-variant truncate">${escapeHtml(company.short_description || company.category || '相似公司')}</p>
                </div>
            </a>
        `).join('');
    }

    async function resolveCompanyId() {
        const directId = getQueryCompanyId();
        if (directId) return directId;
        const listing = await request('/api/companies/?page=1&size=1&sort=geo_score');
        return listing.items?.[0]?.id || null;
    }

    async function init() {
        try {
            const companyId = await resolveCompanyId();
            if (!companyId) {
                throw new Error('当前没有可展示的公司资料');
            }

            const [company, similarCompanies] = await Promise.all([
                request(`/api/companies/${encodeURIComponent(companyId)}`),
                request(`/api/companies/${encodeURIComponent(companyId)}/similar?top_k=3`).catch(() => []),
            ]);

            renderHero(company);
            renderDescription(company);
            renderTeam(company);
            renderInsights(company);
            renderVectorStatus(company);
            renderSimilarCompanies(similarCompanies);

            if (Routes?.buildCompanyDetail && company?.id) {
                window.history.replaceState({ companyId: company.id }, '', Routes.buildCompanyDetail(company.path_key || company.id));
            }

            const detailTitle = `${company.name} - GEOrank`;
            document.title = window.GEOrank?.SiteSettings?.replaceBrand?.(detailTitle) || detailTitle;
            const meta = document.querySelector('meta[name="description"]');
            if (meta) {
                meta.setAttribute('content', company.short_description || company.description || '查看 GEO 公司详情');
            }
        } catch (error) {
            const message = escapeHtml(error.message || '加载失败');
            const fallback = `<div class="company-state-card company-state-card-error">加载公司详情失败：${message}</div>`;
            if (elements.heroLeft) elements.heroLeft.innerHTML = fallback;
            if (elements.heroRight) elements.heroRight.innerHTML = fallback;
            if (elements.description) elements.description.innerHTML = fallback;
            if (elements.team) elements.team.innerHTML = fallback;
            if (elements.insightGrid) elements.insightGrid.innerHTML = fallback;
            if (elements.vectorStatus) elements.vectorStatus.innerHTML = fallback;
            if (elements.similarCompanies) elements.similarCompanies.innerHTML = fallback;
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
