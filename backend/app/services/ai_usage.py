"""
AI 访问策略、用量统计和用户自定义 Key 临时上下文。
"""
from __future__ import annotations

import math
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request, status
from sqlalchemy import desc, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_usage import (
    AICreditWallet,
    AIGlobalDailyBudget,
    AIPrincipalDevice,
    AIPrincipalUser,
    AIQuotaAuditLog,
    AIQuotaPrincipal,
    AITokenReservation,
    AIUsageEvent,
    UserDailyUsage,
)
from app.models.settings import Setting
from app.models.user import User, UserRole
from app.services.runtime_settings import get_ai_usage_policy_config

AI_USAGE_POLICY_SETTING_KEY = "api_usage_policy"
PLATFORM_MODES = {
    "platform_unlimited",
    "daily_quota",
    "quota_with_byok",
    "lifetime_quota_with_byok",
}
QUOTA_MODES = {"daily_quota", "quota_with_byok"}
ASYNC_TASK_MIN_TOKENS = {
    "diagnostics": 10000,
    "companies": 10000,
}
MODULE_RESERVATION_MIN_TOKENS = {
    "solutions": 6500,
    "keywords": 6500,
    "diagnostics": 10000,
    "companies": 10000,
    "tools": 4500,
}
MODULE_CHARGE_MIN_TOKENS = {
    "solutions": 1200,
    "keywords": 2500,
    "diagnostics": 2500,
    "companies": 6500,
    "tools": 1200,
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
    principal_id: uuid.UUID | None = None
    reservation_id: uuid.UUID | None = None
    reserved_tokens: int = 0
    usage_date: Any = None
    used_tokens: int = 0
    remaining_tokens: int | None = None


def estimate_token_count(*texts: str | None) -> int:
    combined = "".join(text or "" for text in texts)
    if not combined:
        return 0
    non_ascii_chars = sum(1 for char in combined if ord(char) > 127)
    ascii_chars = len(combined) - non_ascii_chars
    # CJK text is commonly close to one token per character, while Latin text
    # is closer to four characters per token. This intentionally errs high.
    return max(1, non_ascii_chars + math.ceil(ascii_chars / 4))


def estimate_async_task_tokens(module: str, *texts: str | None) -> int:
    module_key = str(module or "").strip().lower()
    baseline = ASYNC_TASK_MIN_TOKENS.get(module_key, 1200)
    return max(baseline, estimate_token_count(*texts))


def calculate_reservation_tokens(module: str, input_tokens: int) -> int:
    """Return a conservative pre-authorization amount for a platform call."""
    module_key = str(module or "").strip().lower()
    minimum = MODULE_RESERVATION_MIN_TOKENS.get(module_key, 1200)
    return max(minimum, max(0, int(input_tokens or 0)) * 3)


def evaluate_platform_quota(
    *,
    policy: dict[str, Any],
    requested_tokens: int,
    personal_remaining: int | None,
    global_remaining: int | None,
    personal_quota_required: bool,
) -> str | None:
    """Return a stable reason code when a platform reservation must be denied."""
    if policy.get("emergency_byok_only"):
        return "emergency_byok_only"
    if personal_quota_required and (personal_remaining or 0) < requested_tokens:
        return "personal_quota_exhausted"
    if policy.get("global_budget_enabled") and (global_remaining or 0) < requested_tokens:
        return "global_daily_budget_exhausted"
    return None


def build_quota_error_detail(
    *,
    reason_code: str,
    policy: dict[str, Any],
    requested_tokens: int,
    personal_remaining: int | None,
    global_remaining: int | None,
) -> dict[str, Any]:
    allow_user_byok = bool(policy.get("allow_user_byok", True))
    if allow_user_byok:
        messages = {
            "personal_quota_exhausted": "平台赠送的 AI Token 已用完，请绑定自己的 API Key 后继续使用。",
            "personal_quota_frozen": "当前账号的 AI 免费额度已被冻结，请联系管理员或绑定自己的 API Key。",
            "global_daily_budget_exhausted": "今日平台 AI Token 预算已达到上限，请绑定自己的 API Key 后继续使用。",
            "emergency_byok_only": "平台已临时切换为自备 API 模式，请绑定自己的 API Key 后继续使用。",
            "byok_required": "当前 AI 功能需要使用你自己的 API Key。",
        }
        fallback_message = "当前平台额度不可用，请绑定自己的 API Key。"
    else:
        messages = {
            "personal_quota_exhausted": "平台赠送的 AI Token 已用完，当前未开放自备 API，请联系管理员。",
            "personal_quota_frozen": "当前账号的 AI 免费额度已被冻结，请联系管理员。",
            "global_daily_budget_exhausted": "今日平台 AI Token 预算已达到上限，请稍后再试或联系管理员。",
            "emergency_byok_only": "平台 AI 服务当前暂停，请稍后再试或联系管理员。",
            "byok_required": "当前 AI 功能暂不可用，请联系管理员。",
        }
        fallback_message = "当前平台额度不可用，请稍后再试或联系管理员。"
    return {
        "code": reason_code,
        "message": messages.get(reason_code, fallback_message),
        "guidance": dict(policy.get("byok_guidance") or {}),
        "quota": {
            "requested_tokens": max(0, int(requested_tokens or 0)),
            "personal_remaining_tokens": personal_remaining,
            "global_remaining_tokens": global_remaining,
        },
        "allow_user_byok": allow_user_byok,
    }


def _timezone(policy: dict[str, Any]) -> ZoneInfo:
    try:
        return ZoneInfo(policy.get("quota_reset_timezone") or "Asia/Shanghai")
    except Exception:
        return ZoneInfo("Asia/Shanghai")


def usage_date_for_policy(policy: dict[str, Any]):
    return datetime.now(_timezone(policy)).date()


def reservation_expiry_for_policy(policy: dict[str, Any], module: str) -> datetime:
    max_lifetime = timedelta(hours=6 if module in ASYNC_TASK_MIN_TOKENS else 1)
    now_utc = datetime.utcnow()
    if module not in ASYNC_TASK_MIN_TOKENS:
        return now_utc + max_lifetime
    timezone = _timezone(policy)
    now_local = datetime.now(timezone)
    next_day_local = datetime.combine(
        now_local.date() + timedelta(days=1),
        datetime.min.time(),
        tzinfo=timezone,
    )
    until_rollover = next_day_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None) - now_utc
    return now_utc + min(max_lifetime, max(timedelta(seconds=1), until_rollover))


