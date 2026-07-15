import asyncio
import unittest
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.routes import admin as admin_routes
from app.models.homepage import HomepageReleaseStatus


class _RecordingDb:
    def __init__(self, events: list[str], *, commit_error: Exception | None = None):
        self.events = events
        self.commit_error = commit_error

    async def execute(self, statement, *_args, **_kwargs):
        self.events.append(f"execute:{statement}")

    async def commit(self):
        self.events.append("commit")
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self):
        self.events.append("rollback")


class _CommitCoordinatedDb:
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        fail_commit: bool = False,
        commit_entered: asyncio.Event | None = None,
        successor_waiting: asyncio.Event | None = None,
    ):
        self.name = name
        self.events = events
        self.fail_commit = fail_commit
        self.commit_entered = commit_entered
        self.successor_waiting = successor_waiting

    async def execute(self, statement, *_args, **_kwargs):
        self.events.append(f"{self.name}:execute")

    async def commit(self):
        self.events.append(f"{self.name}:commit")
        if self.fail_commit:
            if self.commit_entered is not None:
                self.commit_entered.set()
            if self.successor_waiting is not None:
                await self.successor_waiting.wait()
            raise RuntimeError("commit failed")

    async def rollback(self):
        self.events.append(f"{self.name}:rollback")


class _StageBlockingDb(_RecordingDb):
    def __init__(
        self,
        events: list[str],
        blocked: asyncio.Event,
        rollback_entered: asyncio.Event,
        allow_rollback: asyncio.Event,
    ):
        super().__init__(events)
        self.blocked = blocked
        self.rollback_entered = rollback_entered
        self.allow_rollback = allow_rollback

    async def execute(self, statement, *_args, **_kwargs):
        self.events.append("A:db-await")
        self.blocked.set()
        await asyncio.Event().wait()

    async def rollback(self):
        self.events.append("rollback-entered")
        self.rollback_entered.set()
        await self.allow_rollback.wait()
        self.events.append("rollback")


class _CommitBlockingDb(_RecordingDb):
    def __init__(self, events: list[str], entered: asyncio.Event, allow: asyncio.Event):
        super().__init__(events)
        self.entered = entered
        self.allow = allow

    async def commit(self):
        self.events.append("commit-entered")
        self.entered.set()
        await self.allow.wait()
        self.events.append("commit-complete")


