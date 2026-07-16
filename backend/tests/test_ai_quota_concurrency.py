import asyncio
import hashlib
import sys
import unittest
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import delete, select
from starlette.requests import Request


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session  # noqa: E402
from app.models.ai_usage import (  # noqa: E402
    AICreditWallet,
    AIGlobalDailyBudget,
    AIPrincipalDevice,
    AIPrincipalUser,
    AIQuotaAuditLog,
    AIQuotaPrincipal,
    AITokenReservation,
    AIUsageEvent,
    UserDailyUsage,
)
from app.models.user import User, UserRole  # noqa: E402
from app.models.diagnostic import DiagnosticReport, DiagnosticStatus  # noqa: E402
from app.services.ai_usage import (  # noqa: E402
    claim_async_reservation_stage,
    complete_async_reservation_stage,
    get_or_create_quota_principal,
    record_ai_usage,
    release_ai_access,
    release_async_reservation_stage_claim,
    release_expired_token_reservations,
    resolve_ai_access,
    settle_token_reservation,
)
from app.services.runtime_settings import get_default_ai_usage_policy_config  # noqa: E402
from app.tasks.crawl import _diagnostic_reservation_state as crawl_diagnostic_reservation_state  # noqa: E402
from app.tasks.diagnose import _diagnostic_reservation_state as analyze_diagnostic_reservation_state  # noqa: E402


TEST_PREFIX = "ai_quota_concurrency_"


def make_request(device_id: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/solutions/chat",
            "headers": [
                (b"x-georank-device-id", device_id.encode("utf-8")),
                (b"user-agent", b"GEOrank quota test"),
            ],
        }
    )


class AiQuotaConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)

    @classmethod
    def tearDownClass(cls):
        from app.core.database import engine

        cls.loop.run_until_complete(engine.dispose())
        cls.loop.close()

    def run_async(self, coro):
        return self.loop.run_until_complete(coro)

    def setUp(self):
        self.run_async(self._cleanup())

    def tearDown(self):
        self.run_async(self._cleanup())

    async def _cleanup(self):
        async with async_session() as db:
            await db.execute(delete(AIQuotaAuditLog))
            await db.execute(delete(DiagnosticReport))
            await db.execute(delete(AITokenReservation))
            await db.execute(delete(AIGlobalDailyBudget))
            await db.execute(delete(AICreditWallet))
            await db.execute(delete(AIPrincipalDevice))
            await db.execute(delete(AIPrincipalUser))
            await db.execute(delete(AIQuotaPrincipal))
            await db.execute(delete(UserDailyUsage))
            await db.execute(delete(AIUsageEvent))
            await db.execute(delete(User).where(User.email.like(f"{TEST_PREFIX}%")))
            await db.commit()

    async def _create_user(self) -> uuid.UUID:
        suffix = uuid.uuid4().hex
        async with async_session() as db:
            user = User(
                email=f"{TEST_PREFIX}{suffix}@example.com",
                username=f"{TEST_PREFIX}{suffix}",
                hashed_password="test-only",
                role=UserRole.USER,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            await db.commit()
            return user.id

    async def _reserve_unpatched(self, user_id: uuid.UUID, device_id: str):
        async with async_session() as db:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
            return await resolve_ai_access(
                db=db,
                request=make_request(device_id),
                current_user=user,
                module="solutions",
                prompt_text="测试平台额度预占",
            )

    async def _reserve(self, user_id: uuid.UUID, device_id: str, policy: dict):
        with patch(
            "app.services.ai_usage.get_ai_usage_policy_config",
            new=AsyncMock(return_value=policy),
        ):
            return await self._reserve_unpatched(user_id, device_id)

    def test_successful_call_settles_wallet_and_global_budget(self):
        async def scenario():
            user_id = await self._create_user()
            policy = get_default_ai_usage_policy_config()
            access = await self._reserve(user_id, "device-success-00000001", policy)

            async with async_session() as db:
                await record_ai_usage(db, access, output_text="已完成")
                await db.commit()
                wallet = (await db.execute(select(AICreditWallet))).scalar_one()
                budget = (await db.execute(select(AIGlobalDailyBudget))).scalar_one()
                reservation = (
                    await db.execute(
                        select(AITokenReservation).where(AITokenReservation.id == access.reservation_id)
                    )
                ).scalar_one()

            self.assertEqual(wallet.reserved_tokens, 0)
            self.assertGreater(wallet.consumed_tokens, 0)
            self.assertEqual(budget.reserved_tokens, 0)
            self.assertEqual(budget.consumed_tokens, wallet.consumed_tokens)
            self.assertEqual(reservation.status, "settled")

        self.run_async(scenario())

    def test_settlement_tracks_actual_overage_and_keeps_global_limit_hard(self):
        async def scenario():
            user_id = await self._create_user()
            policy = get_default_ai_usage_policy_config()
            access = await self._reserve(user_id, "device-actual-overage-01", policy)

            async with async_session() as db:
                await settle_token_reservation(
                    db,
                    reservation_id=access.reservation_id,
                    actual_tokens=7000,
                    succeeded=True,
                )
                await db.commit()
                wallet = (await db.execute(select(AICreditWallet))).scalar_one()
                budget = (await db.execute(select(AIGlobalDailyBudget))).scalar_one()
                reservation = (
                    await db.execute(
                        select(AITokenReservation).where(AITokenReservation.id == access.reservation_id)
                    )
                ).scalar_one()

            self.assertEqual(access.reserved_tokens, 6500)
            self.assertEqual(wallet.reserved_tokens, 0)
            self.assertEqual(wallet.consumed_tokens, 7000)
            self.assertEqual(budget.reserved_tokens, 0)
            self.assertEqual(budget.consumed_tokens, 7000)
            self.assertEqual(reservation.actual_tokens, 7000)
            self.assertEqual(reservation.charged_tokens, 7000)
            self.assertEqual(reservation.event_metadata["reservation_overage_tokens"], 500)

        self.run_async(scenario())

    def test_actual_overage_saturates_global_budget_and_blocks_followup_calls(self):
        async def scenario():
            first_user = await self._create_user()
            second_user = await self._create_user()
            policy = {
                **get_default_ai_usage_policy_config(),
                "global_daily_token_limit": 6500,
            }
            access = await self._reserve(first_user, "device-global-overage-01", policy)

            async with async_session() as db:
                await settle_token_reservation(
                    db,
                    reservation_id=access.reservation_id,
                    actual_tokens=7000,
                    succeeded=True,
                )
                await db.commit()
                budget = (await db.execute(select(AIGlobalDailyBudget))).scalar_one()

            self.assertEqual(budget.consumed_tokens, 6500)
            with patch(
                "app.services.ai_usage.get_ai_usage_policy_config",
                new=AsyncMock(return_value=policy),
            ):
                with self.assertRaises(HTTPException) as context:
                    await self._reserve_unpatched(second_user, "device-global-overage-02")
            self.assertEqual(
                context.exception.detail["code"],
                "global_daily_budget_exhausted",
            )

        self.run_async(scenario())

    def test_cancelled_stream_can_conservatively_charge_full_reservation(self):
        async def scenario():
            user_id = await self._create_user()
            policy = get_default_ai_usage_policy_config()
            access = await self._reserve(user_id, "device-stream-cancel-01", policy)

            async with async_session() as db:
                await record_ai_usage(
                    db,
                    access,
                    output_text="",
                    status_value="error",
                    error_code="client_disconnected",
                    charge_reserved_tokens_on_error=True,
                )
                await db.commit()
                wallet = (await db.execute(select(AICreditWallet))).scalar_one()
                reservation = await db.get(AITokenReservation, access.reservation_id)

            self.assertEqual(wallet.consumed_tokens, access.reserved_tokens)
            self.assertEqual(reservation.charged_tokens, access.reserved_tokens)
            self.assertEqual(reservation.status, "settled")

        self.run_async(scenario())

    def test_same_device_or_same_account_reuses_risk_principal(self):
        async def scenario():
            first_user = await self._create_user()
            second_user = await self._create_user()
            policy = get_default_ai_usage_policy_config()
            first = await self._reserve(first_user, "device-shared-000000001", policy)
            async with async_session() as db:
                await release_ai_access(db, first)
                await db.commit()

            switched_account = await self._reserve(second_user, "device-shared-000000001", policy)
            async with async_session() as db:
                await release_ai_access(db, switched_account)
                await db.commit()
            switched_browser = await self._reserve(second_user, "device-new-browser-00001", policy)

            self.assertEqual(first.principal_id, switched_account.principal_id)
            self.assertEqual(switched_account.principal_id, switched_browser.principal_id)

            async with async_session() as db:
                await release_ai_access(db, switched_browser)
                await db.commit()

        self.run_async(scenario())

    def test_principal_merge_preserves_freeze_and_pending_reservation(self):
        async def scenario():
            first_user = await self._create_user()
            second_user = await self._create_user()
            device_hash = hashlib.sha256(b"shared-merge-device-0001").hexdigest()
            reservation_id = uuid.uuid4()

            async with async_session() as db:
                first_principal = AIQuotaPrincipal(status="active")
                second_principal = AIQuotaPrincipal(status="active")
                db.add_all([first_principal, second_principal])
                await db.flush()
                db.add_all(
                    [
                        AIPrincipalUser(principal_id=first_principal.id, user_id=first_user),
                        AIPrincipalUser(principal_id=second_principal.id, user_id=second_user),
                        AIPrincipalDevice(
                            principal_id=first_principal.id,
                            device_hash=device_hash,
                        ),
                        AICreditWallet(
                            principal_id=first_principal.id,
                            granted_tokens=10_000,
                            consumed_tokens=100,
                            reserved_tokens=6_500,
                            request_count=1,
                            frozen=True,
                        ),
                        AICreditWallet(
                            principal_id=second_principal.id,
                            granted_tokens=10_000,
                            consumed_tokens=200,
                            reserved_tokens=0,
                            request_count=2,
                        ),
                        AITokenReservation(
                            id=reservation_id,
                            idempotency_key=f"merge-{reservation_id}",
                            principal_id=first_principal.id,
                            user_id=first_user,
                            usage_date=date.today(),
                            module="solutions",
                            status="pending",
                            reserved_tokens=6_500,
                            personal_reserved_tokens=6_500,
                            global_reserved_tokens=0,
                            expires_at=datetime.utcnow() + timedelta(hours=1),
                        ),
                    ]
                )
                await db.commit()

            async with async_session() as db:
                merged_id, wallet = await get_or_create_quota_principal(
                    db,
                    user_id=second_user,
                    device_hash=device_hash,
                    user_agent_hash=None,
                    default_grant=10_000,
                )
                await db.commit()
                self.assertTrue(wallet.frozen)
                self.assertEqual(wallet.consumed_tokens, 300)
                self.assertEqual(wallet.reserved_tokens, 6_500)
                self.assertEqual(wallet.request_count, 3)
                reservation = await db.get(AITokenReservation, reservation_id)
                self.assertEqual(reservation.principal_id, merged_id)

                await settle_token_reservation(
                    db,
                    reservation_id=reservation_id,
                    actual_tokens=0,
                    succeeded=False,
                )
                await db.commit()
                merged_wallet = (
                    await db.execute(
                        select(AICreditWallet).where(AICreditWallet.principal_id == merged_id)
                    )
                ).scalar_one()
                self.assertTrue(merged_wallet.frozen)
                self.assertEqual(merged_wallet.consumed_tokens, 300)
                self.assertEqual(merged_wallet.reserved_tokens, 0)

        self.run_async(scenario())

    def test_cross_linked_principals_merge_once_under_concurrency(self):
        async def scenario():
            first_user = await self._create_user()
            second_user = await self._create_user()
            first_device = hashlib.sha256(b"cross-device-1").hexdigest()
            second_device = hashlib.sha256(b"cross-device-2").hexdigest()

            async with async_session() as db:
                first_principal = AIQuotaPrincipal(status="active")
                second_principal = AIQuotaPrincipal(status="active")
                db.add_all([first_principal, second_principal])
                await db.flush()
                db.add_all([
                    AIPrincipalUser(principal_id=first_principal.id, user_id=first_user),
                    AIPrincipalUser(principal_id=second_principal.id, user_id=second_user),
                    AIPrincipalDevice(
                        principal_id=first_principal.id,
                        device_hash=first_device,
                    ),
                    AIPrincipalDevice(
                        principal_id=second_principal.id,
                        device_hash=second_device,
                    ),
                    AICreditWallet(
                        principal_id=first_principal.id,
                        granted_tokens=10_000,
                        consumed_tokens=100,
                    ),
                    AICreditWallet(
                        principal_id=second_principal.id,
                        granted_tokens=10_000,
                        consumed_tokens=200,
                    ),
                ])
                await db.commit()

            async def link(user_id, device_hash):
                async with async_session() as db:
                    principal_id, _ = await get_or_create_quota_principal(
                        db,
                        user_id=user_id,
                        device_hash=device_hash,
                        user_agent_hash=None,
                        default_grant=10_000,
                    )
                    await db.commit()
                    return principal_id

            linked = await asyncio.gather(
                link(first_user, second_device),
                link(second_user, first_device),
            )
            self.assertEqual(linked[0], linked[1])

            async with async_session() as db:
                user_links = set((await db.scalars(select(AIPrincipalUser.principal_id))).all())
                device_links = set((await db.scalars(select(AIPrincipalDevice.principal_id))).all())
                wallet = await db.scalar(
                    select(AICreditWallet).where(AICreditWallet.principal_id == linked[0])
                )
                self.assertEqual(user_links, {linked[0]})
                self.assertEqual(device_links, {linked[0]})
                self.assertIsNotNone(wallet)
                self.assertEqual(wallet.consumed_tokens, 300)

        self.run_async(scenario())

    def test_concurrent_personal_reservations_cannot_exceed_grant(self):
        async def scenario():
            user_id = await self._create_user()
            policy = {**get_default_ai_usage_policy_config(), "lifetime_token_grant": 6500}
            with patch(
                "app.services.ai_usage.get_ai_usage_policy_config",
                new=AsyncMock(return_value=policy),
            ):
                results = await asyncio.gather(
                    self._reserve_unpatched(user_id, "device-personal-race-01"),
                    self._reserve_unpatched(user_id, "device-personal-race-01"),
                    return_exceptions=True,
                )
            successes = [item for item in results if not isinstance(item, Exception)]
            failures = [item for item in results if isinstance(item, HTTPException)]

            self.assertEqual(len(successes), 1, repr(results))
            self.assertEqual(len(failures), 1, repr(results))
            self.assertEqual(failures[0].detail["code"], "personal_quota_exhausted")

            async with async_session() as db:
                wallet = (await db.execute(select(AICreditWallet))).scalar_one()
                self.assertEqual(wallet.reserved_tokens, 6500)
                await release_ai_access(db, successes[0])
                await db.commit()

        self.run_async(scenario())

    def test_concurrent_global_reservations_cannot_exceed_daily_limit(self):
        async def scenario():
            first_user = await self._create_user()
            second_user = await self._create_user()
            policy = {
                **get_default_ai_usage_policy_config(),
                "lifetime_token_grant": 10000,
                "global_daily_token_limit": 6500,
            }
            with patch(
                "app.services.ai_usage.get_ai_usage_policy_config",
                new=AsyncMock(return_value=policy),
            ):
                results = await asyncio.gather(
                    self._reserve_unpatched(first_user, "device-global-race-0001"),
                    self._reserve_unpatched(second_user, "device-global-race-0002"),
                    return_exceptions=True,
                )
            successes = [item for item in results if not isinstance(item, Exception)]
            failures = [item for item in results if isinstance(item, HTTPException)]

            self.assertEqual(len(successes), 1, repr(results))
            self.assertEqual(len(failures), 1, repr(results))
            self.assertEqual(failures[0].detail["code"], "global_daily_budget_exhausted")

            async with async_session() as db:
                budget = (await db.execute(select(AIGlobalDailyBudget))).scalar_one()
                self.assertEqual(budget.reserved_tokens, 6500)
                await release_ai_access(db, successes[0])
                await db.commit()

        self.run_async(scenario())

    def test_expired_reservation_releases_personal_and_global_holds(self):
        async def scenario():
            user_id = await self._create_user()
            policy = get_default_ai_usage_policy_config()
            access = await self._reserve(user_id, "device-expired-hold-001", policy)

            async with async_session() as db:
                reservation = (
                    await db.execute(
                        select(AITokenReservation).where(AITokenReservation.id == access.reservation_id)
                    )
                ).scalar_one()
                reservation.expires_at = datetime.utcnow() - timedelta(seconds=1)
                await db.commit()

            async with async_session() as db:
                released = await release_expired_token_reservations(db)
                await db.commit()
                wallet = (await db.execute(select(AICreditWallet))).scalar_one()
                budget = (await db.execute(select(AIGlobalDailyBudget))).scalar_one()
                reservation = (
                    await db.execute(
                        select(AITokenReservation).where(AITokenReservation.id == access.reservation_id)
                    )
                ).scalar_one()

            self.assertEqual(released, 1)
            self.assertEqual(wallet.reserved_tokens, 0)
            self.assertEqual(budget.reserved_tokens, 0)
            self.assertEqual(reservation.status, "released")
            self.assertEqual(reservation.event_metadata["release_reason"], "reservation_expired")

        self.run_async(scenario())

    def test_expired_reservation_charges_provider_progress_already_recorded(self):
        async def scenario():
            user_id = await self._create_user()
            policy = get_default_ai_usage_policy_config()
            access = await self._reserve(user_id, "device-expired-spend-001", policy)

            async with async_session() as db:
                self.assertTrue(
                    await claim_async_reservation_stage(
                        db,
                        reservation_id=access.reservation_id,
                        stage="company_profile:attempt-1",
                        claim_id="attempt-1",
                    )
                )
                self.assertTrue(
                    await complete_async_reservation_stage(
                        db,
                        reservation_id=access.reservation_id,
                        stage="company_profile:attempt-1",
                        claim_id="attempt-1",
                        actual_tokens=321,
                    )
                )
                reservation = await db.get(AITokenReservation, access.reservation_id)
                reservation.expires_at = datetime.utcnow() - timedelta(seconds=1)
                await db.commit()

            async with async_session() as db:
                self.assertEqual(await release_expired_token_reservations(db), 1)
                await db.commit()
                wallet = (await db.execute(select(AICreditWallet))).scalar_one()
                budget = (await db.execute(select(AIGlobalDailyBudget))).scalar_one()
                reservation = await db.get(AITokenReservation, access.reservation_id)

            self.assertEqual(wallet.reserved_tokens, 0)
            self.assertEqual(wallet.consumed_tokens, 321)
            self.assertEqual(budget.reserved_tokens, 0)
            self.assertEqual(budget.consumed_tokens, 321)
            self.assertEqual(reservation.status, "settled")
            self.assertEqual(reservation.actual_tokens, 321)
            self.assertEqual(reservation.charged_tokens, 321)

        self.run_async(scenario())

    def test_completed_provider_progress_is_retained_across_retry_attempts(self):
        async def scenario():
            user_id = await self._create_user()
            policy = get_default_ai_usage_policy_config()
            access = await self._reserve(user_id, "device-stage-retry-0001", policy)

            async with async_session() as db:
                self.assertTrue(
                    await claim_async_reservation_stage(
                        db,
                        reservation_id=access.reservation_id,
                        stage="company_graph:attempt-1",
                        claim_id="attempt-1",
                    )
                )
                self.assertFalse(
                    await claim_async_reservation_stage(
                        db,
                        reservation_id=access.reservation_id,
                        stage="company_graph:attempt-1",
                        claim_id="duplicate",
                    )
                )
                self.assertTrue(
                    await complete_async_reservation_stage(
                        db,
                        reservation_id=access.reservation_id,
                        stage="company_graph:attempt-1",
                        claim_id="attempt-1",
                        actual_tokens=321,
                    )
                )
                await release_async_reservation_stage_claim(
                    db,
                    reservation_id=access.reservation_id,
                    stage="company_graph:attempt-1",
                    claim_id="attempt-1",
                )
                self.assertTrue(
                    await claim_async_reservation_stage(
                        db,
                        reservation_id=access.reservation_id,
                        stage="company_graph:attempt-2",
                        claim_id="attempt-2",
                    )
                )
                self.assertTrue(
                    await complete_async_reservation_stage(
                        db,
                        reservation_id=access.reservation_id,
                        stage="company_graph:attempt-2",
                        claim_id="attempt-2",
                        actual_tokens=111,
                    )
                )
                # Replaying the same completion is idempotent.
                self.assertTrue(
                    await complete_async_reservation_stage(
                        db,
                        reservation_id=access.reservation_id,
                        stage="company_graph:attempt-2",
                        claim_id="attempt-2",
                        actual_tokens=999,
                    )
                )
                reservation = await db.get(AITokenReservation, access.reservation_id)
                self.assertEqual(reservation.actual_tokens, 432)
                await db.rollback()

            async with async_session() as db:
                await release_ai_access(db, access)
                await db.commit()

        self.run_async(scenario())

    def test_completed_diagnostic_ignores_duplicate_task_delivery(self):
        async def scenario():
            user_id = await self._create_user()
            policy = get_default_ai_usage_policy_config()
            access = await self._reserve(user_id, "device-diagnostic-finished-01", policy)
            report_id = uuid.uuid4()
            async with async_session() as db:
                db.add(DiagnosticReport(
                    id=report_id,
                    url="https://example.com",
                    status=DiagnosticStatus.COMPLETED,
                    user_id=user_id,
                    ai_reservation_id=access.reservation_id,
                ))
                await db.commit()

            self.assertEqual(
                await crawl_diagnostic_reservation_state(
                    str(report_id),
                    str(access.reservation_id),
                ),
                "finished",
            )
            self.assertEqual(
                await analyze_diagnostic_reservation_state(
                    str(report_id),
                    str(access.reservation_id),
                ),
                "finished",
            )

            async with async_session() as db:
                await db.execute(delete(DiagnosticReport).where(DiagnosticReport.id == report_id))
                await release_ai_access(db, access)
                await db.commit()

        self.run_async(scenario())


if __name__ == "__main__":
    unittest.main()
