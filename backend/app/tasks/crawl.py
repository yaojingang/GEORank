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
    validate_public_crawl_url,
)
from app.tasks.runtime import run_async as _run
from app.tasks.process import NextStageDispatchError, StageClaimBusy

logger = logging.getLogger("georank.crawl")


def _is_final_attempt(task) -> bool:
    max_retries = getattr(task, "max_retries", None)
    return max_retries is not None and task.request.retries >= max_retries


async def _company_reservation_state(
    company_id: str,
    reservation_id: str | uuid.UUID | None = None,
) -> str:
    from app.core.database import async_session
    from app.models.company import Company
    from app.services.ai_usage import async_reservation_is_pending
    from sqlalchemy import select

    async with async_session() as db:
        company_state = (
            await db.execute(
                select(Company.ai_reservation_id, Company.pipeline_status).where(
                    Company.id == uuid.UUID(company_id)
                )
            )
        ).one_or_none()
        if company_state is None:
            return "missing"
        current_reservation_id, pipeline_status = company_state
        if current_reservation_id is None:
            return "missing"
        if reservation_id is not None:
            try:
                expected_reservation_id = uuid.UUID(str(reservation_id))
            except (TypeError, ValueError):
                return "stale"
            if current_reservation_id != expected_reservation_id:
                return "stale"
        if await async_reservation_is_pending(db, current_reservation_id):
            return "active"
        from app.models.company import PipelineStatus
        if pipeline_status in {PipelineStatus.COMPLETED, PipelineStatus.FAILED}:
            return "finished"
        return "expired"


async def _diagnostic_reservation_state(
    report_id: str,
    reservation_id: str | uuid.UUID | None = None,
) -> str:
    from app.core.database import async_session
    from app.models.diagnostic import DiagnosticReport, DiagnosticStatus
    from app.services.ai_usage import async_reservation_is_pending
    from sqlalchemy import select

    async with async_session() as db:
        report_state = (
            await db.execute(
                select(
                    DiagnosticReport.ai_reservation_id,
                    DiagnosticReport.status,
                ).where(
                    DiagnosticReport.id == uuid.UUID(report_id)
                )
            )
        ).one_or_none()
        if report_state is None:
            return "missing"
        current_reservation_id, report_status = report_state
        if report_status in {DiagnosticStatus.COMPLETED, DiagnosticStatus.FAILED}:
            return "finished"
        if current_reservation_id is None:
            return "missing"
        if reservation_id is not None:
            try:
                expected_reservation_id = uuid.UUID(str(reservation_id))
            except (TypeError, ValueError):
                return "stale"
            if current_reservation_id != expected_reservation_id:
                return "stale"
        if await async_reservation_is_pending(db, current_reservation_id):
            return "active"
        return "expired"


def _normalize_update_values(values: dict) -> dict:
    """Convert Enum members to their database labels for Core updates."""
    normalized = {}
    for key, value in values.items():
        normalized[key] = value.value if isinstance(value, enum.Enum) else value
    return normalized


async def _update_company(
    company_id: str,
    *,
    reservation_id: str | uuid.UUID | None = None,
    **kwargs,
) -> bool:
    from app.core.database import async_session
    from app.models.company import Company
    from sqlalchemy import update
    async with async_session() as db:
        query = update(Company).where(Company.id == uuid.UUID(company_id))
        if reservation_id is not None:
            try:
                expected_reservation_id = uuid.UUID(str(reservation_id))
            except (TypeError, ValueError):
                return False
            query = query.where(Company.ai_reservation_id == expected_reservation_id)
        result = await db.execute(
            query.values(**_normalize_update_values(kwargs)).returning(Company.id)
        )
        await db.commit()
        return result.scalar_one_or_none() is not None


async def _update_report(
    report_id: str,
    *,
    reservation_id: str | uuid.UUID | None = None,
    **kwargs,
) -> bool:
    from app.core.database import async_session
    from app.models.diagnostic import DiagnosticReport
    from sqlalchemy import update
    async with async_session() as db:
        query = update(DiagnosticReport).where(DiagnosticReport.id == uuid.UUID(report_id))
        if reservation_id is not None:
            try:
                expected_reservation_id = uuid.UUID(str(reservation_id))
            except (TypeError, ValueError):
                return False
            query = query.where(DiagnosticReport.ai_reservation_id == expected_reservation_id)
        result = await db.execute(
            query.values(**_normalize_update_values(kwargs)).returning(DiagnosticReport.id)
        )
        await db.commit()
        return result.scalar_one_or_none() is not None


