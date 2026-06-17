"""
系统配置表 — KV 结构，支持后台修改站点名称等平台配置
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    category: Mapped[str] = mapped_column(String(50), default="basic", index=True)
    # is_public=True 的配置可通过 GET /api/settings/public 公开读取（前端动态获取站点名称等）
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
