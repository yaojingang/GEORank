"""
公司详情页服务端渲染
"""
from __future__ import annotations

import json
from datetime import date, datetime
from html import escape
from typing import Iterable
from urllib.parse import urljoin

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.deps import DbSession
from app.models.company import Company, PipelineStatus, PublishStatus
from app.services.company_lookup import company_public_path, get_company_by_identifier
from app.services.company_profile import (
    company_profile_needs_hydration,
    ensure_company_profile,
    normalize_company_name,
)
from app.services.company_retrieval import fallback_similar_companies

router = APIRouter(include_in_schema=False)


def _absolute_url(request: Request, path: str) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if forwarded_host:
        scheme = forwarded_proto or request.url.scheme or "http"
        return f"{scheme}://{forwarded_host.rstrip('/')}/{path.lstrip('/')}"
    return urljoin(str(request.base_url), path.lstrip("/"))


def _render_json_ld(*payloads: dict) -> str:
    return "\n".join(
        f'<script type="application/ld+json">{json.dumps(payload, ensure_ascii=False)}</script>'
        for payload in payloads if payload
    )


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _normalize_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for item in values:
        if isinstance(item, dict):
            text = _normalize_text(item.get("name") or item.get("title") or item.get("label"))
        else:
            text = _normalize_text(str(item) if item is not None else "")
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _paragraphs(text: str | None) -> list[str]:
    if not text:
        return []
    paragraphs = []
    for block in (text or "").replace("\r", "").split("\n\n"):
        normalized = _normalize_text(block)
        if normalized:
            paragraphs.append(normalized)
    return paragraphs or ([_normalize_text(text)] if _normalize_text(text) else [])


def _company_keywords(company: Company) -> list[str]:
    company_name = normalize_company_name(company.name, fallback_name=company.name) or company.name
    keywords = [
        company_name,
        company.category,
        company.short_description,
        company.tech_level,
        company.headquarters,
    ]
    keywords.extend(_normalize_list(company.tags))
    keywords.extend(_normalize_list(company.tech_stack))
    deduped: list[str] = []
    for item in keywords:
        text = _normalize_text(item)
        if text and text not in deduped:
            deduped.append(text)
    return deduped[:20]


def _format_short_date(value: datetime | date | None) -> str:
    if not value:
        return "--"
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%Y/%m")


def _format_iso_date(value: datetime | date | None) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    return value.isoformat()


def _og_image(company: Company) -> str | None:
    if company.logo_url and company.logo_url.startswith(("http://", "https://")):
        return company.logo_url
    return None


def _progress_value(status: PipelineStatus | str | None) -> int:
    progress_map = {
        "pending": 10,
        "crawling": 25,
        "cleaning": 45,
        "graph_building": 65,
        "vectorizing": 85,
        "completed": 100,
        "failed": 0,
    }
    key = status.value if isinstance(status, PipelineStatus) else str(status or "").lower()
    return progress_map.get(key, 0)


def _logo_markup(company: Company) -> str:
    company_name = normalize_company_name(company.name, fallback_name=company.name) or company.name
    if company.logo_url:
        return (
            f'<img alt="{escape(company_name)} Logo" class="w-20 h-20 object-contain" '
            f'src="{escape(company.logo_url)}">'
        )
    initials = "".join(part[:1] for part in (company_name or "?").split())[:2].upper() or "?"
    return (
        '<div class="w-20 h-20 flex items-center justify-center text-3xl '
        f'font-extrabold text-primary">{escape(initials)}</div>'
    )


def _score_rows(company: Company) -> str:
    details = company.geo_details if isinstance(company.geo_details, dict) else {}
    rows = []
    for label, key in (
        ("Schema", "schema"),
        ("Content", "content"),
        ("Meta", "meta"),
        ("Citation", "citation"),
    ):
        value = float(details.get(key, 0) or 0)
        rows.append(
            f"""
            <div>
                <div class="flex items-center justify-between text-sm font-medium mb-1.5">
                    <span>{label}</span>
                    <span class="text-primary">{value:.0f}</span>
                </div>
                <div class="w-full h-2 bg-white rounded-full overflow-hidden">
                    <div class="h-full bg-primary rounded-full" style="width:{max(0, min(value, 100))}%"></div>
                </div>
            </div>
            """
        )
    return "".join(rows)


def _team_cards(company: Company) -> str:
    members = company.team_members if isinstance(company.team_members, list) else []
    if not members:
        return '<div class="company-state-card">该公司暂未公开团队信息。</div>'

    cards = []
    for index, member in enumerate(members):
        name = _normalize_text(member.get("name") if isinstance(member, dict) else None) or f"成员 {index + 1}"
        role = _normalize_text(member.get("role") if isinstance(member, dict) else None) or "核心成员"
        background = _normalize_text(member.get("bg") if isinstance(member, dict) else None)
        cards.append(
            f"""
            <article class="team-card flex items-center gap-4 p-6 bg-white border border-slate-100 rounded-xl hover:shadow-xl hover:shadow-slate-200/50 transition-all">
                <div class="w-16 h-16 rounded-full bg-slate-100 overflow-hidden flex items-center justify-center text-lg font-extrabold text-primary">
                    {escape(name[:1])}
                </div>
                <div>
                    <h4 class="font-bold">{escape(name)}</h4>
                    <p class="text-xs text-on-surface-variant">{escape(role)}</p>
                    {'<p class="text-[11px] text-slate-400 mt-1">' + escape(background) + '</p>' if background else ''}
                </div>
            </article>
            """
        )
    return f'<div class="grid grid-cols-1 md:grid-cols-2 gap-6">{"".join(cards)}</div>'