def _provider_map(policy: dict[str, Any]) -> dict[str, dict[str, str]]:
    providers = policy.get("allowed_byok_providers") or []
    return {
        str(provider.get("key", "")).lower(): provider
        for provider in providers
        if provider.get("key")
    }


def _clean_header(value: str | None, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]


def _http_origin(value: str) -> tuple[str, str, int] | None:
    try:
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            return None
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None
    return parsed.scheme, parsed.hostname.lower(), port


def _is_module_metered(policy: dict[str, Any], module: str) -> bool:
    return str(module or "").strip().lower() in set(policy.get("metered_modules") or [])


def parse_byok_override(request: Request, policy: dict[str, Any]) -> AIProviderOverride | None:
    api_key = _clean_header(request.headers.get("X-GEOrank-BYOK-Key"), 1000)
    if not api_key:
        return None
    if not policy.get("allow_user_byok", True):
        return None
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

    configured_base_url = _clean_header(provider.get("base_url", ""), 240)
    base_url = _clean_header(request.headers.get("X-GEOrank-BYOK-Base-URL"), 240) or configured_base_url
    model = _clean_header(request.headers.get("X-GEOrank-BYOK-Model"), 100) or provider.get("default_model", "")
    configured_origin = _http_origin(configured_base_url)
    requested_origin = _http_origin(base_url)
    if not configured_origin or requested_origin != configured_origin:
        raise HTTPException(
            status_code=400,
            detail="API Base URL 必须使用后台允许的供应商地址",
        )
    if not model:
        raise HTTPException(status_code=400, detail="请填写模型名称")

    return AIProviderOverride(
        provider=provider_key,
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        model=model,
    )


def _request_device_hash(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    raw_device_id = _clean_header(request.headers.get("X-GEOrank-Device-ID"), 200)
    if len(raw_device_id) < 16:
        return None, None
    device_hash = hashlib.sha256(raw_device_id.encode("utf-8")).hexdigest()
    user_agent = _clean_header(request.headers.get("User-Agent"), 500)
    user_agent_hash = hashlib.sha256(user_agent.encode("utf-8")).hexdigest() if user_agent else None
    return device_hash, user_agent_hash


async def _advisory_lock(db: AsyncSession, key: str) -> None:
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": key},
    )


async def _active_principal_id(
    db: AsyncSession,
    principal_id: uuid.UUID,
) -> uuid.UUID:
    """Resolve a merged principal chain to its current active principal."""
    current_id = principal_id
    visited: set[uuid.UUID] = set()
    while current_id not in visited:
        visited.add(current_id)
        row = (
            await db.execute(
                select(
                    AIQuotaPrincipal.status,
                    AIQuotaPrincipal.merged_into_id,
                ).where(AIQuotaPrincipal.id == current_id)
            )
        ).one_or_none()
        if not row or row.status != "merged" or not row.merged_into_id:
            return current_id
        current_id = row.merged_into_id
    return current_id


async def _linked_principal_ids(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    device_hash: str | None,
) -> list[uuid.UUID]:
    user_principal_id = await db.scalar(
        select(AIPrincipalUser.principal_id).where(AIPrincipalUser.user_id == user_id)
    )
    device_principal_id = None
    if device_hash:
        device_principal_id = await db.scalar(
            select(AIPrincipalDevice.principal_id).where(
                AIPrincipalDevice.device_hash == device_hash
            )
        )
    return [
        principal_id
        for principal_id in (user_principal_id, device_principal_id)
        if principal_id is not None
    ]


async def _lock_linked_principals(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    device_hash: str | None,
) -> list[uuid.UUID]:
    """Lock active principals and re-read links to serialize cross-link merges."""
    locked_ids: set[uuid.UUID] = set()
    for _ in range(8):
        linked_ids = await _linked_principal_ids(
            db,
            user_id=user_id,
            device_hash=device_hash,
        )
        active_ids = sorted(
            {
                await _active_principal_id(db, principal_id)
                for principal_id in linked_ids
            },
            key=str,
        )
        for principal_id in active_ids:
            if principal_id in locked_ids:
                continue
            await _advisory_lock(db, f"ai-quota-principal:{principal_id}")
            locked_ids.add(principal_id)

        refreshed_ids = await _linked_principal_ids(
            db,
            user_id=user_id,
            device_hash=device_hash,
        )
        refreshed_active_ids = sorted(
            {
                await _active_principal_id(db, principal_id)
                for principal_id in refreshed_ids
            },
            key=str,
        )
        if set(refreshed_active_ids).issubset(locked_ids):
            return refreshed_active_ids
    raise RuntimeError("AI 额度主体关联持续变化，请稍后重试")


async def _historical_platform_usage(db: AsyncSession, user_ids: list[uuid.UUID]) -> tuple[int, int]:
    if not user_ids:
        return 0, 0
    total, request_count = (
        await db.execute(
            select(
                func.coalesce(func.sum(AIUsageEvent.total_tokens), 0),
                func.count(AIUsageEvent.id),
            ).where(
                AIUsageEvent.user_id.in_(user_ids),
                AIUsageEvent.provider_source == "platform",
                AIUsageEvent.status == "success",
            )
        )
    ).one()
    return max(0, int(total or 0)), max(0, int(request_count or 0))


