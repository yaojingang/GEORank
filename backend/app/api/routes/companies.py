"""
公司 API — 提交 / 列表 / 详情 / 投票 / 进度 / 相似推荐
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError

from app.core.deps import DbSession, CurrentUser, OptionalUser
from app.models.company import Company, PublishStatus, PipelineStatus
from app.models.user import UserRole
from app.models.vote import CompanyVote
from app.services.company_lookup import get_company_by_identifier
from app.services.company_profile import (
    company_profile_missing_fields,
    company_profile_needs_hydration,
)
from app.services.company_ingest import normalize_company_url
from app.services.ai_usage import (
    release_ai_access,
    resolve_async_ai_access,
    settle_token_reservation,
)
from app.schemas.company import (
    SubmitCompanyRequest, SubmitCompanyResponse, CompanyBrief, CompanyDetail,
    PaginatedCompanies, PipelineStatusResponse, VoteResponse, SimilarCompanyItem,
)

router = APIRouter()
_QUEUE_DISPATCH_ERROR = "官网分析任务创建失败，请稍后重试。"
_PENDING_RECOVERY_AFTER = timedelta(minutes=5)


def _can_view_company_draft(company: Company, current_user) -> bool:
    if company.publish_status == PublishStatus.PUBLISHED:
        return True
    if current_user is None:
        return False
    return bool(
        current_user.role == UserRole.ADMIN
        or company.submitted_by == current_user.id
    )


def _company_pipeline_needs_restart(company: Company) -> bool:
    if company.pipeline_status == PipelineStatus.FAILED:
        return True
    if company.pipeline_status != PipelineStatus.PENDING:
        return False
    if company.ai_reservation_id is None:
        return True
    last_progress_at = company.updated_at or company.created_at
    if last_progress_at is None:
        return True
    return last_progress_at <= datetime.utcnow() - _PENDING_RECOVERY_AFTER

@router.post("/submit", response_model=SubmitCompanyResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_company(data: SubmitCompanyRequest, request: Request, db: DbSession, current_user: CurrentUser):
    """
    用户提交公司 URL → 创建记录 → 触发 AI 入库流水线
    返回 company_id，前端可轮询 pipeline-status
    """
    try:
        normalized_url = normalize_company_url(data.url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # 检查是否已存在
    result = await db.execute(
        select(Company).where(Company.url == normalized_url).with_for_update()
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.publish_status == PublishStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"该 URL 已存在，company_id: {existing.id}",
            )

        if (
            existing.submitted_by
            and existing.submitted_by != current_user.id
            and current_user.role != UserRole.ADMIN
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="该公司分析由其他账号创建。",
            )

        should_restart = _company_pipeline_needs_restart(existing)
        if should_restart:
            previous_pipeline_status = existing.pipeline_status
            previous_reservation_id = existing.ai_reservation_id
            if previous_reservation_id:
                await settle_token_reservation(
                    db,
                    reservation_id=previous_reservation_id,
                    actual_tokens=0,
                    succeeded=False,
                )
            access = await resolve_async_ai_access(
                db=db,
                current_user=current_user,
                module="companies",
                prompt_text=normalized_url,
                request=request,
            )
            try:
                restart_result = await db.execute(
                    update(Company)
                    .where(
                        Company.id == existing.id,
                        Company.pipeline_status == previous_pipeline_status,
                        (
                            Company.ai_reservation_id.is_(None)
                            if previous_reservation_id is None
                            else Company.ai_reservation_id == previous_reservation_id
                        ),
                    )
                    .values(
                        pipeline_status=PipelineStatus.PENDING,
                        pipeline_error=None,
                        crawl_candidates=[],
                        crawl_pages=[],
                        submitted_by=current_user.id,
                        ai_reservation_id=access.reservation_id,
                    )
                    .returning(Company.id)
                )
            except Exception:
                await db.rollback()
                await release_ai_access(
                    db,
                    access,
                    error_code="company_restart_update_failed",
                )
                await db.commit()
                raise
            if restart_result.scalar_one_or_none() is None:
                await release_ai_access(
                    db,
                    access,
                    error_code="company_pipeline_already_restarted",
                )
                await db.commit()
                await db.refresh(existing)
                return SubmitCompanyResponse(
                    company_id=str(existing.id),
                    status=existing.pipeline_status.value,
                    message="已存在同域名分析任务，正在恢复分析进度。",
                    normalized_url=normalized_url,
                    publish_status=existing.publish_status.value,
                    resumed=True,
                )
            try:
                await db.commit()
            except Exception:
                await db.rollback()
                await release_ai_access(
                    db,
                    access,
                    error_code="company_restart_commit_failed",
                )
                await db.commit()
                raise

            queue_failed = False
            try:
                from app.core.celery_app import celery_app

                celery_app.send_task(
                    "app.tasks.crawl.crawl_company_website",
                    args=[str(existing.id), normalized_url, str(access.reservation_id)],
                )
            except Exception:
                queue_failed = True
                await db.execute(
                    update(Company)
                    .where(
                        Company.id == existing.id,
                        Company.ai_reservation_id == access.reservation_id,
                        Company.pipeline_status == PipelineStatus.PENDING,
                    )
                    .values(
                        pipeline_status=PipelineStatus.FAILED,
                        pipeline_error=_QUEUE_DISPATCH_ERROR,
                    )
                )
                await release_ai_access(db, access, error_code="queue_dispatch_failed")
                await db.commit()

            return SubmitCompanyResponse(
                company_id=str(existing.id),
                status="failed" if queue_failed else "pending",
                message=_QUEUE_DISPATCH_ERROR if queue_failed else "已重新加入处理队列",
                normalized_url=normalized_url,
                publish_status=existing.publish_status.value,
                resumed=True,
            )

        if not existing.submitted_by:
            existing.submitted_by = current_user.id
            await db.commit()

        return SubmitCompanyResponse(
            company_id=str(existing.id),
            status=existing.pipeline_status.value,
            message="已存在同域名分析任务，正在恢复分析进度。",
            normalized_url=normalized_url,
            publish_status=existing.publish_status.value,
            resumed=True,
        )

    access = await resolve_async_ai_access(
        db=db,
        current_user=current_user,
        module="companies",
        prompt_text=normalized_url,
        request=request,
    )

    company = Company(
        name=normalized_url.split("//")[-1].split("/")[0],  # 临时从 URL 提取域名作为名称
        url=normalized_url,
        pipeline_status=PipelineStatus.PENDING,
        publish_status=PublishStatus.DRAFT,
        submitted_by=current_user.id,
        ai_reservation_id=access.reservation_id,
    )
    db.add(company)
    try:
        await db.commit()
    except IntegrityError:
        # 两个请求可能同时通过首次查询。URL 唯一约束负责最终仲裁。
        await db.rollback()
        await release_ai_access(db, access, error_code="duplicate_company_race")
        await db.commit()
        raced_company = await db.scalar(
            select(Company).where(Company.url == normalized_url)
        )
        if raced_company is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="公司记录创建冲突，请重试。",
            )
        if raced_company.publish_status == PublishStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"该 URL 已存在，company_id: {raced_company.id}",
            )
        if not _can_view_company_draft(raced_company, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="该公司分析由其他账号创建。",
            )
        return SubmitCompanyResponse(
            company_id=str(raced_company.id),
            status=raced_company.pipeline_status.value,
            message="已存在同域名分析任务，正在恢复分析进度。",
            normalized_url=normalized_url,
            publish_status=raced_company.publish_status.value,
            resumed=True,
        )
    except Exception:
        await db.rollback()
        await release_ai_access(db, access, error_code="company_record_create_failed")
        await db.commit()
        raise
    await db.refresh(company)

    # 触发 Celery 爬取任务（如果 Celery 可用）
    queue_failed = False
    try:
        from app.core.celery_app import celery_app
        celery_app.send_task(
            "app.tasks.crawl.crawl_company_website",
            args=[str(company.id), normalized_url, str(access.reservation_id)],
        )
    except Exception:
        queue_failed = True
        await db.execute(
            update(Company)
            .where(
                Company.id == company.id,
                Company.ai_reservation_id == access.reservation_id,
                Company.pipeline_status == PipelineStatus.PENDING,
            )
            .values(
                pipeline_status=PipelineStatus.FAILED,
                pipeline_error=_QUEUE_DISPATCH_ERROR,
            )
        )
        await release_ai_access(db, access, error_code="queue_dispatch_failed")
        await db.commit()

    return SubmitCompanyResponse(
        company_id=str(company.id),
        status="failed" if queue_failed else "pending",
        message=_QUEUE_DISPATCH_ERROR if queue_failed else "已加入处理队列",
        normalized_url=normalized_url,
        publish_status=company.publish_status.value,
    )


@router.get("/", response_model=PaginatedCompanies)
async def list_companies(
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    sort: str = Query("newest", pattern="^(newest|geo_score|views|upvotes)$"),
    q: Optional[str] = None,
):
    """公司列表 — 支持分类筛选、排序、全文搜索"""
    query = select(Company).where(Company.publish_status == PublishStatus.PUBLISHED)

    if category:
        query = query.where(Company.category == category)
    if q:
        query = query.where(
            Company.name.ilike(f"%{q}%") | Company.short_description.ilike(f"%{q}%")
        )

    # 排序
    if sort == "geo_score":
        query = query.order_by(Company.geo_score.desc().nullslast())
    elif sort == "views":
        query = query.order_by(
            Company.view_count.desc(),
            Company.created_at.desc(),
            Company.id.asc(),
        )
    elif sort == "upvotes":
        query = query.order_by(Company.upvotes.desc())
    else:
        query = query.order_by(Company.created_at.desc())

    # 总数
    count_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = count_result.scalar_one()

    # 分页
    result = await db.execute(query.offset((page - 1) * size).limit(size))
    companies = result.scalars().all()

    items = []
    for c in companies:
        items.append(CompanyBrief(
            id=str(c.id),
            path_key=c.path_key,
            name=c.name,
            url=c.url,
            logo_url=c.logo_url,
            short_description=c.short_description,
            category=c.category,
            tags=c.tags if isinstance(c.tags, list) else [],
            geo_score=c.geo_score,
            is_geo_certified=c.is_geo_certified,
            tech_level=c.tech_level,
            funding_stage=c.funding_stage,
            headquarters=c.headquarters,
            pipeline_status=c.pipeline_status.value,
            publish_status=c.publish_status.value,
            upvotes=c.upvotes,
            view_count=c.view_count,
        ))

    return PaginatedCompanies(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if total > 0 else 1,
    )


@router.get("/{company_id}", response_model=CompanyDetail)
async def get_company(company_id: str, db: DbSession, current_user: OptionalUser):
    """公司详情 — 含完整知识库信息"""
    company = await get_company_by_identifier(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")
    if not _can_view_company_draft(company, current_user):
        raise HTTPException(status_code=404, detail="公司不存在")

    return CompanyDetail(
        id=str(company.id),
        path_key=company.path_key,
        name=company.name,
        url=company.url,
        logo_url=company.logo_url,
        short_description=company.short_description,
        description=company.description,
        category=company.category,
        tags=company.tags if isinstance(company.tags, list) else [],
        geo_score=company.geo_score,
        geo_details=company.geo_details,
        is_geo_certified=company.is_geo_certified,
        tech_level=company.tech_level,
        tech_stack=company.tech_stack if isinstance(company.tech_stack, list) else [],
        team_members=company.team_members if isinstance(company.team_members, list) else [],
        funding_stage=company.funding_stage,
        headquarters=company.headquarters,
        employee_count=company.employee_count,
        founded_date=str(company.founded_date) if company.founded_date else None,
        pipeline_status=company.pipeline_status.value,
        publish_status=company.publish_status.value,
        pipeline_error=company.pipeline_error,
        upvotes=company.upvotes,
        view_count=company.view_count,
    )


@router.post("/{company_id}/upvote", response_model=VoteResponse)
async def upvote_company(company_id: str, db: DbSession, current_user: CurrentUser):
    """
    投票（幂等）
    - 写入 company_votes（UNIQUE company_id+user_id）
    - 若已投票返回 HTTP 409
    - 成功则 companies.upvotes 原子递增
    """
    company = await get_company_by_identifier(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")
    if company.publish_status != PublishStatus.PUBLISHED:
        raise HTTPException(status_code=409, detail="公司尚未发布，暂不能投票")
    cid = company.id

    vote = CompanyVote(company_id=cid, user_id=current_user.id)
    db.add(vote)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已投过票")

    # 原子递增
    await db.execute(
        update(Company).where(Company.id == cid).values(upvotes=Company.upvotes + 1)
    )
    await db.commit()

    result = await db.execute(select(Company.upvotes).where(Company.id == cid))
    upvotes = result.scalar_one()
    return VoteResponse(upvotes=upvotes)


@router.get("/{company_id}/pipeline-status", response_model=PipelineStatusResponse)
async def get_pipeline_status(company_id: str, db: DbSession, current_user: OptionalUser):
    """查询入库流水线当前进度（前端轮询）"""
    company = await get_company_by_identifier(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")
    if not _can_view_company_draft(company, current_user):
        raise HTTPException(status_code=404, detail="公司不存在")

    progress_map = {
        PipelineStatus.PENDING: 0,
        PipelineStatus.CRAWLING: 20,
        PipelineStatus.CLEANING: 40,
        PipelineStatus.GRAPH_BUILDING: 65,
        PipelineStatus.VECTORIZING: 85,
        PipelineStatus.COMPLETED: 100,
        PipelineStatus.FAILED: 0,
    }

    crawl_pages = []
    for page in company.crawl_pages or []:
        crawl_pages.append(
            {
                "url": page.get("url"),
                "title": page.get("title"),
                "role": page.get("role"),
                "reason": page.get("reason"),
                "status": page.get("status"),
            }
        )

    current_activity = {
        PipelineStatus.PENDING: "已创建任务，等待进入官网解析队列。",
        PipelineStatus.CRAWLING: (
            "已解析首页一级目录，正在抓取 AI 选出的关键页面。"
            if crawl_pages
            else "正在抓取官网首页，并从一级目录里识别最值得深入的页面。"
        ),
        PipelineStatus.CLEANING: "已完成关键页面抓取，正在提取企业介绍、产品与团队信息。",
        PipelineStatus.GRAPH_BUILDING: "正在梳理实体关系并构建企业知识图谱。",
        PipelineStatus.VECTORIZING: "正在将企业知识写入语义检索索引。",
        PipelineStatus.COMPLETED: "企业知识库构建完成，等待你确认提交审核。",
        PipelineStatus.FAILED: company.pipeline_error or "本次知识库构建未成功完成。",
    }.get(company.pipeline_status)

    return PipelineStatusResponse(
        company_id=str(company.id),
        status=company.pipeline_status.value,
        progress=progress_map.get(company.pipeline_status, 0),
        error=company.pipeline_error,
        current_activity=current_activity,
        publish_status=company.publish_status.value,
        company_name=company.name,
        company_summary=company.short_description,
        selected_pages=crawl_pages,
    )


@router.post("/{company_id}/submit-review")
async def submit_company_for_review(company_id: str, db: DbSession, current_user: CurrentUser):
    """用户确认分析结果后，提交后台审核。"""
    company = await get_company_by_identifier(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")
    cid = company.id

    if (
        company.submitted_by
        and company.submitted_by != current_user.id
        and current_user.role != UserRole.ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能提交由当前账号创建的公司分析。",
        )

    if company.publish_status == PublishStatus.PUBLISHED:
        return {
            "status": "published",
            "company_id": company_id,
            "message": "该公司已发布。",
        }

    if company.pipeline_status != PipelineStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="请等待分析完成后再提交审核。",
        )

    if company_profile_needs_hydration(company):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "企业资料尚未抽取完整，请重新运行分析。",
                "missing_fields": company_profile_missing_fields(company),
            },
        )

    update_values = {
        "publish_status": PublishStatus.PENDING_REVIEW,
    }
    if not company.submitted_by:
        update_values["submitted_by"] = current_user.id

    await db.execute(update(Company).where(Company.id == cid).values(**update_values))
    await db.commit()

    return {
        "status": "pending_review",
        "company_id": company_id,
        "message": "公司资料已提交审核，审核通过后将在前台展示。",
    }


@router.get("/{company_id}/similar", response_model=list[SimilarCompanyItem])
async def get_similar_companies(
    company_id: str,
    db: DbSession,
    current_user: OptionalUser,
    top_k: int = 3,
):
    """
    相似公司推荐 — 先尝试 Qdrant 向量检索，
    向量库为空时降级为同类别随机推荐（保证接口始终有数据）
    """
    company = await get_company_by_identifier(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")
    if not _can_view_company_draft(company, current_user):
        raise HTTPException(status_code=404, detail="公司不存在")
    from app.services.company_retrieval import rank_similar_companies

    companies = await rank_similar_companies(db, company, limit=top_k)

    return [
        SimilarCompanyItem(
            id=str(c.id),
            path_key=c.path_key,
            name=c.name,
            short_description=c.short_description,
            logo_url=c.logo_url,
            geo_score=c.geo_score,
            category=c.category,
        )
        for c in companies
    ]
