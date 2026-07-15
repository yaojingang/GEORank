"""
内容管理数据模型 — 教程与知识资产
"""
import secrets
import string
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.core.database import Base
from app.models.enum_types import pg_enum

CONTENT_PATH_KEY_ALPHABET = string.ascii_lowercase
CONTENT_PATH_KEY_LENGTH = 5


def generate_content_path_key_value() -> str:
    return "".join(
        secrets.choice(CONTENT_PATH_KEY_ALPHABET)
        for _ in range(CONTENT_PATH_KEY_LENGTH)
    )


class ContentType(str, enum.Enum):
    TUTORIAL = "tutorial"
    TEMPLATE = "template"
    WHITEPAPER = "whitepaper"
    ANNOUNCEMENT = "announcement"


class ContentStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Content(Base):
    __tablename__ = "contents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    path_key: Mapped[str] = mapped_column(String(CONTENT_PATH_KEY_LENGTH), unique=True, index=True, default=generate_content_path_key_value)
    content_type: Mapped[ContentType] = mapped_column(pg_enum(ContentType, "contenttype"), default=ContentType.TUTORIAL)
    status: Mapped[ContentStatus] = mapped_column(pg_enum(ContentStatus, "contentstatus"), default=ContentStatus.DRAFT, index=True)
    markdown_body: Mapped[str] = mapped_column(Text, default="")
    cover_image: Mapped[str | None] = mapped_column(String(500))
    reading_time_minutes: Mapped[int | None] = mapped_column(Integer)
    tags: Mapped[dict | None] = mapped_column(JSONB, default=list)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
