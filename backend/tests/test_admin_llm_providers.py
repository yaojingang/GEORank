import sys
import unittest
from pathlib import Path

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.admin import (  # noqa: E402
    _ensure_enabled_llm_provider_has_key,
    _merge_llm_provider_keys_from_config,
    _normalize_admin_llm_provider,
)


class AdminLLMProviderTests(unittest.TestCase):
    def test_masked_provider_key_can_be_recovered_from_legacy_runtime_config(self):
        existing_keys = _merge_llm_provider_keys_from_config(
            {},
            {
                "providers": [
                    {
                        "id": "primary",
                        "api_key": "sk-existing",
                    }
                ]
            },
        )

        provider = _normalize_admin_llm_provider(
            {
                "id": "primary",
                "name": "主线路",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "api_key": "••••••••••••••••",
                "enabled": True,
                "priority": 1,
            },
            existing_keys,
            0,
        )

        self.assertEqual(provider["api_key"], "sk-existing")

    def test_missing_enabled_provider_key_is_rejectable(self):
        provider = _normalize_admin_llm_provider(
            {
                "id": "primary",
                "name": "主线路",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "api_key": "",
                "enabled": True,
                "priority": 1,
            },
            {},
            0,
        )

        with self.assertRaises(HTTPException):
            _ensure_enabled_llm_provider_has_key(provider, 0)

    def test_disabled_provider_can_be_saved_without_key(self):
        provider = _normalize_admin_llm_provider(
            {
                "id": "standby",
                "name": "备用线路",
                "base_url": "https://api.example.com",
                "model": "model",
                "api_key": "",
                "enabled": False,
                "priority": 2,
            },
            {},
            1,
        )

        _ensure_enabled_llm_provider_has_key(provider, 1)


if __name__ == "__main__":
    unittest.main()
