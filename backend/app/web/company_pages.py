"""
公司详情页服务端渲染
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime
from html import escape
from typing import Any, Iterable
from urllib.parse import urljoin
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import async_session
from app.core.config import settings
from app.core.deps import DbSession
from app.models.company import Company, PipelineStatus, PublishStatus
from app.services.company_lookup import company_public_path, get_company_by_identifier
from app.services.company_preview import verify_company_preview_token
from app.services.company_profile import normalize_company_name
from app.services.company_retrieval import rank_similar_companies

router = APIRouter(include_in_schema=False)
logger = logging.getLogger("georank")


async def _increment_company_view_count(company_id: UUID) -> None:
    async with async_session() as tracking_db:
        try:
            await tracking_db.execute(
                update(Company)
                .where(Company.id == company_id)
                .values(view_count=Company.view_count + 1)
            )
            await tracking_db.commit()
        except SQLAlchemyError:
            await tracking_db.rollback()
            logger.warning(
                "Company page view increment failed: company_id=%s",
                company_id,
                exc_info=True,
            )


def _absolute_url(request: Request, path: str) -> str:
    # Canonical links and redirects must not inherit an attacker-controlled
    # Host/X-Forwarded-Host value. Local debug/test hosts retain their active
    # port; all other traffic uses the configured public origin.
    if settings.DEBUG and request.url.hostname in {"localhost", "127.0.0.1", "testserver"}:
        base_url = str(request.base_url)
    else:
        base_url = settings.PUBLIC_BASE_URL
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def _render_json_ld(*payloads: dict) -> str:
    return "\n".join(
        f'<script type="application/ld+json">{_json_for_html(payload)}</script>'
        for payload in payloads if payload
    )


def _json_for_html(payload: dict) -> str:
    """序列化可安全嵌入 script 元素的 JSON，阻止外部资料闭合标签。"""
    return (
        json.dumps(payload, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


_PUBLIC_PLACEHOLDER_VALUES = {
    "--",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "待补充",
    "未知",
}


def _public_profile_value(value: object) -> str:
    text = _normalize_text(str(value) if value is not None else "")
    return "" if text.lower() in _PUBLIC_PLACEHOLDER_VALUES else text


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


def _public_record_list(values: object, fields: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [
        item
        for item in values
        if isinstance(item, dict)
        and any(_public_profile_value(item.get(field)) for field in fields)
    ]


def _public_team_members(values: object) -> list[dict[str, Any]]:
    return [
        member
        for member in _public_record_list(values, ("name", "role", "bg"))
        if _public_profile_value(member.get("name"))
    ]


def _public_source_pages(values: object) -> list[dict[str, Any]]:
    pages = _public_record_list(values, ("role", "title", "reason", "url", "key", "status"))
    return [
        page
        for page in pages
        if page.get("status") == "captured"
        and bool(_public_profile_value(page.get("key")))
        and (
            _public_profile_value(page.get("title"))
            or _public_profile_value(page.get("url")).startswith(("http://", "https://"))
        )
    ]


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
        text = _public_profile_value(item)
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
        ("当前判断", "人物实体密度偏低，但品牌档案和技术语义已经完成入库。", False),
        ("建议抓取", f"下一轮优先补抓 {preferred_text}，增强组织信号。", False),
        ("目标结果", "补齐核心成员、职责分工和公开团队页面，提高可信度与引用稳定性。", True),
    ]
    rendered = []
    for label, value, is_wide in cards:
        note_class = (
            "company-organization-note company-organization-note--wide"
            if is_wide
            else "company-organization-note"
        )
        rendered.append(
            f"""
            <article class="{note_class}">
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


_GEO_DIMENSIONS = (
    ("schema", "结构化", "组织、网站与问答等机器可读标记"),
    ("content", "答案内容", "定义、步骤、案例与可直接引用的结论"),
    ("meta", "预览信息", "标题、摘要、Canonical 与 Open Graph"),
    ("citation", "引用信号", "公开引用材料的完整度与可核验性"),
)

_GEO_PRIORITY_ACTIONS = {
    "schema": "补齐 Organization、WebSite、FAQPage 与 BreadcrumbList。",
    "content": "补充 FAQ、案例和答案段落，增加可引用内容密度。",
    "meta": "重写 Title、Description、Canonical 与 Open Graph。",
    "citation": "增加案例引用、合作伙伴和权威来源链接。",
}


