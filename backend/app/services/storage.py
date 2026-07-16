"""
对象存储服务 — MinIO (S3 兼容)
负责原始 HTML、截图等大文件的存储与读取
懒初始化 — MinIO 不可用时降级为内存缓存
"""
import io
from typing import Optional
from app.core.config import settings


class StorageService:
    """MinIO 存储封装，懒初始化"""

    def __init__(self):
        self._client = None
        self._fallback: dict[str, bytes] = {}  # 内存降级缓存

    def _get_client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config
            self._client = boto3.client(
                "s3",
                endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                config=Config(connect_timeout=5, read_timeout=30),
            )
            # 确保 bucket 存在
            try:
                self._client.head_bucket(Bucket=settings.MINIO_BUCKET)
            except Exception:
                try:
                    self._client.create_bucket(Bucket=settings.MINIO_BUCKET)
                except Exception:
                    pass
        return self._client

    def put(self, key: str, data: bytes, content_type: str = "text/html") -> bool:
        """上传文件，失败时降级到内存缓存"""
        try:
            client = self._get_client()
            client.put_object(
                Bucket=settings.MINIO_BUCKET,
                Key=key,
                Body=io.BytesIO(data),
                ContentType=content_type,
            )
            self._fallback.pop(key, None)
            return True
        except Exception:
            self._fallback[key] = data
            return False

    def get(self, key: str) -> Optional[bytes]:
        """下载文件，先查内存缓存"""
        if key in self._fallback:
            return self._fallback[key]
        try:
            client = self._get_client()
            response = client.get_object(Bucket=settings.MINIO_BUCKET, Key=key)
            return response["Body"].read()
        except Exception:
            return None

    def delete(self, key: str):
        """删除文件"""
        self._fallback.pop(key, None)
        try:
            client = self._get_client()
            client.delete_object(Bucket=settings.MINIO_BUCKET, Key=key)
        except Exception:
            pass


# 全局单例
storage = StorageService()
