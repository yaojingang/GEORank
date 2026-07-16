from datetime import datetime, timedelta, timezone
import uuid

from jose import JWTError, jwt

from app.core.config import settings


_PREVIEW_SCOPE = "company:preview"


def create_company_preview_token(company_id: uuid.UUID | str, *, ttl_minutes: int = 15) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=max(1, ttl_minutes))
    return jwt.encode(
        {"sub": str(company_id), "scope": _PREVIEW_SCOPE, "exp": expires_at},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_company_preview_token(token: str | None, company_id: uuid.UUID | str) -> bool:
    if not token:
        return False
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return False
    return bool(
        payload.get("scope") == _PREVIEW_SCOPE
        and payload.get("sub") == str(company_id)
    )
