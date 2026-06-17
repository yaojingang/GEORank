import asyncio
import sys
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import delete, or_, select, update

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models.ai_usage import AIUsageEvent, UserDailyUsage  # noqa: E402
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
        return {"Authorization": f"Bearer {token}"}

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
        self.assertEqual(payload["access_mode"], "platform_unlimited")
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
                    "access_mode": "daily_quota",
                    "daily_token_limit": 123,
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
        self.assertEqual(payload["access_mode"], "daily_quota")
        self.assertEqual(payload["daily_token_limit"], 123)
        self.assertEqual(payload["remaining_tokens"], 123)

    def test_solutions_chat_is_blocked_when_estimated_request_exceeds_daily_quota(self):
        admin = self.run_async(self._register_user(admin=True))
        user = self.run_async(self._register_user())
        self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json={
                    "access_mode": "daily_quota",
                    "daily_token_limit": 1,
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
        self.assertIn("异步任务", response.text)
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
                    "access_mode": "daily_quota",
                    "daily_token_limit": 1,
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
        self.assertIn("额度不足", response.text)
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
                    "access_mode": "daily_quota",
                    "daily_token_limit": 20000,
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
                    "access_mode": "daily_quota",
                    "daily_token_limit": 10000,
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
                    UserDailyUsage(
                        user_id=user_row.id,
                        usage_date=date.today(),
                        total_tokens=9000,
                        request_count=1,
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
        self.assertIn("额度不足", response.text)
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
