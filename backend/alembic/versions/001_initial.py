"""初始建表 — GEOrank 全部 8 张核心表

Revision ID: 001_initial
Revises:
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===== users =====
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(200), nullable=False),
        sa.Column("role", sa.Enum("admin", "enterprise", "user", name="userrole"), nullable=False, default="user"),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("is_verified", sa.Boolean, nullable=False, default=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ===== companies =====
    op.create_table(
        "companies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("url", sa.String(500), nullable=False, unique=True),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("description", sa.Text),
        sa.Column("short_description", sa.String(300)),
        sa.Column("category", sa.String(50)),
        sa.Column("tags", JSONB),
        sa.Column("is_geo_certified", sa.Boolean, default=False),
        sa.Column("founded_date", sa.Date),
        sa.Column("headquarters", sa.String(200)),
        sa.Column("employee_count", sa.String(50)),
        sa.Column("funding_stage", sa.String(50)),
        sa.Column("tech_level", sa.String(50)),
        sa.Column("tech_stack", JSONB),
        sa.Column("team_members", JSONB),
        sa.Column("geo_score", sa.Float),
        sa.Column("geo_details", JSONB),
        sa.Column("pipeline_status", sa.Enum(
            "pending", "crawling", "cleaning", "graph_building", "vectorizing", "completed", "failed",
            name="pipelinestatus"
        ), nullable=False, default="pending"),
        sa.Column("pipeline_error", sa.Text),
        sa.Column("publish_status", sa.Enum(
            "draft", "pending_review", "published", "archived",
            name="publishstatus"
        ), nullable=False, default="draft"),
        sa.Column("raw_html_key", sa.String(500)),
        sa.Column("about_html_key", sa.String(500)),
        sa.Column("screenshots", JSONB),
        sa.Column("upvotes", sa.Integer, default=0),
        sa.Column("submitted_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_companies_name", "companies", ["name"])
    op.create_index("ix_companies_pipeline_status", "companies", ["pipeline_status"])
    op.create_index("ix_companies_publish_status", "companies", ["publish_status"])

    # ===== contents =====
    op.create_table(
        "contents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("slug", sa.String(300), nullable=False, unique=True),
        sa.Column("content_type", sa.Enum(
            "tutorial", "template", "whitepaper", "announcement",
            name="contenttype"
        ), nullable=False, default="tutorial"),
        sa.Column("status", sa.Enum("draft", "published", "archived", name="contentstatus"), nullable=False, default="draft"),
        sa.Column("markdown_body", sa.Text, default=""),
        sa.Column("cover_image", sa.String(500)),
        sa.Column("reading_time_minutes", sa.Integer),
        sa.Column("tags", JSONB),
        sa.Column("view_count", sa.Integer, default=0),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_contents_slug", "contents", ["slug"])
    op.create_index("ix_contents_status", "contents", ["status"])

    # ===== diagnostic_reports =====
    op.create_table(
        "diagnostic_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL")),
        sa.Column("status", sa.Enum(
            "pending", "crawling", "analyzing", "completed", "failed",
            name="diagnosticstatus"
        ), nullable=False, default="pending"),
        sa.Column("overall_score", sa.Float),
        sa.Column("schema_analysis", JSONB),
        sa.Column("content_analysis", JSONB),
        sa.Column("meta_analysis", JSONB),
        sa.Column("citation_analysis", JSONB),
        sa.Column("recommendations", JSONB),
        sa.Column("raw_html_key", sa.String(500)),
        sa.Column("error_message", sa.Text),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_diagnostic_reports_url", "diagnostic_reports", ["url"])
    op.create_index("ix_diagnostic_reports_company_id", "diagnostic_reports", ["company_id"])

    # ===== conversations =====
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200)),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    # ===== messages =====
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Enum("user", "assistant", name="messagerole"), nullable=False),
        sa.Column("content", sa.Text, default=""),
        sa.Column("recommended_companies", JSONB),
        sa.Column("diagnostic_context_id", UUID(as_uuid=True), sa.ForeignKey("diagnostic_reports.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # ===== company_votes =====
    op.create_table(
        "company_votes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "user_id", name="uq_company_user_vote"),
    )
    op.create_index("ix_company_votes_company_id", "company_votes", ["company_id"])
    op.create_index("ix_company_votes_user_id", "company_votes", ["user_id"])

    # ===== settings =====
    op.create_table(
        "settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", JSONB, nullable=False),
        sa.Column("category", sa.String(50), default="basic"),
        sa.Column("is_public", sa.Boolean, default=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    op.create_index("ix_settings_category", "settings", ["category"])


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_table("company_votes")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("diagnostic_reports")
    op.drop_table("contents")
    op.drop_table("companies")
    op.drop_table("users")

    # 删除枚举类型
    for enum_name in ["userrole", "pipelinestatus", "publishstatus", "contenttype", "contentstatus", "diagnosticstatus", "messagerole"]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
