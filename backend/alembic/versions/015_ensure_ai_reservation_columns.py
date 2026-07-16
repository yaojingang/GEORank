"""补齐 AI 任务 reservation 关联列

Revision ID: 015_ensure_ai_reservation
Revises: 014_add_ai_quota_v2
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "015_ensure_ai_reservation"
down_revision = "014_add_ai_quota_v2"
branch_labels = None
depends_on = None


def _ensure_column_and_index(table_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_name = "ai_reservation_id"
    index_name = f"ix_{table_name}_{column_name}"

    if column_name not in {item["name"] for item in inspector.get_columns(table_name)}:
        op.add_column(
            table_name,
            sa.Column(column_name, postgresql.UUID(as_uuid=True), nullable=True),
        )

    inspector = sa.inspect(bind)
    if index_name not in {item["name"] for item in inspector.get_indexes(table_name)}:
        op.create_index(index_name, table_name, [column_name])


def upgrade() -> None:
    _ensure_column_and_index("companies")
    _ensure_column_and_index("diagnostic_reports")


def downgrade() -> None:
    # 014 已声明并持有这些列；回退 015 时保留 014 对应的数据库契约。
    pass
