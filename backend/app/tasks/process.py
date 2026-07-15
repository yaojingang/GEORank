"""
数据处理流水线任务 — 清洗 → 知识图谱 → 向量化
"""
import json
import logging
import uuid
import enum

from celery import shared_task
from app.core.logging_utils import log_event
from app.tasks.runtime import run_async as _run

logger = logging.getLogger("georank.process")


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


async def _run_clean(company_id: str):
    from app.core.database import async_session
    from app.models.company import Company, PipelineStatus
    from app.services.company_profile import (
        build_company_profile_values,
        extract_company_profile,
        load_company_source_html,
    )
    from sqlalchemy import select, update

    async with async_session() as db:
        result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
        company = result.scalar_one_or_none()
        if not company:
            return

        combined_html = load_company_source_html(company)
        if not combined_html:
            # 降级：直接 HTTP 获取
            import httpx
            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(company.url, headers={"User-Agent": "GEOrankBot/1.0"})
                    combined_html = resp.text
            except Exception as e:
                await db.execute(
                    update(Company)
                    .where(Company.id == uuid.UUID(company_id))
                    .values(**_normalize_update_values({
                        "pipeline_status": PipelineStatus.FAILED,
                        "pipeline_error": f"无法获取页面: {e}",
                    }))
                )
                await db.commit()
                return

        profile = await extract_company_profile(combined_html, fallback_name=company.name)

        # 构建更新字段
        values: dict = {"pipeline_status": PipelineStatus.GRAPH_BUILDING}
        values.update(build_company_profile_values(company, profile))

        await db.execute(
            update(Company)
            .where(Company.id == uuid.UUID(company_id))
            .values(**_normalize_update_values(values))
        )
        await db.commit()

        # 链式触发知识图谱构建
        from app.core.celery_app import celery_app
        celery_app.send_task("app.tasks.process.build_knowledge_graph", args=[company_id])


async def _run_graph(company_id: str):
    from app.core.database import async_session
    from app.models.company import Company, PipelineStatus
    from app.services.storage import storage
    from app.services.ai_client import ai_client
    from sqlalchemy import select, update
    from bs4 import BeautifulSoup

    async with async_session() as db:
        result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
        company = result.scalar_one_or_none()
        if not company:
            return

        # 获取文本
        text = company.description or company.short_description or ""
        graph_key = None
        for page in company.crawl_pages or []:
            if page.get("role") == "homepage" and page.get("key"):
                graph_key = page.get("key")
                break
        graph_key = graph_key or company.raw_html_key
        if graph_key:
            raw = storage.get(graph_key)
            if raw:
                soup = BeautifulSoup(raw.decode("utf-8", errors="replace"), "lxml")
                for tag in soup(["script", "style"]):
                    tag.decompose()
                text = soup.get_text(separator=" ", strip=True)[:5000]

        # LLM 实体抽取（失败时跳过，不阻塞流水线）
        try:
            entities_data = await ai_client.extract_entities(text)
            nodes = entities_data.get("nodes", [])
            rels = entities_data.get("relationships", [])

            if nodes:
                from app.services.graph_store import create_company_node, add_entities_and_relations
                await create_company_node(company_id, {
                    "name": company.name,
                    "url": company.url,
                    "category": company.category or "",
                })
                entities = [{"name": n["name"], "type": n.get("type", "Entity"), "props": {"description": n.get("description", "")}} for n in nodes]
                relations = [{"from": r["from"], "to": r["to"], "type": r["type"]} for r in rels]
                await add_entities_and_relations(company_id, entities, relations)
        except Exception as e:
            logger.warning("Graph building failed for %s (non-fatal): %s", company_id, e)

        await db.execute(
            update(Company)
            .where(Company.id == uuid.UUID(company_id))
            .values(**_normalize_update_values({
                "pipeline_status": PipelineStatus.VECTORIZING,
            }))
        )
        await db.commit()

        from app.core.celery_app import celery_app
        celery_app.send_task("app.tasks.process.vectorize_knowledge_base", args=[company_id])