async def _resume_diagnostic_analysis(
    report_id: str,
    reservation_id: str | uuid.UUID | None,
) -> bool:
    from app.core.database import async_session
    from app.core.celery_app import celery_app
    from app.models.diagnostic import DiagnosticReport, DiagnosticStatus
    from sqlalchemy import select

    expected_reservation_id = (
        uuid.UUID(str(reservation_id)) if reservation_id is not None else None
    )
    async with async_session() as db:
        report = await db.scalar(
            select(DiagnosticReport).where(DiagnosticReport.id == uuid.UUID(report_id))
        )
        if (
            not report
            or report.status != DiagnosticStatus.ANALYZING
            or (
                expected_reservation_id is not None
                and report.ai_reservation_id != expected_reservation_id
            )
        ):
            return False
    try:
        celery_app.send_task(
            "app.tasks.diagnose.analyze_page",
            args=[report_id, str(reservation_id) if reservation_id is not None else None],
        )
    except Exception as exc:
        raise NextStageDispatchError(str(exc)) from exc
    return True


def _retry_diagnostic_dispatch_or_finalize(
    task,
    *,
    report_id: str,
    reservation_id: str | uuid.UUID | None,
    error: Exception,
) -> None:
    from celery.exceptions import MaxRetriesExceededError

    try:
        task.retry(exc=error, countdown=60, max_retries=20)
    except MaxRetriesExceededError:
        from app.models.diagnostic import DiagnosticStatus
        from app.tasks.diagnose import _finalize_diagnostic_failure

        _run(_update_report(
            report_id,
            reservation_id=reservation_id,
            status=DiagnosticStatus.FAILED,
            error_message=f"诊断分析任务连续派发失败：{error}",
        ))
        _run(_finalize_diagnostic_failure(
            report_id,
            "diagnostic_dispatch_failed",
            reservation_id,
        ))


