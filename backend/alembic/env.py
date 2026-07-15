"""
Alembic 环境配置 — 支持异步 SQLAlchemy
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Alembic Config 对象
config = context.config

# 设置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入所有模型，让 Base.metadata 感知到所有表
from app.core.database import Base
import app.models  # noqa: F401

target_metadata = Base.metadata


def get_url():
    from app.core.config import settings
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """离线迁移（无需真实 DB 连接，生成 SQL 文件）"""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """在线迁移（连接真实 DB 执行）"""
    connectable = create_async_engine(get_url(), poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
