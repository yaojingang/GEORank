"""
数据处理流水线任务 — 清洗 → 知识图谱 → 向量化
"""
import json
import logging
import uuid
import enum
import time

from celery import shared_task
from app.core.logging_utils import log_event
from app.tasks.runtime import run_async as _run

logger = logging.getLogger("georank.process")


class StageClaimBusy(RuntimeError):
    """A live worker already owns the same asynchronous pipeline stage."""


class NextStageDispatchError(RuntimeError):
    """Business state advanced, but the next Celery task was not dispatched."""


def _normalize_update_values(values: dict) -> dict:
    """Convert Enum members to their database labels for Core updates."""
    normalized = {}
    for key, value in values.items():
        normalized[key] = value.value if isinstance(value, enum.Enum) else value
    return normalized


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """按词数切分文本，带重叠"""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def _is_final_attempt(task) -> bool:
    max_retries = getattr(task, "max_retries", None)
    return max_retries is not None and task.request.retries >= max_retries


async def _mark_company_failed(
    company_id: str,
    error: Exception | str,
    *,
    finalize_quota: bool = False,
    reservation_id: str | uuid.UUID | None = None,
) -> None:
    from app.core.database import async_session
    from app.models.company import Company, PipelineStatus
    from sqlalchemy import select, update

    async with async_session() as db:
        query = select(Company).where(Company.id == uuid.UUID(company_id))
        if reservation_id is not None:
            try:
                expected_reservation_id = uuid.UUID(str(reservation_id))
            except (TypeError, ValueError):
                return
            query = query.where(Company.ai_reservation_id == expected_reservation_id)
        company = (await db.execute(query.with_for_update())).scalar_one_or_none()
        if not company:
            return
        await db.execute(
            update(Company)
            .where(Company.id == uuid.UUID(company_id))
            .values(**_normalize_update_values({
                "pipeline_status": PipelineStatus.FAILED,
                "pipeline_error": str(error)[:500],
            }))
        )
        if finalize_quota and company.ai_reservation_id:
            from app.services.ai_usage import record_async_task_usage
            await record_async_task_usage(
                db,
                module="companies",
                user_id=company.submitted_by,
                reservation_id=company.ai_reservation_id,
                status_value="error",
                error_code="company_pipeline_failed",
                metadata={
                    "company_id": str(company.id),
                    "async_task": True,
                    "terminal_failure": True,
                },
                charge_recorded_progress_on_error=True,
            )
        await db.commit()


async def _record_company_retry_error(
    company_id: str,
    error: Exception | str,
    *,
    reservation_id: str | uuid.UUID | None = None,
    retry_status=None,
) -> None:
    from app.core.database import async_session
    from app.models.company import Company
    from sqlalchemy import update

    query = update(Company).where(Company.id == uuid.UUID(company_id))
    if reservation_id is not None:
        try:
            expected_reservation_id = uuid.UUID(str(reservation_id))
        except (TypeError, ValueError):
            return
        query = query.where(Company.ai_reservation_id == expected_reservation_id)

    async with async_session() as db:
        values = {"pipeline_error": f"任务将自动重试：{str(error)[:450]}"}
        if retry_status is not None:
            values["pipeline_status"] = (
                retry_status.value if isinstance(retry_status, enum.Enum) else retry_status
            )
        await db.execute(query.values(**values))
        await db.commit()


async def _claim_company_stage(
    company_id: str,
    *,
    reservation_id: str | uuid.UUID | None,
    expected_status,
    stage: str,
    task_id: str | None,
) -> bool:
    from app.core.database import async_session
    from app.models.company import Company
    from sqlalchemy import select

    expected_reservation_id = None
    if reservation_id is not None:
        try:
            expected_reservation_id = uuid.UUID(str(reservation_id))
        except (TypeError, ValueError):
            return False
    now_epoch = int(time.time())
    marker = f"__georank_task_claim__:{stage}:{task_id or 'unknown'}:{now_epoch}"
    async with async_session() as db:
        company = (
            await db.execute(
                select(Company)
                .where(Company.id == uuid.UUID(company_id))
                .with_for_update()
            )
        ).scalar_one_or_none()
        expected_statuses = (
            set(expected_status)
            if isinstance(expected_status, (set, tuple, list))
            else {expected_status}
        )
        if (
            not company
            or company.pipeline_status not in expected_statuses
            or (
                expected_reservation_id is not None
                and company.ai_reservation_id != expected_reservation_id
            )
        ):
            return False
        current_error = str(company.pipeline_error or "")
        if current_error.startswith("__georank_task_claim__:"):
            try:
                claimed_epoch = int(current_error.rsplit(":", 1)[-1])
            except ValueError:
                claimed_epoch = now_epoch
            if claimed_epoch > now_epoch - 900:
                raise StageClaimBusy(f"{stage} 阶段正由其他任务处理")
        elif current_error and not current_error.startswith("任务将自动重试："):
            return False
        company.pipeline_error = marker
        await db.commit()
        return True


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


