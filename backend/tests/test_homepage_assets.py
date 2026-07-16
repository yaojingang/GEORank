import io
import hashlib
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.homepage_assets as homepage_assets  # noqa: E402
from app.services.homepage_assets import (  # noqa: E402
    HomepageAssetError,
    HomepageAssetLimits,
    activate_homepage_release,
    build_single_html_release,
    build_zip_homepage_release,
    read_homepage_entry_source,
    reset_active_homepage,
    update_homepage_entry_source,
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
        self.assertIn("script-src 'self'", index_html)
        self.assertNotIn("window.__bad", index_html)
        self.assertEqual(index_html.count('data-georank-navigation-runtime'), 1)
        self.assertIn('src="/js/site-navigation.js"', index_html)
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
        self.assertIn("script-src 'self'", index_html)
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

    def test_reads_original_homepage_html_for_editing(self):
        original = '<html><body onload="boot()"><h1>Original</h1><script>boot()</script></body></html>'
        build_single_html_release(self.root, "release-edit", "Editable", original)

        self.assertEqual(read_homepage_entry_source(self.root, "release-edit"), original)

    def test_updates_active_homepage_from_edited_source(self):
        build_zip_homepage_release(
            self.root,
            "release-edit-active",
            "Editable package",
            "home.zip",
            self._zip_bytes(
                {
                    "index.html": '<link href="./style.css" rel="stylesheet"><h1>Before</h1>',
                    "style.css": "h1 { color: blue; }",
                }
            ),
        )
        activate_homepage_release(self.root, "release-edit-active")

        manifest = update_homepage_entry_source(
            self.root,
            "release-edit-active",
            '<html><body onload="bad()"><h1>After</h1><script>bad()</script></body></html>',
            title="Editable package",
            source_type="zip_package",
            sync_active=True,
        )

        source_html = read_homepage_entry_source(self.root, "release-edit-active")
        public_html = (self.root / "public" / "releases" / "release-edit-active" / "index.html").read_text()
        active_html = (self.root / "public" / "active" / "index.html").read_text()
        self.assertIn("onload", source_html)
        self.assertIn("After", public_html)
        self.assertNotIn("onload", public_html.lower())
        self.assertNotIn("bad()", public_html)
        self.assertEqual(public_html.count('data-georank-navigation-runtime'), 1)
        self.assertIn("After", active_html)
        self.assertTrue((self.root / "public" / "releases" / "release-edit-active" / "style.css").is_file())
        self.assertEqual(manifest["file_count"], 2)
        self.assertIn("updated_at", manifest)

    def test_active_edit_keeps_analytics_and_manifest_hash_in_sync(self):
        build_single_html_release(
            self.root,
            "release-edit-analytics",
            "Analytics homepage",
            "<html><body><h1>Before</h1></body></html>",
        )
        activate_homepage_release(self.root, "release-edit-analytics")

        try:
            manifest = update_homepage_entry_source(
                self.root,
                "release-edit-analytics",
                "<html><body><h1>After</h1></body></html>",
                title="Analytics homepage",
                source_type="single_html",
                sync_active=True,
                analytics_code='<script data-site="analytics">track()</script>',
            )
        except TypeError as exc:
            self.fail(f"active homepage edits must preserve analytics in one write: {exc}")

        public_index = self.root / "public" / "releases" / "release-edit-analytics" / "index.html"
        public_bytes = public_index.read_bytes()
        public_entry = next(item for item in manifest["files"] if item["path"] == "index.html")
        self.assertIn('data-site="analytics"', public_bytes.decode("utf-8"))
        self.assertEqual(public_entry["sha256"], hashlib.sha256(public_bytes).hexdigest())
        self.assertEqual(
            (self.root / "public" / "active" / "index.html").read_bytes(),
            public_bytes,
        )

    def test_rejects_saving_over_a_newer_homepage_source(self):
        initial_html = "<html><body><h1>Initial</h1></body></html>"
        build_single_html_release(
            self.root,
            "release-edit-conflict",
            "Conflict homepage",
            initial_html,
        )
        initial_sha256 = hashlib.sha256(initial_html.encode("utf-8")).hexdigest()

        try:
            update_homepage_entry_source(
                self.root,
                "release-edit-conflict",
                "<html><body><h1>First editor</h1></body></html>",
                title="Conflict homepage",
                source_type="single_html",
                expected_sha256=initial_sha256,
            )
        except TypeError as exc:
            self.fail(f"homepage saves must accept a source revision: {exc}")

        with self.assertRaisesRegex(HomepageAssetError, "已被其他管理员更新"):
            update_homepage_entry_source(
                self.root,
                "release-edit-conflict",
                "<html><body><h1>Stale editor</h1></body></html>",
                title="Conflict homepage",
                source_type="single_html",
                expected_sha256=initial_sha256,
            )

        self.assertIn("First editor", read_homepage_entry_source(self.root, "release-edit-conflict"))

    def test_editor_revision_preserves_crlf_source_bytes(self):
        original_html = "<html>\r\n<body><h1>Windows package</h1></body>\r\n</html>"
        build_zip_homepage_release(
            self.root,
            "release-edit-crlf",
            "CRLF homepage",
            "home.zip",
            self._zip_bytes({"index.html": original_html}),
        )
        editor_html = read_homepage_entry_source(self.root, "release-edit-crlf")
        editor_sha256 = hashlib.sha256(editor_html.encode("utf-8")).hexdigest()

        update_homepage_entry_source(
            self.root,
            "release-edit-crlf",
            editor_html.replace("Windows package", "Saved package"),
            title="CRLF homepage",
            source_type="zip_package",
            expected_sha256=editor_sha256,
        )

        self.assertIn("Saved package", read_homepage_entry_source(self.root, "release-edit-crlf"))

    def test_clones_homepage_package_as_clean_editable_release(self):
        source_html = '<html><head></head><body><h1>Built in</h1><script>unsafe()</script></body></html>'
        build_zip_homepage_release(
            self.root,
            "release-builtin",
            "Built-in homepage",
            "home.zip",
            self._zip_bytes(
                {
                    "index.html": source_html,
                    "assets/style.css": "h1 { color: blue; }",
                }
            ),
        )
        activate_homepage_release(self.root, "release-builtin")
        homepage_assets.apply_analytics_to_active_homepage(
            self.root,
            '<script data-site="analytics">track()</script>',
        )

        clone_release = getattr(homepage_assets, "clone_homepage_release", None)
        self.assertIsNotNone(clone_release, "homepage assets must support safe release cloning")
        manifest = clone_release(
            self.root,
            "release-builtin",
            "release-copy",
            title="Built-in homepage 可编辑副本",
            source_type="zip_package",
        )

        cloned_source = read_homepage_entry_source(self.root, "release-copy")
        cloned_public = (self.root / "public" / "releases" / "release-copy" / "index.html").read_text()
        self.assertEqual(cloned_source, source_html)
        self.assertNotIn("unsafe()", cloned_public)
        self.assertNotIn("GEORANK_ANALYTICS_START", cloned_public)
        self.assertTrue((self.root / "public" / "releases" / "release-copy" / "assets" / "style.css").is_file())
        self.assertEqual(manifest["id"], "release-copy")
        self.assertEqual(manifest["title"], "Built-in homepage 可编辑副本")
        self.assertEqual(manifest["source_type"], "zip_package")


if __name__ == "__main__":
    unittest.main()
