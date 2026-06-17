import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.content_render import render_markdown  # noqa: E402


class ContentRenderTests(unittest.TestCase):
    def test_render_markdown_removes_dangerous_html(self):
        html = render_markdown(
            "# Title\n\n"
            '<script>window.bad = true</script>\n\n'
            '<img src="javascript:alert(1)" onerror="alert(2)" alt="x">\n\n'
            '<a href="javascript:alert(3)" onclick="alert(4)">bad link</a>'
        )

        self.assertIn("<h1>Title</h1>", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("window.bad", html)
        self.assertNotIn("javascript:", html)
        self.assertNotIn("onerror", html)
        self.assertNotIn("onclick", html)

    def test_render_markdown_keeps_safe_links_tables_and_code(self):
        html = render_markdown(
            "See [GEOrank](https://example.com).\n\n"
            "| A | B |\n| - | - |\n| 1 | 2 |\n\n"
            "```html\n<script>example only</script>\n```"
        )

        self.assertIn('href="https://example.com"', html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn("<table>", html)
        self.assertIn("<code", html)
        self.assertIn("&lt;script&gt;example only&lt;/script&gt;", html)


if __name__ == "__main__":
    unittest.main()
