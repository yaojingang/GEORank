"""Allow public solution conversations without an owner

Revision ID: 002_conversations_user_nullable
Revises: 001_initial
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa

revision = "002_conversations_user_nullable"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("conversations", "user_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("conversations", "user_id", existing_type=sa.UUID(), nullable=False)
