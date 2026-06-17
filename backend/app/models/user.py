"""
用户数据模型
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.core.database import Base
from app.models.enum_types import pg_enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ENTERPRISE = "enterprise"
    USER = "user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "userrole"), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
