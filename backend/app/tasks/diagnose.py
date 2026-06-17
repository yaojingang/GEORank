"""
GEO 诊断分析任务 — 确定性规则引擎 + LLM 优化建议
"""
import json
import logging
import uuid
import enum
import re
from statistics import mean

from celery import shared_task
from app.core.logging_utils import log_event
from app.tasks.runtime import run_async as _run

logger = logging.getLogger("georank.diagnose")


def _normalize_update_values(values: dict) -> dict:
    """Convert Enum members to their database labels for Core updates."""
    normalized = {}
    for key, value in values.items():
        normalized[key] = value.value if isinstance(value, enum.Enum) else value
    return normalized

DEFAULT_DIAGNOSTIC_RULE_WEIGHTS = {
    "schema": 0.3,
    "content": 0.3,
    "meta": 0.2,
    "citation": 0.2,
}


# ===== 确定性规则检测 =====

def _check_schema(soup) -> dict:
    """检测 JSON-LD Schema 标签"""
    import json as _json
    scripts = soup.find_all("script", type="application/ld+json")
    found_types = []
    raw_schemas = []

    for s in scripts:
        try:
            data = _json.loads(s.string or "")
            if isinstance(data, list):
                for item in data:
                    t = item.get("@type", "")
                    if t:
                        found_types.append(t)
                        raw_schemas.append(item)
            elif isinstance(data, dict):
                t = data.get("@type", "")
                if t:
                    found_types.append(t)
                    raw_schemas.append(data)
        except Exception:
            pass

    unique_types = list(dict.fromkeys(found_types))
    recommended = ["WebSite", "Organization", "FAQPage", "Article", "BreadcrumbList"]
    missing = [t for t in recommended if t not in unique_types]

    coverage_ratio = round((len(set(unique_types) & set(recommended)) / len(recommended)) * 100) if recommended else 0
    score = min(100, max(len(unique_types) * 16, coverage_ratio))
    return {
        "found_types": unique_types,
        "missing_recommended": missing,
        "schema_count": len(scripts),
        "score": score,
        "coverage_ratio": coverage_ratio,
        "has_faq": "FAQPage" in unique_types,
        "has_org": "Organization" in unique_types or "WebSite" in unique_types,
        "has_article": "Article" in unique_types,
        "has_breadcrumb": "BreadcrumbList" in unique_types,
        "has_product": "Product" in unique_types,
        "has_website": "WebSite" in unique_types,
    }


def _check_meta(soup) -> dict:
    """检测 Meta / Open Graph / Twitter Card 标签"""
    checks = {}

    title_tag = soup.find("title")
    html_tag = soup.find("html")
    checks["title"] = bool(title_tag and title_tag.text.strip())
    checks["title_length"] = len(title_tag.text.strip()) if title_tag else 0
    checks["html_lang"] = bool(html_tag and html_tag.get("lang", "").strip())

    desc = soup.find("meta", attrs={"name": "description"})
    checks["meta_description"] = bool(desc and desc.get("content", "").strip())
    checks["meta_description_length"] = len(desc.get("content", "")) if desc else 0

    canonical = soup.find("link", rel="canonical")
    checks["canonical"] = bool(canonical and canonical.get("href"))

    viewport = soup.find("meta", attrs={"name": "viewport"})
    robots = soup.find("meta", attrs={"name": "robots"})
    favicon = soup.find("link", rel=lambda value: value and "icon" in value.lower())
    checks["viewport"] = bool(viewport and viewport.get("content"))
    checks["robots"] = bool(robots and robots.get("content"))
    checks["favicon"] = bool(favicon and favicon.get("href"))

    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    og_image = soup.find("meta", property="og:image")
    og_type = soup.find("meta", property="og:type")
    og_locale = soup.find("meta", property="og:locale")
    checks["og_title"] = bool(og_title and og_title.get("content"))
    checks["og_description"] = bool(og_desc and og_desc.get("content"))
    checks["og_image"] = bool(og_image and og_image.get("content"))
    checks["og_type"] = bool(og_type and og_type.get("content"))
    checks["og_locale"] = bool(og_locale and og_locale.get("content"))

    tw_card = soup.find("meta", attrs={"name": "twitter:card"})
    checks["twitter_card"] = bool(tw_card and tw_card.get("content"))

    passed = sum(1 for v in checks.values() if v is True)
    total_bool = sum(1 for v in checks.values() if isinstance(v, bool))
    score = round(passed / total_bool * 100) if total_bool else 0

    missing = [k for k, v in checks.items() if v is False]
    return {
        "checks": checks,
        "missing": missing,
        "score": score,
        "preview_score": round(mean([
            100 if checks["title"] else 0,
            100 if checks["meta_description"] else 0,
            100 if checks["og_title"] else 0,
            100 if checks["og_description"] else 0,
            100 if checks["og_image"] else 0,
            100 if checks["twitter_card"] else 0,
        ])),
    }


