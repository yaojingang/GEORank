import copy
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.routes.experts import list_public_experts
from app.core.config import settings
from migration_contracts.expert_migration_contract import (
    build_tombstone_transition,
    load_expert_fixture_contracts,
    render_state_migration,
    validate_expert_fixture_projection,
    validate_expert_migration_snapshot,
)
from tests.database_safety import resolve_test_database, verify_test_database_engine


REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_FIXTURE_PATH = REPO_ROOT / "data" / "public" / "experts.json"
SEED_SNAPSHOT_PATH = (
    REPO_ROOT / "backend" / "alembic" / "snapshots" / "012_seed_expert_profiles.json"
)
SEED_MIGRATION_PATH = (
    REPO_ROOT / "backend" / "alembic" / "versions" / "012_seed_expert_profiles.py"
)
TARGET_SLUG = "yao-jingang"
STATE_SNAPSHOT_PATH = "backend/alembic/snapshots/015_unpublish_yao_jingang.json"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _build_dry_run():
    fixture = json.loads(CANONICAL_FIXTURE_PATH.read_text(encoding="utf-8"))
    return fixture, build_tombstone_transition(
        fixture,
        target_slug=TARGET_SLUG,
        revision="015_unpublish_yao_jingang",
        down_revision="016_merge_platform_iterations",
        effective_date="2026-07-16",
        snapshot_path=STATE_SNAPSHOT_PATH,
        reason="verified rights or privacy request",
    )


