import importlib.util
import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests.database_safety import resolve_test_database, verify_test_database_engine
from app.core.config import settings
from app.main import _seed_default_homepage_release


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "014_migrate_builtin_homepage_release.py"
)
OLD_RELEASE_ID = "f7e16e7c-e1aa-4e39-951b-4c274dd05175"
NEW_RELEASE_ID = "43a461f6-6be2-4931-9dbb-f1d56576292a"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEW_MANIFEST_PATH = (
    PROJECT_ROOT
    / "runtime"
    / "homepages"
    / "releases"
    / NEW_RELEASE_ID
    / "manifest.json"
)
OLD_MANIFEST = {
    "id": OLD_RELEASE_ID,
    "title": "首页 8 模块工作台入口 2026-06-16",
    "source_type": "zip_package",
    "entry_path": "index.html",
    "storage_path": f"/app/runtime/homepages/releases/{OLD_RELEASE_ID}",
    "public_path": f"/app/runtime/homepages/public/releases/{OLD_RELEASE_ID}",
    "file_count": 4,
    "compressed_size": 14105,
    "extracted_size": 1525609,
    "sha256": "8e03d99ce95cfffb003a48258eb76457aa75869297e0f7e16655a1c9b5eaba99",
    "files": [
        {
            "path": "css/style.css",
            "size": 35442,
            "sha256": "8072bf21c8297c981a9ba83fbf05fee408f49e01bfa22cae23808f8fb740b927",
        },
        {
            "path": "favicon.svg",
            "size": 513,
            "sha256": "4ed02e3c7de9b2c1b2efd461eeec75fd7e56b6272bad3bc2a37bb8e56fb2bce8",
        },
        {
            "path": "images/ai-marketing-book.png",
            "size": 1456316,
            "sha256": "d797fe991235da5b9d7308db24fc78ca0d142456b707931caf9c6764e0f13636",
        },
        {
            "path": "index.html",
            "size": 33338,
            "sha256": "0f7aa384c88a9b62930796dc38a4f02d9ddd950b67979240f26771f730ae5c88",
        },
    ],
    "created_at": "2026-06-16T06:58:21.368734Z",
}


