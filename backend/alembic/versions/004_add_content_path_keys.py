"""为内容增加公开短码

Revision ID: 004_add_content_path_keys
Revises: 003_normalize_enum_labels
Create Date: 2026-04-09
"""

import secrets
import string

from alembic import op
import sqlalchemy as sa

revision = "004_add_content_path_keys"
down_revision = "003_normalize_enum_labels"
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
    op.add_column("contents", sa.Column("path_key", sa.String(length=PATH_KEY_LENGTH), nullable=True))
    op.create_index("ix_contents_path_key", "contents", ["path_key"], unique=True)

    bind = op.get_bind()
    existing = {
        row[0]
        for row in bind.execute(sa.text("SELECT path_key FROM contents WHERE path_key IS NOT NULL"))
    }
    rows = bind.execute(sa.text("SELECT id FROM contents WHERE path_key IS NULL")).fetchall()
    for row in rows:
        bind.execute(
            sa.text("UPDATE contents SET path_key = :path_key WHERE id = :content_id"),
            {
                "path_key": _generate_path_key(existing),
                "content_id": row[0],
            },
        )

    op.alter_column("contents", "path_key", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_contents_path_key", table_name="contents")
    op.drop_column("contents", "path_key")