def _crawl_page(url: str, timeout_ms: int = 30000) -> dict:
    """
    使用 Playwright 爬取单个页面，返回 {html, text, title, links}
    """
    from playwright.sync_api import sync_playwright

    validated_url = validate_public_crawl_url(url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            context = browser.new_context(
                user_agent="Mozilla/5.0 (compatible; GEOrankBot/1.0; +https://georank.com/bot)",
                service_workers="block",
            )

            def enforce_public_request(route):
                request_url = route.request.url
                from urllib.parse import urlparse

                parsed = urlparse(request_url)
                if parsed.scheme not in {"http", "https"}:
                    route.abort("blockedbyclient")
                    return
                try:
                    # 每次网络请求重新解析，避免复用已过期的 DNS 判断。
                    validate_public_crawl_url(request_url)
                except ValueError:
                    route.abort("blockedbyclient")
                    return
                route.continue_()

            context.route("**/*", enforce_public_request)
            context.route_web_socket("**/*", lambda web_socket: web_socket.close())
            page = context.new_page()
            page.goto(validated_url, wait_until="domcontentloaded", timeout=timeout_ms)
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

            return {
                "html": html,
                "text": text[:50000],
                "title": title,
                "links": links,
                "url": validate_public_crawl_url(page.url),
            }
        finally:
            browser.close()


def _slugify_page_key(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:40] or "page"


def persist_crawl_html(storage_service, key: str, html: str) -> None:
    """Persist crawl HTML and prove that another process can read it back."""
    payload = html.encode("utf-8", errors="replace")
    if not storage_service.put(key, payload):
        raise RuntimeError(f"对象存储写入失败：{key}")
    stored = storage_service.get(key)
    if stored != payload:
        raise RuntimeError(f"对象存储回读校验失败：{key}")


async def _plan_company_pages(
    base_url: str,
    homepage_title: str,
    links: list[dict],
) -> tuple[list[dict], list[dict], bool]:
    candidate_links = build_candidate_links(base_url, links, limit=12)
    provider_succeeded = False
    try:
        from app.services.ai_client import ai_client

        selected_pages = await ai_client.select_company_pages(base_url, homepage_title, candidate_links)
        provider_succeeded = True
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
    return candidate_links, selected_pages[:3], provider_succeeded


async def _complete_company_page_plan_stage(
    reservation_id: str | uuid.UUID | None,
    stage: str,
    claim_id: str,
    *,
    base_url: str,
    homepage_title: str,
    candidate_links: list[dict],
    selected_pages: list[dict],
    provider_succeeded: bool,
) -> bool:
    import json
    from app.core.database import async_session
    from app.services.ai_usage import (
        complete_async_reservation_stage,
        estimate_token_count,
    )

    async with async_session() as db:
        completed = await complete_async_reservation_stage(
            db,
            reservation_id=reservation_id,
            stage=stage,
            claim_id=claim_id,
            actual_tokens=(
                estimate_token_count(
                    base_url,
                    homepage_title,
                    json.dumps(candidate_links, ensure_ascii=False),
                    json.dumps(selected_pages, ensure_ascii=False),
                )
                if provider_succeeded
                else 0
            ),
        )
        await db.commit()
        return completed


@shared_task(name="app.tasks.crawl.crawl_company_website", bind=True, max_retries=3)
def crawl_company_website(
    self,
    company_id: str,
    url: str,
    reservation_id: str | None = None,
):
    """
    爬取公司官网:
    1. Playwright 加载页面
    2. 尝试发现并爬取「关于我们」页面
    3. 将原始 HTML 持久化到对象存储并完成回读校验
    4. 更新 Company.pipeline_status → 'cleaning'
    5. 链式触发: clean_company_data
    """
    from app.models.company import PipelineStatus

    provider_claim_id = f"{self.request.id}:{self.request.retries}"
    provider_stage = f"company_page_plan:{provider_claim_id}"
    try:
        reservation_state = _run(_company_reservation_state(company_id, reservation_id))
        if reservation_state != "active":
            if reservation_state in {"missing", "stale", "finished"}:
                return
            from app.tasks.process import _mark_company_failed

            _run(
                _mark_company_failed(
                    company_id,
                    "AI 额度预占已失效，请重新发起分析。",
                    finalize_quota=True,
                    reservation_id=reservation_id,
                )
            )
            return
        from app.tasks.process import _claim_company_stage
        if not _run(
            _claim_company_stage(
                company_id,
                reservation_id=reservation_id,
                expected_status=(PipelineStatus.PENDING, PipelineStatus.CRAWLING),
                stage="crawl",
                task_id=self.request.id,
            )
        ):
            from app.tasks.process import _resume_company_pipeline
            _run(_resume_company_pipeline(company_id, reservation_id, "crawl"))
            return
        log_event(
            logger,
            logging.INFO,
            "task.crawl_company.started",
            task_id=self.request.id,
            company_id=company_id,
            url=url,
            retries=self.request.retries,
        )
        if not _run(
            _update_company(
                company_id,
                reservation_id=reservation_id,
                pipeline_status=PipelineStatus.CRAWLING,
            )
        ):
            return

        normalized_url = normalize_company_url(url)

        # 爬取主页
        result = _crawl_page(normalized_url)
        html = result["html"]
        title = result["title"]
        links = result["links"]
        homepage_url = result.get("url") or normalized_url
        from app.tasks.process import _claim_company_provider_stage
        if not _run(_claim_company_provider_stage(
            reservation_id,
            provider_stage,
            provider_claim_id,
        )):
            return
        candidate_links, selected_pages, provider_succeeded = _run(
            _plan_company_pages(homepage_url, title, links)
        )
        if not _run(_complete_company_page_plan_stage(
            reservation_id,
            provider_stage,
            provider_claim_id,
            base_url=homepage_url,
            homepage_title=title,
            candidate_links=candidate_links,
            selected_pages=selected_pages,
            provider_succeeded=provider_succeeded,
        )):
            raise RuntimeError("公司页面规划计量阶段完成失败")
        # 上传到 MinIO
        from app.services.storage import storage
        raw_key = f"companies/{company_id}/raw.html"
        crawl_pages = []
        about_key = None

        for index, page in enumerate(selected_pages):
            page_url = page.get("url") or homepage_url
            page_title = page.get("title") or title or "主页"
            page_role = page.get("role") or ("homepage" if index == 0 else "supporting")
            page_reason = page.get("reason") or "该页面被选入企业知识库分析流程。"
            page_key = raw_key if page_url == homepage_url else f"companies/{company_id}/{_slugify_page_key(page_role or page_title)}-{index + 1}.html"

            page_html = html
            status = "captured"
            if page_url != homepage_url:
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
                persist_crawl_html(storage, page_key, page_html)
                if page_role in {"about", "team"} and about_key is None and page_url != homepage_url:
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
                reservation_id=reservation_id,
                pipeline_status=PipelineStatus.CRAWLING,
                crawl_candidates=candidate_links,
                crawl_pages=crawl_pages,
            )
        )

        # 更新状态，进入清洗阶段
        if not _run(
            _update_company(
                company_id,
                reservation_id=reservation_id,
                pipeline_status=PipelineStatus.CLEANING,
                pipeline_error=None,
                raw_html_key=raw_key,
                about_html_key=about_key,
                crawl_candidates=candidate_links,
                crawl_pages=crawl_pages,
            )
        ):
            return

        # 链式触发清洗任务
        from app.core.celery_app import celery_app
        try:
            celery_app.send_task(
                "app.tasks.process.clean_company_data",
                args=[company_id, reservation_id],
            )
        except Exception as exc:
            raise NextStageDispatchError(str(exc)) from exc
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

    except NextStageDispatchError as exc:
        from app.tasks.process import _retry_dispatch_or_finalize
        _retry_dispatch_or_finalize(
            self,
            company_id=company_id,
            reservation_id=reservation_id,
            error=exc,
        )
    except StageClaimBusy as exc:
        raise self.retry(exc=exc, countdown=60, max_retries=20)
    except Exception as exc:
        try:
            from app.tasks.process import _release_company_provider_stage
            _run(_release_company_provider_stage(
                reservation_id,
                provider_stage,
                provider_claim_id,
            ))
        except Exception:
            pass
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
            if _is_final_attempt(self):
                from app.tasks.process import _mark_company_failed

                _run(_mark_company_failed(
                    company_id,
                    exc,
                    finalize_quota=True,
                    reservation_id=reservation_id,
                ))
            else:
                _run(
                    _update_company(
                        company_id,
                        reservation_id=reservation_id,
                        pipeline_status=PipelineStatus.PENDING,
                        pipeline_error=f"任务将自动重试：{str(exc)[:450]}",
                    )
                )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="app.tasks.crawl.crawl_diagnostic_page", bind=True, max_retries=3)