def _check_content(soup) -> dict:
    """检测内容结构：标题层级、段落质量"""
    h1s = soup.find_all("h1")
    h2s = soup.find_all("h2")
    h3s = soup.find_all("h3")
    paragraphs = soup.find_all("p")
    lists = soup.find_all(["ul", "ol"])
    tables = soup.find_all("table")
    images = soup.find_all("img")
    buttons = soup.find_all(["button", "a"])

    h1_count = len(h1s)
    h2_count = len(h2s)
    h3_count = len(h3s)
    para_count = len(paragraphs)

    # 首段是否直接回答核心问题（长度 > 80 字符视为有实质内容）
    first_para = paragraphs[0].get_text(strip=True) if paragraphs else ""
    first_para_quality = len(first_para) > 80

    # 标题层级合理性
    has_single_h1 = h1_count == 1
    has_h2_structure = h2_count >= 2
    heading_hierarchy_ok = has_single_h1 and has_h2_structure

    # 内容长度
    body_text = soup.get_text(separator=" ", strip=True)
    word_count = len(body_text.split())
    character_count = len(re.sub(r"\s+", "", body_text))
    reading_time_minutes = max(1, round(max(character_count, 1) / 450))

    headings = [tag.get_text(" ", strip=True) for tag in soup.find_all(["h1", "h2", "h3", "h4"])]
    faq_like_sections = sum(1 for text in headings if re.search(r"(faq|常见问题|问题|q&a)", text, re.IGNORECASE))

    image_count = len(images)
    image_with_alt_count = sum(1 for image in images if image.get("alt", "").strip())
    image_alt_ratio = round((image_with_alt_count / image_count) * 100) if image_count else 100

    cta_keywords = ("联系", "咨询", "预约", "试用", "联系销售", "立即开始", "demo", "contact", "pricing")
    cta_count = sum(
        1 for button in buttons
        if any(keyword in button.get_text(" ", strip=True).lower() for keyword in cta_keywords)
    )

    score = 0
    if has_single_h1:
        score += 20
    if has_h2_structure:
        score += 20
    if first_para_quality:
        score += 20
    if character_count > 800:
        score += 20
    if image_alt_ratio >= 60:
        score += 10
    if faq_like_sections >= 1 or len(lists) >= 2:
        score += 10

    return {
        "h1_count": h1_count,
        "h2_count": h2_count,
        "h3_count": h3_count,
        "paragraph_count": para_count,
        "word_count": word_count,
        "character_count": character_count,
        "reading_time_minutes": reading_time_minutes,
        "has_single_h1": has_single_h1,
        "has_h2_structure": has_h2_structure,
        "first_para_quality": first_para_quality,
        "heading_hierarchy_ok": heading_hierarchy_ok,
        "list_count": len(lists),
        "table_count": len(tables),
        "image_count": image_count,
        "image_with_alt_count": image_with_alt_count,
        "image_alt_ratio": image_alt_ratio,
        "faq_like_sections": faq_like_sections,
        "cta_count": cta_count,
        "score": min(100, score),
    }