def _guard_company_reservation(
    company_id: str,
    reservation_id: str | uuid.UUID | None = None,
) -> bool:
    reservation_state = _run(_company_reservation_state(company_id, reservation_id))
    if reservation_state == "active":
        return True
    if reservation_state in {"missing", "stale", "finished"}:
        return False
    _run(
        _mark_company_failed(
            company_id,
            "AI 额度预占已失效，请重新发起分析。",
            finalize_quota=True,
            reservation_id=reservation_id,
        )
    )
    return False


async def _claim_company_provider_stage(
    reservation_id: str | uuid.UUID | None,
    stage: str,
    claim_id: str,
) -> bool:
    from app.core.database import async_session
    from app.services.ai_usage import claim_async_reservation_stage

    async with async_session() as db:
        claimed = await claim_async_reservation_stage(
            db,
            reservation_id=reservation_id,
            stage=stage,
            claim_id=claim_id,
        )
        await db.commit()
        return claimed


async def _release_company_provider_stage(
    reservation_id: str | uuid.UUID | None,
    stage: str,
    claim_id: str,
) -> None:
    from app.core.database import async_session
    from app.services.ai_usage import release_async_reservation_stage_claim

    async with async_session() as db:
        await release_async_reservation_stage_claim(
            db,
            reservation_id=reservation_id,
            stage=stage,
            claim_id=claim_id,
        )
        await db.commit()


async def _resume_company_pipeline(
    company_id: str,
    reservation_id: str | uuid.UUID | None,
    completed_stage: str,
) -> bool:
    """Re-dispatch a next stage after a worker crashed between commit and send."""
    from app.core.database import async_session
    from app.core.celery_app import celery_app
    from app.models.company import Company, PipelineStatus
    from sqlalchemy import select

    expected_reservation_id = (
        uuid.UUID(str(reservation_id)) if reservation_id is not None else None
    )
    transitions = {
        "crawl": (
            PipelineStatus.CLEANING,
            "app.tasks.process.clean_company_data",
        ),
        "clean": (
            PipelineStatus.GRAPH_BUILDING,
            "app.tasks.process.build_knowledge_graph",
        ),
        "graph": (
            PipelineStatus.VECTORIZING,
            "app.tasks.process.vectorize_knowledge_base",
        ),
    }
    if completed_stage == "vector":
        async with async_session() as db:
            company = await db.get(Company, uuid.UUID(company_id))
            return bool(
                company
                and company.pipeline_status == PipelineStatus.COMPLETED
                and (
                    expected_reservation_id is None
                    or company.ai_reservation_id == expected_reservation_id
                )
            )
    transition = transitions.get(completed_stage)
    if not transition:
        return False
    expected_status, task_name = transition
    async with async_session() as db:
        company = await db.scalar(
            select(Company).where(Company.id == uuid.UUID(company_id))
        )
        if (
            not company
            or company.pipeline_status != expected_status
            or (
                expected_reservation_id is not None
                and company.ai_reservation_id != expected_reservation_id
            )
        ):
            return False
    try:
        celery_app.send_task(
            task_name,
            args=[company_id, str(reservation_id) if reservation_id is not None else None],
        )
    except Exception as exc:
        raise NextStageDispatchError(str(exc)) from exc
    return True


def _retry_dispatch_or_finalize(
    task,
    *,
    company_id: str,
    reservation_id: str | uuid.UUID | None,
    error: Exception,
) -> None:
    from celery.exceptions import MaxRetriesExceededError

    try:
        task.retry(exc=error, countdown=60, max_retries=20)
    except MaxRetriesExceededError:
        _run(_mark_company_failed(
            company_id,
            f"下一阶段任务连续派发失败：{error}",
            finalize_quota=True,
            reservation_id=reservation_id,
        ))


