"""
专家频道数据模型
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExpertProfile(Base):
    __tablename__ = "expert_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    avatar_initials: Mapped[str | None] = mapped_column(String(12))
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="strategy", index=True)
    specialty_label: Mapped[str] = mapped_column(String(50), default="策略")
    summary: Mapped[str] = mapped_column(Text, default="")
    expertise: Mapped[list | None] = mapped_column(JSONB, default=list)
    consultation: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list | None] = mapped_column(JSONB, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, index=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
