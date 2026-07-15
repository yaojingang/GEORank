"""为公司增加公开短码

Revision ID: 006_add_company_path_keys
Revises: 005_company_crawl_plan
Create Date: 2026-04-10
"""

import secrets
import string

from alembic import op
import sqlalchemy as sa

revision = "006_add_company_path_keys"
down_revision = "005_company_crawl_plan"
branch_labels = None
depends_on = None

PATH_KEY_LENGTH = 5
PATH_KEY_ALPHABET = string.ascii_lowercase


def _generate_path_key(existing: set[str]) -> str:
    while True:
        candidate = "".join(
            secrets.choice(PATH_KEY_ALPHABET)
            for _ in range(PATH_KEY_LENGTH)
        )
        if candidate not in existing:
            existing.add(candidate)
            return candidate


def upgrade() -> None:
    op.add_column("companies", sa.Column("path_key", sa.String(length=PATH_KEY_LENGTH), nullable=True))
    op.create_index("ix_companies_path_key", "companies", ["path_key"], unique=True)

    bind = op.get_bind()
    existing = {
        row[0]
        for row in bind.execute(sa.text("SELECT path_key FROM companies WHERE path_key IS NOT NULL"))
    }
    rows = bind.execute(sa.text("SELECT id FROM companies WHERE path_key IS NULL")).fetchall()
    for row in rows:
        bind.execute(
            sa.text("UPDATE companies SET path_key = :path_key WHERE id = :company_id"),
            {
                "path_key": _generate_path_key(existing),
                "company_id": row[0],
            },
        )

    op.alter_column("companies", "path_key", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_companies_path_key", table_name="companies")
    op.drop_column("companies", "path_key")