async def _run_clean(
    company_id: str,
    reservation_id: str | uuid.UUID | None = None,
    claim_id: str | None = None,
):
    from app.core.database import async_session
    from app.models.company import Company, PipelineStatus
    from app.services.company_profile import (
        build_company_profile_values,
        calculate_company_geo_profile,
        company_profile_missing_fields,
        extract_company_profile,
        load_company_homepage_html,
        load_company_source_text,
    )
    from sqlalchemy import select, update

    async with async_session() as db:
        company_query = select(Company).where(Company.id == uuid.UUID(company_id))
        expected_reservation_id = None
        if reservation_id is not None:
            expected_reservation_id = uuid.UUID(str(reservation_id))
            company_query = company_query.where(
                Company.ai_reservation_id == expected_reservation_id
            )
        result = await db.execute(company_query)
        company = result.scalar_one_or_none()
        if not company:
            return

        source_text = load_company_source_text(company)
        homepage_html = load_company_homepage_html(company)
        if not source_text or not homepage_html:
            raise RuntimeError("持久化官网资料缺失或无法回读")

        profile = await extract_company_profile(source_text, fallback_name=company.name)
        provider_succeeded = bool(profile.pop("_provider_succeeded", False))
        provider_tokens = 0
        if provider_succeeded:
            from app.services.ai_usage import estimate_token_count
            provider_tokens = estimate_token_count(
                source_text,
                json.dumps(profile, ensure_ascii=False),
            )
        if claim_id:
            from app.services.ai_usage import complete_async_reservation_stage
            completed = await complete_async_reservation_stage(
                db,
                reservation_id=reservation_id,
                stage=f"company_profile:{claim_id}",
                claim_id=claim_id,
                actual_tokens=provider_tokens,
            )
            if not completed:
                raise RuntimeError("公司资料抽取计量阶段完成失败")
            await db.commit()
        profile.update(calculate_company_geo_profile(company, homepage_html))

        # 构建更新字段
        values: dict = {
            "pipeline_status": PipelineStatus.GRAPH_BUILDING,
            "pipeline_error": None,
        }
        values.update(build_company_profile_values(company, profile, replace=True))

        profile_update = update(Company).where(Company.id == uuid.UUID(company_id))
        if expected_reservation_id is not None:
            profile_update = profile_update.where(
                Company.ai_reservation_id == expected_reservation_id
            )
        profile_result = await db.execute(
            profile_update
            .values(**_normalize_update_values(values))
            .returning(Company.id)
        )
        if profile_result.scalar_one_or_none() is None:
            await db.rollback()
            return
        await db.commit()
        await db.refresh(company)

        missing_fields = company_profile_missing_fields(company)
        if missing_fields:
            raise RuntimeError(f"公司资料抽取不完整：{', '.join(missing_fields)}")

        # 链式触发知识图谱构建
        from app.core.celery_app import celery_app
        try:
            celery_app.send_task(
                "app.tasks.process.build_knowledge_graph",
                args=[company_id, str(reservation_id) if reservation_id is not None else None],
            )
        except Exception as exc:
            raise NextStageDispatchError(str(exc)) from exc