def crawl_diagnostic_page(
    self,
    report_id: str,
    url: str,
    reservation_id: str | None = None,
):
    """
    诊断用爬虫 — 爬取单个页面:
    1. 获取完整 HTML 源码
    2. 上传到 MinIO
    3. 更新 DiagnosticReport.status → 'analyzing'
    4. 链式触发: analyze_page
    """
    from app.models.diagnostic import DiagnosticStatus

    try:
        reservation_state = _run(_diagnostic_reservation_state(report_id, reservation_id))
        if reservation_state in {"missing", "stale", "finished"}:
            return
        if reservation_state != "active":
            _run(
                _update_report(
                    report_id,
                    reservation_id=reservation_id,
                    status=DiagnosticStatus.FAILED,
                    error_message="AI 额度预占已失效，请重新发起诊断。",
                )
            )
            from app.tasks.diagnose import _finalize_diagnostic_failure

            _run(_finalize_diagnostic_failure(
                report_id,
                "diagnostic_reservation_inactive",
                reservation_id,
            ))
            return
        if _run(_resume_diagnostic_analysis(report_id, reservation_id)):
            return
        log_event(
            logger,
            logging.INFO,
            "task.crawl_diagnostic.started",
            task_id=self.request.id,
            report_id=report_id,
            url=url,
            retries=self.request.retries,
        )
        _run(_update_report(
            report_id,
            reservation_id=reservation_id,
            status=DiagnosticStatus.CRAWLING,
        ))

        result = _crawl_page(url)
        html = result["html"]

        # 上传到 MinIO
        from app.services.storage import storage
        raw_key = f"diagnostics/{report_id}/raw.html"
        persist_crawl_html(storage, raw_key, html)

        _run(_update_report(
            report_id,
            reservation_id=reservation_id,
            status=DiagnosticStatus.ANALYZING,
            raw_html_key=raw_key,
        ))

        # 链式触发分析任务
        from app.core.celery_app import celery_app
        try:
            celery_app.send_task(
                "app.tasks.diagnose.analyze_page",
                args=[report_id, reservation_id],
            )
        except Exception as exc:
            raise NextStageDispatchError(str(exc)) from exc
        log_event(
            logger,
            logging.INFO,
            "task.crawl_diagnostic.completed",
            task_id=self.request.id,
            report_id=report_id,
            url=url,
        )

    except NextStageDispatchError as exc:
        _retry_diagnostic_dispatch_or_finalize(
            self,
            report_id=report_id,
            reservation_id=reservation_id,
            error=exc,
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
                reservation_id=reservation_id,
                status=(
                    DiagnosticStatus.FAILED
                    if _is_final_attempt(self)
                    else DiagnosticStatus.PENDING
                ),
                error_message=(
                    str(exc)[:500]
                    if _is_final_attempt(self)
                    else f"任务将自动重试：{str(exc)[:450]}"
                ),
            ))
        except Exception:
            pass
        if _is_final_attempt(self):
            try:
                from app.tasks.diagnose import _finalize_diagnostic_failure

                _run(_finalize_diagnostic_failure(
                    report_id,
                    "diagnostic_crawl_failed",
                    reservation_id,
                ))
            except Exception:
                pass
        raise self.retry(exc=exc, countdown=60)
