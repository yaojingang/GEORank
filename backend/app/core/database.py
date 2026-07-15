"""
数据库连接与 Session 管理
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,        # 高峰期最多额外开 10 个连接
    pool_recycle=3600,      # 1 小时回收连接，防止 DB 端超时断开
    pool_pre_ping=True,     # 使用前探活，自动丢弃失效连接
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI 依赖注入 — 获取数据库 Session"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
