import json
import unittest
from unittest.mock import patch

import httpx

from app.core.config import settings
from app.services import ai_overview
from app.services.ai_overview import (
    AIOverviewNotConfiguredError,
    AIOverviewRequestError,
    brand_visibility,
    extract_citations,
    fetch_ai_overview,
    normalize_source_url,
    summarize,
)

OVERVIEW_CONTENT = {
    "results": [
        {
            "type": "ai_summary",
            "title": "AI Overview",
            "text": "Solar panels convert sunlight into electricity via the photovoltaic effect.",
            "links": [
                {"title": "How Do Solar Panels Work? | EnergySage", "url": "https://www.energysage.com/solar/"},
                {"title": "Explain like I'm five - Reddit", "url": "https://www.reddit.com/r/explainlikeimfive/comments/abc/"},
            ],
        }
    ],
    "serp_features": [
        {
            "type": "ai_summary",
            "links": [
                # 与 results 中的条目重复，只是多了追踪参数，应当被去重。
                {"title": "How Do Solar Panels Work? | EnergySage", "url": "https://energysage.com/solar?utm_source=google&utm_medium=serp"},
                {"title": "Solar panels - National Grid", "url": "https://www.nationalgrid.com/energy-solutions/solar"},
            ],
        }
    ],
    "search_parameters": {
        "query": "how do solar panels work",
        "country": "us",
        "language": "en",
        "device": "desktop",
        "feature_available": True,
    },
}

EMPTY_CONTENT = {
    "results": [],
    "serp_features": [],
    "search_parameters": {
        "query": "site:example.com inurl:no-result",
        "country": "us",
        "language": "en",
        "device": "desktop",
        "feature_available": False,
    },
}


def _payload(content):
    return {
        "code": "ok",
        "message": "Saved example response",
        "data": {
            "endpoint": "google-ai-overview",
            "query": content.get("search_parameters", {}).get("query", ""),
            "costCredits": 3,
            "remainingCredits": 1234,
            "result": {"format": "json", "content": content},
        },
    }


class SummarizeTest(unittest.TestCase):
    def test_extracts_answer_citations_and_billing(self):
        summary = summarize(_payload(OVERVIEW_CONTENT))

        self.assertTrue(summary["available"])
        self.assertIn("photovoltaic", summary["answer"])
        self.assertEqual(summary["country"], "us")
        self.assertEqual(summary["cost_credits"], 3)
        self.assertEqual(summary["remaining_credits"], 1234)
        # 3 条唯一来源：EnergySage 重复项被去重。
        self.assertEqual(len(summary["citations"]), 3)
        self.assertEqual([item["rank"] for item in summary["citations"]], [1, 2, 3])

    def test_missing_overview_is_still_a_successful_response(self):
        summary = summarize(_payload(EMPTY_CONTENT), query="site:example.com inurl:no-result")

        self.assertFalse(summary["available"])
        self.assertEqual(summary["answer"], "")
        self.assertEqual(summary["citations"], [])
        self.assertEqual(summary["query"], "site:example.com inurl:no-result")

    def test_falls_back_to_results_when_feature_flag_absent(self):
        content = {key: value for key, value in OVERVIEW_CONTENT.items() if key != "search_parameters"}
        summary = summarize({"data": {"result": {"content": content}}})

        self.assertTrue(summary["available"])

    def test_tolerates_empty_payload(self):
        summary = summarize(None)

        self.assertFalse(summary["available"])
        self.assertEqual(summary["citations"], [])


class CitationTest(unittest.TestCase):
    def test_normalize_drops_tracking_params_and_trailing_slash(self):
        left = normalize_source_url("https://WWW.Example.com/a/?utm_source=x&b=2#frag")
        right = normalize_source_url("https://www.example.com/a?b=2")

        self.assertEqual(left, right)
        self.assertEqual(normalize_source_url("https://example.com"), "https://example.com/")

    def test_citations_without_url_are_skipped(self):
        content = {"results": [{"links": [{"title": "no url"}, {"url": "   "}]}]}

        self.assertEqual(extract_citations(content), [])

    def test_citations_ignore_malformed_shapes(self):
        content = {"results": "not-a-list", "serp_features": [{"links": ["bad"]}]}

        self.assertEqual(extract_citations(content), [])


class BrandVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.citations = summarize(_payload(OVERVIEW_CONTENT))["citations"]

    def test_domain_match_reports_position_and_share(self):
        result = brand_visibility(self.citations, "EnergySage", domains=["energysage.com"])

        self.assertTrue(result["cited"])
        self.assertEqual(result["matched_by"], "domain")
        self.assertEqual(result["position"], 1)
        self.assertAlmostEqual(result["share"], 1 / 3, places=4)

    def test_subdomain_matches_registered_domain(self):
        result = brand_visibility(self.citations, "", domains=["reddit.com"])

        self.assertTrue(result["cited"])
        self.assertEqual(result["position"], 2)

    def test_title_match_when_domain_unknown(self):
        result = brand_visibility(self.citations, "National Grid")

        self.assertTrue(result["cited"])
        self.assertEqual(result["matched_by"], "title")
        self.assertEqual(result["position"], 3)

    def test_absent_brand_reports_no_citation(self):
        result = brand_visibility(self.citations, "GoAnyAPI", domains=["goanyapi.com"])

        self.assertFalse(result["cited"])
        self.assertIsNone(result["position"])
        self.assertEqual(result["citation_count"], 3)
        self.assertEqual(result["share"], 0.0)

    def test_empty_citations_do_not_divide_by_zero(self):
        result = brand_visibility([], "Anything", domains=["anything.com"])

        self.assertFalse(result["cited"])
        self.assertEqual(result["share"], 0.0)


class FetchAIOverviewTest(unittest.IsolatedAsyncioTestCase):
    async def test_raises_when_key_missing(self):
        with patch.object(settings, "GOANYAPI_API_KEY", ""):
            with self.assertRaises(AIOverviewNotConfiguredError):
                await fetch_ai_overview("how do solar panels work")

    async def test_sends_query_and_bearer_token(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_payload(OVERVIEW_CONTENT))

        with patch.object(settings, "GOANYAPI_API_KEY", "test-key"):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                summary = await fetch_ai_overview(
                    "how do solar panels work",
                    country="US",
                    language="en",
                    device="Desktop",
                    client=client,
                )

        self.assertTrue(summary["available"])
        self.assertEqual(captured["url"], "https://api.goanyapi.com/api/v1/google-ai-overview")
        self.assertEqual(captured["auth"], "Bearer test-key")
        self.assertEqual(
            captured["body"],
            {
                "query": "how do solar panels work",
                "output": "json",
                "country": "us",
                "language": "en",
                "device": "desktop",
            },
        )

    async def test_insufficient_credits_is_not_retryable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(402, json={"code": "insufficient_credits"})

        with patch.object(settings, "GOANYAPI_API_KEY", "test-key"):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(AIOverviewRequestError) as ctx:
                    await fetch_ai_overview("q", client=client)

        self.assertEqual(ctx.exception.status_code, 402)
        self.assertFalse(ctx.exception.retryable)
        self.assertIn("余额不足", str(ctx.exception))

    async def test_rate_limit_and_timeout_are_retryable(self):
        for status in (429, 504):
            def handler(request: httpx.Request, status=status) -> httpx.Response:
                return httpx.Response(status, json={"code": "error"})

            with patch.object(settings, "GOANYAPI_API_KEY", "test-key"):
                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                    with self.assertRaises(AIOverviewRequestError) as ctx:
                        await fetch_ai_overview("q", client=client)

            self.assertEqual(ctx.exception.status_code, status)
            self.assertTrue(ctx.exception.retryable)

    async def test_network_error_is_retryable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        with patch.object(settings, "GOANYAPI_API_KEY", "test-key"):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(AIOverviewRequestError) as ctx:
                    await fetch_ai_overview("q", client=client)

        self.assertTrue(ctx.exception.retryable)

    async def test_non_json_body_is_reported(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>gateway</html>")

        with patch.object(settings, "GOANYAPI_API_KEY", "test-key"):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(AIOverviewRequestError):
                    await fetch_ai_overview("q", client=client)

    async def test_business_error_code_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"code": "invalid_params", "data": {}})

        with patch.object(settings, "GOANYAPI_API_KEY", "test-key"):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(AIOverviewRequestError) as ctx:
                    await fetch_ai_overview("q", client=client)

        self.assertFalse(ctx.exception.retryable)

    async def test_blank_query_rejected_before_network(self):
        with patch.object(settings, "GOANYAPI_API_KEY", "test-key"):
            with self.assertRaises(ValueError):
                await fetch_ai_overview("   ")


if __name__ == "__main__":
    unittest.main()