def _geo_dimension_values(company: Company) -> list[dict[str, Any]]:
    details = company.geo_details if isinstance(company.geo_details, dict) else {}
    dimensions: list[dict[str, Any]] = []
    for key, label, hint in _GEO_DIMENSIONS:
        raw_value = details.get(key)
        value = None
        if raw_value is not None:
            try:
                value = max(0, min(int(round(float(raw_value))), 100))
            except (TypeError, ValueError, OverflowError):
                value = None
        dimensions.append({"key": key, "label": label, "hint": hint, "value": value})
    return dimensions


def _geo_score_band(score: float | None) -> str:
    if score is None:
        return "等待评估"
    if score >= 85:
        return "表现稳健"
    if score >= 70:
        return "具备良好基础"
    if score >= 50:
        return "需要持续增强"
    return "优先完成基础建设"


def _geo_priority(
    company: Company,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    dimensions = _geo_dimension_values(company)
    scored = [item for item in dimensions if item["value"] is not None]
    if not scored:
        return None, None
    strongest = max(scored, key=lambda item: item["value"])
    weakest = min(scored, key=lambda item: item["value"])
    return strongest, weakest


def _profile_completeness_items(
    company: Company,
    tags: list[str],
    tech_stack: list[str],
    pages: list[dict],
    members: list[dict],
) -> list[tuple[str, bool]]:
    return [
        ("公司简介", bool(_normalize_text(company.description) or _normalize_text(company.short_description))),
        ("语义标签", bool(tags)),
        ("技术主题", bool(tech_stack)),
        ("来源页面", bool(pages)),
        ("团队实体", bool(members)),
        ("地区信息", bool(_normalize_text(company.headquarters))),
    ]


def _geo_overview_markup(company: Company) -> str:
    dimensions = [item for item in _geo_dimension_values(company) if item["value"] is not None]
    strongest, weakest = _geo_priority(company)
    score_rows = []
    for item in dimensions:
        value = item["value"]
        score_rows.append(
            f"""
            <li class="company-dimension-row">
                <div class="company-dimension-copy">
                    <span class="company-dimension-name">{escape(item['label'])}</span>
                    <span class="company-dimension-hint">{escape(item['hint'])}</span>
                </div>
                <div class="company-dimension-measure">
                    <span class="company-dimension-value">{value if value is not None else '待评估'}</span>
                    <span class="company-dimension-track" aria-hidden="true">
                        <span class="company-dimension-fill" style="width:{value if value is not None else 0}%"></span>
                    </span>
                </div>
            </li>
            """
        )

    strongest_label = strongest["label"] if strongest else "待评估"
    weakest_label = weakest["label"] if weakest else "待评估"
    verdict = "当前公司尚未形成完整的 GEO 评估。"
    if strongest:
        verdict = f"当前最稳定的维度是{strongest_label}，{strongest['value']} 分。"
    overall_score = "待评估" if company.geo_score is None else f"{max(0.0, min(float(company.geo_score), 100.0)):.1f}"
    dimension_markup = (
        f'<ol class="company-dimension-list" aria-label="GEO 四维评分">{"".join(score_rows)}</ol>'
        if score_rows
        else '<p class="company-compact-state">四个 GEO 维度仍在等待评估。</p>'
    )
    priority_markup = ""
    if weakest:
        priority_markup = f"""
            <div class="company-overview-priority">
                <p class="company-mini-label">建议优先关注</p>
                <h3>{escape(weakest_label)}</h3>
                <p>{escape(_GEO_PRIORITY_ACTIONS[weakest['key']])}</p>
                <span>{weakest['value']} 分</span>
            </div>
        """
    return f"""
    <div class="company-overview-layout">
        <div class="company-overview-summary">
            <p class="company-overview-verdict">{escape(verdict)}</p>
            <p class="company-overview-explanation">GEOrank 从结构化表达、答案内容、预览信息和外部引用四个方向，判断公开资料被生成式引擎理解和引用的稳定程度。</p>
            <dl class="company-overview-facts">
                <div><dt>综合评分</dt><dd>{escape(overall_score)}</dd></div>
                <div><dt>当前表现</dt><dd>{escape(_geo_score_band(company.geo_score))}</dd></div>
                <div><dt>优势维度</dt><dd>{escape(strongest_label)}</dd></div>
                <div><dt>关注维度</dt><dd>{escape(weakest_label)}</dd></div>
            </dl>
            {priority_markup}
        </div>
        {dimension_markup}
    </div>
    """


def _semantic_map_markup(
    company: Company,
    display_name: str,
    tags: list[str],
    tech_stack: list[str],
    graph_nodes: list[str] | None = None,
) -> str:
    candidates = [
        *(graph_nodes or [])[:8],
        company.category,
        company.headquarters,
        company.funding_stage,
        *tech_stack[:3],
        *tags[:5],
    ]
    nodes: list[str] = []
    for item in candidates:
        text = _public_profile_value(item)
        if text and text != display_name and text not in nodes:
            nodes.append(text)

    if len(nodes) < 4:
        terms = nodes or ["待补充语义实体"]
        return (
            '<div class="company-semantic-terms">'
            + "".join(f'<span class="company-term">{escape(term)}</span>' for term in terms)
            + "</div>"
        )

    rendered_nodes = "".join(
        f'<li class="company-semantic-node">{escape(node)}</li>' for node in nodes[:8]
    )
    return f"""
    <div class="company-semantic-map" aria-label="{escape(display_name)} 语义关系">
        <div class="company-semantic-center">
            <span>Company</span>
            <strong>{escape(display_name)}</strong>
        </div>
        <ul class="company-semantic-nodes">{rendered_nodes}</ul>
    </div>
    """


def _company_story_markup(
    company: Company,
    display_name: str,
    short_description: str,
) -> str:
    description_paragraphs = _paragraphs(
        _public_profile_value(company.description) or short_description
    )
    narrative = description_paragraphs[:3]
    prose = "".join(f"<p>{escape(paragraph)}</p>" for paragraph in narrative if paragraph)

    story_facts = [
        ("公司类型", _public_profile_value(company.category)),
        ("总部地区", _public_profile_value(company.headquarters)),
        ("成立时间", _public_profile_value(_format_short_date(company.founded_date))),
        ("团队规模", _public_profile_value(company.employee_count)),
        ("融资阶段", _public_profile_value(company.funding_stage)),
    ]
    story_facts = [(label, value) for label, value in story_facts if value]
    facts_markup = "".join(
        f'<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>'
        for label, value in story_facts
    )
    facts_content = (
        f"<dl>{facts_markup}</dl>"
        if facts_markup
        else '<p class="company-compact-state">公司公开档案仍在完善。</p>'
    )

    return f"""
    <div class="company-story-layout">
        <article class="company-story-copy">
            <p class="company-mini-label">Company story</p>
            <h3>{escape(display_name)} 在做什么</h3>
            <p class="company-story-lead">{escape(short_description)}</p>
            <div class="company-reading-prose">{prose}</div>
        </article>
        <aside class="company-story-facts" aria-label="公司档案摘要">
            <p class="company-mini-label">Company facts</p>
            {facts_content}
        </aside>
    </div>
    """


def _business_capabilities_markup(
    company: Company,
    display_name: str,
    tags: list[str],
    tech_stack: list[str],
) -> str:
    category = _public_profile_value(company.category) or "公开业务资料"
    business_topics = tags[:8]
    business_terms = "、".join(business_topics[:4]) if business_topics else category
    topic_markup = "".join(
        f'<span class="company-term">{escape(value)}</span>' for value in business_topics
    ) or '<span class="company-term">业务主题待完善</span>'
    tool_markup = "".join(
        f'<span class="company-tool-term">{escape(value)}</span>' for value in tech_stack[:8]
    )
    tool_content = (
        f'<div class="company-tool-list">{tool_markup}</div>'
        if tool_markup
        else '<p class="company-compact-state">暂未识别到可公开展示的数字工具。</p>'
    )
    tech_level = _public_profile_value(company.tech_level)
    tech_level_markup = (
        f'<p class="company-capability-level"><span>GEO 技术层级</span><strong>{escape(tech_level)}</strong></p>'
        if tech_level
        else ""
    )

    return f"""
    <div class="company-capabilities-layout">
        <article class="company-capability-positioning">
            <p class="company-mini-label">Business positioning</p>
            <h3>{escape(category)}</h3>
            <p>{escape(display_name)} 的公开信息主要围绕{escape(business_terms)}展开，用于描述公司的业务方向与市场定位。</p>
            <div class="company-term-list">{topic_markup}</div>
        </article>
        <article class="company-capability-tools">
            <p class="company-mini-label">Detected tools</p>
            <h3>已识别的技术与数字工具</h3>
            <p>以下信息来自官网公开页面的技术检测结果，用于理解公司的数字化环境。</p>
            {tool_content}
            {tech_level_markup}
        </article>
    </div>
    """


def _geo_semantic_profile_markup(
    company: Company,
    display_name: str,
    tags: list[str],
    tech_stack: list[str],
    graph_nodes: list[str] | None = None,
) -> str:
    category = _public_profile_value(company.category) or "公司档案"
    service_terms = "、".join(tags[:4]) if tags else "品牌定位与公开资料"
    tech_terms = "、".join(tech_stack[:3]) if tech_stack else "尚未形成稳定的技术主题"
    interpretation = (
        f"AI 当前将 {display_name} 识别为{category}，核心语义集中在{service_terms}。"
        f"技术与数字工具层主要关联{tech_terms}。"
    )
    return f"""
    <div class="company-geo-semantic">
        <div class="company-geo-semantic-copy">
            <p class="company-mini-label">AI interpretation</p>
            <h3>AI 如何理解这家公司</h3>
            <p>{escape(interpretation)}</p>
        </div>
        {_semantic_map_markup(company, display_name, tags, tech_stack, graph_nodes)}
    </div>
    """


def _source_evidence_markup(company: Company) -> str:
    pages = _public_source_pages(company.crawl_pages)
    if not pages:
        return ""

    items = []
    for index, page in enumerate(pages[:5]):
        page = page if isinstance(page, dict) else {}
        role = _public_profile_value(page.get("role")) or f"页面 {index + 1}"
        title = (
            _public_profile_value(page.get("title"))
            or _public_profile_value(page.get("url"))
            or "未命名页面"
        )
        reason = _public_profile_value(page.get("reason")) or "该页面被纳入企业知识库的优先来源。"
        url = _public_profile_value(page.get("url"))
        url_markup = ""
        if url:
            safe_url = escape(url)
            if url.startswith(("http://", "https://")):
                url_markup = f'<a href="{safe_url}" target="_blank" rel="noreferrer">{safe_url}</a>'
            else:
                url_markup = f"<span>{safe_url}</span>"
        items.append(
            f"""
            <li class="company-source-item">
                <span class="company-source-index">{index + 1:02d}</span>
                <div class="company-source-copy">
                    <p class="company-source-role">{escape(role)}</p>
                    <h3>{escape(title)}</h3>
                    <p>{escape(reason)}</p>
                    <div class="company-source-url">{url_markup}</div>
                </div>
            </li>
            """
        )
    return f'<ol class="company-source-list">{"".join(items)}</ol>'


def _team_profile_section_markup(company: Company) -> str:
    members = _public_team_members(company.team_members)
    if not members:
        return ""

    roles: list[str] = []
    rows = []
    for index, member in enumerate(members[:8]):
        name = _public_profile_value(member.get("name")) or f"成员 {index + 1}"
        role = _public_profile_value(member.get("role")) or "核心成员"
        background = _public_profile_value(member.get("bg"))
        if role not in roles:
            roles.append(role)
        rows.append(
            f"""
            <li class="company-person-row">
                <span class="company-person-mark">{escape(name[:1])}</span>
                <div>
                    <strong>{escape(name)}</strong>
                    <span>{escape(role)}</span>
                    {f'<p>{escape(background)}</p>' if background else ''}
                </div>
            </li>
            """
        )

    role_terms = "".join(
        f'<span class="company-term">{escape(role)}</span>' for role in roles[:6]
    )
    return f"""
    <section id="company-team" class="company-editorial-section" aria-labelledby="company-team-title">
        <header class="company-section-heading">
            <p>People / 公开团队</p>
            <h2 id="company-team-title">团队与信任</h2>
            <span>通过公开成员、角色和背景信息建立清晰的组织实体。</span>
        </header>
        <div class="company-team-layout">
            <article class="company-team-summary">
                <p class="company-mini-label">Public team</p>
                <h3>已识别 {len(members)} 位公开成员</h3>
                <p>这些人物信息来自公司公开资料。明确的姓名、职责与背景有助于用户和生成式引擎确认组织身份。</p>
                <div class="company-term-list">{role_terms}</div>
            </article>
            <div class="company-team-list-panel">
                <ul class="company-person-list">{"".join(rows)}</ul>
            </div>
        </div>
    </section>
    """


def _public_sources_section_markup(company: Company) -> str:
    pages = _public_source_pages(company.crawl_pages)
    if not pages:
        return ""

    roles: list[str] = []
    linked_pages = 0
    for page in pages:
        role = _public_profile_value(page.get("role")) or "其他"
        if role not in roles:
            roles.append(role)
        url = _public_profile_value(page.get("url"))
        if url.startswith(("http://", "https://")):
            linked_pages += 1

    role_terms = "".join(
        f'<span class="company-term">{escape(role)}</span>' for role in roles[:6]
    )
    return f"""
    <section id="company-sources" class="company-editorial-section" aria-labelledby="company-sources-title">
        <header class="company-section-heading">
            <p>Sources / 公开资料</p>
            <h2 id="company-sources-title">公开资料与可信信号</h2>
            <span>列出构成公司档案的官网页面，方便访客核对信息来源。</span>
        </header>
        <div class="company-sources-layout">
            <article class="company-sources-summary">
                <p class="company-mini-label">Source overview</p>
                <h3>已收录 {len(pages)} 个公开页面</h3>
                <p>这些页面是公司介绍、业务能力和 GEO 分析的主要公开依据。</p>
                <dl class="company-source-facts">
                    <div><dt>公开页面</dt><dd>{len(pages)}</dd></div>
                    <div><dt>来源类型</dt><dd>{len(roles)}</dd></div>
                    <div><dt>可访问链接</dt><dd>{linked_pages}</dd></div>
                </dl>
                <div class="company-term-list">{role_terms}</div>
            </article>
            {_source_evidence_markup(company)}
        </div>
    </section>
    """


def _trust_and_entities_markup(company: Company) -> str:
    members = company.team_members if isinstance(company.team_members, list) else []
    pages = company.crawl_pages if isinstance(company.crawl_pages, list) else []
    dimensions = {item["key"]: item["value"] for item in _geo_dimension_values(company)}
    citation_score = dimensions.get("citation")
    has_case_source = any(
        any(token in (_normalize_text(page.get("role")) + " " + _normalize_text(page.get("title"))).lower()
            for token in ("case", "customer", "client", "partner", "案例", "客户", "合作"))
        for page in pages if isinstance(page, dict)
    )

    member_markup = ""
    if members:
        rows = []
        for index, member in enumerate(members[:6]):
            member = member if isinstance(member, dict) else {}
            name = _normalize_text(member.get("name")) or f"成员 {index + 1}"
            role = _normalize_text(member.get("role")) or "核心成员"
            background = _normalize_text(member.get("bg"))
            rows.append(
                f"""
                <li class="company-person-row">
                    <span class="company-person-mark">{escape(name[:1])}</span>
                    <div><strong>{escape(name)}</strong><span>{escape(role)}</span>{f'<p>{escape(background)}</p>' if background else ''}</div>
                </li>
                """
            )
        member_markup = f'<ul class="company-person-list">{"".join(rows)}</ul>'
    else:
        member_markup = """
        <div class="company-trust-gap">
            <p class="company-mini-label">团队实体待补充</p>
            <strong>当前没有可验证的团队与高管节点</strong>
            <p>建议公开团队页、高管介绍、作者署名与案例责任人。</p>
        </div>
        """

    gaps = []
    if not members:
        gaps.append("团队与高管实体")
    if not has_case_source:
        gaps.append("案例或合作伙伴证明")
    if citation_score is None or citation_score < 70:
        gaps.append("外部权威引用")
    gap_text = "、".join(gaps)
    trust_claim = (
        f"可信度仍需重点检查 {gap_text}。"
        if gap_text
        else "当前核心信任信号已经形成基础覆盖。"
    )
    citation_display = citation_score if citation_score is not None else "待评估"

    return f"""
    <div class="company-trust-layout">
        <div class="company-trust-summary">
            <p class="company-understanding-claim">{escape(trust_claim)}</p>
            <dl class="company-trust-facts">
                <div><dt>团队实体</dt><dd>{len(members)}</dd></div>
                <div><dt>公开来源</dt><dd>{len(pages)}</dd></div>
                <div><dt>外部背书</dt><dd>{citation_display}</dd></div>
            </dl>
            <p class="company-trust-note">实体、案例与外部引用越清晰，生成式引擎越容易确认品牌身份和引用边界。</p>
        </div>
        <div class="company-trust-entities">{member_markup}</div>
    </div>
    """


def _editorial_roadmap_markup(company: Company) -> str:
    dimensions = _geo_dimension_values(company)
    ordered = sorted(
        dimensions,
        key=lambda item: item["value"] if item["value"] is not None else -1,
    )
    phases = (
        ("01", "7 天", ordered[:2]),
        ("02", "30 天", ordered[2:3]),
        ("03", "90 天", ordered[3:4]),
    )
    steps = []
    for phase_code, phase_label, phase_items in phases:
        actions = "".join(
            f"""
            <li>
                <strong>{escape(item['label'])}</strong>
                <p>{escape(_GEO_PRIORITY_ACTIONS[item['key']])}</p>
                <span>当前 {item['value'] if item['value'] is not None else '待评估'} 分</span>
            </li>
            """
            for item in phase_items
        )
        steps.append(
            f"""
            <article class="company-roadmap-step">
                <div class="company-roadmap-marker"><span>{phase_code}</span></div>
                <div class="company-roadmap-copy">
                    <p class="company-mini-label">Phase {phase_code}</p>
                    <h3>{phase_label}</h3>
                    <ul>{actions}</ul>
                </div>
            </article>
            """
        )
    return f'<div class="company-roadmap-timeline">{"".join(steps)}</div>'


def _similar_companies_section_markup(companies: list[Company]) -> str:
    if not companies:
        return ""
    items = []
    for company in companies[:3]:
        company_name = normalize_company_name(company.name, fallback_name=company.name) or company.name
        score = f"{float(company.geo_score):.1f}" if company.geo_score is not None else "待评估"
        items.append(
            f"""
            <a href="{company_public_path(company)}" class="company-related-item">
                <span class="company-related-name">{escape(company_name)}</span>
                <span class="company-related-category">{escape(_public_profile_value(company.category) or '公司档案')}</span>
                <strong>GEO {escape(score)}</strong>
            </a>
            """
        )
    return f"""
    <section id="company-recommendations" class="company-editorial-section company-related-section" aria-labelledby="company-recommendations-title">
        <header class="company-section-heading">
            <p>Related / 同类公司</p>
            <h2 id="company-recommendations-title">相关公司</h2>
            <span>继续查看同类公司的 GEO 状态与公开资料。</span>
        </header>
        <div class="company-related-list">{"".join(items)}</div>
    </section>
    """


def _company_structured_data(request: Request, company: Company, canonical_url: str, description: str, keywords: list[str]) -> str:
    company_name = normalize_company_name(company.name, fallback_name=company.name) or company.name
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": _absolute_url(request, "/")},
            {"@type": "ListItem", "position": 2, "name": "公司", "item": _absolute_url(request, "/companies")},
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
    headquarters = _public_profile_value(company.headquarters)
    if headquarters:
        organization["location"] = {
            "@type": "Place",
            "name": headquarters,
            "address": headquarters,
        }
    if company.founded_date:
        organization["foundingDate"] = _format_iso_date(company.founded_date)
    employee_count = _public_profile_value(company.employee_count)
    if employee_count:
        organization["numberOfEmployees"] = employee_count

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
    graph_data: dict[str, Any] | None = None,
) -> HTMLResponse:
    display_name = normalize_company_name(company.name, fallback_name=company.name) or company.name
    canonical_url = _absolute_url(request, company_public_path(company))
    allow_index = company.publish_status == PublishStatus.PUBLISHED
    short_description = (
        _public_profile_value(company.short_description)
        or _public_profile_value(company.description)
        or "查看该公司的 GEO 资料、技术栈、团队信息与相似推荐。"
    )[:300]
    title = f"{display_name} - GEO 公司档案 | GEOrank"
    keywords = _company_keywords(company)
    meta_tags = _render_meta_tags(
        title=title,
        description=short_description,
        canonical_url=canonical_url,
        keywords=keywords,
        cover_image_url=_og_image(company),
        allow_index=allow_index,
    )
    structured_data = _company_structured_data(request, company, canonical_url, short_description, keywords)
    tags = [
        value for value in _normalize_list(company.tags) if _public_profile_value(value)
    ]
    tech_stack = [
        value
        for value in _normalize_list(company.tech_stack)
        if _public_profile_value(value)
    ]
    pages = company.crawl_pages if isinstance(company.crawl_pages, list) else []
    members = company.team_members if isinstance(company.team_members, list) else []
    hero_title_class = _hero_title_class(display_name)
    graph_nodes = [
        _public_profile_value(node.get("name"))
        for node in ((graph_data or {}).get("nodes") or [])
        if isinstance(node, dict) and _public_profile_value(node.get("name"))
    ]

    score_value = None if company.geo_score is None else max(0.0, min(float(company.geo_score), 100.0))
    score_display = "待评估" if score_value is None else f"{score_value:.1f}"
    score_progress = 0 if score_value is None else score_value
    score_gauge_angle = score_progress * 3.6
    strongest, weakest = _geo_priority(company)
    strongest_label = strongest["label"] if strongest else "待评估"
    weakest_label = weakest["label"] if weakest else "待评估"
    profile_status = {
        "completed": "公开资料已收录",
        "failed": "资料更新受阻",
    }.get(company.pipeline_status.value, "公开资料整理中")
    score_visual_html = (
        f"""
        <div class="company-score-gauge" style="--company-score-angle:{score_gauge_angle:.1f}deg" aria-label="GEO 评分 {escape(score_display)}">
            <div class="company-score-gauge-core">
                <strong>{escape(score_display)}</strong>
                <span>/ 100</span>
            </div>
        </div>
        """
        if score_value is not None
        else """
        <div class="company-score-empty">
            <span>GEO score</span>
            <strong>待评估</strong>
        </div>
        """
    )

    hero_facts = [
        ("公司类型", _public_profile_value(company.category) or "公司档案"),
        ("总部地区", _public_profile_value(company.headquarters)),
        ("成立时间", _public_profile_value(_format_short_date(company.founded_date))),
        ("团队规模", _public_profile_value(company.employee_count)),
    ]
    hero_facts = [(label, value) for label, value in hero_facts if value]
    hero_facts_html = "".join(
        f'<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>'
        for label, value in hero_facts
    )
    hero_topics: list[str] = []
    for item in [company.category, company.funding_stage, company.headquarters, *tags[:5]]:
        text = _public_profile_value(item)
        if text and text not in hero_topics:
            hero_topics.append(text)
    if company.is_geo_certified:
        hero_topics.append("GEO 认证合作伙伴")
    hero_topics_html = "".join(
        f'<span class="company-term">{escape(topic)}</span>' for topic in hero_topics
    )
    hero_topics_block = (
        f'<div class="company-term-list">{hero_topics_html}</div>' if hero_topics_html else ""
    )

    similar_section_html = _similar_companies_section_markup(similar_companies)
    team_section_html = _team_profile_section_markup(company)
    public_sources_section_html = _public_sources_section_markup(company)
    team_nav_link = '<a href="#company-team">团队与信任</a>' if team_section_html else ""
    sources_nav_link = '<a href="#company-sources">公开资料</a>' if public_sources_section_html else ""
    preview_notice = ""
    if company.publish_status != PublishStatus.PUBLISHED:
        preview_notice = """
        <div class="company-preview-notice">
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
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap" rel="stylesheet" media="print" onload="this.media='all'">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" media="print" onload="this.media='all'">
    <link rel="stylesheet" href="/css/public-tailwind.css?v=20260716-first-paint-lifecycle">
    <link rel="stylesheet" href="/css/common.css?v=20260716-first-paint-lifecycle">
    <link rel="stylesheet" href="/css/company.css?v=20260716-company-profile">
    {structured_data}
</head>
<body class="company-page">
    <a class="company-skip-link" href="#company-profile">跳到公司档案</a>
    <div id="header-container"></div>

    <div class="company-page-shell">
        <main id="company-content" class="company-page-content">
            <nav class="company-breadcrumb" aria-label="面包屑">
                <a href="/">首页</a><span>/</span><a href="/companies">公司</a><span>/</span><span>{escape(display_name)}</span>
            </nav>

            {preview_notice}

            <section id="company-profile" class="company-hero" aria-labelledby="company-profile-title">
                <div class="company-hero-layout">
                    <article class="company-identity">
                        <div class="company-identity-brand">
                            <div class="company-hero-logo">{_logo_markup(company)}</div>
                            <div class="company-identity-title">
                                <p class="company-kicker">Company dossier</p>
                                <h1 id="company-profile-title" class="{hero_title_class}">{escape(display_name)}</h1>
                                <a class="company-domain" href="{escape(company.url)}" target="_blank" rel="noreferrer">{escape(company.url)}</a>
                            </div>
                        </div>
                        <p class="company-hero-description">{escape(short_description)}</p>
                        <dl class="company-identity-facts">{hero_facts_html}</dl>
                        {hero_topics_block}
                        <div class="company-hero-actions">
                            <a class="company-primary-action" href="{escape(company.url)}" target="_blank" rel="noreferrer">访问官网 <span aria-hidden="true">↗</span></a>
                            <a class="company-text-action" href="/diagnostic?company_id={company.id}&url={escape(company.url)}">发起 GEO 诊断</a>
                        </div>
                    </article>

                    <aside class="company-hero-score" aria-label="GEO 快照">
                        <div class="company-score-heading">
                            <p>GEO 快照</p>
                            <span>{escape(_geo_score_band(score_value))}</span>
                        </div>
                        {score_visual_html}
                        <p class="company-score-status">{escape(profile_status)}</p>
                        <div class="company-score-snapshot">
                            <div>
                                <span>优势维度</span>
                                <strong>{escape(strongest_label)}</strong>
                            </div>
                            <div>
                                <span>关注维度</span>
                                <strong>{escape(weakest_label)}</strong>
                            </div>
                        </div>
                        <a class="company-score-link" href="#company-geo">查看 GEO 分析 <span aria-hidden="true">↓</span></a>
                        <p class="company-score-updated">档案更新于 {_format_short_date(company.updated_at or company.created_at)}</p>
                    </aside>
                </div>
            </section>

            <nav class="company-profile-nav" aria-label="公司档案章节">
                <a href="#company-story">公司介绍</a>
                <a href="#company-capabilities">业务与能力</a>
                {team_nav_link}
                {sources_nav_link}
                <a href="#company-geo">GEO 分析</a>
            </nav>

            <section id="company-story" class="company-editorial-section" aria-labelledby="company-story-title">
                <header class="company-section-heading">
                    <p>About / 公司故事</p>
                    <h2 id="company-story-title">公司介绍</h2>
                    <span>从公开资料理解公司的定位、背景与发展阶段。</span>
                </header>
                {_company_story_markup(company, display_name, short_description)}
            </section>

            <section id="company-capabilities" class="company-editorial-section" aria-labelledby="company-capabilities-title">
                <header class="company-section-heading">
                    <p>Capabilities / 业务档案</p>
                    <h2 id="company-capabilities-title">业务与能力</h2>
                    <span>梳理公司公开业务主题，以及官网中识别到的技术与数字工具。</span>
                </header>
                {_business_capabilities_markup(company, display_name, tags, tech_stack)}
            </section>

            {team_section_html}

            {public_sources_section_html}

            <section id="company-geo" class="company-editorial-section" aria-labelledby="company-geo-title">
                <header class="company-section-heading">
                    <p>GEOrank / AI 可见性</p>
                    <h2 id="company-geo-title">GEO 分析</h2>
                    <span>查看公司公开信息被生成式引擎理解、识别和引用的当前状态。</span>
                </header>
                {_geo_overview_markup(company)}
                {_geo_semantic_profile_markup(company, display_name, tags, tech_stack, graph_nodes)}
                <div class="company-geo-actions">
                    <a class="company-primary-action" href="/diagnostic?company_id={company.id}&url={escape(company.url)}">查看完整 GEO 诊断</a>
                </div>
            </section>

            {similar_section_html}
        </main>
    </div>

    <div id="footer-container"></div>
    <script src="/js/common.js?v=20260716-first-paint-lifecycle"></script>
</body>
</html>
"""
    return HTMLResponse(content=html)