def _check_citations(soup, base_domain: str) -> dict:
    """检测外部链接与权威引用密度"""
    from urllib.parse import urlparse

    authority_domains = {
        "arxiv.org", "scholar.google.com", "pubmed.ncbi.nlm.nih.gov",
        "doi.org", "ieee.org", "acm.org", "nature.com", "science.org",
        "wikipedia.org", "gov", "edu",
    }
    social_domains = {
        "linkedin.com", "x.com", "twitter.com", "github.com", "youtube.com",
        "wechat.com", "weixin.qq.com", "zhihu.com", "bilibili.com",
    }

    all_links = soup.find_all("a", href=True)
    external_links = []
    authority_links = []
    internal_links = []
    social_links = []

    for a in all_links:
        href = a.get("href", "")
        try:
            parsed = urlparse(href)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                domain = parsed.netloc.lower()
                if base_domain not in domain:
                    external_links.append(href)
                    if any(auth in domain for auth in authority_domains):
                        authority_links.append(href)
                    if any(social in domain for social in social_domains):
                        social_links.append(href)
                else:
                    internal_links.append(href)
        except Exception:
            pass

    ext_count = len(external_links)
    auth_count = len(authority_links)
    internal_count = len(internal_links)
    social_count = len(social_links)

    score = 0
    if ext_count >= 3:
        score += 40
    elif ext_count >= 1:
        score += 20
    if auth_count >= 2:
        score += 40
    elif auth_count >= 1:
        score += 20
    if ext_count >= 10 or internal_count >= 12:
        score += 20

    return {
        "external_link_count": ext_count,
        "authority_link_count": auth_count,
        "internal_link_count": internal_count,
        "social_link_count": social_count,
        "authority_links": authority_links[:5],
        "social_links": social_links[:5],
        "score": min(100, score),
    }


async def _llm_recommendations(url: str, schema: dict, meta: dict, content: dict, citation: dict) -> dict:
    """调用 LLM 生成优先级排序的优化建议"""
    from app.services.ai_client import ai_client

    summary = f"""网站: {url}
Schema 评分: {schema['score']}/100，已有类型: {schema['found_types']}，缺失: {schema['missing_recommended']}
Meta 评分: {meta['score']}/100，缺失: {meta['missing']}，预览得分: {meta.get('preview_score', 0)}
内容评分: {content['score']}/100，H1数量: {content['h1_count']}，字符数: {content.get('character_count', 0)}，列表: {content.get('list_count', 0)}，图片Alt覆盖: {content.get('image_alt_ratio', 0)}%
引用评分: {citation['score']}/100，外链: {citation['external_link_count']}，权威引用: {citation['authority_link_count']}，站内链接: {citation.get('internal_link_count', 0)}"""

    system = """你是 GEO（生成式引擎优化）专家。根据网站诊断数据，返回 JSON 格式的分析与建议：
{
  "summary": {
    "headline": "...",
    "overview": "...",
    "priority_action": "..."
  },
  "strengths": ["..."],
  "gaps": ["..."],
  "urgent": [{"item": "...", "action": "..."}],
  "recommended": [{"item": "...", "action": "..."}],
  "optional": [{"item": "...", "action": "..."}],
  "phase_plan": [{"phase": "P0", "title": "...", "goal": "...", "success_metric": "..."}]
}
要求：
1. summary.overview 控制在 120 字内，适合直接展示在诊断报告顶部。
2. strengths 和 gaps 各最多 3 条，强调可见的优劣势。
3. urgent / recommended / optional 各最多 3 条。
4. action 必须给具体操作步骤，避免空泛表达。
5. phase_plan 最多 3 条，分别对应 P0/P1/P2 的执行节奏。
6. 严格返回 JSON。"""

    try:
        raw = await ai_client.complete(system, summary, temperature=0.2)
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except Exception as e:
        logger.warning("LLM recommendations failed: %s", e)

    # 降级：基于规则生成建议
    urgent, recommended = [], []
    if not schema["has_org"]:
        urgent.append({"item": "缺少 Organization/WebSite Schema", "action": "在 <head> 中添加 JSON-LD Organization Schema，包含 name、url、description、logo 字段"})
    if not schema["has_faq"] and content["h2_count"] >= 3:
        recommended.append({"item": "建议添加 FAQPage Schema", "action": "将页面中的问答内容标记为 FAQPage Schema，提升 AI 搜索引擎摘要提取率"})
    if not meta["checks"].get("meta_description"):
        urgent.append({"item": "缺少 meta description", "action": "添加 150-160 字符的 meta description，包含核心关键词"})
    if not meta["checks"].get("og_image"):
        recommended.append({"item": "缺少 og:image", "action": "添加 1200×630px 的 og:image，提升社交分享和 AI 摘要图片展示"})
    if not content["has_single_h1"]:
        urgent.append({"item": f"H1 标签数量异常（{content['h1_count']}个）", "action": "每页只保留一个 H1 标签，清晰表达页面主题"})

    strengths = []
    if schema["score"] >= 80:
        strengths.append("结构化 Schema 覆盖较完整，AI 更容易识别页面实体与上下文。")
    if meta["score"] >= 80:
        strengths.append("Meta 与 Open Graph 信息较完整，有利于摘要抓取和结果展示。")
    if citation["authority_link_count"] >= 1:
        strengths.append("页面已具备基础权威引用，能够增强答案可信度。")

    gaps = []
    if schema["missing_recommended"]:
        gaps.append(f"缺少 { '、'.join(schema['missing_recommended'][:3]) } 等关键 Schema 类型。")
    if not content["first_para_quality"]:
        gaps.append("首段缺少直达答案式表达，不利于 AI 快速生成摘要。")
    if citation["score"] < 40:
        gaps.append("权威引用密度偏低，页面缺少足够的外部信任背书。")

    overall = _calculate_overall_score(
        schema["score"],
        content["score"],
        meta["score"],
        citation["score"],
    )
    headline = "页面具备一定 GEO 基础，但仍有明显优化空间。" if overall >= 60 else "页面 GEO 基础偏弱，建议先补齐结构化与内容要点。"
    if overall >= 80:
        headline = "页面 GEO 基础较强，适合继续优化引用与高价值页面结构。"

    priority_action = urgent[0]["action"] if urgent else (
        recommended[0]["action"] if recommended else "继续扩充 FAQ、案例与权威引用，提升 AI 引用概率。"
    )
    phase_plan = []
    if urgent:
        phase_plan.append({
            "phase": "P0",
            "title": urgent[0]["item"],
            "goal": urgent[0]["action"],
            "success_metric": "关键结构化与摘要信号补齐，页面可被 AI 稳定识别。",
        })
    if recommended:
        phase_plan.append({
            "phase": "P1",
            "title": recommended[0]["item"],
            "goal": recommended[0]["action"],
            "success_metric": "页面在摘要展示、问答引用与社交预览中更完整。",
        })
    phase_plan.append({
        "phase": "P2",
        "title": "持续补强引用与案例",
        "goal": "扩充 FAQ、案例、权威引用和内部链接，让页面在生成式答案里更容易被调用。",
        "success_metric": "权威引用密度和可引用段落数量持续增长。",
    })

    return {
        "summary": {
            "headline": headline,
            "overview": f"当前页面综合 GEO 评分为 {overall} 分。建议优先补齐结构化标记、首段答案表达与权威引用，再逐步优化开放图谱与内容层级。",
            "priority_action": priority_action,
        },
        "strengths": strengths[:3],
        "gaps": gaps[:3],
        "urgent": urgent[:3],
        "recommended": recommended[:3],
        "optional": [],
        "phase_plan": phase_plan[:3],
    }


