"""
教程频道服务端渲染页面
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.core.deps import DbSession
from app.models.content import Content, ContentStatus, ContentType
from app.services.content_render import render_markdown
from app.services.tutorial_enrichment import estimate_reading_time_minutes, get_public_markdown

router = APIRouter(include_in_schema=False)

TUTORIAL_CHAPTER_ORDER = [
    "GEO认知",
    "AI原理",
    "内容优化",
    "页面技术",
    "策略执行",
    "评估治理",
    "实战案例",
]

TUTORIAL_CHAPTER_ICONS = {
    "GEO认知": "travel_explore",
    "AI原理": "neurology",
    "内容优化": "edit_note",
    "页面技术": "code_blocks",
    "策略执行": "conversion_path",
    "评估治理": "query_stats",
    "实战案例": "folder_managed",
}

TUTORIAL_ARTICLE_ORDER = {
    "GEO认知": ["GEO是什么", "GEO与SEO", "商业价值", "行业影响"],
    "AI原理": ["LLM基础", "RAG流程", "答案生成", "AI搜索"],
    "内容优化": ["EEAT原则", "答案优先", "结构化写法", "差异化内容"],
    "页面技术": ["产品页优化", "Schema标记", "llms协议", "内容分块"],
    "策略执行": ["长尾规划", "官网优先", "信源运营", "推荐逻辑"],
    "评估治理": ["排名指标", "心智指标", "转化归因", "合规治理"],
    "实战案例": ["国内概览", "SaaS案例", "金融案例", "本地案例"],
}

HOME_OVERVIEW = (
    "这里汇总当前频道下全部已发布的 GEO 教程，覆盖认知、AI 原理、内容优化、页面技术、"
    "策略执行、评估治理与案例拆解，适合按章节连续阅读，也适合按主题跳读。"
)

SITE_DESCRIPTION = "GEO 生成式引擎优化教程中心 — 科普教程、最佳实践与技术文档。"


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _slugify(value: str | None) -> str:
    text = re.sub(r"<[^>]*>", "", value or "").strip().lower()
    text = re.sub(r"[\s\W-]+", "-", text)
    return text.strip("-")


def _format_date(value: datetime | None) -> str:
    if not value:
        return "--"
    return value.strftime("%Y/%m/%d")


def _format_iso(value: datetime | None) -> str:
    if not value:
        return ""
    return value.replace(microsecond=0).isoformat() + "Z"


def _format_reading_time(minutes: int | None) -> str:
    value = int(minutes or 0)
    if not value:
        return "预计阅读时间：待估算"
    return f"预计阅读时间：{value} 分钟"


def _tutorial_markdown(article: Content) -> str:
    return get_public_markdown(article)


def _tutorial_reading_time(article: Content) -> int:
    return estimate_reading_time_minutes(
        _tutorial_markdown(article),
        article.reading_time_minutes,
    )


def _absolute_url(request: Request, path: str) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if forwarded_host:
        scheme = forwarded_proto or request.url.scheme or "http"
        return f"{scheme}://{forwarded_host.rstrip('/')}/{path.lstrip('/')}"
    return urljoin(str(request.base_url), path.lstrip("/"))


def _article_identifier(article: Content) -> str:
    return article.path_key or article.slug


def _tutorial_detail_path(article: Content) -> str:
    return f"/tutorial/{_article_identifier(article)}"


def _tutorial_detail_url(request: Request, article: Content) -> str:
    return _absolute_url(request, _tutorial_detail_path(article))


def _cover_image_url(request: Request, article: Content) -> str:
    if not article.cover_image:
        return _absolute_url(request, "/images/og-default.png")
    if article.cover_image.startswith(("http://", "https://")):
        return article.cover_image
    return _absolute_url(request, article.cover_image)


def _tutorial_category(article: Content) -> str:
    tags = article.tags if isinstance(article.tags, list) else []
    return tags[0] if tags else "其他"


def _compare_tutorials(article: Content) -> tuple:
    category = _tutorial_category(article)
    category_index = TUTORIAL_CHAPTER_ORDER.index(category) if category in TUTORIAL_CHAPTER_ORDER else 999
    article_order = TUTORIAL_ARTICLE_ORDER.get(category, [])
    article_index = article_order.index(article.title) if article.title in article_order else 999
    timestamp = article.updated_at or article.created_at or datetime.utcnow()
    return (category_index, article_index, timestamp)


def _group_tutorials(articles: Iterable[Content]) -> list[tuple[str, list[Content]]]:
    grouped: dict[str, list[Content]] = {}
    for article in sorted(articles, key=_compare_tutorials):
        category = _tutorial_category(article)
        grouped.setdefault(category, []).append(article)
    return list(grouped.items())


def _ordered_tutorials(articles: Iterable[Content]) -> list[Content]:
    return sorted(articles, key=_compare_tutorials)


def _find_tutorial_neighbors(articles: Iterable[Content], current_identifier: str) -> tuple[Content | None, Content | None]:
    ordered = _ordered_tutorials(articles)
    for index, article in enumerate(ordered):
        if _article_identifier(article) != current_identifier:
            continue
        previous_article = ordered[index - 1] if index > 0 else None
        next_article = ordered[index + 1] if index + 1 < len(ordered) else None
        return previous_article, next_article
    return None, None


def _extract_article_summary(article: Content) -> str:
    html = render_markdown(_tutorial_markdown(article))
    soup = BeautifulSoup(html, "html.parser")
    paragraph = soup.find(["p", "li"])
    if paragraph:
        text = _normalize_text(paragraph.get_text(" ", strip=True))
        if text:
            return text[:140]
    text = _normalize_text(soup.get_text(" ", strip=True))
    return text[:140] if text else "这篇文章围绕 GEO 实战主题，拆解关键步骤、判断依据与可复用方法。"


def _build_channel_step_copy(category: str, items: list[Content]) -> tuple[str, str]:
    latest = sorted(items, key=lambda item: item.updated_at or item.created_at or datetime.utcnow(), reverse=True)[0]
    primary = f"这个章节收录 {len(items)} 篇围绕「{category}」展开的教程文章，按照执行场景组织，适合从基础理解一路读到落地模板。"
    secondary = f"建议先打开《{latest.title}》，这是当前该章节最近一次更新的内容。"
    return primary, secondary


def _decorate_article_html(html_body: str) -> tuple[str, list[dict[str, str]]]:
    soup = BeautifulSoup(html_body or "", "html.parser")
    headings: list[dict[str, str]] = []
    existing_ids: set[str] = set()

    for paragraph in soup.find_all(["p", "li"]):
        text = _normalize_text(paragraph.get_text(" ", strip=True))
        if text.startswith("下一篇《") or text.startswith("上一篇《"):
            paragraph.decompose()

    for heading in soup.find_all(["h2", "h3", "h4"]):
        text = _normalize_text(heading.get_text(" ", strip=True))
        base_id = _slugify(text) or f"section-{len(headings) + 1}"
        candidate = base_id
        suffix = 2
        while candidate in existing_ids:
            candidate = f"{base_id}-{suffix}"
            suffix += 1
        heading["id"] = candidate
        existing_ids.add(candidate)
        headings.append({
            "id": candidate,
            "title": text,
            "level": heading.name.upper(),
        })

    return str(soup), headings


def _render_json_ld(*payloads: dict) -> str:
    return "\n".join(
        f'<script type="application/ld+json">{json.dumps(payload, ensure_ascii=False)}</script>'
        for payload in payloads if payload
    )


def _render_article_nav(previous_article: Content | None, next_article: Content | None) -> str:
    if not previous_article and not next_article:
        return ""

    links: list[str] = []
    if previous_article:
        links.append(
            f'<a class="tutorial-article-nav-link" href="{escape(_tutorial_detail_path(previous_article))}">'
            f'<span class="tutorial-article-nav-label">上一篇</span>'
            f'<span class="tutorial-article-nav-title">{escape(previous_article.title)}</span>'
            f"</a>"
        )
    if next_article:
        links.append(
            f'<a class="tutorial-article-nav-link" href="{escape(_tutorial_detail_path(next_article))}">'
            f'<span class="tutorial-article-nav-label">下一篇</span>'
            f'<span class="tutorial-article-nav-title">{escape(next_article.title)}</span>'
            f"</a>"
        )

    return f"""
    <nav class="tutorial-article-nav" aria-label="文章前后导航">
        <div class="tutorial-article-nav-links">
            {''.join(links)}
        </div>
    </nav>
    """


def _render_side_nav(request: Request, groups: list[tuple[str, list[Content]]], current_identifier: str = "") -> str:
    return "".join(
        f"""
        <section class="tutorial-nav-group">
            <div class="tutorial-nav-group-header">
                <span class="material-symbols-outlined tutorial-nav-group-icon">{escape(TUTORIAL_CHAPTER_ICONS.get(category, "library_books"))}</span>
                <p class="tutorial-nav-group-title">{escape(category)}</p>
            </div>
            <div class="tutorial-nav-tree">
                {''.join(
                    f'''
                    <a
                        href="{escape(_tutorial_detail_path(article))}"
                        class="tutorial-side-link {'is-active' if _article_identifier(article) == current_identifier else ''}"
                        data-tutorial-key="{escape(_article_identifier(article))}"
                    >
                        <span class="tutorial-side-link-main">
                            <span class="material-symbols-outlined tutorial-side-link-icon">article</span>
                            <span class="tutorial-side-link-label">{escape(article.title)}</span>
                        </span>
                    </a>
                    '''
                    for article in items
                )}
            </div>
        </section>
        """
        for category, items in groups
    )


def _render_mobile_nav(articles: list[Content], current_identifier: str = "") -> str:
    return "".join(
        f'''
        <a
            href="{escape(_tutorial_detail_path(article))}"
            class="tutorial-mobile-chip {'is-active' if _article_identifier(article) == current_identifier else ''}"
            data-tutorial-key="{escape(_article_identifier(article))}"
        >
            {escape(article.title)}
        </a>
        '''
        for article in articles
    )


def _render_channel_flow_item(article: Content, item_index: int) -> str:
    open_attr = "open" if item_index == 0 else ""
    return f"""
    <details class="tutorial-flow-item" {open_attr}>
        <summary class="tutorial-flow-summary">
            <span class="tutorial-flow-summary-main">
                <span class="material-symbols-outlined tutorial-flow-summary-icon">chevron_right</span>
                <span class="tutorial-flow-summary-title">{escape(article.title)}</span>
            </span>
            <span class="tutorial-flow-summary-meta">{_tutorial_reading_time(article)} 分钟</span>
        </summary>
        <div class="tutorial-flow-panel">
            <p class="tutorial-flow-panel-text">{escape(_extract_article_summary(article))}</p>
            <div class="tutorial-flow-panel-meta">
                <span>更新于 {_format_date(article.updated_at or article.created_at)}</span>
                <span>{int(article.view_count or 0)} 次阅读</span>
            </div>
            <a
                href="{escape(_tutorial_detail_path(article))}"
                class="tutorial-flow-panel-link"
                data-tutorial-key="{escape(_article_identifier(article))}"
            >
                阅读这篇文章
                <span class="material-symbols-outlined text-base">arrow_forward</span>
            </a>
        </div>
    </details>
    """


def _render_channel_flow_group(index: int, category: str, items: list[Content]) -> str:
    step_copy = _build_channel_step_copy(category, items)
    item_markup = "".join(
        _render_channel_flow_item(article, item_index)
        for item_index, article in enumerate(items)
    )
    return f"""
    <section id="tutorial-group-{escape(_slugify(category))}" class="tutorial-flow-step">
        <div class="tutorial-flow-step-marker">
            <span class="tutorial-flow-step-index">{index + 1}</span>
        </div>
        <div class="tutorial-flow-step-body">
            <p class="tutorial-flow-step-kicker">章节 {str(index + 1).zfill(2)}</p>
            <h3 class="tutorial-flow-step-title">{escape(category)}</h3>
            <p class="tutorial-flow-step-text">{escape(step_copy[0])}</p>
            <p class="tutorial-flow-step-text tutorial-flow-step-text-muted">{escape(step_copy[1])}</p>
            <div class="tutorial-flow-accordion">
                {item_markup}
            </div>
        </div>
    </section>
    """


def _render_channel_home_article(groups: list[tuple[str, list[Content]]]) -> str:
    group_markup = "".join(
        _render_channel_flow_group(index, category, items)
        for index, (category, items) in enumerate(groups)
    )
    return f"""
    <div class="tutorial-flow">
        {group_markup}
    </div>
    """


def _render_channel_toc(groups: list[tuple[str, list[Content]]]) -> str:
    return f"""
    <div class="tutorial-channel-sidebar">
        <section class="space-y-2">
            {''.join(
                f'''
                <a href="#tutorial-group-{escape(_slugify(category))}" class="tutorial-channel-sidebar-step-link tutorial-toc-link">
                    <span class="tutorial-channel-sidebar-step-index">{index + 1}</span>
                    <span>{escape(category)}</span>
                </a>
                '''
                for index, (category, _) in enumerate(groups)
            )}
        </section>
    </div>
    """


def _render_article_toc(headings: list[dict[str, str]]) -> str:
    if not headings:
        return '<span class="block text-sm text-slate-400 px-3 py-1.5">当前文章暂无目录</span>'

    links = []
    for heading in headings:
        padding_class = "pl-3"
        if heading["level"] == "H3":
            padding_class = "pl-6"
        elif heading["level"] == "H4":
            padding_class = "pl-9"
        links.append(
            f'<a href="#{escape(heading["id"])}" class="tutorial-toc-link {padding_class}">{escape(heading["title"])}</a>'
        )
    return "".join(links)


def _render_meta_tags(
    *,
    title: str,
    description: str,
    canonical_url: str,
    cover_image_url: str | None = None,
    keywords: list[str] | None = None,
    og_type: str = "website",
    article_section: str | None = None,
) -> str:
    tags = [
        f"<title>{escape(title)}</title>",
        f'<meta name="description" content="{escape(description)}">',
        f'<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">',
        f'<link rel="canonical" href="{escape(canonical_url)}">',
        f'<meta property="og:site_name" content="GEOrank">',
        f'<meta property="og:type" content="{escape(og_type)}">',
        f'<meta property="og:title" content="{escape(title)}">',
        f'<meta property="og:description" content="{escape(description)}">',
        f'<meta property="og:url" content="{escape(canonical_url)}">',
        f'<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{escape(title)}">',
        f'<meta name="twitter:description" content="{escape(description)}">',
    ]
    if cover_image_url:
        tags.append(f'<meta property="og:image" content="{escape(cover_image_url)}">')
        tags.append(f'<meta name="twitter:image" content="{escape(cover_image_url)}">')
    if keywords:
        tags.append(f'<meta name="keywords" content="{escape(", ".join(keywords))}">')
    if article_section:
        tags.append(f'<meta property="article:section" content="{escape(article_section)}">')
    return "\n    ".join(tags)


def _render_page(
    *,
    title: str,
    description: str,
    canonical_url: str,
    side_nav_html: str,
    mobile_nav_html: str,
    breadcrumb_category: str,
    breadcrumb_title: str,
    heading_title: str,
    overview_html: str,
    reading_meta_html: str,
    updated_meta_html: str,
    article_html: str,
    article_nav_html: str,
    toc_title: str,
    toc_html: str,
    feedback_hidden: bool,
    page_class: str = "",
    structured_data: str = "",
    cover_image_url: str | None = None,
    keywords: list[str] | None = None,
    og_type: str = "website",
    article_section: str | None = None,
) -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    {_render_meta_tags(
        title=title,
        description=description,
        canonical_url=canonical_url,
        cover_image_url=cover_image_url,
        keywords=keywords,
        og_type=og_type,
        article_section=article_section,
    )}
    <style>body{{opacity:0;transition:opacity 0.15s ease}}</style>
    <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
    <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
    <script src="/js/tailwind.config.js"></script>
    <link rel="stylesheet" href="/css/common.css?v=20260613-common-hidden-fix">
    <link rel="stylesheet" href="/css/tutorial.css">
    {structured_data}
</head>
<body class="bg-white text-on-surface antialiased {escape(page_class)}">
    <div id="header-container"></div>

    <div class="tutorial-page-frame max-w-7xl mx-auto bg-white min-h-screen relative">
        <div class="flex pt-16 md:pt-24">
            <main class="order-2 flex-1 bg-white min-h-screen border-r border-slate-100">
                <div class="flex flex-col">
                <div id="tutorial-main-shell" class="order-2 max-w-3xl mx-auto px-4 md:px-8 py-8 md:py-12">
                    <nav class="flex flex-wrap items-center gap-1 text-xs font-medium text-slate-400 mb-6 md:mb-8">
                        <a href="/" class="hover:text-primary transition-colors">首页</a>
                        <span class="material-symbols-outlined text-[14px]">chevron_right</span>
                        <a href="/tutorial" id="tutorial-breadcrumb-category" class="hover:text-primary transition-colors">{escape(breadcrumb_category)}</a>
                        <span class="material-symbols-outlined text-[14px]">chevron_right</span>
                        <span id="tutorial-breadcrumb-title" class="text-on-surface">{escape(breadcrumb_title)}</span>
                    </nav>

                    <header id="tutorial-header" class="mb-8 md:mb-10">
                        <h1 id="tutorial-title" class="text-2xl md:text-3xl lg:text-4xl font-extrabold tracking-tight font-headline mb-4">{escape(heading_title)}</h1>
                        <p id="tutorial-overview" class="{'hidden ' if not overview_html else ''}max-w-2xl text-sm md:text-[15px] leading-8 text-slate-500 mb-5">{overview_html}</p>
                        <div class="flex flex-wrap items-center gap-4 text-xs text-on-surface-variant font-medium">
                            <div id="tutorial-reading-time" class="flex items-center gap-1.5">{reading_meta_html}</div>
                            <div id="tutorial-updated-at" class="flex items-center gap-1.5 {'hidden' if not updated_meta_html else ''}">{updated_meta_html}</div>
                        </div>
                    </header>

                    <article id="tutorial-article" class="max-w-none">
                        {article_html}
                    </article>

                    {article_nav_html}

                    <section id="tutorial-feedback" class="{'hidden ' if feedback_hidden else ''}mt-16 pt-10 border-t border-slate-100 flex flex-col md:flex-row items-center justify-between gap-6">
                        <div>
                            <h4 class="text-sm font-bold mb-1">这篇文章对您有帮助吗？</h4>
                            <p class="text-xs text-on-surface-variant">您的反馈将帮助我们改进文档。</p>
                        </div>
                        <div class="flex gap-3">
                            <button class="flex items-center gap-2 px-5 py-2 rounded-lg bg-white text-sm text-slate-600 hover:bg-primary hover:text-white transition-all font-medium border border-slate-100">
                                <span class="material-symbols-outlined text-base">thumb_up</span>
                                <span>有帮助</span>
                            </button>
                            <button class="flex items-center gap-2 px-5 py-2 rounded-lg bg-white text-sm text-slate-600 hover:bg-slate-100 transition-all font-medium border border-slate-100">
                                <span class="material-symbols-outlined text-base">thumb_down</span>
                                <span>待改进</span>
                            </button>
                        </div>
                    </section>
                </div>
                <div class="order-1 lg:hidden overflow-x-auto scrollbar-hide border-b border-slate-100 bg-white sticky top-16 z-10">
                    <div id="tutorial-mobile-nav" class="flex gap-1 px-4 py-2 min-w-max">
                        {mobile_nav_html}
                    </div>
                </div>
                </div>
            </main>

            <aside class="order-1 tutorial-sticky-sidebar tutorial-sticky-sidebar-left hidden lg:flex flex-col p-6 space-y-2 w-64 border-r border-slate-100 bg-white overflow-y-auto scrollbar-hide">
                <div class="mb-6">
                    <h2 class="text-sm font-bold font-headline">教程中心</h2>
                    <p class="text-[10px] font-bold text-on-surface-variant">GEO 科普教程与最佳实践</p>
                </div>
                <nav class="flex flex-col space-y-1" id="side-nav">
                    {side_nav_html}
                </nav>
            </aside>

            <aside id="tutorial-secondary" class="order-3 tutorial-sticky-sidebar tutorial-sticky-sidebar-right hidden xl:block w-64 p-6 overflow-y-auto bg-white">
                <h3 id="tutorial-secondary-title" class="text-xs font-bold text-slate-400 tracking-widest uppercase mb-5">{escape(toc_title)}</h3>
                <nav class="space-y-1" id="toc-nav">
                    {toc_html}
                </nav>
                <div class="mt-10 p-5 rounded-xl border border-slate-100 bg-white">
                    <h4 class="text-xs font-bold mb-1.5">需要更多帮助？</h4>
                    <p class="text-xs text-on-surface-variant mb-3 leading-relaxed">联系我们的解决方案架构师，获取定制化的 GEO 优化方案。</p>
                    <a href="/solutions" class="text-xs font-semibold text-primary flex items-center gap-1 group">
                        提交咨询单
                        <span class="material-symbols-outlined text-sm group-hover:translate-x-1 transition-transform">arrow_forward</span>
                    </a>
                </div>
            </aside>
        </div>
    </div>

    <div id="footer-container"></div>

    <script src="/js/common.js?v=20260613-site-settings2"></script>
    <script src="/js/tutorial.js?v=20260613-site-settings2"></script>
</body>
</html>"""
    return HTMLResponse(content=html)