def _load_migration():
    spec = importlib.util.spec_from_file_location("migrate_builtin_homepage_release_014", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _invoke_migration(sync_connection, direction: str) -> None:
    migration = _load_migration()
    with patch.object(migration.op, "get_bind", return_value=sync_connection):
        getattr(migration, direction)()


class BuiltinHomepageMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        database_url, database_name = resolve_test_database(
            default_database_url=settings.DATABASE_URL,
            configured_database_name=os.environ.get("POSTGRES_DB"),
            explicit_test_database_url=os.environ.get("TEST_DATABASE_URL"),
        )
        self.engine = create_async_engine(database_url, poolclass=NullPool)
        await verify_test_database_engine(self.engine, database_url, database_name)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    async def _reset_rows(self, connection) -> None:
        await connection.execute(
            text("DELETE FROM homepage_releases WHERE id IN (CAST(:old_id AS uuid), CAST(:new_id AS uuid))"),
            {"old_id": OLD_RELEASE_ID, "new_id": NEW_RELEASE_ID},
        )
        await connection.execute(text("DELETE FROM settings WHERE key = 'homepage_runtime'"))

    async def _insert_setting(self, connection, active_release_id: str) -> None:
        value = json.dumps(
            {
                "mode": "custom",
                "active_release_id": active_release_id,
                "fallback_to_company": True,
            }
        )
        await connection.execute(
            text(
                """
                INSERT INTO settings (key, value, category, is_public)
                VALUES ('homepage_runtime', CAST(:value AS jsonb), 'frontend', false)
                """
            ),
            {"value": value},
        )

    async def _insert_release(self, connection, release_id: str, status: str, title: str = "test") -> None:
        await connection.execute(
            text(
                """
                INSERT INTO homepage_releases (
                    id, title, source_type, status, entry_path, storage_path,
                    file_count, compressed_size, extracted_size
                ) VALUES (
                    CAST(:release_id AS uuid), :title,
                    CAST('zip_package' AS homepagesourcetype),
                    CAST(:status AS homepagereleasestatus),
                    'index.html', :storage_path, 1, 1, 1
                )
                """
            ),
            {
                "release_id": release_id,
                "title": title,
                "status": status,
                "storage_path": f"/app/runtime/homepages/releases/{release_id}",
            },
        )

    async def _snapshot(self, connection):
        setting = (
            await connection.execute(
                text("SELECT value FROM settings WHERE key = 'homepage_runtime'")
            )
        ).scalar_one()
        releases = (
            await connection.execute(
                text(
                    """
                    SELECT id::text, title, status::text, manifest
                    FROM homepage_releases
                    WHERE id IN (CAST(:old_id AS uuid), CAST(:new_id AS uuid))
                    ORDER BY id::text
                    """
                ),
                {"old_id": OLD_RELEASE_ID, "new_id": NEW_RELEASE_ID},
            )
        ).all()
        return setting, releases

    async def test_upgrade_moves_old_builtin_selection_and_archives_old_release(self):
        async with self.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await self._reset_rows(connection)
                await self._insert_setting(connection, OLD_RELEASE_ID)
                await self._insert_release(connection, OLD_RELEASE_ID, "active", "old builtin")

                await connection.run_sync(lambda sync: _invoke_migration(sync, "upgrade"))

                setting, releases = await self._snapshot(connection)
                self.assertEqual(setting["active_release_id"], NEW_RELEASE_ID)
                self.assertEqual(
                    {release_id: status for release_id, _title, status, _manifest in releases},
                    {NEW_RELEASE_ID: "active"},
                )
                self.assertEqual(releases[0][3], json.loads(NEW_MANIFEST_PATH.read_text()))
            finally:
                await transaction.rollback()

    async def test_upgrade_is_idempotent(self):
        async with self.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await self._reset_rows(connection)
                await self._insert_setting(connection, OLD_RELEASE_ID)
                await self._insert_release(connection, OLD_RELEASE_ID, "active")

                await connection.run_sync(lambda sync: _invoke_migration(sync, "upgrade"))
                first = await self._snapshot(connection)
                await connection.run_sync(lambda sync: _invoke_migration(sync, "upgrade"))
                second = await self._snapshot(connection)

                self.assertEqual(second, first)
            finally:
                await transaction.rollback()

    async def test_repeated_upgrade_preserves_activation_time_across_transactions(self):
        schema = f"homepage_migration_{uuid.uuid4().hex}"
        try:
            async with self.engine.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.execute(
                    text(f'CREATE TABLE "{schema}".settings (LIKE public.settings INCLUDING ALL)')
                )
                await connection.execute(
                    text(
                        f'CREATE TABLE "{schema}".homepage_releases '
                        '(LIKE public.homepage_releases INCLUDING ALL)'
                    )
                )

            async with self.engine.begin() as connection:
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
                await self._insert_setting(connection, OLD_RELEASE_ID)
                await self._insert_release(connection, OLD_RELEASE_ID, "active")
                await connection.run_sync(lambda sync: _invoke_migration(sync, "upgrade"))
                await connection.execute(
                    text(
                        "UPDATE homepage_releases "
                        "SET activated_at = TIMESTAMP '2000-01-01 00:00:00' "
                        "WHERE id = CAST(:id AS uuid)"
                    ),
                    {"id": NEW_RELEASE_ID},
                )
                first_activated_at = await connection.scalar(
                    text(
                        "SELECT activated_at FROM homepage_releases "
                        "WHERE id = CAST(:id AS uuid)"
                    ),
                    {"id": NEW_RELEASE_ID},
                )

            async with self.engine.begin() as connection:
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
                await connection.run_sync(lambda sync: _invoke_migration(sync, "upgrade"))
                second_activated_at = await connection.scalar(
                    text(
                        "SELECT activated_at FROM homepage_releases "
                        "WHERE id = CAST(:id AS uuid)"
                    ),
                    {"id": NEW_RELEASE_ID},
                )

            self.assertIsNotNone(first_activated_at)
            self.assertEqual(second_activated_at, first_activated_at)
        finally:
            async with self.engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))

    async def test_upgrade_preserves_custom_homepage_selection(self):
        custom_id = str(uuid.uuid4())
        async with self.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await self._reset_rows(connection)
                await self._insert_setting(connection, custom_id)
                await self._insert_release(connection, OLD_RELEASE_ID, "archived")
                await self._insert_release(connection, custom_id, "active", "custom homepage")

                await connection.run_sync(lambda sync: _invoke_migration(sync, "upgrade"))

                setting, releases = await self._snapshot(connection)
                custom_status = await connection.scalar(
                    text("SELECT status::text FROM homepage_releases WHERE id = CAST(:id AS uuid)"),
                    {"id": custom_id},
                )
                builtin_activated_at = await connection.scalar(
                    text("SELECT activated_at FROM homepage_releases WHERE id = CAST(:id AS uuid)"),
                    {"id": NEW_RELEASE_ID},
                )
                self.assertEqual(setting["active_release_id"], custom_id)
                self.assertEqual(custom_status, "active")
                self.assertIsNone(builtin_activated_at)
                self.assertEqual(
                    [(release_id, status) for release_id, _title, status, _manifest in releases],
                    [(NEW_RELEASE_ID, "archived")],
                )
                self.assertEqual(releases[0][3], json.loads(NEW_MANIFEST_PATH.read_text()))
            finally:
                await transaction.rollback()

    async def test_custom_downgrade_preseeds_archived_old_builtin_for_legacy_startup(self):
        custom_id = str(uuid.uuid4())
        async with self.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await self._reset_rows(connection)
                await self._insert_setting(connection, custom_id)
                await self._insert_release(connection, custom_id, "active", "custom homepage")
                await self._insert_release(connection, NEW_RELEASE_ID, "archived", "new builtin")

                await connection.run_sync(lambda sync: _invoke_migration(sync, "downgrade"))

                # Pre-014 startup inserted an ACTIVE built-in only when the row was absent.
                await connection.execute(
                    text(
                        """
                        INSERT INTO homepage_releases (
                            id, title, source_type, status, entry_path, storage_path,
                            file_count, compressed_size, extracted_size
                        )
                        SELECT
                            CAST(:old_id AS uuid), 'legacy startup builtin',
                            CAST('zip_package' AS homepagesourcetype),
                            CAST('active' AS homepagereleasestatus),
                            'index.html', :storage_path, 1, 1, 1
                        WHERE NOT EXISTS (
                            SELECT 1 FROM homepage_releases WHERE id = CAST(:old_id AS uuid)
                        )
                        """
                    ),
                    {
                        "old_id": OLD_RELEASE_ID,
                        "storage_path": f"/app/runtime/homepages/releases/{OLD_RELEASE_ID}",
                    },
                )

                setting, releases = await self._snapshot(connection)
                custom_status = await connection.scalar(
                    text("SELECT status::text FROM homepage_releases WHERE id = CAST(:id AS uuid)"),
                    {"id": custom_id},
                )
                builtin_activated_at = await connection.scalar(
                    text("SELECT activated_at FROM homepage_releases WHERE id = CAST(:id AS uuid)"),
                    {"id": OLD_RELEASE_ID},
                )
                self.assertEqual(setting["active_release_id"], custom_id)
                self.assertEqual(custom_status, "active")
                self.assertIsNone(builtin_activated_at)
                self.assertEqual(
                    [(release_id, status) for release_id, _title, status, _manifest in releases],
                    [(OLD_RELEASE_ID, "archived")],
                )
                self.assertEqual(releases[0][3], OLD_MANIFEST)
            finally:
                await transaction.rollback()

    async def test_downgrade_without_runtime_setting_restores_active_default_builtin(self):
        custom_id = str(uuid.uuid4())
        async with self.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await self._reset_rows(connection)
                await self._insert_release(connection, NEW_RELEASE_ID, "archived", "new builtin")
                await self._insert_release(connection, custom_id, "active", "orphaned active release")

                await connection.run_sync(lambda sync: _invoke_migration(sync, "downgrade"))

                setting_count = await connection.scalar(
                    text("SELECT count(*) FROM settings WHERE key = 'homepage_runtime'")
                )
                release = (
                    await connection.execute(
                        text(
                            """
                            SELECT status::text, activated_at
                            FROM homepage_releases
                            WHERE id = CAST(:id AS uuid)
                            """
                        ),
                        {"id": OLD_RELEASE_ID},
                    )
                ).one()
                custom_status = await connection.scalar(
                    text("SELECT status::text FROM homepage_releases WHERE id = CAST(:id AS uuid)"),
                    {"id": custom_id},
                )
                self.assertEqual(setting_count, 0)
                self.assertEqual(release[0], "active")
                self.assertIsNotNone(release[1])
                self.assertEqual(custom_status, "archived")
            finally:
                await transaction.rollback()

    async def test_startup_seeds_builtin_as_archived_for_custom_selection(self):
        custom_id = str(uuid.uuid4())
        async with self.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await self._reset_rows(connection)
                await self._insert_setting(connection, custom_id)
                await self._insert_release(connection, custom_id, "active", "custom homepage")

                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    with patch(
                        "app.services.homepage_assets.homepage_root",
                        return_value=PROJECT_ROOT / "runtime" / "homepages",
                    ):
                        await _seed_default_homepage_release(session)

                statuses = dict(
                    (
                        await connection.execute(
                            text(
                                """
                                SELECT id::text, status::text
                                FROM homepage_releases
                                WHERE id IN (CAST(:custom_id AS uuid), CAST(:new_id AS uuid))
                                """
                            ),
                            {"custom_id": custom_id, "new_id": NEW_RELEASE_ID},
                        )
                    ).all()
                )
                builtin_activated_at = await connection.scalar(
                    text("SELECT activated_at FROM homepage_releases WHERE id = CAST(:id AS uuid)"),
                    {"id": NEW_RELEASE_ID},
                )
                self.assertEqual(statuses[custom_id], "active")
                self.assertEqual(statuses[NEW_RELEASE_ID], "archived")
                self.assertIsNone(builtin_activated_at)
            finally:
                await transaction.rollback()

    async def test_fresh_migration_startup_activates_builtin_with_timestamp(self):
        async with self.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await self._reset_rows(connection)
                await connection.run_sync(lambda sync: _invoke_migration(sync, "upgrade"))
                await self._insert_setting(connection, NEW_RELEASE_ID)

                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    with patch(
                        "app.services.homepage_assets.homepage_root",
                        return_value=PROJECT_ROOT / "runtime" / "homepages",
                    ):
                        await _seed_default_homepage_release(session)

                release = (
                    await connection.execute(
                        text(
                            """
                            SELECT status::text, activated_at
                            FROM homepage_releases
                            WHERE id = CAST(:id AS uuid)
                            """
                        ),
                        {"id": NEW_RELEASE_ID},
                    )
                ).one()
                self.assertEqual(release[0], "active")
                self.assertIsNotNone(release[1])
            finally:
                await transaction.rollback()

    async def test_downgrade_restores_old_builtin_and_is_idempotent(self):
        async with self.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await self._reset_rows(connection)
                await self._insert_setting(connection, NEW_RELEASE_ID)
                await self._insert_release(connection, NEW_RELEASE_ID, "active", "new builtin")
                await self._insert_release(connection, OLD_RELEASE_ID, "archived", "old builtin")

                await connection.run_sync(lambda sync: _invoke_migration(sync, "downgrade"))
                first = await self._snapshot(connection)
                await connection.run_sync(lambda sync: _invoke_migration(sync, "downgrade"))
                second = await self._snapshot(connection)

                self.assertEqual(second, first)
                self.assertEqual(first[0]["active_release_id"], OLD_RELEASE_ID)
                self.assertEqual(
                    {release_id: status for release_id, _title, status, _manifest in first[1]},
                    {OLD_RELEASE_ID: "active"},
                )
                self.assertEqual(first[1][0][3], OLD_MANIFEST)
            finally:
                await transaction.rollback()


if __name__ == "__main__":
    unittest.main()
