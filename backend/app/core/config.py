"""
全局配置 — 从环境变量 / .env 文件加载
"""
from pydantic_settings import BaseSettings
from typing import List
import hashlib
import base64


class Settings(BaseSettings):
    # ----- 基础 -----
    APP_NAME: str = "GEOrank"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production"
    SETTINGS_ENCRYPTION_KEY: str = ""

    # ----- CORS -----
    CORS_ORIGINS: List[str] = ["http://localhost:8899", "http://localhost:80", "http://localhost", "http://127.0.0.1"]

    # ----- PostgreSQL -----
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "georank"
    POSTGRES_USER: str = "georank"
    POSTGRES_PASSWORD: str = "change-me-postgres-password"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ----- Redis -----
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def CELERY_BROKER_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    # ----- Qdrant 向量数据库 -----
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "companies"

    # ----- Neo4j 知识图谱 -----
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "change-me-neo4j-password"

    # ----- MinIO 对象存储 -----
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "change-me-minio-access-key"
    MINIO_SECRET_KEY: str = "change-me-minio-secret-key"
    MINIO_BUCKET: str = "georank-assets"

    # ----- AI / LLM -----
    # 主 LLM 服务（兼容 OpenAI API 格式的服务均可）
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_FALLBACK_MODEL: str = ""

    CODEX_API_KEY: str = ""
    CODEX_BASE_URL: str = ""
    CODEX_MODEL: str = "gpt-5.3-codex-spark"

    # 向后兼容旧字段（ai_client 内部使用 LLM_* 前缀）
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Embedding 配置，需单独配置兼容 OpenAI 格式的 Embedding Key，或留空使用降级逻辑。
    EMBEDDING_API_KEY: str = ""         # 专用于 Embedding 的 API Key（如有直连 OpenAI）
    EMBEDDING_BASE_URL: str = ""        # 留空则使用 api.openai.com
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    @property
    def effective_llm_key(self) -> str:
        """优先使用 LLM_API_KEY，否则回退到 OPENAI_API_KEY"""
        return self.LLM_API_KEY or self.OPENAI_API_KEY

    @property
    def effective_embedding_key(self) -> str:
        """Embedding 仅使用专用 Key，避免误用不支持向量的 LLM 网关。"""
        return self.EMBEDDING_API_KEY or self.OPENAI_API_KEY

    # ----- JWT -----
    JWT_SECRET: str = "change-me-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60  # 1小时；生产环境建议 15-30 分钟
    JWT_PERSIST_DAYS: int = 365

    @property
    def settings_encryption_key_bytes(self) -> bytes:
        """
        生成 32 字节设置加密密钥。
        未单独配置时回退到 SECRET_KEY，保证本地开发可用。
        """
        material = (self.SETTINGS_ENCRYPTION_KEY or self.SECRET_KEY).encode("utf-8")
        return hashlib.sha256(material).digest()

    @property
    def settings_encryption_key_b64(self) -> str:
        return base64.urlsafe_b64encode(self.settings_encryption_key_bytes).decode("ascii")

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