def _home_structured_data(request: Request, groups: list[tuple[str, list[Content]]]) -> str:
    flat_articles = [article for _, items in groups for article in items]
    collection_page = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "GEO 教程中心",
        "description": SITE_DESCRIPTION,
        "url": _absolute_url(request, "/tutorial"),
        "isPartOf": {
            "@type": "WebSite",
            "name": "GEOrank",
            "url": _absolute_url(request, "/"),
        },
        "about": ["GEO", "生成式引擎优化", "AI 搜索", "品牌增长"],
    }
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": _absolute_url(request, "/")},
            {"@type": "ListItem", "position": 2, "name": "教程", "item": _absolute_url(request, "/tutorial")},
        ],
    }
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "GEO 教程目录",
        "itemListOrder": "https://schema.org/ItemListOrderAscending",
        "numberOfItems": len(flat_articles),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index + 1,
                "name": article.title,
                "url": _tutorial_detail_url(request, article),
            }
            for index, article in enumerate(flat_articles)
        ],
    }
    return _render_json_ld(collection_page, breadcrumbs, item_list)


def _article_structured_data(request: Request, article: Content, description: str, category: str) -> str:
    url = _tutorial_detail_url(request, article)
    article_schema = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": article.title,
        "name": article.title,
        "description": description,
        "inLanguage": "zh-CN",
        "url": url,
        "mainEntityOfPage": url,
        "datePublished": _format_iso(article.created_at),
        "dateModified": _format_iso(article.updated_at or article.created_at),
        "articleSection": category,
        "keywords": article.tags if isinstance(article.tags, list) else [],
        "timeRequired": f"PT{_tutorial_reading_time(article)}M",
        "author": {
            "@type": "Organization",
            "name": "GEOrank",
            "url": _absolute_url(request, "/"),
        },
        "publisher": {
            "@type": "Organization",
            "name": "GEOrank",
            "url": _absolute_url(request, "/"),
            "logo": {
                "@type": "ImageObject",
                "url": _absolute_url(request, "/images/favicon.svg"),
            },
        },
        "image": _cover_image_url(request, article),
    }
    article_schema = {key: value for key, value in article_schema.items() if value not in (None, "", [])}
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": _absolute_url(request, "/")},
            {"@type": "ListItem", "position": 2, "name": "教程", "item": _absolute_url(request, "/tutorial")},
            {"@type": "ListItem", "position": 3, "name": article.title, "item": url},
        ],
    }
    return _render_json_ld(article_schema, breadcrumbs)


