import asyncio
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.admin import (  # noqa: E402
    _ensure_enabled_llm_provider_has_key,
    _llm_chat_completions_url,
    _merge_llm_provider_keys_from_config,
    _normalize_admin_llm_provider,
    _validate_llm_provider_target,
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
                "persisted_base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "api_key": "••••••••••••••••",
                "enabled": True,
                "priority": 1,
            },
            existing_keys,
            0,
        )

        self.assertEqual(provider["api_key"], "sk-existing")

    def test_masked_provider_key_is_not_reused_after_endpoint_change(self):
        provider = _normalize_admin_llm_provider(
            {
                "id": "primary",
                "name": "主线路",
                "base_url": "https://attacker.example",
                "persisted_base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "api_key": "••••••••••••••••",
                "enabled": True,
                "priority": 1,
            },
            {"primary": "sk-existing"},
            0,
        )

        self.assertEqual(provider["api_key"], "")

    def test_provider_test_url_rejects_private_and_insecure_targets(self):
        for url in ("http://api.example.com/v1", "https://127.0.0.1/v1", "https://localhost/v1"):
            with self.subTest(url=url), self.assertRaises(HTTPException):
                _llm_chat_completions_url(url)

    def test_provider_target_rejects_dns_that_resolves_to_private_address(self):
        private_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]
        with patch(
            "app.services.provider_url_security.socket.getaddrinfo",
            return_value=private_resolution,
        ):
            with self.assertRaises(HTTPException):
                asyncio.run(_validate_llm_provider_target("https://provider.example/v1"))

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
