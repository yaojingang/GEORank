import unittest

from app.core.config import Settings


class ConfigSecurityTests(unittest.TestCase):
    def test_production_rejects_development_secrets_and_origin(self):
        config = Settings(_env_file=None, DEBUG=False)

        with self.assertRaisesRegex(RuntimeError, "生产环境安全配置无效"):
            config.validate_production_security()

    def test_production_accepts_independent_secrets_and_https_origin(self):
        config = Settings(
            _env_file=None,
            DEBUG=False,
            SECRET_KEY="s" * 40,
            JWT_SECRET="j" * 40,
            SETTINGS_ENCRYPTION_KEY="e" * 40,
            PUBLIC_BASE_URL="https://app.georank.com",
        )

        config.validate_production_security()

    def test_debug_mode_keeps_local_development_bootable(self):
        config = Settings(_env_file=None, DEBUG=True)

        config.validate_production_security()


if __name__ == "__main__":
    unittest.main()
