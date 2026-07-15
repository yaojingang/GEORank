import asyncio
import ast
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
import signal
from unittest.mock import AsyncMock, patch


from app.scripts.migrate import (
    LegacyUnversionedSchemaError,
    ALEMBIC_MANAGED_TABLES,
    MigrationBootstrapError,
    PostgresMigrationRuntime,
    SchemaState,
    run_migration_preflight,
    run_migration_bootstrap,
)


class FakeMigrationRuntime:
    def __init__(
        self,
        *,
        state: SchemaState,
        expected_heads=("014_builtin_homepage_release",),
        current_versions=("014_builtin_homepage_release",),
        upgrade_error: Exception | None = None,
    ):
        self.state = state
        self.expected_heads = expected_heads
        self.current_versions = current_versions
        self.upgrade_error = upgrade_error
        self.events: list[str] = []

    @asynccontextmanager
    async def migration_lock(self):
        self.events.append("lock")
        try:
            yield object()
        finally:
            self.events.append("unlock")

    async def inspect_schema(self, _connection):
        self.events.append("inspect")
        return self.state

    async def upgrade_to_head(self):
        self.events.append("upgrade")
        if self.upgrade_error:
            raise self.upgrade_error

    async def get_expected_heads(self):
        self.events.append("expected-heads")
        return self.expected_heads

    async def get_current_versions(self, _connection):
        self.events.append("current-versions")
        return self.current_versions


class MigrationBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_database_upgrades_and_verifies_head_while_holding_lock(self):
        runtime = FakeMigrationRuntime(
            state=SchemaState(has_version_table=False, managed_tables=()),
        )

        await run_migration_bootstrap(runtime)

        self.assertEqual(
            runtime.events,
            [
                "lock",
                "inspect",
                "upgrade",
                "expected-heads",
                "current-versions",
                "unlock",
            ],
        )

    async def test_existing_alembic_database_is_upgraded_idempotently(self):
        runtime = FakeMigrationRuntime(
            state=SchemaState(
                has_version_table=True,
                managed_tables=("users", "expert_profiles"),
            ),
        )

        await run_migration_bootstrap(runtime)

        self.assertEqual(runtime.events.count("upgrade"), 1)
        self.assertEqual(runtime.events[-1], "unlock")

    async def test_legacy_create_all_schema_fails_closed_before_upgrade(self):
        runtime = FakeMigrationRuntime(
            state=SchemaState(
                has_version_table=False,
                managed_tables=("users", "expert_profiles"),
            ),
        )

        with self.assertRaisesRegex(
            LegacyUnversionedSchemaError,
            r"alembic_version.*backup.*empty database.*recovery",
        ):
            await run_migration_bootstrap(runtime)

        self.assertNotIn("upgrade", runtime.events)
        self.assertEqual(runtime.events[-1], "unlock")

    async def test_migration_failure_prevents_success_and_releases_lock(self):
        runtime = FakeMigrationRuntime(
            state=SchemaState(has_version_table=False, managed_tables=()),
            upgrade_error=MigrationBootstrapError("upgrade failed"),
        )

        with self.assertRaisesRegex(MigrationBootstrapError, "upgrade failed"):
            await run_migration_bootstrap(runtime)

        self.assertNotIn("current-versions", runtime.events)
        self.assertEqual(runtime.events[-1], "unlock")

    async def test_database_must_reach_exact_script_heads(self):
        runtime = FakeMigrationRuntime(
            state=SchemaState(has_version_table=True, managed_tables=("users",)),
            current_versions=("013_security_invariants",),
        )

        with self.assertRaisesRegex(
            MigrationBootstrapError,
            r"expected.*014_builtin_homepage_release.*found.*013_security_invariants",
        ):
            await run_migration_bootstrap(runtime)

        self.assertEqual(runtime.events[-1], "unlock")

    async def test_preflight_rejects_empty_database_without_running_upgrade(self):
        runtime = FakeMigrationRuntime(
            state=SchemaState(has_version_table=False, managed_tables=()),
        )

        with self.assertRaisesRegex(
            MigrationBootstrapError,
            r"no alembic_version.*run the migration service",
        ):
            await run_migration_preflight(runtime)

        self.assertNotIn("upgrade", runtime.events)
        self.assertEqual(runtime.events[-1], "unlock")

    async def test_preflight_accepts_exact_head_without_writing_schema(self):
        runtime = FakeMigrationRuntime(
            state=SchemaState(has_version_table=True, managed_tables=("users",)),
        )

        await run_migration_preflight(runtime)

        self.assertNotIn("upgrade", runtime.events)
        self.assertEqual(
            runtime.events,
            ["lock", "inspect", "expected-heads", "current-versions", "unlock"],
        )

    async def test_cancelled_upgrade_terminates_and_reaps_child_before_unlock(self):
        class FakeProcess:
            def __init__(self):
                self.pid = 4242
                self.returncode = None
                self.wait_started = asyncio.Event()
                self.terminated = False
                self.reaped = False
                self.wait_calls = 0

            async def wait(self):
                self.wait_calls += 1
                if self.wait_calls == 1:
                    self.wait_started.set()
                    await asyncio.Event().wait()
                self.returncode = -15
                self.reaped = True
                return self.returncode

            def terminate(self):
                self.terminated = True

            def kill(self):
                self.returncode = -9

        process = FakeProcess()
        runtime = PostgresMigrationRuntime()
        killpg_calls = []
        try:
            process_creator = AsyncMock(return_value=process)
            with (
                patch(
                    "app.scripts.migrate.asyncio.create_subprocess_exec",
                    new=process_creator,
                ),
                patch("app.scripts.migrate.os.getpgid", return_value=process.pid),
                patch(
                    "app.scripts.migrate.os.killpg",
                    side_effect=lambda pgid, signum: killpg_calls.append((pgid, signum)),
                ),
            ):
                task = asyncio.create_task(runtime.upgrade_to_head())
                await process.wait_started.wait()
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
        finally:
            await runtime.dispose()

        self.assertTrue(process.reaped)
        self.assertGreaterEqual(process.wait_calls, 2)
        self.assertTrue(process_creator.await_args.kwargs["start_new_session"])
        self.assertEqual(killpg_calls, [(process.pid, signal.SIGTERM)])

    async def test_cancelled_bootstrap_releases_lock_after_upgrade_cleanup(self):
        class WaitingRuntime(FakeMigrationRuntime):
            def __init__(self):
                super().__init__(
                    state=SchemaState(has_version_table=False, managed_tables=())
                )
                self.upgrade_started = asyncio.Event()

            async def upgrade_to_head(self):
                self.events.append("upgrade")
                self.upgrade_started.set()
                await asyncio.Event().wait()

        runtime = WaitingRuntime()
        task = asyncio.create_task(run_migration_bootstrap(runtime))
        await runtime.upgrade_started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertEqual(runtime.events[-1], "unlock")

    def test_stable_managed_table_manifest_covers_current_models(self):
        from app.core.database import Base
        import app.models  # noqa: F401

        current_tables = {table.name for table in Base.metadata.sorted_tables}
        self.assertTrue(current_tables.issubset(ALEMBIC_MANAGED_TABLES))
        self.assertIn("users", ALEMBIC_MANAGED_TABLES)

    def test_stable_managed_table_manifest_covers_alembic_history(self):
        versions_directory = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        historical_tables = set()
        for migration_path in versions_directory.glob("*.py"):
            tree = ast.parse(migration_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                function = node.func
                if not isinstance(function, ast.Attribute) or function.attr != "create_table":
                    continue
                table_name = node.args[0]
                if isinstance(table_name, ast.Constant) and isinstance(table_name.value, str):
                    historical_tables.add(table_name.value)

        self.assertTrue(historical_tables)
        self.assertTrue(historical_tables.issubset(ALEMBIC_MANAGED_TABLES))


if __name__ == "__main__":
    unittest.main()