def _crawl_pages_markup(company: Company) -> str:
    pages = company.crawl_pages if isinstance(company.crawl_pages, list) else []
    if not pages:
        return '<div class="company-state-card">暂无抓取页面信息。</div>'

    items = []
    for index, page in enumerate(pages[:3]):
        role = _normalize_text(page.get("role") if isinstance(page, dict) else None) or f"页面 {index + 1}"
        title = _normalize_text(page.get("title") if isinstance(page, dict) else None) or _normalize_text(page.get("url") if isinstance(page, dict) else None) or "未命名页面"
        reason = _normalize_text(page.get("reason") if isinstance(page, dict) else None) or "该页面被优先纳入企业知识库抽取。"
        url = _normalize_text(page.get("url") if isinstance(page, dict) else None)
        items.append(
            f"""
            <li class="p-5 rounded-2xl border border-slate-100 bg-white">
                <p class="text-xs uppercase tracking-[0.18em] text-slate-400 mb-2">{escape(role)}</p>
                <h4 class="text-lg font-bold text-slate-900">{escape(title)}</h4>
                <p class="mt-2 text-sm leading-7 text-slate-600">{escape(reason)}</p>
                {'<p class="mt-3 text-xs text-slate-400 break-all">' + escape(url) + '</p>' if url else ''}
            </li>
            """
        )
    return f'<ul class="space-y-4">{"".join(items)}</ul>'


def _similar_companies_markup(companies: Iterable[Company]) -> str:
    cards = []
    for company in companies:
        company_name = normalize_company_name(company.name, fallback_name=company.name) or company.name
        score = f"{float(company.geo_score):.1f}" if company.geo_score is not None else "--"
        cards.append(
            f"""
            <a href="{company_public_path(company)}" class="block p-4 rounded-2xl border border-slate-100 bg-white hover:border-primary/30 hover:shadow-lg hover:shadow-slate-200/40 transition-all">
                <p class="text-base font-bold text-slate-900">{escape(company_name)}</p>
                <p class="text-sm text-slate-500 mt-2 line-clamp-2">{escape(_normalize_text(company.short_description) or '查看该公司详情与 GEO 表现。')}</p>
                <div class="mt-3 flex items-center justify-between text-xs text-slate-400">
                    <span>{escape(_normalize_text(company.category) or '公司档案')}</span>
                    <span class="font-semibold text-primary">GEO {score}</span>
                </div>
            </a>
            """
        )
    if not cards:
        return '<div class="company-state-card">暂无相似公司数据。</div>'
    return f'<div class="space-y-3">{"".join(cards)}</div>'


def _brand_summary_markup(
    company: Company,
    *,
    tags: list[str],
    tech_stack: list[str],
    pages: list[dict[str, Any]],
    members: list[dict[str, Any]],
) -> str:
    lines: list[str] = []

    category = _normalize_text(company.category) or "公司档案"
    headquarters = _normalize_text(company.headquarters)
    founded = company.founded_date.strftime("%Y/%m") if company.founded_date else None
    employee_count = _normalize_text(company.employee_count)
    service_terms = "、".join(tags[:4]) if tags else "品牌资料、结构化内容与 AI 可读性优化"
    line_one_parts = [f"该公司当前被归类为 {category}"]
    if headquarters:
        line_one_parts.append(f"主要区域信息为 {headquarters}")
    if founded:
        line_one_parts.append(f"公开成立时间为 {founded}")
    if employee_count:
        line_one_parts.append(f"员工规模为 {employee_count}")
    line_one = "，".join(line_one_parts) + f"。当前沉淀的核心主题包括 {service_terms}。"
    lines.append(line_one)

    if pages:
        page_titles = []
        for page in pages[:3]:
            if isinstance(page, dict):
                title = _normalize_text(page.get("title")) or _normalize_text(page.get("role")) or _normalize_text(page.get("url"))
                if title:
                    page_titles.append(title)
        if page_titles:
            lines.append(f"知识库优先采集了 {len(page_titles)} 个高优先级页面，当前关键来源包括 {('、'.join(page_titles))}。")

    capability_bits = []
    if tech_stack:
        capability_bits.append(f"技术语义聚焦在 {('、'.join(tech_stack[:3]))}")
    if members:
        capability_bits.append(f"团队侧已识别 {len(members)} 个组织节点")
    if capability_bits:
        lines.append("；".join(capability_bits) + "。")

    return "".join(f"<p>{escape(line)}</p>" for line in lines if line)


def _brand_summary_support_markup(tags: list[str], tech_stack: list[str], pages: list[dict], members: list[dict]) -> str:
    source_titles: list[str] = []
    for page in pages[:3]:
        if isinstance(page, dict):
            title = _normalize_text(page.get("title")) or _normalize_text(page.get("role")) or _normalize_text(page.get("url"))
            if title:
                source_titles.append(title)
    themes = []
    for item in [*tags[:4], *tech_stack[:2]]:
        text = _normalize_text(item)
        if text and text not in themes:
            themes.append(text)

    facts = [
        ("抓取页面", str(len(pages))),
        ("语义标签", str(len(tags))),
        ("技术主题", str(len(tech_stack))),
        ("团队节点", str(len(members))),
    ]
    fact_tiles = []
    for label, value in facts:
        fact_tiles.append(
            f"""
            <div class="company-summary-fact">
                <span class="company-summary-fact-label">{escape(label)}</span>
                <strong class="company-summary-fact-value">{escape(value)}</strong>
            </div>
            """
        )

    source_list = "".join(
        f'<li class="company-summary-list-item">{escape(title)}</li>' for title in source_titles
    ) or '<li class="company-summary-list-item">当前暂无明确来源页</li>'
    theme_chips = "".join(
        f'<span class="company-summary-chip">{escape(theme)}</span>' for theme in themes
    ) or '<span class="company-summary-chip">待补充主题</span>'

    return f"""
    <aside class="company-summary-side">
        <div class="company-summary-fact-grid">
            {"".join(fact_tiles)}
        </div>
        <div class="company-summary-panel">
            <p class="company-summary-panel-label">关键来源</p>
            <ul class="company-summary-list">{source_list}</ul>
        </div>
        <div class="company-summary-panel">
            <p class="company-summary-panel-label">核心主题</p>
            <div class="company-summary-chip-wrap">{theme_chips}</div>
        </div>
    </aside>
    """


