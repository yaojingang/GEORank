import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.settings_security import (  # noqa: E402
    ENCRYPTION_MARKER,
    MASKED_VALUE,
    decrypt_setting_value,
    encrypt_setting_value,
    infer_setting_category,
    is_encrypted_setting_value,
    mask_setting_value,
)


class SettingsSecurityTests(unittest.TestCase):
    def test_encrypts_and_decrypts_sensitive_value(self):
        encrypted = encrypt_setting_value("sk-test-123456", "llm_api_key", "api_keys")

        self.assertTrue(is_encrypted_setting_value(encrypted))
        self.assertTrue(encrypted[ENCRYPTION_MARKER])
        self.assertNotIn("sk-test-123456", str(encrypted))
        self.assertEqual(
            decrypt_setting_value(encrypted, "llm_api_key", "api_keys"),
            "sk-test-123456",
        )

    def test_non_sensitive_value_remains_plain(self):
        value = "https://example-openai-compatible.test/v1"

        self.assertEqual(
            encrypt_setting_value(value, "llm_base_url", "llm"),
            value,
        )
        self.assertEqual(
            decrypt_setting_value(value, "llm_base_url", "llm"),
            value,
        )

    def test_sensitive_value_is_masked_for_admin_output(self):
        self.assertEqual(
            mask_setting_value("sk-test-123456", "llm_api_key", "api_keys"),
            MASKED_VALUE,
        )
        self.assertEqual(mask_setting_value("", "llm_api_key", "api_keys"), "")

    def test_infer_setting_category_uses_known_hints(self):
        self.assertEqual(infer_setting_category("llm_model"), "llm")
        self.assertEqual(infer_setting_category("embedding_dimensions"), "llm")
        self.assertEqual(infer_setting_category("google_search_api_key"), "api_keys")
        self.assertEqual(infer_setting_category("unknown_key"), "basic")


if __name__ == "__main__":
    unittest.main()
