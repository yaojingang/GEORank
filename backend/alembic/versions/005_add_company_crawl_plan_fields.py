"""为公司增加爬取候选页与已选页面字段

Revision ID: 005_company_crawl_plan
Revises: 004_add_content_path_keys
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005_company_crawl_plan"
down_revision = "004_add_content_path_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column(
            "crawl_candidates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "crawl_pages",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("companies", "crawl_pages")
    op.drop_column("companies", "crawl_candidates")
