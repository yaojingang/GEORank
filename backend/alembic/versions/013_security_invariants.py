"""Enforce authentication and sensitive-setting invariants.

Revision ID: 013_security_invariants
Revises: 012_seed_expert_profiles
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "013_security_invariants"
down_revision = "012_seed_expert_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        sa.text(
            """
            UPDATE settings
            SET is_public = false
            WHERE is_public = true
              AND (
                lower(coalesce(category, '')) = 'api_keys'
                OR lower(key) IN (
                  'openai_api_key',
                  'llm_api_key',
                  'llm_provider_keys',
                  'embedding_api_key',
                  'codex_api_key',
                  'google_search_api_key'
                )
                OR lower(key) LIKE '%\\_api\\_key' ESCAPE '\\'
                OR lower(key) LIKE '%\\_secret' ESCAPE '\\'
                OR lower(key) LIKE '%\\_token' ESCAPE '\\'
                OR lower(key) LIKE '%\\_password' ESCAPE '\\'
                OR lower(key) LIKE '%\\_private\\_key' ESCAPE '\\'
              )
            """
        )
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
