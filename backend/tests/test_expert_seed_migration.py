import importlib.util
import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from migration_contracts.expert_migration_contract import (
    load_expert_fixture_contracts,
    validate_expert_migration_snapshot,
)
from tests.database_safety import resolve_test_database, verify_test_database_engine


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
MIGRATION_PATH = (
    BACKEND_ROOT
    / "alembic"
    / "versions"
    / "012_seed_expert_profiles.py"
)
MIGRATION_SNAPSHOT_PATH = (
    BACKEND_ROOT
    / "alembic"
    / "snapshots"
    / "012_seed_expert_profiles.json"
)
CANONICAL_FIXTURE_PATH = REPO_ROOT / "data" / "public" / "experts.json"


def _load_migration():
    spec = importlib.util.spec_from_file_location("seed_expert_profiles_012", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _snapshot_runtime_experts(snapshot: dict) -> list[dict]:
    return [
        {
            "id": uuid.UUID(expert["id"]),
            "slug": expert["slug"],
            "display_name": expert["display_name"],
            "avatar_initials": expert["avatar_initials"],
            "title": expert["title"],
            "category": expert["category"],
            "specialty_label": expert["specialty_label"],
            "summary": expert["summary"],
            "consultation": expert["consultation"],
            "expertise": expert["expertise"],
            "keywords": expert["keywords"],
            "sort_order": expert["sort_order"],
            "is_featured": expert["is_featured"],
            "is_published": expert["is_published"],
        }
        for expert in snapshot["experts"]
    ]


class _ConnectionRecorder:
    def __init__(self):
        self.statement = None

    def execute(self, statement):
        self.statement = statement


class ExpertSeedMigrationTests(unittest.TestCase):
    def test_frozen_migration_matches_versioned_seed_snapshot(self):
        self.assertTrue(
            MIGRATION_SNAPSHOT_PATH.is_file(),
            "versioned migration seed snapshot must exist",
        )
        snapshot = json.loads(MIGRATION_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        expected = _snapshot_runtime_experts(snapshot)

        migration = _load_migration()

        self.assertEqual(validate_expert_migration_snapshot(migration, snapshot), "seed")

        self.assertEqual(snapshot["revision"], migration.revision)
        self.assertIn("down_revision", snapshot)
        self.assertEqual(snapshot["down_revision"], migration.down_revision)
        self.assertEqual(snapshot["seed_date"], migration.SEED_DATE.date().isoformat())
        self.assertEqual(migration.EXPERT_SEEDS, expected)

    def test_canonical_fixture_snapshot_matches_its_named_migration(self):
        fixture = json.loads(CANONICAL_FIXTURE_PATH.read_text(encoding="utf-8"))
        contracts = load_expert_fixture_contracts(fixture, REPO_ROOT)
        self.assertEqual(len(contracts), 1)

    def test_downgrade_matches_seed_ids_and_slugs_together(self):
        migration = _load_migration()
        recorder = _ConnectionRecorder()

        with (
            patch.object(migration.op, "get_bind", return_value=recorder),
            patch.object(migration.op, "drop_constraint"),
            patch.object(migration.op, "drop_column"),
        ):
            migration.downgrade()

        where_sql = str(recorder.statement.whereclause)
        self.assertEqual(where_sql.count("expert_profiles.id"), 5)
        self.assertEqual(where_sql.count("expert_profiles.slug"), 5)
        self.assertEqual(where_sql.count(" AND "), 5)
        self.assertEqual(where_sql.count(" OR "), 4)
        actual_pairs = set()
        for group in recorder.statement.whereclause.clauses:
            values_by_column = {
                comparison.left.name: comparison.right.value
                for comparison in group.clauses
            }
            self.assertEqual(set(values_by_column), {"id", "slug"})
            actual_pairs.add((values_by_column["id"], values_by_column["slug"]))
        self.assertEqual(
            actual_pairs,
            {(seed["id"], seed["slug"]) for seed in migration.EXPERT_SEEDS},
        )


class ExpertSeedDowngradeCollisionTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_downgrade_preserves_partial_id_and_slug_collisions(self):
        migration = _load_migration()
        schema = f"expert_seed_collision_{uuid.uuid4().hex}"
        expected_rows = set()
        try:
            async with self.engine.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.execute(
                    text(
                        f'CREATE TABLE "{schema}".expert_profiles ('
                        'id uuid PRIMARY KEY, slug varchar(120) UNIQUE)'
                    )
                )
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
                for seed in migration.EXPERT_SEEDS:
                    collision_id = uuid.uuid4()
                    different_slug = f'{seed["slug"]}-different'
                    await connection.execute(
                        text(
                            """
                            INSERT INTO expert_profiles (id, slug)
                            VALUES
                                (CAST(:seed_id AS uuid), :different_slug),
                                (CAST(:different_id AS uuid), :seed_slug)
                            """
                        ),
                        {
                            "seed_id": str(seed["id"]),
                            "different_slug": different_slug,
                            "different_id": str(collision_id),
                            "seed_slug": seed["slug"],
                        },
                    )
                    expected_rows.update(
                        {
                            (str(seed["id"]), different_slug),
                            (str(collision_id), seed["slug"]),
                        }
                    )

                def invoke_downgrade(sync_connection):
                    with (
                        patch.object(migration.op, "get_bind", return_value=sync_connection),
                        patch.object(migration.op, "drop_constraint"),
                        patch.object(migration.op, "drop_column"),
                    ):
                        migration.downgrade()

                await connection.run_sync(invoke_downgrade)
                rows = (
                    await connection.execute(
                        text("SELECT id::text, slug FROM expert_profiles ORDER BY slug")
                    )
                ).all()
                self.assertEqual(set(rows), expected_rows)
        finally:
            async with self.engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


if __name__ == "__main__":
    unittest.main()
