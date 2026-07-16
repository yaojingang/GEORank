"""
AI 问答 API — 基于 GEO 知识、诊断上下文和公司知识库回答用户问题
对话持久化至 PostgreSQL，AI 部分支持流式输出（SSE）
"""
import asyncio
import json
import uuid
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, update

from app.core.deps import DbSession, CurrentUser, OptionalUser
from app.core.database import async_session
from app.models.conversation import Conversation, Message, MessageRole
from app.models.diagnostic import DiagnosticReport
from app.services.ai_usage import record_ai_usage, release_ai_access, resolve_ai_access

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[uuid.UUID] = None  # 继续已有对话
    diagnostic_report_id: Optional[uuid.UUID] = None  # 携带诊断报告上下文
    channel_key: Optional[str] = None  # 问答频道，如 geo-basics / diagnostic-explain


@router.get("/channels")
async def list_solution_channels():
    """公开问答频道配置，供前台渲染频道与推荐问题。"""
    from app.services.runtime_settings import get_solution_channel_config

    config = await get_solution_channel_config()
    channels = [
        {
            "key": channel.get("key"),
            "name": channel.get("name"),
            "description": channel.get("description"),
            "icon": channel.get("icon") or "forum",
            "enabled": channel.get("enabled", True),
            "sample_questions": channel.get("sample_questions") or [],
        }
        for channel in config.get("channels", [])
        if channel.get("enabled", True)
    ]
    default_key = config.get("default_channel_key")
    if default_key not in {channel["key"] for channel in channels} and channels:
        default_key = channels[0]["key"]
    return {
        "default_channel_key": default_key,
        "channels": channels,
    }


@router.post("/chat")
async def chat(data: ChatRequest, request: Request, db: DbSession, current_user: OptionalUser):
    """
    AI 问答（非流式版本）：
    1. 获取或创建对话
    2. 保存用户消息
    3. 按问答频道执行 RAG 检索和回答生成
    4. 保存 AI 回复
    5. 返回完整响应
    """
    diagnostic_report_id = str(data.diagnostic_report_id) if data.diagnostic_report_id else None
    user_id = current_user.id if current_user else None
    conversation = await _get_requested_conversation(db, data.conversation_id, user_id)
    await _validate_diagnostic_report_access(db, data.diagnostic_report_id, user_id)
    access = await resolve_ai_access(
        db=db,
        request=request,
        current_user=current_user,
        module="solutions",
        prompt_text=data.message,
    )
    try:
        if conversation is None:
            conversation = await _create_conversation(db, user_id)

        # 保存用户消息
        user_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=data.message,
            diagnostic_context_id=data.diagnostic_report_id,
        )
        db.add(user_msg)
        await db.flush()

        # 执行 AI 问答
        reply_text, recommended_companies, provider_succeeded = await _run_rag(
            data.message,
            diagnostic_report_id,
            db,
            data.channel_key,
            provider_override=access.provider_override,
        )
        # 保存 AI 回复
        ai_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=reply_text,
            recommended_companies=recommended_companies,
        )
        db.add(ai_msg)

        # 更新对话标题（取首条用户消息前 30 字）
        if not conversation.title:
            await db.execute(
                update(Conversation)
                .where(Conversation.id == conversation.id)
                .values(title=data.message[:30])
            )

        await record_ai_usage(
            db,
            access,
            output_text=reply_text,
            status_value="success" if provider_succeeded else "error",
            error_code=None if provider_succeeded else "platform_ai_unavailable",
            metadata={
                "channel_key": data.channel_key,
                "diagnostic_report_id": diagnostic_report_id,
                "conversation_id": str(conversation.id),
            },
        )
        await db.commit()
    except Exception:
        await db.rollback()
        await release_ai_access(db, access, error_code="solution_generation_failed")
        await db.commit()
        raise

    return {
        "conversation_id": str(conversation.id),
        "reply": reply_text,
        "recommended_companies": recommended_companies,
    }


