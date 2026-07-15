import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tasks.diagnose import (  # noqa: E402
    _calculate_overall_score,
    _check_citations,
    _check_content,
    _check_meta,
)


class DiagnoseRuleTests(unittest.TestCase):
    def test_calculate_overall_score_uses_runtime_weights(self):
        score = _calculate_overall_score(
            schema_score=90,
            content_score=60,
            meta_score=80,
            citation_score=50,
            weights={"schema": 0.5, "content": 0.2, "meta": 0.2, "citation": 0.1},
        )

        self.assertEqual(score, 78)

    def test_calculate_overall_score_falls_back_to_default_weights(self):
        score = _calculate_overall_score(
            schema_score=100,
            content_score=50,
            meta_score=50,
            citation_score=50,
            weights={"schema": 0, "content": 0, "meta": 0, "citation": 0},
        )

        self.assertEqual(score, 65)

    def test_check_meta_detects_extended_preview_signals(self):
        soup = BeautifulSoup(
            """
            <html lang="zh-CN">
              <head>
                <title>示例页面</title>
                <meta name="description" content="描述">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <meta property="og:title" content="OG Title">
                <meta property="og:description" content="OG Description">
                <meta property="og:image" content="https://example.com/cover.png">
                <meta property="og:type" content="website">
                <meta property="og:locale" content="zh_CN">
                <meta name="twitter:card" content="summary_large_image">
                <link rel="canonical" href="https://example.com/demo">
                <link rel="icon" href="/favicon.ico">
              </head>
            </html>
            """,
            "lxml",
        )

        result = _check_meta(soup)

        self.assertTrue(result["checks"]["html_lang"])
        self.assertTrue(result["checks"]["viewport"])
        self.assertTrue(result["checks"]["favicon"])
        self.assertEqual(result["preview_score"], 100)

    def test_check_content_collects_rich_page_signals(self):
        soup = BeautifulSoup(
            """
            <html>
              <body>
                <h1>主标题</h1>
                <h2>常见问题</h2>
                <p>这是一个足够长的首段，用于说明页面主题和关键价值。它包含较多有效字符，适合被当作直达答案摘要。</p>
                <p>补充段落。</p>
                <ul><li>要点一</li><li>要点二</li></ul>
                <table><tr><td>结构化</td></tr></table>
                <img src="/a.png" alt="示例图片">
                <img src="/b.png">
                <a href="/contact">联系我们</a>
              </body>
            </html>
            """,
            "lxml",
        )

        result = _check_content(soup)

        self.assertEqual(result["list_count"], 1)
        self.assertEqual(result["table_count"], 1)
        self.assertEqual(result["image_count"], 2)
        self.assertEqual(result["image_with_alt_count"], 1)
        self.assertEqual(result["image_alt_ratio"], 50)
        self.assertGreaterEqual(result["faq_like_sections"], 1)
        self.assertGreaterEqual(result["cta_count"], 1)

    def test_check_citations_tracks_internal_social_and_authority_links(self):
        soup = BeautifulSoup(
            """
            <html>
              <body>
                <a href="https://example.com/about">关于我们</a>
                <a href="https://arxiv.org/abs/1234.5678">论文</a>
                <a href="https://linkedin.com/company/demo">LinkedIn</a>
              </body>
            </html>
            """,
            "lxml",
        )

        result = _check_citations(soup, "example.com")

        self.assertEqual(result["internal_link_count"], 1)
        self.assertEqual(result["authority_link_count"], 1)
        self.assertEqual(result["social_link_count"], 1)


if __name__ == "__main__":
    unittest.main()
