"""
FastAPI 依赖注入 — 数据库 Session / JWT 认证 / 权限校验
"""
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, UserRole

# HTTP Bearer Token 提取器（optional=True 允许匿名访问接口可选认证）
bearer_scheme = HTTPBearer(auto_error=False)
bearer_required = HTTPBearer(auto_error=True)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_user_from_token(
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> User | None:
    if not credentials:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    return result.scalar_one_or_none()


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User | None:
    """可选认证 — 未登录时返回 None"""
    return await _get_user_from_token(credentials, db)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_required)],
    db: DbSession,
) -> User:
    """必须认证 — 未登录返回 401"""
    user = await _get_user_from_token(credentials, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")
    return user


async def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """仅管理员可访问"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
AdminUser = Annotated[User, Depends(require_admin)]