async def _load_published_tutorials(db: DbSession) -> list[Content]:
    result = await db.execute(
        select(Content)
        .where(Content.status == ContentStatus.PUBLISHED, Content.content_type == ContentType.TUTORIAL)
    )
    return list(result.scalars())


async def _find_tutorial(identifier: str, db: DbSession) -> Content | None:
    normalized = (identifier or "").strip().lower()
    if not normalized:
        return None

    result = await db.execute(
        select(Content).where(
            Content.status == ContentStatus.PUBLISHED,
            Content.content_type == ContentType.TUTORIAL,
            (Content.path_key == normalized) | (Content.slug == normalized),
        )
    )
    return result.scalar_one_or_none()


@router.get("/tutorial", response_class=HTMLResponse)
async def tutorial_home(request: Request, db: DbSession, slug: str | None = None):
    if slug:
        article = await _find_tutorial(slug, db)
        if article:
            return RedirectResponse(url=_tutorial_detail_path(article), status_code=301)

    tutorials = await _load_published_tutorials(db)
    groups = _group_tutorials(tutorials)
    if not groups:
        return _render_page(
            title="GEO 教程中心 - GEOrank",
            description=SITE_DESCRIPTION,
            canonical_url=_absolute_url(request, "/tutorial"),
            side_nav_html='<div class="tutorial-state-card">当前还没有已发布教程</div>',
            mobile_nav_html='<span class="px-3 py-1.5 text-xs font-medium text-slate-400 whitespace-nowrap">当前还没有已发布教程</span>',
            breadcrumb_category="教程",
            breadcrumb_title="频道首页",
            heading_title="GEO 教程中心",
            overview_html=HOME_OVERVIEW,
            reading_meta_html='<span class="material-symbols-outlined text-sm">library_books</span> 已收录：0 篇文章',
            updated_meta_html="",
            article_html='<div class="tutorial-state-card">当前还没有已发布教程</div>',
            article_nav_html="",
            toc_title="栏目索引",
            toc_html='<span class="block text-sm text-slate-400 px-3 py-1.5">暂无目录</span>',
            feedback_hidden=True,
            page_class="tutorial-channel-home",
        )

    tutorials_sorted = _ordered_tutorials(tutorials)
    return _render_page(
        title="GEO 教程中心 - GEOrank",
        description=SITE_DESCRIPTION,
        canonical_url=_absolute_url(request, "/tutorial"),
        side_nav_html=_render_side_nav(request, groups),
        mobile_nav_html=_render_mobile_nav(tutorials_sorted),
        breadcrumb_category="教程",
        breadcrumb_title="频道首页",
        heading_title="GEO 教程中心",
        overview_html=escape(HOME_OVERVIEW),
        reading_meta_html=f'<span class="material-symbols-outlined text-sm">library_books</span> 已收录：{len(tutorials_sorted)} 篇文章',
        updated_meta_html="",
        article_html=_render_channel_home_article(groups),
        article_nav_html="",
        toc_title="栏目索引",
        toc_html=_render_channel_toc(groups),
        feedback_hidden=True,
        page_class="tutorial-channel-home",
        structured_data=_home_structured_data(request, groups),
        keywords=["GEO", "生成式引擎优化", "AI 搜索", "教程"],
    )


