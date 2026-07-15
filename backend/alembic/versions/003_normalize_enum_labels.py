"""规范化 PostgreSQL 枚举标签为小写值

Revision ID: 003_normalize_enum_labels
Revises: 002_conversations_user_nullable
Create Date: 2026-04-09
"""
from alembic import op

revision = "003_normalize_enum_labels"
down_revision = "002_conversations_user_nullable"
branch_labels = None
depends_on = None


ENUM_RENAMES = {
    "userrole": [
        ("ADMIN", "admin"),
        ("ENTERPRISE", "enterprise"),
        ("USER", "user"),
    ],
    "pipelinestatus": [
        ("PENDING", "pending"),
        ("CRAWLING", "crawling"),
        ("CLEANING", "cleaning"),
        ("GRAPH_BUILDING", "graph_building"),
        ("VECTORIZING", "vectorizing"),
        ("COMPLETED", "completed"),
        ("FAILED", "failed"),
    ],
    "publishstatus": [
        ("DRAFT", "draft"),
        ("PENDING_REVIEW", "pending_review"),
        ("PUBLISHED", "published"),
        ("ARCHIVED", "archived"),
    ],
    "contenttype": [
        ("TUTORIAL", "tutorial"),
        ("TEMPLATE", "template"),
        ("WHITEPAPER", "whitepaper"),
        ("ANNOUNCEMENT", "announcement"),
    ],
    "contentstatus": [
        ("DRAFT", "draft"),
        ("PUBLISHED", "published"),
        ("ARCHIVED", "archived"),
    ],
    "diagnosticstatus": [
        ("PENDING", "pending"),
        ("CRAWLING", "crawling"),
        ("ANALYZING", "analyzing"),
        ("COMPLETED", "completed"),
        ("FAILED", "failed"),
    ],
    "messagerole": [
        ("USER", "user"),
        ("ASSISTANT", "assistant"),
    ],
}


def _rename_enum_label(type_name: str, old_label: str, new_label: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                WHERE t.typname = '{type_name}' AND e.enumlabel = '{old_label}'
            ) THEN
                ALTER TYPE {type_name} RENAME VALUE '{old_label}' TO '{new_label}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    for type_name, renames in ENUM_RENAMES.items():
        for old_label, new_label in renames:
            _rename_enum_label(type_name, old_label, new_label)


def downgrade() -> None:
    for type_name, renames in ENUM_RENAMES.items():
        for old_label, new_label in reversed(renames):
            _rename_enum_label(type_name, new_label, old_label)
