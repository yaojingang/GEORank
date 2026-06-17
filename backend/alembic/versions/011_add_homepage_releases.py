"""增加自定义首页版本表

Revision ID: 011_add_homepage_releases
Revises: 010_add_ai_usage_tracking
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "011_add_homepage_releases"
down_revision = "010_add_ai_usage_tracking"
branch_labels = None
depends_on = None


homepage_source_type = postgresql.ENUM(
    "zip_package",
    "single_html",
    name="homepagesourcetype",
    create_type=False,
)
homepage_release_status = postgresql.ENUM(
    "draft",
    "active",
    "archived",
    "failed",
    name="homepagereleasestatus",
    create_type=False,
)


def upgrade() -> None:
    homepage_source_type.create(op.get_bind(), checkfirst=True)
    homepage_release_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "homepage_releases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source_type", homepage_source_type, nullable=False),
        sa.Column("status", homepage_release_status, nullable=False),
        sa.Column("entry_path", sa.String(length=300), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("compressed_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extracted_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("manifest", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_homepage_releases_status", "homepage_releases", ["status"])
    op.create_index("ix_homepage_releases_created_at", "homepage_releases", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_homepage_releases_created_at", table_name="homepage_releases")
    op.drop_index("ix_homepage_releases_status", table_name="homepage_releases")
    op.drop_table("homepage_releases")
    homepage_release_status.drop(op.get_bind(), checkfirst=True)
    homepage_source_type.drop(op.get_bind(), checkfirst=True)
