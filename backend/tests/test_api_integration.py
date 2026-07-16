import sys
import asyncio
import copy
import io
import os
import tempfile
import unittest
import uuid
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models.company import Company, PipelineStatus, PublishStatus  # noqa: E402
from app.models.content import Content, ContentStatus, ContentType  # noqa: E402
from app.models.conversation import Conversation, Message, MessageRole  # noqa: E402
from app.models.diagnostic import DiagnosticReport, DiagnosticStatus  # noqa: E402
from app.models.expert import ExpertProfile  # noqa: E402
from app.models.homepage import HomepageRelease, HomepageSourceType  # noqa: E402
from app.models.ai_usage import AIUsageEvent, UserDailyUsage  # noqa: E402
from app.models.keyword import KeywordItem, KeywordPack  # noqa: E402
from app.models.settings import Setting  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.models.vote import CompanyVote  # noqa: E402
from app.services.runtime_settings import (  # noqa: E402
    get_default_solution_template_config,
    invalidate_runtime_settings_cache,
)
from app.services.settings_security import MASKED_VALUE, is_encrypted_setting_value  # noqa: E402


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
TEST_PASSWORD = "CodexTest@2026"
_TEST_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_TEST_LOOP)


class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        from app.core.database import engine

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
        return {
            "Authorization": f"Bearer {token}",
            "X-GEOrank-Device-ID": f"integration-device-{token[-32:]}",
        }

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
        next_password = "CodexChanged@2026"

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
                    sensitive_key: {"value": "sk-integration-secret", "category": "api_keys"},
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

    def test_admin_navigation_menu_is_normalized_and_public(self):
        admin = self.run_async(self._register_user(admin=True))

        async def _capture_setting():
            async with async_session() as db:
                result = await db.execute(select(Setting).where(Setting.key == "navigation_menu"))
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
                result = await db.execute(select(Setting).where(Setting.key == "navigation_menu"))
                setting = result.scalar_one_or_none()
                if snapshot is None:
                    if setting:
                        await db.delete(setting)
                elif setting:
                    setting.value = snapshot["value"]
                    setting.category = snapshot["category"]
                    setting.is_public = snapshot["is_public"]
                    setting.updated_by = snapshot["updated_by"]
                else:
                    db.add(Setting(key="navigation_menu", **snapshot))
                await db.commit()
            await invalidate_runtime_settings_cache()

        snapshot = self.run_async(_capture_setting())
        try:
            update_response = self.run_async(
                self.client.put(
                    "/api/admin/settings",
                    headers=self._auth_headers(admin["token"]),
                    json={
                        "navigation_menu": {
                            "value": {
                                "items": [
                                    {"id": "docs", "label": "文档中心", "url": "https://docs.example.com"},
                                    {"id": "home", "label": "首页", "url": "/", "target": "_self"},
                                ]
                            },
                            "category": "basic",
                            "is_public": False,
                        }
                    },
                )
            )
            self.assertEqual(update_response.status_code, 200, update_response.text)

            admin_settings = self.run_async(
                self.client.get("/api/admin/settings", headers=self._auth_headers(admin["token"]))
            ).json()["navigation_menu"]
            self.assertEqual(admin_settings["category"], "frontend")
            self.assertTrue(admin_settings["is_public"])
            self.assertEqual(admin_settings["value"]["items"][0]["target"], "_blank")
            self.assertEqual(admin_settings["value"]["items"][1]["target"], "_self")

            public_menu = self.run_async(self.client.get("/api/settings/public")).json()["navigation_menu"]
            self.assertEqual(public_menu, admin_settings["value"])

            invalid_response = self.run_async(
                self.client.put(
                    "/api/admin/settings",
                    headers=self._auth_headers(admin["token"]),
                    json={
                        "navigation_menu": {
                            "value": {"items": [{"label": "危险", "url": "javascript:alert(1)"}]}
                        }
                    },
                )
            )
            self.assertEqual(invalid_response.status_code, 422, invalid_response.text)
        finally:
            self.run_async(_restore_setting(snapshot))

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
            self.assertNotIn("/", public_modules["companies"]["protected_paths"])
            self.assertEqual(public_modules["companies"]["path"], "/companies")
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

                clone_response = self.run_async(
                    self.client.post(
                        f"/api/admin/homepage/releases/{release['id']}/clone",
                        headers=self._auth_headers(admin["token"]),
                    )
                )
                self.assertEqual(clone_response.status_code, 201, clone_response.text)
                cloned_release = clone_response.json()
                self.assertEqual(cloned_release["status"], "draft")
                self.assertFalse(cloned_release["is_builtin"])
                self.assertIn("可编辑副本", cloned_release["title"])
                cloned_source_response = self.run_async(
                    self.client.get(
                        f"/api/admin/homepage/releases/{cloned_release['id']}/source",
                        headers=self._auth_headers(admin["token"]),
                    )
                )
                self.assertEqual(cloned_source_response.status_code, 200, cloned_source_response.text)
                self.assertIn("自定义首页", cloned_source_response.json()["html"])

                preview_response = self.run_async(
                    self.client.get(
                        release["preview_url"],
                        headers=self._auth_headers(admin["token"]),
                    )
                )
                self.assertEqual(preview_response.status_code, 200, preview_response.text)
                self.assertIn("自定义首页", preview_response.text)
                self.assertIn("script-src 'self'", preview_response.text)
                self.assertNotIn("window.__bad", preview_response.text)
                self.assertEqual(preview_response.text.count('data-georank-navigation-runtime'), 1)
                self.assertNotIn("onerror", preview_response.text.lower())
                self.assertIn(f"/_custom_homepage/releases/{release['id']}/assets/logo.png", preview_response.text)

                source_response = self.run_async(
                    self.client.get(
                        f"/api/admin/homepage/releases/{release['id']}/source",
                        headers=self._auth_headers(admin["token"]),
                    )
                )
                self.assertEqual(source_response.status_code, 200, source_response.text)
                self.assertIn("window.__bad", source_response.json()["html"])
                self.assertEqual(len(source_response.json()["sha256"]), 64)

                activate_response = self.run_async(
                    self.client.post(
                        f"/api/admin/homepage/releases/{release['id']}/activate",
                        headers=self._auth_headers(admin["token"]),
                    )
                )
                self.assertEqual(activate_response.status_code, 200, activate_response.text)
                self.assertEqual(activate_response.json()["runtime"]["mode"], "custom")

                update_response = self.run_async(
                    self.client.put(
                        f"/api/admin/homepage/releases/{release['id']}/source",
                        headers=self._auth_headers(admin["token"]),
                        json={
                            "html": '<html><body onload="bad()"><h1>后台实时更新</h1><script>bad()</script></body></html>',
                            "expected_sha256": source_response.json()["sha256"],
                        },
                    )
                )
                self.assertEqual(update_response.status_code, 200, update_response.text)
                self.assertTrue(update_response.json()["updated_active"])
                active_html = (Path(tmpdir) / "public" / "active" / "index.html").read_text()
                self.assertIn("后台实时更新", active_html)
                self.assertNotIn("onload", active_html.lower())
                self.assertNotIn("bad()", active_html)
                self.assertEqual(active_html.count('data-georank-navigation-runtime'), 1)

                stale_update_response = self.run_async(
                    self.client.put(
                        f"/api/admin/homepage/releases/{release['id']}/source",
                        headers=self._auth_headers(admin["token"]),
                        json={
                            "html": "<html><body><h1>过期编辑</h1></body></html>",
                            "expected_sha256": source_response.json()["sha256"],
                        },
                    )
                )
                self.assertEqual(stale_update_response.status_code, 409, stale_update_response.text)

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
        self.assertTrue(send_task.call_args.kwargs["args"][2])

        status_response = self.run_async(
            self.client.get(
                f"/api/companies/{company_id}/pipeline-status",
                headers=self._auth_headers(user["token"]),
            )
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

    def test_submit_company_restarts_orphaned_pending_record(self):
        user = self.run_async(self._register_user())
        company_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.orphaned.test"

        async def _create_orphaned_company():
            async with async_session() as db:
                member = await db.scalar(select(User).where(User.email == user["email"]))
                company = Company(
                    name="orphaned-pending-company",
                    url=company_url,
                    pipeline_status=PipelineStatus.PENDING,
                    publish_status=PublishStatus.DRAFT,
                    submitted_by=member.id,
                    ai_reservation_id=None,
                )
                db.add(company)
                await db.commit()
                await db.refresh(company)
                return str(company.id)

        company_id = self.run_async(_create_orphaned_company())

        with patch("app.core.celery_app.celery_app.send_task") as send_task:
            retry_response = self.run_async(
                self.client.post(
                    "/api/companies/submit",
                    headers=self._auth_headers(user["token"]),
                    json={"url": company_url},
                )
            )

        self.assertEqual(retry_response.status_code, 202, retry_response.text)
        payload = retry_response.json()
        self.assertTrue(payload["resumed"])
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["company_id"], company_id)
        send_task.assert_called_once()
        self.assertEqual(send_task.call_args.args[0], "app.tasks.crawl.crawl_company_website")
        self.assertEqual(send_task.call_args.kwargs["args"][0], company_id)
        self.assertTrue(send_task.call_args.kwargs["args"][2])

        async def _fetch_reservation_id():
            async with async_session() as db:
                return await db.scalar(
                    select(Company.ai_reservation_id).where(
                        Company.id == uuid.UUID(company_id)
                    )
                )

        self.assertIsNotNone(self.run_async(_fetch_reservation_id()))

    def test_submit_company_marks_pipeline_failed_when_queue_dispatch_fails(self):
        user = self.run_async(self._register_user())
        bare_domain = f"codex-it-{uuid.uuid4().hex[:10]}.queue-failure.test"

        with patch(
            "app.core.celery_app.celery_app.send_task",
            side_effect=RuntimeError("broker unavailable"),
        ):
            submit_response = self.run_async(
                self.client.post(
                    "/api/companies/submit",
                    headers=self._auth_headers(user["token"]),
                    json={"url": bare_domain},
                )
            )

        self.assertEqual(submit_response.status_code, 202, submit_response.text)
        payload = submit_response.json()
        self.assertEqual(payload["status"], "failed")

        async def _fetch_company():
            async with async_session() as db:
                result = await db.execute(
                    select(Company).where(Company.id == uuid.UUID(payload["company_id"]))
                )
                return result.scalar_one()

        company = self.run_async(_fetch_company())
        self.assertEqual(company.pipeline_status, PipelineStatus.FAILED)
        self.assertEqual(company.pipeline_error, "官网分析任务创建失败，请稍后重试。")

    def test_submit_company_requires_login_for_platform_quota(self):
        bare_domain = f"codex-it-{uuid.uuid4().hex[:10]}.public.test"
        company_url = f"https://{bare_domain}"

        with patch("app.core.celery_app.celery_app.send_task") as send_task:
            submit_response = self.run_async(
                self.client.post(
                    "/api/companies/submit",
                    json={"url": bare_domain},
                )
            )

        self.assertEqual(submit_response.status_code, 401, submit_response.text)
        send_task.assert_not_called()

        async def _company_exists():
            async with async_session() as db:
                result = await db.execute(select(Company.id).where(Company.url == company_url))
                return result.scalar_one_or_none() is not None

        self.assertFalse(self.run_async(_company_exists()))

    def test_submit_company_review_requires_completed_pipeline_and_updates_publish_status(self):
        user = self.run_async(self._register_user())
        other_user = self.run_async(self._register_user())
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

        other_submit = self.run_async(
            self.client.post(
                "/api/companies/submit",
                headers=self._auth_headers(other_user["token"]),
                json={"url": company_url},
            )
        )
        self.assertEqual(other_submit.status_code, 403, other_submit.text)

        hidden_status = self.run_async(
            self.client.get(
                f"/api/companies/{company_id}/pipeline-status",
                headers=self._auth_headers(other_user["token"]),
            )
        )
        self.assertEqual(hidden_status.status_code, 404, hidden_status.text)

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
                        category="GEO 服务",
                        tags=["GEO优化"],
                        tech_stack=["OpenAI API"],
                        geo_score=66,
                        geo_details={"schema": 60, "content": 70, "meta": 65, "citation": 68},
                    )
                )
                await db.commit()

        self.run_async(_mark_completed())

        other_review = self.run_async(
            self.client.post(
                f"/api/companies/{company_id}/submit-review",
                headers=self._auth_headers(other_user["token"]),
            )
        )
        self.assertEqual(other_review.status_code, 403, other_review.text)

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

    def test_successful_company_vectorization_keeps_draft_until_user_submits_review(self):
        company_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.vector.test"

        async def _create_company():
            async with async_session() as db:
                company = Company(
                    name="Vector Draft Company",
                    url=company_url,
                    description="用于验证公司知识库向量化后的审核状态。",
                    short_description="向量化状态测试公司。",
                    category="企业服务",
                    tags=["知识库"],
                    geo_score=80,
                    geo_details={"schema": 80, "content": 80, "meta": 80, "citation": 80},
                    pipeline_status=PipelineStatus.VECTORIZING,
                    publish_status=PublishStatus.DRAFT,
                    raw_html_key="companies/vector-draft/raw.html",
                    crawl_pages=[
                        {
                            "url": company_url,
                            "title": "Vector Draft Company",
                            "role": "homepage",
                            "reason": "官网主页",
                            "key": "companies/vector-draft/raw.html",
                            "status": "captured",
                        }
                    ],
                )
                db.add(company)
                await db.commit()
                await db.refresh(company)
                return str(company.id)

        company_id = self.run_async(_create_company())

        async def _embed(chunks):
            return [[0.1] * 1536 for _ in chunks]

        from app.tasks.process import _run_vectorize

        with patch("app.services.storage.storage.get", return_value=b"<html><body>Company knowledge</body></html>"), patch(
            "app.services.ai_client.ai_client.embed_batch",
            new=AsyncMock(side_effect=_embed),
        ), patch("app.services.vector_store.vector_store.ensure_collection"), patch(
            "app.services.vector_store.vector_store.delete_company_vectors"
        ), patch(
            "app.services.vector_store.vector_store.upsert_company_vectors"
        ), patch(
            "app.services.ai_usage.record_async_task_usage",
            new=AsyncMock(),
        ):
            self.run_async(_run_vectorize(company_id))

        async def _fetch_company():
            async with async_session() as db:
                result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
                return result.scalar_one()

        company = self.run_async(_fetch_company())
        self.assertEqual(company.pipeline_status, PipelineStatus.COMPLETED)
        self.assertEqual(company.publish_status, PublishStatus.DRAFT)

    def test_company_vectorization_completes_when_embedding_is_not_configured(self):
        company_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.no-embedding.test"

        async def _create_company():
            async with async_session() as db:
                company = Company(
                    name="No Embedding Company",
                    url=company_url,
                    description="用于验证未配置向量服务时仍能完成公司分析。",
                    category="企业服务",
                    pipeline_status=PipelineStatus.VECTORIZING,
                    publish_status=PublishStatus.DRAFT,
                    raw_html_key="companies/no-embedding/raw.html",
                )
                db.add(company)
                await db.commit()
                await db.refresh(company)
                return str(company.id)

        company_id = self.run_async(_create_company())

        from app.services.ai_client import EmbeddingNotConfiguredError
        from app.tasks.process import _run_vectorize

        with patch(
            "app.services.storage.storage.get",
            return_value=b"<html><body>Company knowledge</body></html>",
        ), patch(
            "app.services.ai_client.ai_client.embed_batch",
            new=AsyncMock(side_effect=EmbeddingNotConfiguredError("embedding unavailable")),
        ), patch(
            "app.services.vector_store.vector_store.ensure_collection"
        ) as ensure_collection, patch(
            "app.services.vector_store.vector_store.delete_company_vectors"
        ) as delete_vectors, patch(
            "app.services.vector_store.vector_store.upsert_company_vectors"
        ) as upsert_vectors, patch(
            "app.services.ai_usage.record_async_task_usage",
            new=AsyncMock(),
        ) as record_usage:
            self.run_async(_run_vectorize(company_id))

        async def _fetch_company():
            async with async_session() as db:
                result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
                return result.scalar_one()

        company = self.run_async(_fetch_company())
        self.assertEqual(company.pipeline_status, PipelineStatus.COMPLETED)
        self.assertIsNone(company.pipeline_error)
        ensure_collection.assert_not_called()
        delete_vectors.assert_not_called()
        upsert_vectors.assert_not_called()
        self.assertEqual(record_usage.await_args.kwargs["metadata"]["vector_count"], 0)
        self.assertEqual(record_usage.await_args.kwargs["estimated_input_tokens"], 0)
        self.assertEqual(record_usage.await_args.kwargs["output_text"], "")

    def test_company_cleaning_generates_geo_profile_from_stored_homepage(self):
        company_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.clean.test"
        homepage_key = "companies/clean-profile/raw.html"
        product_key = "companies/clean-profile/product.html"
        homepage_html = """
        <html><head><title>Clean Profile</title><meta name="description" content="企业介绍"></head>
        <body><h1>Clean Profile</h1><p>企业服务与公开案例。</p></body></html>
        """.encode("utf-8")
        product_html = b"<html><body><h1>SECONDARY_PRODUCT_TEXT</h1></body></html>"
        captured_source = {}

        async def _create_company():
            async with async_session() as db:
                company = Company(
                    name="clean-profile.test",
                    url=company_url,
                    pipeline_status=PipelineStatus.CLEANING,
                    publish_status=PublishStatus.DRAFT,
                    raw_html_key=homepage_key,
                    crawl_pages=[
                        {
                            "url": company_url,
                            "title": "Clean Profile",
                            "role": "homepage",
                            "reason": "官网主页",
                            "key": homepage_key,
                            "status": "captured",
                        },
                        {
                            "url": f"{company_url}/product",
                            "title": "产品",
                            "role": "product",
                            "reason": "产品页面",
                            "key": product_key,
                            "status": "captured",
                        },
                    ],
                )
                db.add(company)
                await db.commit()
                await db.refresh(company)
                return str(company.id)

        async def _extract_profile(source: str, fallback_name: str | None = None):
            captured_source["value"] = source
            return {
                "name": "Clean Profile",
                "description": "提供企业服务与公开案例。",
                "short_description": "企业服务平台。",
                "category": "企业服务",
                "tags": ["企业服务"],
                "tech_stack": [],
                "team_members": [],
            }

        company_id = self.run_async(_create_company())

        def _stored_html(key: str):
            return {homepage_key: homepage_html, product_key: product_html}.get(key)

        from app.tasks.process import _run_clean

        with patch("app.services.company_profile.storage.get", side_effect=_stored_html), patch(
            "app.services.company_profile.extract_company_profile",
            new=AsyncMock(side_effect=_extract_profile),
        ), patch("app.core.celery_app.celery_app.send_task"):
            self.run_async(_run_clean(company_id))

        async def _fetch_company():
            async with async_session() as db:
                result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
                return result.scalar_one()

        company = self.run_async(_fetch_company())
        self.assertIn("SECONDARY_PRODUCT_TEXT", captured_source["value"])
        self.assertEqual(company.pipeline_status, PipelineStatus.GRAPH_BUILDING)
        self.assertIsNotNone(company.geo_score)
        self.assertEqual(set((company.geo_details or {}).keys()), {"schema", "content", "meta", "citation"})

    def test_submit_company_review_requires_pipeline_profile_instead_of_unmetered_hydration(self):
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

        self.assertEqual(final_submit.status_code, 409, final_submit.text)
        self.assertIn("missing_fields", final_submit.json()["detail"])

        async def _fetch_company():
            async with async_session() as db:
                result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
                return result.scalar_one()

        company = self.run_async(_fetch_company())
        self.assertEqual(company.publish_status, PublishStatus.DRAFT)
        self.assertEqual(company.name, "www.geokeji.com")
        self.assertIsNone(company.category)
        self.assertIsNone(company.geo_score)

    def test_admin_approve_requires_pipeline_profile_instead_of_unmetered_hydration(self):
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

        self.assertEqual(approve_response.status_code, 409, approve_response.text)
        self.assertIn("missing_fields", approve_response.json()["detail"])

        async def _fetch_company():
            async with async_session() as db:
                result = await db.execute(select(Company).where(Company.id == uuid.UUID(company_id)))
                return result.scalar_one()

        company = self.run_async(_fetch_company())
        self.assertEqual(company.publish_status, PublishStatus.PENDING_REVIEW)
        self.assertEqual(company.name, "www.geokeji.com")
        self.assertIsNone(company.category)
        self.assertIsNone(company.geo_score)

    def test_admin_approve_incomplete_company_reports_missing_fields(self):
        admin = self.run_async(self._register_user(admin=True))

        async def _create_company():
            async with async_session() as db:
                company = Company(
                    name="Incomplete Company",
                    url=f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.incomplete.test",
                    pipeline_status=PipelineStatus.COMPLETED,
                    publish_status=PublishStatus.PENDING_REVIEW,
                )
                db.add(company)
                await db.commit()
                await db.refresh(company)
                return str(company.id)

        company_id = self.run_async(_create_company())
        approve_response = self.run_async(
            self.client.post(
                f"/api/admin/companies/{company_id}/approve",
                headers=self._auth_headers(admin["token"]),
            )
        )

        self.assertEqual(approve_response.status_code, 409, approve_response.text)
        detail = approve_response.json()["detail"]
        self.assertEqual(detail["message"], "公司资料未抽取完整，暂不能发布")
        self.assertEqual(
            set(detail["missing_fields"]),
            {"description", "category", "tags", "geo_score", "geo_details"},
        )

    def test_admin_cannot_publish_complete_profile_from_failed_pipeline(self):
        admin = self.run_async(self._register_user(admin=True))

        async def _create_company():
            async with async_session() as db:
                company = Company(
                    name="Failed Vector Company",
                    url=f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.failed-vector.test",
                    description="本轮官网资料已成功抽取。",
                    short_description="官网资料完整。",
                    category="教育培训",
                    tags=["教育培训"],
                    geo_score=37,
                    geo_details={"schema": 0, "content": 30, "meta": 38, "citation": 100},
                    pipeline_status=PipelineStatus.FAILED,
                    pipeline_error="Embedding API Key 未配置",
                    publish_status=PublishStatus.PENDING_REVIEW,
                )
                db.add(company)
                await db.commit()
                await db.refresh(company)
                return str(company.id)

        company_id = self.run_async(_create_company())
        approve_response = self.run_async(
            self.client.post(
                f"/api/admin/companies/{company_id}/approve",
                headers=self._auth_headers(admin["token"]),
            )
        )

        self.assertEqual(approve_response.status_code, 409, approve_response.text)
        detail = approve_response.json()["detail"]
        self.assertEqual(detail["message"], "公司分析流程尚未完成，暂不能发布")
        self.assertEqual(detail["pipeline_status"], "failed")
        self.assertEqual(detail["pipeline_error"], "Embedding API Key 未配置")

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
                    "geo_score": 66,
                },
            )
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        created = create_response.json()
        company_id = created["id"]
        self.assertEqual(created["name"], f"Codex Admin Company {suffix}")
        self.assertEqual(created["tags"], ["admin", "crud"])
        self.assertIn("preview=", created["preview_url"])

        hidden_preview = self.run_async(
            self.client.get(created["preview_url"].split("?", 1)[0])
        )
        self.assertEqual(hidden_preview.status_code, 404, hidden_preview.text)
        signed_preview = self.run_async(self.client.get(created["preview_url"]))
        self.assertEqual(signed_preview.status_code, 200, signed_preview.text)
        self.assertIn('name="robots" content="noindex,nofollow"', signed_preview.text)

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
                    "geo_score": 72.5,
                },
            )
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)
        updated = update_response.json()
        self.assertEqual(updated["name"], f"Codex Admin Company Updated {suffix}")
        self.assertEqual(updated["publish_status"], "draft")
        self.assertEqual(updated["category"], "GEO platform")
        self.assertEqual(updated["tech_stack"], ["FastAPI"])

        status_bypass = self.run_async(
            self.client.put(
                f"/api/admin/companies/{company_id}",
                headers=self._auth_headers(admin["token"]),
                json={"publish_status": "published"},
            )
        )
        self.assertEqual(status_bypass.status_code, 409, status_bypass.text)

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
                            "status": "captured",
                            "key": "companies/test/homepage.html",
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
        self.assertEqual(api_response.json()["view_count"], 0)

        async def _view_count():
            async with async_session() as db:
                company = await db.get(Company, uuid.UUID(holder["company_id"]))
                return getattr(company, "view_count", None)

        legacy_response = self.run_async(self.client.get(f"/companies/{holder['company_id']}", follow_redirects=False))
        self.assertEqual(legacy_response.status_code, 301, legacy_response.text)
        expected_origin = "http://testserver" if settings.DEBUG else settings.PUBLIC_BASE_URL.rstrip("/")
        self.assertEqual(legacy_response.headers["location"], f"{expected_origin}/c/{holder['path_key']}")
        self.assertEqual(self.run_async(_view_count()), 0)

        detail_response = self.run_async(self.client.get(f"/c/{holder['path_key']}"))
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        self.assertEqual(self.run_async(_view_count()), 1)
        self.assertIn("SSR Company", detail_response.text)
        self.assertIn("服务端直出的 GEO 公司档案。", detail_response.text)
        self.assertIn('id="company-profile"', detail_response.text)
        self.assertIn("公司介绍", detail_response.text)
        self.assertIn("业务与能力", detail_response.text)
        self.assertIn("公开资料与可信信号", detail_response.text)
        self.assertIn("GEO 分析", detail_response.text)
        self.assertNotIn("GEO 行动计划", detail_response.text)
        self.assertNotIn("页面可读性摘要", detail_response.text)
        self.assertIn("Ada", detail_response.text)
        self.assertIn("application/ld+json", detail_response.text)
        self.assertIn('"@type": "Organization"', detail_response.text)
        self.assertIn(f'rel="canonical" href="{expected_origin}/c/{holder["path_key"]}"', detail_response.text)

        second_detail_response = self.run_async(self.client.get(f"/c/{holder['path_key']}"))
        self.assertEqual(second_detail_response.status_code, 200, second_detail_response.text)
        self.assertEqual(self.run_async(_view_count()), 2)

        with patch(
            "app.web.company_pages.rank_similar_companies",
            side_effect=RuntimeError("forced render failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.run_async(self.client.get(f"/c/{holder['path_key']}"))
        self.assertEqual(self.run_async(_view_count()), 2)

        with patch(
            "app.web.company_pages.update",
            side_effect=SQLAlchemyError("forced PV storage failure"),
        ):
            resilient_response = self.run_async(self.client.get(f"/c/{holder['path_key']}"))
        self.assertEqual(resilient_response.status_code, 200, resilient_response.text)
        self.assertEqual(self.run_async(_view_count()), 2)

    def test_company_list_can_sort_by_real_page_views(self):
        suffix = uuid.uuid4().hex[:10]
        name_prefix = f"PV Sort {suffix}"

        async def _create_companies():
            async with async_session() as db:
                db.add_all(
                    [
                        Company(
                            name=f"{name_prefix} Lower",
                            url=f"{TEST_COMPANY_URL_PREFIX}{suffix}-lower.example.test",
                            pipeline_status=PipelineStatus.COMPLETED,
                            publish_status=PublishStatus.PUBLISHED,
                            view_count=3,
                        ),
                        Company(
                            name=f"{name_prefix} Higher",
                            url=f"{TEST_COMPANY_URL_PREFIX}{suffix}-higher.example.test",
                            pipeline_status=PipelineStatus.COMPLETED,
                            publish_status=PublishStatus.PUBLISHED,
                            view_count=9,
                        ),
                    ]
                )
                await db.commit()

        self.run_async(_create_companies())
        response = self.run_async(
            self.client.get(
                "/api/companies/",
                params={"sort": "views", "q": name_prefix},
            )
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [item["name"] for item in response.json()["items"]],
            [f"{name_prefix} Higher", f"{name_prefix} Lower"],
        )
        self.assertEqual([item["view_count"] for item in response.json()["items"]], [9, 3])

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

    def test_anonymous_diagnostics_require_login_for_platform_quota(self):
        diagnostic_url = f"{TEST_COMPANY_URL_PREFIX}{uuid.uuid4().hex[:10]}.public.test/diagnostic"

        with patch("app.core.celery_app.celery_app.send_task") as send_task:
            create_response = self.run_async(
                self.client.post(
                    "/api/diagnostics/",
                    json={"url": diagnostic_url},
                )
            )

        self.assertEqual(create_response.status_code, 401, create_response.text)
        send_task.assert_not_called()

        async def _report_exists():
            async with async_session() as db:
                report_id = await db.scalar(
                    select(DiagnosticReport.id).where(DiagnosticReport.url == diagnostic_url)
                )
                return report_id is not None

        self.assertFalse(self.run_async(_report_exists()))

    def test_anonymous_solutions_chat_requires_login_for_platform_quota(self):
        with patch(
            "app.api.routes.solutions._run_rag",
            new=AsyncMock(return_value=("不应执行", [])),
        ) as run_rag:
            chat_response = self.run_async(
                self.client.post(
                    "/api/solutions/chat",
                    json={"message": "请基于这份诊断给我一套 GEO 优化方案"},
                )
            )

        self.assertEqual(chat_response.status_code, 401, chat_response.text)
        run_rag.assert_not_awaited()

    def test_authenticated_user_can_claim_public_solution_conversation(self):
        async def _create_legacy_public_conversation():
            async with async_session() as db:
                conversation = Conversation(user_id=None, title="历史公开方案")
                db.add(conversation)
                await db.flush()
                db.add_all(
                    [
                        Message(
                            conversation_id=conversation.id,
                            role=MessageRole.USER,
                            content="历史匿名问题",
                        ),
                        Message(
                            conversation_id=conversation.id,
                            role=MessageRole.ASSISTANT,
                            content="历史公开方案内容",
                            recommended_companies=[],
                        ),
                    ]
                )
                await db.commit()
                return str(conversation.id)

        conversation_id = self.run_async(_create_legacy_public_conversation())
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

    def test_admin_user_update_rejects_fields_owned_by_different_users(self):
        admin = self.run_async(self._register_user(admin=True))
        email_owner = self.run_async(self._register_user())
        username_owner = self.run_async(self._register_user())
        target = self.run_async(self._register_user())
        target_me = self.run_async(
            self.client.get("/api/auth/me", headers=self._auth_headers(target["token"]))
        )
        self.assertEqual(target_me.status_code, 200, target_me.text)

        response = self.run_async(
            self.client.put(
                f"/api/admin/users/{target_me.json()['id']}",
                headers=self._auth_headers(admin["token"]),
                json={
                    "email": email_owner["email"],
                    "username": username_owner["username"],
                },
            )
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("用户名、邮箱或手机号已存在", response.text)

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
                json={"password": "CodexSelfReset@2026"},
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

    def test_admin_can_edit_reset_password_and_delete_user(self):
        admin = self.run_async(self._register_user(admin=True))
        suffix = uuid.uuid4().hex[:8]
        username = f"{TEST_USERNAME_PREFIX}crud_{suffix}"
        email = f"{TEST_EMAIL_PREFIX}crud_{suffix}@example.com"
        phone = f"{TEST_PHONE_PREFIX}{str(uuid.uuid4().int)[-4:]}"
        updated_username = f"{TEST_USERNAME_PREFIX}crud_updated_{suffix}"
        updated_email = f"{TEST_EMAIL_PREFIX}crud_updated_{suffix}@example.com"
        updated_phone = f"{TEST_PHONE_PREFIX}{str(uuid.uuid4().int)[-4:]}"
        reset_password = "CodexReset@2026"

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

        reset_response = self.run_async(
            self.client.put(
                f"/api/admin/users/{user_id}/password",
                headers=self._auth_headers(admin["token"]),
                json={"password": reset_password},
            )
        )
        self.assertEqual(reset_response.status_code, 200, reset_response.text)

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
        self.assertIn("GEO Wiki 知识库", home_response.text)
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