async def _run_graph(
    company_id: str,
    reservation_id: str | uuid.UUID | None = None,
    claim_id: str | None = None,
):
    from app.core.database import async_session
    from app.models.company import Company, PipelineStatus
    from app.services.ai_client import ai_client
    from app.services.company_profile import load_company_source_text
    from sqlalchemy import select, update

    async with async_session() as db:
        company_query = select(Company).where(Company.id == uuid.UUID(company_id))
        expected_reservation_id = None
        if reservation_id is not None:
            expected_reservation_id = uuid.UUID(str(reservation_id))
            company_query = company_query.where(
                Company.ai_reservation_id == expected_reservation_id
            )
        result = await db.execute(company_query)
        company = result.scalar_one_or_none()
        if not company:
            return

        source_text = load_company_source_text(company)
        text = "\n".join(
            part
            for part in [company.description or company.short_description or "", source_text]
            if part
        )[:24000]
        if not text.strip():
            raise RuntimeError("没有可用于构建知识图谱的公司资料")

        entities_data = await ai_client.extract_entities(text)
        nodes = entities_data.get("nodes", [])
        rels = entities_data.get("relationships", [])
        from app.services.ai_usage import estimate_token_count
        provider_tokens = estimate_token_count(
            text,
            json.dumps(entities_data, ensure_ascii=False),
        )
        if claim_id:
            from app.services.ai_usage import complete_async_reservation_stage
            completed = await complete_async_reservation_stage(
                db,
                reservation_id=reservation_id,
                stage=f"company_graph:{claim_id}",
                claim_id=claim_id,
                actual_tokens=provider_tokens,
            )
            if not completed:
                raise RuntimeError("公司知识图谱计量阶段完成失败")
            await db.commit()

        if expected_reservation_id is not None:
            current_reservation_id = await db.scalar(
                select(Company.ai_reservation_id).where(Company.id == company.id)
            )
            if current_reservation_id != expected_reservation_id:
                return

        from app.services.graph_store import create_company_node, add_entities_and_relations
        await create_company_node(company_id, {
            "name": company.name,
            "url": company.url,
            "category": company.category or "",
        })
        entities = [
            {
                "name": node.get("name"),
                "type": node.get("type"),
                "props": {"description": node.get("description", "")},
            }
            for node in nodes
        ]
        if not any(entity["name"] == company.name for entity in entities):
            entities.insert(
                0,
                {
                    "name": company.name,
                    "type": "Company",
                    "props": {"description": company.description or ""},
                },
            )
        relations = [
            {"from": relation.get("from"), "to": relation.get("to"), "type": relation.get("type")}
            for relation in rels
        ]
        await add_entities_and_relations(company_id, entities, relations)

        vector_status_update = update(Company).where(
            Company.id == uuid.UUID(company_id)
        )
        if expected_reservation_id is not None:
            vector_status_update = vector_status_update.where(
                Company.ai_reservation_id == expected_reservation_id
            )
        vector_status_result = await db.execute(
            vector_status_update
            .values(**_normalize_update_values({
                "pipeline_status": PipelineStatus.VECTORIZING,
                "pipeline_error": None,
            }))
            .returning(Company.id)
        )
        if vector_status_result.scalar_one_or_none() is None:
            await db.rollback()
            return
        await db.commit()

        from app.core.celery_app import celery_app
        try:
            celery_app.send_task(
                "app.tasks.process.vectorize_knowledge_base",
                args=[company_id, str(reservation_id) if reservation_id is not None else None],
            )
        except Exception as exc:
            raise NextStageDispatchError(str(exc)) from exc