def _readability_support_markup(company: Company, tags: list[str], tech_stack: list[str], pages: list[dict]) -> str:
    lines = []
    if company.publish_status == PublishStatus.PUBLISHED:
        lines.append("公开页已直出 HTML 正文与公司资料，搜索引擎可直接读取核心内容。")
    if tags:
        lines.append(f"当前已显式输出 {len(tags)} 个语义标签，便于生成式引擎建立品牌主题。")
    if tech_stack:
        lines.append(f"技术主题已沉淀为 {', '.join(tech_stack[:2])} 等可读节点。")
    if pages:
        lines.append(f"关键来源页已锁定 {len(pages)} 个，用于保证知识库主入口稳定。")

    if not lines:
        lines.append("当前页面已具备基础公司资料与结构化摘要输出。")

    rendered = "".join(
        f'<li class="company-summary-list-item">{escape(line)}</li>' for line in lines[:4]
    )
    return f"""
    <div class="company-summary-panel">
        <p class="company-summary-panel-label">机器读取要点</p>
        <ul class="company-summary-list">{rendered}</ul>
    </div>
    """


def _completeness_summary_markup(company: Company, tags: list[str], tech_stack: list[str], pages: list[dict], members: list[dict]) -> str:
    items = [
        bool(_normalize_text(company.description) or _normalize_text(company.short_description)),
        bool(tags),
        bool(tech_stack),
        bool(pages),
        bool(members),
        bool(_normalize_text(company.headquarters)),
    ]
    complete = sum(1 for item in items if item)
    return f"""
    <div class="company-summary-fact-grid company-summary-fact-grid--compact">
        <div class="company-summary-fact">
            <span class="company-summary-fact-label">已具备项</span>
            <strong class="company-summary-fact-value">{complete}/6</strong>
        </div>
        <div class="company-summary-fact">
            <span class="company-summary-fact-label">待增强项</span>
            <strong class="company-summary-fact-value">{6 - complete}</strong>
        </div>
    </div>
    """


def _hero_title_class(display_name: str) -> str:
    length = len(display_name or "")
    if length >= 28:
        return "company-hero-title company-hero-title--compact"
    if length >= 18:
        return "company-hero-title company-hero-title--medium"
    return "company-hero-title"


def _build_signal_items(company: Company, progress: int, tags: list[str], tech_stack: list[str], pages: list[dict], members: list[dict]) -> list[dict]:
    geo_details = company.geo_details if isinstance(company.geo_details, dict) else {}
    page_count = len(pages)
    team_count = len(members)
    signals = [
        {
            "label": "结构化完备度",
            "value": int(float(geo_details.get("schema", 0) or 0)),
            "hint": "Schema、FAQ、Breadcrumb 等可机器读取结构",
        },
        {
            "label": "答案资产密度",
            "value": int(float(geo_details.get("content", 0) or 0)),
            "hint": "页面是否包含可直接引用的答案段落与说明",
        },
        {
            "label": "预览可读性",
            "value": int(float(geo_details.get("meta", 0) or 0)),
            "hint": "Title、Description、OG 与预览摘要质量",
        },
        {
            "label": "外部背书力",
            "value": int(float(geo_details.get("citation", 0) or 0)),
            "hint": "品牌引用、权威来源与站外可验证性",
        },
        {
            "label": "知识覆盖率",
            "value": min(100, page_count * 24 + len(tags) * 6 + len(tech_stack) * 12 + team_count * 15),
            "hint": "抓取来源页、标签、技术栈与团队实体的覆盖广度",
        },
        {
            "label": "入库准备度",
            "value": progress,
            "hint": "知识库从抓取、清洗到语义整理的完成程度",
        },
    ]
    return signals


def _metric_strip_markup(company: Company, progress: int, tags: list[str], tech_stack: list[str], pages: list[dict], members: list[dict]) -> str:
    cards = [
        ("GEO 总分", f"{float(company.geo_score):.1f}" if company.geo_score is not None else "--", "当前公司被 AI 读取与推荐的综合指数"),
        ("知识节点", str(len(tags) + len(tech_stack) + len(members)), "品牌、技术、团队与语义标签的实体数量"),
        ("来源页面", str(len(pages)), "最终被纳入企业知识库构建的优先页面"),
        ("准备度", f"{progress}%", "官网资料进入 GEO 知识库后的结构化成熟度"),
    ]
    rendered = []
    for label, value, hint in cards:
        rendered.append(
            f"""
            <article class="company-metric-card">
                <p class="company-metric-label">{escape(label)}</p>
                <p class="company-metric-value">{escape(value)}</p>
                <p class="company-metric-hint">{escape(hint)}</p>
            </article>
            """
        )
    return "".join(rendered)


def _signal_matrix_markup(company: Company, progress: int, tags: list[str], tech_stack: list[str], pages: list[dict], members: list[dict]) -> str:
    cards = []
    for item in _build_signal_items(company, progress, tags, tech_stack, pages, members):
        value = max(0, min(int(item["value"]), 100))
        cards.append(
            f"""
            <article class="company-signal-card">
                <div class="flex items-start justify-between gap-4">
                    <div>
                        <h4 class="company-signal-title">{escape(item["label"])}</h4>
                        <p class="company-signal-hint">{escape(item["hint"])}</p>
                    </div>
                    <span class="company-signal-score">{value}</span>
                </div>
                <div class="company-signal-bar">
                    <span class="company-signal-bar-fill" style="width:{value}%"></span>
                </div>
            </article>
            """
        )
    return f'<div class="company-signal-grid">{"".join(cards)}</div>'