@router.get("/tutorial/{identifier}", response_class=HTMLResponse)
async def tutorial_detail(identifier: str, request: Request, db: DbSession):
    article = await _find_tutorial(identifier, db)
    if not article:
        return HTMLResponse(status_code=404, content="教程不存在")

    canonical_identifier = _article_identifier(article)
    if identifier != canonical_identifier:
        return RedirectResponse(url=_tutorial_detail_path(article), status_code=301)

    tutorials = await _load_published_tutorials(db)
    groups = _group_tutorials(tutorials)
    public_markdown = _tutorial_markdown(article)
    article_html, headings = _decorate_article_html(render_markdown(public_markdown))
    description = _extract_article_summary(article) or SITE_DESCRIPTION
    category = _tutorial_category(article)
    previous_article, next_article = _find_tutorial_neighbors(tutorials, canonical_identifier)
    reading_time = _tutorial_reading_time(article)

    return _render_page(
        title=f"{article.title} - GEOrank",
        description=description,
        canonical_url=_tutorial_detail_url(request, article),
        side_nav_html=_render_side_nav(request, groups, current_identifier=canonical_identifier),
        mobile_nav_html=_render_mobile_nav(sorted(tutorials, key=_compare_tutorials), current_identifier=canonical_identifier),
        breadcrumb_category=category,
        breadcrumb_title=article.title,
        heading_title=article.title,
        overview_html="",
        reading_meta_html=f'<span class="material-symbols-outlined text-sm">schedule</span> {escape(_format_reading_time(reading_time))}',
        updated_meta_html=f'<span class="material-symbols-outlined text-sm">update</span> 最后更新：{escape(_format_date(article.updated_at or article.created_at))}',
        article_html=f'<div class="prose tutorial-prose max-w-none">{article_html}</div>',
        article_nav_html=_render_article_nav(previous_article, next_article),
        toc_title="目录",
        toc_html=_render_article_toc(headings),
        feedback_hidden=False,
        structured_data=_article_structured_data(request, article, description, category),
        cover_image_url=_cover_image_url(request, article),
        keywords=(article.tags if isinstance(article.tags, list) else []) or ["GEO", "教程"],
        og_type="article",
        article_section=category,
    )
