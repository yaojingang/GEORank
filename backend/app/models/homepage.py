"""
自定义首页版本模型。

上传的首页资产保存在 runtime/homepages，数据库只保存版本元数据和审计信息。
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enum_types import pg_enum


class HomepageSourceType(str, enum.Enum):
    ZIP_PACKAGE = "zip_package"
    SINGLE_HTML = "single_html"


class HomepageReleaseStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    FAILED = "failed"


class HomepageRelease(Base):
    __tablename__ = "homepage_releases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[HomepageSourceType] = mapped_column(
        pg_enum(HomepageSourceType, "homepagesourcetype"),
        nullable=False,
    )
    status: Mapped[HomepageReleaseStatus] = mapped_column(
        pg_enum(HomepageReleaseStatus, "homepagereleasestatus"),
        default=HomepageReleaseStatus.DRAFT,
        index=True,
    )
    entry_path: Mapped[str] = mapped_column(String(300), default="index.html")
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    compressed_size: Mapped[int] = mapped_column(Integer, default=0)
    extracted_size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    release_manifest: Mapped[dict | None] = mapped_column("manifest", JSONB, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