def _score_dashboard_support_markup(company: Company) -> str:
    geo_details = company.geo_details if isinstance(company.geo_details, dict) else {}
    labels = {
        "schema": "结构化",
        "content": "答案内容",
        "meta": "预览元信息",
        "citation": "外部背书",
    }
    values = {key: int(float(geo_details.get(key, 0) or 0)) for key in labels}
    strongest_key = max(values, key=values.get) if values else "schema"
    weakest_key = min(values, key=values.get) if values else "citation"
    average = round(sum(values.values()) / max(len(values), 1))
    priority_map = {
        "schema": "补齐 Organization / WebSite / FAQPage 等结构化标签",
        "content": "增加 FAQ、案例和答案段落，提升可引用内容密度",
        "meta": "优化 Title、Description 与 OG，强化预览摘要",
        "citation": "补强案例、合作伙伴与权威来源的外部背书",
    }
    strongest_value = values[strongest_key]
    weakest_value = values[weakest_key]

    return f"""
    <div class="company-score-dashboard">
        <div class="company-score-overview">
            <div class="company-score-overview-main">
                <p class="company-score-overview-label">综合表现</p>
                <div class="company-score-overview-number-row">
                    <strong class="company-score-overview-number">{average}</strong>
                    <span class="company-score-overview-caption">平均分</span>
                </div>
                <p class="company-score-overview-text">四个核心 GEO 维度的整体表现，用来衡量当前资料被搜索引擎和生成式引擎理解的稳定度。</p>
            </div>
            <div class="company-score-overview-facts">
                <div class="company-score-overview-fact">
                    <span class="company-score-overview-fact-label">优势维度</span>
                    <strong class="company-score-overview-fact-value">{escape(labels[strongest_key])}</strong>
                    <span class="company-score-overview-fact-hint">{strongest_value} 分，当前最容易被机器理解</span>
                </div>
                <div class="company-score-overview-fact">
                    <span class="company-score-overview-fact-label">短板维度</span>
                    <strong class="company-score-overview-fact-value">{escape(labels[weakest_key])}</strong>
                    <span class="company-score-overview-fact-hint">{weakest_value} 分，建议优先补齐</span>
                </div>
            </div>
        </div>

        <div class="company-score-bars-card">
            <div class="company-score-bars-card-head">
                <p class="company-score-bars-card-label">维度拆解</p>
                <p class="company-score-bars-card-caption">从结构、答案内容、预览元信息和外部背书四个方向查看当前状态。</p>
            </div>
            <div class="company-score-bars">
                {_score_rows(company)}
            </div>
        </div>

        <div class="company-score-action-grid">
            <div class="company-score-action-card">
                <p class="company-score-action-label">当前优势</p>
                <strong class="company-score-action-title">{escape(labels[strongest_key])}</strong>
                <p class="company-score-action-text">这一维度说明当前页面已经形成较稳定的机器可读信号，适合继续扩展到更多重点页面。</p>
            </div>
            <div class="company-score-action-card company-score-action-card--primary">
                <p class="company-score-action-label">优先动作</p>
                <strong class="company-score-action-title">{escape(labels[weakest_key])}</strong>
                <p class="company-score-action-text">{escape(priority_map[weakest_key])}</p>
            </div>
        </div>
    </div>
    """


def _semantic_cloud_markup(terms: list[str]) -> str:
    if not terms:
        return '<div class="company-state-card">暂无可展示的语义标签。</div>'

    cloud = []
    for index, term in enumerate(terms[:14]):
        level = ["lg", "md", "sm"][index % 3]
        cloud.append(f'<span class="semantic-pill semantic-pill--{level}">{escape(term)}</span>')
    return f'<div class="semantic-cloud">{"".join(cloud)}</div>'


def _knowledge_graph_markup(company: Company, related_terms: list[str], tags: list[str], tech_stack: list[str]) -> str:
    display_name = normalize_company_name(company.name, fallback_name=company.name) or company.name
    orbit_items = [company.category, company.headquarters, *tech_stack[:3], *tags[:4], *related_terms[:4]]
    nodes: list[str] = []
    seen = set()
    for item in orbit_items:
        text = _normalize_text(item)
        if text and text not in seen and text != display_name:
            seen.add(text)
            nodes.append(text)
    if not nodes:
        return '<div class="company-state-card">暂无足够的实体节点生成语义图谱。</div>'

    rendered = []
    for index, node in enumerate(nodes[:8]):
        rendered.append(
            f'<span class="company-graph-node company-graph-node--{(index % 4) + 1}">{escape(node)}</span>'
        )
    return f"""
    <div class="company-graph">
        <div class="company-graph-center">
            <div class="company-graph-center-label">Company</div>
            <div class="company-graph-center-name">{escape(display_name)}</div>
        </div>
        <div class="company-graph-orbit">
            {"".join(rendered)}
        </div>
    </div>
    """


def _source_structure_markup(company: Company) -> str:
    pages = company.crawl_pages if isinstance(company.crawl_pages, list) else []
    if not pages:
        return '<div class="company-state-card">暂无来源结构数据。</div>'

    role_weights = {
        "homepage": 100,
        "about": 86,
        "team": 82,
        "product": 78,
        "faq": 70,
        "case": 74,
    }
    cards = []
    for index, page in enumerate(pages[:4]):
        role = _normalize_text(page.get("role") if isinstance(page, dict) else None) or f"页面 {index + 1}"
        title = _normalize_text(page.get("title") if isinstance(page, dict) else None) or "未命名页面"
        score = role_weights.get(role.lower(), max(48, 80 - index * 8))
        cards.append(
            f"""
            <article class="source-role-card">
                <div class="flex items-center justify-between gap-4">
                    <div>
                        <p class="source-role-label">{escape(role)}</p>
                        <h4 class="source-role-title">{escape(title)}</h4>
                    </div>
                    <span class="source-role-score">{score}</span>
                </div>
                <div class="company-signal-bar mt-3">
                    <span class="company-signal-bar-fill" style="width:{score}%"></span>
                </div>
            </article>
            """
        )
    return f'<div class="space-y-4">{"".join(cards)}</div>'