@router.post("/chat/stream")
async def chat_stream(data: ChatRequest, request: Request, db: DbSession, current_user: OptionalUser):
    """SSE 流式 AI 问答版本"""
    diagnostic_report_id = str(data.diagnostic_report_id) if data.diagnostic_report_id else None
    user_id = current_user.id if current_user else None
    conversation = await _get_requested_conversation(db, data.conversation_id, user_id)
    await _validate_diagnostic_report_access(db, data.diagnostic_report_id, user_id)
    access = await resolve_ai_access(
        db=db,
        request=request,
        current_user=current_user,
        module="solutions",
        prompt_text=data.message,
    )
    try:
        if conversation is None:
            conversation = await _create_conversation(db, user_id)
        user_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=data.message,
            diagnostic_context_id=data.diagnostic_report_id,
        )
        db.add(user_msg)
        await db.commit()
    except Exception:
        await db.rollback()
        await release_ai_access(db, access, error_code="solution_stream_setup_failed")
        await db.commit()
        raise

    async def event_generator() -> AsyncGenerator[str, None]:
        full_reply = ""
        recommended = []
        status_value = "success"
        error_code = None

        try:
            async for chunk in _stream_rag(
                data.message,
                diagnostic_report_id,
                db,
                data.channel_key,
                provider_override=access.provider_override,
            ):
                if chunk["type"] == "text":
                    full_reply += chunk["content"]
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk['content']})}\n\n"
                elif chunk["type"] == "fallback":
                    status_value = "error"
                    error_code = "platform_ai_unavailable"
                    full_reply += chunk["content"]
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk['content']})}\n\n"
                elif chunk["type"] == "companies":
                    recommended = chunk["content"]
                    yield f"data: {json.dumps({'type': 'companies', 'content': recommended})}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            status_value = "error"
            error_code = "client_disconnected"
            raise
        except Exception as e:
            status_value = "error"
            error_code = "ai_generation_failed"
            error_content = e.detail if isinstance(e, HTTPException) else str(e)
            yield f"data: {json.dumps({'type': 'error', 'content': error_content})}\n\n"
        finally:
            async def finalize_stream() -> None:
                # Use a response-independent session so client cancellation does
                # not roll back the provider cost that has already been incurred.
                async with async_session() as settlement_db:
                    ai_msg = Message(
                        conversation_id=conversation.id,
                        role=MessageRole.ASSISTANT,
                        content=full_reply,
                        recommended_companies=recommended,
                    )
                    settlement_db.add(ai_msg)
                    if not conversation.title:
                        await settlement_db.execute(
                            update(Conversation)
                            .where(Conversation.id == conversation.id)
                            .values(title=data.message[:30])
                        )
                    await record_ai_usage(
                        settlement_db,
                        access,
                        output_text=full_reply,
                        status_value=status_value,
                        error_code=error_code,
                        metadata={
                            "channel_key": data.channel_key,
                            "diagnostic_report_id": diagnostic_report_id,
                            "conversation_id": str(conversation.id),
                            "stream": True,
                        },
                        charge_reserved_tokens_on_error=error_code == "client_disconnected",
                    )
                    await settlement_db.commit()

            finalize_task = asyncio.create_task(finalize_stream())
            try:
                await asyncio.shield(finalize_task)
            except asyncio.CancelledError:
                # Keep settlement alive after the response task is cancelled.
                await finalize_task
                raise
            yield f"data: {json.dumps({'type': 'done', 'conversation_id': str(conversation.id)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/conversations")
