"""
方案对话数据模型
conversations — 对话主表
messages     — 消息明细表
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.core.database import Base
from app.models.enum_types import pg_enum


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    # 取首条用户消息前 30 字作为标题
    title: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    role: Mapped[MessageRole] = mapped_column(pg_enum(MessageRole, "messagerole"), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")

    # AI 回复时写入推荐公司列表
    # 结构: [{"company_id": "...", "name": "...", "match_score": 0.96, "geo_score": 96, ...}]
    recommended_companies: Mapped[dict | None] = mapped_column(JSONB)

    # 携带的诊断报告上下文（从 diagnostic.html「发送到方案生成器」触发）
    diagnostic_context_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
