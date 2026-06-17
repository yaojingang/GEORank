"""
GEO 诊断报告数据模型
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.core.database import Base
from app.models.enum_types import pg_enum


class DiagnosticStatus(str, enum.Enum):
    PENDING = "pending"
    CRAWLING = "crawling"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class DiagnosticReport(Base):
    __tablename__ = "diagnostic_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)  # 从公司页发起时写入
    status: Mapped[DiagnosticStatus] = mapped_column(
        pg_enum(DiagnosticStatus, "diagnosticstatus"), default=DiagnosticStatus.PENDING
    )

    # 综合评分
    overall_score: Mapped[float | None] = mapped_column(Float)

    # 多维诊断结果 (JSONB)
    schema_analysis: Mapped[dict | None] = mapped_column(JSONB)     # Schema 标签检测
    content_analysis: Mapped[dict | None] = mapped_column(JSONB)    # 内容结构分析
    meta_analysis: Mapped[dict | None] = mapped_column(JSONB)       # Meta/OG 标签
    citation_analysis: Mapped[dict | None] = mapped_column(JSONB)   # 引用密度分析
    recommendations: Mapped[dict | None] = mapped_column(JSONB)     # 优化建议

    # 原始数据
    raw_html_key: Mapped[str | None] = mapped_column(String(500))   # MinIO key
    error_message: Mapped[str | None] = mapped_column(Text)

    # 关联
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
