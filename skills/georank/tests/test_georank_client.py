import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import georank_client as client  # noqa: E402


class BaseUrlTests(unittest.TestCase):
    def test_allows_https_and_loopback_http(self):
        self.assertEqual(client.normalize_base_url("https://geo.example.com/"), "https://geo.example.com")
        self.assertEqual(client.normalize_base_url("http://localhost:8000"), "http://localhost:8000")

    def test_rejects_remote_http_and_embedded_credentials(self):
        with self.assertRaises(client.ClientError):
            client.normalize_base_url("http://geo.example.com")
        with self.assertRaises(client.ClientError):
            client.normalize_base_url("https://user:pass@geo.example.com")

    def test_rejects_invalid_port_and_whitespace_in_base_url(self):
        for target in (
            "https://geo.example.com:invalid",
            "https://geo.example.com:99999",
            "https://geo.example.com\n.evil",
            "https://[::1",
        ):
            with self.subTest(target=target), self.assertRaises(client.ClientError):
                client.normalize_base_url(target)

    def test_rejects_external_or_non_api_target(self):
        for target in (
            "https://evil.example/api/admin/users",
            "//evil.example/api/admin/users",
            "//[::1/api/admin/users",
            "/health",
            "/api/admin/../auth/me",
            "/api/admin/%2e%2e/auth/me",
            r"/api/admin\users",
            "/api/admin/%5cusers",
            "/api/companies/?search=bad\nheader",
        ):
            with self.subTest(target=target), self.assertRaises(client.ClientError):
                client.normalize_api_path(target)

    def test_canonicalizes_percent_encoded_admin_path_before_risk_classification(self):
        encoded = "/api/%61dmin/settings"
        self.assertEqual(client.normalize_api_path(encoded), "/api/admin/settings")
        self.assertEqual(client.classify_risk("PUT", encoded), "admin_write")
        with self.assertRaises(client.ClientError):
            client.validate_execution(
                "PUT",
                encoded,
                execute=True,
                confirmation=None,
                detected_role=None,
            )

    def test_rejects_double_encoded_paths_and_secret_query_parameters(self):
        for target in (
            "/api/%2561dmin/settings",
            "/api/companies/?apiKey=secret",
            "/api/companies/?access_token=secret",
        ):
            with self.subTest(target=target), self.assertRaises(client.ClientError):
                client.normalize_api_path(target)

    def test_encodes_non_ascii_query_values(self):
        class Response:
            status = 200
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size=-1):
                return b"{}"

        class Opener:
            request_url = ""

            def open(self, request, timeout):
                self.request_url = request.full_url
                return Response()

        api = client.ApiClient("https://geo.example.com")
        opener = Opener()
        api.opener = opener
        api.request("GET", "/api/companies/?search=中文")
        self.assertIn("search=%E4%B8%AD%E6%96%87", opener.request_url)

    def test_rejects_api_redirects(self):
        handler = client.RejectRedirectHandler()
        with self.assertRaises(client.ClientError):
            handler.redirect_request(None, None, 302, "Found", {}, "https://other.example/api/auth/me")