def _calculate_overall_score(schema_score: float, content_score: float, meta_score: float, citation_score: float, weights: dict | None = None) -> int:
    """按权重计算综合分，权重无效时回退到默认值。"""
    active_weights = weights or DEFAULT_DIAGNOSTIC_RULE_WEIGHTS
    total = sum(max(0.0, float(value or 0)) for value in active_weights.values())
    if total <= 0:
        active_weights = DEFAULT_DIAGNOSTIC_RULE_WEIGHTS
        total = sum(active_weights.values())

    normalized = {
        "schema": max(0.0, float(active_weights.get("schema", DEFAULT_DIAGNOSTIC_RULE_WEIGHTS["schema"]))) / total,
        "content": max(0.0, float(active_weights.get("content", DEFAULT_DIAGNOSTIC_RULE_WEIGHTS["content"]))) / total,
        "meta": max(0.0, float(active_weights.get("meta", DEFAULT_DIAGNOSTIC_RULE_WEIGHTS["meta"]))) / total,
        "citation": max(0.0, float(active_weights.get("citation", DEFAULT_DIAGNOSTIC_RULE_WEIGHTS["citation"]))) / total,
    }

    return round(
        schema_score * normalized["schema"] +
        content_score * normalized["content"] +
        meta_score * normalized["meta"] +
        citation_score * normalized["citation"]
    )