async def _run_vectorize(
    company_id: str,
    reservation_id: str | uuid.UUID | None = None,
    claim_id: str | None = None,
):
    from app.core.database import async_session
    from app.models.company import Company, PipelineStatus
    from app.services.ai_client import EmbeddingNotConfiguredError, ai_client
    from app.services.company_profile import load_company_source_text
    from app.services.vector_store import vector_store
    from sqlalchemy import select, update

    async with async_session() as db:
        company_query = select(Company).where(Company.id == uuid.UUID(company_id))
        expected_reservation_id = None
        if reservation_id is not None:
            expected_reservation_id = uuid.UUID(str(reservation_id))
            company_query = company_query.where(
                Company.ai_reservation_id == expected_reservation_id
            )
        result = await db.execute(company_query)
        company = result.scalar_one_or_none()
        if not company:
            return

        # 构建待向量化文本
        text_parts = []
        if company.name:
            text_parts.append(f"公司名称: {company.name}")
        if company.description:
            text_parts.append(company.description)
        elif company.short_description:
            text_parts.append(company.short_description)
        source_text = load_company_source_text(company, per_page_limit=10000)
        if source_text:
            text_parts.append(source_text)

        full_text = "\n".join(text_parts)
        chunks = _chunk_text(full_text)

        selected_chunks = chunks[:20]
        if not selected_chunks:
            raise RuntimeError("没有可写入向量知识库的公司内容")

        try:
            vectors = await ai_client.embed_batch(selected_chunks)
        except EmbeddingNotConfiguredError:
            vectors = []
            log_event(
                logger,
                logging.WARNING,
                "task.vectorize_company.embedding_skipped",
                company_id=company_id,
                reason="embedding_not_configured",
            )
        if vectors and len(vectors) != len(selected_chunks):
            raise RuntimeError(
                f"Embedding 返回数量不完整：期望 {len(selected_chunks)}，实际 {len(vectors)}"
            )
        from app.services.ai_usage import estimate_token_count
        provider_tokens = estimate_token_count(*selected_chunks) if vectors else 0
        if claim_id:
            from app.services.ai_usage import complete_async_reservation_stage
            provider_completed = await complete_async_reservation_stage(
                db,
                reservation_id=reservation_id,
                stage=f"company_vectors:{claim_id}",
                claim_id=claim_id,
                actual_tokens=provider_tokens,
            )
            if not provider_completed:
                raise RuntimeError("公司向量化计量阶段完成失败")
            await db.commit()

        if expected_reservation_id is not None:
            current_reservation_id = await db.scalar(
                select(Company.ai_reservation_id).where(Company.id == company.id)
            )
            if current_reservation_id != expected_reservation_id:
                return

        points = []
        for i, (chunk, vec) in enumerate(zip(selected_chunks, vectors)):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"georank:{company_id}:{i}"))
            points.append(
                {
                    "id": point_id,
                    "text": chunk,
                    "vector": vec,
                    "metadata": {"chunk_index": i, "category": company.category or ""},
                }
            )
        if points:
            vector_store.ensure_collection()
            vector_store.delete_company_vectors(company_id)
            vector_store.upsert_company_vectors(company_id, points)
        vector_count = len(points)

        # 分析完成后仍保持原发布状态，等待用户明确提交审核。
        completed_update = update(Company).where(Company.id == uuid.UUID(company_id))
        if expected_reservation_id is not None:
            completed_update = completed_update.where(
                Company.ai_reservation_id == expected_reservation_id
            )
        completed_result = await db.execute(
            completed_update
            .values(**_normalize_update_values({
                "pipeline_status": PipelineStatus.COMPLETED,
                "pipeline_error": None,
            }))
            .returning(Company.id)
        )
        if completed_result.scalar_one_or_none() is None:
            await db.rollback()
            return
        from app.services.ai_usage import record_async_task_usage
        await record_async_task_usage(
            db,
            module="companies",
            user_id=company.submitted_by,
            reservation_id=company.ai_reservation_id,
            input_text=full_text[:12000],
            output_text=(
                json.dumps(
                    {
                        "company_name": company.name,
                        "chunks": len(chunks),
                        "vectors": vector_count,
                        "pipeline_status": "completed",
                    },
                    ensure_ascii=False,
                )
                if vectors
                else ""
            ),
            estimated_input_tokens=provider_tokens,
            metadata={
                "company_id": str(company.id),
                "url": company.url,
                "chunk_count": len(chunks),
                "vector_count": vector_count,
                "async_task": True,
            },
        )
        await db.commit()


@shared_task(name="app.tasks.process.clean_company_data", bind=True)
def clean_company_data(self, company_id: str, reservation_id: str | None = None):
    """
    Step 2: 数据结构化清洗
    1. 从 MinIO 获取原始 HTML
    2. BeautifulSoup 提取纯文本
    3. LLM 结构化信息提取
    4. 更新 Company 记录
    5. 链式触发: build_knowledge_graph
    """
    from app.models.company import PipelineStatus

    provider_claim_id = f"{self.request.id}:{self.request.retries}"
    provider_stage = f"company_profile:{provider_claim_id}"
    try:
        if not _guard_company_reservation(company_id, reservation_id):
            return
        if not _run(
            _claim_company_stage(
                company_id,
                reservation_id=reservation_id,
                expected_status=PipelineStatus.CLEANING,
                stage="clean",
                task_id=self.request.id,
            )
        ):
            _run(_resume_company_pipeline(company_id, reservation_id, "clean"))
            return
        if not _run(_claim_company_provider_stage(
            reservation_id,
            provider_stage,
            provider_claim_id,
        )):
            return
        log_event(
            logger,
            logging.INFO,
            "task.clean_company.started",
            task_id=self.request.id,
            company_id=company_id,
            retries=self.request.retries,
        )
        _run(_run_clean(company_id, reservation_id, provider_claim_id))
        log_event(
            logger,
            logging.INFO,
            "task.clean_company.completed",
            task_id=self.request.id,
            company_id=company_id,
        )
    except NextStageDispatchError as exc:
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
            _run(_release_company_provider_stage(
                reservation_id,
                provider_stage,
                provider_claim_id,
            ))
        except Exception:
            pass
        logger.exception("clean_company_data failed: %s", company_id)
        log_event(
            logger,
            logging.ERROR,
            "task.clean_company.failed",
            task_id=self.request.id,
            company_id=company_id,
            retries=self.request.retries,
            error=str(exc)[:500],
        )
        try:
            if _is_final_attempt(self):
                _run(
                    _mark_company_failed(
                        company_id,
                        exc,
                        finalize_quota=True,
                        reservation_id=reservation_id,
                    )
                )
            else:
                _run(
                    _record_company_retry_error(
                        company_id,
                        exc,
                        reservation_id=reservation_id,
                        retry_status=PipelineStatus.CLEANING,
                    )
                )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="app.tasks.process.build_knowledge_graph", bind=True, max_retries=3)
