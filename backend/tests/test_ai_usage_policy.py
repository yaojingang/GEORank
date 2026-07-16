import asyncio
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import delete, func, or_, select, update

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session  # noqa: E402
from app.main import app  # noqa: E402
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
from app.models.company import Company, PipelineStatus, PublishStatus  # noqa: E402
from app.models.conversation import Conversation, Message  # noqa: E402
from app.models.settings import Setting  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.services.ai_usage import record_async_task_usage  # noqa: E402
from app.services.runtime_settings import invalidate_runtime_settings_cache  # noqa: E402


TEST_EMAIL_PREFIX = "usage_policy_"
TEST_USERNAME_PREFIX = "usage_policy_"
TEST_PHONE_PREFIX = "1381000"
TEST_PASSWORD = "UsagePolicy@2026"


class AiUsagePolicyApiTests(unittest.TestCase):
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
        self.run_async(self._async_setup())

    def tearDown(self):
        self.run_async(self._async_teardown())

    async def _async_setup(self):
        self.transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=self.transport, base_url="http://testserver")
        await self._cleanup_test_data()

    async def _async_teardown(self):
        await self.client.aclose()
        await self._cleanup_test_data()

    async def _cleanup_test_data(self):
        async with async_session() as db:
            await db.execute(delete(AIQuotaAuditLog))
            await db.execute(delete(AITokenReservation))
            await db.execute(delete(AIGlobalDailyBudget))
            await db.execute(delete(AICreditWallet))
            await db.execute(delete(AIPrincipalDevice))
            await db.execute(delete(AIPrincipalUser))
            await db.execute(delete(AIQuotaPrincipal))
            user_ids = list(
                (
                    await db.execute(
                        select(User.id).where(
                            or_(
                                User.email.like(f"{TEST_EMAIL_PREFIX}%"),
                                User.phone.like(f"{TEST_PHONE_PREFIX}%"),
                            )
                        )
                    )
                ).scalars()
            )
            if user_ids:
                await db.execute(delete(AIUsageEvent).where(AIUsageEvent.user_id.in_(user_ids)))
                await db.execute(delete(UserDailyUsage).where(UserDailyUsage.user_id.in_(user_ids)))
                await db.execute(delete(Message).where(Message.conversation_id.in_(
                    select(Conversation.id).where(Conversation.user_id.in_(user_ids))
                )))
                await db.execute(delete(Conversation).where(Conversation.user_id.in_(user_ids)))
                await db.execute(delete(Company).where(Company.submitted_by.in_(user_ids)))
                await db.execute(delete(User).where(User.id.in_(user_ids)))
            await db.execute(delete(Company).where(Company.url.like("https://usage-policy-%")))
            await db.execute(delete(Setting).where(Setting.key == "api_usage_policy"))
            await db.commit()
        await invalidate_runtime_settings_cache()

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "X-GEOrank-Device-ID": f"test-device-{token[-32:]}",
        }

    async def _register_user(self, *, admin: bool = False) -> dict[str, str]:
        suffix = uuid.uuid4().hex[:10]
        phone_suffix = str(uuid.uuid4().int)[-4:]
        username = f"{TEST_USERNAME_PREFIX}{suffix}"
        email = f"{TEST_EMAIL_PREFIX}{suffix}@example.com"
        phone = f"{TEST_PHONE_PREFIX}{phone_suffix}"
        response = await self.client.post(
            "/api/auth/register",
            json={"email": email, "username": username, "phone": phone, "password": TEST_PASSWORD},
        )
        self.assertEqual(response.status_code, 201, response.text)
        token = response.json()["access_token"]

        if admin:
            async with async_session() as db:
                await db.execute(update(User).where(User.email == email).values(role=UserRole.ADMIN))
                await db.commit()
        return {"email": email, "username": username, "phone": phone, "token": token}

    def test_usage_policy_default_is_publicly_readable(self):
        response = self.run_async(self.client.get("/api/usage/policy"))

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["access_mode"], "lifetime_quota_with_byok")
        self.assertEqual(payload["lifetime_token_grant"], 10000)
        self.assertEqual(payload["global_daily_token_limit"], 1000000)
        self.assertTrue(payload["allow_user_byok"])
        self.assertIn("solutions", payload["metered_modules"])

    def test_admin_can_update_policy_and_user_sees_remaining_quota(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())

        update_response = self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "lifetime_quota_with_byok",
                    "lifetime_token_grant": 123,
                    "allow_user_byok": False,
                },
            )
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)

        usage_response = self.run_async(
            self.client.get("/api/usage/me", headers=self._auth_headers(user["token"]))
        )
        self.assertEqual(usage_response.status_code, 200, usage_response.text)
        payload = usage_response.json()
        self.assertEqual(payload["access_mode"], "lifetime_quota_with_byok")
        self.assertEqual(payload["grant_tokens"], 123)
        self.assertEqual(payload["remaining_tokens"], 123)

        async def _policy_audit_action():
            async with async_session() as db:
                return (
                    await db.execute(
                        select(AIQuotaAuditLog.action)
                        .where(AIQuotaAuditLog.action == "admin_policy_update")
                    )
                ).scalar_one()

        self.assertEqual(self.run_async(_policy_audit_action()), "admin_policy_update")

    def test_admin_can_adjust_and_freeze_single_user_quota_with_audit(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())

        async def _user_id():
            async with async_session() as db:
                return str(
                    (await db.execute(select(User.id).where(User.email == user["email"]))).scalar_one()
                )

        user_id = self.run_async(_user_id())
        initial = self.run_async(
            self.client.get(
                f"/api/admin/users/{user_id}/ai-quota",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(initial.status_code, 200, initial.text)
        self.assertEqual(initial.json()["granted_tokens"], 10000)

        updated = self.run_async(
            self.client.put(
                f"/api/admin/users/{user_id}/ai-quota",
                headers=self._auth_headers(admin["token"]),
                json={
                    "granted_tokens": 25000,
                    "consumed_tokens": 500,
                    "frozen": True,
                    "reason": "客服补偿后冻结复核",
                },
            )
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["remaining_tokens"], 24500)
        self.assertTrue(updated.json()["frozen"])

        async def _audit_count():
            async with async_session() as db:
                return int(await db.scalar(select(func.count(AIQuotaAuditLog.id))) or 0)

        self.assertEqual(self.run_async(_audit_count()), 1)

    def test_solutions_chat_is_blocked_when_estimated_request_exceeds_daily_quota(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "lifetime_quota_with_byok",
                    "lifetime_token_grant": 1,
                    "allow_user_byok": False,
                },
            )
        )

        with patch("app.services.ai_client.ai_client.rag_recommend", new=AsyncMock(return_value=("SHOULD_NOT_RUN", []))) as rag:
            response = self.run_async(
                self.client.post(
                    "/api/solutions/chat",
                    headers=self._auth_headers(user["token"]),
                    json={"message": "请生成一份完整的 GEO 方案"},
                )
            )

        self.assertEqual(response.status_code, 429, response.text)
        self.assertIn("额度", response.text)
        rag.assert_not_awaited()

    def test_invalid_solution_identifiers_are_rejected_before_quota_reservation(self):
        user = self.run_async(self._register_user())

        response = self.run_async(
            self.client.post(
                "/api/solutions/chat",
                headers=self._auth_headers(user["token"]),
                json={
                    "message": "测试非法会话标识",
                    "conversation_id": "invalid-conversation-id",
                    "diagnostic_report_id": "invalid-report-id",
                },
            )
        )

        self.assertEqual(response.status_code, 422, response.text)

        missing_response = self.run_async(
            self.client.post(
                "/api/solutions/chat",
                headers=self._auth_headers(user["token"]),
                json={
                    "message": "测试不存在的会话",
                    "conversation_id": str(uuid.uuid4()),
                },
            )
        )
        self.assertEqual(missing_response.status_code, 404, missing_response.text)

        async def _reservation_count():
            async with async_session() as db:
                return int(await db.scalar(select(func.count(AITokenReservation.id))) or 0)

        self.assertEqual(self.run_async(_reservation_count()), 0)

    def test_global_daily_budget_blocks_every_platform_user_with_byok_guidance(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "lifetime_quota_with_byok",
                    "lifetime_token_grant": 10000,
                    "global_daily_token_limit": 1,
                    "global_budget_enabled": True,
                    "allow_user_byok": True,
                    "metered_modules": ["tools"],
                },
            )
        )

        with patch("app.services.ai_client.ai_client.rag_recommend", new=AsyncMock(return_value=("SHOULD_NOT_RUN", []))) as rag:
            response = self.run_async(
                self.client.post(
                    "/api/solutions/chat",
                    headers=self._auth_headers(user["token"]),
                    json={"message": "请生成一份完整的 GEO 方案"},
                )
            )

        self.assertEqual(response.status_code, 429, response.text)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "global_daily_budget_exhausted")
        self.assertEqual(detail["guidance"]["provider"], "deepseek")
        rag.assert_not_awaited()

    def test_platform_grant_requires_local_device_identifier(self):
        user = self.run_async(self._register_user())
        with patch(
            "app.services.ai_client.ai_client.rag_recommend",
            new=AsyncMock(return_value=("SHOULD_NOT_RUN", [])),
        ) as rag:
            response = self.run_async(
                self.client.post(
                    "/api/solutions/chat",
                    headers={"Authorization": f"Bearer {user['token']}"},
                    json={"message": "设备标识缺失测试"},
                )
            )

        self.assertEqual(response.status_code, 400, response.text)
        rag.assert_not_awaited()

    def test_disabled_byok_ignores_stale_browser_headers(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={"allow_user_byok": False},
            )
        )

        with patch(
            "app.services.ai_client.ai_client.rag_recommend",
            new=AsyncMock(return_value=("PLATFORM_OK", [])),
        ) as rag:
            response = self.run_async(
                self.client.post(
                    "/api/solutions/chat",
                    headers={
                        **self._auth_headers(user["token"]),
                        "X-GEOrank-BYOK-Provider": "deepseek",
                        "X-GEOrank-BYOK-Base-URL": "https://api.deepseek.com",
                        "X-GEOrank-BYOK-Model": "deepseek-v4-flash",
                        "X-GEOrank-BYOK-Key": "stale-browser-key",
                    },
                    json={"message": "继续使用平台额度"},
                )
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(rag.await_args.kwargs["provider_override"])

    def test_platform_fallback_message_releases_reserved_quota(self):
        user = self.run_async(self._register_user())
        with patch(
            "app.services.ai_client.ai_client.rag_recommend",
            new=AsyncMock(side_effect=RuntimeError("provider unavailable")),
        ):
            response = self.run_async(
                self.client.post(
                    "/api/solutions/chat",
                    headers=self._auth_headers(user["token"]),
                    json={"message": "触发平台降级"},
                )
            )

        self.assertEqual(response.status_code, 200, response.text)
        usage = self.run_async(
            self.client.get("/api/usage/me", headers=self._auth_headers(user["token"]))
        ).json()
        self.assertEqual(usage["used_tokens"], 0)
        self.assertEqual(usage["reserved_tokens"], 0)

    def test_byok_required_allows_chat_with_transient_user_key(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "byok_required",
                    "daily_token_limit": 0,
                    "allow_user_byok": True,
                },
            )
        )

        async def fake_raw_chat_complete(**kwargs):
            self.assertEqual(kwargs["api_key"], "user-secret-key")
            self.assertEqual(kwargs["base_url"], "https://api.deepseek.com/v1")
            self.assertEqual(kwargs["model"], "deepseek-chat")
            return "BYOK_OK"

        with patch("app.services.ai_client.ai_client._raw_chat_complete", new=fake_raw_chat_complete):
            response = self.run_async(
                self.client.post(
                    "/api/solutions/chat",
                    headers={
                        **self._auth_headers(user["token"]),
                        "X-GEOrank-BYOK-Provider": "deepseek",
                        "X-GEOrank-BYOK-Base-URL": "https://api.deepseek.com/v1",
                        "X-GEOrank-BYOK-Model": "deepseek-chat",
                        "X-GEOrank-BYOK-Key": "user-secret-key",
                    },
                    json={"message": "什么是 GEO？"},
                )
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["reply"], "BYOK_OK")

    def test_byok_chat_failure_is_not_silently_downgraded(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "byok_required",
                    "daily_token_limit": 0,
                    "allow_user_byok": True,
                },
            )
        )

        async def fake_raw_chat_complete(**kwargs):
            raise RuntimeError("invalid user key")

        with patch("app.services.ai_client.ai_client._raw_chat_complete", new=fake_raw_chat_complete):
            response = self.run_async(
                self.client.post(
                    "/api/solutions/chat",
                    headers={
                        **self._auth_headers(user["token"]),
                        "X-GEOrank-BYOK-Provider": "deepseek",
                        "X-GEOrank-BYOK-Base-URL": "https://api.deepseek.com/v1",
                        "X-GEOrank-BYOK-Model": "deepseek-chat",
                        "X-GEOrank-BYOK-Key": "bad-user-secret",
                    },
                    json={"message": "什么是 GEO？"},
                )
            )

        self.assertEqual(response.status_code, 502, response.text)
        self.assertIn("自定义 API Key 调用失败", response.text)

    def test_byok_proxy_rejects_origin_not_configured_by_admin(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "byok_required",
                    "allow_user_byok": True,
                },
            )
        )

        with patch(
            "app.services.ai_client.ai_client._raw_chat_complete",
            new=AsyncMock(return_value="SHOULD_NOT_RUN"),
        ) as raw_chat:
            response = self.run_async(
                self.client.post(
                    "/api/solutions/chat",
                    headers={
                        **self._auth_headers(user["token"]),
                        "X-GEOrank-BYOK-Provider": "deepseek",
                        "X-GEOrank-BYOK-Base-URL": "http://127.0.0.1:8000/api/private",
                        "X-GEOrank-BYOK-Model": "deepseek-chat",
                        "X-GEOrank-BYOK-Key": "user-secret-key",
                    },
                    json={"message": "什么是 GEO？"},
                )
            )

        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("后台允许", response.text)
        raw_chat.assert_not_awaited()

    def test_async_diagnostic_is_blocked_when_byok_required(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "byok_required",
                    "daily_token_limit": 0,
                    "allow_user_byok": True,
                },
            )
        )

        with patch("app.core.celery_app.celery_app.send_task") as send_task:
            response = self.run_async(
                self.client.post(
                    "/api/diagnostics/",
                    headers=self._auth_headers(user["token"]),
                    json={"url": "https://async-byok-required.example.test"},
                )
            )

        self.assertEqual(response.status_code, 402, response.text)
        self.assertIn("后台任务", response.text)
        send_task.assert_not_called()

    def test_async_company_submit_is_blocked_when_estimate_exceeds_quota(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        bare_domain = f"async-quota-{uuid.uuid4().hex[:8]}.example.test"
        normalized_url = f"https://{bare_domain}"
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "lifetime_quota_with_byok",
                    "lifetime_token_grant": 1,
                    "allow_user_byok": True,
                },
            )
        )

        with patch("app.core.celery_app.celery_app.send_task") as send_task:
            response = self.run_async(
                self.client.post(
                    "/api/companies/submit",
                    headers=self._auth_headers(user["token"]),
                    json={"url": bare_domain},
                )
            )

        self.assertEqual(response.status_code, 429, response.text)
        self.assertIn("赠送", response.text)
        send_task.assert_not_called()

        async def _company_exists():
            async with async_session() as db:
                result = await db.execute(select(Company.id).where(Company.url == normalized_url))
                return result.scalar_one_or_none() is not None

        self.assertFalse(self.run_async(_company_exists()))

    def test_async_task_success_records_daily_usage_and_dashboard_summary(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "lifetime_quota_with_byok",
                    "lifetime_token_grant": 20000,
                    "allow_user_byok": False,
                },
            )
        )

        async def _record_usage():
            async with async_session() as db:
                result = await db.execute(select(User).where(User.email == user["email"]))
                user_row = result.scalar_one()
                await record_async_task_usage(
                    db,
                    module="diagnostics",
                    user_id=user_row.id,
                    input_text="https://async-usage.example.test",
                    output_text="建议补齐 Schema 和 FAQ。",
                    metadata={"report_id": "test-report", "async_task": True},
                )
                await record_async_task_usage(
                    db,
                    module="companies",
                    user_id=user_row.id,
                    status_value="error",
                    error_code="task_failed",
                    estimated_input_tokens=5000,
                    metadata={"company_id": "failed-company", "async_task": True},
                )
                await db.commit()

        self.run_async(_record_usage())

        usage_response = self.run_async(
            self.client.get("/api/usage/me", headers=self._auth_headers(user["token"]))
        )
        self.assertEqual(usage_response.status_code, 200, usage_response.text)
        usage_payload = usage_response.json()
        self.assertGreaterEqual(usage_payload["used_tokens"], 2500)
        self.assertLess(usage_payload["used_tokens"], 5000)
        self.assertEqual(usage_payload["request_count"], 1)

        dashboard_response = self.run_async(
            self.client.get("/api/admin/dashboard", headers=self._auth_headers(admin["token"]))
        )
        self.assertEqual(dashboard_response.status_code, 200, dashboard_response.text)
        async_usage = dashboard_response.json()["async_usage"]
        self.assertGreaterEqual(async_usage["total_tokens"], 2500)
        self.assertLess(async_usage["total_tokens"], 5000)
        self.assertEqual(async_usage["total_requests"], 1)
        self.assertTrue(any(item["module"] == "diagnostics" for item in async_usage["modules"]))
        self.assertFalse(any(item["module"] == "companies" for item in async_usage["modules"]))

    def test_admin_company_retry_checks_original_submitter_quota(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "lifetime_quota_with_byok",
                    "lifetime_token_grant": 10000,
                    "allow_user_byok": False,
                },
            )
        )

        async def _create_company_with_used_quota():
            async with async_session() as db:
                result = await db.execute(select(User).where(User.email == user["email"]))
                user_row = result.scalar_one()
                company = Company(
                    name="usage-policy-retry-company",
                    url=f"https://usage-policy-retry-{uuid.uuid4().hex[:8]}.example.test",
                    pipeline_status=PipelineStatus.FAILED,
                    publish_status=PublishStatus.DRAFT,
                    submitted_by=user_row.id,
                )
                db.add(company)
                db.add(
                    AIUsageEvent(
                        user_id=user_row.id,
                        module="solutions",
                        provider_source="platform",
                        provider="platform",
                        input_tokens=4500,
                        output_tokens=4500,
                        total_tokens=9000,
                        status="success",
                    )
                )
                await db.commit()
                await db.refresh(company)
                return str(company.id)

        company_id = self.run_async(_create_company_with_used_quota())
        with patch("app.core.celery_app.celery_app.send_task") as send_task:
            response = self.run_async(
                self.client.post(
                    f"/api/admin/companies/{company_id}/retry-pipeline",
                    headers=self._auth_headers(admin["token"]),
                )
            )

        self.assertEqual(response.status_code, 429, response.text)
        self.assertIn("赠送", response.text)
        send_task.assert_not_called()

    def test_byok_keywords_failure_is_not_silently_fallback_generated(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "byok_required",
                    "daily_token_limit": 0,
                    "allow_user_byok": True,
                },
            )
        )

        async def fake_raw_chat_complete(**kwargs):
            raise RuntimeError("invalid user key")

        with patch("app.services.ai_client.ai_client._raw_chat_complete", new=fake_raw_chat_complete):
            response = self.run_async(
                self.client.post(
                    "/api/keywords/expand",
                    headers={
                        **self._auth_headers(user["token"]),
                        "X-GEOrank-BYOK-Provider": "deepseek",
                        "X-GEOrank-BYOK-Base-URL": "https://api.deepseek.com/v1",
                        "X-GEOrank-BYOK-Model": "deepseek-chat",
                        "X-GEOrank-BYOK-Key": "bad-user-secret",
                    },
                    json={"seeds": ["GEO优化"]},
                )
            )

        self.assertEqual(response.status_code, 502, response.text)
        self.assertIn("自定义 API Key 调用失败", response.text)

    def test_browser_direct_usage_report_records_non_sensitive_stats_without_daily_quota(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "quota_with_byok",
                    "byok_transport_mode": "browser_direct",
                    "allow_user_byok": True,
                },
            )
        )

        response = self.run_async(
            self.client.post(
                "/api/usage/browser-direct",
                headers=self._auth_headers(user["token"]),
                json={
                    "module": "tools",
                    "tool_key": "title",
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "input_tokens": 12,
                    "output_tokens": 34,
                },
            )
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["total_tokens"], 46)

        async def _read_usage_rows():
            async with async_session() as db:
                user_row = (await db.execute(select(User).where(User.email == user["email"]))).scalar_one()
                event = (
                    await db.execute(
                        select(AIUsageEvent)
                        .where(AIUsageEvent.user_id == user_row.id)
                        .order_by(AIUsageEvent.created_at.desc())
                    )
                ).scalars().first()
                daily = (
                    await db.execute(select(UserDailyUsage).where(UserDailyUsage.user_id == user_row.id))
                ).scalar_one_or_none()
                return event, daily

        event, daily = self.run_async(_read_usage_rows())
        self.assertIsNotNone(event)
        self.assertEqual(event.module, "tools")
        self.assertEqual(event.provider_source, "user_byok_browser_direct")
        self.assertEqual(event.provider, "deepseek")
        self.assertEqual(event.model, "deepseek-chat")
        self.assertEqual(event.total_tokens, 46)
        self.assertIsNone(daily)

    def test_browser_direct_usage_report_rejects_api_key_payload(self):
        admin = self.run_async(self._register_user(admin=True))
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "byok_transport_mode": "browser_direct",
                    "allow_user_byok": True,
                },
            )
        )

        response = self.run_async(
            self.client.post(
                "/api/usage/browser-direct",
                json={
                    "module": "tools",
                    "tool_key": "jsonld",
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "input_text": "输入",
                    "output_text": "输出",
                    "api_key": "must-not-be-accepted",
                },
            )
        )

        self.assertEqual(response.status_code, 422, response.text)

    def test_browser_direct_usage_report_requires_login_by_default(self):
        admin = self.run_async(self._register_user(admin=True))
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "byok_transport_mode": "browser_direct",
                    "allow_user_byok": True,
                    "allow_anonymous_ai_usage": False,
                },
            )
        )

        response = self.run_async(
            self.client.post(
                "/api/usage/browser-direct",
                json={
                    "module": "tools",
                    "provider": "deepseek",
                    "model": "deepseek-v4-flash",
                    "input_tokens": 1,
                    "output_tokens": 1,
                },
            )
        )

        self.assertEqual(response.status_code, 401, response.text)

    def test_browser_direct_usage_report_rejects_prompt_payload(self):
        admin = self.run_async(self._register_user(admin=True))
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "byok_transport_mode": "browser_direct",
                    "allow_user_byok": True,
                },
            )
        )

        response = self.run_async(
            self.client.post(
                "/api/usage/browser-direct",
                json={
                    "module": "tools",
                    "tool_key": "kb",
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "input_text": "不应上传到后台的用户输入",
                    "output_text": "不应上传到后台的模型输出",
                    "input_tokens": 12,
                    "output_tokens": 34,
                },
            )
        )

        self.assertEqual(response.status_code, 422, response.text)


if __name__ == "__main__":
    unittest.main()
