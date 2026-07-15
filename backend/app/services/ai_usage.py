"""
AI 访问策略、用量统计和用户自定义 Key 临时上下文。
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request, status
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_usage import AIUsageEvent, UserDailyUsage
from app.models.settings import Setting
from app.models.user import User
from app.services.runtime_settings import get_ai_usage_policy_config

AI_USAGE_POLICY_SETTING_KEY = "api_usage_policy"
PLATFORM_MODES = {"platform_unlimited", "daily_quota", "quota_with_byok"}
QUOTA_MODES = {"daily_quota", "quota_with_byok"}
ASYNC_TASK_MIN_TOKENS = {
    "diagnostics": 2500,
    "companies": 6500,
}
ASYNC_TASK_LABELS = {
    "diagnostics": "GEO 诊断",
    "companies": "公司提交",
}
BROWSER_DIRECT_PROVIDER_SOURCE = "user_byok_browser_direct"


@dataclass(frozen=True)
class AIProviderOverride:
    provider: str
    api_key: str
    base_url: str
    model: str
    source: str = "user_byok_proxy"


@dataclass
class AIRequestAccess:
    module: str
    policy: dict[str, Any]
    user_id: uuid.UUID | None
    provider_source: str
    provider_override: AIProviderOverride | None
    estimated_input_tokens: int
    usage_date: Any = None
    used_tokens: int = 0
    remaining_tokens: int | None = None


def estimate_token_count(*texts: str | None) -> int:
    total_chars = sum(len(text or "") for text in texts)
    if total_chars <= 0:
        return 0
    return max(1, math.ceil(total_chars / 4))


def estimate_async_task_tokens(module: str, *texts: str | None) -> int:
    module_key = str(module or "").strip().lower()
    baseline = ASYNC_TASK_MIN_TOKENS.get(module_key, 1200)
    return max(baseline, estimate_token_count(*texts))


def _timezone(policy: dict[str, Any]) -> ZoneInfo:
    try:
        return ZoneInfo(policy.get("quota_reset_timezone") or "Asia/Shanghai")
    except Exception:
        return ZoneInfo("Asia/Shanghai")


def usage_date_for_policy(policy: dict[str, Any]):
    return datetime.now(_timezone(policy)).date()


def _provider_map(policy: dict[str, Any]) -> dict[str, dict[str, str]]:
    providers = policy.get("allowed_byok_providers") or []
    return {
        str(provider.get("key", "")).lower(): provider
        for provider in providers
        if provider.get("key")
    }


def _clean_header(value: str | None, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]


def _is_module_metered(policy: dict[str, Any], module: str) -> bool:
    return str(module or "").strip().lower() in set(policy.get("metered_modules") or [])


def parse_byok_override(request: Request, policy: dict[str, Any]) -> AIProviderOverride | None:
    api_key = _clean_header(request.headers.get("X-GEOrank-BYOK-Key"), 1000)
    if not api_key:
        return None
    if not policy.get("allow_user_byok", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前后台策略不允许使用用户自定义 API Key",
        )
    if policy.get("byok_transport_mode") == "browser_direct":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前策略要求浏览器直连，不能通过服务端代理使用用户 API Key",
        )

    providers = _provider_map(policy)
    provider_key = _clean_header(request.headers.get("X-GEOrank-BYOK-Provider"), 50).lower() or "custom"
    provider = providers.get(provider_key)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前模型供应商不在后台允许的自定义 API 范围内",
        )

    base_url = _clean_header(request.headers.get("X-GEOrank-BYOK-Base-URL"), 240) or provider.get("base_url", "")
    model = _clean_header(request.headers.get("X-GEOrank-BYOK-Model"), 100) or provider.get("default_model", "")
    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="请填写有效的 API Base URL")
    if not model:
        raise HTTPException(status_code=400, detail="请填写模型名称")

    return AIProviderOverride(
        provider=provider_key,
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        model=model,
    )


async def get_user_daily_usage(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    policy: dict[str, Any] | None = None,
) -> tuple[int, int, Any]:
    if not user_id:
        return 0, 0, usage_date_for_policy(policy or {})
    policy = policy or await get_ai_usage_policy_config()
    usage_date = usage_date_for_policy(policy)
    result = await db.execute(
        select(UserDailyUsage).where(
            UserDailyUsage.user_id == user_id,
            UserDailyUsage.usage_date == usage_date,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return 0, 0, usage_date
    return row.total_tokens or 0, row.request_count or 0, usage_date


def _quota_response(policy: dict[str, Any], used_tokens: int, request_tokens: int) -> dict[str, Any]:
    limit = int(policy.get("daily_token_limit") or 0)
    remaining = max(0, limit - used_tokens)
    return {
        "message": "今日 AI Token 额度不足，请明天再试或使用自己的 API Key。",
        "daily_token_limit": limit,
        "used_tokens": used_tokens,
        "remaining_tokens": remaining,
        "estimated_tokens": request_tokens,
        "allow_user_byok": bool(policy.get("allow_user_byok")),
    }


async def resolve_ai_access(
    *,
    db: AsyncSession,
    request: Request,
    current_user: User | None,
    module: str,
    prompt_text: str,
) -> AIRequestAccess:
    policy = await get_ai_usage_policy_config()
    module_key = module.strip().lower()
    if module_key not in set(policy.get("metered_modules") or []):
        return AIRequestAccess(
            module=module_key,
            policy=policy,
            user_id=current_user.id if current_user else None,
            provider_source="platform",
            provider_override=None,
            estimated_input_tokens=estimate_token_count(prompt_text),
        )

    provider_override = parse_byok_override(request, policy)
    if provider_override:
        return AIRequestAccess(
            module=module_key,
            policy=policy,
            user_id=current_user.id if current_user else None,
            provider_source=provider_override.source,
            provider_override=provider_override,
            estimated_input_tokens=estimate_token_count(prompt_text),
        )

    access_mode = policy.get("access_mode") or "platform_unlimited"
    if access_mode == "byok_required":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="当前后台策略要求使用自定义 API Key 后才能调用 AI 功能。",
        )
    if access_mode not in PLATFORM_MODES:
        access_mode = "platform_unlimited"

    request_tokens = estimate_token_count(prompt_text)
    if access_mode in QUOTA_MODES:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="请先登录后再使用平台免费 AI 额度。",
            )
        used_tokens, _, usage_date = await get_user_daily_usage(db, user_id=current_user.id, policy=policy)
        limit = int(policy.get("daily_token_limit") or 0)
        remaining = max(0, limit - used_tokens)
        if request_tokens > remaining:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=_quota_response(policy, used_tokens, request_tokens),
            )
        return AIRequestAccess(
            module=module_key,
            policy=policy,
            user_id=current_user.id,
            provider_source="platform",
            provider_override=None,
            estimated_input_tokens=request_tokens,
            usage_date=usage_date,
            used_tokens=used_tokens,
            remaining_tokens=remaining,
        )

    if not current_user and not policy.get("allow_anonymous_ai_usage", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再使用 AI 功能。",
        )

    return AIRequestAccess(
        module=module_key,
        policy=policy,
        user_id=current_user.id if current_user else None,
        provider_source="platform",
        provider_override=None,
        estimated_input_tokens=request_tokens,
    )


async def resolve_async_ai_access(
    *,
    db: AsyncSession,
    current_user: User | None,
    module: str,
    prompt_text: str,
) -> AIRequestAccess:
    """Pre-check an async AI task before it is queued.

    Async Celery jobs cannot use a browser-local BYOK value because that key is
    intentionally not stored server-side. They can only run on platform quota.
    """
    policy = await get_ai_usage_policy_config()
    module_key = str(module or "").strip().lower()
    request_tokens = estimate_async_task_tokens(module_key, prompt_text)
    access_mode = policy.get("access_mode") or "platform_unlimited"

    if not _is_module_metered(policy, module_key):
        return AIRequestAccess(
            module=module_key,
            policy=policy,
            user_id=current_user.id if current_user else None,
            provider_source="platform",
            provider_override=None,
            estimated_input_tokens=request_tokens,
        )

    label = ASYNC_TASK_LABELS.get(module_key, "异步任务")

    if access_mode == "byok_required":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"{label}属于异步任务，暂不支持使用浏览器本地 API Key 执行。请后台切换为平台额度模式后再发起。",
        )
    if access_mode not in PLATFORM_MODES:
        access_mode = "platform_unlimited"

    if access_mode in QUOTA_MODES:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"请先登录后再使用平台免费额度发起{label}。",
            )
        used_tokens, _, usage_date = await get_user_daily_usage(db, user_id=current_user.id, policy=policy)
        limit = int(policy.get("daily_token_limit") or 0)
        remaining = max(0, limit - used_tokens)
        if request_tokens > remaining:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"今日 AI Token 额度不足，{label}预计需要约 {request_tokens} token，"
                    f"当前剩余 {remaining} token。异步任务暂不支持浏览器本地 API Key，请明天再试或联系管理员增加平台额度。"
                ),
            )
        return AIRequestAccess(
            module=module_key,
            policy=policy,
            user_id=current_user.id,
            provider_source="platform",
            provider_override=None,
            estimated_input_tokens=request_tokens,
            usage_date=usage_date,
            used_tokens=used_tokens,
            remaining_tokens=remaining,
        )

    if not current_user and not policy.get("allow_anonymous_ai_usage", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"请先登录后再发起{label}。",
        )

    return AIRequestAccess(
        module=module_key,
        policy=policy,
        user_id=current_user.id if current_user else None,
        provider_source="platform",
        provider_override=None,
        estimated_input_tokens=request_tokens,
    )


async def record_ai_usage(
    db: AsyncSession,
    access: AIRequestAccess,
    *,
    output_text: str = "",
    status_value: str = "success",
    error_code: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AIUsageEvent:
    output_tokens = estimate_token_count(output_text)
    total_tokens = max(0, access.estimated_input_tokens + output_tokens)
    provider = access.provider_override.provider if access.provider_override else "platform"
    model = access.provider_override.model if access.provider_override else None
    event = AIUsageEvent(
        user_id=access.user_id,
        module=access.module,
        provider_source=access.provider_source,
        provider=provider,
        model=model,
        input_tokens=access.estimated_input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        status=status_value,
        error_code=error_code,
        event_metadata=metadata or {},
    )
    db.add(event)

    if (
        access.user_id
        and access.provider_source == "platform"
        and total_tokens > 0
        and status_value == "success"
        and _is_module_metered(access.policy, access.module)
    ):
        usage_date = access.usage_date or usage_date_for_policy(access.policy)
        result = await db.execute(
            select(UserDailyUsage).where(
                UserDailyUsage.user_id == access.user_id,
                UserDailyUsage.usage_date == usage_date,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            await db.execute(
                update(UserDailyUsage)
                .where(UserDailyUsage.id == row.id)
                .values(
                    total_tokens=(row.total_tokens or 0) + total_tokens,
                    request_count=(row.request_count or 0) + 1,
                    updated_at=datetime.utcnow(),
                )
            )
        else:
            db.add(
                UserDailyUsage(
                    user_id=access.user_id,
                    usage_date=usage_date,
                    total_tokens=total_tokens,
                    request_count=1,
                )
            )
    return event


async def record_async_task_usage(
    db: AsyncSession,
    *,
    module: str,
    user_id: uuid.UUID | None,
    input_text: str = "",
    output_text: str = "",
    status_value: str = "success",
    error_code: str | None = None,
    metadata: dict[str, Any] | None = None,
    estimated_input_tokens: int | None = None,
) -> AIUsageEvent:
    policy = await get_ai_usage_policy_config()
    module_key = str(module or "").strip().lower()
    access = AIRequestAccess(
        module=module_key,
        policy=policy,
        user_id=user_id,
        provider_source="platform",
        provider_override=None,
        estimated_input_tokens=(
            estimated_input_tokens
            if estimated_input_tokens is not None
            else estimate_async_task_tokens(module_key, input_text)
        ),
        usage_date=usage_date_for_policy(policy),
    )
    return await record_ai_usage(
        db,
        access,
        output_text=output_text,
        status_value=status_value,
        error_code=error_code,
        metadata=metadata,
    )


async def record_browser_direct_usage(
    db: AsyncSession,
    *,
    module: str,
    user_id: uuid.UUID | None,
    provider: str,
    model: str,
    input_text: str = "",
    output_text: str = "",
    status_value: str = "success",
    error_code: str | None = None,
    metadata: dict[str, Any] | None = None,
    estimated_input_tokens: int | None = None,
    estimated_output_tokens: int | None = None,
) -> AIUsageEvent:
    """Record non-sensitive stats for browser-direct BYOK calls.

    User API keys never enter this function. Browser-direct events are useful
    for admin visibility, but they do not consume platform daily quota.
    """
    input_tokens = max(0, estimated_input_tokens if estimated_input_tokens is not None else estimate_token_count(input_text))
    output_tokens = max(0, estimated_output_tokens if estimated_output_tokens is not None else estimate_token_count(output_text))
    event = AIUsageEvent(
        user_id=user_id,
        module=str(module or "").strip().lower() or "tools",
        provider_source=BROWSER_DIRECT_PROVIDER_SOURCE,
        provider=str(provider or "custom").strip()[:50] or "custom",
        model=str(model or "").strip()[:100] or None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        status="success" if status_value == "success" else "error",
        error_code=str(error_code or "").strip()[:100] or None,
        event_metadata=metadata or {},
    )
    db.add(event)
    return event


async def build_user_usage_payload(db: AsyncSession, current_user: User | None) -> dict[str, Any]:
    policy = await get_ai_usage_policy_config()
    used_tokens, request_count, usage_date = await get_user_daily_usage(
        db,
        user_id=current_user.id if current_user else None,
        policy=policy,
    )
    limit = int(policy.get("daily_token_limit") or 0)
    remaining = None if policy.get("access_mode") == "platform_unlimited" else max(0, limit - used_tokens)
    return {
        "access_mode": policy.get("access_mode"),
        "daily_token_limit": limit,
        "usage_date": usage_date.isoformat(),
        "used_tokens": used_tokens,
        "request_count": request_count,
        "remaining_tokens": remaining,
        "allow_user_byok": bool(policy.get("allow_user_byok")),
        "byok_transport_mode": policy.get("byok_transport_mode"),
        "metered_modules": policy.get("metered_modules") or [],
    }


def public_policy_payload(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "access_mode": policy.get("access_mode"),
        "daily_token_limit": int(policy.get("daily_token_limit") or 0),
        "quota_reset_timezone": policy.get("quota_reset_timezone"),
        "allow_anonymous_ai_usage": bool(policy.get("allow_anonymous_ai_usage")),
        "allow_user_byok": bool(policy.get("allow_user_byok")),
        "byok_transport_mode": policy.get("byok_transport_mode"),
        "allowed_byok_providers": policy.get("allowed_byok_providers") or [],
        "metered_modules": policy.get("metered_modules") or [],
    }


async def admin_usage_summary(db: AsyncSession) -> dict[str, Any]:
    total_tokens = (
        await db.execute(select(func.coalesce(func.sum(AIUsageEvent.total_tokens), 0)))
    ).scalar_one()
    total_requests = (
        await db.execute(select(func.count(AIUsageEvent.id)))
    ).scalar_one()
    byok_requests = (
        await db.execute(
            select(func.count(AIUsageEvent.id)).where(
                AIUsageEvent.provider_source.in_(["user_byok_proxy", BROWSER_DIRECT_PROVIDER_SOURCE])
            )
        )
    ).scalar_one()
    module_rows = (
        await db.execute(
            select(AIUsageEvent.module, func.coalesce(func.sum(AIUsageEvent.total_tokens), 0))
            .group_by(AIUsageEvent.module)
            .order_by(desc(func.coalesce(func.sum(AIUsageEvent.total_tokens), 0)))
            .limit(8)
        )
    ).all()
    async_module_rows = (
        await db.execute(
            select(
                AIUsageEvent.module,
                func.coalesce(func.sum(AIUsageEvent.total_tokens), 0),
                func.count(AIUsageEvent.id),
            )
            .where(
                AIUsageEvent.module.in_(list(ASYNC_TASK_MIN_TOKENS.keys())),
                AIUsageEvent.provider_source == "platform",
                AIUsageEvent.status == "success",
            )
            .group_by(AIUsageEvent.module)
            .order_by(desc(func.coalesce(func.sum(AIUsageEvent.total_tokens), 0)))
        )
    ).all()
    recent_events = (
        await db.execute(select(AIUsageEvent).order_by(AIUsageEvent.created_at.desc()).limit(20))
    ).scalars().all()
    async_modules = [
        {
            "module": module,
            "label": ASYNC_TASK_LABELS.get(module, module),
            "total_tokens": int(tokens or 0),
            "request_count": int(request_count or 0),
        }
        for module, tokens, request_count in async_module_rows
    ]
    return {
        "total_tokens": int(total_tokens or 0),
        "total_requests": int(total_requests or 0),
        "byok_requests": int(byok_requests or 0),
        "async_total_tokens": sum(item["total_tokens"] for item in async_modules),
        "async_total_requests": sum(item["request_count"] for item in async_modules),
        "async_modules": async_modules,
        "modules": [
            {"module": module, "total_tokens": int(tokens or 0)}
            for module, tokens in module_rows
        ],
        "recent_events": [
            {
                "id": str(event.id),
                "user_id": str(event.user_id) if event.user_id else None,
                "module": event.module,
                "provider_source": event.provider_source,
                "provider": event.provider,
                "model": event.model,
                "total_tokens": event.total_tokens,
                "status": event.status,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in recent_events
        ],
    }


def normalize_policy_payload(payload: dict[str, Any], current_policy: dict[str, Any]) -> dict[str, Any]:
    merged = {**current_policy, **(payload or {})}
    if "allowed_byok_providers" not in payload:
        merged["allowed_byok_providers"] = current_policy.get("allowed_byok_providers") or []
    if "metered_modules" not in payload:
        merged["metered_modules"] = current_policy.get("metered_modules") or []
    return merged


async def store_policy_setting(db: AsyncSession, admin: User, policy: dict[str, Any]) -> None:
    result = await db.execute(
        select(Setting).where(Setting.key == AI_USAGE_POLICY_SETTING_KEY)
    )
    setting = result.scalar_one_or_none()
    if setting:
        await db.execute(
            update(Setting)
            .where(Setting.key == AI_USAGE_POLICY_SETTING_KEY)
            .values(value=policy, category="ai_usage", is_public=False, updated_by=admin.id)
        )
    else:
        db.add(
            Setting(
                key=AI_USAGE_POLICY_SETTING_KEY,
                value=policy,
                category="ai_usage",
                is_public=False,
                updated_by=admin.id,
            )
        )