async def _merge_quota_principals(
    db: AsyncSession,
    principal_ids: list[uuid.UUID],
    *,
    default_grant: int,
) -> uuid.UUID:
    unique_ids = sorted(set(principal_ids), key=str)
    pending_reservations = list(
        (
            await db.execute(
                select(AITokenReservation)
                .where(
                    AITokenReservation.principal_id.in_(unique_ids),
                    AITokenReservation.status == "pending",
                )
                .with_for_update()
            )
        ).scalars()
    )
    wallets = list(
        (
            await db.execute(
                select(AICreditWallet)
                .where(AICreditWallet.principal_id.in_(unique_ids))
                .with_for_update()
            )
        ).scalars()
    )
    grant = max([default_grant, *(wallet.granted_tokens for wallet in wallets)])
    consumed_tokens = sum(max(0, wallet.consumed_tokens) for wallet in wallets)
    reserved_tokens = sum(max(0, wallet.reserved_tokens) for wallet in wallets)
    request_count = sum(max(0, wallet.request_count) for wallet in wallets)
    frozen = any(wallet.frozen for wallet in wallets)

    merged = AIQuotaPrincipal(status="active")
    db.add(merged)
    await db.flush()
    db.add(
        AICreditWallet(
            principal_id=merged.id,
            granted_tokens=grant,
            consumed_tokens=consumed_tokens,
            reserved_tokens=reserved_tokens,
            request_count=request_count,
            frozen=frozen,
        )
    )
    for reservation in pending_reservations:
        reservation.principal_id = merged.id
    await db.execute(
        update(AIPrincipalUser)
        .where(AIPrincipalUser.principal_id.in_(unique_ids))
        .values(principal_id=merged.id, updated_at=datetime.utcnow())
    )
    await db.execute(
        update(AIPrincipalDevice)
        .where(AIPrincipalDevice.principal_id.in_(unique_ids))
        .values(principal_id=merged.id, last_seen_at=datetime.utcnow())
    )
    await db.execute(
        update(AIQuotaPrincipal)
        .where(AIQuotaPrincipal.id.in_(unique_ids))
        .values(status="merged", merged_into_id=merged.id, updated_at=datetime.utcnow())
    )
    return merged.id


