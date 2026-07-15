"""增加 AI 用量和每日额度表

Revision ID: 010_add_ai_usage_tracking
Revises: 009_add_expert_profiles
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "010_add_ai_usage_tracking"
down_revision = "009_add_expert_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.Column("provider_source", sa.String(length=30), nullable=False, server_default="platform"),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="success"),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ai_usage_events_user_id", "ai_usage_events", ["user_id"])
    op.create_index("ix_ai_usage_events_module", "ai_usage_events", ["module"])
    op.create_index("ix_ai_usage_events_provider_source", "ai_usage_events", ["provider_source"])
    op.create_index("ix_ai_usage_events_total_tokens", "ai_usage_events", ["total_tokens"])
    op.create_index("ix_ai_usage_events_request_id", "ai_usage_events", ["request_id"])
    op.create_index("ix_ai_usage_events_status", "ai_usage_events", ["status"])
    op.create_index("ix_ai_usage_events_created_at", "ai_usage_events", ["created_at"])

    op.create_table(
        "user_daily_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "usage_date", name="uq_user_daily_usage_date"),
    )
    op.create_index("ix_user_daily_usage_user_id", "user_daily_usage", ["user_id"])
    op.create_index("ix_user_daily_usage_usage_date", "user_daily_usage", ["usage_date"])


def downgrade() -> None:
    op.drop_index("ix_user_daily_usage_usage_date", table_name="user_daily_usage")
    op.drop_index("ix_user_daily_usage_user_id", table_name="user_daily_usage")
    op.drop_table("user_daily_usage")

    op.drop_index("ix_ai_usage_events_created_at", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_status", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_request_id", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_total_tokens", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_provider_source", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_module", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_user_id", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