class SafetyTests(unittest.TestCase):
    def test_redacts_nested_secrets(self):
        payload = {
            "access_token": "token-value",
            "provider": {"api_key": "key-value", "model": "demo"},
            "legacy": {"apiKey": "legacy-key", "accessToken": "legacy-token"},
            "items": [{"password": "hidden", "name": "visible"}],
        }
        self.assertEqual(client.redact(payload)["access_token"], "[REDACTED]")
        self.assertEqual(client.redact(payload)["provider"]["api_key"], "[REDACTED]")
        self.assertEqual(client.redact(payload)["legacy"]["apiKey"], "[REDACTED]")
        self.assertEqual(client.redact(payload)["legacy"]["accessToken"], "[REDACTED]")
        self.assertEqual(client.redact(payload)["items"][0]["name"], "visible")

    def test_login_payload_has_no_role_selector(self):
        payload = client.build_login_payload(
            account="user@example.com",
            phone=None,
            password="example-password",
            remember_me=True,
        )
        self.assertNotIn("role", payload)
        self.assertEqual(payload["account"], "user@example.com")

    def test_admin_path_requires_live_admin_role(self):
        with self.assertRaises(client.ClientError):
            client.validate_execution(
                "GET",
                "/api/admin/dashboard",
                execute=False,
                confirmation=None,
                detected_role="user",
            )

    def test_admin_write_requires_exact_confirmation(self):
        with self.assertRaises(client.ClientError):
            client.validate_execution(
                "PUT",
                "/api/admin/frontend-modules",
                execute=True,
                confirmation=None,
                detected_role="admin",
            )
        result = client.validate_execution(
            "PUT",
            "/api/admin/frontend-modules",
            execute=True,
            confirmation="APPLY_ADMIN_CHANGE",
            detected_role="admin",
        )
        self.assertEqual(result["risk"], "admin_write")

    def test_delete_confirmation_is_bound_to_exact_path(self):
        path = "/api/admin/diagnostics/reports/report-id"
        expected = f"DELETE:{path}"
        with self.assertRaises(client.ClientError):
            client.validate_execution(
                "DELETE",
                path,
                execute=True,
                confirmation="APPLY_ADMIN_CHANGE",
                detected_role="admin",
            )
        result = client.validate_execution(
            "DELETE",
            path,
            execute=True,
            confirmation=expected,
            detected_role="admin",
        )
        self.assertEqual(result["required_confirmation"], expected)

    def test_delete_confirmation_is_bound_to_query_parameters(self):
        path = "/api/admin/diagnostics/reports/report-id?cascade=true"
        expected = f"DELETE:{path}"
        with self.assertRaises(client.ClientError):
            client.validate_execution(
                "DELETE",
                path,
                execute=True,
                confirmation="DELETE:/api/admin/diagnostics/reports/report-id",
                detected_role="admin",
            )
        result = client.validate_execution(
            "DELETE",
            path,
            execute=True,
            confirmation=expected,
            detected_role="admin",
        )
        self.assertEqual(result["required_confirmation"], expected)

    def test_request_and_response_sizes_are_bounded(self):
        class Response:
            status = 200
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size=-1):
                return b"x" * 11

        class Opener:
            def open(self, request, timeout):
                return Response()

        api = client.ApiClient("https://geo.example.com")
        api.opener = Opener()
        with mock.patch.object(client, "MAX_REQUEST_BYTES", 10):
            with self.assertRaises(client.ClientError):
                api.request("POST", "/api/diagnostics/", payload={"value": "too large"})
        with mock.patch.object(client, "MAX_RESPONSE_BYTES", 10):
            with self.assertRaises(client.ClientError):
                api.request("GET", "/api/diagnostics/report-id")

    def test_client_version_comes_from_manifest(self):
        manifest = json.loads((SCRIPT_DIR.parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(client.client_version(), manifest["version"])


class SessionTests(unittest.TestCase):
    def test_session_is_owner_only_and_round_trips(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_path = Path(temp_dir) / "nested" / "session.json"
            store = client.SessionStore(session_path)
            payload = {
                "base_url": "https://geo.example.com",
                "access_token": "test-session-token",
                "user": {"role": "user"},
            }
            store.save(payload)
            self.assertEqual(stat.S_IMODE(session_path.stat().st_mode), 0o600)
            stored = store.load()
            self.assertEqual(stored["_format"], client.SESSION_FORMAT)
            self.assertEqual({key: stored[key] for key in payload}, payload)
            self.assertTrue(store.clear())
            self.assertFalse(session_path.exists())

    def test_save_does_not_change_existing_parent_permissions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            parent = Path(temp_dir) / "shared"
            parent.mkdir()
            os.chmod(parent, 0o755)
            client.SessionStore(parent / "session.json").save({"access_token": "secret"})
            self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o755)

    def test_refuses_to_load_replace_or_delete_unmarked_private_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_path = Path(temp_dir) / "valuable.json"
            session_path.write_text(json.dumps({"access_token": "valuable-data"}), encoding="utf-8")
            os.chmod(session_path, 0o600)
            store = client.SessionStore(session_path)
            with self.assertRaises(client.ClientError):
                store.load()
            with self.assertRaises(client.ClientError):
                store.save({"access_token": "new-session"})
            with self.assertRaises(client.ClientError):
                store.clear()
            self.assertTrue(session_path.exists())

    @unittest.skipUnless(hasattr(os, "chmod"), "chmod is required")
    def test_rejects_group_readable_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_path = Path(temp_dir) / "session.json"
            session_path.write_text(json.dumps({"access_token": "secret"}), encoding="utf-8")
            os.chmod(session_path, 0o644)
            with self.assertRaises(client.ClientError):
                client.SessionStore(session_path).load()

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support is required")
    def test_rejects_symlinked_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            real_path = Path(temp_dir) / "real.json"
            link_path = Path(temp_dir) / "session.json"
            real_path.write_text(json.dumps({"access_token": "secret"}), encoding="utf-8")
            os.chmod(real_path, 0o600)
            link_path.symlink_to(real_path)
            with self.assertRaises(client.ClientError):
                client.SessionStore(link_path).load()

    def test_request_body_must_be_regular_and_bounded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir) / "body"
            directory.mkdir()
            with self.assertRaises(client.ClientError):
                client.load_request_payload(str(directory), False)

            body_path = Path(temp_dir) / "body.json"
            body_path.write_text(json.dumps({"value": "too large"}), encoding="utf-8")
            with mock.patch.object(client, "MAX_REQUEST_BYTES", 10):
                with self.assertRaises(client.ClientError):
                    client.load_request_payload(str(body_path), False)


if __name__ == "__main__":
    unittest.main()
