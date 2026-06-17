"""为用户增加手机号

Revision ID: 007_add_user_phone
Revises: 006_add_company_path_keys
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa

revision = "007_add_user_phone"
down_revision = "006_add_company_path_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=30), nullable=True))
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_column("users", "phone")
