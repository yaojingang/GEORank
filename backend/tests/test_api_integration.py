import sys
import asyncio
import copy
import io
import os
import tempfile
import unittest
import uuid
import zipfile
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.database_safety import resolve_test_database, verify_test_database_engine  # noqa: E402
from app.core.database import async_session, engine  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models.company import Company, PipelineStatus, PublishStatus  # noqa: E402
from app.models.content import Content, ContentStatus, ContentType  # noqa: E402
from app.models.conversation import Conversation, Message, MessageRole  # noqa: E402
from app.models.diagnostic import DiagnosticReport, DiagnosticStatus  # noqa: E402
from app.models.expert import ExpertProfile  # noqa: E402
from app.models.homepage import HomepageRelease, HomepageReleaseStatus, HomepageSourceType  # noqa: E402
from app.models.ai_usage import AIUsageEvent, UserDailyUsage  # noqa: E402
from app.models.keyword import KeywordItem, KeywordPack  # noqa: E402
from app.models.settings import Setting  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.models.vote import CompanyVote  # noqa: E402
from app.services.runtime_settings import (  # noqa: E402
    get_homepage_runtime_config,
    get_default_solution_template_config,
    invalidate_runtime_settings_cache,
)
from app.services.settings_security import (  # noqa: E402
    MASKED_VALUE,
    decrypt_setting_value,
    is_encrypted_setting_value,
)


TEST_EMAIL_PREFIX = "codex_it_"
TEST_USERNAME_PREFIX = "codex_it_"
TEST_PHONE_PREFIX = "1390000"
TEST_COMPANY_URL_PREFIX = "https://codex-it-"
TEST_SETTING_PREFIX = "codex_it_"
TEST_CONTENT_SLUG_PREFIX = "codex-it-content-"
TEST_KEYWORD_TITLE_PREFIX = "codex-it-keyword-"
TEST_EXPERT_NAME_PREFIX = "Codex Expert "
TEST_HOMEPAGE_TITLE_PREFIX = "Codex Homepage "
TEST_USAGE_REQUEST_PREFIX = "codex_it_usage_"
TEST_PASSWORD = "Test-Codex-2026-Aa"
_TEST_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_TEST_LOOP)