async def list_conversations(db: DbSession, current_user: CurrentUser, page: int = 1, size: int = 20):
    """用户的历史对话列表"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    conversations = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "title": c.title or "未命名对话",
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, db: DbSession, current_user: OptionalUser):
    """获取完整对话记录（含所有消息）"""
    cid = uuid.UUID(conversation_id)
    result = await db.execute(
        select(Conversation).where(Conversation.id == cid)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    if conversation.user_id is not None and (not current_user or conversation.user_id != current_user.id):
        raise HTTPException(status_code=404, detail="对话不存在")

    result = await db.execute(
        select(Message).where(Message.conversation_id == cid).order_by(Message.created_at)
    )
    messages = result.scalars().all()

    return {
        "id": str(conversation.id),
        "title": conversation.title or "未命名对话",
        "user_id": str(conversation.user_id) if conversation.user_id else None,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
        "messages": [
            {
                "id": str(m.id),
                "role": m.role.value,
                "content": m.content,
                "recommended_companies": m.recommended_companies,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.post("/conversations/{conversation_id}/claim")
async def claim_conversation(conversation_id: str, db: DbSession, current_user: CurrentUser):
    """将匿名公开会话认领到当前登录用户历史中。"""
    cid = uuid.UUID(conversation_id)
    result = await db.execute(select(Conversation).where(Conversation.id == cid))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    if conversation.user_id and conversation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="对话不存在")
    if conversation.user_id == current_user.id:
        return {
            "status": "already_owned",
            "conversation_id": str(conversation.id),
            "title": conversation.title or "未命名对话",
        }

    await db.execute(
        update(Conversation)
        .where(Conversation.id == cid)
        .values(user_id=current_user.id)
    )
    await db.commit()

    return {
        "status": "claimed",
        "conversation_id": str(conversation.id),
        "title": conversation.title or "未命名对话",
    }


# ============================================================
# 内部工具函数
# ============================================================

async def _get_requested_conversation(
    db,
    conversation_id: Optional[uuid.UUID],
    user_id: Optional[uuid.UUID],
) -> Conversation | None:
    """在额度预占前校验客户端传入的会话。"""
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")
        if conversation.user_id is not None and conversation.user_id != user_id:
            raise HTTPException(status_code=404, detail="对话不存在")
        return conversation
    return None


async def _create_conversation(db, user_id: Optional[uuid.UUID]) -> Conversation:
    conversation = Conversation(user_id=user_id)
    db.add(conversation)
    await db.flush()
    return conversation


async def _validate_diagnostic_report_access(
    db,
    report_id: Optional[uuid.UUID],
    user_id: Optional[uuid.UUID],
) -> None:
    if not report_id:
        return
    report = (
        await db.execute(select(DiagnosticReport).where(DiagnosticReport.id == report_id))
    ).scalar_one_or_none()
    if not report or (report.user_id is not None and report.user_id != user_id):
        raise HTTPException(status_code=404, detail="诊断报告不存在")


async def _run_rag(
    message: str,
    diagnostic_report_id: Optional[str],
    db,
    channel_key: Optional[str] = None,
    provider_override=None,
) -> tuple[str, list, bool]:
    """
    RAG 问答管道：
    1. 将用户问题向量化
    2. 在 Qdrant 中检索相关公司知识块
    3. 结合问答频道构建 Prompt → LLM 生成回答
    4. 返回 (回复文本, 关联公司列表)
    如果 OpenAI / Qdrant 不可用，返回友好的占位回复
    """
    try:
        from app.services.ai_client import ai_client
        reply, companies = await ai_client.rag_recommend(
            message,
            diagnostic_report_id,
            db,
            channel_key=channel_key,
            provider_override=provider_override,
        )
        return reply, companies, True
    except Exception as e:
        if provider_override is not None:
            raise HTTPException(
                status_code=502,
                detail="自定义 API Key 调用失败，请检查供应商、Base URL、模型和 Key。",
            ) from e
        # AI 服务不可用时的降级回复（用于本地开发）
        reply = (
            f"感谢您的提问：「{message}」\n\n"
            "目前 AI 问答服务需要配置可用的 LLM API Key 才能启用。\n"
            "请在后台设置中填入有效的 `openai_api_key`，或联系管理员。\n\n"
            "您也可以先浏览教程和诊断报告，手动梳理 GEO 优化问题。"
        )
        return reply, [], False


async def _stream_rag(
    message: str,
    diagnostic_report_id: Optional[str],
    db,
    channel_key: Optional[str] = None,
    provider_override=None,
):
    """流式 RAG（生成器），优先使用 AI，降级时输出提示"""
    try:
        from app.services.ai_client import ai_client
        async for chunk in ai_client.rag_recommend_stream(
            message,
            diagnostic_report_id,
            db,
            channel_key=channel_key,
            provider_override=provider_override,
        ):
            yield chunk
    except Exception as e:
        if provider_override is not None:
            raise HTTPException(
                status_code=502,
                detail="自定义 API Key 调用失败，请检查供应商、Base URL、模型和 Key。",
            ) from e
        text = (
            "AI 问答服务暂不可用。请配置 LLM API Key 后重试，"
            "或先浏览教程、诊断报告和公司目录获取帮助。"
        )
        # 逐词流式输出降级提示
        for word in text.split("，"):
            yield {"type": "fallback", "content": word + "，"}
