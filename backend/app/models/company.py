"""
公司数据模型 — 核心实体
"""
import secrets
import string
import uuid
from datetime import datetime, date
from sqlalchemy import String, Text, Integer, Float, DateTime, Date, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.core.database import Base
from app.models.enum_types import pg_enum

COMPANY_PATH_KEY_ALPHABET = string.ascii_lowercase
COMPANY_PATH_KEY_LENGTH = 5


def generate_company_path_key_value() -> str:
    return "".join(
        secrets.choice(COMPANY_PATH_KEY_ALPHABET)
        for _ in range(COMPANY_PATH_KEY_LENGTH)
    )


class PipelineStatus(str, enum.Enum):
    """入库流水线状态"""
    PENDING = "pending"           # 等待处理
    CRAWLING = "crawling"         # 爬取中
    CLEANING = "cleaning"         # 数据清洗中
    GRAPH_BUILDING = "graph_building"  # 知识图谱构建中
    VECTORIZING = "vectorizing"   # 向量化中
    COMPLETED = "completed"       # 完成
    FAILED = "failed"             # 失败


class PublishStatus(str, enum.Enum):
    """发布状态"""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 基础信息
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    path_key: Mapped[str] = mapped_column(
        String(COMPANY_PATH_KEY_LENGTH),
        unique=True,
        index=True,
        default=generate_company_path_key_value,
    )
    logo_url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    short_description: Mapped[str | None] = mapped_column(String(300))

    # 分类与标签
    category: Mapped[str | None] = mapped_column(String(50))
    tags: Mapped[dict | None] = mapped_column(JSONB, default=list)

    # GEO 认证（对应前端「GEO 认证合作伙伴」特殊徽章）
    is_geo_certified: Mapped[bool] = mapped_column(Boolean, default=False)

    # AI 提取的结构化信息
    founded_date: Mapped[date | None] = mapped_column(Date)          # 精确到年月，替代原 founded_year
    headquarters: Mapped[str | None] = mapped_column(String(200))
    employee_count: Mapped[str | None] = mapped_column(String(50))
    funding_stage: Mapped[str | None] = mapped_column(String(50))
    tech_level: Mapped[str | None] = mapped_column(String(50))       # GEO 技术等级，如 "L5 级语义映射"
    tech_stack: Mapped[dict | None] = mapped_column(JSONB, default=list)
    team_members: Mapped[dict | None] = mapped_column(JSONB, default=list)

    # GEO 评分
    geo_score: Mapped[float | None] = mapped_column(Float)
    geo_details: Mapped[dict | None] = mapped_column(JSONB)  # 各维度评分明细

    # 流水线状态
    pipeline_status: Mapped[PipelineStatus] = mapped_column(
        pg_enum(PipelineStatus, "pipelinestatus"), default=PipelineStatus.PENDING, index=True
    )
    pipeline_error: Mapped[str | None] = mapped_column(Text)

    # 发布状态
    publish_status: Mapped[PublishStatus] = mapped_column(
        pg_enum(PublishStatus, "publishstatus"), default=PublishStatus.DRAFT, index=True
    )

    # 原始爬取数据引用
    raw_html_key: Mapped[str | None] = mapped_column(String(500))    # MinIO key
    about_html_key: Mapped[str | None] = mapped_column(String(500))  # MinIO key
    crawl_candidates: Mapped[list | None] = mapped_column(JSONB, default=list)
    crawl_pages: Mapped[list | None] = mapped_column(JSONB, default=list)
    screenshots: Mapped[dict | None] = mapped_column(JSONB, default=list)

    # 投票
    upvotes: Mapped[int] = mapped_column(Integer, default=0)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
