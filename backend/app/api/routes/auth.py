"""
认证 API — 注册 / 登录 / 获取当前用户
"""
from datetime import datetime, timedelta, timezone
import re
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from jose import jwt
import bcrypt
from sqlalchemy import or_, select

from app.core.config import settings
from app.core.deps import DbSession, CurrentUser
from app.models.user import User, UserRole
from app.schemas.user import (
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    UserProfileUpdateRequest,
)

router = APIRouter()


# ---------- 工具函数 ----------

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _normalize_phone(phone: str | None) -> str:
    digits = re.sub(r"\D+", "", str(phone or ""))
    if digits.startswith("86") and len(digits) == 13:
        digits = digits[2:]
    if not re.fullmatch(r"1\d{10}", digits):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="请输入有效的手机号",
        )
    return digits


async def _username_exists(db: DbSession, username: str) -> bool:
    result = await db.execute(select(User.id).where(User.username == username))
    return result.scalar_one_or_none() is not None


async def _build_phone_identity(db: DbSession, phone: str) -> tuple[str, str]:
    base_username = f"u_{phone}"
    username = base_username
    suffix = 1
    while await _username_exists(db, username):
        username = f"{base_username}_{suffix}"
        suffix += 1
    email = f"phone_{phone}@phone.local"
    return username, email


def _create_access_token(user_id: str, persistent: bool = False) -> str:
    expire = datetime.now(timezone.utc) + (
        timedelta(days=settings.JWT_PERSIST_DAYS)
        if persistent
        else timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


# ---------- 路由 ----------

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: DbSession):
    """用户注册 — 创建账号并返回 JWT"""
    phone = _normalize_phone(data.phone) if data.phone else None
    username = data.username
    email = str(data.email) if data.email else None

    if phone:
        result = await db.execute(select(User).where(User.phone == phone))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已被注册")
        if not username or not email:
            username, email = await _build_phone_identity(db, phone)

    if not username or not email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="注册信息不完整")

    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已被注册")

    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已被占用")

    user = User(
        email=email,
        username=username,
        phone=phone,
        hashed_password=_hash_password(data.password),
        role=UserRole.USER,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = _create_access_token(str(user.id), persistent=data.remember_me)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, data: LoginRequest, db: DbSession):
    """用户登录 — 支持用户名或邮箱登录（全局限速 200次/分钟/IP 兜底）"""
    identifier = data.phone or data.account or data.username or ""
    filters = []
    if data.phone:
        normalized_phone = _normalize_phone(data.phone)
        filters.append(User.phone == normalized_phone)
    else:
        filters.extend([User.username == identifier, User.email == identifier])

    result = await db.execute(select(User).where(or_(*filters)))
    user = result.scalar_one_or_none()

    if not user or not _verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码不正确",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")

    token = _create_access_token(str(user.id), persistent=data.remember_me)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: CurrentUser):
    """获取当前登录用户信息"""
    return UserOut(
        id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        phone=current_user.phone,
        role=current_user.role.value if hasattr(current_user.role, "value") else current_user.role,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
    )


@router.put("/me", response_model=UserOut)
async def update_me(data: UserProfileUpdateRequest, current_user: CurrentUser, db: DbSession):
    """修改当前登录用户资料"""
    updates = data.model_dump(exclude_unset=True)

    if "username" in updates and updates["username"] is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="用户名不能为空")
    if "email" in updates and updates["email"] is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="邮箱不能为空")

    next_username = updates["username"].strip() if "username" in updates and updates["username"] else None
    if "username" in updates and not next_username:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="用户名不能为空")
    if next_username and next_username != current_user.username:
        result = await db.execute(
            select(User.id).where(User.username == next_username, User.id != current_user.id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已被占用")
        current_user.username = next_username

    next_email = str(updates["email"]).strip() if "email" in updates and updates["email"] else None
    if "email" in updates and not next_email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="邮箱不能为空")
    if next_email and next_email != current_user.email:
        result = await db.execute(
            select(User.id).where(User.email == next_email, User.id != current_user.id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已被注册")
        current_user.email = next_email

    if "phone" in updates:
        raw_phone = updates["phone"]
        next_phone = _normalize_phone(raw_phone) if raw_phone and str(raw_phone).strip() else None
        if next_phone != current_user.phone:
            if next_phone:
                result = await db.execute(
                    select(User.id).where(User.phone == next_phone, User.id != current_user.id)
                )
                if result.scalar_one_or_none():
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已被注册")
            current_user.phone = next_phone

    await db.commit()
    await db.refresh(current_user)
    return UserOut(
        id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        phone=current_user.phone,
        role=current_user.role.value if hasattr(current_user.role, "value") else current_user.role,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )


@router.put("/password")
async def change_password(data: PasswordChangeRequest, current_user: CurrentUser, db: DbSession):
    """修改当前登录用户密码"""
    if not _verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")
    if _verify_password(data.new_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码不能与当前密码相同")

    current_user.hashed_password = _hash_password(data.new_password)
    await db.commit()
    return {"message": "密码已更新"}
