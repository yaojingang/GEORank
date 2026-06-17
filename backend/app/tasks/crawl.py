"""
爬虫任务 — 使用 Playwright 爬取目标网站
在独立的 crawler 容器中执行
"""
import uuid
import logging
import enum
import re

from celery import shared_task
from app.core.logging_utils import log_event
from app.services.company_ingest import (
    build_candidate_links,
    fallback_select_company_pages,
    normalize_company_url,
)
from app.tasks.runtime import run_async as _run

logger = logging.getLogger("georank.crawl")


def _normalize_update_values(values: dict) -> dict:
    """Convert Enum members to their database labels for Core updates."""
    normalized = {}
    for key, value in values.items():
        normalized[key] = value.value if isinstance(value, enum.Enum) else value
    return normalized


async def _update_company(company_id: str, **kwargs):
    from app.core.database import async_session
    from app.models.company import Company
    from sqlalchemy import update
    async with async_session() as db:
        await db.execute(
            update(Company)
            .where(Company.id == uuid.UUID(company_id))
            .values(**_normalize_update_values(kwargs))
        )
        await db.commit()


async def _update_report(report_id: str, **kwargs):
    from app.core.database import async_session
    from app.models.diagnostic import DiagnosticReport
    from sqlalchemy import update
    async with async_session() as db:
        await db.execute(
            update(DiagnosticReport)
            .where(DiagnosticReport.id == uuid.UUID(report_id))
            .values(**_normalize_update_values(kwargs))
        )
        await db.commit()


def _crawl_page(url: str, timeout_ms: int = 30000) -> dict:
    """
    使用 Playwright 爬取单个页面，返回 {html, text, title, links}
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = browser.new_page(
                user_agent="Mozilla/5.0 (compatible; GEOrankBot/1.0; +https://georank.com/bot)"
            )
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # 等待主要内容渲染
            page.wait_for_timeout(2000)

            html = page.content()
            title = page.title()

            # 提取纯文本
            text = page.evaluate("() => document.body.innerText || ''")

            # 提取所有一级导航候选链接
            links = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .map(a => ({
                        url: a.href,
                        title: (a.textContent || a.getAttribute('aria-label') || a.getAttribute('title') || '').trim()
                    }))
                    .filter(item => item.url && item.url.startsWith('http'))
                    .slice(0, 80);
            }""")

            return {"html": html, "text": text[:50000], "title": title, "links": links}
        finally:
            browser.close()


def _slugify_page_key(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:40] or "page"


async def _plan_company_pages(base_url: str, homepage_title: str, links: list[dict]) -> tuple[list[dict], list[dict]]:
    candidate_links = build_candidate_links(base_url, links, limit=12)
    try:
        from app.services.ai_client import ai_client

        selected_pages = await ai_client.select_company_pages(base_url, homepage_title, candidate_links)
    except Exception:
        selected_pages = fallback_select_company_pages(base_url, homepage_title, candidate_links, limit=3)

    normalized_base = normalize_company_url(base_url)
    if not any(page.get("url") == normalized_base for page in selected_pages):
        selected_pages.insert(
            0,
            {
                "url": normalized_base,
                "title": homepage_title or "主页",
                "role": "homepage",
                "reason": "主页通常包含公司定位、产品摘要与核心导航，是企业知识库的主入口。",
            },
        )
    return candidate_links, selected_pages[:3]