def _tech_stack_markup(company: Company, tags: list[str], tech_stack: list[str]) -> str:
    if not tech_stack and not tags:
        return '<div class="company-state-card">暂无技术与语义资产信息。</div>'

    chips = []
    for item in tech_stack[:6]:
        chips.append(f'<span class="asset-chip asset-chip--primary">{escape(item)}</span>')
    for item in tags[:6]:
        chips.append(f'<span class="asset-chip">{escape(item)}</span>')

    asset_rows = [
        ("技术栈数量", str(len(tech_stack))),
        ("语义标签数", str(len(tags))),
        ("结构化得分", str(int(float((company.geo_details or {}).get("schema", 0) or 0)))),
        ("内容得分", str(int(float((company.geo_details or {}).get("content", 0) or 0)))),
    ]
    rows = []
    for label, value in asset_rows:
        rows.append(
            f"""
            <div class="company-mini-stat">
                <span class="company-mini-stat-label">{escape(label)}</span>
                <strong class="company-mini-stat-value">{escape(value)}</strong>
            </div>
            """
        )
    return f"""
    <div class="space-y-5">
        <div class="asset-chip-wrap">{"".join(chips)}</div>
        <div class="company-mini-stat-grid">{"".join(rows)}</div>
    </div>
    """


def _team_signal_markup(company: Company) -> str:
    members = company.team_members if isinstance(company.team_members, list) else []
    pages = company.crawl_pages if isinstance(company.crawl_pages, list) else []
    preferred_pages = []
    for page in pages[:3]:
        if isinstance(page, dict):
            title = _normalize_text(page.get("title")) or _normalize_text(page.get("role")) or "来源页"
            preferred_pages.append(title)

    support_pages = "".join(
        f'<li class="company-summary-list-item">{escape(title)}</li>' for title in preferred_pages
    ) or '<li class="company-summary-list-item">建议继续补抓 About / Team / Leadership 页面。</li>'

    if members:
        role_names = []
        for member in members[:4]:
            if isinstance(member, dict):
                role = _normalize_text(member.get("role")) or _normalize_text(member.get("name"))
                if role and role not in role_names:
                    role_names.append(role)
        role_chips = "".join(
            f'<span class="company-summary-chip">{escape(role)}</span>' for role in role_names
        ) or '<span class="company-summary-chip">核心成员</span>'
        return f"""
        <div class="company-organization-layout">
            <div class="company-organization-member-grid">
                {_team_cards(company)}
            </div>
            <div class="company-organization-support">
                <div class="company-summary-panel">
                    <p class="company-summary-panel-label">角色覆盖</p>
                    <div class="company-summary-chip-wrap">{role_chips}</div>
                </div>
                <div class="company-summary-panel">
                    <p class="company-summary-panel-label">关键来源</p>
                    <ul class="company-summary-list">{support_pages}</ul>
                </div>
            </div>
        </div>
        """
    preferred_text = "、".join(preferred_pages) if preferred_pages else "About / Team / Leadership"
    cards = [
        ("当前判断", "人物实体密度偏低，但品牌档案和技术语义已经完成入库。"),
        ("建议抓取", f"下一轮优先补抓 {preferred_text}，增强组织信号。"),
        ("目标结果", "补齐核心成员、职责分工和公开团队页面，提高可信度与引用稳定性。"),
    ]
    rendered = []
    for label, value in cards:
        rendered.append(
            f"""
            <article class="company-organization-note">
                <p class="company-organization-note-label">{escape(label)}</p>
                <p class="company-organization-note-text">{escape(value)}</p>
            </article>
            """
        )
    action_chips = "".join(
        f'<span class="company-summary-chip">{escape(item)}</span>'
        for item in ("团队页", "高管介绍", "作者署名", "案例署名")
    )
    return f"""
    <div class="company-organization-layout">
        <div class="company-organization-grid">{"".join(rendered)}</div>
        <div class="company-organization-support">
            <div class="company-summary-panel">
                <p class="company-summary-panel-label">优先页面</p>
                <ul class="company-summary-list">{support_pages}</ul>
            </div>
            <div class="company-summary-panel">
                <p class="company-summary-panel-label">增强目标</p>
                <div class="company-summary-chip-wrap">{action_chips}</div>
            </div>
        </div>
    </div>
    """


def _action_roadmap_markup(company: Company) -> str:
    geo_details = company.geo_details if isinstance(company.geo_details, dict) else {}
    playbook = {
        "schema": ("补结构化", "补齐 Organization / WebSite / FAQPage / BreadcrumbList", "让实体、页面类型和问答结构更容易被生成式引擎识别。"),
        "content": ("补答案层", "重构产品页、FAQ 与案例页的答案段落", "增加可直接引用的定义、步骤、对比与结论段落。"),
        "meta": ("补预览层", "重写 title、description、canonical 与 Open Graph", "提升搜索预览质量和摘要生成的稳定性。"),
        "citation": ("补背书层", "增加案例引用、合作伙伴与权威来源链接", "增强可信度与可验证性，降低答案生成时的风险。"),
    }
    ordered = sorted(
        ((key, int(float(geo_details.get(key, 0) or 0))) for key in ("schema", "content", "meta", "citation")),
        key=lambda item: item[1],
    )
    phases = [
        ("Phase 01", "7 天内", ordered[:2]),
        ("Phase 02", "30 天内", ordered[2:3]),
        ("Phase 03", "90 天内", ordered[3:4]),
    ]
    columns = []
    for phase_code, phase_label, phase_items in phases:
        actions = []
        for key, _score in phase_items:
            title, action, desc = playbook[key]
            actions.append(
                f"""
                <li>
                    <p class="company-roadmap-item-title">{escape(title)}</p>
                    <p class="company-roadmap-item-text">{escape(action)}</p>
                    <p class="company-roadmap-item-desc">{escape(desc)}</p>
                </li>
                """
            )
        columns.append(
            f"""
            <article class="company-roadmap-column">
                <p class="company-roadmap-phase">{escape(phase_code)}</p>
                <h4 class="company-roadmap-title">{escape(phase_label)}</h4>
                <ul class="space-y-4 mt-4">
                    {"".join(actions) if actions else '<li><p class="company-roadmap-item-text">当前该阶段暂无新增动作。</p></li>'}
                </ul>
            </article>
            """
        )
    return f'<div class="company-roadmap-grid">{"".join(columns)}</div>'


