"""增加公司详情页访问量

Revision ID: 013_add_company_view_count
Revises: 012_seed_expert_profiles
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa


revision = "013_add_company_view_count"
down_revision = "012_seed_expert_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("view_count", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("companies", "view_count")
