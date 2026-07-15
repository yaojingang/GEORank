import os
import subprocess
import sys
import unittest

from app.core.config import Settings
from tests.database_safety import bootstrap_test_database_environment, resolve_test_database


class DatabaseSafetyTests(unittest.TestCase):
    def test_requires_an_explicit_test_database_setting(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "explicitly configured"):
            resolve_test_database(
                default_database_url="postgresql+asyncpg://user:pass@127.0.0.1/project_ci_42",
                configured_database_name=None,
            )

    def test_rejects_default_production_database(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "dedicated test database"):
            resolve_test_database(
                default_database_url="postgresql+asyncpg://user:pass@127.0.0.1/georank",
                configured_database_name="georank",
            )

    def test_rejects_production_shaped_postgres_db_without_explicit_url(self) -> None:
        for database_name in ("georank_prod", "customers_prod"):
            with self.subTest(database_name=database_name):
                with self.assertRaisesRegex(RuntimeError, "test or ci marker"):
                    resolve_test_database(
                        default_database_url=f"postgresql+asyncpg://user:pass@127.0.0.1/{database_name}",
                        configured_database_name=database_name,
                    )

    def test_accepts_explicit_postgres_db_without_a_hardcoded_name(self) -> None:
        database_url, database_name = resolve_test_database(
            default_database_url="postgresql+asyncpg://user:pass@127.0.0.1/project_ci_42",
            configured_database_name="project_ci_42",
        )

        self.assertEqual(database_name, "project_ci_42")
        self.assertEqual(database_url, "postgresql+asyncpg://user:pass@127.0.0.1:5432/project_ci_42")

    def test_explicit_test_database_url_takes_precedence_and_uses_asyncpg(self) -> None:
        database_url, database_name = resolve_test_database(
            default_database_url="postgresql+asyncpg://user:pass@127.0.0.1/georank",
            configured_database_name=None,
            explicit_test_database_url="postgresql://ci:secret@db.internal/isolated_ci",
        )

        self.assertEqual(database_name, "isolated_ci")
        self.assertEqual(database_url, "postgresql+asyncpg://ci:secret@db.internal:5432/isolated_ci")

    def test_rejects_production_shaped_explicit_test_database_url(self) -> None:
        for database_name in ("customers_prod", "georank_production"):
            with self.subTest(database_name=database_name):
                with self.assertRaisesRegex(RuntimeError, "test or ci marker"):
                    resolve_test_database(
                        default_database_url="postgresql+asyncpg://user:pass@127.0.0.1/georank",
                        configured_database_name=None,
                        explicit_test_database_url=(
                            f"postgresql://ci:secret@db.internal/{database_name}"
                        ),
                    )

    def test_general_settings_database_url_ignores_test_database_url(self) -> None:
        configured = Settings(
            POSTGRES_HOST="postgres",
            POSTGRES_PORT=5432,
            POSTGRES_DB="georank_prod",
            POSTGRES_USER="georank",
            POSTGRES_PASSWORD="change-me-postgres-password",
            TEST_DATABASE_URL="postgresql://ci:secret@db.internal/isolated_override",
        )

        self.assertEqual(
            configured.DATABASE_URL,
            "postgresql+asyncpg://georank:change-me-postgres-password"
            "@postgres:5432/georank_prod",
        )

    def test_bootstrap_maps_validated_test_url_to_app_database_environment(self) -> None:
        environment = {
            "POSTGRES_HOST": "prod.internal",
            "POSTGRES_DB": "georank_production",
            "TEST_DATABASE_URL": "postgresql://ci_user:secret@test-db:5544/project_ci_42",
        }

        database_url, database_name = bootstrap_test_database_environment(environment)

        self.assertEqual(database_name, "project_ci_42")
        self.assertEqual(
            database_url,
            "postgresql+asyncpg://ci_user:secret@test-db:5544/project_ci_42",
        )
        self.assertEqual(
            {key: environment[key] for key in (
                "POSTGRES_HOST",
                "POSTGRES_PORT",
                "POSTGRES_DB",
                "POSTGRES_USER",
                "POSTGRES_PASSWORD",
            )},
            {
                "POSTGRES_HOST": "test-db",
                "POSTGRES_PORT": "5544",
                "POSTGRES_DB": "project_ci_42",
                "POSTGRES_USER": "ci_user",
                "POSTGRES_PASSWORD": "secret",
            },
        )

    def test_bootstrap_rejects_dangerous_explicit_url_before_mutating_environment(self) -> None:
        environment = {
            "POSTGRES_DB": "georank_production",
            "TEST_DATABASE_URL": "postgresql://ci:secret@db.internal/customers_prod",
        }

        with self.assertRaisesRegex(RuntimeError, "test or ci marker"):
            bootstrap_test_database_environment(environment)

        self.assertEqual(environment["POSTGRES_DB"], "georank_production")

    def test_bootstrap_canonicalizes_default_port_and_encoded_password(self) -> None:
        environment = {
            "TEST_DATABASE_URL": (
                "postgresql://ci_user:p%40ss@127.0.0.1/project_ci_42"
            ),
        }

        database_url, _ = bootstrap_test_database_environment(environment)
        configured = Settings(
            POSTGRES_HOST=environment["POSTGRES_HOST"],
            POSTGRES_PORT=int(environment["POSTGRES_PORT"]),
            POSTGRES_DB=environment["POSTGRES_DB"],
            POSTGRES_USER=environment["POSTGRES_USER"],
            POSTGRES_PASSWORD=environment["POSTGRES_PASSWORD"],
        )

        self.assertEqual(
            database_url,
            "postgresql+asyncpg://ci_user:p%40ss@127.0.0.1:5432/project_ci_42",
        )
        self.assertEqual(configured.DATABASE_URL, database_url)

    def test_tests_package_bootstraps_global_engine_from_validated_url(self) -> None:
        environment = os.environ.copy()
        environment.update(
            {
                "POSTGRES_DB": "georank_production",
                "TEST_DATABASE_URL": (
                    "postgresql://ci_user:secret@test-db:5544/project_ci_42"
                ),
            }
        )
        script = """
import tests
from app.core.config import settings
from app.core.database import engine
assert settings.POSTGRES_DB == 'project_ci_42'
assert settings.DATABASE_URL.endswith('/project_ci_42')
assert engine.url.database == 'project_ci_42'
"""

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_general_global_engine_is_not_rewritten_by_test_database_url(self) -> None:
        environment = os.environ.copy()
        environment.update(
            {
                "POSTGRES_DB": "georank_production",
                "TEST_DATABASE_URL": (
                    "postgresql://ci_user:secret@test-db:5544/project_ci_42"
                ),
            }
        )
        script = """
from app.core.config import settings
from app.core.database import engine
assert settings.POSTGRES_DB == 'georank_production'
assert settings.DATABASE_URL.endswith('/georank_production')
assert engine.url.database == 'georank_production'
"""

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_tests_package_rejects_dangerous_url_before_global_engine_import(self) -> None:
        environment = os.environ.copy()
        environment.update(
            {
                "POSTGRES_DB": "georank_production",
                "TEST_DATABASE_URL": (
                    "postgresql://ci_user:secret@test-db:5544/customers_prod"
                ),
            }
        )
        script = """
import sys
try:
    import tests
except RuntimeError:
    assert 'app.core.database' not in sys.modules
    raise
"""

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("test or ci marker", completed.stderr)

    def test_top_level_integration_module_bootstraps_before_global_engine_import(self) -> None:
        environment = os.environ.copy()
        backend_root = os.path.dirname(os.path.dirname(__file__))
        environment.update(
            {
                "PYTHONPATH": os.pathsep.join(
                    [os.path.join(backend_root, "tests"), backend_root]
                ),
                "POSTGRES_DB": "georank_production",
                "TEST_DATABASE_URL": (
                    "postgresql://ci_user:secret@test-db:5544/project_ci_42"
                ),
            }
        )
        script = """
import test_api_integration
from app.core.database import engine
assert engine.url.database == 'project_ci_42'
"""

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=backend_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_top_level_integration_module_rejects_dangerous_url_before_engine_import(self) -> None:
        environment = os.environ.copy()
        backend_root = os.path.dirname(os.path.dirname(__file__))
        environment.update(
            {
                "PYTHONPATH": os.pathsep.join(
                    [os.path.join(backend_root, "tests"), backend_root]
                ),
                "POSTGRES_DB": "georank_production",
                "TEST_DATABASE_URL": (
                    "postgresql://ci_user:secret@test-db:5544/customers_prod"
                ),
            }
        )
        script = """
import sys
try:
    import test_api_integration
except RuntimeError as exc:
    assert 'test or ci marker' in str(exc)
    assert 'app.core.database' not in sys.modules
else:
    raise AssertionError('dangerous test URL was accepted')
"""

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=backend_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