class ExpertMigrationContractTests(unittest.TestCase):
    def test_generic_loader_validates_frozen_seed_contract(self):
        snapshot = json.loads(SEED_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        migration = _load_module(SEED_MIGRATION_PATH, "seed_contract_012")
        self.assertEqual(
            validate_expert_migration_snapshot(migration, snapshot),
            "seed",
        )

    def test_builds_and_loads_temporary_exact_pair_tombstone_contract(self):
        original, plan = _build_dry_run()
        mutated = plan.fixture
        snapshot = plan.snapshot
        original_target = next(item for item in original["experts"] if item["slug"] == TARGET_SLUG)
        mutated_target = next(item for item in mutated["experts"] if item["slug"] == TARGET_SLUG)

        self.assertEqual(original_target["status"], "published")
        self.assertTrue(original_target["featured"])
        self.assertEqual(mutated_target["status"], "hidden")
        self.assertFalse(mutated_target["featured"])
        self.assertEqual(original["migration_snapshot"], SEED_SNAPSHOT_PATH.relative_to(REPO_ROOT).as_posix())
        self.assertNotIn("migration_chain", original)
        self.assertEqual(
            mutated["migration_chain"],
            [
                {"kind": "seed", "snapshot": original["migration_snapshot"]},
                {"kind": "state", "snapshot": STATE_SNAPSHOT_PATH},
            ],
        )
        self.assertEqual(snapshot["operations"][0]["id"], original_target["id"])
        self.assertEqual(snapshot["operations"][0]["slug"], original_target["slug"])

        with tempfile.TemporaryDirectory() as temporary_directory:
            migration_path = Path(temporary_directory) / "015_unpublish_yao_jingang.py"
            migration_path.write_text(render_state_migration(snapshot), encoding="utf-8")
            migration = _load_module(migration_path, "temporary_tombstone_015")
            self.assertEqual(
                validate_expert_migration_snapshot(migration, snapshot),
                "state",
            )
            seed_snapshot = json.loads(SEED_SNAPSHOT_PATH.read_text(encoding="utf-8"))
            seed_migration = _load_module(SEED_MIGRATION_PATH, "seed_projection_012")
            validate_expert_fixture_projection(
                mutated,
                [
                    (seed_migration, seed_snapshot),
                    (migration, snapshot),
                ],
            )

            drifted_fixture = copy.deepcopy(mutated)
            drifted_fixture["experts"][0]["status"] = "published"
            with self.assertRaises(AssertionError):
                validate_expert_fixture_projection(
                    drifted_fixture,
                    [
                        (seed_migration, seed_snapshot),
                        (migration, snapshot),
                    ],
                )

            temporary_root = Path(temporary_directory) / "repository"
            versions_directory = temporary_root / "backend" / "alembic" / "versions"
            snapshots_directory = temporary_root / "backend" / "alembic" / "snapshots"
            versions_directory.mkdir(parents=True)
            snapshots_directory.mkdir(parents=True)
            shutil.copy2(SEED_MIGRATION_PATH, versions_directory / SEED_MIGRATION_PATH.name)
            shutil.copy2(SEED_SNAPSHOT_PATH, snapshots_directory / SEED_SNAPSHOT_PATH.name)
            state_migration_path = versions_directory / migration_path.name
            state_migration_path.write_text(render_state_migration(snapshot), encoding="utf-8")
            (temporary_root / STATE_SNAPSHOT_PATH).write_text(
                json.dumps(snapshot),
                encoding="utf-8",
            )
            loaded_contracts = load_expert_fixture_contracts(mutated, temporary_root)
            self.assertEqual(len(loaded_contracts), 2)

            duplicate_path_fixture = copy.deepcopy(mutated)
            duplicate_path_fixture["migration_chain"][1]["snapshot"] = (
                duplicate_path_fixture["migration_chain"][0]["snapshot"]
            )
            with self.assertRaises(AssertionError):
                load_expert_fixture_contracts(duplicate_path_fixture, temporary_root)

            wrong_kind_fixture = copy.deepcopy(mutated)
            wrong_kind_fixture["migration_chain"][0]["kind"] = "state"
            with self.assertRaises(AssertionError):
                load_expert_fixture_contracts(wrong_kind_fixture, temporary_root)

            missing_fixture = copy.deepcopy(mutated)
            missing_fixture["migration_chain"][1]["snapshot"] = (
                "backend/alembic/snapshots/015_missing.json"
            )
            with self.assertRaises(AssertionError):
                load_expert_fixture_contracts(missing_fixture, temporary_root)

            escaping_fixture = copy.deepcopy(mutated)
            escaping_fixture["migration_chain"][1]["snapshot"] = "../../outside.json"
            with self.assertRaises(AssertionError):
                load_expert_fixture_contracts(escaping_fixture, temporary_root)

            duplicate_revision_path = (
                temporary_root / "backend/alembic/snapshots/016_duplicate_revision.json"
            )
            duplicate_revision_path.write_text(json.dumps(snapshot), encoding="utf-8")
            duplicate_revision_fixture = copy.deepcopy(mutated)
            duplicate_revision_fixture["migration_chain"].append(
                {
                    "kind": "state",
                    "snapshot": "backend/alembic/snapshots/016_duplicate_revision.json",
                }
            )
            with self.assertRaises(AssertionError):
                load_expert_fixture_contracts(duplicate_revision_fixture, temporary_root)

            parent_drift = copy.deepcopy(snapshot)
            parent_drift["down_revision"] = "013_security_invariants"
            (temporary_root / STATE_SNAPSHOT_PATH).write_text(
                json.dumps(parent_drift),
                encoding="utf-8",
            )
            with self.assertRaises(AssertionError):
                load_expert_fixture_contracts(mutated, temporary_root)

            drifted = copy.deepcopy(snapshot)
            drifted["operations"][0]["slug"] = "wrong-slug"
            with self.assertRaises(AssertionError):
                validate_expert_migration_snapshot(migration, drifted)

            republish = copy.deepcopy(snapshot)
            republish["operations"][0]["from_state"] = {
                "is_published": False,
                "is_featured": False,
            }
            republish["operations"][0]["to_state"] = {
                "is_published": True,
                "is_featured": True,
            }
            with self.assertRaises(AssertionError):
                render_state_migration(republish)

        self.assertFalse(
            (REPO_ROOT / "backend" / "alembic" / "versions" / "015_unpublish_yao_jingang.py").exists()
        )
        self.assertFalse((REPO_ROOT / STATE_SNAPSHOT_PATH).exists())


class ExpertStateMigrationDryRunTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_temporary_tombstone_removes_one_expert_from_public_api_projection(self):
        original, plan = _build_dry_run()
        schema = f"expert_tombstone_dry_run_{uuid.uuid4().hex}"
        with tempfile.TemporaryDirectory() as temporary_directory:
            migration_path = Path(temporary_directory) / "015_unpublish_yao_jingang.py"
            migration_path.write_text(render_state_migration(plan.snapshot), encoding="utf-8")
            migration = _load_module(migration_path, "temporary_tombstone_pg_015")
            validate_expert_migration_snapshot(migration, plan.snapshot)

            try:
                async with self.engine.begin() as connection:
                    await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                    await connection.execute(
                        text(
                            f'CREATE TABLE "{schema}".expert_profiles '
                            '(LIKE public.expert_profiles INCLUDING ALL)'
                        )
                    )
                    await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
                    for expert in original["experts"]:
                        await connection.execute(
                            text(
                                """
                                INSERT INTO expert_profiles (
                                    id, slug, display_name, title, sort_order,
                                    is_published, is_featured
                                ) VALUES (
                                    CAST(:id AS uuid), :slug, :display_name, :title, :sort_order,
                                    :is_published, :is_featured
                                )
                                """
                            ),
                            {
                                "id": expert["id"],
                                "slug": expert["slug"],
                                "display_name": expert["name"],
                                "title": expert["title"],
                                "sort_order": expert["sort_order"],
                                "is_published": expert["status"] == "published",
                                "is_featured": expert["featured"],
                            },
                        )

                    def invoke_upgrade(sync_connection):
                        with patch.object(migration.op, "get_bind", return_value=sync_connection):
                            migration.upgrade()

                    await connection.run_sync(invoke_upgrade)

                    async with AsyncSession(
                        bind=connection,
                        expire_on_commit=False,
                        join_transaction_mode="create_savepoint",
                    ) as session:
                        projection = await list_public_experts(db=session)

                    published_slugs = {item["slug"] for item in projection["items"]}
                    self.assertEqual(projection["total"], 4)
                    self.assertNotIn(TARGET_SLUG, published_slugs)
                    self.assertEqual(
                        published_slugs,
                        {expert["slug"] for expert in original["experts"] if expert["slug"] != TARGET_SLUG},
                    )
                    target_state = (
                        await connection.execute(
                            text(
                                """
                                SELECT is_published, is_featured
                                FROM expert_profiles
                                WHERE id = CAST(:id AS uuid) AND slug = :slug
                                """
                            ),
                            {
                                "id": plan.snapshot["operations"][0]["id"],
                                "slug": TARGET_SLUG,
                            },
                        )
                    ).one()
                    self.assertEqual(target_state, (False, False))

                    def invoke_downgrade_and_reupgrade(sync_connection):
                        with patch.object(migration.op, "get_bind", return_value=sync_connection):
                            migration.downgrade()
                            migration.upgrade()

                    await connection.run_sync(invoke_downgrade_and_reupgrade)
                    async with AsyncSession(
                        bind=connection,
                        expire_on_commit=False,
                        join_transaction_mode="create_savepoint",
                    ) as session:
                        repeated_projection = await list_public_experts(db=session)
                    self.assertEqual(repeated_projection["total"], 4)
                    self.assertNotIn(
                        TARGET_SLUG,
                        {item["slug"] for item in repeated_projection["items"]},
                    )
            finally:
                async with self.engine.begin() as connection:
                    await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))

    async def test_exact_pair_transition_preserves_partial_id_and_slug_collisions(self):
        _, plan = _build_dry_run()
        schema = f"expert_tombstone_collision_{uuid.uuid4().hex}"
        operation = plan.snapshot["operations"][0]
        with tempfile.TemporaryDirectory() as temporary_directory:
            migration_path = Path(temporary_directory) / "015_unpublish_yao_jingang.py"
            migration_path.write_text(render_state_migration(plan.snapshot), encoding="utf-8")
            migration = _load_module(migration_path, "temporary_tombstone_collision_015")
            try:
                async with self.engine.begin() as connection:
                    await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                    await connection.execute(
                        text(
                            f'CREATE TABLE "{schema}".expert_profiles ('
                            'id uuid, slug varchar(120), '
                            'is_published boolean, is_featured boolean)'
                        )
                    )
                    await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
                    collision_rows = [
                        (operation["id"], operation["slug"], "exact"),
                        (operation["id"], f'{operation["slug"]}-different', "id-only"),
                        (str(uuid.uuid4()), operation["slug"], "slug-only"),
                    ]
                    for row_id, slug, _ in collision_rows:
                        await connection.execute(
                            text(
                                """
                                INSERT INTO expert_profiles
                                    (id, slug, is_published, is_featured)
                                VALUES (CAST(:id AS uuid), :slug, true, true)
                                """
                            ),
                            {"id": row_id, "slug": slug},
                        )

                    def invoke_upgrade(sync_connection):
                        with patch.object(migration.op, "get_bind", return_value=sync_connection):
                            migration.upgrade()

                    await connection.run_sync(invoke_upgrade)
                    states = {
                        label: (
                            await connection.execute(
                                text(
                                    """
                                    SELECT is_published, is_featured
                                    FROM expert_profiles
                                    WHERE id = CAST(:id AS uuid) AND slug = :slug
                                    """
                                ),
                                {"id": row_id, "slug": slug},
                            )
                        ).one()
                        for row_id, slug, label in collision_rows
                    }
                    self.assertEqual(states["exact"], (False, False))
                    self.assertEqual(states["id-only"], (True, True))
                    self.assertEqual(states["slug-only"], (True, True))
            finally:
                async with self.engine.begin() as connection:
                    await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


if __name__ == "__main__":
    unittest.main()
