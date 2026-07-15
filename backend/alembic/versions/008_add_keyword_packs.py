"""增加拓词词包资产表

Revision ID: 008_add_keyword_packs
Revises: 007_add_user_phone
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008_add_keyword_packs"
down_revision = "007_add_user_phone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "keyword_packs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("seed_keywords", postgresql.JSONB(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("source_ref_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="completed"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("profile", postgresql.JSONB(), nullable=True),
        sa.Column("dimension_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_keywords", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_recommendation_score", sa.Float(), nullable=True),
        sa.Column("avg_business_score", sa.Float(), nullable=True),
        sa.Column("high_recommendation_ratio", sa.Float(), nullable=True),
        sa.Column("high_business_ratio", sa.Float(), nullable=True),
        sa.Column("generation_mode", sa.String(length=30), nullable=False, server_default="hybrid"),
        sa.Column("generation_meta", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_keyword_packs_title", "keyword_packs", ["title"])
    op.create_index("ix_keyword_packs_source_type", "keyword_packs", ["source_type"])
    op.create_index("ix_keyword_packs_source_ref_id", "keyword_packs", ["source_ref_id"])
    op.create_index("ix_keyword_packs_status", "keyword_packs", ["status"])
    op.create_index("ix_keyword_packs_created_by", "keyword_packs", ["created_by"])
    op.create_index("ix_keyword_packs_created_at", "keyword_packs", ["created_at"])

    op.create_table(
        "keyword_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dimension_key", sa.String(length=50), nullable=False),
        sa.Column("dimension_name", sa.String(length=100), nullable=True),
        sa.Column("dimension_icon", sa.String(length=50), nullable=True),
        sa.Column("dimension_description", sa.Text(), nullable=True),
        sa.Column("keyword", sa.String(length=300), nullable=False),
        sa.Column("recommendation_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("business_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("intent_label", sa.String(length=50), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="generated"),
        sa.Column("dedupe_key", sa.String(length=500), nullable=False),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("pack_id", "dedupe_key", name="uq_keyword_pack_dedupe"),
    )
    op.create_index("ix_keyword_items_pack_id", "keyword_items", ["pack_id"])
    op.create_index("ix_keyword_items_dimension_key", "keyword_items", ["dimension_key"])
    op.create_index("ix_keyword_items_keyword", "keyword_items", ["keyword"])
    op.create_index("ix_keyword_items_created_at", "keyword_items", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_keyword_items_created_at", table_name="keyword_items")
    op.drop_index("ix_keyword_items_keyword", table_name="keyword_items")
    op.drop_index("ix_keyword_items_dimension_key", table_name="keyword_items")
    op.drop_index("ix_keyword_items_pack_id", table_name="keyword_items")
    op.drop_table("keyword_items")

    op.drop_index("ix_keyword_packs_created_at", table_name="keyword_packs")
    op.drop_index("ix_keyword_packs_created_by", table_name="keyword_packs")
    op.drop_index("ix_keyword_packs_status", table_name="keyword_packs")
    op.drop_index("ix_keyword_packs_source_ref_id", table_name="keyword_packs")
    op.drop_index("ix_keyword_packs_source_type", table_name="keyword_packs")
    op.drop_index("ix_keyword_packs_title", table_name="keyword_packs")
    op.drop_table("keyword_packs")