@shared_task(name="app.tasks.crawl.crawl_company_website", bind=True, max_retries=3)
def crawl_company_website(self, company_id: str, url: str):
    """
    爬取公司官网:
    1. Playwright 加载页面
    2. 尝试发现并爬取「关于我们」页面
    3. 将原始 HTML 上传到 MinIO（降级到内存缓存）
    4. 更新 Company.pipeline_status → 'cleaning'
    5. 链式触发: clean_company_data
    """
    from app.models.company import PipelineStatus

    try:
        log_event(
            logger,
            logging.INFO,
            "task.crawl_company.started",
            task_id=self.request.id,
            company_id=company_id,
            url=url,
            retries=self.request.retries,
        )
        _run(_update_company(company_id, pipeline_status=PipelineStatus.CRAWLING))

        normalized_url = normalize_company_url(url)

        # 爬取主页
        result = _crawl_page(normalized_url)
        html = result["html"]
        title = result["title"]
        links = result["links"]
        candidate_links, selected_pages = _run(_plan_company_pages(normalized_url, title, links))

        # 上传到 MinIO
        from app.services.storage import storage
        raw_key = f"companies/{company_id}/raw.html"
        storage.put(raw_key, html.encode("utf-8", errors="replace"))
        crawl_pages = []
        about_key = None

        for index, page in enumerate(selected_pages):
            page_url = page.get("url") or normalized_url
            page_title = page.get("title") or title or "主页"
            page_role = page.get("role") or ("homepage" if index == 0 else "supporting")
            page_reason = page.get("reason") or "该页面被选入企业知识库分析流程。"
            page_key = raw_key if page_url == normalized_url else f"companies/{company_id}/{_slugify_page_key(page_role or page_title)}-{index + 1}.html"

            page_html = html
            status = "captured"
            if page_url != normalized_url:
                try:
                    page_result = _crawl_page(page_url)
                    page_html = page_result["html"]
                    if not page_title or page_title == "主页":
                        page_title = page_result["title"] or page_title
                except Exception as exc:
                    status = "failed"
                    page_reason = f"{page_reason} 页面抓取失败：{str(exc)[:120]}"
                    page_html = ""

            if page_html:
                storage.put(page_key, page_html.encode("utf-8", errors="replace"))
                if page_role in {"about", "team"} and about_key is None and page_url != normalized_url:
                    about_key = page_key

            crawl_pages.append(
                {
                    "url": page_url,
                    "title": page_title,
                    "role": page_role,
                    "reason": page_reason,
                    "key": page_key if page_html else None,
                    "status": status,
                }
            )

        _run(
            _update_company(
                company_id,
                pipeline_status=PipelineStatus.CRAWLING,
                crawl_candidates=candidate_links,
                crawl_pages=crawl_pages,
            )
        )

        # 更新状态，进入清洗阶段
        _run(_update_company(
            company_id,
            pipeline_status=PipelineStatus.CLEANING,
            raw_html_key=raw_key,
            about_html_key=about_key,
            crawl_candidates=candidate_links,
            crawl_pages=crawl_pages,
        ))

        # 链式触发清洗任务
        from app.core.celery_app import celery_app
        celery_app.send_task("app.tasks.process.clean_company_data", args=[company_id])
        log_event(
            logger,
            logging.INFO,
            "task.crawl_company.completed",
            task_id=self.request.id,
            company_id=company_id,
            url=normalized_url,
            selected_pages=len(crawl_pages),
            about_page_found=bool(about_key),
        )

    except Exception as exc:
        logger.exception("crawl_company_website failed: %s", company_id)
        log_event(
            logger,
            logging.ERROR,
            "task.crawl_company.failed",
            task_id=self.request.id,
            company_id=company_id,
            url=url,
            retries=self.request.retries,
            error=str(exc)[:500],
        )
        try:
            _run(_update_company(
                company_id,
                pipeline_status=PipelineStatus.FAILED,
                pipeline_error=str(exc)[:500],
            ))
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="app.tasks.crawl.crawl_diagnostic_page", bind=True, max_retries=3)
def crawl_diagnostic_page(self, report_id: str, url: str):
    """
    诊断用爬虫 — 爬取单个页面:
    1. 获取完整 HTML 源码
    2. 上传到 MinIO
    3. 更新 DiagnosticReport.status → 'analyzing'
    4. 链式触发: analyze_page
    """
    from app.models.diagnostic import DiagnosticStatus

    try:
        log_event(
            logger,
            logging.INFO,
            "task.crawl_diagnostic.started",
            task_id=self.request.id,
            report_id=report_id,
            url=url,
            retries=self.request.retries,
        )
        _run(_update_report(report_id, status=DiagnosticStatus.CRAWLING))

        result = _crawl_page(url)
        html = result["html"]

        # 上传到 MinIO
        from app.services.storage import storage
        raw_key = f"diagnostics/{report_id}/raw.html"
        storage.put(raw_key, html.encode("utf-8", errors="replace"))

        _run(_update_report(
            report_id,
            status=DiagnosticStatus.ANALYZING,
            raw_html_key=raw_key,
        ))

        # 链式触发分析任务
        from app.core.celery_app import celery_app
        celery_app.send_task("app.tasks.diagnose.analyze_page", args=[report_id])
        log_event(
            logger,
            logging.INFO,
            "task.crawl_diagnostic.completed",
            task_id=self.request.id,
            report_id=report_id,
            url=url,
        )

    except Exception as exc:
        logger.exception("crawl_diagnostic_page failed: %s", report_id)
        log_event(
            logger,
            logging.ERROR,
            "task.crawl_diagnostic.failed",
            task_id=self.request.id,
            report_id=report_id,
            url=url,
            retries=self.request.retries,
            error=str(exc)[:500],
        )
        try:
            _run(_update_report(
                report_id,
                status=DiagnosticStatus.FAILED,
                error_message=str(exc)[:500],
            ))
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)
