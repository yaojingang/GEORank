import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.company_retrieval import (
    fallback_company_recommendations,
    fallback_similar_companies,
    rank_similar_companies,
)


def _company(
    name: str,
    *,
    category: str,
    tags: list[str],
    tech_stack: list[str] | None = None,
    geo_score: float = 80,
    upvotes: int = 0,
    is_geo_certified: bool = False,
    short_description: str = "",
    description: str = "",
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        category=category,
        tags=tags,
        tech_stack=tech_stack or [],
        geo_score=geo_score,
        upvotes=upvotes,
        is_geo_certified=is_geo_certified,
        short_description=short_description,
        description=description,
        tech_level=None,
        funding_stage=None,
    )


class CompanyRetrievalTests(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_company_recommendations_prefers_keyword_matches(self):
        brightedge = _company(
            "BrightEdge",
            category="GEO工具",
            tags=["GEO监控", "SEO平台", "内容优化"],
            geo_score=88,
            upvotes=200,
            description="企业级 GEO 监控平台",
        )
        narrato = _company(
            "Narrato",
            category="AI写作",
            tags=["AI写作", "内容工作流"],
            geo_score=66,
            upvotes=60,
            description="AI 写作与内容协作平台",
        )
        generic = _company(
            "Goodie",
            category="GEO咨询",
            tags=["品牌AI可见度"],
            geo_score=72,
            upvotes=40,
            description="GEO 咨询服务",
        )

        with patch(
            "app.services.company_retrieval._get_published_companies",
            return_value=[generic, narrato, brightedge],
        ):
            results = await fallback_company_recommendations(
                None,
                "我想找 GEO监控 和 AI写作 相关平台",
                limit=3,
            )

        top_two = [company.name for company in results[:2]]
        self.assertIn("BrightEdge", top_two)
        self.assertIn("Narrato", top_two)

    async def test_fallback_similar_companies_prefers_shared_category_and_tags(self):
        target = _company(
            "Aily Labs",
            category="企业AI",
            tags=["知识图谱", "企业AI", "语义数据"],
            tech_stack=["Neo4j", "Qdrant"],
            geo_score=86,
            upvotes=150,
            is_geo_certified=True,
        )
        close_match = _company(
            "GraphPulse",
            category="企业AI",
            tags=["知识图谱", "企业AI"],
            tech_stack=["Neo4j", "Postgres"],
            geo_score=84,
            upvotes=120,
            is_geo_certified=True,
        )
        weak_match = _company(
            "WriterFlow",
            category="AI写作",
            tags=["AI写作"],
            tech_stack=["Notion"],
            geo_score=88,
            upvotes=180,
        )

        with patch(
            "app.services.company_retrieval._get_published_companies",
            return_value=[target, weak_match, close_match],
        ):
            results = await fallback_similar_companies(None, target, limit=2)

        self.assertEqual(results[0].name, "GraphPulse")

    async def test_rank_similar_companies_uses_vector_results_before_fallback(self):
        target = _company("Target", category="教育培训", tags=["教育"])
        vector_match = _company("Vector Match", category="企业服务", tags=["软件"])

        with patch(
            "app.services.vector_store.vector_store.get_similar_company_ids",
            new=AsyncMock(return_value=[str(target.id), str(vector_match.id)]),
        ), patch(
            "app.services.company_retrieval._get_published_companies_by_ids",
            new=AsyncMock(return_value=[vector_match]),
        ), patch(
            "app.services.company_retrieval.fallback_similar_companies",
            new=AsyncMock(return_value=[]),
        ):
            results = await rank_similar_companies(None, target, limit=3)

        self.assertEqual([company.name for company in results], ["Vector Match"])
