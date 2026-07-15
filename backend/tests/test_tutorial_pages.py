import unittest
from pathlib import Path

from app.web.tutorial_pages import _render_page


class TutorialPageTests(unittest.TestCase):
    def test_empty_tutorial_page_uses_public_tutorial_branding(self):
        response = _render_page(
            title="GEO 教程中心 - GEOrank",
            description="公开教程",
            canonical_url="https://example.test/tutorial",
            side_nav_html='<div class="tutorial-state-card">当前还没有已发布教程</div>',
            mobile_nav_html="",
            breadcrumb_category="教程",
            breadcrumb_title="频道首页",
            heading_title="GEO 教程中心",
            overview_html="",
            reading_meta_html="已收录：0 篇文章",
            updated_meta_html="",
            article_html='<div class="tutorial-state-card">当前还没有已发布教程</div>',
            article_nav_html="",
            toc_title="栏目索引",
            toc_html="暂无目录",
            feedback_hidden=True,
        )
        html = response.body.decode("utf-8")

        self.assertIn("GEO 教程中心", html)
        self.assertIn("当前还没有已发布教程", html)
        self.assertNotIn("Wiki", html)

    def test_static_tutorial_entry_points_use_public_tutorial_branding(self):
        repo_root = Path(__file__).resolve().parents[2]
        paths = [
            repo_root / "backend" / "app" / "web" / "tutorial_pages.py",
            repo_root / "packages" / "i18n" / "src" / "dictionaries" / "zh-CN.ts",
            repo_root / "packages" / "i18n" / "src" / "dictionaries" / "en-US.ts",
            repo_root / "dist" / "index.html",
            repo_root / "dist" / "tutorial.html",
            repo_root / "dist" / "js" / "tutorial.js",
        ]

        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("Wiki", text, str(path))

        for path in (paths[0], paths[1], paths[4], paths[5]):
            self.assertIn("GEO 教程中心", path.read_text(encoding="utf-8"), str(path))
        self.assertIn("GEO Tutorial Center", paths[2].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
