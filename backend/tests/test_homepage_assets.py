import io
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.homepage_assets import (  # noqa: E402
    HomepageAssetError,
    HomepageAssetLimits,
    activate_homepage_release,
    build_single_html_release,
    build_zip_homepage_release,
    reset_active_homepage,
)


class HomepageAssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _zip_bytes(self, files: dict[str, bytes | str]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                data = content.encode("utf-8") if isinstance(content, str) else content
                archive.writestr(name, data)
        return buffer.getvalue()

    def test_single_html_release_strips_scripts_and_rewrites_local_assets(self):
        release = build_single_html_release(
            self.root,
            "release-one",
            "Demo 首页",
            """
            <html>
              <head><title>Demo</title></head>
              <body onload="alert(1)">
                <img src="./assets/logo.png" onclick="alert(2)">
                <a href="/assets/doc.txt">资料</a>
                <a href="https://example.com">外链</a>
                <script>window.__bad = true</script>
              </body>
            </html>
            """,
        )

        index_html = (self.root / "public" / "releases" / "release-one" / "index.html").read_text()
        self.assertEqual(release["entry_path"], "index.html")
        self.assertIn('<meta charset="utf-8">', index_html)
        self.assertIn("script-src 'none'", index_html)
        self.assertNotIn("<script", index_html.lower())
        self.assertNotIn("onload", index_html.lower())
        self.assertNotIn("onclick", index_html.lower())
        self.assertIn('/_custom_homepage/active/assets/logo.png', index_html)
        self.assertIn('/_custom_homepage/active/assets/doc.txt', index_html)
        self.assertIn('href="https://example.com"', index_html)

    def test_single_html_release_replaces_uploaded_csp_and_dangerous_urls(self):
        build_single_html_release(
            self.root,
            "release-csp",
            "CSP 首页",
            """
            <html>
              <head>
                <meta http-equiv="Content-Security-Policy" content="script-src 'unsafe-inline' *">
              </head>
              <body>
                <a href="javascript:alert(1)">危险链接</a>
                <iframe srcdoc="<img src=x onerror=alert(2)>"></iframe>
              </body>
            </html>
            """,
        )

        index_html = (self.root / "public" / "releases" / "release-csp" / "index.html").read_text()
        self.assertIn("script-src 'none'", index_html)
        self.assertNotIn("unsafe-inline", index_html)
        self.assertNotIn("javascript:", index_html.lower())
        self.assertNotIn("srcdoc", index_html.lower())
        self.assertEqual(index_html.lower().count("content-security-policy"), 1)

    def test_zip_release_rejects_path_traversal(self):
        payload = self._zip_bytes({"index.html": "<h1>ok</h1>", "../evil.txt": "bad"})

        with self.assertRaises(HomepageAssetError):
            build_zip_homepage_release(self.root, "release-slip", "Bad", "home.zip", payload)

    def test_zip_release_rejects_symlinks(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("index.html", "<h1>ok</h1>")
            info = zipfile.ZipInfo("assets/link.txt")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "target.txt")

        with self.assertRaises(HomepageAssetError):
            build_zip_homepage_release(self.root, "release-link", "Bad", "home.zip", buffer.getvalue())

    def test_zip_release_rejects_unsupported_files(self):
        payload = self._zip_bytes({"index.html": "<h1>ok</h1>", "assets/app.js": "alert(1)"})

        with self.assertRaises(HomepageAssetError):
            build_zip_homepage_release(self.root, "release-js", "Bad", "home.zip", payload)

    def test_zip_release_rejects_extension_content_mismatch(self):
        payload = self._zip_bytes({"index.html": "<h1>ok</h1>", "assets/logo.png": b"not-a-png"})

        with self.assertRaises(HomepageAssetError):
            build_zip_homepage_release(self.root, "release-fake-image", "Bad", "home.zip", payload)

    def test_zip_release_sanitizes_svg_public_assets(self):
        payload = self._zip_bytes(
            {
                "index.html": '<img src="./assets/logo.svg">',
                "assets/logo.svg": '<svg onload="alert(1)"><script>alert(2)</script><a href="javascript:alert(3)"><circle /></a></svg>',
            }
        )

        build_zip_homepage_release(self.root, "release-svg", "SVG", "home.zip", payload)

        svg = (self.root / "public" / "releases" / "release-svg" / "assets" / "logo.svg").read_text()
        self.assertNotIn("<script", svg.lower())
        self.assertNotIn("onload", svg.lower())
        self.assertNotIn("javascript:", svg.lower())
        self.assertIn("<circle", svg)

    def test_zip_release_requires_index_html(self):
        payload = self._zip_bytes({"assets/style.css": "body{}"})

        with self.assertRaises(HomepageAssetError):
            build_zip_homepage_release(self.root, "release-missing", "Bad", "home.zip", payload)

    def test_zip_release_rejects_extra_html_pages(self):
        payload = self._zip_bytes(
            {
                "index.html": "<h1>ok</h1>",
                "extra.html": "<script>window.__bad = true</script>",
            }
        )

        with self.assertRaises(HomepageAssetError):
            build_zip_homepage_release(self.root, "release-extra-html", "Bad", "home.zip", payload)

    def test_zip_release_enforces_file_count_limit(self):
        payload = self._zip_bytes({"index.html": "<h1>ok</h1>", "style.css": "body{}"})

        with self.assertRaises(HomepageAssetError):
            build_zip_homepage_release(
                self.root,
                "release-many",
                "Bad",
                "home.zip",
                payload,
                limits=HomepageAssetLimits(max_files=1),
            )

    def test_zip_release_enforces_compressed_size_limit(self):
        payload = self._zip_bytes({"index.html": "<h1>ok</h1>"})

        with self.assertRaises(HomepageAssetError):
            build_zip_homepage_release(
                self.root,
                "release-too-large",
                "Bad",
                "home.zip",
                payload,
                limits=HomepageAssetLimits(max_compressed_size=1),
            )

    def test_zip_release_enforces_extracted_size_limit(self):
        payload = self._zip_bytes({"index.html": "<h1>ok</h1>", "content.txt": "x" * 40})

        with self.assertRaises(HomepageAssetError):
            build_zip_homepage_release(
                self.root,
                "release-extracted-too-large",
                "Bad",
                "home.zip",
                payload,
                limits=HomepageAssetLimits(max_extracted_size=16),
            )

    def test_zip_release_enforces_path_depth_limit(self):
        payload = self._zip_bytes(
            {
                "index.html": "<h1>ok</h1>",
                "a/b/c/d/e/f/g/h/i/style.css": "body{}",
            }
        )

        with self.assertRaises(HomepageAssetError):
            build_zip_homepage_release(
                self.root,
                "release-deep",
                "Bad",
                "home.zip",
                payload,
                limits=HomepageAssetLimits(max_path_depth=4),
            )

    def test_activate_and_reset_homepage_release(self):
        build_zip_homepage_release(
            self.root,
            "release-active",
            "Active",
            "home.zip",
            self._zip_bytes({"index.html": "<h1>Active</h1>", "style.css": "body{}"}),
        )

        active_path = activate_homepage_release(self.root, "release-active")
        self.assertTrue((active_path / "index.html").exists())
        self.assertIn("Active", (self.root / "public" / "active" / "index.html").read_text())

        reset_active_homepage(self.root)
        self.assertFalse((self.root / "public" / "active").exists())

    def test_activate_homepage_release_replaces_existing_active_pointer(self):
        build_zip_homepage_release(
            self.root,
            "release-one",
            "One",
            "one.zip",
            self._zip_bytes({"index.html": "<h1>One</h1>"}),
        )
        build_zip_homepage_release(
            self.root,
            "release-two",
            "Two",
            "two.zip",
            self._zip_bytes({"index.html": "<h1>Two</h1>"}),
        )

        activate_homepage_release(self.root, "release-one")
        activate_homepage_release(self.root, "release-two")

        self.assertIn("Two", (self.root / "public" / "active" / "index.html").read_text())


if __name__ == "__main__":
    unittest.main()
