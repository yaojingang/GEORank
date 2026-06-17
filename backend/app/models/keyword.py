"""
拓词资产模型

keyword_packs 保存一次拓词任务的主记录，keyword_items 保存八维词项明细。
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KeywordPack(Base):
    __tablename__ = "keyword_packs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    seed_keywords: Mapped[list | None] = mapped_column(JSONB, default=list)
    source_type: Mapped[str] = mapped_column(String(50), default="manual", index=True)
    source_ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    profile: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    dimension_count: Mapped[int] = mapped_column(Integer, default=0)
    total_keywords: Mapped[int] = mapped_column(Integer, default=0)
    avg_recommendation_score: Mapped[float | None] = mapped_column(Float)
    avg_business_score: Mapped[float | None] = mapped_column(Float)
    high_recommendation_ratio: Mapped[float | None] = mapped_column(Float)
    high_business_ratio: Mapped[float | None] = mapped_column(Float)
    generation_mode: Mapped[str] = mapped_column(String(30), default="hybrid")
    generation_meta: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KeywordItem(Base):
    __tablename__ = "keyword_items"
    __table_args__ = (
        UniqueConstraint("pack_id", "dedupe_key", name="uq_keyword_pack_dedupe"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    dimension_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    dimension_name: Mapped[str | None] = mapped_column(String(100))
    dimension_icon: Mapped[str | None] = mapped_column(String(50))
    dimension_description: Mapped[str | None] = mapped_column(Text)
    keyword: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    recommendation_score: Mapped[int] = mapped_column(Integer, default=0)
    business_score: Mapped[int] = mapped_column(Integer, default=0)
    intent_label: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(50), default="generated")
    dedupe_key: Mapped[str] = mapped_column(String(500), nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
