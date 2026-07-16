from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from starlette.requests import Request

from app.web.company_pages import (
    _company_story_markup,
    _absolute_url,
    _geo_overview_markup,
    _geo_priority,
    _public_sources_section_markup,
    _render_json_ld,
    _semantic_map_markup,
    _source_evidence_markup,
    _team_profile_section_markup,
)


class CompanyPageHelperTests(TestCase):
    def test_absolute_url_ignores_untrusted_host_header(self):
        request = Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "https",
                "path": "/companies/demo",
                "raw_path": b"/companies/demo",
                "query_string": b"",
                "headers": [(b"host", b"evil.example")],
                "client": ("127.0.0.1", 1234),
                "server": ("evil.example", 443),
            }
        )

        with (
            patch("app.web.company_pages.settings.DEBUG", False),
            patch("app.web.company_pages.settings.PUBLIC_BASE_URL", "https://public.example"),
        ):
            absolute_url = _absolute_url(request, "/c/demo")

        self.assertEqual(absolute_url, "https://public.example/c/demo")
        self.assertNotIn("evil.example", absolute_url)

    def test_json_ld_cannot_close_its_script_element(self):
        markup = _render_json_ld(
            {
                "@type": "Organization",
                "name": '</script><img src=x onerror="alert(1)">',
            }
        )

        self.assertEqual(markup.count("</script>"), 1)
        self.assertNotIn("<img", markup)
        self.assertIn("\\u003c/script\\u003e", markup)

    def test_empty_geo_details_do_not_create_dimension_claims(self):
        company = SimpleNamespace(geo_details={}, geo_score=None)

        strongest, weakest = _geo_priority(company)
        markup = _geo_overview_markup(company)

        self.assertIsNone(strongest)
        self.assertIsNone(weakest)
        self.assertNotIn("建议优先关注", markup)
        self.assertNotIn("结构化</dd>", markup)
        self.assertIn("待评估", markup)

    def test_sparse_team_and_source_records_are_hidden(self):
        team_company = SimpleNamespace(team_members=[{"bg": "公开履历"}])
        source_company = SimpleNamespace(crawl_pages=[{"reason": "公司介绍来源"}])

        self.assertEqual(_team_profile_section_markup(team_company), "")
        self.assertEqual(_public_sources_section_markup(source_company), "")

    def test_source_placeholders_fall_back_when_url_is_valid(self):
        company = SimpleNamespace(
            crawl_pages=[
                {
                    "role": "unknown",
                    "title": "未知",
                    "reason": "待补充",
                    "url": "https://example.com/about",
                    "status": "captured",
                    "key": "companies/example/about.html",
                }
            ]
        )

        markup = _source_evidence_markup(company)

        self.assertNotIn("unknown", markup)
        self.assertNotIn("未知", markup)
        self.assertNotIn("待补充", markup)
        self.assertIn("页面 1", markup)
        self.assertIn("https://example.com/about", markup)

    def test_failed_or_unpersisted_pages_are_not_presented_as_public_sources(self):
        company = SimpleNamespace(
            crawl_pages=[
                {
                    "title": "抓取失败页",
                    "url": "https://example.com/failed",
                    "status": "failed",
                    "key": None,
                },
                {
                    "title": "未持久化页",
                    "url": "https://example.com/missing",
                    "status": "captured",
                    "key": None,
                },
            ]
        )

        self.assertEqual(_source_evidence_markup(company), "")
        self.assertEqual(_public_sources_section_markup(company), "")

    def test_story_hides_placeholder_description_and_profile_facts(self):
        company = SimpleNamespace(
            description="待补充",
            category="unknown",
            headquarters="未知",
            founded_date=None,
            employee_count="n/a",
            funding_stage="--",
        )

        markup = _company_story_markup(company, "Demo Company", "公开简介暂未补充")

        self.assertNotIn("unknown", markup)
        self.assertNotIn("未知", markup)
        self.assertNotIn(">n/a<", markup)
        self.assertNotIn(">待补充<", markup)
        self.assertIn("公司公开档案仍在完善", markup)

    def test_semantic_map_prefers_entities_loaded_from_company_graph(self):
        company = SimpleNamespace(category=None, headquarters=None, funding_stage=None)

        markup = _semantic_map_markup(
            company,
            "Demo Company",
            [],
            [],
            graph_nodes=["Graph Product", "Founder", "Knowledge Graph", "AI Platform"],
        )

        self.assertIn("Graph Product", markup)
        self.assertIn("Founder", markup)
