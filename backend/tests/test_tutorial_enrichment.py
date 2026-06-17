import re
import unittest
from pathlib import Path

from app.services.tutorial_enrichment import (
    MIN_PUBLIC_TUTORIAL_LENGTH,
    TUTORIAL_SUPPLEMENTS,
    enrich_tutorial_markdown,
    estimate_reading_time_minutes,
)


def _find_repo_root() -> Path | None:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        tutorial_root = candidate / "docs" / "tutorial-wiki"
        if tutorial_root.exists():
            return candidate
    return None


REPO_ROOT = _find_repo_root()
TUTORIAL_SOURCE_ROOT = REPO_ROOT / "docs" / "tutorial-wiki" if REPO_ROOT else None


def _extract_title(markdown_text: str) -> str:
    frontmatter_match = re.search(r"^title:\s*(.+)$", markdown_text, flags=re.M)
    if frontmatter_match:
        return frontmatter_match.group(1).strip()

    heading_match = re.search(r"^#\s+(.+)$", markdown_text, flags=re.M)
    if heading_match:
        return heading_match.group(1).strip()

    raise AssertionError("教程源稿缺少标题")


class TutorialEnrichmentTests(unittest.TestCase):
    def test_every_tutorial_has_whitepaper_supplement(self):
        self.assertEqual(len(TUTORIAL_SUPPLEMENTS), 28)

        if TUTORIAL_SOURCE_ROOT is None or not TUTORIAL_SOURCE_ROOT.exists():
            return

        source_titles = {
            _extract_title(path.read_text(encoding="utf-8"))
            for path in TUTORIAL_SOURCE_ROOT.rglob("*.md")
        }
        self.assertEqual(source_titles, set(TUTORIAL_SUPPLEMENTS))

    def test_enriched_public_markdown_reaches_minimum_depth(self):
        tutorial_sources: list[tuple[str, str]] = []

        if TUTORIAL_SOURCE_ROOT is not None and TUTORIAL_SOURCE_ROOT.exists():
            tutorial_sources = [
                (_extract_title(path.read_text(encoding="utf-8")), path.read_text(encoding="utf-8"))
                for path in sorted(TUTORIAL_SOURCE_ROOT.rglob("*.md"))
            ]
        else:
            tutorial_sources = [
                (title, f"# {title}\n\n这是《{title}》的基础教程正文。")
                for title in sorted(TUTORIAL_SUPPLEMENTS)
            ]

        for title, raw_markdown in tutorial_sources:
            enriched_markdown = enrich_tutorial_markdown(title, raw_markdown)

            compact = re.sub(r"\s+", "", enriched_markdown)
            self.assertGreaterEqual(
                len(compact),
                MIN_PUBLIC_TUTORIAL_LENGTH,
                f"{title} 富化后的公开教程正文不足 1500 字",
            )
            self.assertGreaterEqual(
                estimate_reading_time_minutes(enriched_markdown),
                5,
                f"{title} 的公开阅读时长估算过低",
            )

    def test_legacy_next_article_marker_is_removed(self):
        raw_markdown = """# 示例教程

正文段落。

下一篇《商业价值》会继续往前推进。
"""
        enriched_markdown = enrich_tutorial_markdown("GEO与SEO", raw_markdown)
        self.assertNotIn("下一篇《商业价值》", enriched_markdown)