class HomepageMutationCoordinationTests(unittest.IsolatedAsyncioTestCase):
    async def test_activation_acquires_database_lock_before_loading_or_switching_release(self):
        events: list[str] = []
        release = SimpleNamespace(
            id=uuid.uuid4(),
            status=HomepageReleaseStatus.DRAFT,
            activated_at=None,
        )

        async def load_release(*_args, **_kwargs):
            events.append("load")
            return release

        @asynccontextmanager
        async def recording_lock():
            events.append("lock-acquired")
            try:
                yield
            finally:
                events.append("lock-released")

        with (
            patch.object(
                admin_routes,
                "_load_homepage_release_or_404",
                side_effect=load_release,
            ),
            patch.object(admin_routes, "_homepage_mutation_lock", new=recording_lock),
            patch.object(
                admin_routes,
                "_load_setting_value",
                new=AsyncMock(return_value=""),
            ),
            patch.object(
                admin_routes,
                "activate_homepage_release",
                side_effect=lambda *_args, **_kwargs: events.append("activate"),
            ),
            patch.object(admin_routes, "snapshot_active_homepage_target", return_value=None),
            patch.object(admin_routes, "_cleanup_previous_homepage_overlay"),
            patch.object(
                admin_routes,
                "_store_homepage_runtime",
                new=AsyncMock(return_value={}),
            ),
            patch.object(
                admin_routes,
                "invalidate_runtime_settings_cache",
                new=AsyncMock(),
            ),
            patch.object(admin_routes, "_serialize_homepage_release", return_value={}),
        ):
            await admin_routes.activate_homepage_release_admin(
                release.id,
                _RecordingDb(events),
                SimpleNamespace(id=uuid.uuid4()),
            )

        self.assertEqual(events[0], "lock-acquired")
        self.assertLess(0, events.index("load"))
        self.assertLess(events.index("load"), events.index("activate"))
        self.assertLess(events.index("commit"), events.index("lock-released"))

    async def test_activation_restores_previous_pointer_when_database_commit_fails(self):
        events: list[str] = []
        release = SimpleNamespace(
            id=uuid.uuid4(),
            status=HomepageReleaseStatus.DRAFT,
            activated_at=None,
        )
        previous_target = Path("releases/previous")

        @asynccontextmanager
        async def recording_lock():
            events.append("lock-acquired")
            try:
                yield
            finally:
                events.append("lock-released")

        with (
            patch.object(
                admin_routes,
                "_load_homepage_release_or_404",
                new=AsyncMock(return_value=release),
            ),
            patch.object(admin_routes, "_homepage_mutation_lock", new=recording_lock),
            patch.object(
                admin_routes,
                "_load_setting_value",
                new=AsyncMock(return_value=""),
            ),
            patch.object(
                admin_routes,
                "activate_homepage_release",
                side_effect=lambda *_args, **_kwargs: events.append("activate"),
            ),
            patch.object(
                admin_routes,
                "snapshot_active_homepage_target",
                return_value=previous_target,
            ),
            patch.object(
                admin_routes,
                "restore_active_homepage_target",
                side_effect=lambda _root, target: events.append(f"restore:{target}"),
            ),
            patch.object(
                admin_routes,
                "_store_homepage_runtime",
                new=AsyncMock(return_value={}),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "commit failed"):
                await admin_routes.activate_homepage_release_admin(
                    release.id,
                    _RecordingDb(events, commit_error=RuntimeError("commit failed")),
                    SimpleNamespace(id=uuid.uuid4()),
                )

        self.assertLess(events.index("commit"), events.index(f"restore:{previous_target}"))
        self.assertLess(events.index(f"restore:{previous_target}"), events.index("rollback"))

    async def test_failed_activation_compensates_before_successor_can_acquire_lock(self):
        events: list[str] = []
        transaction_lock = asyncio.Lock()
        first_commit_entered = asyncio.Event()
        successor_waiting = asyncio.Event()
        pointer = {"target": Path("releases/previous")}
        first_release = SimpleNamespace(
            id=uuid.uuid4(), status=HomepageReleaseStatus.DRAFT, activated_at=None
        )
        second_release = SimpleNamespace(
            id=uuid.uuid4(), status=HomepageReleaseStatus.DRAFT, activated_at=None
        )
        releases = {first_release.id: first_release, second_release.id: second_release}

        async def load_release(_db, release_id):
            return releases[release_id]

        def activate(_root, release_id, **_kwargs):
            pointer["target"] = Path("releases") / release_id
            events.append(f"activate:{release_id}")

        def restore(_root, target):
            pointer["target"] = target
            events.append(f"restore:{target}")

        first_db = _CommitCoordinatedDb(
            "A",
            events,
            fail_commit=True,
            commit_entered=first_commit_entered,
            successor_waiting=successor_waiting,
        )
        second_db = _CommitCoordinatedDb(
            "B",
            events,
            successor_waiting=successor_waiting,
        )

        @asynccontextmanager
        async def coordinated_lock():
            task_name = asyncio.current_task().get_name()
            events.append(f"{task_name}:lock-attempt")
            if task_name == "B":
                successor_waiting.set()
            await transaction_lock.acquire()
            events.append(f"{task_name}:lock-acquired")
            try:
                yield
            finally:
                events.append(f"{task_name}:lock-released")
                transaction_lock.release()

        with (
            patch.object(admin_routes, "_load_homepage_release_or_404", side_effect=load_release),
            patch.object(admin_routes, "_homepage_mutation_lock", new=coordinated_lock),
            patch.object(admin_routes, "_load_setting_value", new=AsyncMock(return_value="")),
            patch.object(admin_routes, "snapshot_active_homepage_target", side_effect=lambda _root: pointer["target"]),
            patch.object(admin_routes, "activate_homepage_release", side_effect=activate),
            patch.object(admin_routes, "restore_active_homepage_target", side_effect=restore),
            patch.object(admin_routes, "_cleanup_previous_homepage_overlay"),
            patch.object(admin_routes, "_store_homepage_runtime", new=AsyncMock(return_value={})),
            patch.object(admin_routes, "invalidate_runtime_settings_cache", new=AsyncMock()),
            patch.object(admin_routes, "_serialize_homepage_release", return_value={}),
        ):
            first_task = asyncio.create_task(
                admin_routes.activate_homepage_release_admin(
                    first_release.id, first_db, SimpleNamespace(id=uuid.uuid4())
                ),
                name="A",
            )
            await first_commit_entered.wait()
            second_task = asyncio.create_task(
                admin_routes.activate_homepage_release_admin(
                    second_release.id, second_db, SimpleNamespace(id=uuid.uuid4())
                ),
                name="B",
            )
            results = await asyncio.gather(first_task, second_task, return_exceptions=True)

        self.assertIsInstance(results[0], RuntimeError)
        self.assertNotIsInstance(results[1], Exception)
        self.assertEqual(pointer["target"], Path("releases") / str(second_release.id))
        self.assertLess(events.index("restore:releases/previous"), events.index("A:rollback"))
        self.assertLess(events.index("A:rollback"), events.index("A:lock-released"))
        self.assertLess(events.index("A:lock-released"), events.index("B:lock-acquired"))

    async def test_cancelled_activation_compensates_before_successor_acquires_lock(self):
        events: list[str] = []
        session_lock = asyncio.Lock()
        first_blocked_after_stage = asyncio.Event()
        rollback_entered = asyncio.Event()
        allow_rollback = asyncio.Event()
        successor_attempted = asyncio.Event()
        pointer = {"target": Path("releases/previous")}
        first_release = SimpleNamespace(
            id=uuid.uuid4(), status=HomepageReleaseStatus.DRAFT, activated_at=None
        )
        second_release = SimpleNamespace(
            id=uuid.uuid4(), status=HomepageReleaseStatus.DRAFT, activated_at=None
        )
        releases = {first_release.id: first_release, second_release.id: second_release}

        @asynccontextmanager
        async def coordinated_lock():
            task_name = asyncio.current_task().get_name()
            events.append(f"{task_name}:lock-attempt")
            if task_name == "B":
                successor_attempted.set()
            await session_lock.acquire()
            events.append(f"{task_name}:lock-acquired")
            try:
                yield
            finally:
                events.append(f"{task_name}:lock-released")
                session_lock.release()

        async def load_release(_db, release_id):
            return releases[release_id]

        def activate(_root, release_id, **_kwargs):
            pointer["target"] = Path("releases") / release_id
            events.append(f"activate:{release_id}")

        def restore(_root, target):
            pointer["target"] = target
            events.append(f"restore:{target}")

        first_db = _StageBlockingDb(
            events,
            first_blocked_after_stage,
            rollback_entered,
            allow_rollback,
        )
        second_db = _RecordingDb(events)
        with (
            patch.object(admin_routes, "_homepage_mutation_lock", new=coordinated_lock),
            patch.object(admin_routes, "_load_homepage_release_or_404", side_effect=load_release),
            patch.object(admin_routes, "_load_setting_value", new=AsyncMock(return_value="")),
            patch.object(admin_routes, "snapshot_active_homepage_target", side_effect=lambda _root: pointer["target"]),
            patch.object(admin_routes, "activate_homepage_release", side_effect=activate),
            patch.object(admin_routes, "restore_active_homepage_target", side_effect=restore),
            patch.object(admin_routes, "_cleanup_previous_homepage_overlay"),
            patch.object(admin_routes, "_store_homepage_runtime", new=AsyncMock(return_value={})),
            patch.object(admin_routes, "invalidate_runtime_settings_cache", new=AsyncMock()),
            patch.object(admin_routes, "_serialize_homepage_release", return_value={}),
        ):
            first_task = asyncio.create_task(
                admin_routes.activate_homepage_release_admin(
                    first_release.id, first_db, SimpleNamespace(id=uuid.uuid4())
                ),
                name="A",
            )
            await first_blocked_after_stage.wait()
            second_task = asyncio.create_task(
                admin_routes.activate_homepage_release_admin(
                    second_release.id, second_db, SimpleNamespace(id=uuid.uuid4())
                ),
                name="B",
            )
            await successor_attempted.wait()
            self.assertNotIn("B:lock-acquired", events)
            first_task.cancel()
            await rollback_entered.wait()
            first_task.cancel()
            allow_rollback.set()
            first_result, second_result = await asyncio.gather(
                first_task, second_task, return_exceptions=True
            )

        self.assertIsInstance(first_result, asyncio.CancelledError)
        self.assertNotIsInstance(second_result, Exception)
        self.assertEqual(pointer["target"], Path("releases") / str(second_release.id))
        self.assertLess(events.index("restore:releases/previous"), events.index("rollback"))
        self.assertLess(events.index("rollback"), events.index("A:lock-released"))
        self.assertLess(events.index("A:lock-released"), events.index("B:lock-acquired"))

    async def test_cancelled_release_deletion_restores_quarantine_before_unlock(self):
        events: list[str] = []
        blocked_after_stage = asyncio.Event()
        rollback_entered = asyncio.Event()
        allow_rollback = asyncio.Event()
        release = SimpleNamespace(id=uuid.uuid4(), status=HomepageReleaseStatus.DRAFT)
        db = _StageBlockingDb(
            events,
            blocked_after_stage,
            rollback_entered,
            allow_rollback,
        )

        class Deletion:
            def rollback(self):
                events.append("quarantine-rollback")

            def commit(self):
                events.append("quarantine-commit")

        @asynccontextmanager
        async def recording_lock():
            events.append("lock-acquired")
            try:
                yield
            finally:
                events.append("lock-released")

        with (
            patch.object(admin_routes, "_homepage_mutation_lock", new=recording_lock),
            patch.object(
                admin_routes,
                "_load_homepage_release_or_404",
                new=AsyncMock(return_value=release),
            ),
            patch.object(
                admin_routes,
                "stage_homepage_release_deletion",
                side_effect=lambda *_args: events.append("quarantine-stage") or Deletion(),
            ),
        ):
            task = asyncio.create_task(
                admin_routes.delete_homepage_release_admin(
                    release.id,
                    db,
                    SimpleNamespace(id=uuid.uuid4()),
                )
            )
            await blocked_after_stage.wait()
            task.cancel()
            await rollback_entered.wait()
            task.cancel()
            allow_rollback.set()
            result = (await asyncio.gather(task, return_exceptions=True))[0]

        self.assertIsInstance(result, asyncio.CancelledError)
        self.assertLess(events.index("quarantine-stage"), events.index("quarantine-rollback"))
        self.assertLess(events.index("quarantine-rollback"), events.index("rollback"))
        self.assertLess(events.index("rollback"), events.index("lock-released"))
        self.assertNotIn("quarantine-commit", events)

    async def test_cancellation_during_successful_commit_keeps_committed_pointer(self):
        events: list[str] = []
        commit_entered = asyncio.Event()
        allow_commit = asyncio.Event()
        finalize_entered = asyncio.Event()
        allow_finalize = asyncio.Event()
        release = SimpleNamespace(
            id=uuid.uuid4(), status=HomepageReleaseStatus.DRAFT, activated_at=None
        )
        pointer = {"target": Path("releases/previous")}
        db = _CommitBlockingDb(events, commit_entered, allow_commit)

        async def invalidate_cache():
            events.append("cache-invalidate-entered")
            finalize_entered.set()
            await allow_finalize.wait()
            events.append("cache-invalidated")

        @asynccontextmanager
        async def recording_lock():
            events.append("lock-acquired")
            try:
                yield
            finally:
                events.append("lock-released")

        with (
            patch.object(admin_routes, "_homepage_mutation_lock", new=recording_lock),
            patch.object(
                admin_routes,
                "_load_homepage_release_or_404",
                new=AsyncMock(return_value=release),
            ),
            patch.object(admin_routes, "_load_setting_value", new=AsyncMock(return_value="")),
            patch.object(admin_routes, "snapshot_active_homepage_target", return_value=pointer["target"]),
            patch.object(
                admin_routes,
                "activate_homepage_release",
                side_effect=lambda _root, release_id, **_kwargs: pointer.update(
                    target=Path("releases") / release_id
                ),
            ),
            patch.object(
                admin_routes,
                "restore_active_homepage_target",
                side_effect=lambda _root, target: events.append(f"restore:{target}"),
            ),
            patch.object(
                admin_routes,
                "_cleanup_previous_homepage_overlay",
                side_effect=lambda *_args: events.append("overlay-cleanup"),
            ),
            patch.object(
                admin_routes,
                "invalidate_runtime_settings_cache",
                new=invalidate_cache,
            ),
            patch.object(admin_routes, "_store_homepage_runtime", new=AsyncMock(return_value={})),
        ):
            task = asyncio.create_task(
                admin_routes.activate_homepage_release_admin(
                    release.id,
                    db,
                    SimpleNamespace(id=uuid.uuid4()),
                )
            )
            await commit_entered.wait()
            task.cancel()
            allow_commit.set()
            await finalize_entered.wait()
            task.cancel()
            allow_finalize.set()
            result = (await asyncio.gather(task, return_exceptions=True))[0]

        self.assertIsInstance(result, asyncio.CancelledError)
        self.assertEqual(pointer["target"], Path("releases") / str(release.id))
        self.assertNotIn("restore:releases/previous", events)
        self.assertNotIn("rollback", events)
        self.assertLess(events.index("commit-complete"), events.index("overlay-cleanup"))
        self.assertLess(events.index("overlay-cleanup"), events.index("cache-invalidated"))
        self.assertLess(events.index("cache-invalidated"), events.index("lock-released"))


if __name__ == "__main__":
    unittest.main()
