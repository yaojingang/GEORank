import unittest
import os
from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.tasks.crawl import persist_crawl_html
from app.services.storage import StorageService


class _StorageProbe:
    def __init__(self, *, put_ok: bool, stored: bytes | None):
        self.put_ok = put_ok
        self.stored = stored

    def put(self, _key: str, _data: bytes, content_type: str = "text/html") -> bool:
        return self.put_ok

    def get(self, _key: str) -> bytes | None:
        return self.stored


class CompanyPipelineContractTests(unittest.TestCase):
    def test_storage_config_accepts_existing_minio_user_variable_names(self):
        with patch.dict(
            os.environ,
            {"MINIO_USER": "legacy-user", "MINIO_PASSWORD": "legacy-password"},
            clear=True,
        ):
            config = Settings(_env_file=None)

        self.assertEqual(config.MINIO_ACCESS_KEY, "legacy-user")
        self.assertEqual(config.MINIO_SECRET_KEY, "legacy-password")

    def test_crawl_html_requires_durable_storage(self):
        with self.assertRaisesRegex(RuntimeError, "对象存储"):
            persist_crawl_html(
                _StorageProbe(put_ok=False, stored=b"<html>fallback only</html>"),
                "companies/example/raw.html",
                "<html>example</html>",
            )

    def test_successful_object_write_clears_stale_memory_fallback(self):
        storage = StorageService()
        storage._fallback["companies/example/raw.html"] = b"stale"
        storage._client = MagicMock()

        self.assertTrue(
            storage.put("companies/example/raw.html", b"fresh")
        )
        self.assertNotIn("companies/example/raw.html", storage._fallback)


if __name__ == "__main__":
    unittest.main()
