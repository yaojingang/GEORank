"""
系统设置安全工具。

对敏感配置项做统一的识别、加密、解密和脱敏展示。
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

ENCRYPTION_MARKER = "__secure__"
ENCRYPTION_VERSION = 1
MASKED_VALUE = "••••••••••••••••"

SENSITIVE_SUFFIXES = (
    "_api_key",
    "_secret",
    "_token",
    "_password",
    "_private_key",
)

SENSITIVE_KEYS = {
    "openai_api_key",
    "llm_api_key",
    "llm_provider_keys",
    "embedding_api_key",
    "codex_api_key",
    "google_search_api_key",
}

SETTINGS_CATEGORY_HINTS = {
    "site_name": "basic",
    "site_description": "basic",
    "default_language": "basic",
    "timezone": "basic",
    "admin_entry_path": "security",
    "analytics_tracking_code": "analytics",
    "openai_api_key": "api_keys",
    "llm_api_key": "api_keys",
    "embedding_api_key": "api_keys",
    "google_search_api_key": "api_keys",
    "llm_base_url": "llm",
    "llm_model": "llm",
    "llm_fallback_model": "llm",
    "llm_providers": "llm",
    "llm_provider_keys": "api_keys",
    "embedding_base_url": "llm",
    "embedding_model": "llm",
    "embedding_dimensions": "llm",
    "codex_api_key": "api_keys",
    "codex_base_url": "llm",
    "codex_model": "llm",
    "geo_auto_score": "geo_engine",
    "geo_rescan_days": "geo_engine",
    "geo_score_public": "geo_engine",
    "geo_score_version": "geo_engine",
    "api_usage_policy": "ai_usage",
    "frontend_modules": "frontend",
    "homepage_runtime": "frontend",
    "navigation_menu": "frontend",
}


def is_sensitive_setting(key: str, category: str | None = None) -> bool:
    normalized = key.strip().lower()
    return (
        (category or "").strip().lower() == "api_keys"
        or normalized in SENSITIVE_KEYS
        or normalized.endswith(SENSITIVE_SUFFIXES)
    )


def infer_setting_category(key: str, current_category: str | None = None) -> str:
    hinted_category = SETTINGS_CATEGORY_HINTS.get(key)
    if current_category and current_category != "basic":
        return current_category
    if hinted_category:
        return hinted_category
    return current_category or "basic"


def is_encrypted_setting_value(value: Any) -> bool:
    return isinstance(value, dict) and value.get(ENCRYPTION_MARKER) is True


def mask_setting_value(value: Any, key: str, category: str | None = None) -> Any:
    if not is_sensitive_setting(key, category):
        return value
    if value in (None, "", [], {}):
        return ""
    return MASKED_VALUE


def encrypt_setting_value(value: Any, key: str, category: str | None = None) -> Any:
    if not is_sensitive_setting(key, category):
        return value
    if value in (None, "") or is_encrypted_setting_value(value):
        return value

    plaintext = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    nonce = os.urandom(12)
    ciphertext = AESGCM(settings.settings_encryption_key_bytes).encrypt(
        nonce, plaintext, key.encode("utf-8")
    )
    return {
        ENCRYPTION_MARKER: True,
        "v": ENCRYPTION_VERSION,
        "alg": "AES-256-GCM",
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt_setting_value(value: Any, key: str, category: str | None = None) -> Any:
    if not is_sensitive_setting(key, category):
        return value
    if not is_encrypted_setting_value(value):
        return value
    try:
        nonce = base64.b64decode(value["nonce"])
        ciphertext = base64.b64decode(value["ciphertext"])
        plaintext = AESGCM(settings.settings_encryption_key_bytes).decrypt(
            nonce, ciphertext, key.encode("utf-8")
        )
        return json.loads(plaintext.decode("utf-8"))
    except Exception:
        # 兼容历史坏数据或密钥切换场景，避免后台接口直接 500。
        return value