async def get_or_create_quota_principal(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    device_hash: str | None,
    user_agent_hash: str | None,
    default_grant: int,
) -> tuple[uuid.UUID, AICreditWallet]:
    lock_keys = [f"ai-quota-user:{user_id}"]
    if device_hash:
        lock_keys.append(f"ai-quota-device:{device_hash}")
    for lock_key in sorted(lock_keys):
        await _advisory_lock(db, lock_key)

    user_was_linked = bool(
        await db.scalar(
            select(AIPrincipalUser.id).where(AIPrincipalUser.user_id == user_id)
        )
    )
    linked_ids = await _lock_linked_principals(
        db,
        user_id=user_id,
        device_hash=device_hash,
    )
    if len(set(linked_ids)) > 1:
        principal_id = await _merge_quota_principals(
            db,
            linked_ids,
            default_grant=default_grant,
        )
    elif linked_ids:
        principal_id = linked_ids[0]
    else:
        principal = AIQuotaPrincipal(status="active")
        db.add(principal)
        await db.flush()
        principal_id = principal.id

    await db.execute(
        pg_insert(AIPrincipalUser)
        .values(
            id=uuid.uuid4(),
            principal_id=principal_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        .on_conflict_do_update(
            constraint="uq_ai_principal_users_user_id",
            set_={"principal_id": principal_id, "updated_at": datetime.utcnow()},
        )
    )
    if device_hash:
        await db.execute(
            pg_insert(AIPrincipalDevice)
            .values(
                id=uuid.uuid4(),
                principal_id=principal_id,
                device_hash=device_hash,
                user_agent_hash=user_agent_hash,
                created_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
            )
            .on_conflict_do_update(
                constraint="uq_ai_principal_devices_device_hash",
                set_={
                    "principal_id": principal_id,
                    "user_agent_hash": user_agent_hash,
                    "last_seen_at": datetime.utcnow(),
                },
            )
        )

    wallet = (
        await db.execute(
            select(AICreditWallet)
            .where(AICreditWallet.principal_id == principal_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if wallet is None:
        member_ids = list(
            (
                await db.execute(
                    select(AIPrincipalUser.user_id).where(AIPrincipalUser.principal_id == principal_id)
                )
            ).scalars()
        )
        historical_usage, historical_requests = await _historical_platform_usage(db, member_ids)
        wallet = AICreditWallet(
            principal_id=principal_id,
            granted_tokens=default_grant,
            consumed_tokens=min(default_grant, historical_usage),
            reserved_tokens=0,
            request_count=historical_requests,
        )
        db.add(wallet)
        await db.flush()
    elif not user_was_linked:
        historical_usage, historical_requests = await _historical_platform_usage(
            db,
            [user_id],
        )
        if historical_usage or historical_requests:
            wallet.consumed_tokens = min(
                wallet.granted_tokens,
                max(0, wallet.consumed_tokens) + historical_usage,
            )
            wallet.request_count = max(0, wallet.request_count) + historical_requests
            wallet.version += 1
            wallet.updated_at = datetime.utcnow()
    return principal_id, wallet


async def _ensure_global_budget(
    db: AsyncSession,
    *,
    usage_date: Any,
    limit_tokens: int,
) -> None:
    await db.execute(
        pg_insert(AIGlobalDailyBudget)
        .values(
            id=uuid.uuid4(),
            usage_date=usage_date,
            limit_tokens=limit_tokens,
            consumed_tokens=0,
            reserved_tokens=0,
            request_count=0,
            updated_at=datetime.utcnow(),
        )
        .on_conflict_do_update(
            constraint="uq_ai_global_daily_budgets_date",
            set_={"limit_tokens": limit_tokens, "updated_at": datetime.utcnow()},
        )
    )


async def _reserve_platform_tokens(
    *,
    db: AsyncSession,
    request: Request | None,
    current_user: User | None,
    module: str,
    policy: dict[str, Any],
    input_tokens: int,
    reservation_tokens: int | None = None,
) -> AIRequestAccess:
    if not current_user and not policy.get("allow_anonymous_ai_usage", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再使用平台赠送的 AI 额度。",
        )

    released_count = await release_expired_token_reservations(db, limit=50)
    if released_count:
        await db.commit()

    requested_tokens = (
        max(0, int(reservation_tokens))
        if reservation_tokens is not None
        else calculate_reservation_tokens(module, input_tokens)
    )
    usage_date = usage_date_for_policy(policy)
    global_limit = max(0, int(policy.get("global_daily_token_limit") or 0))
    principal_id = None
    wallet = None
    personal_remaining = None
    personal_required = bool(
        current_user
        and current_user.role == UserRole.USER
        and policy.get("access_mode") == "lifetime_quota_with_byok"
    )

    if policy.get("emergency_byok_only"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=build_quota_error_detail(
                reason_code="emergency_byok_only",
                policy=policy,
                requested_tokens=requested_tokens,
                personal_remaining=None,
                global_remaining=None,
            ),
        )

    if personal_required and current_user:
        device_hash, user_agent_hash = _request_device_hash(request)
        if request is not None and not device_hash:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少有效的本地设备标识，请刷新页面后重试。",
            )
        principal_id, wallet = await get_or_create_quota_principal(
            db,
            user_id=current_user.id,
            device_hash=device_hash,
            user_agent_hash=user_agent_hash,
            default_grant=max(0, int(policy.get("lifetime_token_grant") or 0)),
        )
        personal_remaining = max(
            0,
            wallet.granted_tokens - wallet.consumed_tokens - wallet.reserved_tokens,
        )
        if wallet.frozen or personal_remaining < requested_tokens:
            reason = "personal_quota_frozen" if wallet.frozen else "personal_quota_exhausted"
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=build_quota_error_detail(
                    reason_code=reason,
                    policy=policy,
                    requested_tokens=requested_tokens,
                    personal_remaining=personal_remaining,
                    global_remaining=None,
                ),
            )
        wallet_update = await db.execute(
            update(AICreditWallet)
            .where(
                AICreditWallet.id == wallet.id,
                AICreditWallet.frozen.is_(False),
                AICreditWallet.granted_tokens
                - AICreditWallet.consumed_tokens
                - AICreditWallet.reserved_tokens
                >= requested_tokens,
            )
            .values(
                reserved_tokens=AICreditWallet.reserved_tokens + requested_tokens,
                version=AICreditWallet.version + 1,
                updated_at=datetime.utcnow(),
            )
            .returning(AICreditWallet.id)
        )
        if wallet_update.scalar_one_or_none() is None:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=build_quota_error_detail(
                    reason_code="personal_quota_exhausted",
                    policy=policy,
                    requested_tokens=requested_tokens,
                    personal_remaining=0,
                    global_remaining=None,
                ),
            )

    global_reserved = 0
    global_remaining = None
    if policy.get("global_budget_enabled", True):
        await _ensure_global_budget(db, usage_date=usage_date, limit_tokens=global_limit)
        budget = (
            await db.execute(
                select(AIGlobalDailyBudget).where(AIGlobalDailyBudget.usage_date == usage_date)
            )
        ).scalar_one()
        global_remaining = max(0, budget.limit_tokens - budget.consumed_tokens - budget.reserved_tokens)
        global_update = await db.execute(
            update(AIGlobalDailyBudget)
            .where(
                AIGlobalDailyBudget.id == budget.id,
                AIGlobalDailyBudget.limit_tokens
                - AIGlobalDailyBudget.consumed_tokens
                - AIGlobalDailyBudget.reserved_tokens
                >= requested_tokens,
            )
            .values(
                reserved_tokens=AIGlobalDailyBudget.reserved_tokens + requested_tokens,
                updated_at=datetime.utcnow(),
            )
            .returning(AIGlobalDailyBudget.id)
        )
        if global_update.scalar_one_or_none() is None:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=build_quota_error_detail(
                    reason_code="global_daily_budget_exhausted",
                    policy=policy,
                    requested_tokens=requested_tokens,
                    personal_remaining=personal_remaining,
                    global_remaining=global_remaining,
                ),
            )
        global_reserved = requested_tokens

    reservation = AITokenReservation(
        idempotency_key=uuid.uuid4().hex,
        principal_id=principal_id,
        user_id=current_user.id if current_user else None,
        usage_date=usage_date,
        module=module,
        status="pending",
        provider_source="platform",
        reserved_tokens=requested_tokens,
        personal_reserved_tokens=requested_tokens if personal_required else 0,
        global_reserved_tokens=global_reserved,
        expires_at=reservation_expiry_for_policy(policy, module),
    )
    db.add(reservation)
    await db.commit()
    return AIRequestAccess(
        module=module,
        policy=policy,
        user_id=current_user.id if current_user else None,
        provider_source="platform",
        provider_override=None,
        estimated_input_tokens=input_tokens,
        principal_id=principal_id,
        reservation_id=reservation.id,
        reserved_tokens=requested_tokens,
        usage_date=usage_date,
        used_tokens=wallet.consumed_tokens if wallet else 0,
        remaining_tokens=(
            max(0, personal_remaining - requested_tokens)
            if personal_remaining is not None
            else None
        ),
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
    input_tokens = estimate_token_count(prompt_text)
    provider_override = parse_byok_override(request, policy)
    if provider_override:
        if not current_user and not policy.get("allow_anonymous_ai_usage", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="请先登录后再使用自定义 API Key。",
            )
        return AIRequestAccess(
            module=module_key,
            policy=policy,
            user_id=current_user.id if current_user else None,
            provider_source=provider_override.source,
            provider_override=provider_override,
            estimated_input_tokens=input_tokens,
        )

    access_mode = policy.get("access_mode") or "lifetime_quota_with_byok"
    if access_mode == "byok_required":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=build_quota_error_detail(
                reason_code="byok_required",
                policy=policy,
                requested_tokens=calculate_reservation_tokens(module_key, input_tokens),
                personal_remaining=None,
                global_remaining=None,
            ),
        )
    if access_mode not in PLATFORM_MODES:
        policy = {**policy, "access_mode": "lifetime_quota_with_byok"}

    return await _reserve_platform_tokens(
        db=db,
        request=request,
        current_user=current_user,
        module=module_key,
        policy=policy,
        input_tokens=input_tokens,
    )


async def resolve_async_ai_access(
    *,
    db: AsyncSession,
    current_user: User | None,
    module: str,
    prompt_text: str,
    request: Request | None = None,
) -> AIRequestAccess:
    """Pre-check an async AI task before it is queued.

    Async Celery jobs cannot use a browser-local BYOK value because that key is
    intentionally not stored server-side. They can only run on platform quota.
    """
    policy = await get_ai_usage_policy_config()
    module_key = str(module or "").strip().lower()
    request_tokens = estimate_async_task_tokens(module_key, prompt_text)
    access_mode = policy.get("access_mode") or "lifetime_quota_with_byok"

    label = ASYNC_TASK_LABELS.get(module_key, "异步任务")

    if access_mode == "byok_required":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                **build_quota_error_detail(
                    reason_code="byok_required",
                    policy=policy,
                    requested_tokens=request_tokens,
                    personal_remaining=None,
                    global_remaining=None,
                ),
                "message": f"{label}需要可供后台任务使用的 API 凭据，请联系管理员或使用同步 AI 功能。",
            },
        )
    if access_mode not in PLATFORM_MODES:
        policy = {**policy, "access_mode": "lifetime_quota_with_byok"}

    return await _reserve_platform_tokens(
        db=db,
        request=request,
        current_user=current_user,
        module=module_key,
        policy=policy,
        input_tokens=request_tokens,
        reservation_tokens=request_tokens,
    )


