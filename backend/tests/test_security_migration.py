import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "013_security_invariants.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("security_invariants_013", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SecurityMigrationTests(unittest.TestCase):
    def test_upgrade_repairs_sensitive_settings_marked_public(self):
        migration = _load_migration()
        statements = []

        with (
            patch.object(migration.op, "add_column"),
            patch.object(migration.op, "execute", side_effect=statements.append),
        ):
            migration.upgrade()

        self.assertEqual(len(statements), 1)
        sql = str(statements[0]).lower()
        self.assertIn("set is_public = false", sql)
        self.assertIn("api_keys", sql)
        self.assertIn("_private", sql)


if __name__ == "__main__":
    unittest.main()
