import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.company_profile import (
    build_company_profile_values,
    company_profile_needs_hydration,
    load_company_source_text,
    normalize_company_name,
)


class CompanyProfileTests(unittest.TestCase):
    def test_normalize_company_name_removes_marketing_suffixes(self):
        self.assertEqual(
            normalize_company_name("移山科技官网 | GEO优化服务 | AI搜索引擎优化"),
            "移山科技",
        )

    def test_normalize_company_name_preserves_clean_brand_name(self):
        self.assertEqual(
            normalize_company_name("BrightEdge"),
            "BrightEdge",
        )

    def test_normalize_company_name_falls_back_when_primary_empty(self):
        self.assertEqual(
            normalize_company_name("", fallback_name="Narrato"),
            "Narrato",
        )

    def test_publishable_profile_does_not_require_a_detected_tech_stack(self):
        company = SimpleNamespace(
            description="一家公开资料完整的教育企业。",
            short_description="教育企业。",
            category="教育培训",
            tags=["教育"],
            tech_stack=[],
            geo_score=82,
            geo_details={"schema": 80, "content": 85, "meta": 82, "citation": 81},
        )

        self.assertFalse(company_profile_needs_hydration(company))

    def test_pipeline_refresh_clears_stale_fields_missing_from_current_extraction(self):
        company = SimpleNamespace(
            name="旧公司名",
            description="旧介绍",
            short_description="旧简介",
            category="企业AI",
            headquarters="旧总部",
            funding_stage="A轮",
            employee_count="200-500人",
            founded_date="2001-01-01",
            tags=["旧标签"],
            tech_stack=["旧技术"],
            team_members=[{"name": "旧成员"}],
        )

        values = build_company_profile_values(
            company,
            {
                "name": "新公司名",
                "description": "本轮官网介绍",
                "short_description": "本轮简介",
                "category": None,
                "headquarters": None,
                "funding_stage": None,
                "employee_count": None,
                "founded_date": None,
                "tags": [],
                "tech_stack": [],
                "team_members": [],
            },
            replace=True,
        )

        self.assertEqual(values["name"], "新公司名")
        self.assertEqual(values["description"], "本轮官网介绍")
        self.assertIsNone(values["category"])
        self.assertIsNone(values["headquarters"])
        self.assertIsNone(values["funding_stage"])
        self.assertIsNone(values["employee_count"])
        self.assertIsNone(values["founded_date"])
        self.assertEqual(values["tags"], [])
        self.assertEqual(values["tech_stack"], [])
        self.assertEqual(values["team_members"], [])

    @patch("app.services.company_profile.storage.get")
    def test_source_text_keeps_each_captured_page_and_removes_page_chrome(self, storage_get):
        pages = {
            "companies/demo/homepage.html": b"<html><head><title>Demo</title><script>secret()</script></head><body><nav>menu</nav><main>HOME_TEXT</main></body></html>",
            "companies/demo/product.html": b"<html><body><main>SECONDARY_PRODUCT_TEXT</main><footer>footer</footer></body></html>",
        }
        storage_get.side_effect = pages.get
        company = SimpleNamespace(
            crawl_pages=[
                {
                    "role": "homepage",
                    "title": "首页",
                    "url": "https://example.com",
                    "status": "captured",
                    "key": "companies/demo/homepage.html",
                },
                {
                    "role": "product",
                    "title": "产品",
                    "url": "https://example.com/product",
                    "status": "captured",
                    "key": "companies/demo/product.html",
                },
                {
                    "role": "about",
                    "status": "failed",
                    "key": "companies/demo/missing.html",
                },
            ],
            raw_html_key=None,
            about_html_key=None,
        )

        source = load_company_source_text(company)

        self.assertIn("HOME_TEXT", source)
        self.assertIn("SECONDARY_PRODUCT_TEXT", source)
        self.assertIn("[页面 product | 产品 | https://example.com/product]", source)
        self.assertNotIn("secret()", source)
        self.assertNotIn("menu", source)
        self.assertNotIn("footer", source)
        storage_get.assert_any_call("companies/demo/homepage.html")
        storage_get.assert_any_call("companies/demo/product.html")
        self.assertEqual(storage_get.call_count, 2)