def _snapshot_rows(company: Company, progress: int) -> str:
    rows = [
        ("GEO 评分", f"{float(company.geo_score):.1f} / 100" if company.geo_score is not None else "--"),
        ("知识库状态", company.pipeline_status.value),
        ("发布时间", _format_short_date(company.updated_at or company.created_at)),
        ("成立时间", _format_short_date(company.founded_date)),
        ("员工规模", _normalize_text(company.employee_count) or "--"),
        ("技术等级", _normalize_text(company.tech_level) or "--"),
    ]
    return "".join(
        f"""
        <div class="company-snapshot-row">
            <span class="text-on-surface-variant">{escape(label)}</span>
            <strong>{escape(value)}</strong>
        </div>
        """
        for label, value in rows
    ) + f"""
        <div class="pt-2">
            <div class="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                <div class="h-full bg-primary rounded-full" style="width:{progress}%"></div>
            </div>
            <p class="mt-2 text-xs text-slate-400">当前企业知识库准备度 {progress}%</p>
        </div>
    """


def _hero_fact_tiles(company: Company, tags: list[str], tech_stack: list[str], pages: list[dict], members: list[dict]) -> str:
    fact_pairs = [
        ("分类", _normalize_text(company.category) or "公司档案"),
        ("区域", _normalize_text(company.headquarters) or "待补充"),
        ("来源页", str(len(pages) or 0)),
        ("语义节点", str(len(tags) + len(tech_stack) + len(members))),
    ]
    tiles = []
    for label, value in fact_pairs:
        tiles.append(
            f"""
            <div class="company-hero-fact">
                <span class="company-hero-fact-label">{escape(label)}</span>
                <strong class="company-hero-fact-value">{escape(value)}</strong>
            </div>
            """
        )
    return "".join(tiles)


def _completeness_markup(company: Company, tags: list[str], tech_stack: list[str], pages: list[dict], members: list[dict]) -> str:
    items = [
        ("公司简介", bool(_normalize_text(company.description) or _normalize_text(company.short_description))),
        ("语义标签", bool(tags)),
        ("技术栈", bool(tech_stack)),
        ("来源页面", bool(pages)),
        ("团队实体", bool(members)),
        ("地区信息", bool(_normalize_text(company.headquarters))),
    ]
    rows = []
    for label, ready in items:
        rows.append(
            f"""
            <li class="company-check-row">
                <span>{escape(label)}</span>
                <span class="company-check-badge {'company-check-badge--ok' if ready else 'company-check-badge--pending'}">{'已具备' if ready else '待增强'}</span>
            </li>
            """
        )
    return f'<ul class="space-y-3">{"".join(rows)}</ul>'


def _company_structured_data(request: Request, company: Company, canonical_url: str, description: str, keywords: list[str]) -> str:
    company_name = normalize_company_name(company.name, fallback_name=company.name) or company.name
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": _absolute_url(request, "/")},
            {"@type": "ListItem", "position": 2, "name": "公司", "item": _absolute_url(request, "/")},
            {"@type": "ListItem", "position": 3, "name": company_name, "item": canonical_url},
        ],
    }

    organization = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": canonical_url,
        "name": company_name,
        "url": company.url,
        "description": description,
        "identifier": str(company.id),
        "keywords": ", ".join(keywords),
        "knowsAbout": keywords,
    }
    if company.logo_url:
        organization["logo"] = company.logo_url
    if company.headquarters:
        organization["location"] = {
            "@type": "Place",
            "name": company.headquarters,
            "address": company.headquarters,
        }
    if company.founded_date:
        organization["foundingDate"] = _format_iso_date(company.founded_date)
    if company.employee_count:
        organization["numberOfEmployees"] = company.employee_count

    webpage = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": f"{company_name} - GEOrank 公司档案",
        "description": description,
        "url": canonical_url,
        "mainEntity": {"@id": canonical_url},
        "about": keywords[:8],
        "isPartOf": {
            "@type": "WebSite",
            "name": "GEOrank",
            "url": _absolute_url(request, "/"),
        },
    }

    return _render_json_ld(breadcrumbs, organization, webpage)


def _render_meta_tags(
    *,
    title: str,
    description: str,
    canonical_url: str,
    keywords: list[str],
    cover_image_url: str | None,
    allow_index: bool,
) -> str:
    robots = "index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1" if allow_index else "noindex,nofollow"
    tags = [
        f"<title>{escape(title)}</title>",
        f'<meta name="description" content="{escape(description)}">',
        f'<meta name="robots" content="{escape(robots)}">',
        f'<meta name="keywords" content="{escape(", ".join(keywords))}">',
        f'<link rel="canonical" href="{escape(canonical_url)}">',
        '<meta property="og:site_name" content="GEOrank">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:title" content="{escape(title)}">',
        f'<meta property="og:description" content="{escape(description)}">',
        f'<meta property="og:url" content="{escape(canonical_url)}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{escape(title)}">',
        f'<meta name="twitter:description" content="{escape(description)}">',
    ]
    if cover_image_url:
        tags.append(f'<meta property="og:image" content="{escape(cover_image_url)}">')
        tags.append(f'<meta name="twitter:image" content="{escape(cover_image_url)}">')
    return "\n    ".join(tags)