def build_knowledge_graph(self, company_id: str, reservation_id: str | None = None):
    """
    Step 3: AI 知识图谱构建
    1. LLM 实体抽取 (NER)
    2. 校验实体与关系类型后写入 Neo4j
    3. 链式触发: vectorize_knowledge_base
    """
    from app.models.company import PipelineStatus

    provider_claim_id = f"{self.request.id}:{self.request.retries}"
    provider_stage = f"company_graph:{provider_claim_id}"
    try:
        if not _guard_company_reservation(company_id, reservation_id):
            return
        if not _run(
            _claim_company_stage(
                company_id,
                reservation_id=reservation_id,
                expected_status=PipelineStatus.GRAPH_BUILDING,
                stage="graph",
                task_id=self.request.id,
            )
        ):
            _run(_resume_company_pipeline(company_id, reservation_id, "graph"))
            return
        if not _run(_claim_company_provider_stage(
            reservation_id,
            provider_stage,
            provider_claim_id,
        )):
            return
        log_event(
            logger,
            logging.INFO,
            "task.build_graph.started",
            task_id=self.request.id,
            company_id=company_id,
            retries=self.request.retries,
        )
        _run(_run_graph(company_id, reservation_id, provider_claim_id))
        log_event(
            logger,
            logging.INFO,
            "task.build_graph.completed",
            task_id=self.request.id,
            company_id=company_id,
        )
    except NextStageDispatchError as exc:
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
            _run(_release_company_provider_stage(
                reservation_id,
                provider_stage,
                provider_claim_id,
            ))
        except Exception:
            pass
        logger.exception("build_knowledge_graph failed: %s", company_id)
        log_event(
            logger,
            logging.ERROR,
            "task.build_graph.failed",
            task_id=self.request.id,
            company_id=company_id,
            retries=self.request.retries,
            error=str(exc)[:500],
        )
        try:
            if _is_final_attempt(self):
                _run(
                    _mark_company_failed(
                        company_id,
                        exc,
                        finalize_quota=True,
                        reservation_id=reservation_id,
                    )
                )
            else:
                _run(
                    _record_company_retry_error(
                        company_id,
                        exc,
                        reservation_id=reservation_id,
                        retry_status=PipelineStatus.GRAPH_BUILDING,
                    )
                )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="app.tasks.process.vectorize_knowledge_base", bind=True, max_retries=3)
