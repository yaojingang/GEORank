"""Run the Alembic chain as the single database-schema bootstrap owner."""

from __future__ import annotations

import asyncio
import argparse
from contextlib import asynccontextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import sys
from typing import AsyncContextManager, AsyncIterator, Protocol

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
ALEMBIC_DIRECTORY = BACKEND_ROOT / "alembic"
MIGRATION_LOCK_ID = 0x47454F52414E4B  # ASCII "GEORANK", fits signed bigint.
# Append-only ownership sentinels. Keep historical Alembic tables here after a
# model rename or removal so an unversioned legacy schema still fails closed.
ALEMBIC_MANAGED_TABLES = frozenset(
    {
        "users",
        "companies",
        "contents",
        "diagnostic_reports",
        "conversations",
        "messages",
        "company_votes",
        "settings",
        "keyword_packs",
        "keyword_items",
        "expert_profiles",
        "ai_usage_events",
        "user_daily_usage",
        "homepage_releases",
    }
)
PROCESS_TERMINATION_TIMEOUT_SECONDS = 10


class MigrationBootstrapError(RuntimeError):
    """The schema bootstrap could not establish the required Alembic head."""


class LegacyUnversionedSchemaError(MigrationBootstrapError):
    """Managed tables exist but Alembic has no ownership record."""


@dataclass(frozen=True)
class SchemaState:
    has_version_table: bool
    managed_tables: tuple[str, ...]


class MigrationRuntime(Protocol):
    def migration_lock(self) -> AsyncContextManager[object]: ...

    async def inspect_schema(self, connection: object) -> SchemaState: ...

    async def upgrade_to_head(self) -> None: ...

    async def get_expected_heads(self) -> tuple[str, ...]: ...

    async def get_current_versions(self, connection: object) -> tuple[str, ...]: ...


async def run_migration_bootstrap(runtime: MigrationRuntime) -> None:
    """Upgrade a fresh or Alembic-owned database and verify its exact heads."""
    async with runtime.migration_lock() as connection:
        state = await runtime.inspect_schema(connection)
        _reject_legacy_unversioned_schema(state)

        await runtime.upgrade_to_head()
        await _verify_exact_heads(runtime, connection)


async def run_migration_preflight(runtime: MigrationRuntime) -> None:
    """Verify schema ownership and exact heads without changing the database."""
    async with runtime.migration_lock() as connection:
        state = await runtime.inspect_schema(connection)
        _reject_legacy_unversioned_schema(state)
        if not state.has_version_table:
            raise MigrationBootstrapError(
                "database has no alembic_version; run the migration service before "
                "starting application runtimes"
            )
        await _verify_exact_heads(runtime, connection)


def _reject_legacy_unversioned_schema(state: SchemaState) -> None:
    if state.has_version_table or not state.managed_tables:
        return
    names = ", ".join(state.managed_tables)
    raise LegacyUnversionedSchemaError(
        "managed tables exist without alembic_version "
        f"({names}). Create a backup, then use an empty database or follow "
        "the documented legacy recovery procedure. Automatic stamp is refused."
    )


async def _verify_exact_heads(
    runtime: MigrationRuntime,
    connection: object,
) -> None:
    expected = tuple(sorted(await runtime.get_expected_heads()))
    current = tuple(sorted(await runtime.get_current_versions(connection)))
    if current != expected:
        raise MigrationBootstrapError(
            f"database migration verification failed: expected {expected}, found {current}"
        )


