import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ai_usage import (  # noqa: E402
    build_quota_error_detail,
    calculate_reservation_tokens,
    evaluate_platform_quota,
    normalize_policy_payload,
)
from app.services.runtime_settings import _build_ai_usage_policy_config  # noqa: E402


class AiQuotaPolicyRulesTests(unittest.TestCase):
    def test_default_policy_uses_lifetime_grant_and_global_daily_budget(self):
        policy = _build_ai_usage_policy_config({})

        self.assertEqual(policy["access_mode"], "lifetime_quota_with_byok")
        self.assertEqual(policy["lifetime_token_grant"], 10_000)
        self.assertEqual(policy["global_daily_token_limit"], 1_000_000)
        self.assertTrue(policy["global_budget_enabled"])
        self.assertFalse(policy["allow_anonymous_ai_usage"])
        self.assertEqual(policy["byok_guidance"]["provider"], "deepseek")
        self.assertEqual(policy["byok_guidance"]["base_url"], "https://api.deepseek.com")
        self.assertEqual(policy["byok_guidance"]["model"], "deepseek-v4-flash")

    def test_policy_normalization_clamps_numbers_and_sanitizes_guidance(self):
        policy = _build_ai_usage_policy_config(
            {
                "api_usage_policy": {
                    "lifetime_token_grant": -3,
                    "global_daily_token_limit": -5,
                    "byok_guidance": {
                        "provider": "deepseek",
                        "title": "额度已用完",
                        "message": "请绑定自己的 API Key",
                        "cta_label": "前往 DeepSeek",
                        "official_url": "javascript:alert(1)",
                        "base_url": "ftp://api.example.com",
                        "model": "deepseek-v4-flash",
                    },
                }
            }
        )

        self.assertEqual(policy["lifetime_token_grant"], 0)
        self.assertEqual(policy["global_daily_token_limit"], 0)
        self.assertEqual(policy["byok_guidance"]["official_url"], "https://platform.deepseek.com/api_keys")
        self.assertEqual(policy["byok_guidance"]["base_url"], "https://api.deepseek.com")

        oversized = _build_ai_usage_policy_config(
            {
                "api_usage_policy": {
                    "daily_token_limit": 9_000_000_000,
                    "lifetime_token_grant": 9_000_000_000,
                    "global_daily_token_limit": 9_000_000_000,
                }
            }
        )
        self.assertEqual(oversized["daily_token_limit"], 2_147_483_647)
        self.assertEqual(oversized["lifetime_token_grant"], 2_147_483_647)
        self.assertEqual(oversized["global_daily_token_limit"], 2_147_483_647)

    def test_reservation_estimate_has_module_floor(self):
        self.assertEqual(calculate_reservation_tokens("solutions", 10), 6_500)
        self.assertEqual(calculate_reservation_tokens("diagnostics", 10), 10_000)
        self.assertEqual(calculate_reservation_tokens("companies", 10), 10_000)
        self.assertEqual(calculate_reservation_tokens("solutions", 2_000), 6_500)

    def test_legacy_daily_modes_upgrade_to_lifetime_quota(self):
        for legacy_mode in ("daily_quota", "quota_with_byok"):
            policy = _build_ai_usage_policy_config(
                {"api_usage_policy": {"access_mode": legacy_mode}}
            )
            self.assertEqual(policy["access_mode"], "lifetime_quota_with_byok")

    def test_default_byok_providers_all_have_admin_allowed_origins(self):
        policy = _build_ai_usage_policy_config({})
        self.assertNotIn("custom", {item["key"] for item in policy["allowed_byok_providers"]})
        self.assertTrue(all(item["base_url"] for item in policy["allowed_byok_providers"]))

    def test_partial_guidance_update_preserves_existing_fields(self):
        current = _build_ai_usage_policy_config({})
        merged = normalize_policy_payload(
            {"byok_guidance": {"title": "自定义标题"}},
            current,
        )
        self.assertEqual(merged["byok_guidance"]["title"], "自定义标题")
        self.assertEqual(
            merged["byok_guidance"]["official_url"],
            current["byok_guidance"]["official_url"],
        )

    def test_personal_quota_is_checked_before_platform_call(self):
        reason = evaluate_platform_quota(
            policy={"global_budget_enabled": True, "emergency_byok_only": False},
            requested_tokens=1_200,
            personal_remaining=900,
            global_remaining=50_000,
            personal_quota_required=True,
        )

        self.assertEqual(reason, "personal_quota_exhausted")

    def test_global_budget_and_emergency_switch_apply_to_every_platform_call(self):
        global_reason = evaluate_platform_quota(
            policy={"global_budget_enabled": True, "emergency_byok_only": False},
            requested_tokens=2_500,
            personal_remaining=None,
            global_remaining=2_000,
            personal_quota_required=False,
        )
        emergency_reason = evaluate_platform_quota(
            policy={"global_budget_enabled": False, "emergency_byok_only": True},
            requested_tokens=1,
            personal_remaining=None,
            global_remaining=None,
            personal_quota_required=False,
        )

        self.assertEqual(global_reason, "global_daily_budget_exhausted")
        self.assertEqual(emergency_reason, "emergency_byok_only")

    def test_quota_error_contains_stable_code_and_admin_guidance(self):
        detail = build_quota_error_detail(
            reason_code="personal_quota_exhausted",
            policy={
                "byok_guidance": {
                    "title": "继续使用 AI",
                    "message": "请绑定 API Key",
                    "cta_label": "立即配置",
                    "official_url": "https://platform.deepseek.com/api_keys",
                    "provider": "deepseek",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-flash",
                }
            },
            requested_tokens=1200,
            personal_remaining=0,
            global_remaining=800000,
        )

        self.assertEqual(detail["code"], "personal_quota_exhausted")
        self.assertEqual(detail["guidance"]["cta_label"], "立即配置")
        self.assertEqual(detail["quota"]["requested_tokens"], 1200)

    def test_quota_error_does_not_prompt_for_byok_when_admin_disables_it(self):
        detail = build_quota_error_detail(
            reason_code="global_daily_budget_exhausted",
            policy={"allow_user_byok": False, "byok_guidance": {}},
            requested_tokens=1200,
            personal_remaining=8000,
            global_remaining=0,
        )

        self.assertFalse(detail["allow_user_byok"])
        self.assertNotIn("绑定", detail["message"])
        self.assertIn("稍后再试", detail["message"])


if __name__ == "__main__":
    unittest.main()