async def _run_analysis(report_id: str):
    from app.core.database import async_session
    from app.models.diagnostic import DiagnosticReport, DiagnosticStatus
    from sqlalchemy import select, update
    from urllib.parse import urlparse
    from bs4 import BeautifulSoup

    async with async_session() as db:
        result = await db.execute(select(DiagnosticReport).where(DiagnosticReport.id == uuid.UUID(report_id)))
        report = result.scalar_one_or_none()
        if not report:
            return

        # 获取 HTML
        html = None
        if report.raw_html_key:
            from app.services.storage import storage
            raw = storage.get(report.raw_html_key)
            if raw:
                html = raw.decode("utf-8", errors="replace")

        if not html:
            # 直接 HTTP 获取（降级，不用 Playwright）
            import httpx
            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(report.url, headers={"User-Agent": "GEOrankBot/1.0"})
                    html = resp.text
            except Exception as e:
                await db.execute(
                    update(DiagnosticReport)
                    .where(DiagnosticReport.id == uuid.UUID(report_id))
                    .values(**_normalize_update_values({
                        "status": DiagnosticStatus.FAILED,
                        "error_message": f"无法获取页面内容: {e}",
                    }))
                )
                await db.commit()
                return

        soup = BeautifulSoup(html, "lxml")
        base_domain = urlparse(report.url).netloc

        schema = _check_schema(soup)
        meta = _check_meta(soup)
        content = _check_content(soup)
        citation = _check_citations(soup, base_domain)
        from app.services.runtime_settings import get_diagnostic_rule_config
        rule_config = await get_diagnostic_rule_config()
        overall = _calculate_overall_score(
            schema["score"],
            content["score"],
            meta["score"],
            citation["score"],
            rule_config.get("normalized_weights"),
        )

        recommendations = await _llm_recommendations(report.url, schema, meta, content, citation)

        await db.execute(
            update(DiagnosticReport)
            .where(DiagnosticReport.id == uuid.UUID(report_id))
            .values(**_normalize_update_values({
                "status": DiagnosticStatus.COMPLETED,
                "overall_score": overall,
                "schema_analysis": schema,
                "content_analysis": content,
                "meta_analysis": meta,
                "citation_analysis": citation,
                "recommendations": recommendations,
            }))
        )
        from app.services.ai_usage import record_async_task_usage
        await record_async_task_usage(
            db,
            module="diagnostics",
            user_id=report.user_id,
            input_text=f"{report.url}\n{html[:6000]}",
            output_text=json.dumps(recommendations, ensure_ascii=False),
            metadata={
                "report_id": str(report.id),
                "url": report.url,
                "overall_score": overall,
                "async_task": True,
            },
        )
        await db.commit()


@shared_task(name="app.tasks.diagnose.analyze_page", bind=True)
def analyze_page(self, report_id: str):
    """
    对爬取的页面进行 GEO 多维诊断:
    1. Schema 标签检测（确定性规则）
    2. Meta / OG 标签检测（确定性规则）
    3. 内容结构分析（确定性规则）
    4. 权威引用密度（确定性规则）
    5. 综合评分 = schema*0.3 + content*0.3 + meta*0.2 + citation*0.2
    6. LLM 生成优先级优化建议（降级为规则建议）
    """
    try:
        log_event(
            logger,
            logging.INFO,
            "task.analyze_diagnostic.started",
            task_id=self.request.id,
            report_id=report_id,
            retries=self.request.retries,
        )
        _run(_run_analysis(report_id))
        log_event(
            logger,
            logging.INFO,
            "task.analyze_diagnostic.completed",
            task_id=self.request.id,
            report_id=report_id,
        )
    except Exception as exc:
        logger.exception("analyze_page failed: %s", report_id)
        log_event(
            logger,
            logging.ERROR,
            "task.analyze_diagnostic.failed",
            task_id=self.request.id,
            report_id=report_id,
            retries=self.request.retries,
            error=str(exc)[:500],
        )
        async def _mark_failed():
            from app.core.database import async_session
            from app.models.diagnostic import DiagnosticReport, DiagnosticStatus
            from sqlalchemy import update
            async with async_session() as db:
                await db.execute(
                    update(DiagnosticReport)
                    .where(DiagnosticReport.id == uuid.UUID(report_id))
                    .values(**_normalize_update_values({
                        "status": DiagnosticStatus.FAILED,
                        "error_message": str(exc)[:500],
                    }))
                )
                await db.commit()
        try:
            _run(_mark_failed())
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=30)
