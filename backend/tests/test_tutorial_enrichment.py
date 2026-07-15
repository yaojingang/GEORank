import unittest

from app.services.tutorial_enrichment import (
    enrich_tutorial_markdown,
    estimate_reading_time_minutes,
)

class TutorialEnrichmentTests(unittest.TestCase):
    def test_public_tutorial_keeps_only_the_authored_markdown(self):
        raw_markdown = "# 公开示例\n\n这是一个短小的原创示例。"

        self.assertEqual(
            enrich_tutorial_markdown("公开示例", raw_markdown),
            raw_markdown,
        )

    def test_empty_tutorial_remains_empty(self):
        self.assertEqual(enrich_tutorial_markdown("", None), "")

    def test_legacy_next_article_marker_is_removed(self):
        raw_markdown = """# 示例教程

正文段落。

下一篇《商业价值》会继续往前推进。
"""
        enriched_markdown = enrich_tutorial_markdown("GEO与SEO", raw_markdown)
        self.assertNotIn("下一篇《商业价值》", enriched_markdown)

    def test_short_public_example_has_a_one_minute_reading_time(self):
        self.assertEqual(estimate_reading_time_minutes("# 示例\n\n三条检查项。"), 1)
