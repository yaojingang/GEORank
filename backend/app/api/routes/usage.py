"""
前台 AI 用量与策略接口。
"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.deps import DbSession, OptionalUser
from app.services.ai_usage import build_user_usage_payload, public_policy_payload, record_browser_direct_usage
from app.services.runtime_settings import get_ai_usage_policy_config

router = APIRouter()


class BrowserDirectUsageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: str = Field(default="tools", max_length=50)
    tool_key: str | None = Field(default=None, max_length=50)
    provider: str = Field(default="custom", max_length=50)
    model: str = Field(default="", max_length=100)
    input_tokens: int | None = Field(default=None, ge=0, le=300000)
    output_tokens: int | None = Field(default=None, ge=0, le=300000)
    status_value: Literal["success", "error"] = "success"
    error_code: str | None = Field(default=None, max_length=100)


@router.get("/policy")
async def get_usage_policy():
    policy = await get_ai_usage_policy_config()
    return public_policy_payload(policy)


@router.get("/me")
async def get_my_usage(request: Request, db: DbSession, current_user: OptionalUser):
    return await build_user_usage_payload(db, current_user, request)


@router.post("/browser-direct")
async def report_browser_direct_usage(
    payload: BrowserDirectUsageReport,
    db: DbSession,
    current_user: OptionalUser,
):
    """Record non-sensitive browser-direct tool usage stats.

    The request schema forbids extra fields so API keys cannot be accepted by
    this endpoint accidentally. Browser-direct usage never increments platform
    daily quota.
    """
    policy = await get_ai_usage_policy_config()
    if not current_user and not policy.get("allow_anonymous_ai_usage", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录后再上报 AI 用量")
    if not policy.get("allow_user_byok", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前后台策略不允许使用用户自定义 API Key")
    if policy.get("byok_transport_mode") != "browser_direct":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前后台策略未启用浏览器直连模式")

    module = (payload.module or "tools").strip().lower()
    if module != "tools":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="浏览器直连统计当前只支持工具频道")

    allowed_providers = {
        str(provider.get("key", "")).lower()
        for provider in policy.get("allowed_byok_providers") or []
        if provider.get("key")
    }
    provider_key = (payload.provider or "custom").strip().lower()
    if provider_key not in allowed_providers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前模型供应商不在后台允许范围内")

    event = await record_browser_direct_usage(
        db,
        module=module,
        user_id=current_user.id if current_user else None,
        provider=provider_key,
        model=payload.model,
        status_value=payload.status_value,
        error_code=payload.error_code,
        estimated_input_tokens=payload.input_tokens,
        estimated_output_tokens=payload.output_tokens,
        metadata={"tool_key": payload.tool_key, "transport": "browser_direct"},
    )
    await db.commit()
    return {
        "status": "recorded",
        "event_id": str(event.id),
        "total_tokens": event.total_tokens,
    }