async def resolve_system_async_ai_access(
    *,
    db: AsyncSession,
    module: str,
    prompt_text: str,
) -> AIRequestAccess:
    """Reserve global platform budget for scheduled, system-owned AI work."""
    policy = await get_ai_usage_policy_config()
    module_key = str(module or "").strip().lower()
    request_tokens = estimate_async_task_tokens(module_key, prompt_text)
    access_mode = policy.get("access_mode") or "lifetime_quota_with_byok"
    if access_mode == "byok_required" or policy.get("emergency_byok_only"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=build_quota_error_detail(
                reason_code=(
                    "emergency_byok_only"
                    if policy.get("emergency_byok_only")
                    else "byok_required"
                ),
                policy=policy,
                requested_tokens=request_tokens,
                personal_remaining=None,
                global_remaining=None,
            ),
        )
    if access_mode not in PLATFORM_MODES:
        policy = {**policy, "access_mode": "lifetime_quota_with_byok"}
    return await _reserve_platform_tokens(
        db=db,
        request=None,
        current_user=None,
        module=module_key,
        policy={**policy, "allow_anonymous_ai_usage": True},
        input_tokens=request_tokens,
        reservation_tokens=request_tokens,
    )


async def settle_token_reservation(
    db: AsyncSession,
    *,
    reservation_id: uuid.UUID | None,
    actual_tokens: int,
    succeeded: bool,
    charge_recorded_progress_on_error: bool = False,
) -> AITokenReservation | None:
    if not reservation_id:
        return None
    reservation = (
        await db.execute(
            select(AITokenReservation)
            .where(AITokenReservation.id == reservation_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if reservation is None or reservation.status != "pending":
        return reservation

    recorded_tokens = max(
        max(0, int(reservation.actual_tokens or 0)),
        max(0, int(actual_tokens or 0)),
    )
    if succeeded:
        calculated_charge = max(
            recorded_tokens,
            MODULE_CHARGE_MIN_TOKENS.get(reservation.module, 0),
        )
    elif charge_recorded_progress_on_error:
        calculated_charge = recorded_tokens
    else:
        calculated_charge = 0
    charged_tokens = calculated_charge
    authorized_tokens = max(0, int(reservation.reserved_tokens or 0))
    if calculated_charge > authorized_tokens:
        event_metadata = dict(reservation.event_metadata or {})
        event_metadata["reservation_overage_tokens"] = calculated_charge - authorized_tokens
        event_metadata["calculated_charge_tokens"] = calculated_charge
        reservation.event_metadata = event_metadata
    if reservation.personal_reserved_tokens and reservation.principal_id:
        await db.execute(
            update(AICreditWallet)
            .where(AICreditWallet.principal_id == reservation.principal_id)
            .values(
                reserved_tokens=func.greatest(
                    0,
                    AICreditWallet.reserved_tokens - reservation.personal_reserved_tokens,
                ),
                consumed_tokens=AICreditWallet.consumed_tokens + charged_tokens,
                request_count=AICreditWallet.request_count + (1 if charged_tokens else 0),
                version=AICreditWallet.version + 1,
                updated_at=datetime.utcnow(),
            )
        )
    if reservation.global_reserved_tokens:
        await db.execute(
            update(AIGlobalDailyBudget)
            .where(AIGlobalDailyBudget.usage_date == reservation.usage_date)
            .values(
                reserved_tokens=func.greatest(
                    0,
                    AIGlobalDailyBudget.reserved_tokens - reservation.global_reserved_tokens,
                ),
                consumed_tokens=func.least(
                    AIGlobalDailyBudget.limit_tokens,
                    AIGlobalDailyBudget.consumed_tokens + charged_tokens,
                ),
                request_count=AIGlobalDailyBudget.request_count + (1 if charged_tokens else 0),
                updated_at=datetime.utcnow(),
            )
        )
    reservation.actual_tokens = recorded_tokens
    reservation.charged_tokens = charged_tokens
    reservation.status = "settled" if succeeded or charged_tokens else "released"
    if charged_tokens and not succeeded:
        event_metadata = dict(reservation.event_metadata or {})
        event_metadata["settlement_outcome"] = "charged_recorded_progress_on_error"
        reservation.event_metadata = event_metadata
    reservation.settled_at = datetime.utcnow()
    return reservation


async def release_expired_token_reservations(
    db: AsyncSession,
    *,
    limit: int = 100,
) -> int:
    reservations = list(
        (
            await db.execute(
                select(AITokenReservation)
                .where(
                    AITokenReservation.status == "pending",
                    AITokenReservation.expires_at <= datetime.utcnow(),
                )
                .order_by(AITokenReservation.expires_at.asc())
                .limit(max(1, min(int(limit), 1000)))
                .with_for_update(skip_locked=True)
            )
        ).scalars()
    )
    for reservation in reservations:
        released = await settle_token_reservation(
            db,
            reservation_id=reservation.id,
            actual_tokens=0,
            succeeded=False,
            charge_recorded_progress_on_error=True,
        )
        if released:
            metadata = dict(released.event_metadata or {})
            metadata["release_reason"] = "reservation_expired"
            released.event_metadata = metadata
    return len(reservations)


async def async_reservation_is_pending(
    db: AsyncSession,
    reservation_id: uuid.UUID | str | None,
) -> bool:
    """Return whether an async worker is still authorized to spend platform quota."""
    if not reservation_id:
        return False
    try:
        resolved_id = uuid.UUID(str(reservation_id))
    except (TypeError, ValueError):
        return False
    reservation = (
        await db.execute(
            select(AITokenReservation).where(AITokenReservation.id == resolved_id)
        )
    ).scalar_one_or_none()
    policy = await get_ai_usage_policy_config()
    return bool(
        reservation
        and reservation.status == "pending"
        and reservation.expires_at > datetime.utcnow()
        and reservation.usage_date == usage_date_for_policy(policy)
    )


def _reservation_uuid(reservation_id: uuid.UUID | str | None) -> uuid.UUID | None:
    if not reservation_id:
        return None
    try:
        return uuid.UUID(str(reservation_id))
    except (TypeError, ValueError):
        return None


async def claim_async_reservation_stage(
    db: AsyncSession,
    *,
    reservation_id: uuid.UUID | str | None,
    stage: str,
    claim_id: str,
    lease_seconds: int = 900,
) -> bool:
    """Claim one provider-spending stage and reject concurrent duplicates."""
    resolved_id = _reservation_uuid(reservation_id)
    stage_key = str(stage or "").strip()[:80]
    claim_key = str(claim_id or "").strip()[:160]
    if not resolved_id or not stage_key or not claim_key:
        return False
    reservation = (
        await db.execute(
            select(AITokenReservation)
            .where(AITokenReservation.id == resolved_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if (
        not reservation
        or reservation.status != "pending"
        or reservation.expires_at <= datetime.utcnow()
    ):
        return False
    policy = await get_ai_usage_policy_config()
    if reservation.usage_date != usage_date_for_policy(policy):
        return False

    metadata = dict(reservation.event_metadata or {})
    stages = dict(metadata.get("provider_stages") or {})
    existing = dict(stages.get(stage_key) or {})
    if existing.get("status") == "completed":
        return False
    claimed_at = existing.get("claimed_at")
    if existing.get("status") == "claimed" and claimed_at:
        try:
            claimed_time = datetime.fromisoformat(str(claimed_at))
        except ValueError:
            claimed_time = datetime.utcnow()
        if claimed_time > datetime.utcnow() - timedelta(seconds=max(30, lease_seconds)):
            return False

    stages[stage_key] = {
        "status": "claimed",
        "claim_id": claim_key,
        "claimed_at": datetime.utcnow().isoformat(),
        "tokens": max(0, int(existing.get("tokens") or 0)),
    }
    metadata["provider_stages"] = stages
    reservation.event_metadata = metadata
    return True


async def complete_async_reservation_stage(
    db: AsyncSession,
    *,
    reservation_id: uuid.UUID | str | None,
    stage: str,
    claim_id: str,
    actual_tokens: int,
) -> bool:
    """Persist idempotent provider progress before a downstream stage runs."""
    resolved_id = _reservation_uuid(reservation_id)
    if not resolved_id:
        return False
    reservation = (
        await db.execute(
            select(AITokenReservation)
            .where(AITokenReservation.id == resolved_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not reservation or reservation.status != "pending":
        return False
    metadata = dict(reservation.event_metadata or {})
    stages = dict(metadata.get("provider_stages") or {})
    stage_key = str(stage or "").strip()[:80]
    existing = dict(stages.get(stage_key) or {})
    if existing.get("status") == "completed":
        return True
    if existing.get("claim_id") != str(claim_id or "").strip()[:160]:
        return False
    stages[stage_key] = {
        **existing,
        "status": "completed",
        "completed_at": datetime.utcnow().isoformat(),
        "tokens": max(0, int(actual_tokens or 0)),
    }
    metadata["provider_stages"] = stages
    reservation.event_metadata = metadata
    reservation.actual_tokens = sum(
        max(0, int(dict(value or {}).get("tokens") or 0))
        for value in stages.values()
        if dict(value or {}).get("status") == "completed"
    )
    return True


async def release_async_reservation_stage_claim(
    db: AsyncSession,
    *,
    reservation_id: uuid.UUID | str | None,
    stage: str,
    claim_id: str,
) -> None:
    resolved_id = _reservation_uuid(reservation_id)
    if not resolved_id:
        return
    reservation = (
        await db.execute(
            select(AITokenReservation)
            .where(AITokenReservation.id == resolved_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not reservation or reservation.status != "pending":
        return
    metadata = dict(reservation.event_metadata or {})
    stages = dict(metadata.get("provider_stages") or {})
    stage_key = str(stage or "").strip()[:80]
    existing = dict(stages.get(stage_key) or {})
    if existing.get("claim_id") != str(claim_id or "").strip()[:160]:
        return
    # Completed entries are append-only provider spend records. A later
    # persistence or dispatch failure may retry under a new stage key, but it
    # must not erase cost that the provider has already incurred.
    if existing.get("status") == "completed":
        return
    if existing.get("status") != "claimed":
        return
    stages.pop(stage_key, None)
    metadata["provider_stages"] = stages
    reservation.event_metadata = metadata
    reservation.actual_tokens = sum(
        max(0, int(dict(value or {}).get("tokens") or 0))
        for value in stages.values()
        if dict(value or {}).get("status") == "completed"
    )


async def release_ai_access(
    db: AsyncSession,
    access: AIRequestAccess,
    *,
    error_code: str | None = None,
) -> None:
    reservation = await settle_token_reservation(
        db,
        reservation_id=access.reservation_id,
        actual_tokens=0,
        succeeded=False,
    )
    if reservation and error_code:
        metadata = dict(reservation.event_metadata or {})
        metadata["release_error_code"] = error_code
        reservation.event_metadata = metadata


async def record_ai_usage(
    db: AsyncSession,
    access: AIRequestAccess,
    *,
    output_text: str = "",
    status_value: str = "success",
    error_code: str | None = None,
    metadata: dict[str, Any] | None = None,
    charge_recorded_progress_on_error: bool = False,
    charge_reserved_tokens_on_error: bool = False,
) -> AIUsageEvent:
    output_tokens = estimate_token_count(output_text)
    total_tokens = max(0, access.estimated_input_tokens + output_tokens)
    provider = access.provider_override.provider if access.provider_override else "platform"
    model = access.provider_override.model if access.provider_override else None
    event = AIUsageEvent(
        user_id=access.user_id,
        principal_id=access.principal_id,
        reservation_id=access.reservation_id,
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

    if access.provider_source == "platform" and access.reservation_id:
        settlement_tokens = total_tokens
        if status_value != "success" and charge_reserved_tokens_on_error:
            settlement_tokens = max(settlement_tokens, access.reserved_tokens)
        settled_reservation = await settle_token_reservation(
            db,
            reservation_id=access.reservation_id,
            actual_tokens=settlement_tokens,
            succeeded=status_value == "success",
            charge_recorded_progress_on_error=(
                charge_recorded_progress_on_error or charge_reserved_tokens_on_error
            ),
        )
        if settled_reservation and settled_reservation.charged_tokens > 0:
            total_tokens = settled_reservation.charged_tokens
            event.total_tokens = total_tokens

    if (
        access.provider_source == "platform"
        and status_value == "success"
        and not access.reservation_id
    ):
        total_tokens = max(total_tokens, MODULE_CHARGE_MIN_TOKENS.get(access.module, 0))
        event.total_tokens = total_tokens

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
    reservation_id: uuid.UUID | str | None = None,
    charge_recorded_progress_on_error: bool = False,
) -> AIUsageEvent:
    policy = await get_ai_usage_policy_config()
    module_key = str(module or "").strip().lower()
    resolved_reservation_id = uuid.UUID(str(reservation_id)) if reservation_id else None
    reservation = None
    if resolved_reservation_id:
        reservation = (
            await db.execute(
                select(AITokenReservation).where(AITokenReservation.id == resolved_reservation_id)
            )
        ).scalar_one_or_none()
    access = AIRequestAccess(
        module=module_key,
        policy=policy,
        user_id=user_id,
        provider_source="platform",
        provider_override=None,
        estimated_input_tokens=(
            estimated_input_tokens
            if estimated_input_tokens is not None
            else estimate_token_count(input_text)
        ),
        principal_id=reservation.principal_id if reservation else None,
        reservation_id=resolved_reservation_id,
        reserved_tokens=reservation.reserved_tokens if reservation else 0,
        usage_date=usage_date_for_policy(policy),
    )
    return await record_ai_usage(
        db,
        access,
        output_text=output_text,
        status_value=status_value,
        error_code=error_code,
        metadata=metadata,
        charge_recorded_progress_on_error=charge_recorded_progress_on_error,
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


async def build_user_usage_payload(
    db: AsyncSession,
    current_user: User | None,
    request: Request | None = None,
) -> dict[str, Any]:
    policy = await get_ai_usage_policy_config()
    usage_date = usage_date_for_policy(policy)
    grant_tokens = max(0, int(policy.get("lifetime_token_grant") or 0))
    used_tokens = 0
    reserved_tokens = 0
    request_count = 0
    remaining = grant_tokens if current_user else 0
    principal_id = None
    frozen = False
    linked_user_count = 0
    linked_device_count = 0
    if current_user and current_user.role == UserRole.USER:
        device_hash, user_agent_hash = _request_device_hash(request)
        principal_id, wallet = await get_or_create_quota_principal(
            db,
            user_id=current_user.id,
            device_hash=device_hash,
            user_agent_hash=user_agent_hash,
            default_grant=grant_tokens,
        )
        grant_tokens = wallet.granted_tokens
        used_tokens = wallet.consumed_tokens
        reserved_tokens = wallet.reserved_tokens
        request_count = wallet.request_count
        frozen = wallet.frozen
        remaining = max(0, grant_tokens - used_tokens - reserved_tokens)
        linked_user_count = int(
            await db.scalar(
                select(func.count(AIPrincipalUser.id)).where(AIPrincipalUser.principal_id == principal_id)
            ) or 0
        )
        linked_device_count = int(
            await db.scalar(
                select(func.count(AIPrincipalDevice.id)).where(AIPrincipalDevice.principal_id == principal_id)
            ) or 0
        )
        await db.commit()

    global_limit = max(0, int(policy.get("global_daily_token_limit") or 0))
    global_budget = (
        await db.execute(
            select(AIGlobalDailyBudget).where(AIGlobalDailyBudget.usage_date == usage_date)
        )
    ).scalar_one_or_none()
    global_used = global_budget.consumed_tokens if global_budget else 0
    global_reserved = global_budget.reserved_tokens if global_budget else 0
    global_remaining = max(0, global_limit - global_used - global_reserved)
    reason_code = None
    if policy.get("emergency_byok_only"):
        reason_code = "emergency_byok_only"
    elif frozen:
        reason_code = "personal_quota_frozen"
    elif (
        current_user
        and current_user.role == UserRole.USER
        and remaining < min(MODULE_RESERVATION_MIN_TOKENS.values())
    ):
        reason_code = "personal_quota_exhausted"
    elif (
        policy.get("global_budget_enabled")
        and global_remaining < min(MODULE_RESERVATION_MIN_TOKENS.values())
    ):
        reason_code = "global_daily_budget_exhausted"
    return {
        "access_mode": policy.get("access_mode"),
        "daily_token_limit": int(policy.get("daily_token_limit") or 0),
        "lifetime_token_grant": grant_tokens,
        "grant_tokens": grant_tokens,
        "usage_date": usage_date.isoformat(),
        "used_tokens": used_tokens,
        "reserved_tokens": reserved_tokens,
        "request_count": request_count,
        "remaining_tokens": remaining,
        "quota_state": (
            "frozen"
            if frozen
            else (
                "exhausted"
                if remaining < min(MODULE_RESERVATION_MIN_TOKENS.values())
                else "available"
            )
        ),
        "principal_id": str(principal_id) if principal_id else None,
        "linked_user_count": linked_user_count,
        "linked_device_count": linked_device_count,
        "global_budget": {
            "enabled": bool(policy.get("global_budget_enabled")),
            "usage_date": usage_date.isoformat(),
            "limit_tokens": global_limit,
            "used_tokens": global_used,
            "reserved_tokens": global_reserved,
            "remaining_tokens": global_remaining,
            "state": "exhausted" if policy.get("global_budget_enabled") and global_remaining <= 0 else "available",
        },
        "platform_available": reason_code is None,
        "reason_code": reason_code,
        "byok_guidance": dict(policy.get("byok_guidance") or {}),
        "provider_presets": policy.get("allowed_byok_providers") or [],
        "allow_user_byok": bool(policy.get("allow_user_byok")),
        "byok_transport_mode": policy.get("byok_transport_mode"),
        "metered_modules": policy.get("metered_modules") or [],
    }


def public_policy_payload(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "access_mode": policy.get("access_mode"),
        "daily_token_limit": int(policy.get("daily_token_limit") or 0),
        "lifetime_token_grant": int(policy.get("lifetime_token_grant") or 0),
        "global_daily_token_limit": int(policy.get("global_daily_token_limit") or 0),
        "global_budget_enabled": bool(policy.get("global_budget_enabled")),
        "emergency_byok_only": bool(policy.get("emergency_byok_only")),
        "quota_reset_timezone": policy.get("quota_reset_timezone"),
        "allow_anonymous_ai_usage": bool(policy.get("allow_anonymous_ai_usage")),
        "allow_user_byok": bool(policy.get("allow_user_byok")),
        "byok_transport_mode": policy.get("byok_transport_mode"),
        "byok_guidance": dict(policy.get("byok_guidance") or {}),
        "allowed_byok_providers": policy.get("allowed_byok_providers") or [],
        "metered_modules": policy.get("metered_modules") or [],
    }


async def admin_usage_summary(db: AsyncSession) -> dict[str, Any]:
    policy = await get_ai_usage_policy_config()
    usage_date = usage_date_for_policy(policy)
    global_budget = (
        await db.execute(
            select(AIGlobalDailyBudget).where(AIGlobalDailyBudget.usage_date == usage_date)
        )
    ).scalar_one_or_none()
    global_limit = int(policy.get("global_daily_token_limit") or 0)
    global_used = global_budget.consumed_tokens if global_budget else 0
    global_reserved = global_budget.reserved_tokens if global_budget else 0
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
        "global_budget": {
            "enabled": bool(policy.get("global_budget_enabled")),
            "emergency_byok_only": bool(policy.get("emergency_byok_only")),
            "usage_date": usage_date.isoformat(),
            "limit_tokens": global_limit,
            "used_tokens": global_used,
            "reserved_tokens": global_reserved,
            "remaining_tokens": max(0, global_limit - global_used - global_reserved),
            "state": (
                "byok_only"
                if policy.get("emergency_byok_only")
                else (
                    "exhausted"
                    if policy.get("global_budget_enabled") and global_limit - global_used - global_reserved <= 0
                    else "available"
                )
            ),
        },
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


def _wallet_payload(
    wallet: AICreditWallet,
    *,
    principal_id: uuid.UUID,
    linked_user_count: int,
    linked_device_count: int,
) -> dict[str, Any]:
    return {
        "principal_id": str(principal_id),
        "granted_tokens": wallet.granted_tokens,
        "consumed_tokens": wallet.consumed_tokens,
        "reserved_tokens": wallet.reserved_tokens,
        "remaining_tokens": max(
            0,
            wallet.granted_tokens - wallet.consumed_tokens - wallet.reserved_tokens,
        ),
        "request_count": wallet.request_count,
        "frozen": wallet.frozen,
        "linked_user_count": linked_user_count,
        "linked_device_count": linked_device_count,
        "updated_at": wallet.updated_at.isoformat() if wallet.updated_at else None,
    }


async def admin_user_quota_payload(db: AsyncSession, user: User) -> dict[str, Any]:
    policy = await get_ai_usage_policy_config()
    principal_id, wallet = await get_or_create_quota_principal(
        db,
        user_id=user.id,
        device_hash=None,
        user_agent_hash=None,
        default_grant=max(0, int(policy.get("lifetime_token_grant") or 0)),
    )
    linked_user_count = int(
        await db.scalar(
            select(func.count(AIPrincipalUser.id)).where(AIPrincipalUser.principal_id == principal_id)
        ) or 0
    )
    linked_device_count = int(
        await db.scalar(
            select(func.count(AIPrincipalDevice.id)).where(AIPrincipalDevice.principal_id == principal_id)
        ) or 0
    )
    return {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
        **_wallet_payload(
            wallet,
            principal_id=principal_id,
            linked_user_count=linked_user_count,
            linked_device_count=linked_device_count,
        ),
    }


async def update_admin_user_quota(
    db: AsyncSession,
    *,
    user: User,
    admin: User,
    granted_tokens: int | None,
    consumed_tokens: int | None,
    frozen: bool | None,
    reason: str,
) -> dict[str, Any]:
    policy = await get_ai_usage_policy_config()
    principal_id, wallet = await get_or_create_quota_principal(
        db,
        user_id=user.id,
        device_hash=None,
        user_agent_hash=None,
        default_grant=max(0, int(policy.get("lifetime_token_grant") or 0)),
    )
    before_state = {
        "granted_tokens": wallet.granted_tokens,
        "consumed_tokens": wallet.consumed_tokens,
        "reserved_tokens": wallet.reserved_tokens,
        "frozen": wallet.frozen,
    }
    if granted_tokens is not None:
        wallet.granted_tokens = max(0, int(granted_tokens))
    if consumed_tokens is not None:
        wallet.consumed_tokens = max(0, int(consumed_tokens))
    if frozen is not None:
        wallet.frozen = bool(frozen)
    wallet.version += 1
    wallet.updated_at = datetime.utcnow()
    after_state = {
        "granted_tokens": wallet.granted_tokens,
        "consumed_tokens": wallet.consumed_tokens,
        "reserved_tokens": wallet.reserved_tokens,
        "frozen": wallet.frozen,
    }
    available_token_delta = (
        wallet.granted_tokens
        - int(before_state["granted_tokens"])
        - (wallet.consumed_tokens - int(before_state["consumed_tokens"]))
    )
    db.add(
        AIQuotaAuditLog(
            actor_user_id=admin.id,
            target_user_id=user.id,
            principal_id=principal_id,
            action="admin_wallet_update",
            delta_tokens=available_token_delta,
            before_state=before_state,
            after_state=after_state,
            reason=reason.strip(),
        )
    )
    await db.commit()
    return await admin_user_quota_payload(db, user)


def normalize_policy_payload(payload: dict[str, Any], current_policy: dict[str, Any]) -> dict[str, Any]:
    merged = {**current_policy, **(payload or {})}
    if "byok_guidance" in payload:
        merged["byok_guidance"] = {
            **(current_policy.get("byok_guidance") or {}),
            **(payload.get("byok_guidance") or {}),
        }
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
    before_policy = setting.value if setting and isinstance(setting.value, dict) else {}
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
    db.add(
        AIQuotaAuditLog(
            actor_user_id=admin.id,
            action="admin_policy_update",
            delta_tokens=(
                int(policy.get("lifetime_token_grant") or 0)
                - int(before_policy.get("lifetime_token_grant") or 0)
            ),
            before_state=before_policy,
            after_state=policy,
            reason="后台更新 AI 额度与 BYOK 策略",
        )
    )
