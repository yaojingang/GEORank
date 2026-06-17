"""增加专家频道画像表

Revision ID: 009_add_expert_profiles
Revises: 008_add_keyword_packs
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "009_add_expert_profiles"
down_revision = "008_add_keyword_packs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expert_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("avatar_initials", sa.String(length=12), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="strategy"),
        sa.Column("specialty_label", sa.String(length=50), nullable=False, server_default="策略"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("expertise", postgresql.JSONB(), nullable=True),
        sa.Column("consultation", sa.Text(), nullable=False, server_default=""),
        sa.Column("keywords", postgresql.JSONB(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_expert_profiles_display_name", "expert_profiles", ["display_name"])
    op.create_index("ix_expert_profiles_category", "expert_profiles", ["category"])
    op.create_index("ix_expert_profiles_sort_order", "expert_profiles", ["sort_order"])
    op.create_index("ix_expert_profiles_is_featured", "expert_profiles", ["is_featured"])
    op.create_index("ix_expert_profiles_is_published", "expert_profiles", ["is_published"])
    op.create_index("ix_expert_profiles_created_by", "expert_profiles", ["created_by"])
    op.create_index("ix_expert_profiles_created_at", "expert_profiles", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_expert_profiles_created_at", table_name="expert_profiles")
    op.drop_index("ix_expert_profiles_created_by", table_name="expert_profiles")
    op.drop_index("ix_expert_profiles_is_published", table_name="expert_profiles")
    op.drop_index("ix_expert_profiles_is_featured", table_name="expert_profiles")
    op.drop_index("ix_expert_profiles_sort_order", table_name="expert_profiles")
    op.drop_index("ix_expert_profiles_category", table_name="expert_profiles")
    op.drop_index("ix_expert_profiles_display_name", table_name="expert_profiles")
    op.drop_table("expert_profiles")