@router.get("/c/{company_identifier}", response_class=HTMLResponse)
@router.get("/companies/{company_identifier}", response_class=HTMLResponse)
async def company_detail_page(
    company_identifier: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
):
    company = await get_company_by_identifier(db, company_identifier)
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")
    preview_token = request.query_params.get("preview")
    if (
        company.publish_status != PublishStatus.PUBLISHED
        and not verify_company_preview_token(preview_token, company.id)
    ):
        raise HTTPException(status_code=404, detail="公司不存在")

    canonical_path = company_public_path(company)
    if request.url.path != canonical_path:
        redirect_url = _absolute_url(request, canonical_path)
        if preview_token:
            from urllib.parse import quote

            redirect_url = f"{redirect_url}?preview={quote(preview_token)}"
        return RedirectResponse(url=redirect_url, status_code=301)

    async def load_graph_data() -> dict[str, Any]:
        try:
            from app.services.graph_store import get_company_graph

            return await asyncio.wait_for(get_company_graph(str(company.id)), timeout=2.0)
        except Exception:
            logger.warning("Company graph unavailable: company_id=%s", company.id, exc_info=True)
            return {}

    similar_companies, graph_data = await asyncio.gather(
        rank_similar_companies(db, company, limit=3),
        load_graph_data(),
    )
    response = _render_page(
        request=request,
        company=company,
        similar_companies=similar_companies,
        graph_data=graph_data,
    )

    if company.publish_status == PublishStatus.PUBLISHED:
        background_tasks.add_task(_increment_company_view_count, company.id)

    return response
