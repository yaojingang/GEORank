"""
GEO 诊断 API — 提交 URL → 爬取 → 分析 → 报告
"""
import uuid

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.core.deps import DbSession, CurrentUser, OptionalUser
from app.models.diagnostic import DiagnosticReport, DiagnosticStatus
from app.services.company_ingest import normalize_company_url
from app.services.ai_usage import release_ai_access, resolve_async_ai_access
from app.schemas.diagnostic import (
    DiagnoseRequest, DiagnoseResponse, DiagnosticReportResponse, DiagnosticHistoryItem,
)

router = APIRouter()
_QUEUE_DISPATCH_ERROR = "诊断任务创建失败，请稍后重试。"


@router.post("/", response_model=DiagnoseResponse)
async def start_diagnosis(data: DiagnoseRequest, request: Request, db: DbSession, current_user: OptionalUser):
    """
    开始 GEO 诊断：
    1. 创建 DiagnosticReport 记录 (pending)
    2. 触发 Celery diagnose 任务
    3. 返回 report_id，前端轮询状态
    """
    try:
        normalized_url = normalize_company_url(data.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    company_id = uuid.UUID(data.company_id) if data.company_id else None
    access = await resolve_async_ai_access(
        db=db,
        current_user=current_user,
        module="diagnostics",
        prompt_text=f"{normalized_url}\n{data.company_id or ''}",
        request=request,
    )

    report = DiagnosticReport(
        url=normalized_url,
        company_id=company_id,
        status=DiagnosticStatus.PENDING,
        user_id=current_user.id if current_user else None,
        ai_reservation_id=access.reservation_id,
    )
    db.add(report)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        await release_ai_access(db, access, error_code="diagnostic_record_create_failed")
        await db.commit()
        raise
    await db.refresh(report)

    # 触发 Celery 任务：先爬取页面，再进入 analyze_page
    queue_failed = False
    try:
        from app.core.celery_app import celery_app
        celery_app.send_task(
            "app.tasks.crawl.crawl_diagnostic_page",
            args=[str(report.id), normalized_url, str(access.reservation_id)],
        )
    except Exception:
        queue_failed = True
        report.status = DiagnosticStatus.FAILED
        report.error_message = _QUEUE_DISPATCH_ERROR
        await release_ai_access(db, access, error_code="queue_dispatch_failed")
        await db.commit()

    return DiagnoseResponse(
        report_id=str(report.id),
        status="failed" if queue_failed else "pending",
    )


@router.get("/history")
async def diagnosis_history(db: DbSession, current_user: CurrentUser, page: int = 1, size: int = 20):
    """当前用户的诊断历史"""
    result = await db.execute(
        select(DiagnosticReport)
        .where(DiagnosticReport.user_id == current_user.id)
        .order_by(DiagnosticReport.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    reports = result.scalars().all()
    return [
        {
            "report_id": str(r.id),
            "url": r.url,
            "status": r.status.value,
            "overall_score": r.overall_score,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]


@router.get("/{report_id}")
async def get_report(report_id: str, db: DbSession, current_user: OptionalUser):
    """获取诊断报告（前端轮询直到 completed）"""
    result = await db.execute(
        select(DiagnosticReport).where(DiagnosticReport.id == uuid.UUID(report_id))
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.user_id is not None and (not current_user or report.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="无权访问此报告")

    return {
        "report_id": str(report.id),
        "url": report.url,
        "company_id": str(report.company_id) if report.company_id else None,
        "status": report.status.value,
        "overall_score": report.overall_score,
        "schema_analysis": report.schema_analysis,
        "content_analysis": report.content_analysis,
        "meta_analysis": report.meta_analysis,
        "citation_analysis": report.citation_analysis,
        "recommendations": report.recommendations,
        "error_message": report.error_message,
        "created_at": report.created_at.isoformat(),
    }