def _render_page(
    *,
    request: Request,
    company: Company,
    similar_companies: list[Company],
) -> HTMLResponse:
    display_name = normalize_company_name(company.name, fallback_name=company.name) or company.name
    canonical_url = _absolute_url(request, company_public_path(company))
    allow_index = company.publish_status == PublishStatus.PUBLISHED
    short_description = _normalize_text(company.short_description) or "查看该公司的 GEO 资料、技术栈、团队信息与相似推荐。"
    description = _normalize_text(company.description) or short_description
    title = f"{display_name} - GEO 公司档案 | GEOrank"
    keywords = _company_keywords(company)
    progress = _progress_value(company.pipeline_status)
    meta_tags = _render_meta_tags(
        title=title,
        description=short_description,
        canonical_url=canonical_url,
        keywords=keywords,
        cover_image_url=_og_image(company),
        allow_index=allow_index,
    )
    structured_data = _company_structured_data(request, company, canonical_url, short_description, keywords)
    tags = _normalize_list(company.tags)
    tech_stack = _normalize_list(company.tech_stack)
    pages = company.crawl_pages if isinstance(company.crawl_pages, list) else []
    members = company.team_members if isinstance(company.team_members, list) else []
    brand_summary_html = _brand_summary_markup(
        company,
        tags=tags,
        tech_stack=tech_stack,
        pages=pages,
        members=members,
    )
    related_terms = (tech_stack + tags)[:12]
    meta_chips = [chip for chip in [company.category, company.funding_stage, company.headquarters] if _normalize_text(chip)]
    hero_title_class = _hero_title_class(display_name)
    score_value = max(0.0, min(float(company.geo_score or 0), 100.0))
    score_ratio = f"{score_value:.1f}"
    readiness_text = (
        "该页面已经将品牌名称、简介、抓取来源、技术语义和 GEO 评分拆解直接输出到 HTML，便于搜索引擎和生成式引擎优先理解核心资料。"
        if progress >= 70
        else "当前页面已具备基础资料输出，但仍建议继续补强结构化标记、答案层与外部背书，提升 AI 优先读取能力。"
    )
    preview_notice = ""
    if company.publish_status != PublishStatus.PUBLISHED:
        preview_notice = """
        <div class="mb-6 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm leading-7 text-amber-700">
            当前页面为审核预览状态，尚未在公开目录中放出；搜索引擎将收到 noindex。
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    {meta_tags}
    <style>body{{opacity:0;transition:opacity 0.15s ease}}</style>
    <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
    <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
    <script src="/js/tailwind.config.js"></script>
    <link rel="stylesheet" href="/css/common.css?v=20260613-common-hidden-fix">
    <link rel="stylesheet" href="/css/company.css">
    {structured_data}
</head>
<body class="bg-white text-on-surface antialiased overflow-x-hidden company-page">
    <div id="header-container"></div>

    <div class="company-page-shell">
        <div class="company-glow company-glow--blue"></div>
        <div class="company-glow company-glow--violet"></div>
        <div class="max-w-7xl mx-auto px-4 md:px-6 lg:px-8 pt-24 md:pt-32 pb-16 md:pb-24">
        <main class="company-page-content">
            <section class="company-page-hero">
                <nav class="flex flex-wrap items-center gap-1 text-xs font-medium text-slate-400">
                    <a href="/" class="hover:text-primary transition-colors">首页</a>
                    <span class="material-symbols-outlined text-[14px]">chevron_right</span>
                    <a href="/" class="hover:text-primary transition-colors">公司</a>
                    <span class="material-symbols-outlined text-[14px]">chevron_right</span>
                    <span class="text-on-surface">{escape(display_name)}</span>
                </nav>

                {preview_notice}

                <div class="company-hero-shell">
                    <div class="company-hero-main company-card">
                        <div class="company-hero-top">
                            <div class="company-hero-brand">
                                <div class="company-hero-logo">
                                    {_logo_markup(company)}
                                </div>
                                <div class="company-hero-copy">
                                    <p class="company-eyebrow">Company Profile</p>
                                    <h1 class="{hero_title_class}">{escape(display_name)}</h1>
                                    <div class="company-hero-domain">{escape(company.url)}</div>
                                </div>
                            </div>
                            <div class="company-hero-summary-card">
                                <p class="company-hero-summary-label">品牌概述</p>
                                <p class="company-hero-description">{escape(short_description)}</p>
                            </div>
                        </div>

                        <div class="company-hero-insights">
                            <div class="company-hero-fact-grid">
                                {_hero_fact_tiles(company, tags, tech_stack, pages, members)}
                            </div>
                            <div class="company-hero-tag-block">
                                <p class="company-hero-summary-label">核心主题</p>
                                <div class="company-chip-row">
                                    {"".join(f'<span class="tag">{escape(item)}</span>' for item in meta_chips)}
                                    {"".join(f'<span class="tag {'tag-primary' if index < 4 else ''}">{escape(item)}</span>' for index, item in enumerate(tags[:8]))}
                                    {'<span class="tag tag-primary">GEO 认证合作伙伴</span>' if company.is_geo_certified else ''}
                                </div>
                            </div>
                        </div>

                        <div class="company-cta-row">
                            <a href="{escape(company.url)}" target="_blank" rel="noreferrer" class="company-primary-action">
                                <span class="material-symbols-outlined text-base">language</span>
                                访问官网
                            </a>
                            <a href="/diagnostic?company_id={company.id}&url={escape(company.url)}" class="company-secondary-action">
                                <span class="material-symbols-outlined text-base">analytics</span>
                                发起诊断
                            </a>
                        </div>
                    </div>

                    <aside class="company-card company-hero-panel">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Snapshot</p>
                                <h2 class="company-card-title">企业快照</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">dashboard</span>
                        </div>
                        <div class="company-score-shell">
                            <div class="company-score-ring" style="background:conic-gradient(#2563eb 0 {score_ratio}%, rgba(37, 99, 235, 0.12) {score_ratio}% 100%)">
                                <div class="company-score-core">
                                    <strong class="company-score-value">{f"{score_value:.1f}" if company.geo_score is not None else "--"}</strong>
                                    <span class="company-score-caption">GEO Score</span>
                                </div>
                            </div>
                            <div class="company-score-meta">
                                <span class="company-score-pill">{escape(company.pipeline_status.value)}</span>
                                <span class="company-score-pill">HTML Ready</span>
                                <span class="company-score-pill">AI Readable</span>
                            </div>
                        </div>
                        {_snapshot_rows(company, progress)}
                    </aside>
                </div>
            </section>

            <section class="company-metric-grid">
                {_metric_strip_markup(company, progress, tags, tech_stack, pages, members)}
            </section>

            <section class="company-results-grid">
                <div class="company-results-two">
                    <article class="company-card company-card-tall">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Executive Summary</p>
                                <h2 class="company-card-title">品牌摘要</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">business_center</span>
                        </div>
                        <div class="company-prose">
                            {brand_summary_html or "<p>该公司暂未补充更多档案摘要。</p>"}
                        </div>
                    </article>

                    <article class="company-card">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Readability</p>
                                <h2 class="company-card-title">页面可读性摘要</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">analytics</span>
                        </div>
                        <div class="company-card-stack">
                            <p class="company-story-text">{escape(readiness_text)}</p>
                            {_readability_support_markup(company, tags, tech_stack, pages)}
                        </div>
                    </article>
                </div>

                <div class="company-results-two">
                    <article class="company-card">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Knowledge Base</p>
                                <h2 class="company-card-title">知识库概览</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">inventory_2</span>
                        </div>
                        {_brand_summary_support_markup(tags, tech_stack, pages, members)}
                    </article>

                    <article class="company-card">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Completeness</p>
                                <h2 class="company-card-title">资料完备清单</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">checklist</span>
                        </div>
                        <div class="company-card-stack">
                            {_completeness_summary_markup(company, tags, tech_stack, pages, members)}
                            {_completeness_markup(company, tags, tech_stack, pages, members)}
                        </div>
                    </article>
                </div>

                <div class="company-results-two">
                    <article class="company-card">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Score Dashboard</p>
                                <h2 class="company-card-title">GEO 评分拆解</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">monitoring</span>
                        </div>
                        <div class="company-score-layout">
                            <div class="company-score-bars">
                                {_score_rows(company)}
                            </div>
                            {_score_dashboard_support_markup(company)}
                        </div>
                    </article>

                    <article class="company-card">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Signals</p>
                                <h2 class="company-card-title">AI 读取信号矩阵</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">neurology</span>
                        </div>
                        {_signal_matrix_markup(company, progress, tags, tech_stack, pages, members)}
                    </article>
                </div>

                <div class="company-results-two">
                    <article class="company-card">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Semantic Layer</p>
                                <h2 class="company-card-title">核心语义关键词</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">cloud</span>
                        </div>
                        {_semantic_cloud_markup(related_terms)}
                    </article>

                    <article class="company-card">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Knowledge Graph</p>
                                <h2 class="company-card-title">企业语义图谱</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">device_hub</span>
                        </div>
                        {_knowledge_graph_markup(company, related_terms, tags, tech_stack)}
                    </article>
                </div>

                <div class="company-results-full">
                    <section class="company-card company-section-block">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Source Pages</p>
                                <h2 class="company-card-title">AI 优先抓取页面</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">travel_explore</span>
                        </div>
                        <p class="company-section-intro">系统先从官网首页抽取一级目录，再优先选择不超过 3 个最适合构建企业知识库的页面进入最终分析。</p>
                        {_crawl_pages_markup(company)}
                    </section>
                </div>

                <div class="company-results-two">
                    <article class="company-card">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Source Structure</p>
                                <h2 class="company-card-title">来源结构优先级</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">schema</span>
                        </div>
                        {_source_structure_markup(company)}
                    </article>

                    <article class="company-card">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Tech & Assets</p>
                                <h2 class="company-card-title">技术与内容资产</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">code_blocks</span>
                        </div>
                        {_tech_stack_markup(company, tags, tech_stack)}
                    </article>
                </div>

                <div class="company-results-two">
                    <section class="company-card company-section-block">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Organization</p>
                                <h2 class="company-card-title">团队与组织信号</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">groups</span>
                        </div>
                        {_team_signal_markup(company)}
                    </section>

                    <section class="company-card company-section-block">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Recommended</p>
                                <h2 class="company-card-title">相似公司推荐</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">hub</span>
                        </div>
                        {_similar_companies_markup(similar_companies)}
                    </section>
                </div>

                <div class="company-results-full">
                    <section class="company-card company-section-block">
                        <div class="company-card-head">
                            <div>
                                <p class="company-card-eyebrow">Action Roadmap</p>
                                <h2 class="company-card-title">GEO 行动路线图</h2>
                            </div>
                            <span class="material-symbols-outlined text-primary">conversion_path</span>
                        </div>
                        {_action_roadmap_markup(company)}
                    </section>
                </div>
            </section>
        </main>
        </div>
    </div>

    <div id="footer-container"></div>
    <script src="/js/common.js?v=20260613-site-settings2"></script>
</body>
</html>
"""
    return HTMLResponse(content=html)


@router.get("/c/{company_identifier}", response_class=HTMLResponse)
@router.get("/companies/{company_identifier}", response_class=HTMLResponse)
async def company_detail_page(company_identifier: str, request: Request, db: DbSession):
    company = await get_company_by_identifier(db, company_identifier)
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")

    if company.pipeline_status == PipelineStatus.COMPLETED and company_profile_needs_hydration(company):
        try:
            await ensure_company_profile(db, company)
            refreshed = await get_company_by_identifier(db, company_identifier)
            company = refreshed or company
        except Exception:
            pass

    canonical_path = company_public_path(company)
    if request.url.path != canonical_path:
        return RedirectResponse(url=_absolute_url(request, canonical_path), status_code=301)

    similar_companies = await fallback_similar_companies(db, company, limit=3)
    return _render_page(request=request, company=company, similar_companies=similar_companies)