async def _run_vectorize(company_id: str):
    from app.core.database import async_session
    from app.models.company import Company, PipelineStatus, PublishStatus
    from app.services.storage import storage
    from app.services.ai_client import ai_client
    from app.services.vector_store import vector_store
    from sqlalchemy import select, update
    from bs4 import BeautifulSoup

    async with async_session() as db:
        result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
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
        page_keys = []
        for page in company.crawl_pages or []:
            if page.get("key"):
                page_keys.append(page["key"])
        if not page_keys and company.raw_html_key:
            page_keys = [company.raw_html_key]

        for key in page_keys:
            raw = storage.get(key)
            if not raw:
                continue
            soup = BeautifulSoup(raw.decode("utf-8", errors="replace"), "lxml")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            text_parts.append(soup.get_text(separator=" ", strip=True)[:10000])

        full_text = "\n".join(text_parts)
        chunks = _chunk_text(full_text)

        # 批量 Embedding（失败时跳过，不阻塞流水线）
        vector_count = 0
        try:
            vector_store.ensure_collection()
            vectors = await ai_client.embed_batch(chunks[:20])  # 最多 20 块
            points = []
            for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
                # Qdrant point id 需要是整数或 UUID 字符串
                point_id = abs(hash(f"{company_id}_{i}")) % (2**63)
                points.append({"id": point_id, "text": chunk, "vector": vec, "metadata": {"chunk_index": i}})
            vector_store.upsert_company_vectors(company_id, points)
            vector_count = len(points)
        except Exception as e:
            logger.warning("Vectorization failed for %s (non-fatal): %s", company_id, e)

        # 流水线完成，进入待审核
        await db.execute(
            update(Company)
            .where(Company.id == uuid.UUID(company_id))
            .values(**_normalize_update_values({
                "pipeline_status": PipelineStatus.COMPLETED,
                "publish_status": PublishStatus.PENDING_REVIEW,
            }))
        )
        from app.services.ai_usage import record_async_task_usage
        await record_async_task_usage(
            db,
            module="companies",
            user_id=company.submitted_by,
            input_text=full_text[:12000],
            output_text=json.dumps(
                {
                    "company_name": company.name,
                    "chunks": len(chunks),
                    "vectors": vector_count,
                    "pipeline_status": "completed",
                },
                ensure_ascii=False,
            ),
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
def clean_company_data(self, company_id: str):
    """
    Step 2: 数据结构化清洗
    1. 从 MinIO 获取原始 HTML
    2. BeautifulSoup 提取纯文本
    3. LLM 结构化信息提取
    4. 更新 Company 记录
    5. 链式触发: build_knowledge_graph
    """
    try:
        log_event(
            logger,
            logging.INFO,
            "task.clean_company.started",
            task_id=self.request.id,
            company_id=company_id,
            retries=self.request.retries,
        )
        _run(_run_clean(company_id))
        log_event(
            logger,
            logging.INFO,
            "task.clean_company.completed",
            task_id=self.request.id,
            company_id=company_id,
        )
    except Exception as exc:
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
        async def _mark_failed():
            from app.core.database import async_session
            from app.models.company import Company, PipelineStatus
            from sqlalchemy import update
            async with async_session() as db:
                await db.execute(
                    update(Company)
                    .where(Company.id == uuid.UUID(company_id))
                    .values(**_normalize_update_values({
                        "pipeline_status": PipelineStatus.FAILED,
                        "pipeline_error": str(exc)[:500],
                    }))
                )
                await db.commit()
        try:
            _run(_mark_failed())
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="app.tasks.process.build_knowledge_graph", bind=True)
def build_knowledge_graph(self, company_id: str):
    """
    Step 3: AI 知识图谱构建
    1. LLM 实体抽取 (NER)
    2. 写入 Neo4j（失败时跳过，不阻塞流水线）
    3. 链式触发: vectorize_knowledge_base
    """
    try:
        log_event(
            logger,
            logging.INFO,
            "task.build_graph.started",
            task_id=self.request.id,
            company_id=company_id,
            retries=self.request.retries,
        )
        _run(_run_graph(company_id))
        log_event(
            logger,
            logging.INFO,
            "task.build_graph.completed",
            task_id=self.request.id,
            company_id=company_id,
        )
    except Exception as exc:
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
        # 图谱构建失败不阻塞，直接进入向量化
        try:
            from app.core.celery_app import celery_app
            celery_app.send_task("app.tasks.process.vectorize_knowledge_base", args=[company_id])
        except Exception:
            pass


@shared_task(name="app.tasks.process.vectorize_knowledge_base", bind=True)
def vectorize_knowledge_base(self, company_id: str):
    """
    Step 4: 向量化知识库
    1. 文本切分（~400 词/块）
    2. 批量 Embedding
    3. 写入 Qdrant（失败时跳过）
    4. 更新 pipeline_status → 'completed'，publish_status → 'pending_review'
    """
    try:
        log_event(
            logger,
            logging.INFO,
            "task.vectorize_company.started",
            task_id=self.request.id,
            company_id=company_id,
            retries=self.request.retries,
        )
        _run(_run_vectorize(company_id))
        log_event(
            logger,
            logging.INFO,
            "task.vectorize_company.completed",
            task_id=self.request.id,
            company_id=company_id,
        )
    except Exception as exc:
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
        async def _mark_failed():
            from app.core.database import async_session
            from app.models.company import Company, PipelineStatus
            from sqlalchemy import update
            async with async_session() as db:
                await db.execute(
                    update(Company)
                    .where(Company.id == uuid.UUID(company_id))
                    .values(**_normalize_update_values({
                        "pipeline_status": PipelineStatus.FAILED,
                        "pipeline_error": str(exc)[:500],
                    }))
                )
                await db.commit()
        try:
            _run(_mark_failed())
        except Exception:
            pass


@shared_task(name="app.tasks.process.re_diagnose_all")
def re_diagnose_all():
    """定时任务: 每 30 天重新诊断所有已收录公司"""
    async def _run_all():
        from app.core.database import async_session
        from app.models.company import Company, PublishStatus, PipelineStatus
        from sqlalchemy import select
        async with async_session() as db:
            result = await db.execute(
                select(Company).where(Company.publish_status == PublishStatus.PUBLISHED)
            )
            companies = result.scalars().all()

        from app.core.celery_app import celery_app
        for c in companies:
            celery_app.send_task("app.tasks.crawl.crawl_company_website", args=[str(c.id), c.url])

    try:
        _run(_run_all())
    except Exception as e:
        logger.exception("re_diagnose_all failed: %s", e)
        log_event(logger, logging.ERROR, "task.re_diagnose_all.failed", error=str(e)[:500])