def vectorize_knowledge_base(self, company_id: str, reservation_id: str | None = None):
    """
    Step 4: 向量化知识库
    1. 文本切分（~400 词/块）
    2. 批量 Embedding
    3. 写入 Qdrant，失败时将流水线标记为失败
    4. 更新 pipeline_status → 'completed'，保留现有发布状态
    """
    from app.models.company import PipelineStatus

    provider_claim_id = f"{self.request.id}:{self.request.retries}"
    provider_stage = f"company_vectors:{provider_claim_id}"
    try:
        if not _guard_company_reservation(company_id, reservation_id):
            return
        if not _run(
            _claim_company_stage(
                company_id,
                reservation_id=reservation_id,
                expected_status=PipelineStatus.VECTORIZING,
                stage="vector",
                task_id=self.request.id,
            )
        ):
            _run(_resume_company_pipeline(company_id, reservation_id, "vector"))
            return
        if not _run(_claim_company_provider_stage(
            reservation_id,
            provider_stage,
            provider_claim_id,
        )):
            return
        log_event(
            logger,
            logging.INFO,
            "task.vectorize_company.started",
            task_id=self.request.id,
            company_id=company_id,
            retries=self.request.retries,
        )
        _run(_run_vectorize(company_id, reservation_id, provider_claim_id))
        log_event(
            logger,
            logging.INFO,
            "task.vectorize_company.completed",
            task_id=self.request.id,
            company_id=company_id,
        )
    except NextStageDispatchError as exc:
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
            _run(_release_company_provider_stage(
                reservation_id,
                provider_stage,
                provider_claim_id,
            ))
        except Exception:
            pass
        logger.exception("vectorize_knowledge_base failed: %s", company_id)
        log_event(
            logger,
            logging.ERROR,
            "task.vectorize_company.failed",
            task_id=self.request.id,
            company_id=company_id,
            retries=self.request.retries,
            error=str(exc)[:500],
        )
        try:
            if _is_final_attempt(self):
                _run(
                    _mark_company_failed(
                        company_id,
                        exc,
                        finalize_quota=True,
                        reservation_id=reservation_id,
                    )
                )
            else:
                _run(
                    _record_company_retry_error(
                        company_id,
                        exc,
                        reservation_id=reservation_id,
                        retry_status=PipelineStatus.VECTORIZING,
                    )
                )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="app.tasks.process.re_diagnose_all")
def re_diagnose_all():
    """定时任务: 每 30 天重新诊断所有已收录公司"""
    async def _run_all():
        from app.core.database import async_session
        from app.models.company import Company, PublishStatus, PipelineStatus
        from app.services.ai_usage import release_ai_access, resolve_system_async_ai_access
        from sqlalchemy import select, update
        from fastapi import HTTPException
        async with async_session() as db:
            result = await db.execute(
                select(Company).where(
                    Company.publish_status == PublishStatus.PUBLISHED,
                    Company.pipeline_status.in_([
                        PipelineStatus.COMPLETED,
                        PipelineStatus.FAILED,
                    ]),
                )
            )
            companies = result.scalars().all()
            from app.core.celery_app import celery_app
            for company in companies:
                try:
                    access = await resolve_system_async_ai_access(
                        db=db,
                        module="companies",
                        prompt_text=f"{company.name}\n{company.url}",
                    )
                except HTTPException as exc:
                    log_event(
                        logger,
                        logging.WARNING,
                        "task.re_diagnose_all.quota_blocked",
                        company_id=str(company.id),
                        detail=str(exc.detail)[:500],
                    )
                    break
                previous_pipeline_status = company.pipeline_status
                claim_result = await db.execute(
                    update(Company)
                    .where(
                        Company.id == company.id,
                        Company.pipeline_status == previous_pipeline_status,
                    )
                    .values(
                        ai_reservation_id=access.reservation_id,
                        pipeline_status=PipelineStatus.PENDING,
                        pipeline_error=None,
                        crawl_candidates=[],
                        crawl_pages=[],
                    )
                    .returning(Company.id)
                )
                if claim_result.scalar_one_or_none() is None:
                    await release_ai_access(
                        db,
                        access,
                        error_code="scheduled_company_state_changed",
                    )
                    await db.commit()
                    continue
                await db.commit()
                try:
                    celery_app.send_task(
                        "app.tasks.crawl.crawl_company_website",
                        args=[str(company.id), company.url, str(access.reservation_id)],
                    )
                except Exception as exc:
                    await db.execute(
                        update(Company)
                        .where(
                            Company.id == company.id,
                            Company.ai_reservation_id == access.reservation_id,
                        )
                        .values(
                            pipeline_status=PipelineStatus.FAILED,
                            pipeline_error="定时官网分析任务创建失败，请稍后重试。",
                        )
                    )
                    await release_ai_access(db, access, error_code="scheduled_task_queue_failed")
                    await db.commit()
                    log_event(
                        logger,
                        logging.ERROR,
                        "task.re_diagnose_all.queue_failed",
                        company_id=str(company.id),
                        error=str(exc)[:500],
                    )

    try:
        _run(_run_all())
    except Exception as e:
        logger.exception("re_diagnose_all failed: %s", e)
        log_event(logger, logging.ERROR, "task.re_diagnose_all.failed", error=str(e)[:500])