class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_url, database_name = resolve_test_database(
            default_database_url=settings.DATABASE_URL,
            configured_database_name=os.environ.get("POSTGRES_DB"),
            explicit_test_database_url=os.environ.get("TEST_DATABASE_URL"),
        )
        _TEST_LOOP.run_until_complete(
            verify_test_database_engine(engine, database_url, database_name)
        )

    @classmethod
    def tearDownClass(cls):
        _TEST_LOOP.run_until_complete(engine.dispose())
        _TEST_LOOP.close()

    def run_async(self, coro):
        return _TEST_LOOP.run_until_complete(coro)

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
            company_ids = list(
                (
                    await db.execute(
                        select(Company.id).where(Company.url.like(f"{TEST_COMPANY_URL_PREFIX}%"))
                    )
                ).scalars()
            )

            if company_ids:
                await db.execute(delete(CompanyVote).where(CompanyVote.company_id.in_(company_ids)))
            if user_ids:
                await db.execute(delete(UserDailyUsage).where(UserDailyUsage.user_id.in_(user_ids)))
                await db.execute(delete(AIUsageEvent).where(AIUsageEvent.user_id.in_(user_ids)))
                await db.execute(delete(CompanyVote).where(CompanyVote.user_id.in_(user_ids)))
                await db.execute(delete(DiagnosticReport).where(DiagnosticReport.user_id.in_(user_ids)))
                await db.execute(delete(Message).where(Message.conversation_id.in_(
                    select(Conversation.id).where(Conversation.user_id.in_(user_ids))
                )))
                await db.execute(delete(Conversation).where(Conversation.user_id.in_(user_ids)))
            await db.execute(delete(AIUsageEvent).where(AIUsageEvent.request_id.like(f"{TEST_USAGE_REQUEST_PREFIX}%")))
            keyword_cleanup_conditions = [KeywordPack.title.like(f"{TEST_KEYWORD_TITLE_PREFIX}%")]
            if user_ids:
                keyword_cleanup_conditions.append(KeywordPack.created_by.in_(user_ids))
            keyword_pack_ids = list(
                (
                    await db.execute(
                        select(KeywordPack.id).where(or_(*keyword_cleanup_conditions))
                    )
                ).scalars()
            )
            if keyword_pack_ids:
                await db.execute(delete(KeywordItem).where(KeywordItem.pack_id.in_(keyword_pack_ids)))
                await db.execute(delete(KeywordPack).where(KeywordPack.id.in_(keyword_pack_ids)))
            await db.execute(delete(ExpertProfile).where(ExpertProfile.display_name.like(f"{TEST_EXPERT_NAME_PREFIX}%")))
            await db.execute(delete(HomepageRelease).where(HomepageRelease.title.like(f"{TEST_HOMEPAGE_TITLE_PREFIX}%")))
            await db.execute(delete(Content).where(Content.slug.like(f"{TEST_CONTENT_SLUG_PREFIX}%")))
            await db.execute(delete(Setting).where(Setting.key.like(f"{TEST_SETTING_PREFIX}%")))
            if company_ids:
                await db.execute(delete(Company).where(Company.id.in_(company_ids)))
            if user_ids:
                await db.execute(delete(User).where(User.id.in_(user_ids)))
            await db.commit()

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _zip_bytes(self, files: dict[str, bytes | str]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                data = content.encode("utf-8") if isinstance(content, str) else content
                archive.writestr(name, data)
        return buffer.getvalue()

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
                await db.execute(
                    update(User).where(User.email == email).values(role=UserRole.ADMIN)
                )
                await db.commit()

        return {"email": email, "username": username, "phone": phone, "token": token}

    async def _get_setting(self, key: str) -> Setting | None:
        async with async_session() as db:
            result = await db.execute(select(Setting).where(Setting.key == key))
            return result.scalar_one_or_none()

    async def _snapshot_settings(self, keys: tuple[str, ...]) -> dict[str, dict | None]:
        async with async_session() as db:
            rows = (
                await db.execute(select(Setting).where(Setting.key.in_(keys)))
            ).scalars().all()
            by_key = {row.key: row for row in rows}
            return {
                key: None if key not in by_key else {
                    "value": by_key[key].value,
                    "category": by_key[key].category,
                    "is_public": by_key[key].is_public,
                    "updated_by": by_key[key].updated_by,
                }
                for key in keys
            }

    async def _restore_settings(self, snapshot: dict[str, dict | None]):
        async with async_session() as db:
            for key, values in snapshot.items():
                if values is None:
                    await db.execute(delete(Setting).where(Setting.key == key))
                else:
                    await db.execute(update(Setting).where(Setting.key == key).values(**values))
            await db.commit()
        await invalidate_runtime_settings_cache()

    def test_auth_register_login_and_me(self):
        user = self.run_async(self._register_user())

        login_response = self.run_async(
            self.client.post(
                "/api/auth/login",
                json={"username": user["username"], "password": TEST_PASSWORD},
            )
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)
        login_token = login_response.json()["access_token"]

        me_response = self.run_async(
            self.client.get("/api/auth/me", headers=self._auth_headers(login_token))
        )
        self.assertEqual(me_response.status_code, 200, me_response.text)
        me = me_response.json()
        self.assertEqual(me["email"], user["email"])
        self.assertEqual(me["username"], user["username"])
        self.assertEqual(me["phone"], user["phone"])
        self.assertEqual(me["role"], "user")

        duplicate_response = self.run_async(
            self.client.post(
                "/api/auth/register",
                json={"email": user["email"], "username": user["username"], "password": TEST_PASSWORD},
            )
        )
        self.assertEqual(duplicate_response.status_code, 409, duplicate_response.text)

    def test_auth_phone_register_and_phone_login(self):
        phone = f"{TEST_PHONE_PREFIX}{str(uuid.uuid4().int)[-4:]}"
        response = self.run_async(
            self.client.post(
                "/api/auth/register",
                json={"phone": phone, "password": TEST_PASSWORD},
            )
        )
        self.assertEqual(response.status_code, 201, response.text)

        login_response = self.run_async(
            self.client.post(
                "/api/auth/login",
                json={"phone": phone, "password": TEST_PASSWORD},
            )
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)

        me_response = self.run_async(
            self.client.get(
                "/api/auth/me",
                headers=self._auth_headers(login_response.json()["access_token"]),
            )
        )
        self.assertEqual(me_response.status_code, 200, me_response.text)
        self.assertEqual(me_response.json()["phone"], phone)

    def test_auth_profile_update_and_password_change(self):
        user = self.run_async(self._register_user())
        suffix = uuid.uuid4().hex[:8]
        next_username = f"{TEST_USERNAME_PREFIX}profile_{suffix}"
        next_email = f"{TEST_EMAIL_PREFIX}profile_{suffix}@example.com"
        next_phone = f"{TEST_PHONE_PREFIX}{str(uuid.uuid4().int)[-4:]}"
        next_password = "Test-CodexChanged-2026-Aa"

        update_response = self.run_async(
            self.client.put(
                "/api/auth/me",
                headers=self._auth_headers(user["token"]),
                json={
                    "username": next_username,
                    "email": next_email,
                    "phone": next_phone,
                },
            )
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)
        updated = update_response.json()
        self.assertEqual(updated["username"], next_username)
        self.assertEqual(updated["email"], next_email)
        self.assertEqual(updated["phone"], next_phone)

        clear_phone_response = self.run_async(
            self.client.put(
                "/api/auth/me",
                headers=self._auth_headers(user["token"]),
                json={"phone": None},
            )
        )
        self.assertEqual(clear_phone_response.status_code, 200, clear_phone_response.text)
        self.assertIsNone(clear_phone_response.json()["phone"])

        cleared_phone_login_response = self.run_async(
            self.client.post(
                "/api/auth/login",
                json={"phone": next_phone, "password": TEST_PASSWORD},
            )
        )
        self.assertEqual(cleared_phone_login_response.status_code, 401, cleared_phone_login_response.text)

        restore_phone_response = self.run_async(
            self.client.put(
                "/api/auth/me",
                headers=self._auth_headers(user["token"]),
                json={"phone": next_phone},
            )
        )
        self.assertEqual(restore_phone_response.status_code, 200, restore_phone_response.text)
        self.assertEqual(restore_phone_response.json()["phone"], next_phone)

        phone_login_response = self.run_async(
            self.client.post(
                "/api/auth/login",
                json={"phone": next_phone, "password": TEST_PASSWORD},
            )
        )
        self.assertEqual(phone_login_response.status_code, 200, phone_login_response.text)

        password_response = self.run_async(
            self.client.put(
                "/api/auth/password",
                headers=self._auth_headers(user["token"]),
                json={
                    "current_password": TEST_PASSWORD,
                    "new_password": next_password,
                },
            )
        )
        self.assertEqual(password_response.status_code, 200, password_response.text)

        revoked_token_response = self.run_async(
            self.client.get(
                "/api/auth/me",
                headers=self._auth_headers(user["token"]),
            )
        )
        self.assertEqual(revoked_token_response.status_code, 401, revoked_token_response.text)

        old_password_response = self.run_async(
            self.client.post(
                "/api/auth/login",
                json={"phone": next_phone, "password": TEST_PASSWORD},
            )
        )
        self.assertEqual(old_password_response.status_code, 401, old_password_response.text)

        new_password_response = self.run_async(
            self.client.post(
                "/api/auth/login",
                json={"phone": next_phone, "password": next_password},
            )
        )
        self.assertEqual(new_password_response.status_code, 200, new_password_response.text)

    def test_admin_settings_masks_sensitive_values_and_exposes_public_values(self):
        admin = self.run_async(self._register_user(admin=True))
        sensitive_key = f"{TEST_SETTING_PREFIX}{uuid.uuid4().hex[:8]}_api_key"
        public_key = f"{TEST_SETTING_PREFIX}{uuid.uuid4().hex[:8]}_public"

        update_response = self.run_async(
            self.client.put(
                "/api/admin/settings",
                headers=self._auth_headers(admin["token"]),
                json={
                    sensitive_key: {
                        "value": "sk-integration-secret",
                        "category": "api_keys",
                        "is_public": True,
                    },
                    public_key: {"value": "hello-world", "is_public": True},
                },
            )
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)

        admin_settings_response = self.run_async(
            self.client.get(
                "/api/admin/settings",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(admin_settings_response.status_code, 200, admin_settings_response.text)
        admin_settings = admin_settings_response.json()
        self.assertEqual(admin_settings[sensitive_key]["value"], MASKED_VALUE)
        self.assertEqual(admin_settings[public_key]["value"], "hello-world")

        public_response = self.run_async(self.client.get("/api/settings/public"))
        self.assertEqual(public_response.status_code, 200, public_response.text)
        self.assertEqual(public_response.json()[public_key], "hello-world")

        stored_setting = self.run_async(self._get_setting(sensitive_key))
        self.assertIsNotNone(stored_setting)
        self.assertTrue(is_encrypted_setting_value(stored_setting.value))
        self.assertFalse(stored_setting.is_public)

        async def _force_legacy_public_flag():
            async with async_session() as db:
                await db.execute(
                    update(Setting).where(Setting.key == sensitive_key).values(is_public=True)
                )
                await db.commit()

        self.run_async(_force_legacy_public_flag())
        defensive_public_response = self.run_async(self.client.get("/api/settings/public"))
        self.assertEqual(defensive_public_response.status_code, 200, defensive_public_response.text)
        self.assertNotIn(sensitive_key, defensive_public_response.json())

        category_only_key = f"codex_it_custom_credential_{uuid.uuid4().hex}"
        create_category_sensitive = self.run_async(
            self.client.put(
                "/api/admin/settings",
                headers=self._auth_headers(admin["token"]),
                json={category_only_key: {"value": "category-secret", "category": "api_keys"}},
            )
        )
        self.assertEqual(create_category_sensitive.status_code, 200, create_category_sensitive.text)
        downgrade_category = self.run_async(
            self.client.put(
                "/api/admin/settings",
                headers=self._auth_headers(admin["token"]),
                json={
                    category_only_key: {
                        "value": "replacement-secret",
                        "category": "basic",
                        "is_public": True,
                    }
                },
            )
        )
        self.assertEqual(downgrade_category.status_code, 200, downgrade_category.text)
        downgraded_setting = self.run_async(self._get_setting(category_only_key))
        self.assertEqual(downgraded_setting.category, "api_keys")
        self.assertFalse(downgraded_setting.is_public)
        self.assertTrue(is_encrypted_setting_value(downgraded_setting.value))

    def test_llm_provider_test_rejects_redirects_without_following_them(self):
        admin = self.run_async(self._register_user(admin=True))
        redirect_response = MagicMock(
            status_code=302,
            is_redirect=True,
            is_error=False,
            text="redirect",
        )
        redirect_response.json.return_value = {}
        fake_client = MagicMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=None)
        fake_client.post = AsyncMock(return_value=redirect_response)

        with (
            patch(
                "app.api.routes.admin._validate_llm_provider_target",
                new=AsyncMock(return_value="https://provider.example/v1/chat/completions"),
            ),
            patch(
                "app.api.routes.admin.build_provider_http_client",
                return_value=fake_client,
            ) as client_factory,
        ):
            response = self.run_async(
                self.client.post(
                    "/api/admin/llm-providers/test",
                    headers=self._auth_headers(admin["token"]),
                    json={
                        "provider": {
                            "id": "redirect-test",
                            "name": "Redirect test",
                            "base_url": "https://provider.example/v1",
                            "model": "test-model",
                            "api_key": "test-explicit-key",
                            "enabled": True,
                            "priority": 1,
                        }
                    },
                )
            )

        self.assertEqual(response.status_code, 502, response.text)
        client_factory.assert_called_once_with(timeout=20.0)
        fake_client.post.assert_awaited_once()

    def test_llm_provider_persistence_rejects_private_targets(self):
        admin = self.run_async(self._register_user(admin=True))
        response = self.run_async(
            self.client.put(
                "/api/admin/llm-providers",
                headers=self._auth_headers(admin["token"]),
                json={
                    "strategy": "failover",
                    "providers": [
                        {
                            "id": "private-target",
                            "name": "Private target",
                            "base_url": "https://127.0.0.1/v1",
                            "model": "test-model",
                            "api_key": "test-explicit-key",
                            "enabled": True,
                            "priority": 1,
                        }
                    ],
                },
            )
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("非公网网络", response.json()["detail"])

    def test_legacy_provider_urls_require_new_credentials_for_effective_key_fallbacks(self):
        admin = self.run_async(self._register_user(admin=True))
        runtime_config = {
            "llm_api_key": "test-environment-llm-key",
            "llm_base_url": "https://example.com/v1",
            "codex_api_key": "test-environment-codex-key",
            "codex_base_url": "https://example.com/v1",
            "embedding_api_key": "test-environment-embedding-key",
            "embedding_base_url": "https://example.com/v1",
        }
        bindings = (
            ("llm_base_url", "llm_api_key"),
            ("codex_base_url", "codex_api_key"),
            ("embedding_base_url", "embedding_api_key"),
        )

        for base_key, credential_key in bindings:
            with self.subTest(base_key=base_key), patch(
                "app.api.routes.admin.get_ai_runtime_config",
                new=AsyncMock(return_value=runtime_config),
            ):
                response = self.run_async(
                    self.client.put(
                        "/api/admin/settings",
                        headers=self._auth_headers(admin["token"]),
                        json={
                            base_key: {"value": "https://example.org/v1", "category": "llm"},
                            credential_key: {
                                "value": MASKED_VALUE,
                                "category": "api_keys",
                            },
                        },
                    )
                )
            self.assertEqual(response.status_code, 400, response.text)
            self.assertIn(credential_key, response.json()["detail"])

    def test_legacy_provider_url_change_accepts_an_explicit_replacement_key(self):
        admin = self.run_async(self._register_user(admin=True))
        snapshot = self.run_async(
            self._snapshot_settings(("llm_base_url", "llm_api_key", "codex_api_key"))
        )
        self.run_async(self._restore_settings({"codex_api_key": None}))
        runtime_config = {
            "llm_api_key": "test-environment-llm-key",
            "llm_base_url": "https://example.com/v1",
            "codex_api_key": "test-environment-llm-key",
            "codex_base_url": "https://example.com/v1",
            "embedding_api_key": "",
            "embedding_base_url": "",
        }
        try:
            with (
                patch(
                    "app.api.routes.admin.get_ai_runtime_config",
                    new=AsyncMock(return_value=runtime_config),
                ),
                patch(
                    "app.api.routes.admin.validate_provider_base_url",
                    new=AsyncMock(return_value="https://example.org/v1"),
                ) as validate_url,
                patch("app.core.config.settings.CODEX_API_KEY", ""),
            ):
                response = self.run_async(
                    self.client.put(
                        "/api/admin/settings",
                        headers=self._auth_headers(admin["token"]),
                        json={
                            "llm_base_url": {
                                "value": "https://example.org/v1",
                                "category": "llm",
                            },
                            "llm_api_key": {
                                "value": "explicit-replacement-key",
                                "category": "api_keys",
                            },
                        },
                    )
                )
            self.assertEqual(response.status_code, 200, response.text)
            validate_url.assert_awaited_once_with("https://example.org/v1")
        finally:
            self.run_async(self._restore_settings(snapshot))

    def test_llm_url_change_requires_distinct_codex_fallback_key_replacement(self):
        admin = self.run_async(self._register_user(admin=True))
        runtime_config = {
            "llm_api_key": "test-environment-llm-key",
            "llm_base_url": "https://example.com/v1",
            "codex_api_key": "test-distinct-codex-key",
            "codex_base_url": "https://example.com/v1",
            "embedding_api_key": "",
            "embedding_base_url": "",
        }
        with patch(
            "app.api.routes.admin.get_ai_runtime_config",
            new=AsyncMock(return_value=runtime_config),
        ), patch("app.core.config.settings.CODEX_API_KEY", "test-distinct-codex-key"):
            response = self.run_async(
                self.client.put(
                    "/api/admin/settings",
                    headers=self._auth_headers(admin["token"]),
                    json={
                        "llm_base_url": {"value": "https://example.org/v1", "category": "llm"},
                        "llm_api_key": {
                            "value": "explicit-replacement-key",
                            "category": "api_keys",
                        },
                        "codex_api_key": {"value": MASKED_VALUE, "category": "api_keys"},
                    },
                )
            )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("codex_api_key", response.json()["detail"])

    def test_llm_url_change_requires_separately_stored_equal_codex_key(self):
        admin = self.run_async(self._register_user(admin=True))
        snapshot = self.run_async(
            self._snapshot_settings(("llm_base_url", "llm_api_key", "codex_api_key"))
        )
        try:
            seed_response = self.run_async(
                self.client.put(
                    "/api/admin/settings",
                    headers=self._auth_headers(admin["token"]),
                    json={
                        "codex_api_key": {
                            "value": "test-shared-old-key",
                            "category": "api_keys",
                        }
                    },
                )
            )
            self.assertEqual(seed_response.status_code, 200, seed_response.text)
            runtime_config = {
                "llm_api_key": "test-shared-old-key",
                "llm_base_url": "https://example.com/v1",
                "codex_api_key": "test-shared-old-key",
                "codex_base_url": "https://example.com/v1",
                "embedding_api_key": "",
                "embedding_base_url": "",
            }
            with patch(
                "app.api.routes.admin.get_ai_runtime_config",
                new=AsyncMock(return_value=runtime_config),
            ), patch("app.core.config.settings.CODEX_API_KEY", ""):
                response = self.run_async(
                    self.client.put(
                        "/api/admin/settings",
                        headers=self._auth_headers(admin["token"]),
                        json={
                            "llm_base_url": {
                                "value": "https://example.org/v1",
                                "category": "llm",
                            },
                            "llm_api_key": {
                                "value": "explicit-replacement-key",
                                "category": "api_keys",
                            },
                        },
                    )
                )
            self.assertEqual(response.status_code, 400, response.text)
            self.assertIn("codex_api_key", response.json()["detail"])
        finally:
            self.run_async(self._restore_settings(snapshot))

    def test_legacy_provider_replacement_credentials_must_be_nonempty_strings(self):
        admin = self.run_async(self._register_user(admin=True))
        runtime_config = {
            "llm_api_key": "test-environment-llm-key",
            "llm_base_url": "https://example.com/v1",
            "codex_api_key": "test-environment-llm-key",
            "codex_base_url": "https://example.com/v1",
            "embedding_api_key": "",
            "embedding_base_url": "",
        }
        for invalid_key in ({"unexpected": "object"}, 123):
            with self.subTest(invalid_key=invalid_key), patch(
                "app.api.routes.admin.get_ai_runtime_config",
                new=AsyncMock(return_value=runtime_config),
            ):
                response = self.run_async(
                    self.client.put(
                        "/api/admin/settings",
                        headers=self._auth_headers(admin["token"]),
                        json={
                            "llm_base_url": {
                                "value": "https://example.org/v1",
                                "category": "llm",
                            },
                            "llm_api_key": {"value": invalid_key, "category": "api_keys"},
                        },
                    )
                )
            self.assertEqual(response.status_code, 400, response.text)
            self.assertIn("llm_api_key", response.json()["detail"])

    def test_generic_settings_rejects_structured_provider_keys(self):
        admin = self.run_async(self._register_user(admin=True))
        for managed_key in ("llm_providers", "llm_provider_keys"):
            with self.subTest(managed_key=managed_key):
                response = self.run_async(
                    self.client.put(
                        "/api/admin/settings",
                        headers=self._auth_headers(admin["token"]),
                        json={managed_key: {"value": {}, "category": "llm"}},
                    )
                )
            self.assertEqual(response.status_code, 400, response.text)
            self.assertIn("专用 API", response.json()["detail"])

    def test_admin_can_delete_custom_setting_but_not_protected_setting(self):
        admin = self.run_async(self._register_user(admin=True))
        custom_key = f"{TEST_SETTING_PREFIX}{uuid.uuid4().hex[:8]}_delete_custom"

        create_response = self.run_async(
            self.client.put(
                "/api/admin/settings",
                headers=self._auth_headers(admin["token"]),
                json={custom_key: {"value": {"enabled": True}, "category": "test"}},
            )
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)

        delete_response = self.run_async(
            self.client.delete(
                f"/api/admin/settings/{custom_key}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(delete_response.status_code, 200, delete_response.text)

        deleted_setting = self.run_async(self._get_setting(custom_key))
        self.assertIsNone(deleted_setting)

        protected_response = self.run_async(
            self.client.delete(
                "/api/admin/settings/site_name",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(protected_response.status_code, 400, protected_response.text)

    def test_admin_settings_normalizes_and_validates_admin_entry_path(self):
        admin = self.run_async(self._register_user(admin=True))

        async def _capture_setting():
            async with async_session() as db:
                result = await db.execute(select(Setting).where(Setting.key == "admin_entry_path"))
                setting = result.scalar_one_or_none()
                if not setting:
                    return None
                return {
                    "value": copy.deepcopy(setting.value),
                    "category": setting.category,
                    "is_public": setting.is_public,
                    "updated_by": setting.updated_by,
                }

        async def _restore_setting(snapshot):
            async with async_session() as db:
                result = await db.execute(select(Setting).where(Setting.key == "admin_entry_path"))
                setting = result.scalar_one_or_none()
                if snapshot is None:
                    if setting:
                        await db.execute(delete(Setting).where(Setting.key == "admin_entry_path"))
                elif setting:
                    await db.execute(
                        update(Setting)
                        .where(Setting.key == "admin_entry_path")
                        .values(**snapshot)
                    )
                else:
                    db.add(Setting(key="admin_entry_path", **snapshot))
                await db.commit()
            await invalidate_runtime_settings_cache()

        snapshot = self.run_async(_capture_setting())
        try:
            valid_response = self.run_async(
                self.client.put(
                    "/api/admin/settings",
                    headers=self._auth_headers(admin["token"]),
                    json={"admin_entry_path": {"value": "admin-review"}},
                )
            )
            self.assertEqual(valid_response.status_code, 200, valid_response.text)

            settings_response = self.run_async(
                self.client.get("/api/admin/settings", headers=self._auth_headers(admin["token"]))
            )
            self.assertEqual(settings_response.status_code, 200, settings_response.text)
            setting = settings_response.json()["admin_entry_path"]
            self.assertEqual(setting["value"], "/admin-review")
            self.assertEqual(setting["category"], "security")
            self.assertFalse(setting["is_public"])

            invalid_response = self.run_async(
                self.client.put(
                    "/api/admin/settings",
                    headers=self._auth_headers(admin["token"]),
                    json={"admin_entry_path": {"value": "https://example.com/admin"}},
                )
            )
            self.assertEqual(invalid_response.status_code, 422, invalid_response.text)

            stored_setting = self.run_async(self._get_setting("admin_entry_path"))
            self.assertIsNotNone(stored_setting)
            self.assertEqual(stored_setting.value, "/admin-review")
        finally:
            self.run_async(_restore_setting(snapshot))

    def test_admin_frontend_modules_can_disable_company_and_public_endpoint_reflects_it(self):
        admin = self.run_async(self._register_user(admin=True))

        async def _capture_frontend_modules_setting():
            async with async_session() as db:
                result = await db.execute(select(Setting).where(Setting.key == "frontend_modules"))
                setting = result.scalar_one_or_none()
                if not setting:
                    return None
                return {
                    "value": copy.deepcopy(setting.value),
                    "category": setting.category,
                    "is_public": setting.is_public,
                    "updated_by": setting.updated_by,
                }

        async def _restore_frontend_modules_setting(snapshot):
            async with async_session() as db:
                result = await db.execute(select(Setting).where(Setting.key == "frontend_modules"))
                setting = result.scalar_one_or_none()
                if snapshot is None:
                    if setting:
                        await db.execute(delete(Setting).where(Setting.key == "frontend_modules"))
                elif setting:
                    setting.value = snapshot["value"]
                    setting.category = snapshot["category"]
                    setting.is_public = snapshot["is_public"]
                    setting.updated_by = snapshot["updated_by"]
                else:
                    db.add(
                        Setting(
                            key="frontend_modules",
                            value=snapshot["value"],
                            category=snapshot["category"],
                            is_public=snapshot["is_public"],
                            updated_by=snapshot["updated_by"],
                        )
                    )
                await db.commit()
            await invalidate_runtime_settings_cache()

        snapshot = self.run_async(_capture_frontend_modules_setting())
        try:
            get_response = self.run_async(
                self.client.get(
                    "/api/admin/frontend-modules",
                    headers=self._auth_headers(admin["token"]),
                )
            )
            self.assertEqual(get_response.status_code, 200, get_response.text)
            modules = get_response.json()["modules"]
            payload_modules = [
                {"key": item["key"], "enabled": item["key"] != "companies"}
                for item in modules
            ]

            update_response = self.run_async(
                self.client.put(
                    "/api/admin/frontend-modules",
                    headers=self._auth_headers(admin["token"]),
                    json={"default_module": "tools", "modules": payload_modules},
                )
            )
            self.assertEqual(update_response.status_code, 200, update_response.text)
            updated = update_response.json()
            self.assertEqual(updated["default_module"], "tools")
            updated_modules = {item["key"]: item for item in updated["modules"]}
            self.assertFalse(updated_modules["companies"]["enabled"])
            self.assertTrue(updated_modules["tools"]["is_default"])

            public_response = self.run_async(self.client.get("/api/settings/frontend-modules"))
            self.assertEqual(public_response.status_code, 200, public_response.text)
            public_payload = public_response.json()
            public_modules = {item["key"]: item for item in public_payload["modules"]}
            self.assertEqual(public_payload["default_module"], "tools")
            self.assertFalse(public_modules["companies"]["enabled"])
            self.assertIn("/", public_modules["companies"]["protected_paths"])
        finally:
            self.run_async(_restore_frontend_modules_setting(snapshot))

    def test_admin_frontend_modules_rejects_disabling_all_modules(self):
        admin = self.run_async(self._register_user(admin=True))
        get_response = self.run_async(
            self.client.get(
                "/api/admin/frontend-modules",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(get_response.status_code, 200, get_response.text)
        modules = [{"key": item["key"], "enabled": False} for item in get_response.json()["modules"]]

        response = self.run_async(
            self.client.put(
                "/api/admin/frontend-modules",
                headers=self._auth_headers(admin["token"]),
                json={"default_module": "companies", "modules": modules},
            )
        )

        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("至少需要保留一个前台模块开启", response.text)

    def test_admin_frontend_modules_rejects_unknown_module_keys(self):
        admin = self.run_async(self._register_user(admin=True))
        response = self.run_async(
            self.client.put(
                "/api/admin/frontend-modules",
                headers=self._auth_headers(admin["token"]),
                json={
                    "default_module": "ghost",
                    "modules": [{"key": "ghost", "enabled": True}],
                },
            )
        )

        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("未知前台模块", response.text)

    def test_admin_homepage_upload_activate_and_restore_default(self):
        admin = self.run_async(self._register_user(admin=True))

        async def _capture_homepage_runtime_setting():
            async with async_session() as db:
                result = await db.execute(select(Setting).where(Setting.key == "homepage_runtime"))
                setting = result.scalar_one_or_none()
                if not setting:
                    return None
                return {
                    "value": copy.deepcopy(setting.value),
                    "category": setting.category,
                    "is_public": setting.is_public,
                    "updated_by": setting.updated_by,
                }

        async def _restore_homepage_runtime_setting(snapshot):
            async with async_session() as db:
                result = await db.execute(select(Setting).where(Setting.key == "homepage_runtime"))
                setting = result.scalar_one_or_none()
                if snapshot is None:
                    if setting:
                        await db.execute(delete(Setting).where(Setting.key == "homepage_runtime"))
                elif setting:
                    setting.value = snapshot["value"]
                    setting.category = snapshot["category"]
                    setting.is_public = snapshot["is_public"]
                    setting.updated_by = snapshot["updated_by"]
                else:
                    db.add(
                        Setting(
                            key="homepage_runtime",
                            value=snapshot["value"],
                            category=snapshot["category"],
                            is_public=snapshot["is_public"],
                            updated_by=snapshot["updated_by"],
                        )
                    )
                await db.commit()
            await invalidate_runtime_settings_cache()

        snapshot = self.run_async(_capture_homepage_runtime_setting())
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"GEORANK_HOMEPAGE_ROOT": tmpdir}):
            try:
                payload = self._zip_bytes(
                    {
                        "index.html": """
                        <html>
                          <head><title>Codex custom home</title></head>
                          <body>
                            <img src="./assets/logo.png" onerror="alert(1)">
                            <script>window.__bad = true</script>
                            <h1>自定义首页</h1>
                          </body>
                        </html>
                        """,
                        "assets/logo.png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
                    }
                )

                upload_response = self.run_async(
                    self.client.post(
                        "/api/admin/homepage/releases",
                        headers=self._auth_headers(admin["token"]),
                        data={"source_type": "zip_package", "title": f"{TEST_HOMEPAGE_TITLE_PREFIX}{uuid.uuid4().hex[:8]}"},
                        files={"file": ("homepage.zip", payload, "application/zip")},
                    )
                )
                self.assertEqual(upload_response.status_code, 201, upload_response.text)
                release = upload_response.json()
                self.assertEqual(release["status"], "draft")
                self.assertEqual(release["entry_path"], "index.html")
                self.assertTrue(release["preview_url"].endswith("/preview"))

                preview_response = self.run_async(
                    self.client.get(
                        release["preview_url"],
                        headers=self._auth_headers(admin["token"]),
                    )
                )
                self.assertEqual(preview_response.status_code, 200, preview_response.text)
                self.assertIn("自定义首页", preview_response.text)
                self.assertIn("script-src 'none'", preview_response.text)
                self.assertNotIn("<script", preview_response.text.lower())
                self.assertNotIn("onerror", preview_response.text.lower())
                self.assertIn(f"/_custom_homepage/releases/{release['id']}/assets/logo.png", preview_response.text)

                activate_response = self.run_async(
                    self.client.post(
                        f"/api/admin/homepage/releases/{release['id']}/activate",
                        headers=self._auth_headers(admin["token"]),
                    )
                )
                self.assertEqual(activate_response.status_code, 200, activate_response.text)
                self.assertEqual(activate_response.json()["runtime"]["mode"], "custom")

                public_response = self.run_async(self.client.get("/api/settings/homepage"))
                self.assertEqual(public_response.status_code, 200, public_response.text)
                self.assertIn("no-cache", public_response.headers.get("cache-control", ""))
                public_payload = public_response.json()
                self.assertTrue(public_payload["active"])
                self.assertEqual(public_payload["mode"], "custom")
                self.assertEqual(public_payload["company_list_path"], "/companies")

                default_response = self.run_async(
                    self.client.post(
                        "/api/admin/homepage/default",
                        headers=self._auth_headers(admin["token"]),
                    )
                )
                self.assertEqual(default_response.status_code, 200, default_response.text)
                self.assertEqual(default_response.json()["runtime"]["mode"], "default")

                public_after_default = self.run_async(self.client.get("/api/settings/homepage")).json()
                self.assertFalse(public_after_default["active"])
                self.assertEqual(public_after_default["mode"], "default")

                delete_response = self.run_async(
                    self.client.delete(
                        f"/api/admin/homepage/releases/{release['id']}",
                        headers=self._auth_headers(admin["token"]),
                    )
                )
                self.assertEqual(delete_response.status_code, 200, delete_response.text)
                self.assertEqual(delete_response.json()["status"], "deleted")

                detail_after_delete = self.run_async(
                    self.client.get(
                        f"/api/admin/homepage/releases/{release['id']}",
                        headers=self._auth_headers(admin["token"]),
                    )
                )
                self.assertEqual(detail_after_delete.status_code, 404, detail_after_delete.text)
            finally:
                self.run_async(_restore_homepage_runtime_setting(snapshot))

    def test_homepage_mutations_serialize_database_and_filesystem_state(self):
        admin = self.run_async(self._register_user(admin=True))
        headers = self._auth_headers(admin["token"])
        settings_snapshot = self.run_async(
            self._snapshot_settings(("homepage_runtime", "analytics_tracking_code"))
        )

        async def exercise(root: Path):
            from app.api.routes import admin as admin_routes

            async def upload(label: str) -> str:
                response = await self.client.post(
                    "/api/admin/homepage/releases",
                    headers=headers,
                    data={
                        "source_type": "zip_package",
                        "title": f"{TEST_HOMEPAGE_TITLE_PREFIX}{label}-{uuid.uuid4().hex[:8]}",
                    },
                    files={
                        "file": (
                            f"{label}.zip",
                            self._zip_bytes(
                                {"index.html": f"<html><head></head><body>{label}</body></html>"}
                            ),
                            "application/zip",
                        )
                    },
                )
                self.assertEqual(response.status_code, 201, response.text)
                return response.json()["id"]

            async def run_while_database_lock_is_held(*request_factories):
                original_lock = admin_routes._homepage_mutation_lock
                all_waiting = asyncio.Event()
                waiting_count = 0

                @asynccontextmanager
                async def observed_lock():
                    nonlocal waiting_count
                    waiting_count += 1
                    if waiting_count == len(request_factories):
                        all_waiting.set()
                    async with original_lock():
                        yield

                async with async_session() as blocker:
                    await blocker.execute(
                        text("SELECT pg_advisory_lock(hashtext(:lock_name))"),
                        {"lock_name": admin_routes.HOMEPAGE_MUTATION_ADVISORY_LOCK},
                    )
                    with patch.object(admin_routes, "_homepage_mutation_lock", new=observed_lock):
                        tasks = [asyncio.create_task(factory()) for factory in request_factories]
                        await asyncio.wait_for(all_waiting.wait(), timeout=2)
                        await blocker.execute(
                            text("SELECT pg_advisory_unlock(hashtext(:lock_name))"),
                            {"lock_name": admin_routes.HOMEPAGE_MUTATION_ADVISORY_LOCK},
                        )
                        return await asyncio.gather(*tasks)

            async def assert_custom_state_is_consistent(expected_ids: set[str]):
                runtime = await get_homepage_runtime_config(force_refresh=True)
                async with async_session() as db:
                    active_ids = {
                        str(release_id)
                        for release_id in (
                            await db.execute(
                                select(HomepageRelease.id).where(
                                    HomepageRelease.status == HomepageReleaseStatus.ACTIVE,
                                )
                            )
                        ).scalars()
                    }
                self.assertEqual(len(active_ids), 1)
                active_id = next(iter(active_ids))
                self.assertIn(active_id, expected_ids)
                self.assertEqual(runtime["mode"], "custom")
                self.assertEqual(runtime["active_release_id"], active_id)
                active_path = root / "public" / "active"
                self.assertTrue(active_path.is_symlink())
                self.assertEqual(active_path.readlink(), Path("releases") / active_id)
                return active_id

            async with async_session() as db:
                await db.execute(delete(Setting).where(Setting.key == "analytics_tracking_code"))
                await db.commit()
            await invalidate_runtime_settings_cache()

            release_a, release_b = await asyncio.gather(upload("race-a"), upload("race-b"))
            activation_responses = await run_while_database_lock_is_held(
                lambda: self.client.post(
                    f"/api/admin/homepage/releases/{release_a}/activate", headers=headers
                ),
                lambda: self.client.post(
                    f"/api/admin/homepage/releases/{release_b}/activate", headers=headers
                ),
            )
            self.assertEqual([response.status_code for response in activation_responses], [200, 200])
            await assert_custom_state_is_consistent({release_a, release_b})

            release_c = await upload("race-delete")
            activate_delete_responses = await run_while_database_lock_is_held(
                lambda: self.client.post(
                    f"/api/admin/homepage/releases/{release_c}/activate", headers=headers
                ),
                lambda: self.client.delete(
                    f"/api/admin/homepage/releases/{release_c}", headers=headers
                ),
            )
            status_codes = [response.status_code for response in activate_delete_responses]
            self.assertEqual(status_codes.count(200), 1, [response.text for response in activate_delete_responses])
            self.assertIn(next(code for code in status_codes if code != 200), {400, 404})
            await assert_custom_state_is_consistent({release_a, release_b, release_c})

            analytics_code = '<script data-georank-race="analytics">trackRace()</script>'
            analytics_default_responses = await run_while_database_lock_is_held(
                lambda: self.client.put(
                    "/api/admin/settings",
                    headers=headers,
                    json={
                        "analytics_tracking_code": {
                            "value": analytics_code,
                            "category": "analytics",
                            "is_public": True,
                        }
                    },
                ),
                lambda: self.client.post("/api/admin/homepage/default", headers=headers),
            )
            self.assertEqual(
                [response.status_code for response in analytics_default_responses],
                [200, 200],
                [response.text for response in analytics_default_responses],
            )
            runtime = await get_homepage_runtime_config(force_refresh=True)
            self.assertEqual(runtime["mode"], "default")
            self.assertIsNone(runtime["active_release_id"])
            self.assertFalse((root / "public" / "active").exists())
            async with async_session() as db:
                self.assertEqual(
                    await db.scalar(
                        select(func.count(HomepageRelease.id)).where(
                            HomepageRelease.status == HomepageReleaseStatus.ACTIVE,
                        )
                    ),
                    0,
                )
                analytics_setting = await db.scalar(
                    select(Setting).where(Setting.key == "analytics_tracking_code")
                )
                self.assertIsNotNone(analytics_setting)
                self.assertEqual(
                    decrypt_setting_value(
                        analytics_setting.value,
                        analytics_setting.key,
                        analytics_setting.category,
                    ),
                    analytics_code,
                )

        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"GEORANK_HOMEPAGE_ROOT": tmpdir},
        ):
            try:
                self.run_async(exercise(Path(tmpdir)))
            finally:
                self.run_async(self._restore_settings(settings_snapshot))

    def test_homepage_session_lock_survives_server_side_commit_failure(self):
        admin = self.run_async(self._register_user(admin=True))
        headers = self._auth_headers(admin["token"])
        settings_snapshot = self.run_async(
            self._snapshot_settings(("homepage_runtime", "analytics_tracking_code"))
        )

        async def exercise(root: Path):
            from app.api.routes import admin as admin_routes

            async with async_session() as db:
                admin_id = await db.scalar(select(User.id).where(User.email == admin["email"]))
                await db.execute(delete(Setting).where(Setting.key == "analytics_tracking_code"))
                await db.commit()
            await invalidate_runtime_settings_cache()
            admin_user = SimpleNamespace(id=admin_id)

            async def upload(label: str) -> uuid.UUID:
                response = await self.client.post(
                    "/api/admin/homepage/releases",
                    headers=headers,
                    data={
                        "source_type": "zip_package",
                        "title": f"{TEST_HOMEPAGE_TITLE_PREFIX}{label}-{uuid.uuid4().hex[:8]}",
                    },
                    files={
                        "file": (
                            f"{label}.zip",
                            self._zip_bytes(
                                {"index.html": f"<html><head></head><body>{label}</body></html>"}
                            ),
                            "application/zip",
                        )
                    },
                )
                self.assertEqual(response.status_code, 201, response.text)
                return uuid.UUID(response.json()["id"])

            failed_release_id, successor_release_id = await asyncio.gather(
                upload("commit-failure"), upload("commit-successor")
            )
            original_lock = admin_routes._homepage_mutation_lock
            original_restore = admin_routes._restore_homepage_pointer_before_rollback
            restore_entered = asyncio.Event()
            allow_restore = asyncio.Event()
            successor_attempted = asyncio.Event()
            successor_acquired = asyncio.Event()
            order: list[str] = []

            async def probe_database_lock() -> bool:
                async with engine.connect() as probe_connection:
                    acquired = bool(
                        await probe_connection.scalar(
                            text("SELECT pg_try_advisory_lock(hashtext(:lock_name))"),
                            {"lock_name": admin_routes.HOMEPAGE_MUTATION_ADVISORY_LOCK},
                        )
                    )
                    if acquired:
                        await probe_connection.execute(
                            text("SELECT pg_advisory_unlock(hashtext(:lock_name))"),
                            {"lock_name": admin_routes.HOMEPAGE_MUTATION_ADVISORY_LOCK},
                        )
                    await probe_connection.commit()
                    return acquired

            @asynccontextmanager
            async def observed_lock():
                task_name = asyncio.current_task().get_name()
                order.append(f"{task_name}:attempt")
                if task_name == "successor":
                    successor_attempted.set()
                async with original_lock():
                    order.append(f"{task_name}:acquired")
                    if task_name == "successor":
                        successor_acquired.set()
                    try:
                        yield
                    finally:
                        order.append(f"{task_name}:release")

            async def paused_restore(db, runtime_root, previous_target, pointer_staged):
                order.append("failed:restore-entered")
                restore_entered.set()
                await allow_restore.wait()
                await original_restore(db, runtime_root, previous_target, pointer_staged)
                order.append("failed:restore-complete")

            async with async_session() as failed_db:
                suffix = uuid.uuid4().hex
                parent_table = f"tmp_homepage_parent_{suffix}"
                child_table = f"tmp_homepage_child_{suffix}"
                await failed_db.execute(
                    text(f"CREATE TEMP TABLE {parent_table} (id integer PRIMARY KEY)")
                )
                await failed_db.execute(
                    text(
                        f"CREATE TEMP TABLE {child_table} ("
                        f"parent_id integer REFERENCES {parent_table}(id) "
                        "DEFERRABLE INITIALLY DEFERRED)"
                    )
                )
                await failed_db.execute(
                    text(f"INSERT INTO {child_table} (parent_id) VALUES (1)")
                )

                async def run_successor():
                    async with async_session() as successor_db:
                        return await admin_routes.activate_homepage_release_admin(
                            successor_release_id,
                            successor_db,
                            admin_user,
                        )

                with (
                    patch.object(admin_routes, "_homepage_mutation_lock", new=observed_lock),
                    patch.object(
                        admin_routes,
                        "_restore_homepage_pointer_before_rollback",
                        new=paused_restore,
                    ),
                ):
                    failed_task = asyncio.create_task(
                        admin_routes.activate_homepage_release_admin(
                            failed_release_id,
                            failed_db,
                            admin_user,
                        ),
                        name="failed",
                    )
                    await asyncio.wait_for(restore_entered.wait(), timeout=2)
                    successor_task = asyncio.create_task(run_successor(), name="successor")
                    await asyncio.wait_for(successor_attempted.wait(), timeout=2)
                    self.assertFalse(successor_acquired.is_set())
                    self.assertFalse(await probe_database_lock())
                    allow_restore.set()
                    failed_result, successor_result = await asyncio.gather(
                        failed_task,
                        successor_task,
                        return_exceptions=True,
                    )

            self.assertIsInstance(failed_result, IntegrityError)
            self.assertNotIsInstance(successor_result, Exception)
            self.assertLess(
                order.index("failed:restore-complete"),
                order.index("failed:release"),
            )
            self.assertLess(order.index("failed:release"), order.index("successor:acquired"))
            self.assertTrue(await probe_database_lock())
            active_path = root / "public" / "active"
            self.assertTrue(active_path.is_symlink())
            self.assertEqual(active_path.readlink(), Path("releases") / str(successor_release_id))
            runtime = await get_homepage_runtime_config(force_refresh=True)
            self.assertEqual(runtime["mode"], "custom")
            self.assertEqual(runtime["active_release_id"], str(successor_release_id))
            async with async_session() as db:
                active_ids = set(
                    (
                        await db.execute(
                            select(HomepageRelease.id).where(
                                HomepageRelease.status == HomepageReleaseStatus.ACTIVE
                            )
                        )
                    ).scalars()
                )
            self.assertEqual(active_ids, {successor_release_id})

        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"GEORANK_HOMEPAGE_ROOT": tmpdir},
        ):
            try:
                self.run_async(exercise(Path(tmpdir)))
            finally:
                self.run_async(self._restore_settings(settings_snapshot))

    def test_cancelled_homepage_lock_acquisition_invalidates_physical_connection(self):
        async def exercise():
            from app.api.routes import admin as admin_routes

            real_connection = await engine.connect()
            server_locked = asyncio.Event()
            hold_client_return = asyncio.Event()
            invalidated = asyncio.Event()

            class AcquisitionBarrierConnection:
                async def execute(self, statement, parameters=None):
                    result = await real_connection.execute(statement, parameters or {})
                    if "pg_advisory_lock" in str(statement):
                        server_locked.set()
                        await hold_client_return.wait()
                    return result

                async def commit(self):
                    await real_connection.commit()

                async def invalidate(self):
                    await real_connection.invalidate()
                    invalidated.set()

                async def close(self):
                    await real_connection.close()

            async def acquire_lock():
                async with admin_routes._homepage_mutation_lock():
                    self.fail("取消发生在协调锁进入 handler 之前")

            proxy = AcquisitionBarrierConnection()
            with patch.object(
                admin_routes,
                "engine",
                new=SimpleNamespace(connect=AsyncMock(return_value=proxy)),
            ):
                acquisition_task = asyncio.create_task(acquire_lock())
                await asyncio.wait_for(server_locked.wait(), timeout=2)
                acquisition_task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await acquisition_task

            self.assertTrue(invalidated.is_set())
            async with engine.connect() as probe_connection:
                acquired = bool(
                    await probe_connection.scalar(
                        text("SELECT pg_try_advisory_lock(hashtext(:lock_name))"),
                        {"lock_name": admin_routes.HOMEPAGE_MUTATION_ADVISORY_LOCK},
                    )
                )
                self.assertTrue(acquired)
                await probe_connection.execute(
                    text("SELECT pg_advisory_unlock(hashtext(:lock_name))"),
                    {"lock_name": admin_routes.HOMEPAGE_MUTATION_ADVISORY_LOCK},
                )
                await probe_connection.commit()

        self.run_async(exercise())

    def test_admin_homepage_upload_requires_admin(self):
        user = self.run_async(self._register_user())
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"GEORANK_HOMEPAGE_ROOT": tmpdir}):
            response = self.run_async(
                self.client.post(
                    "/api/admin/homepage/releases",
                    headers=self._auth_headers(user["token"]),
                    data={"source_type": "single_html", "title": f"{TEST_HOMEPAGE_TITLE_PREFIX}{uuid.uuid4().hex[:8]}", "html": "<h1>Hi</h1>"},
                )
            )

        self.assertEqual(response.status_code, 403, response.text)

    def test_submit_company_creates_pending_record_and_pipeline_status(self):
        user = self.run_async(self._register_user())
        bare_domain = f"codex-it-{uuid.uuid4().hex[:10]}.example.test"
        company_url = f"https://{bare_domain}"

        with patch("app.core.celery_app.celery_app.send_task") as send_task:
            submit_response = self.run_async(
                self.client.post(
                    "/api/companies/submit",
                    headers=self._auth_headers(user["token"]),
                    json={"url": bare_domain},
                )
            )

        self.assertEqual(submit_response.status_code, 202, submit_response.text)
        payload = submit_response.json()
        company_id = payload["company_id"]
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["normalized_url"], company_url)
        self.assertEqual(payload["publish_status"], "draft")
        send_task.assert_called_once()
        self.assertEqual(send_task.call_args.args[0], "app.tasks.crawl.crawl_company_website")
        self.assertEqual(send_task.call_args.kwargs["args"][1], company_url)

        status_response = self.run_async(
            self.client.get(f"/api/companies/{company_id}/pipeline-status")
        )
        self.assertEqual(status_response.status_code, 200, status_response.text)
        status_payload = status_response.json()
        self.assertEqual(status_payload["status"], "pending")
        self.assertEqual(status_payload["progress"], 0)
        self.assertEqual(status_payload["publish_status"], "draft")

        duplicate_response = self.run_async(
            self.client.post(
                "/api/companies/submit",
                headers=self._auth_headers(user["token"]),
                json={"url": company_url},
            )
        )
        self.assertEqual(duplicate_response.status_code, 202, duplicate_response.text)
        duplicate_payload = duplicate_response.json()
        self.assertTrue(duplicate_payload["resumed"])
        self.assertEqual(duplicate_payload["company_id"], company_id)

    def test_submit_company_allows_anonymous_requests(self):
        bare_domain = f"codex-it-{uuid.uuid4().hex[:10]}.public.test"
        company_url = f"https://{bare_domain}"

        with patch("app.core.celery_app.celery_app.send_task") as send_task:
            submit_response = self.run_async(
                self.client.post(
                    "/api/companies/submit",
                    json={"url": bare_domain},
                )
            )

        self.assertEqual(submit_response.status_code, 202, submit_response.text)
        company_id = submit_response.json()["company_id"]
        send_task.assert_called_once()

        async def _fetch_company():
            async with async_session() as db:
                result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
                return result.scalar_one()

        company = self.run_async(_fetch_company())
        self.assertIsNone(company.submitted_by)
        self.assertEqual(company.pipeline_status, PipelineStatus.PENDING)

    def test_submit_company_review_requires_completed_pipeline_and_updates_publish_status(self):
        user = self.run_async(self._register_user())
        company_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.review.test"

        with patch("app.core.celery_app.celery_app.send_task"):
            submit_response = self.run_async(
                self.client.post(
                    "/api/companies/submit",
                    headers=self._auth_headers(user["token"]),
                    json={"url": company_url},
                )
            )

        self.assertEqual(submit_response.status_code, 202, submit_response.text)
        company_id = submit_response.json()["company_id"]

        early_submit = self.run_async(
            self.client.post(
                f"/api/companies/{company_id}/submit-review",
                headers=self._auth_headers(user["token"]),
            )
        )
        self.assertEqual(early_submit.status_code, 409, early_submit.text)

        async def _mark_completed():
            async with async_session() as db:
                await db.execute(
                    update(Company)
                    .where(Company.id == uuid.UUID(company_id))
                    .values(
                        pipeline_status=PipelineStatus.COMPLETED,
                        publish_status=PublishStatus.DRAFT,
                        short_description="测试公司简介",
                        description="测试公司完整介绍",
                        tags=["GEO优化"],
                        tech_stack=["OpenAI API"],
                        geo_score=66,
                        geo_details={"schema": 60, "content": 70, "meta": 65, "citation": 68},
                    )
                )
                await db.commit()

        self.run_async(_mark_completed())

        final_submit = self.run_async(
            self.client.post(
                f"/api/companies/{company_id}/submit-review",
                headers=self._auth_headers(user["token"]),
            )
        )
        self.assertEqual(final_submit.status_code, 200, final_submit.text)
        self.assertEqual(final_submit.json()["status"], "pending_review")

        async def _fetch_company():
            async with async_session() as db:
                result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
                return result.scalar_one()

        company = self.run_async(_fetch_company())
        self.assertEqual(company.publish_status, PublishStatus.PENDING_REVIEW)
        self.assertIsNotNone(company.submitted_by)

    def test_submit_company_review_auto_hydrates_missing_profile(self):
        user = self.run_async(self._register_user())
        company_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.review.test"
        html = """
        <html>
          <head>
            <title>移山科技官网</title>
            <meta name=\"description\" content=\"中国领先的 GEO 优化服务商\" />
          </head>
          <body>
            <h1>移山科技</h1>
            <p>提供 GEO 诊断与 AI 搜索优化方案。</p>
          </body>
        </html>
        """.encode("utf-8")

        async def _create_company():
            async with async_session() as db:
                company = Company(
                    name="www.geokeji.com",
                    url=company_url,
                    pipeline_status=PipelineStatus.COMPLETED,
                    publish_status=PublishStatus.DRAFT,
                    raw_html_key="companies/test/raw.html",
                )
                db.add(company)
                await db.commit()
                await db.refresh(company)
                return str(company.id)

        company_id = self.run_async(_create_company())

        with patch("app.services.company_profile.storage.get", return_value=html), patch(
            "app.services.company_profile.ai_client.extract_company_info",
            new=AsyncMock(
                return_value={
                    "name": "移山科技",
                    "description": "移山科技专注 GEO 优化与 AI 搜索可见度提升。",
                    "short_description": "中国领先的 GEO 优化服务商。",
                    "category": "GEO咨询",
                    "tags": ["GEO优化", "AI搜索"],
                    "tech_stack": ["OpenAI API", "Firecrawl"],
                    "team_members": [{"name": "张三", "role": "创始人"}],
                }
            ),
        ):
            final_submit = self.run_async(
                self.client.post(
                    f"/api/companies/{company_id}/submit-review",
                    headers=self._auth_headers(user["token"]),
                )
            )

        self.assertEqual(final_submit.status_code, 200, final_submit.text)

        async def _fetch_company():
            async with async_session() as db:
                result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
                return result.scalar_one()

        company = self.run_async(_fetch_company())
        self.assertEqual(company.publish_status, PublishStatus.PENDING_REVIEW)
        self.assertEqual(company.name, "移山科技")
        self.assertEqual(company.category, "GEO咨询")
        self.assertTrue(company.short_description)
        self.assertTrue(company.description)
        self.assertIn("GEO优化", company.tags or [])
        self.assertIn("OpenAI API", company.tech_stack or [])
        self.assertEqual((company.team_members or [{}])[0].get("name"), "张三")
        self.assertIsNotNone(company.geo_score)
        self.assertIsNotNone(company.geo_details)

    def test_admin_approve_company_auto_hydrates_missing_profile(self):
        admin = self.run_async(self._register_user(admin=True))
        company_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.review.test"
        html = """
        <html>
          <head>
            <title>移山科技官网</title>
            <meta name=\"description\" content=\"中国领先的 GEO 优化服务商\" />
          </head>
          <body>
            <h1>移山科技</h1>
            <p>提供 GEO 诊断与 AI 搜索优化方案。</p>
          </body>
        </html>
        """.encode("utf-8")

        async def _create_company():
            async with async_session() as db:
                company = Company(
                    name="www.geokeji.com",
                    url=company_url,
                    pipeline_status=PipelineStatus.COMPLETED,
                    publish_status=PublishStatus.PENDING_REVIEW,
                    raw_html_key="companies/test/raw.html",
                )
                db.add(company)
                await db.commit()
                await db.refresh(company)
                return str(company.id)

        company_id = self.run_async(_create_company())

        with patch("app.services.company_profile.storage.get", return_value=html), patch(
            "app.services.company_profile.ai_client.extract_company_info",
            new=AsyncMock(
                return_value={
                    "name": "移山科技",
                    "description": "移山科技专注 GEO 优化与 AI 搜索可见度提升。",
                    "short_description": "中国领先的 GEO 优化服务商。",
                    "category": "GEO咨询",
                    "tags": ["GEO优化", "AI搜索"],
                    "tech_stack": ["OpenAI API", "Firecrawl"],
                    "team_members": [{"name": "张三", "role": "创始人"}],
                }
            ),
        ):
            approve_response = self.run_async(
                self.client.post(
                    f"/api/admin/companies/{company_id}/approve",
                    headers=self._auth_headers(admin["token"]),
                )
            )

        self.assertEqual(approve_response.status_code, 200, approve_response.text)

        async def _fetch_company():
            async with async_session() as db:
                result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
                return result.scalar_one()

        company = self.run_async(_fetch_company())
        self.assertEqual(company.publish_status, PublishStatus.PUBLISHED)
        self.assertEqual(company.name, "移山科技")
        self.assertEqual(company.category, "GEO咨询")
        self.assertTrue(company.short_description)
        self.assertTrue(company.description)
        self.assertIn("GEO优化", company.tags or [])
        self.assertIn("OpenAI API", company.tech_stack or [])
        self.assertEqual((company.team_members or [{}])[0].get("name"), "张三")
        self.assertIsNotNone(company.geo_score)
        self.assertIsNotNone(company.geo_details)

    def test_admin_company_detail_returns_pipeline_and_diagnostic_context(self):
        admin = self.run_async(self._register_user(admin=True))
        member = self.run_async(self._register_user())
        company_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.example.test"

        async def _create_company_detail_data():
            from datetime import datetime, timedelta

            async with async_session() as db:
                user_result = await db.execute(select(User).where(User.email == member["email"]))
                member_user = user_result.scalar_one()

                company = Company(
                    name=f"codex-it-company-{uuid.uuid4().hex[:8]}",
                    url=company_url,
                    short_description="面向 GEO 的语义优化平台",
                    description="提供结构化数据、FAQ 页面和品牌知识卡优化。",
                    category="GEO工具",
                    tags=["Semantic SEO", "FAQ"],
                    is_geo_certified=True,
                    headquarters="Shanghai",
                    employee_count="11-50",
                    funding_stage="Series A",
                    tech_level="L4",
                    tech_stack=["Python", "Qdrant"],
                    team_members=[{"name": "Ada", "role": "Founder"}],
                    geo_score=91.4,
                    geo_details={"content": 92, "citation": 88},
                    pipeline_status=PipelineStatus.COMPLETED,
                    publish_status=PublishStatus.PUBLISHED,
                    raw_html_key="companies/raw/demo.html",
                    about_html_key="companies/about/demo.html",
                    screenshots=["companies/screenshots/home.png"],
                    upvotes=17,
                    submitted_by=member_user.id,
                )
                db.add(company)
                await db.flush()

                old_report = DiagnosticReport(
                    url=f"{company_url}/geo",
                    company_id=company.id,
                    user_id=member_user.id,
                    status=DiagnosticStatus.COMPLETED,
                    overall_score=83.6,
                    created_at=datetime.utcnow() - timedelta(days=1),
                )
                db.add(old_report)
                await db.flush()

                latest_report = DiagnosticReport(
                    url=f"{company_url}/geo/latest",
                    company_id=company.id,
                    user_id=member_user.id,
                    status=DiagnosticStatus.COMPLETED,
                    overall_score=87.1,
                    created_at=datetime.utcnow(),
                )
                db.add(latest_report)
                await db.flush()

                conversation = Conversation(
                    user_id=member_user.id,
                    title="围绕目标公司生成方案",
                )
                db.add(conversation)
                await db.flush()

                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role=MessageRole.ASSISTANT,
                        content="建议把该品牌 FAQ、案例页和引用链接一起加强。",
                        recommended_companies=[
                            {
                                "company_id": str(company.id),
                                "name": company.name,
                                "match_score": 0.97,
                            }
                        ],
                        diagnostic_context_id=old_report.id,
                    )
                )
                await db.commit()
                return str(company.id), str(latest_report.id), member_user.username, str(conversation.id)

        company_id, report_id, username, conversation_id = self.run_async(_create_company_detail_data())

        list_response = self.run_async(
            self.client.get(
                "/api/admin/companies?search=FAQ",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertTrue(any(item["id"] == company_id for item in list_response.json()["items"]))

        detail_response = self.run_async(
            self.client.get(
                f"/api/admin/companies/{company_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        detail = detail_response.json()
        self.assertEqual(detail["id"], company_id)
        self.assertEqual(detail["pipeline_status"], "completed")
        self.assertEqual(detail["publish_status"], "published")
        self.assertEqual(detail["submitted_by_user"]["username"], username)
        self.assertEqual(detail["diagnostic_report_count"], 2)
        self.assertEqual(detail["latest_diagnostic"]["id"], report_id)
        self.assertIn("Semantic SEO", detail["tags"])
        self.assertEqual(detail["geo_details"]["content"], 92)
        self.assertTrue(detail["related_solutions"])
        self.assertEqual(detail["related_solutions"][0]["id"], conversation_id)
        self.assertIn("recommended_company", detail["related_solutions"][0]["match_types"])
        self.assertIn("diagnostic_context", detail["related_solutions"][0]["match_types"])

    def test_admin_can_retry_failed_company_pipeline(self):
        admin = self.run_async(self._register_user(admin=True))
        member = self.run_async(self._register_user())
        company_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.retry.test"

        policy_response = self.run_async(
            self.client.get(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(policy_response.status_code, 200, policy_response.text)
        original_policy = policy_response.json()["policy"]
        unlimited_policy = {**original_policy, "access_mode": "platform_unlimited"}

        save_policy_response = self.run_async(
            self.client.put(
                "/api/admin/api-policy",
                headers=self._auth_headers(admin["token"]),
                json=unlimited_policy,
            )
        )
        self.assertEqual(save_policy_response.status_code, 200, save_policy_response.text)

        async def _create_failed_company():
            async with async_session() as db:
                user_result = await db.execute(select(User).where(User.email == member["email"]))
                member_user = user_result.scalar_one()

                company = Company(
                    name=f"codex-retry-{uuid.uuid4().hex[:8]}",
                    url=company_url,
                    pipeline_status=PipelineStatus.FAILED,
                    pipeline_error="crawler timeout",
                    publish_status=PublishStatus.DRAFT,
                    submitted_by=member_user.id,
                )
                db.add(company)
                await db.commit()
                await db.refresh(company)
                return str(company.id)

        try:
            company_id = self.run_async(_create_failed_company())

            with patch("app.core.celery_app.celery_app.send_task") as send_task:
                retry_response = self.run_async(
                    self.client.post(
                        f"/api/admin/companies/{company_id}/retry-pipeline",
                        headers=self._auth_headers(admin["token"]),
                    )
                )

            self.assertEqual(retry_response.status_code, 200, retry_response.text)
            self.assertEqual(retry_response.json()["status"], "retrying")
            send_task.assert_called_once()
            self.assertEqual(send_task.call_args.args[0], "app.tasks.crawl.crawl_company_website")
            self.assertEqual(send_task.call_args.kwargs["args"][0], company_id)
            self.assertEqual(send_task.call_args.kwargs["args"][1], company_url)

            async def _fetch_company():
                async with async_session() as db:
                    result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
                    return result.scalar_one()

            company = self.run_async(_fetch_company())
            self.assertEqual(company.pipeline_status, PipelineStatus.PENDING)
            self.assertIsNone(company.pipeline_error)
        finally:
            restore_response = self.run_async(
                self.client.put(
                    "/api/admin/api-policy",
                    headers=self._auth_headers(admin["token"]),
                    json=original_policy,
                )
            )
            self.assertEqual(restore_response.status_code, 200, restore_response.text)

    def test_admin_can_delete_company_and_related_records(self):
        admin = self.run_async(self._register_user(admin=True))
        member = self.run_async(self._register_user())
        company_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.delete.test"

        async def _create_company_bundle():
            async with async_session() as db:
                user_result = await db.execute(select(User).where(User.email == member["email"]))
                member_user = user_result.scalar_one()

                company = Company(
                    name=f"codex-delete-{uuid.uuid4().hex[:8]}",
                    url=company_url,
                    short_description="待删除的测试公司",
                    description="用于验证后台删除公司接口。",
                    category="GEO工具",
                    pipeline_status=PipelineStatus.COMPLETED,
                    publish_status=PublishStatus.PENDING_REVIEW,
                )
                db.add(company)
                await db.flush()

                db.add(
                    CompanyVote(
                        company_id=company.id,
                        user_id=member_user.id,
                    )
                )
                db.add(
                    report := DiagnosticReport(
                        url=f"{company_url}/diagnostic",
                        company_id=company.id,
                        user_id=member_user.id,
                        status=DiagnosticStatus.COMPLETED,
                        overall_score=72.5,
                    )
                )
                await db.flush()
                conversation = Conversation(user_id=member_user.id, title="Company deletion context")
                db.add(conversation)
                await db.flush()
                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role=MessageRole.USER,
                        content="Use this report",
                        diagnostic_context_id=report.id,
                    )
                )
                await db.commit()
                return str(company.id), str(conversation.id)

        company_id, conversation_id = self.run_async(_create_company_bundle())

        delete_response = self.run_async(
            self.client.delete(
                f"/api/admin/companies/{company_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(delete_response.status_code, 200, delete_response.text)
        self.assertEqual(delete_response.json()["status"], "deleted")

        detail_response = self.run_async(
            self.client.get(
                f"/api/admin/companies/{company_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(detail_response.status_code, 404, detail_response.text)

        async def _counts():
            async with async_session() as db:
                company_count = await db.scalar(
                    select(func.count()).select_from(Company).where(Company.id == uuid.UUID(company_id))
                )
                vote_count = await db.scalar(
                    select(func.count()).select_from(CompanyVote).where(CompanyVote.company_id == uuid.UUID(company_id))
                )
                diagnostic_count = await db.scalar(
                    select(func.count()).select_from(DiagnosticReport).where(DiagnosticReport.company_id == uuid.UUID(company_id))
                )
                message_context = await db.scalar(
                    select(Message.diagnostic_context_id).where(Message.conversation_id == uuid.UUID(conversation_id))
                )
                return company_count, vote_count, diagnostic_count, message_context

        company_count, vote_count, diagnostic_count, message_context = self.run_async(_counts())
        self.assertEqual(company_count, 0)
        self.assertEqual(vote_count, 0)
        self.assertEqual(diagnostic_count, 0)
        self.assertIsNone(message_context)

    def test_admin_can_create_and_update_company(self):
        admin = self.run_async(self._register_user(admin=True))
        suffix = uuid.uuid4().hex[:10]
        company_url = f"{TEST_COMPANY_URL_PREFIX}{suffix}.create.test"

        create_response = self.run_async(
            self.client.post(
                "/api/admin/companies",
                headers=self._auth_headers(admin["token"]),
                json={
                    "name": f"Codex Admin Company {suffix}",
                    "url": company_url,
                    "short_description": "Created from admin",
                    "category": "GEO tools",
                    "tags": ["admin", "crud"],
                    "tech_stack": ["Next.js"],
                    "publish_status": "draft",
                    "pipeline_status": "completed",
                    "geo_score": 66,
                },
            )
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        created = create_response.json()
        company_id = created["id"]
        self.assertEqual(created["name"], f"Codex Admin Company {suffix}")
        self.assertEqual(created["tags"], ["admin", "crud"])

        update_response = self.run_async(
            self.client.put(
                f"/api/admin/companies/{company_id}",
                headers=self._auth_headers(admin["token"]),
                json={
                    "name": f"Codex Admin Company Updated {suffix}",
                    "url": company_url,
                    "short_description": "Updated from admin",
                    "category": "GEO platform",
                    "tags": ["updated"],
                    "tech_stack": ["FastAPI"],
                    "publish_status": "pending_review",
                    "pipeline_status": "completed",
                    "geo_score": 72.5,
                },
            )
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)
        updated = update_response.json()
        self.assertEqual(updated["name"], f"Codex Admin Company Updated {suffix}")
        self.assertEqual(updated["publish_status"], "pending_review")
        self.assertEqual(updated["category"], "GEO platform")
        self.assertEqual(updated["tech_stack"], ["FastAPI"])

    def test_company_detail_page_is_server_rendered_with_schema(self):
        company_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.example.test"
        holder = {}

        async def _create_company():
            async with async_session() as db:
                company = Company(
                    name="SSR Company",
                    url=company_url,
                    short_description="服务端直出的 GEO 公司档案。",
                    description="这是一段直接写进 HTML 源码中的公司介绍。\n\n用于验证搜索引擎可以直接读取正文。",
                    category="GEO工具",
                    tags=["知识图谱", "GEO优化"],
                    tech_level="L4",
                    tech_stack=["OpenAI API", "Firecrawl"],
                    team_members=[{"name": "Ada", "role": "Founder"}],
                    geo_score=88.2,
                    geo_details={"schema": 92, "content": 86, "meta": 85, "citation": 90},
                    pipeline_status=PipelineStatus.COMPLETED,
                    publish_status=PublishStatus.PUBLISHED,
                    crawl_pages=[
                        {
                            "role": "homepage",
                            "title": "SSR Company 官网",
                            "url": company_url,
                            "reason": "作为企业知识库的主入口页面。",
                        }
                    ],
                )
                db.add(company)
                await db.commit()
                await db.refresh(company)
                holder["company_id"] = str(company.id)
                holder["path_key"] = company.path_key

        self.run_async(_create_company())

        api_response = self.run_async(self.client.get(f"/api/companies/{holder['path_key']}"))
        self.assertEqual(api_response.status_code, 200, api_response.text)
        self.assertEqual(api_response.json()["id"], holder["company_id"])
        self.assertEqual(api_response.json()["path_key"], holder["path_key"])

        legacy_response = self.run_async(self.client.get(f"/companies/{holder['company_id']}", follow_redirects=False))
        self.assertEqual(legacy_response.status_code, 301, legacy_response.text)
        self.assertEqual(legacy_response.headers["location"], f"http://testserver/c/{holder['path_key']}")

        detail_response = self.run_async(self.client.get(f"/c/{holder['path_key']}"))
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        self.assertIn("SSR Company", detail_response.text)
        self.assertIn("服务端直出的 GEO 公司档案。", detail_response.text)
        self.assertIn("企业快照", detail_response.text)
        self.assertIn("GEO 行动路线图", detail_response.text)
        self.assertIn("Ada", detail_response.text)
        self.assertIn("application/ld+json", detail_response.text)
        self.assertIn('"@type": "Organization"', detail_response.text)
        self.assertIn(f'rel="canonical" href="http://testserver/c/{holder["path_key"]}"', detail_response.text)

    def test_diagnostics_create_history_and_report_are_user_scoped(self):
        user = self.run_async(self._register_user())
        other_user = self.run_async(self._register_user())
        diagnostic_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.example.test/diagnostic"

        with patch("app.core.celery_app.celery_app.send_task") as send_task:
            create_response = self.run_async(
                self.client.post(
                    "/api/diagnostics/",
                    headers=self._auth_headers(user["token"]),
                    json={"url": diagnostic_url},
                )
            )

        self.assertEqual(create_response.status_code, 200, create_response.text)
        payload = create_response.json()
        report_id = payload["report_id"]
        self.assertEqual(payload["status"], "pending")
        send_task.assert_called_once()
        self.assertEqual(send_task.call_args.args[0], "app.tasks.crawl.crawl_diagnostic_page")
        self.assertEqual(send_task.call_args.kwargs["args"][1], diagnostic_url)

        history_response = self.run_async(
            self.client.get(
                "/api/diagnostics/history",
                headers=self._auth_headers(user["token"]),
            )
        )
        self.assertEqual(history_response.status_code, 200, history_response.text)
        history = history_response.json()
        self.assertTrue(any(item["report_id"] == report_id for item in history))

        report_response = self.run_async(
            self.client.get(
                f"/api/diagnostics/{report_id}",
                headers=self._auth_headers(user["token"]),
            )
        )
        self.assertEqual(report_response.status_code, 200, report_response.text)
        report = report_response.json()
        self.assertEqual(report["report_id"], report_id)
        self.assertEqual(report["status"], "pending")
        self.assertEqual(report["url"], diagnostic_url)

        forbidden_response = self.run_async(
            self.client.get(
                f"/api/diagnostics/{report_id}",
                headers=self._auth_headers(other_user["token"]),
            )
        )
        self.assertEqual(forbidden_response.status_code, 403, forbidden_response.text)

    def test_diagnostics_normalize_bare_domain_before_queueing(self):
        user = self.run_async(self._register_user())
        bare_domain = f"codex-it-{uuid.uuid4().hex[:10]}.example.test"
        expected_url = f"https://{bare_domain}"

        with patch("app.core.celery_app.celery_app.send_task") as send_task:
            create_response = self.run_async(
                self.client.post(
                    "/api/diagnostics/",
                    headers=self._auth_headers(user["token"]),
                    json={"url": bare_domain},
                )
            )

        self.assertEqual(create_response.status_code, 200, create_response.text)
        payload = create_response.json()
        send_task.assert_called_once()
        self.assertEqual(send_task.call_args.kwargs["args"][1], expected_url)

        report_response = self.run_async(
            self.client.get(
                f"/api/diagnostics/{payload['report_id']}",
                headers=self._auth_headers(user["token"]),
            )
        )
        self.assertEqual(report_response.status_code, 200, report_response.text)
        self.assertEqual(report_response.json()["url"], expected_url)

    def test_anonymous_diagnostics_can_create_and_fetch_ownerless_report(self):
        diagnostic_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.public.test/diagnostic"

        with patch("app.core.celery_app.celery_app.send_task") as send_task:
            create_response = self.run_async(
                self.client.post(
                    "/api/diagnostics/",
                    json={"url": diagnostic_url},
                )
            )

        self.assertEqual(create_response.status_code, 200, create_response.text)
        payload = create_response.json()
        report_id = payload["report_id"]
        self.assertEqual(payload["status"], "pending")
        send_task.assert_called_once()

        async def _mark_report_completed():
            async with async_session() as db:
                report = await db.get(DiagnosticReport, uuid.UUID(report_id))
                self.assertIsNotNone(report)
                report.status = DiagnosticStatus.COMPLETED
                report.overall_score = 88
                report.schema_analysis = {"score": 90, "found_types": ["WebSite"], "missing_recommended": ["Organization"]}
                report.content_analysis = {"score": 84, "word_count": 640, "has_single_h1": True, "has_h2_structure": True}
                report.meta_analysis = {"score": 86, "missing": ["og_type"], "checks": {"title": True}}
                report.citation_analysis = {"score": 72, "authority_link_count": 1, "external_link_count": 4, "authority_links": ["https://example.org/source"]}
                report.recommendations = {"urgent": [{"item": "补充 Organization Schema", "action": "添加 JSON-LD"}], "recommended": [], "optional": []}
                await db.commit()

        self.run_async(_mark_report_completed())

        report_response = self.run_async(
            self.client.get(f"/api/diagnostics/{report_id}")
        )
        self.assertEqual(report_response.status_code, 200, report_response.text)
        report = report_response.json()
        self.assertEqual(report["report_id"], report_id)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["overall_score"], 88)

    def test_anonymous_solutions_chat_creates_ownerless_conversation(self):
        recommended = [{"company_id": "demo-company", "name": "Demo Company", "match_score": 0.93}]

        with patch(
            "app.api.routes.solutions._run_rag",
            new=AsyncMock(return_value=("这里是一份基于诊断结果生成的 GEO 方案。", recommended)),
        ):
            chat_response = self.run_async(
                self.client.post(
                    "/api/solutions/chat",
                    json={"message": "请基于这份诊断给我一套 GEO 优化方案"},
                )
            )

        self.assertEqual(chat_response.status_code, 200, chat_response.text)
        payload = chat_response.json()
        conversation_id = payload["conversation_id"]
        self.assertEqual(payload["recommended_companies"], recommended)

        async def _fetch_conversation_and_messages():
            async with async_session() as db:
                conversation = await db.get(Conversation, uuid.UUID(conversation_id))
                result = await db.execute(
                    select(Message).where(Message.conversation_id == uuid.UUID(conversation_id)).order_by(Message.created_at)
                )
                return conversation, result.scalars().all()

        conversation, messages = self.run_async(_fetch_conversation_and_messages())
        self.assertIsNone(conversation.user_id)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, MessageRole.USER)
        self.assertEqual(messages[1].role, MessageRole.ASSISTANT)

        public_conversation = self.run_async(
            self.client.get(f"/api/solutions/conversations/{conversation_id}")
        )
        self.assertEqual(public_conversation.status_code, 200, public_conversation.text)
        detail = public_conversation.json()
        self.assertEqual(detail["id"], conversation_id)
        self.assertEqual(detail["messages"][1]["recommended_companies"], recommended)
        self.assertIsNone(detail["user_id"])

    def test_authenticated_user_can_claim_public_solution_conversation(self):
        with patch(
            "app.api.routes.solutions._run_rag",
            new=AsyncMock(return_value=("公开方案内容", [])),
        ):
            chat_response = self.run_async(
                self.client.post(
                    "/api/solutions/chat",
                    json={"message": "先匿名生成一条方案"},
                )
            )

        self.assertEqual(chat_response.status_code, 200, chat_response.text)
        conversation_id = chat_response.json()["conversation_id"]
        user = self.run_async(self._register_user())

        claim_response = self.run_async(
            self.client.post(
                f"/api/solutions/conversations/{conversation_id}/claim",
                headers=self._auth_headers(user["token"]),
            )
        )
        self.assertEqual(claim_response.status_code, 200, claim_response.text)
        self.assertEqual(claim_response.json()["status"], "claimed")

        history_response = self.run_async(
            self.client.get(
                "/api/solutions/conversations",
                headers=self._auth_headers(user["token"]),
            )
        )
        self.assertEqual(history_response.status_code, 200, history_response.text)
        self.assertTrue(any(item["id"] == conversation_id for item in history_response.json()))

        owned_detail_response = self.run_async(
            self.client.get(
                f"/api/solutions/conversations/{conversation_id}",
                headers=self._auth_headers(user["token"]),
            )
        )
        self.assertEqual(owned_detail_response.status_code, 200, owned_detail_response.text)

        async def _fetch_conversation_owner():
            async with async_session() as db:
                conversation = await db.get(Conversation, uuid.UUID(conversation_id))
                return str(conversation.user_id) if conversation and conversation.user_id else None

        owner_id = self.run_async(_fetch_conversation_owner())
        self.assertIsNotNone(owner_id)
        self.assertEqual(owned_detail_response.json()["user_id"], owner_id)

    def test_admin_recent_failures_lists_pipeline_and_diagnostic_errors(self):
        admin = self.run_async(self._register_user(admin=True))

        async def _create_failures():
            async with async_session() as db:
                company = Company(
                    name=f"codex-it-failed-{uuid.uuid4().hex[:8]}",
                    url=f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.example.test/failed",
                    pipeline_status=PipelineStatus.FAILED,
                    publish_status=PublishStatus.DRAFT,
                    pipeline_error="crawler timeout",
                )
                report = DiagnosticReport(
                    url=f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.example.test/failed-diagnostic",
                    status=DiagnosticStatus.FAILED,
                    error_message="invalid html",
                )
                db.add(company)
                db.add(report)
                await db.commit()
                await db.refresh(company)
                await db.refresh(report)
                return str(company.id), str(report.id)

        company_id, report_id = self.run_async(_create_failures())

        response = self.run_async(
            self.client.get(
                "/api/admin/ops/recent-failures?limit=5",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["limit"], 5)
        self.assertTrue(any(item["id"] == company_id for item in payload["companies"]))
        self.assertTrue(any(item["id"] == report_id for item in payload["diagnostics"]))

        company_entry = next(item for item in payload["companies"] if item["id"] == company_id)
        diagnostic_entry = next(item for item in payload["diagnostics"] if item["id"] == report_id)
        self.assertEqual(company_entry["pipeline_error"], "crawler timeout")
        self.assertEqual(diagnostic_entry["error_message"], "invalid html")

    def test_admin_solutions_endpoints_return_conversation_list_and_detail(self):
        admin = self.run_async(self._register_user(admin=True))
        member = self.run_async(self._register_user())
        report_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.example.test/solution-diagnostic"
        public_title = f"公开运营方案-{uuid.uuid4().hex[:6]}"

        async def _create_solution_data():
            async with async_session() as db:
                report = DiagnosticReport(
                    url=report_url,
                    status=DiagnosticStatus.COMPLETED,
                    overall_score=82.5,
                )
                db.add(report)
                await db.flush()

                user_result = await db.execute(select(User).where(User.email == member["email"]))
                member_user = user_result.scalar_one()

                report.user_id = member_user.id
                conversation = Conversation(
                    user_id=member_user.id,
                    title="企业 GEO 提升方案",
                )
                db.add(conversation)
                await db.flush()

                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role=MessageRole.USER,
                        content="请给我一套 GEO 提升方案",
                    )
                )
                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role=MessageRole.ASSISTANT,
                        content="建议先补齐 FAQ、案例页和结构化数据。",
                        recommended_companies=[
                            {"name": "Perplexity AI", "match_score": 0.96, "geo_score": 96}
                        ],
                        diagnostic_context_id=report.id,
                    )
                )
                public_conversation = Conversation(
                    user_id=None,
                    title=public_title,
                )
                db.add(public_conversation)
                await db.flush()
                db.add(
                    Message(
                        conversation_id=public_conversation.id,
                        role=MessageRole.ASSISTANT,
                        content="这是一条公开方案会话。",
                        recommended_companies=[],
                    )
                )
                await db.commit()
                return str(conversation.id), str(report.id), str(member_user.id), str(public_conversation.id)

        conversation_id, report_id, member_user_id, public_conversation_id = self.run_async(_create_solution_data())

        list_response = self.run_async(
            self.client.get(
                "/api/admin/solutions/conversations",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(list_response.status_code, 200, list_response.text)
        payload = list_response.json()
        self.assertTrue(any(item["id"] == conversation_id for item in payload["items"]))
        entry = next(item for item in payload["items"] if item["id"] == conversation_id)
        self.assertEqual(entry["user_id"], member_user_id)
        self.assertEqual(entry["message_count"], 2)
        self.assertEqual(entry["assistant_message_count"], 1)
        self.assertTrue(entry["has_recommendations"])
        self.assertEqual(entry["recommendation_company_count"], 1)
        self.assertEqual(entry["diagnostic_context_count"], 1)
        self.assertIn(report_id, entry["diagnostic_context_ids"])
        self.assertGreaterEqual(payload["summary"]["owned_conversation_count"], 1)
        self.assertIn("public_conversation_count", payload["summary"])

        detail_response = self.run_async(
            self.client.get(
                f"/api/admin/solutions/conversations/{conversation_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        detail = detail_response.json()
        self.assertEqual(detail["id"], conversation_id)
        self.assertEqual(len(detail["messages"]), 2)
        self.assertEqual(detail["message_count"], 2)
        self.assertEqual(detail["assistant_message_count"], 1)
        self.assertEqual(detail["diagnostic_context_count"], 1)
        self.assertEqual(detail["recommended_company_count"], 1)
        assistant_message = next(msg for msg in detail["messages"] if msg["role"] == "assistant")
        self.assertEqual(assistant_message["diagnostic_context"]["report_id"], report_id)
        self.assertEqual(assistant_message["recommended_companies"][0]["name"], "Perplexity AI")

        search_response = self.run_async(
            self.client.get(
                "/api/admin/solutions/conversations?search=Perplexity",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(search_response.status_code, 200, search_response.text)
        self.assertTrue(any(item["id"] == conversation_id for item in search_response.json()["items"]))

        public_filter_response = self.run_async(
            self.client.get(
                f"/api/admin/solutions/conversations?visibility=public&search={public_title}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(public_filter_response.status_code, 200, public_filter_response.text)
        self.assertTrue(any(item["id"] == public_conversation_id for item in public_filter_response.json()["items"]))

        owned_filter_response = self.run_async(
            self.client.get(
                "/api/admin/solutions/conversations?visibility=owned&search=企业 GEO 提升方案",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(owned_filter_response.status_code, 200, owned_filter_response.text)
        self.assertTrue(any(item["id"] == conversation_id for item in owned_filter_response.json()["items"]))

        recommendation_filter_response = self.run_async(
            self.client.get(
                "/api/admin/solutions/conversations?linkage=recommendations&search=企业 GEO 提升方案",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(recommendation_filter_response.status_code, 200, recommendation_filter_response.text)
        self.assertTrue(any(item["id"] == conversation_id for item in recommendation_filter_response.json()["items"]))

        diagnostics_filter_response = self.run_async(
            self.client.get(
                "/api/admin/solutions/conversations?linkage=diagnostics&search=企业 GEO 提升方案",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(diagnostics_filter_response.status_code, 200, diagnostics_filter_response.text)
        self.assertTrue(any(item["id"] == conversation_id for item in diagnostics_filter_response.json()["items"]))

    def test_admin_can_delete_solution_conversation(self):
        admin = self.run_async(self._register_user(admin=True))
        member = self.run_async(self._register_user())

        async def _create_conversation():
            async with async_session() as db:
                user_result = await db.execute(select(User).where(User.email == member["email"]))
                member_user = user_result.scalar_one()

                conversation = Conversation(
                    user_id=member_user.id,
                    title="待删除方案会话",
                )
                db.add(conversation)
                await db.flush()
                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role=MessageRole.USER,
                        content="删除我",
                    )
                )
                await db.commit()
                return str(conversation.id)

        conversation_id = self.run_async(_create_conversation())

        delete_response = self.run_async(
            self.client.delete(
                f"/api/admin/solutions/conversations/{conversation_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(delete_response.status_code, 200, delete_response.text)
        self.assertEqual(delete_response.json()["status"], "deleted")

        async def _fetch_counts():
            async with async_session() as db:
                conversation_count = await db.scalar(
                    select(func.count()).select_from(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
                )
                message_count = await db.scalar(
                    select(func.count()).select_from(Message).where(Message.conversation_id == uuid.UUID(conversation_id))
                )
                return conversation_count, message_count

        conversation_count, message_count = self.run_async(_fetch_counts())
        self.assertEqual(conversation_count, 0)
        self.assertEqual(message_count, 0)

    def test_admin_solution_templates_can_be_viewed_and_updated(self):
        admin = self.run_async(self._register_user(admin=True))
        defaults = get_default_solution_template_config()

        async def _capture_template_setting():
            async with async_session() as db:
                result = await db.execute(select(Setting).where(Setting.key == "solution_templates"))
                setting = result.scalar_one_or_none()
                if not setting:
                    return None
                return {
                    "value": dict(setting.value or {}),
                    "category": setting.category,
                    "is_public": setting.is_public,
                    "updated_by": setting.updated_by,
                }

        async def _restore_template_setting(snapshot):
            async with async_session() as db:
                result = await db.execute(select(Setting).where(Setting.key == "solution_templates"))
                setting = result.scalar_one_or_none()
                if snapshot is None:
                    if setting:
                        await db.execute(delete(Setting).where(Setting.key == "solution_templates"))
                elif setting:
                    setting.value = snapshot["value"]
                    setting.category = snapshot["category"]
                    setting.is_public = snapshot["is_public"]
                    setting.updated_by = snapshot["updated_by"]
                else:
                    db.add(
                        Setting(
                            key="solution_templates",
                            value=snapshot["value"],
                            category=snapshot["category"],
                            is_public=snapshot["is_public"],
                            updated_by=snapshot["updated_by"],
                        )
                    )
                await db.commit()
            await invalidate_runtime_settings_cache()

        snapshot = self.run_async(_capture_template_setting())

        try:
            get_response = self.run_async(
                self.client.get(
                    "/api/admin/solutions/templates",
                    headers=self._auth_headers(admin["token"]),
                )
            )
            self.assertEqual(get_response.status_code, 200, get_response.text)
            self.assertIn("system_prompt", get_response.json())
            self.assertIn("response_instruction", get_response.json())
            self.assertIn("uses_default", get_response.json())
            self.assertIn("customized_fields", get_response.json())

            update_response = self.run_async(
                self.client.put(
                    "/api/admin/solutions/templates",
                    headers=self._auth_headers(admin["token"]),
                    json={
                        "system_prompt": "你是自定义方案顾问。",
                        "response_instruction": "请只推荐 2 家公司并给出匹配理由。",
                        "streaming_system_prompt": "你是流式输出模式下的自定义顾问。",
                    },
                )
            )
            self.assertEqual(update_response.status_code, 200, update_response.text)
            payload = update_response.json()
            self.assertEqual(payload["system_prompt"], "你是自定义方案顾问。")
            self.assertIn("2 家公司", payload["response_instruction"])
            self.assertIn("流式输出模式", payload["streaming_system_prompt"])
            self.assertIsNotNone(payload["updated_at"])
            self.assertFalse(payload["uses_default"])
            self.assertEqual(payload["customized_field_count"], 3)
            self.assertEqual(sorted(payload["customized_fields"]), sorted(list(defaults.keys())))
            self.assertEqual(payload["updated_by_username"], admin["username"])

            async def _fetch_template_setting():
                async with async_session() as db:
                    result = await db.execute(select(Setting).where(Setting.key == "solution_templates"))
                    return result.scalar_one_or_none()

            setting = self.run_async(_fetch_template_setting())
            self.assertIsNotNone(setting)
            self.assertEqual(setting.category, "solutions")
            self.assertEqual(setting.value["system_prompt"], "你是自定义方案顾问。")

            reset_response = self.run_async(
                self.client.post(
                    "/api/admin/solutions/templates/reset",
                    headers=self._auth_headers(admin["token"]),
                )
            )
            self.assertEqual(reset_response.status_code, 200, reset_response.text)
            reset_payload = reset_response.json()
            self.assertTrue(reset_payload["uses_default"])
            self.assertEqual(reset_payload["customized_fields"], [])
            self.assertIsNone(reset_payload["updated_at"])
            self.assertEqual(reset_payload["system_prompt"], defaults["system_prompt"])
        finally:
            self.run_async(_restore_template_setting(snapshot))

    def test_admin_diagnostics_endpoints_return_report_list_and_detail(self):
        admin = self.run_async(self._register_user(admin=True))
        member = self.run_async(self._register_user())
        company_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.example.test"
        report_url = f"{company_url}/diagnostics"
        company_name = f"codex-it-diagnostic-{uuid.uuid4().hex[:8]}"

        async def _create_diagnostic_data():
            async with async_session() as db:
                user_result = await db.execute(select(User).where(User.email == member["email"]))
                member_user = user_result.scalar_one()

                company = Company(
                    name=company_name,
                    url=company_url,
                    pipeline_status=PipelineStatus.COMPLETED,
                    publish_status=PublishStatus.PUBLISHED,
                    geo_score=88.0,
                )
                db.add(company)
                await db.flush()

                report = DiagnosticReport(
                    url=report_url,
                    company_id=company.id,
                    user_id=member_user.id,
                    status=DiagnosticStatus.COMPLETED,
                    overall_score=79.2,
                    schema_analysis={"score": 80},
                    content_analysis={"score": 78},
                    meta_analysis={"score": 76},
                    citation_analysis={"score": 83},
                    recommendations={"high_priority": ["补充 FAQ schema"]},
                )
                db.add(report)
                await db.flush()

                conversation = Conversation(
                    user_id=member_user.id,
                    title="基于诊断结果生成优化方案",
                )
                db.add(conversation)
                await db.flush()

                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role=MessageRole.USER,
                        content="请根据这份诊断结果给我一版优化方案。",
                        diagnostic_context_id=report.id,
                    )
                )
                await db.commit()
                return str(report.id), str(company.id), member_user.username, str(conversation.id)

        report_id, company_id, username, conversation_id = self.run_async(_create_diagnostic_data())

        list_response = self.run_async(
            self.client.get(
                "/api/admin/diagnostics/reports",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(list_response.status_code, 200, list_response.text)
        payload = list_response.json()
        self.assertTrue(any(item["id"] == report_id for item in payload["items"]))
        entry = next(item for item in payload["items"] if item["id"] == report_id)
        self.assertEqual(entry["company_id"], company_id)
        self.assertEqual(entry["username"], username)
        self.assertEqual(entry["status"], "completed")

        company_search_response = self.run_async(
            self.client.get(
                f"/api/admin/diagnostics/reports?search={company_name.split('-')[-1]}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(company_search_response.status_code, 200, company_search_response.text)
        self.assertTrue(any(item["id"] == report_id for item in company_search_response.json()["items"]))

        user_search_response = self.run_async(
            self.client.get(
                f"/api/admin/diagnostics/reports?search={username}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(user_search_response.status_code, 200, user_search_response.text)
        self.assertTrue(any(item["id"] == report_id for item in user_search_response.json()["items"]))

        detail_response = self.run_async(
            self.client.get(
                f"/api/admin/diagnostics/reports/{report_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        detail = detail_response.json()
        self.assertEqual(detail["id"], report_id)
        self.assertEqual(detail["overall_score"], 79.2)
        self.assertEqual(detail["recommendations"]["high_priority"], ["补充 FAQ schema"])
        self.assertTrue(detail["related_solutions"])
        self.assertEqual(detail["related_solutions"][0]["id"], conversation_id)
        self.assertIn("diagnostic_context", detail["related_solutions"][0]["match_types"])

    def test_admin_can_retry_failed_diagnostic_report(self):
        admin = self.run_async(self._register_user(admin=True))
        member = self.run_async(self._register_user())
        report_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.example.test/retry"

        async def _create_failed_report():
            async with async_session() as db:
                user_result = await db.execute(select(User).where(User.email == member["email"]))
                member_user = user_result.scalar_one()

                report = DiagnosticReport(
                    url=report_url,
                    user_id=member_user.id,
                    status=DiagnosticStatus.FAILED,
                    error_message="schema parser error",
                )
                db.add(report)
                await db.commit()
                return str(report.id)

        report_id = self.run_async(_create_failed_report())

        with patch("app.core.celery_app.celery_app.send_task") as send_task:
            retry_response = self.run_async(
                self.client.post(
                    f"/api/admin/diagnostics/reports/{report_id}/retry",
                    headers=self._auth_headers(admin["token"]),
                )
            )

        self.assertEqual(retry_response.status_code, 200, retry_response.text)
        self.assertEqual(retry_response.json()["status"], "retrying")
        send_task.assert_called_once()
        self.assertEqual(send_task.call_args.args[0], "app.tasks.crawl.crawl_diagnostic_page")
        self.assertEqual(send_task.call_args.kwargs["args"][0], report_id)
        self.assertEqual(send_task.call_args.kwargs["args"][1], report_url)

        async def _fetch_report():
            async with async_session() as db:
                result = await db.execute(select(DiagnosticReport).where(DiagnosticReport.id == uuid.UUID(report_id)))
                return result.scalar_one()

        report = self.run_async(_fetch_report())
        self.assertEqual(report.status, DiagnosticStatus.PENDING)
        self.assertIsNone(report.error_message)

    def test_admin_can_delete_diagnostic_report_and_clear_message_context(self):
        admin = self.run_async(self._register_user(admin=True))
        member = self.run_async(self._register_user())
        report_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.example.test/delete-report"

        async def _create_report_context():
            async with async_session() as db:
                user_result = await db.execute(select(User).where(User.email == member["email"]))
                member_user = user_result.scalar_one()
                report = DiagnosticReport(
                    url=report_url,
                    user_id=member_user.id,
                    status=DiagnosticStatus.COMPLETED,
                    overall_score=91,
                )
                db.add(report)
                await db.flush()
                conversation = Conversation(user_id=member_user.id, title="Diagnostic delete context")
                db.add(conversation)
                await db.flush()
                message = Message(
                    conversation_id=conversation.id,
                    role=MessageRole.USER,
                    content="Use this diagnostic",
                    diagnostic_context_id=report.id,
                )
                db.add(message)
                await db.commit()
                return str(report.id), str(message.id)

        report_id, message_id = self.run_async(_create_report_context())

        delete_response = self.run_async(
            self.client.delete(
                f"/api/admin/diagnostics/reports/{report_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(delete_response.status_code, 200, delete_response.text)
        self.assertEqual(delete_response.json()["status"], "deleted")

        async def _assert_cleanup():
            async with async_session() as db:
                self.assertIsNone(await db.get(DiagnosticReport, uuid.UUID(report_id)))
                message = await db.get(Message, uuid.UUID(message_id))
                self.assertIsNotNone(message)
                self.assertIsNone(message.diagnostic_context_id)

        self.run_async(_assert_cleanup())

    def test_admin_diagnostic_rules_and_export_workflow(self):
        admin = self.run_async(self._register_user(admin=True))
        member = self.run_async(self._register_user())
        report_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.example.test/export"

        async def _capture_rule_setting():
            async with async_session() as db:
                result = await db.execute(select(Setting).where(Setting.key == "diagnostic_rule_weights"))
                setting = result.scalar_one_or_none()
                if not setting:
                    return None
                return {
                    "value": dict(setting.value or {}),
                    "category": setting.category,
                    "is_public": setting.is_public,
                    "updated_by": setting.updated_by,
                }

        async def _restore_rule_setting(snapshot):
            async with async_session() as db:
                result = await db.execute(select(Setting).where(Setting.key == "diagnostic_rule_weights"))
                setting = result.scalar_one_or_none()
                if snapshot is None:
                    if setting:
                        await db.execute(delete(Setting).where(Setting.key == "diagnostic_rule_weights"))
                elif setting:
                    setting.value = snapshot["value"]
                    setting.category = snapshot["category"]
                    setting.is_public = snapshot["is_public"]
                    setting.updated_by = snapshot["updated_by"]
                else:
                    db.add(
                        Setting(
                            key="diagnostic_rule_weights",
                            value=snapshot["value"],
                            category=snapshot["category"],
                            is_public=snapshot["is_public"],
                            updated_by=snapshot["updated_by"],
                        )
                    )
                await db.commit()
            await invalidate_runtime_settings_cache()

        async def _create_completed_report():
            async with async_session() as db:
                user_result = await db.execute(select(User).where(User.email == member["email"]))
                member_user = user_result.scalar_one()

                report = DiagnosticReport(
                    url=report_url,
                    user_id=member_user.id,
                    status=DiagnosticStatus.COMPLETED,
                    overall_score=81.3,
                    schema_analysis={"score": 92},
                    content_analysis={"score": 75},
                    meta_analysis={"score": 68},
                    citation_analysis={"score": 70},
                    recommendations={
                        "urgent": [{"item": "补 FAQ schema", "action": "新增 FAQPage JSON-LD"}],
                        "recommended": ["补 canonical"],
                    },
                )
                db.add(report)
                await db.commit()
                return str(report.id)

        snapshot = self.run_async(_capture_rule_setting())
        report_id = self.run_async(_create_completed_report())

        try:
            rules_response = self.run_async(
                self.client.get(
                    "/api/admin/diagnostics/rules",
                    headers=self._auth_headers(admin["token"]),
                )
            )
            self.assertEqual(rules_response.status_code, 200, rules_response.text)
            self.assertEqual(rules_response.json()["weights"]["schema"], 30.0)

            update_response = self.run_async(
                self.client.put(
                    "/api/admin/diagnostics/rules",
                    headers=self._auth_headers(admin["token"]),
                    json={"schema": 45, "content": 25, "meta": 20, "citation": 10},
                )
            )
            self.assertEqual(update_response.status_code, 200, update_response.text)
            updated_rules = update_response.json()
            self.assertEqual(updated_rules["weights"]["schema"], 45.0)
            self.assertEqual(updated_rules["weights"]["citation"], 10.0)
            self.assertAlmostEqual(updated_rules["normalized_weights"]["schema"], 0.45)

            detail_response = self.run_async(
                self.client.get(
                    f"/api/admin/diagnostics/reports/{report_id}",
                    headers=self._auth_headers(admin["token"]),
                )
            )
            self.assertEqual(detail_response.status_code, 200, detail_response.text)
            detail = detail_response.json()
            self.assertEqual(detail["rule_config"]["weights"]["schema"], 45.0)

            export_markdown = self.run_async(
                self.client.get(
                    f"/api/admin/diagnostics/reports/{report_id}/export?format=markdown",
                    headers=self._auth_headers(admin["token"]),
                )
            )
            self.assertEqual(export_markdown.status_code, 200, export_markdown.text)
            self.assertIn("# GEO 诊断报告", export_markdown.text)
            self.assertIn(report_url, export_markdown.text)
            self.assertIn("Schema: 45.0%", export_markdown.text)
            self.assertIn("补 FAQ schema", export_markdown.text)

            export_json = self.run_async(
                self.client.get(
                    f"/api/admin/diagnostics/reports/{report_id}/export?format=json",
                    headers=self._auth_headers(admin["token"]),
                )
            )
            self.assertEqual(export_json.status_code, 200, export_json.text)
            self.assertEqual(export_json.json()["id"], report_id)
            self.assertEqual(export_json.json()["rule_config"]["weights"]["content"], 25.0)
        finally:
            self.run_async(_restore_rule_setting(snapshot))

    def test_admin_content_list_supports_filters_search_and_summary(self):
        admin = self.run_async(self._register_user(admin=True))
        unique_token = uuid.uuid4().hex[:8]
        tutorial_slug = f"{TEST_CONTENT_SLUG_PREFIX}schema-{unique_token}"
        draft_slug = f"{TEST_CONTENT_SLUG_PREFIX}draft-{unique_token}"
        template_slug = f"{TEST_CONTENT_SLUG_PREFIX}template-{unique_token}"

        async def _get_content_baseline():
            async with async_session() as db:
                return {
                    "tutorial_total": await db.scalar(
                        select(func.count(Content.id)).where(Content.content_type == ContentType.TUTORIAL)
                    ),
                    "tutorial_published": await db.scalar(
                        select(func.count(Content.id)).where(
                            Content.content_type == ContentType.TUTORIAL,
                            Content.status == ContentStatus.PUBLISHED,
                        )
                    ),
                    "draft_assets": await db.scalar(
                        select(func.count(Content.id)).where(Content.status == ContentStatus.DRAFT)
                    ),
                    "template_total": await db.scalar(
                        select(func.count(Content.id)).where(Content.content_type == ContentType.TEMPLATE)
                    ),
                    "total_views": await db.scalar(
                        select(func.coalesce(func.sum(Content.view_count), 0))
                    ),
                }

        baseline = self.run_async(_get_content_baseline())

        async def _create_content_assets():
            async with async_session() as db:
                db.add_all([
                    Content(
                        title=f"Codex Schema Tutorial {unique_token}",
                        slug=tutorial_slug,
                        content_type=ContentType.TUTORIAL,
                        status=ContentStatus.PUBLISHED,
                        markdown_body="# Schema Tutorial",
                        tags=["Schema", "Guide"],
                        reading_time_minutes=6,
                        view_count=21,
                    ),
                    Content(
                        title=f"Codex Draft Tutorial {unique_token}",
                        slug=draft_slug,
                        content_type=ContentType.TUTORIAL,
                        status=ContentStatus.DRAFT,
                        markdown_body="Draft body",
                        tags=["Checklist"],
                        reading_time_minutes=4,
                        view_count=3,
                    ),
                    Content(
                        title=f"Codex B2B Template {unique_token}",
                        slug=template_slug,
                        content_type=ContentType.TEMPLATE,
                        status=ContentStatus.DRAFT,
                        markdown_body="Template body",
                        tags=["B2B", "Template"],
                        reading_time_minutes=5,
                        view_count=5,
                    ),
                ])
                await db.commit()

        self.run_async(_create_content_assets())

        response = self.run_async(
            self.client.get(
                f"/api/admin/tutorials?content_type=tutorial&status_filter=published&search={unique_token}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["slug"], tutorial_slug)
        self.assertEqual(payload["items"][0]["content_type"], "tutorial")
        self.assertEqual(payload["items"][0]["status"], "published")
        self.assertIn("updated_at", payload["items"][0])
        self.assertEqual(payload["summary"]["tutorial_total"], baseline["tutorial_total"] + 2)
        self.assertEqual(payload["summary"]["tutorial_published"], baseline["tutorial_published"] + 1)
        self.assertEqual(payload["summary"]["draft_assets"], baseline["draft_assets"] + 2)
        self.assertEqual(payload["summary"]["template_total"], baseline["template_total"] + 1)
        self.assertEqual(payload["summary"]["total_views"], baseline["total_views"] + 29)

    def test_admin_content_create_and_update_respects_status_and_type(self):
        admin = self.run_async(self._register_user(admin=True))
        title = f"{TEST_CONTENT_SLUG_PREFIX}{uuid.uuid4().hex[:8]}"

        create_response = self.run_async(
            self.client.post(
                "/api/admin/tutorials",
                headers=self._auth_headers(admin["token"]),
                json={
                    "title": title,
                    "content_type": "whitepaper",
                    "markdown_body": "# Whitepaper",
                    "status": "published",
                    "tags": ["Report"],
                },
            )
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        create_payload = create_response.json()
        content_id = create_payload["id"]
        self.assertRegex(create_payload["path_key"], r"^[a-z]{5}$")

        detail_response = self.run_async(
            self.client.get(
                f"/api/admin/tutorials/{content_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        detail = detail_response.json()
        self.assertEqual(detail["status"], "published")
        self.assertEqual(detail["content_type"], "whitepaper")
        self.assertEqual(detail["path_key"], create_payload["path_key"])

        update_response = self.run_async(
            self.client.put(
                f"/api/admin/tutorials/{content_id}",
                headers=self._auth_headers(admin["token"]),
                json={
                    "title": title,
                    "content_type": "template",
                    "markdown_body": "# Updated Template",
                    "status": "draft",
                    "tags": ["Template"],
                },
            )
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)

        updated_detail_response = self.run_async(
            self.client.get(
                f"/api/admin/tutorials/{content_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(updated_detail_response.status_code, 200, updated_detail_response.text)
        updated_detail = updated_detail_response.json()
        self.assertEqual(updated_detail["status"], "draft")
        self.assertEqual(updated_detail["content_type"], "template")
        self.assertIn("<h1>Updated Template</h1>", updated_detail["html_body"])

        legacy_detail_response = self.run_async(
            self.client.get(
                f"/api/admin/content/{content_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(legacy_detail_response.status_code, 200, legacy_detail_response.text)

    def test_admin_experts_crud_and_public_listing(self):
        admin = self.run_async(self._register_user(admin=True))
        suffix = uuid.uuid4().hex[:8]
        display_name = f"Codex Expert {suffix}"
        slug = f"codex-expert-{suffix}"
        payload = {
            "slug": slug,
            "display_name": display_name,
            "avatar_initials": "CE",
            "title": "GEO 知识库专家",
            "category": "technical",
            "specialty_label": "技术",
            "summary": "负责把企业资料清洗成 AI 可引用的结构化知识库。",
            "expertise": ["知识库生成", "资料清洗", "RAG 内容规范"],
            "consultation": "适合资料分散、内容不统一、AI 难以稳定引用品牌事实时。",
            "keywords": ["知识库", "RAG", "结构化"],
            "sort_order": 9,
            "is_featured": True,
            "is_published": False,
        }

        create_response = self.run_async(
            self.client.post(
                "/api/admin/experts",
                headers=self._auth_headers(admin["token"]),
                json=payload,
            )
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        created = create_response.json()
        expert_id = created["id"]
        self.assertEqual(created["display_name"], display_name)
        self.assertEqual(created["slug"], slug)
        self.assertEqual(created["expertise"], payload["expertise"])
        self.assertFalse(created["is_published"])

        admin_list_response = self.run_async(
            self.client.get(
                f"/api/admin/experts?search={suffix}&category=technical",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(admin_list_response.status_code, 200, admin_list_response.text)
        admin_list = admin_list_response.json()
        self.assertEqual(admin_list["total"], 1)
        self.assertEqual(admin_list["items"][0]["id"], expert_id)
        self.assertEqual(admin_list["summary"]["draft"], 1)

        featured_list_response = self.run_async(
            self.client.get(
                f"/api/admin/experts?search={suffix}&status_filter=featured",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(featured_list_response.status_code, 200, featured_list_response.text)
        featured_list = featured_list_response.json()
        self.assertEqual(featured_list["total"], 1)
        self.assertEqual(featured_list["items"][0]["id"], expert_id)

        public_draft_response = self.run_async(self.client.get("/api/experts?category=technical"))
        self.assertEqual(public_draft_response.status_code, 200, public_draft_response.text)
        self.assertNotIn(expert_id, [item["id"] for item in public_draft_response.json()["items"]])

        update_payload = {**payload, "title": "GEO 技术与知识库专家", "is_published": True}
        update_response = self.run_async(
            self.client.put(
                f"/api/admin/experts/{expert_id}",
                headers=self._auth_headers(admin["token"]),
                json=update_payload,
            )
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)
        self.assertEqual(update_response.json()["title"], "GEO 技术与知识库专家")
        self.assertTrue(update_response.json()["is_published"])

        public_response = self.run_async(self.client.get(f"/api/experts?search={suffix}"))
        self.assertEqual(public_response.status_code, 200, public_response.text)
        public_payload = public_response.json()
        self.assertEqual(public_payload["total"], 1)
        self.assertEqual(public_payload["items"][0]["id"], expert_id)
        self.assertEqual(public_payload["items"][0]["specialty_label"], "技术")

        delete_response = self.run_async(
            self.client.delete(
                f"/api/admin/experts/{expert_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(delete_response.status_code, 204, delete_response.text)

        detail_after_delete = self.run_async(
            self.client.get(
                f"/api/admin/experts/{expert_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(detail_after_delete.status_code, 404)

    def test_seeded_experts_are_published_and_keep_public_slugs(self):
        response = self.run_async(self.client.get("/api/experts"))
        self.assertEqual(response.status_code, 200, response.text)

        experts = {item["display_name"]: item for item in response.json()["items"]}
        expected_slugs = {
            "姚金刚": "yao-jingang",
            "乔向阳": "qiao-xiangyang",
            "夫唯": "fu-wei",
            "光头牛哥": "guangtou-niuge",
            "张凯": "zhang-kai",
        }

        self.assertTrue(set(expected_slugs).issubset(experts))
        for display_name, slug in expected_slugs.items():
            self.assertEqual(experts[display_name]["slug"], slug)
            self.assertTrue(experts[display_name]["is_published"])
            self.assertTrue(experts[display_name]["summary"])
            self.assertTrue(experts[display_name]["consultation"])
            self.assertTrue(experts[display_name]["expertise"])

    def test_admin_keyword_pack_workflow(self):
        admin = self.run_async(self._register_user(admin=True))
        title = f"{TEST_KEYWORD_TITLE_PREFIX}{uuid.uuid4().hex[:8]}"
        invalid_source_response = self.run_async(
            self.client.post(
                "/api/admin/keywords/packs",
                headers=self._auth_headers(admin["token"]),
                json={"seeds": ["CRM 软件"], "source_ref_id": "not-a-uuid"},
            )
        )
        self.assertEqual(invalid_source_response.status_code, 422, invalid_source_response.text)

        fake_expand = {
            "seeds": ["CRM 软件", "AI 搜索优化"],
            "profile": {
                "name": "B2B SaaS",
                "company_hint": "CRM",
                "business_model": "订阅制软件",
                "target_users": ["市场负责人", "销售运营"],
                "keyword_strategy": "优先覆盖采购、对比和 AI 搜索问题。",
            },
            "dimensions": [
                {
                    "key": "semantic",
                    "name": "语义拓展",
                    "icon": "hub",
                    "description": "核心语义和同义表达。",
                    "count": 2,
                    "items": [
                        {
                            "keyword": "CRM 软件推荐",
                            "recommendation_score": 88,
                            "business_score": 82,
                            "reason": "采购意图明确",
                        },
                        {
                            "keyword": "AI 搜索优化 CRM",
                            "recommendation_score": 86,
                            "business_score": 78,
                            "reason": "GEO 场景相关",
                        },
                    ],
                }
            ],
            "summary": {
                "total_keywords": 2,
                "average_recommendation_score": 87,
                "average_business_score": 80,
                "high_recommendation_ratio": 100,
                "high_business_ratio": 50,
            },
        }

        with patch("app.api.routes.admin.expand_keywords", new=AsyncMock(return_value=fake_expand)):
            create_response = self.run_async(
                self.client.post(
                    "/api/admin/keywords/packs",
                    headers=self._auth_headers(admin["token"]),
                    json={"title": title, "seeds": ["CRM 软件", "AI 搜索优化"], "source_type": "manual"},
                )
            )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        created = create_response.json()
        pack_id = created["id"]
        self.assertEqual(created["title"], title)
        self.assertEqual(created["total_keywords"], 2)
        self.assertEqual(created["dimensions"][0]["items"][0]["keyword"], "CRM 软件推荐")

        list_response = self.run_async(
            self.client.get(
                f"/api/admin/keywords/packs?search={title}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(list_response.status_code, 200, list_response.text)
        listed = list_response.json()
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["items"][0]["id"], pack_id)

        summary_response = self.run_async(
            self.client.get("/api/admin/keywords/summary", headers=self._auth_headers(admin["token"]))
        )
        self.assertEqual(summary_response.status_code, 200, summary_response.text)
        self.assertGreaterEqual(summary_response.json()["total_packs"], 1)

        export_response = self.run_async(
            self.client.get(
                f"/api/admin/keywords/packs/{pack_id}/export",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(export_response.status_code, 200, export_response.text)
        self.assertIn("CRM 软件推荐", export_response.text)

        delete_response = self.run_async(
            self.client.delete(
                f"/api/admin/keywords/packs/{pack_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(delete_response.status_code, 204, delete_response.text)

    def test_admin_can_create_local_user(self):
        admin = self.run_async(self._register_user(admin=True))
        suffix = uuid.uuid4().hex[:8]
        username = f"{TEST_USERNAME_PREFIX}invite_{suffix}"
        email = f"{TEST_EMAIL_PREFIX}invite_{suffix}@example.com"

        create_response = self.run_async(
            self.client.post(
                "/api/admin/users",
                headers=self._auth_headers(admin["token"]),
                json={
                    "username": username,
                    "email": email,
                    "password": TEST_PASSWORD,
                    "role": "enterprise",
                },
            )
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        created = create_response.json()
        self.assertEqual(created["username"], username)
        self.assertEqual(created["role"], "enterprise")

        list_response = self.run_async(
            self.client.get(
                f"/api/admin/users?search={username}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertEqual(list_response.json()["total"], 1)

        duplicate_response = self.run_async(
            self.client.post(
                "/api/admin/users",
                headers=self._auth_headers(admin["token"]),
                json={
                    "username": username,
                    "email": email,
                    "password": TEST_PASSWORD,
                    "role": "user",
                },
            )
        )
        self.assertEqual(duplicate_response.status_code, 409, duplicate_response.text)

    def test_admin_cannot_disable_or_demote_current_admin_account(self):
        admin = self.run_async(self._register_user(admin=True))
        me_response = self.run_async(
            self.client.get("/api/auth/me", headers=self._auth_headers(admin["token"]))
        )
        self.assertEqual(me_response.status_code, 200, me_response.text)
        admin_id = me_response.json()["id"]

        toggle_response = self.run_async(
            self.client.post(
                f"/api/admin/users/{admin_id}/toggle-active",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(toggle_response.status_code, 400, toggle_response.text)
        self.assertIn("不能停用当前登录的管理员账号", toggle_response.text)

        role_response = self.run_async(
            self.client.put(
                f"/api/admin/users/{admin_id}/role",
                headers=self._auth_headers(admin["token"]),
                json={"role": "user"},
            )
        )
        self.assertEqual(role_response.status_code, 400, role_response.text)
        self.assertIn("不能修改当前登录管理员的角色", role_response.text)

        password_response = self.run_async(
            self.client.put(
                f"/api/admin/users/{admin_id}/password",
                headers=self._auth_headers(admin["token"]),
                json={"password": "Test-CodexSelfReset-2026-Aa"},
            )
        )
        self.assertEqual(password_response.status_code, 400, password_response.text)
        self.assertIn("请通过个人中心修改当前管理员密码", password_response.text)

        delete_response = self.run_async(
            self.client.delete(
                f"/api/admin/users/{admin_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(delete_response.status_code, 400, delete_response.text)
        self.assertIn("不能删除当前登录的管理员账号", delete_response.text)

        me_after_response = self.run_async(
            self.client.get("/api/auth/me", headers=self._auth_headers(admin["token"]))
        )
        self.assertEqual(me_after_response.status_code, 200, me_after_response.text)
        self.assertEqual(me_after_response.json()["role"], "admin")
        self.assertTrue(me_after_response.json()["is_active"])

    def test_admin_user_role_update_requires_existing_user(self):
        admin = self.run_async(self._register_user(admin=True))
        missing_id = uuid.uuid4()

        response = self.run_async(
            self.client.put(
                f"/api/admin/users/{missing_id}/role",
                headers=self._auth_headers(admin["token"]),
                json={"role": "user"},
            )
        )
        self.assertEqual(response.status_code, 404, response.text)
        self.assertIn("用户不存在", response.text)

    def test_admin_can_update_other_user_role_and_active_state(self):
        admin = self.run_async(self._register_user(admin=True))
        suffix = uuid.uuid4().hex[:8]
        username = f"{TEST_USERNAME_PREFIX}ops_{suffix}"
        email = f"{TEST_EMAIL_PREFIX}ops_{suffix}@example.com"

        create_response = self.run_async(
            self.client.post(
                "/api/admin/users",
                headers=self._auth_headers(admin["token"]),
                json={
                    "username": username,
                    "email": email,
                    "password": TEST_PASSWORD,
                    "role": "user",
                },
            )
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        user_id = create_response.json()["id"]

        role_response = self.run_async(
            self.client.put(
                f"/api/admin/users/{user_id}/role",
                headers=self._auth_headers(admin["token"]),
                json={"role": "enterprise"},
            )
        )
        self.assertEqual(role_response.status_code, 200, role_response.text)
        self.assertEqual(role_response.json()["role"], "enterprise")

        toggle_response = self.run_async(
            self.client.post(
                f"/api/admin/users/{user_id}/toggle-active",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(toggle_response.status_code, 200, toggle_response.text)
        self.assertFalse(toggle_response.json()["is_active"])

        list_response = self.run_async(
            self.client.get(
                f"/api/admin/users?search={username}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(list_response.status_code, 200, list_response.text)
        listed = list_response.json()["items"][0]
        self.assertEqual(listed["role"], "enterprise")
        self.assertFalse(listed["is_active"])

    def test_admin_survival_guard_serializes_concurrent_demotion_checks(self):
        first_admin = self.run_async(self._register_user(admin=True))
        second_admin = self.run_async(self._register_user(admin=True))

        async def _exercise_guard():
            from app.api.routes import admin as admin_routes

            async with async_session() as db:
                first_admin_id = await db.scalar(
                    select(User.id).where(User.email == first_admin["email"])
                )
                second_admin_id = await db.scalar(
                    select(User.id).where(User.email == second_admin["email"])
                )

            original_loader = admin_routes._load_admin_user_or_404
            both_loaded = asyncio.Event()
            loaded_count = 0

            async def barrier_loader(db, user_id):
                nonlocal loaded_count
                user = await original_loader(db, user_id)
                loaded_count += 1
                if loaded_count == 2:
                    both_loaded.set()
                await asyncio.wait_for(both_loaded.wait(), timeout=1)
                return user

            with patch("app.api.routes.admin._load_admin_user_or_404", new=barrier_loader):
                responses = await asyncio.gather(
                    self.client.put(
                        f"/api/admin/users/{second_admin_id}/role",
                        headers=self._auth_headers(first_admin["token"]),
                        json={"role": "user"},
                    ),
                    self.client.put(
                        f"/api/admin/users/{first_admin_id}/role",
                        headers=self._auth_headers(second_admin["token"]),
                        json={"role": "user"},
                    ),
                )

            self.assertEqual(sorted(response.status_code for response in responses), [200, 400])
            async with async_session() as db:
                self.assertEqual(await db.scalar(
                    select(func.count(User.id)).where(
                        User.role == UserRole.ADMIN,
                        User.is_active == True,
                    )
                ), 1)

        self.run_async(_exercise_guard())

    def test_concurrent_admin_password_resets_increment_token_version_twice(self):
        admin = self.run_async(self._register_user(admin=True))
        target = self.run_async(self._register_user())

        async def _exercise_resets():
            from app.api.routes import admin as admin_routes

            async with async_session() as db:
                target_id = await db.scalar(select(User.id).where(User.email == target["email"]))

            original_loader = admin_routes._load_admin_user_or_404
            both_loaded = asyncio.Event()
            loaded_count = 0

            async def barrier_loader(db, user_id):
                nonlocal loaded_count
                user = await original_loader(db, user_id)
                loaded_count += 1
                if loaded_count == 2:
                    both_loaded.set()
                await asyncio.wait_for(both_loaded.wait(), timeout=1)
                return user

            with patch("app.api.routes.admin._load_admin_user_or_404", new=barrier_loader):
                responses = await asyncio.gather(
                    self.client.put(
                        f"/api/admin/users/{target_id}/password",
                        headers=self._auth_headers(admin["token"]),
                        json={"password": "Test-ConcurrentResetA-123"},
                    ),
                    self.client.put(
                        f"/api/admin/users/{target_id}/password",
                        headers=self._auth_headers(admin["token"]),
                        json={"password": "Test-ConcurrentResetB-123"},
                    ),
                )
            self.assertEqual([response.status_code for response in responses], [200, 200])
            async with async_session() as db:
                token_version = await db.scalar(
                    select(User.token_version).where(User.id == target_id)
                )
                self.assertEqual(token_version, 2)

        self.run_async(_exercise_resets())

    def test_admin_can_edit_reset_password_and_delete_user(self):
        admin = self.run_async(self._register_user(admin=True))
        suffix = uuid.uuid4().hex[:8]
        username = f"{TEST_USERNAME_PREFIX}crud_{suffix}"
        email = f"{TEST_EMAIL_PREFIX}crud_{suffix}@example.com"
        phone = f"{TEST_PHONE_PREFIX}{str(uuid.uuid4().int)[-4:]}"
        updated_username = f"{TEST_USERNAME_PREFIX}crud_updated_{suffix}"
        updated_email = f"{TEST_EMAIL_PREFIX}crud_updated_{suffix}@example.com"
        updated_phone = f"{TEST_PHONE_PREFIX}{str(uuid.uuid4().int)[-4:]}"
        reset_password = "Test-CodexReset-2026-Aa"

        create_response = self.run_async(
            self.client.post(
                "/api/admin/users",
                headers=self._auth_headers(admin["token"]),
                json={
                    "username": username,
                    "email": email,
                    "phone": phone,
                    "password": TEST_PASSWORD,
                    "role": "user",
                },
            )
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        user_id = uuid.UUID(create_response.json()["id"])

        update_response = self.run_async(
            self.client.put(
                f"/api/admin/users/{user_id}",
                headers=self._auth_headers(admin["token"]),
                json={
                    "username": updated_username,
                    "email": updated_email,
                    "phone": updated_phone,
                    "role": "enterprise",
                    "is_active": True,
                    "is_verified": True,
                },
            )
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)
        updated = update_response.json()
        self.assertEqual(updated["username"], updated_username)
        self.assertEqual(updated["email"], updated_email)
        self.assertEqual(updated["phone"], updated_phone)
        self.assertEqual(updated["role"], "enterprise")
        self.assertTrue(updated["is_verified"])

        original_login_response = self.run_async(
            self.client.post(
                "/api/auth/login",
                json={"phone": updated_phone, "password": TEST_PASSWORD},
            )
        )
        self.assertEqual(original_login_response.status_code, 200, original_login_response.text)
        original_token = original_login_response.json()["access_token"]

        reset_response = self.run_async(
            self.client.put(
                f"/api/admin/users/{user_id}/password",
                headers=self._auth_headers(admin["token"]),
                json={"password": reset_password},
            )
        )
        self.assertEqual(reset_response.status_code, 200, reset_response.text)

        revoked_token_response = self.run_async(
            self.client.get(
                "/api/auth/me",
                headers=self._auth_headers(original_token),
            )
        )
        self.assertEqual(revoked_token_response.status_code, 401, revoked_token_response.text)

        login_response = self.run_async(
            self.client.post(
                "/api/auth/login",
                json={"phone": updated_phone, "password": reset_password},
            )
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)

        holder = {}

        async def _create_related_rows():
            async with async_session() as db:
                company = Company(
                    name=f"Codex Delete Target {suffix}",
                    url=f"{TEST_COMPANY_URL_PREFIX}{suffix}.example.com",
                    submitted_by=user_id,
                    upvotes=1,
                )
                db.add(company)
                await db.flush()
                conversation = Conversation(user_id=user_id, title="Delete target")
                db.add(conversation)
                await db.flush()
                db.add(Message(conversation_id=conversation.id, role=MessageRole.USER, content="hello"))
                report = DiagnosticReport(
                    url=f"{TEST_COMPANY_URL_PREFIX}{suffix}.example.com",
                    company_id=company.id,
                    user_id=user_id,
                )
                db.add(report)
                db.add(CompanyVote(company_id=company.id, user_id=user_id))
                db.add(
                    UserDailyUsage(
                        user_id=user_id,
                        usage_date=date.today(),
                        total_tokens=100,
                        request_count=1,
                    )
                )
                db.add(
                    AIUsageEvent(
                        user_id=user_id,
                        module="test",
                        provider_source="platform",
                        total_tokens=100,
                        request_id=f"{TEST_USAGE_REQUEST_PREFIX}{suffix}",
                    )
                )
                content = Content(
                    title=f"Codex Delete Content {suffix}",
                    slug=f"{TEST_CONTENT_SLUG_PREFIX}{suffix}",
                    content_type=ContentType.TUTORIAL,
                    status=ContentStatus.DRAFT,
                    author_id=user_id,
                )
                db.add(content)
                setting = Setting(
                    key=f"{TEST_SETTING_PREFIX}delete_{suffix}",
                    value={"enabled": True},
                    category="test",
                    updated_by=user_id,
                )
                db.add(setting)
                keyword_pack = KeywordPack(
                    title=f"{TEST_KEYWORD_TITLE_PREFIX}{suffix}",
                    seed_keywords=["codex"],
                    created_by=user_id,
                )
                db.add(keyword_pack)
                expert = ExpertProfile(
                    display_name=f"{TEST_EXPERT_NAME_PREFIX}{suffix}",
                    title="Codex Reviewer",
                    created_by=user_id,
                )
                db.add(expert)
                homepage = HomepageRelease(
                    title=f"{TEST_HOMEPAGE_TITLE_PREFIX}{suffix}",
                    source_type=HomepageSourceType.SINGLE_HTML,
                    storage_path=f"codex/{suffix}/index.html",
                    created_by=user_id,
                )
                db.add(homepage)
                await db.commit()
                holder["company_id"] = company.id
                holder["conversation_id"] = conversation.id
                holder["report_id"] = report.id
                holder["content_id"] = content.id
                holder["setting_key"] = setting.key
                holder["keyword_pack_id"] = keyword_pack.id
                holder["expert_id"] = expert.id
                holder["homepage_id"] = homepage.id

        self.run_async(_create_related_rows())

        delete_response = self.run_async(
            self.client.delete(
                f"/api/admin/users/{user_id}",
                headers=self._auth_headers(admin["token"]),
            )
        )
        self.assertEqual(delete_response.status_code, 200, delete_response.text)

        async def _assert_deleted_cleanup():
            async with async_session() as db:
                self.assertIsNone(await db.get(User, user_id))
                self.assertIsNone(await db.get(Conversation, holder["conversation_id"]))
                self.assertIsNone(
                    (
                        await db.execute(
                            select(Message.id).where(Message.conversation_id == holder["conversation_id"])
                        )
                    ).scalar_one_or_none()
                )
                self.assertIsNone(
                    (
                        await db.execute(select(CompanyVote.id).where(CompanyVote.user_id == user_id))
                    ).scalar_one_or_none()
                )
                self.assertIsNone(
                    (
                        await db.execute(select(UserDailyUsage.id).where(UserDailyUsage.user_id == user_id))
                    ).scalar_one_or_none()
                )
                company = await db.get(Company, holder["company_id"])
                self.assertIsNotNone(company)
                self.assertIsNone(company.submitted_by)
                self.assertEqual(company.upvotes, 0)
                report = await db.get(DiagnosticReport, holder["report_id"])
                self.assertIsNotNone(report)
                self.assertIsNone(report.user_id)
                usage_event = (
                    await db.execute(
                        select(AIUsageEvent).where(AIUsageEvent.request_id == f"{TEST_USAGE_REQUEST_PREFIX}{suffix}")
                    )
                ).scalar_one()
                self.assertIsNone(usage_event.user_id)
                content = await db.get(Content, holder["content_id"])
                self.assertIsNotNone(content)
                self.assertIsNone(content.author_id)
                setting = await db.get(Setting, holder["setting_key"])
                self.assertIsNotNone(setting)
                self.assertIsNone(setting.updated_by)
                keyword_pack = await db.get(KeywordPack, holder["keyword_pack_id"])
                self.assertIsNotNone(keyword_pack)
                self.assertIsNone(keyword_pack.created_by)
                expert = await db.get(ExpertProfile, holder["expert_id"])
                self.assertIsNotNone(expert)
                self.assertIsNone(expert.created_by)
                homepage = await db.get(HomepageRelease, holder["homepage_id"])
                self.assertIsNotNone(homepage)
                self.assertIsNone(homepage.created_by)

        self.run_async(_assert_deleted_cleanup())

    def test_public_content_detail_returns_rendered_html(self):
        slug = f"{TEST_CONTENT_SLUG_PREFIX}{uuid.uuid4().hex[:10]}"
        holder = {}

        async def _create_content():
            async with async_session() as db:
                article = Content(
                    title="Codex Content Rendering",
                    slug=slug,
                    content_type=ContentType.TUTORIAL,
                    status=ContentStatus.PUBLISHED,
                    markdown_body="# Heading\n\n```python\nprint('hello')\n```",
                    tags=["Guide"],
                    reading_time_minutes=3,
                )
                db.add(article)
                await db.commit()
                await db.refresh(article)
                holder["path_key"] = article.path_key

        self.run_async(_create_content())

        response = self.run_async(self.client.get(f"/api/content/{slug}"))
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["slug"], slug)
        self.assertRegex(payload["path_key"], r"^[a-z]{5}$")
        self.assertIn("<h1>Heading</h1>", payload["html_body"])
        self.assertIn("<code", payload["html_body"])
        self.assertIn("print", payload["html_body"])

        resolve_response = self.run_async(self.client.get(f"/api/content/resolve/{holder['path_key']}"))
        self.assertEqual(resolve_response.status_code, 200, resolve_response.text)
        self.assertEqual(resolve_response.json()["slug"], slug)

    def test_tutorial_pages_are_server_rendered_with_schema(self):
        slug = f"{TEST_CONTENT_SLUG_PREFIX}{uuid.uuid4().hex[:10]}"
        holder = {}

        async def _create_content():
            async with async_session() as db:
                article = Content(
                    title="GEO SSR Tutorial",
                    slug=slug,
                    content_type=ContentType.TUTORIAL,
                    status=ContentStatus.PUBLISHED,
                    markdown_body="# GEO SSR Tutorial\n\n这是服务端直出的正文段落。\n\n## 什么是直出\n\n让搜索引擎直接拿到 HTML 正文。",
                    tags=["GEO认知", "SSR", "Schema"],
                    reading_time_minutes=4,
                )
                db.add(article)
                await db.commit()
                await db.refresh(article)
                holder["path_key"] = article.path_key

        self.run_async(_create_content())

        home_response = self.run_async(self.client.get("/tutorial"))
        self.assertEqual(home_response.status_code, 200, home_response.text)
        self.assertIn("GEO 教程中心", home_response.text)
        self.assertNotIn("Wiki", home_response.text)
        self.assertIn("GEO SSR Tutorial", home_response.text)
        self.assertIn("application/ld+json", home_response.text)
        self.assertIn("ItemList", home_response.text)

        detail_response = self.run_async(self.client.get(f"/tutorial/{holder['path_key']}"))
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        self.assertIn("这是服务端直出的正文段落", detail_response.text)
        self.assertIn("什么是直出", detail_response.text)
        self.assertIn("application/ld+json", detail_response.text)
        self.assertIn("TechArticle", detail_response.text)
        self.assertIn(f'rel="canonical" href="http://testserver/tutorial/{holder["path_key"]}"', detail_response.text)


if __name__ == "__main__":
    unittest.main()
