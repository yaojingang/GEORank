import io
import hashlib
import json
import stat
import shutil
import tempfile
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.homepage_assets import (  # noqa: E402
    _render_public_homepage_file,
    HomepageAssetError,
    HomepageAssetLimits,
    activate_homepage_release,
    apply_analytics_to_active_homepage,
    build_single_html_release,
    build_zip_homepage_release,
    reset_active_homepage,
)
from app.services.runtime_settings import DEFAULT_HOMEPAGE_RELEASE_ID  # noqa: E402
from app.services import homepage_assets  # noqa: E402


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

    def _release_snapshot(self, release_id: str) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for base in (
            self.root / "releases" / release_id,
            self.root / "public" / "releases" / release_id,
        ):
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    key = path.relative_to(self.root).as_posix()
                    snapshot[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        return snapshot

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

    def test_single_html_release_preserves_preformatted_trailing_spaces(self):
        build_single_html_release(
            self.root,
            "release-preformatted",
            "Preformatted 首页",
            "<html><head></head><body><pre>line  \nnext</pre></body></html>",
        )

        index_html = (
            self.root / "public" / "releases" / "release-preformatted" / "index.html"
        ).read_text(encoding="utf-8")

        self.assertIn("<pre>line  \nnext</pre>", index_html)

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

    def test_activate_rejects_release_tree_with_runtime_symlink(self):
        build_zip_homepage_release(
            self.root,
            "release-runtime-link",
            "Runtime link",
            "runtime-link.zip",
            self._zip_bytes({"index.html": "<h1>Safe</h1>"}),
        )
        outside = self.root / "outside.css"
        outside.write_text("body { color: red; }")
        (
            self.root / "public" / "releases" / "release-runtime-link" / "linked.css"
        ).symlink_to(outside)

        with self.assertRaisesRegex(HomepageAssetError, "不能包含符号链接"):
            activate_homepage_release(self.root, "release-runtime-link")

        self.assertFalse((self.root / "public" / "active").exists())

    def test_analytics_overlay_keeps_release_and_manifest_immutable(self):
        build_zip_homepage_release(
            self.root,
            "release-analytics",
            "Analytics",
            "analytics.zip",
            self._zip_bytes(
                {
                    "index.html": "<html><head></head><body><h1>Original</h1></body></html>",
                    "style.css": "body { color: navy; }",
                }
            ),
        )
        release_snapshot = self._release_snapshot("release-analytics")
        activate_homepage_release(self.root, "release-analytics")

        changed = apply_analytics_to_active_homepage(
            self.root,
            '<script data-georank-test="analytics">window.track = true</script>',
        )

        self.assertTrue(changed)
        active_html = (self.root / "public" / "active" / "index.html").read_text()
        self.assertIn('data-georank-test="analytics"', active_html)
        self.assertEqual(self._release_snapshot("release-analytics"), release_snapshot)

        removed = apply_analytics_to_active_homepage(self.root, "")

        self.assertTrue(removed)
        active_html = (self.root / "public" / "active" / "index.html").read_text()
        self.assertNotIn('data-georank-test="analytics"', active_html)
        self.assertEqual(self._release_snapshot("release-analytics"), release_snapshot)

    def test_activation_can_publish_analytics_overlay_in_one_atomic_operation(self):
        build_zip_homepage_release(
            self.root,
            "release-activate-analytics",
            "Activate analytics",
            "activate-analytics.zip",
            self._zip_bytes({"index.html": "<html><head></head><body>Atomic</body></html>"}),
        )
        release_snapshot = self._release_snapshot("release-activate-analytics")

        active_path = activate_homepage_release(
            self.root,
            "release-activate-analytics",
            analytics_code="<script>activateTrack()</script>",
        )

        self.assertEqual(active_path.readlink().parts[0], "active-overlays")
        self.assertIn("activateTrack()", (active_path / "index.html").read_text())
        self.assertEqual(
            self._release_snapshot("release-activate-analytics"),
            release_snapshot,
        )

    def test_activate_analytics_remove_and_rollback_preserve_release_previews(self):
        for release_id, heading in (("release-one", "One"), ("release-two", "Two")):
            build_zip_homepage_release(
                self.root,
                release_id,
                heading,
                f"{release_id}.zip",
                self._zip_bytes({"index.html": f"<html><head></head><body>{heading}</body></html>"}),
            )
        snapshots = {
            release_id: self._release_snapshot(release_id)
            for release_id in ("release-one", "release-two")
        }

        activate_homepage_release(self.root, "release-one")
        apply_analytics_to_active_homepage(self.root, "<script>trackOne()</script>")
        apply_analytics_to_active_homepage(self.root, "")
        activate_homepage_release(self.root, "release-two")
        self.assertIn("Two", (self.root / "public" / "active" / "index.html").read_text())

        activate_homepage_release(self.root, "release-one")

        active_html = (self.root / "public" / "active" / "index.html").read_text()
        preview_html = (
            self.root / "public" / "releases" / "release-one" / "index.html"
        ).read_text()
        self.assertIn("One", active_html)
        self.assertNotIn("trackOne", active_html)
        self.assertEqual(active_html, preview_html)
        for release_id, snapshot in snapshots.items():
            self.assertEqual(self._release_snapshot(release_id), snapshot)

    def test_concurrent_analytics_updates_leave_one_safe_complete_overlay(self):
        build_zip_homepage_release(
            self.root,
            "release-concurrent",
            "Concurrent",
            "concurrent.zip",
            self._zip_bytes({"index.html": "<html><head></head><body>Concurrent</body></html>"}),
        )
        release_snapshot = self._release_snapshot("release-concurrent")
        activate_homepage_release(self.root, "release-concurrent")
        snippets = [f"<script>track({index})</script>" for index in range(8)]

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(
                executor.map(
                    lambda snippet: apply_analytics_to_active_homepage(self.root, snippet),
                    snippets,
                )
            )

        self.assertTrue(all(results))
        active_path = self.root / "public" / "active"
        self.assertTrue(active_path.is_symlink())
        self.assertEqual(active_path.readlink().parts[0], "active-overlays")
        self.assertTrue(active_path.resolve().is_relative_to((self.root / "public" / "active-overlays").resolve()))
        active_html = (active_path / "index.html").read_text()
        self.assertEqual(active_html.count("GEORANK_ANALYTICS_START"), 1)
        self.assertEqual(active_html.count("GEORANK_ANALYTICS_END"), 1)
        self.assertEqual(active_html.count("<script>track("), 1)
        self.assertEqual(self._release_snapshot("release-concurrent"), release_snapshot)

    def test_overlay_replacement_and_reset_remove_stale_overlay_directories(self):
        build_zip_homepage_release(
            self.root,
            "release-cleanup",
            "Cleanup",
            "cleanup.zip",
            self._zip_bytes({"index.html": "<html><head></head><body>Cleanup</body></html>"}),
        )
        active_path = activate_homepage_release(self.root, "release-cleanup")
        apply_analytics_to_active_homepage(self.root, "<script>first()</script>")
        first_overlay = (active_path.parent / active_path.readlink()).resolve()

        apply_analytics_to_active_homepage(self.root, "<script>second()</script>")
        second_overlay = (active_path.parent / active_path.readlink()).resolve()

        self.assertNotEqual(first_overlay, second_overlay)
        self.assertFalse(first_overlay.exists())
        self.assertTrue(second_overlay.exists())

        reset_active_homepage(self.root)

        self.assertFalse(active_path.exists())
        self.assertFalse(second_overlay.exists())

    def test_stale_overlay_cleanup_failure_does_not_roll_back_committed_pointer(self):
        build_zip_homepage_release(
            self.root,
            "release-cleanup-failure",
            "Cleanup failure",
            "cleanup-failure.zip",
            self._zip_bytes({"index.html": "<html><head></head><body>Cleanup</body></html>"}),
        )
        release_snapshot = self._release_snapshot("release-cleanup-failure")
        active_path = activate_homepage_release(self.root, "release-cleanup-failure")
        apply_analytics_to_active_homepage(self.root, "<script>first()</script>")
        stale_overlay = (active_path.parent / active_path.readlink()).resolve()

        from app.services import homepage_assets

        original_remove_path = homepage_assets._remove_path

        def fail_stale_cleanup(path):
            if Path(path) == stale_overlay:
                raise PermissionError("simulated stale overlay cleanup failure")
            return original_remove_path(path)

        with patch(
            "app.services.homepage_assets._remove_path",
            side_effect=fail_stale_cleanup,
        ):
            changed = apply_analytics_to_active_homepage(
                self.root,
                "<script>second()</script>",
            )

        self.assertTrue(changed)
        self.assertTrue(active_path.is_symlink())
        self.assertTrue(active_path.exists())
        self.assertIn("second()", (active_path / "index.html").read_text())
        self.assertTrue(stale_overlay.exists())
        self.assertEqual(
            self._release_snapshot("release-cleanup-failure"),
            release_snapshot,
        )

    def test_analytics_rejects_active_pointer_outside_runtime_public_roots(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "index.html").write_text("<html><head></head></html>")
        public_root = self.root / "public"
        public_root.mkdir()
        (public_root / "active").symlink_to(outside)

        with self.assertRaisesRegex(HomepageAssetError, "目标不安全"):
            apply_analytics_to_active_homepage(self.root, "<script>bad()</script>")

        self.assertNotIn("bad()", (outside / "index.html").read_text())

    def test_analytics_rejects_symlinked_overlay_root_without_deleting_release(self):
        release_id = "release-overlay-root-link"
        build_zip_homepage_release(
            self.root,
            release_id,
            "Overlay root link",
            "overlay-root-link.zip",
            self._zip_bytes({"index.html": "<html><head></head><body>Safe</body></html>"}),
        )
        release_snapshot = self._release_snapshot(release_id)
        public_root = self.root / "public"
        (public_root / "active-overlays").symlink_to("releases")
        (public_root / "active").symlink_to(Path("active-overlays") / release_id)

        with self.assertRaisesRegex(HomepageAssetError, "overlay.*符号链接"):
            apply_analytics_to_active_homepage(self.root, "<script>bad()</script>")

        self.assertEqual(self._release_snapshot(release_id), release_snapshot)

    def test_release_deletion_rejects_symlinked_parent_without_touching_external_data(self):
        release_id = "release-delete-parent-link"
        build_zip_homepage_release(
            self.root,
            release_id,
            "Delete parent link",
            "delete-parent-link.zip",
            self._zip_bytes({"index.html": "<html><body>Safe</body></html>"}),
        )
        external_root = self.root / "external-public-releases"
        public_releases = self.root / "public" / "releases"
        shutil.move(public_releases, external_root)
        public_releases.symlink_to(external_root)
        external_snapshot = {
            path.relative_to(external_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in external_root.rglob("*")
            if path.is_file()
        }

        with self.assertRaisesRegex(HomepageAssetError, "releases.*符号链接"):
            homepage_assets.stage_homepage_release_deletion(self.root, release_id)

        self.assertEqual(
            {
                path.relative_to(external_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in external_root.rglob("*")
                if path.is_file()
            },
            external_snapshot,
        )

    def test_staged_release_deletion_can_rollback_or_commit(self):
        release_id = "release-delete-staged"
        build_zip_homepage_release(
            self.root,
            release_id,
            "Delete staged",
            "delete-staged.zip",
            self._zip_bytes({"index.html": "<html><body>Safe</body></html>"}),
        )
        release_snapshot = self._release_snapshot(release_id)

        deletion = homepage_assets.stage_homepage_release_deletion(self.root, release_id)
        self.assertFalse((self.root / "releases" / release_id).exists())
        self.assertFalse((self.root / "public" / "releases" / release_id).exists())
        deletion.rollback()
        self.assertEqual(self._release_snapshot(release_id), release_snapshot)

        deletion = homepage_assets.stage_homepage_release_deletion(self.root, release_id)
        deletion.commit()
        deletion.commit()
        self.assertFalse((self.root / "releases" / release_id).exists())
        self.assertFalse((self.root / "public" / "releases" / release_id).exists())

    def test_release_deletion_rejects_real_active_target_during_crash_window(self):
        release_id = "release-delete-active-pointer"
        build_zip_homepage_release(
            self.root,
            release_id,
            "Delete active pointer",
            "delete-active-pointer.zip",
            self._zip_bytes({"index.html": "<html><body>Still active</body></html>"}),
        )
        active_path = activate_homepage_release(self.root, release_id, analytics_code="")

        with self.assertRaisesRegex(HomepageAssetError, "当前 active 指针"):
            homepage_assets.stage_homepage_release_deletion(self.root, release_id)

        self.assertTrue(active_path.is_symlink())
        self.assertTrue(active_path.exists())
        self.assertTrue((self.root / "releases" / release_id).is_dir())
        self.assertTrue((self.root / "public" / "releases" / release_id).is_dir())

    def test_release_deletion_rejects_active_overlay_source_during_crash_window(self):
        release_id = "release-delete-active-overlay"
        build_zip_homepage_release(
            self.root,
            release_id,
            "Delete active overlay",
            "delete-active-overlay.zip",
            self._zip_bytes({"index.html": "<html><head></head><body>Still active</body></html>"}),
        )
        active_path = activate_homepage_release(
            self.root,
            release_id,
            analytics_code="<script>trackCrashWindow()</script>",
        )

        with self.assertRaisesRegex(HomepageAssetError, "active overlay"):
            homepage_assets.stage_homepage_release_deletion(self.root, release_id)

        self.assertTrue(active_path.is_symlink())
        self.assertTrue(active_path.exists())
        self.assertTrue((self.root / "releases" / release_id).is_dir())
        self.assertTrue((self.root / "public" / "releases" / release_id).is_dir())

    def test_release_deletion_cleanup_failure_is_best_effort_after_commit(self):
        release_id = "release-delete-cleanup-failure"
        build_zip_homepage_release(
            self.root,
            release_id,
            "Delete cleanup failure",
            "delete-cleanup-failure.zip",
            self._zip_bytes({"index.html": "<html><body>Safe</body></html>"}),
        )
        deletion = homepage_assets.stage_homepage_release_deletion(self.root, release_id)
        original_remove_path = homepage_assets._remove_path
        attempted_paths: list[Path] = []

        def fail_source_cleanup(path: Path) -> None:
            attempted_paths.append(Path(path))
            if Path(path).parent == (self.root / "releases").resolve():
                raise PermissionError("simulated quarantine cleanup failure")
            original_remove_path(Path(path))

        with patch.object(homepage_assets, "_remove_path", side_effect=fail_source_cleanup):
            deletion.commit()

        self.assertTrue(deletion.finalized)
        self.assertEqual(len(attempted_paths), 2)
        self.assertTrue(any(path.parent == (self.root / "releases").resolve() for path in attempted_paths))
        self.assertFalse(
            any(
                path.parent == (self.root / "public" / "releases").resolve() and path.exists()
                for path in attempted_paths
            )
        )

    def test_failed_analytics_pointer_swap_preserves_previous_active_release(self):
        build_zip_homepage_release(
            self.root,
            "release-atomic",
            "Atomic",
            "atomic.zip",
            self._zip_bytes({"index.html": "<html><head></head><body>Atomic</body></html>"}),
        )
        release_snapshot = self._release_snapshot("release-atomic")
        active_path = activate_homepage_release(self.root, "release-atomic")
        original_target = active_path.readlink()
        original_replace = __import__("os").replace

        def fail_pointer_swap(source, destination):
            if Path(destination) == active_path:
                raise OSError("simulated pointer swap failure")
            return original_replace(source, destination)

        with patch("app.services.homepage_assets.os.replace", side_effect=fail_pointer_swap):
            with self.assertRaisesRegex(OSError, "pointer swap failure"):
                apply_analytics_to_active_homepage(self.root, "<script>never()</script>")

        self.assertEqual(active_path.readlink(), original_target)
        self.assertNotIn("never()", (active_path / "index.html").read_text())
        self.assertEqual(self._release_snapshot("release-atomic"), release_snapshot)

    def test_builtin_homepage_manifest_matches_public_release_files(self):
        repo_root = Path(__file__).resolve().parents[2]
        release_id = DEFAULT_HOMEPAGE_RELEASE_ID
        manifest_path = repo_root / "runtime" / "homepages" / "releases" / release_id / "manifest.json"
        public_dir = repo_root / "runtime" / "homepages" / "public" / "releases" / release_id
        source_dir = repo_root / "runtime" / "homepages" / "releases" / release_id / "source"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        expected_files = []
        for path in sorted(public_dir.rglob("*")):
            if path.is_file():
                payload = path.read_bytes()
                expected_files.append(
                    {
                        "path": path.relative_to(public_dir).as_posix(),
                        "size": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                )

        self.assertEqual(manifest["files"], expected_files)
        self.assertEqual(manifest["file_count"], len(expected_files))
        self.assertEqual(
            manifest["extracted_size"],
            sum(path.stat().st_size for path in source_dir.rglob("*") if path.is_file()),
        )
        self.assertEqual(manifest["storage_path"], f"/app/runtime/homepages/releases/{release_id}")
        self.assertEqual(manifest["public_path"], f"/app/runtime/homepages/public/releases/{release_id}")
        active_path = repo_root / "runtime" / "homepages" / "public" / "active"
        self.assertTrue(active_path.is_symlink())
        self.assertEqual(active_path.readlink(), Path("releases") / release_id)
        self.assertFalse(
            (repo_root / "runtime" / "homepages" / "releases" / "f7e16e7c-e1aa-4e39-951b-4c274dd05175").exists()
        )

    def test_builtin_homepage_source_rebuilds_the_published_release(self):
        repo_root = Path(__file__).resolve().parents[2]
        release_id = "43a461f6-6be2-4931-9dbb-f1d56576292a"
        release_root = repo_root / "runtime" / "homepages"
        source_root = release_root / "releases" / release_id / "source"
        public_root = release_root / "public" / "releases" / release_id
        manifest = json.loads(
            (release_root / "releases" / release_id / "manifest.json").read_text(encoding="utf-8")
        )

        source_files = sorted(path for path in source_root.rglob("*") if path.is_file())
        public_files = sorted(path for path in public_root.rglob("*") if path.is_file())
        self.assertEqual(
            [path.relative_to(source_root).as_posix() for path in source_files],
            [path.relative_to(public_root).as_posix() for path in public_files],
        )

        for source_path in source_files:
            relative_path = source_path.relative_to(source_root)
            public_payload = (public_root / relative_path).read_bytes()
            expected_payload = _render_public_homepage_file(
                relative_path.as_posix(),
                source_path.read_bytes(),
            )
            self.assertEqual(public_payload, expected_payload, relative_path.as_posix())

        manifest_by_path = {item["path"]: item for item in manifest["files"]}
        for public_path in public_files:
            relative_path = public_path.relative_to(public_root).as_posix()
            payload = public_path.read_bytes()
            self.assertEqual(manifest_by_path[relative_path]["size"], len(payload))
            self.assertEqual(
                manifest_by_path[relative_path]["sha256"],
                hashlib.sha256(payload).hexdigest(),
            )

        self.assertIn("/tutorial", source_root.joinpath("index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