class PostgresMigrationRuntime:
    def __init__(self) -> None:
        self._engine = create_async_engine(
            settings.DATABASE_URL,
            poolclass=NullPool,
        )

    @asynccontextmanager
    async def migration_lock(self) -> AsyncIterator[AsyncConnection]:
        async with self._engine.connect() as connection:
            await connection.execute(
                text("SELECT pg_advisory_lock(:lock_id)"),
                {"lock_id": MIGRATION_LOCK_ID},
            )
            try:
                yield connection
            finally:
                await connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": MIGRATION_LOCK_ID},
                )
                await connection.commit()

    async def inspect_schema(self, connection: AsyncConnection) -> SchemaState:
        version_result = await connection.execute(
            text("SELECT to_regclass('alembic_version') IS NOT NULL")
        )
        has_version_table = bool(version_result.scalar_one())

        table_result = await connection.execute(
            text(
                "SELECT tablename FROM pg_catalog.pg_tables "
                "WHERE schemaname = current_schema()"
            )
        )
        existing_tables = set(table_result.scalars())
        managed_tables = tuple(sorted(existing_tables & ALEMBIC_MANAGED_TABLES))
        return SchemaState(
            has_version_table=has_version_table,
            managed_tables=managed_tables,
        )

    async def upgrade_to_head(self) -> None:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ALEMBIC_INI),
            "upgrade",
            "head",
            cwd=str(BACKEND_ROOT),
            start_new_session=True,
        )
        try:
            return_code = await process.wait()
        except BaseException:
            await _terminate_and_reap(process)
            raise
        if return_code != 0:
            raise MigrationBootstrapError(
                f"alembic upgrade head failed with exit code {return_code}"
            )

    async def get_expected_heads(self) -> tuple[str, ...]:
        config = Config(str(ALEMBIC_INI))
        config.set_main_option("script_location", str(ALEMBIC_DIRECTORY))
        return tuple(ScriptDirectory.from_config(config).get_heads())

    async def get_current_versions(
        self,
        connection: AsyncConnection,
    ) -> tuple[str, ...]:
        result = await connection.execute(
            text("SELECT version_num FROM alembic_version ORDER BY version_num")
        )
        return tuple(result.scalars())

    async def dispose(self) -> None:
        await self._engine.dispose()


async def _terminate_and_reap(process) -> None:
    if process.returncode is not None:
        return
    _signal_process_group(process, signal.SIGTERM)
    wait_task = asyncio.create_task(process.wait())
    exited = await _wait_for_reap(
        wait_task,
        timeout=PROCESS_TERMINATION_TIMEOUT_SECONDS,
    )
    if exited:
        return
    _signal_process_group(process, signal.SIGKILL)
    await _wait_for_reap(wait_task, timeout=None)


def _signal_process_group(process, signum: signal.Signals) -> None:
    try:
        os.killpg(os.getpgid(process.pid), signum)
    except (AttributeError, OSError, ProcessLookupError):
        if process.returncode is not None:
            return
        if signum == signal.SIGTERM:
            process.terminate()
        else:
            process.kill()


async def _wait_for_reap(
    wait_task: asyncio.Task,
    *,
    timeout: float | None,
) -> bool:
    loop = asyncio.get_running_loop()
    deadline = None if timeout is None else loop.time() + timeout
    while True:
        remaining = None if deadline is None else max(0, deadline - loop.time())
        try:
            if remaining is None:
                await asyncio.shield(wait_task)
            else:
                await asyncio.wait_for(asyncio.shield(wait_task), timeout=remaining)
            return True
        except asyncio.CancelledError:
            continue
        except asyncio.TimeoutError:
            return False


async def _main(*, check_only: bool) -> int:
    runtime = PostgresMigrationRuntime()
    loop = asyncio.get_running_loop()
    current_task = asyncio.current_task()
    received_signal: signal.Signals | None = None

    def request_shutdown(signum: signal.Signals) -> None:
        nonlocal received_signal
        received_signal = signum
        if current_task is not None:
            current_task.cancel()

    installed_signals: list[signal.Signals] = []
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, request_shutdown, signum)
            installed_signals.append(signum)
        except NotImplementedError:
            pass

    try:
        if check_only:
            await run_migration_preflight(runtime)
        else:
            await run_migration_bootstrap(runtime)
    except MigrationBootstrapError as error:
        print(f"[migration] {error}", file=sys.stderr)
        return 1
    except asyncio.CancelledError:
        print("[migration] cancelled after stopping the Alembic child", file=sys.stderr)
        return 128 + int(received_signal or signal.SIGINT)
    finally:
        for signum in installed_signals:
            loop.remove_signal_handler(signum)
        await runtime.dispose()
    action = "preflight" if check_only else "database"
    print(f"[migration] {action} is at the required Alembic head")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the exact Alembic head without changing the database",
    )
    arguments = parser.parse_args(argv)
    return asyncio.run(_main(check_only=arguments.check))


if __name__ == "__main__":
    raise SystemExit(main())
