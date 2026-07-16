"""增加终身额度、风险主体和全站每日预算

Revision ID: 014_add_ai_quota_v2
Revises: 013_add_company_view_count
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "014_add_ai_quota_v2"
down_revision = "013_add_company_view_count"
branch_labels = None
depends_on = None


_QUOTA_TABLES = {
    "ai_quota_principals",
    "ai_principal_users",
    "ai_principal_devices",
    "ai_credit_wallets",
    "ai_global_daily_budgets",
    "ai_token_reservations",
    "ai_quota_audit_logs",
}

_POLICY_UPDATE_SQL = """
    UPDATE settings
    SET value = value || '{
      "access_mode": "lifetime_quota_with_byok",
      "daily_token_limit": 0,
      "lifetime_token_grant": 10000,
      "global_daily_token_limit": 1000000,
      "global_budget_enabled": true,
      "emergency_byok_only": false,
      "allow_anonymous_ai_usage": false,
      "byok_guidance": {
        "provider": "deepseek",
        "title": "平台赠送额度已用完",
        "message": "绑定自己的 DeepSeek API Key 后，可以继续使用 AI 功能。",
        "cta_label": "配置 DeepSeek API",
        "official_url": "https://platform.deepseek.com/api_keys",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash"
      }
    }'::jsonb
    WHERE key = 'api_usage_policy'
"""

_POLICY_DOWNGRADE_SQL = """
    UPDATE settings
    SET value = value || '{
      "access_mode": "byok_required",
      "allow_anonymous_ai_usage": false,
      "allow_user_byok": true
    }'::jsonb
    WHERE key = 'api_usage_policy'
"""


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in existing_columns:
        op.add_column(table_name, column)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    existing_indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in existing_indexes:
        op.create_index(index_name, table_name, columns)


def _upgrade_precreated_schema() -> None:
    """补齐应用启动时由 create_all 提前创建表后遗漏的旧表字段。"""
    uuid_type = postgresql.UUID(as_uuid=True)
    for table_name, column_name, index_name in (
        ("ai_usage_events", "principal_id", "ix_ai_usage_events_principal_id"),
        ("ai_usage_events", "reservation_id", "ix_ai_usage_events_reservation_id"),
        ("companies", "ai_reservation_id", "ix_companies_ai_reservation_id"),
        ("diagnostic_reports", "ai_reservation_id", "ix_diagnostic_reports_ai_reservation_id"),
    ):
        _add_column_if_missing(
            table_name,
            sa.Column(column_name, uuid_type, nullable=True),
        )
        _create_index_if_missing(index_name, table_name, [column_name])


def upgrade() -> None:
    # 当前应用会在启动时执行 Base.metadata.create_all。新模型可能因此先建出
    # 配额表，而 Alembic 版本仍停留在上一版；此时只需补齐旧表新增列。
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if _QUOTA_TABLES.issubset(existing_tables):
        _upgrade_precreated_schema()
        op.execute(_POLICY_UPDATE_SQL)
        return

    op.create_table(
        "ai_quota_principals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("merged_into_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ai_quota_principals_status", "ai_quota_principals", ["status"])
    op.create_index("ix_ai_quota_principals_merged_into_id", "ai_quota_principals", ["merged_into_id"])

    op.create_table(
        "ai_principal_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_ai_principal_users_user_id"),
    )
    op.create_index("ix_ai_principal_users_principal_id", "ai_principal_users", ["principal_id"])
    op.create_index("ix_ai_principal_users_user_id", "ai_principal_users", ["user_id"])

    op.create_table(
        "ai_principal_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("device_hash", name="uq_ai_principal_devices_device_hash"),
    )
    op.create_index("ix_ai_principal_devices_principal_id", "ai_principal_devices", ["principal_id"])
    op.create_index("ix_ai_principal_devices_device_hash", "ai_principal_devices", ["device_hash"])
    op.create_index("ix_ai_principal_devices_last_seen_at", "ai_principal_devices", ["last_seen_at"])

    op.create_table(
        "ai_credit_wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_tokens", sa.Integer(), nullable=False, server_default="10000"),
        sa.Column("consumed_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("frozen", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("principal_id", name="uq_ai_credit_wallets_principal_id"),
    )
    op.create_index("ix_ai_credit_wallets_principal_id", "ai_credit_wallets", ["principal_id"])
    op.create_index("ix_ai_credit_wallets_frozen", "ai_credit_wallets", ["frozen"])

    op.create_table(
        "ai_global_daily_budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("limit_tokens", sa.Integer(), nullable=False, server_default="1000000"),
        sa.Column("consumed_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("usage_date", name="uq_ai_global_daily_budgets_date"),
    )
    op.create_index("ix_ai_global_daily_budgets_usage_date", "ai_global_daily_budgets", ["usage_date"])

    op.create_table(
        "ai_token_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("provider_source", sa.String(length=30), nullable=False, server_default="platform"),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("personal_reserved_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("global_reserved_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("charged_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_ai_token_reservations_idempotency_key"),
    )
    for column in ("idempotency_key", "principal_id", "user_id", "usage_date", "module", "status", "expires_at", "created_at"):
        op.create_index(f"ix_ai_token_reservations_{column}", "ai_token_reservations", [column])

    op.create_table(
        "ai_quota_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("delta_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("before_state", postgresql.JSONB(), nullable=True),
        sa.Column("after_state", postgresql.JSONB(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for column in ("actor_user_id", "target_user_id", "principal_id", "action", "created_at"):
        op.create_index(f"ix_ai_quota_audit_logs_{column}", "ai_quota_audit_logs", [column])

    op.add_column("ai_usage_events", sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("ai_usage_events", sa.Column("reservation_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_ai_usage_events_principal_id", "ai_usage_events", ["principal_id"])
    op.create_index("ix_ai_usage_events_reservation_id", "ai_usage_events", ["reservation_id"])

    op.add_column("companies", sa.Column("ai_reservation_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("diagnostic_reports", sa.Column("ai_reservation_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_companies_ai_reservation_id", "companies", ["ai_reservation_id"])
    op.create_index("ix_diagnostic_reports_ai_reservation_id", "diagnostic_reports", ["ai_reservation_id"])

    op.execute(_POLICY_UPDATE_SQL)


def downgrade() -> None:
    # 旧应用不认识 lifetime_quota_with_byok。先切到旧版支持的 BYOK 模式，
    # 避免旧版把未知模式回退为 platform_unlimited。
    op.execute(_POLICY_DOWNGRADE_SQL)
    op.drop_index("ix_diagnostic_reports_ai_reservation_id", table_name="diagnostic_reports")
    op.drop_index("ix_companies_ai_reservation_id", table_name="companies")
    op.drop_column("diagnostic_reports", "ai_reservation_id")
    op.drop_column("companies", "ai_reservation_id")
    op.drop_index("ix_ai_usage_events_reservation_id", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_principal_id", table_name="ai_usage_events")
    op.drop_column("ai_usage_events", "reservation_id")
    op.drop_column("ai_usage_events", "principal_id")
    op.drop_table("ai_quota_audit_logs")
    op.drop_table("ai_token_reservations")
    op.drop_table("ai_global_daily_budgets")
    op.drop_table("ai_credit_wallets")
    op.drop_table("ai_principal_devices")
    op.drop_table("ai_principal_users")
    op.drop_table("ai_quota_principals")
