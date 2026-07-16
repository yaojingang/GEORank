#!/usr/bin/env python3
"""Secure deterministic client for the GEOrank operator skill."""

from __future__ import annotations

import argparse
import getpass
import json
import math
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


SCRIPT_INTERFACE = "cli"
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 30.0
MAX_REQUEST_BYTES = 16 * 1024 * 1024
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_SESSION_BYTES = 1024 * 1024
SESSION_FORMAT = "georank-session-v1"
SAFE_METHODS = {"GET", "HEAD"}
SENSITIVE_KEY_FRAGMENTS = (
    "access_token",
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
)


class ClientError(RuntimeError):
    """Expected user-facing client failure."""


class RejectRedirectHandler(HTTPRedirectHandler):
    """Keep credentials on the user-selected GEOrank origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise ClientError(f"Refusing GEOrank API redirect (HTTP {code})")


def default_session_file() -> Path:
    configured = os.environ.get("GEORANK_SESSION_FILE")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".config" / "georank" / "session.json"


def normalize_base_url(value: str) -> str:
    raw = str(value or "")
    if any(character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F for character in raw):
        raise ClientError("GEOrank base URL must not contain whitespace or control characters")
    raw = raw.rstrip("/")
    try:
        parsed = urlsplit(raw)
    except ValueError as exc:
        raise ClientError("GEOrank base URL is malformed") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ClientError("GEOrank base URL must be an absolute HTTP(S) origin")
    if parsed.username or parsed.password:
        raise ClientError("GEOrank base URL must not contain credentials")
    try:
        parsed.port
    except ValueError as exc:
        raise ClientError("GEOrank base URL contains an invalid port") from exc
    if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ClientError("GEOrank base URL must not contain a path, query, or fragment")
    loopback_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme == "http" and parsed.hostname not in loopback_hosts:
        raise ClientError("Remote GEOrank instances must use HTTPS")
    return raw


def normalize_api_path(value: str) -> str:
    raw = str(value or "").strip()
    if any(character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F for character in raw):
        raise ClientError("API target must not contain whitespace or control characters")
    try:
        parsed = urlsplit(raw)
    except ValueError as exc:
        raise ClientError("API target is malformed") from exc
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ClientError("API target must be a relative /api path without a fragment")
    if not parsed.path.startswith("/api/"):
        raise ClientError("API target must begin with /api/")
    decoded_path = unquote(parsed.path)
    if "%" in decoded_path:
        raise ClientError("API target must not contain invalid or double-encoded path escapes")
    if "\\" in decoded_path:
        raise ClientError("API target must use forward slashes")
    if any(character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F for character in decoded_path):
        raise ClientError("API target path must not contain whitespace or control characters")
    decoded_segments = decoded_path.split("/")
    if any(segment in {".", ".."} for segment in decoded_segments):
        raise ClientError("API target must not contain path traversal segments")
    decoded_query = unquote(parsed.query)
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in decoded_query):
        raise ClientError("API target query must not contain control characters")
    query_fields = parse_qsl(parsed.query.replace(";", "&"), keep_blank_values=True)
    if any(is_sensitive_key(key) for key, _value in query_fields):
        raise ClientError("Secrets are not allowed in API query parameters; use the session or a JSON body")
    canonical_path = quote(decoded_path, safe="/:@!$&'()*+,;=-._~")
    return canonical_path + (f"?{parsed.query}" if parsed.query else "")


def is_sensitive_key(key: str) -> bool:
    compact_key = "".join(character for character in key.casefold() if character.isalnum())
    return any(
        "".join(character for character in fragment.casefold() if character.isalnum()) in compact_key
        for fragment in SENSITIVE_KEY_FRAGMENTS
    )


def redact(value: Any, parent_key: str = "") -> Any:
    if parent_key and is_sensitive_key(parent_key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(key): redact(item, str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def classify_risk(method: str, path: str) -> str:
    normalized_method = method.upper()
    normalized_path = normalize_api_path(path).split("?", 1)[0]
    if normalized_method in SAFE_METHODS:
        return "read"
    if normalized_method == "DELETE":
        return "destructive"
    if normalized_path == "/api/admin" or normalized_path.startswith("/api/admin/"):
        return "admin_write"
    return "user_write"


def required_confirmation(risk: str, path: str) -> str | None:
    canonical_target = normalize_api_path(path)
    if risk == "destructive":
        return f"DELETE:{canonical_target}"
    if risk == "admin_write":
        return "APPLY_ADMIN_CHANGE"
    return None


def validate_execution(
    method: str,
    path: str,
    *,
    execute: bool,
    confirmation: str | None,
    detected_role: str | None,
) -> dict[str, Any]:
    clean_path = normalize_api_path(path).split("?", 1)[0]
    is_admin_path = clean_path == "/api/admin" or clean_path.startswith("/api/admin/")
    if is_admin_path and detected_role != "admin":
        raise ClientError(f"Administrator role required; detected role: {detected_role or 'none'}")

    risk = classify_risk(method, path)
    phrase = required_confirmation(risk, path)
    if execute and phrase and confirmation != phrase:
        raise ClientError(f"Execution requires exact confirmation: {phrase}")
    return {
        "risk": risk,
        "execute_requested": bool(execute),
        "required_confirmation": phrase,
        "role_verified": detected_role if is_admin_path else None,
    }


def build_login_payload(
    *, account: str | None, phone: str | None, password: str, remember_me: bool
) -> dict[str, Any]:
    if bool(account) == bool(phone):
        raise ClientError("Provide exactly one of --account or --phone")
    payload: dict[str, Any] = {
        "password": password,
        "remember_me": remember_me,
    }
    if account:
        payload["account"] = account
    else:
        payload["phone"] = phone
    return payload


def parse_json_bytes(payload: bytes) -> Any:
    if not payload:
        return None
    text = payload.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def read_limited_bytes(stream: Any, limit: int, label: str) -> bytes:
    payload = stream.read(limit + 1)
    if len(payload) > limit:
        raise ClientError(f"{label} exceeds the {limit}-byte safety limit")
    return payload


def client_version() -> str:
    manifest_path = Path(__file__).resolve().parents[1] / "manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown"
    version = payload.get("version") if isinstance(payload, dict) else None
    return str(version) if version else "unknown"


class ApiClient:
    def __init__(self, base_url: str, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = normalize_base_url(base_url)
        timeout_value = float(timeout)
        if not math.isfinite(timeout_value):
            raise ClientError("Request timeout must be a finite number")
        self.timeout = max(1.0, min(timeout_value, 300.0))
        self.opener = build_opener(RejectRedirectHandler())

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: Any = None,
    ) -> dict[str, Any]:
        api_path = normalize_api_path(path)
        headers = {"Accept": "application/json", "User-Agent": f"georank-skill/{client_version()}"}
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if len(body) > MAX_REQUEST_BYTES:
                raise ClientError(f"GEOrank request body exceeds the {MAX_REQUEST_BYTES}-byte safety limit")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        encoded_api_path = quote(api_path, safe="/?&=%:+,;@[]!$'()*~-._")
        request = Request(
            f"{self.base_url}{encoded_api_path}",
            data=body,
            headers=headers,
            method=method.upper(),
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                data = parse_json_bytes(read_limited_bytes(response, MAX_RESPONSE_BYTES, "GEOrank response"))
                return {
                    "status_code": response.status,
                    "request_id": response.headers.get("X-Request-ID"),
                    "data": data,
                }
        except HTTPError as exc:
            data = parse_json_bytes(read_limited_bytes(exc, MAX_RESPONSE_BYTES, "GEOrank error response"))
            request_id = exc.headers.get("X-Request-ID") if exc.headers else None
            detail = json.dumps(redact(data), ensure_ascii=False) if data is not None else "no response body"
            raise ClientError(f"HTTP {exc.code} (request_id={request_id or 'unknown'}): {detail}") from exc
        except URLError as exc:
            raise ClientError(f"GEOrank network request failed: {exc.reason}") from exc


class SessionStore:
    def __init__(self, path: Path):
        expanded = path.expanduser()
        self.path = Path(os.path.abspath(os.fspath(expanded)))

    def load(self) -> dict[str, Any]:
        if self.path.is_symlink():
            raise ClientError("Refusing to read a symlinked GEOrank session file")
        if not self.path.exists():
            return {}
        file_stat = self.path.stat()
        if not stat.S_ISREG(file_stat.st_mode):
            raise ClientError("GEOrank session path must be a regular file")
        if hasattr(os, "getuid") and file_stat.st_uid != os.getuid():
            raise ClientError("GEOrank session file is not owned by the current user")
        if stat.S_IMODE(file_stat.st_mode) & 0o077:
            raise ClientError("GEOrank session file permissions must be 0600")
        try:
            if file_stat.st_size > MAX_SESSION_BYTES:
                raise ClientError(f"GEOrank session exceeds the {MAX_SESSION_BYTES}-byte safety limit")
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ClientError(f"Unable to read GEOrank session: {exc}") from exc
        if not isinstance(payload, dict):
            raise ClientError("GEOrank session must be a JSON object")
        if payload.get("_format") != SESSION_FORMAT:
            raise ClientError("Session path does not contain a recognized GEOrank session")
        return payload

    def save(self, payload: dict[str, Any]) -> None:
        parent = self.path.parent
        if parent.exists():
            if parent.is_symlink() or not parent.is_dir():
                raise ClientError("GEOrank session parent must be a regular directory")
        else:
            parent.mkdir(parents=True, mode=0o700)
        if self.path.is_symlink():
            raise ClientError("Refusing to replace a symlinked GEOrank session file")
        if self.path.exists():
            self.load()
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=".session-",
            suffix=".json",
            delete=False,
        )
        temp_path = Path(handle.name)
        try:
            os.chmod(temp_path, 0o600)
            with handle:
                json.dump({**payload, "_format": SESSION_FORMAT}, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            os.chmod(self.path, 0o600)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def clear(self) -> bool:
        if self.path.is_symlink():
            raise ClientError("Refusing to remove a symlinked GEOrank session file")
        if not self.path.exists():
            return False
        self.load()
        self.path.unlink()
        return True


def load_request_payload(json_file: str | None, json_stdin: bool) -> Any:
    if json_file and json_stdin:
        raise ClientError("Use only one of --json-file or --json-stdin")
    if json_stdin:
        raw = sys.stdin.read(MAX_REQUEST_BYTES + 1)
    elif json_file:
        path = Path(json_file).expanduser()
        if path.is_symlink():
            raise ClientError("Refusing to read a symlinked request body")
        try:
            file_stat = path.stat()
            if not stat.S_ISREG(file_stat.st_mode):
                raise ClientError("Request body path must be a regular file")
            if file_stat.st_size > MAX_REQUEST_BYTES:
                raise ClientError(f"Request body exceeds the {MAX_REQUEST_BYTES}-byte safety limit")
            raw = path.read_text(encoding="utf-8")
        except ClientError:
            raise
        except (OSError, UnicodeError) as exc:
            raise ClientError(f"Unable to read request body: {exc}") from exc
    else:
        return None
    if len(raw.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ClientError(f"Request body exceeds the {MAX_REQUEST_BYTES}-byte safety limit")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClientError(f"Request body is not valid JSON: {exc}") from exc


def emit(payload: Any, *, stream: Any = sys.stdout) -> None:
    print(json.dumps(redact(payload), ensure_ascii=False, indent=2), file=stream)


def require_token(token: str | None) -> str:
    if not token:
        raise ClientError("No GEOrank session found; run login or set GEORANK_TOKEN")
    return token


def resolve_runtime(args: argparse.Namespace) -> tuple[ApiClient, SessionStore, dict[str, Any], str | None]:
    store = SessionStore(Path(args.session_file))
    session = store.load()
    base_url = args.base_url or os.environ.get("GEORANK_BASE_URL") or session.get("base_url") or DEFAULT_BASE_URL
    client = ApiClient(base_url, args.timeout)
    token = os.environ.get("GEORANK_TOKEN") or session.get("access_token")
    return client, store, session, token


def get_current_user(client: ApiClient, token: str) -> dict[str, Any]:
    response = client.request("GET", "/api/auth/me", token=token)
    data = response.get("data")
    if not isinstance(data, dict):
        raise ClientError("GEOrank /api/auth/me returned an invalid response")
    return {**data, "request_id": response.get("request_id")}


def command_login(args: argparse.Namespace) -> int:
    client, store, _session, _token = resolve_runtime(args)
    password = os.environ.get(args.password_env)
    if not password:
        if not sys.stdin.isatty():
            raise ClientError(f"Set {args.password_env} or run login in an interactive terminal")
        password = getpass.getpass("GEOrank password: ")
    payload = build_login_payload(
        account=args.account,
        phone=args.phone,
        password=password,
        remember_me=not args.short_session,
    )
    login_response = client.request("POST", "/api/auth/login", payload=payload)
    data = login_response.get("data")
    if not isinstance(data, dict) or not data.get("access_token"):
        raise ClientError("GEOrank login response did not contain an access token")
    token = str(data["access_token"])
    user = get_current_user(client, token)
    store.save(
        {
            "base_url": client.base_url,
            "access_token": token,
            "user": {key: user.get(key) for key in ("id", "email", "username", "phone", "role")},
        }
    )
    emit(
        {
            "authenticated": True,
            "default_login_profile": "user",
            "detected_role": user.get("role"),
            "admin_capabilities_enabled": user.get("role") == "admin",
            "user": {key: user.get(key) for key in ("id", "email", "username", "phone", "role")},
            "session_file": str(store.path),
            "request_id": user.get("request_id") or login_response.get("request_id"),
        }
    )
    return 0


def command_logout(args: argparse.Namespace) -> int:
    _client, store, _session, _token = resolve_runtime(args)
    removed = store.clear()
    emit(
        {
            "logged_out": removed,
            "session_file": str(store.path),
            "environment_token_present": bool(os.environ.get("GEORANK_TOKEN")),
        }
    )
    return 0


def command_whoami(args: argparse.Namespace) -> int:
    client, _store, _session, token = resolve_runtime(args)
    user = get_current_user(client, require_token(token))
    emit({"access_level": "admin" if user.get("role") == "admin" else "user", "user": user})
    return 0


def command_capabilities(args: argparse.Namespace) -> int:
    client, _store, _session, token = resolve_runtime(args)
    public = ["companies.read", "content.read", "experts.read", "solutions.channels", "usage.policy"]
    if not token:
        emit({"access_level": "public", "capabilities": public})
        return 0
    user = get_current_user(client, token)
    capabilities = public + [
        "profile.manage",
        "companies.submit",
        "diagnostics.manage-own",
        "solutions.manage-own",
        "keywords.expand",
        "usage.read-own",
    ]
    access_level = "user"
    if user.get("role") == "admin":
        access_level = "admin"
        capabilities.append("admin.manage-platform")
    emit({"access_level": access_level, "detected_role": user.get("role"), "capabilities": capabilities})
    return 0


def command_call(args: argparse.Namespace) -> int:
    client, _store, _session, token = resolve_runtime(args)
    method = args.method.upper()
    path = normalize_api_path(args.path)
    payload = load_request_payload(args.json_file, args.json_stdin)
    clean_path = path.split("?", 1)[0]
    is_admin_path = clean_path == "/api/admin" or clean_path.startswith("/api/admin/")
    detected_role = None
    if is_admin_path:
        user = get_current_user(client, require_token(token))
        detected_role = str(user.get("role") or "")
    preflight = validate_execution(
        method,
        path,
        execute=args.execute,
        confirmation=args.confirm,
        detected_role=detected_role,
    )
    receipt = {
        "operation": f"{method} {path}",
        "base_url": client.base_url,
        "access_level": "admin" if detected_role == "admin" else ("user" if token else "public"),
        "payload": redact(payload),
        **preflight,
    }
    if method not in SAFE_METHODS and not args.execute:
        emit({**receipt, "status": "dry-run", "next_step": "Review the target and run again with --execute"})
        return 0
    response = client.request(method, path, token=token, payload=payload)
    emit(
        {
            **receipt,
            "status": "executed",
            "status_code": response.get("status_code"),
            "request_id": response.get("request_id"),
            "data": response.get("data"),
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Secure GEOrank API operator with ordinary-user login defaults and admin safety gates."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {client_version()}")
    parser.add_argument("--base-url", help="GEOrank origin; defaults to GEORANK_BASE_URL, session, or localhost")
    parser.add_argument("--session-file", default=str(default_session_file()), help="Private session JSON path")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Request timeout in seconds (1-300)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login", help="Log in with an ordinary-user flow, then detect the live role")
    identity = login.add_mutually_exclusive_group(required=True)
    identity.add_argument("--account", help="Username or email")
    identity.add_argument("--phone", help="Phone number")
    login.add_argument("--password-env", default="GEORANK_PASSWORD", help="Environment variable for the password")
    login.add_argument("--short-session", action="store_true", help="Request the backend short-lived token policy")
    login.set_defaults(handler=command_login)

    logout = subparsers.add_parser("logout", help="Remove the local session file")
    logout.set_defaults(handler=command_logout)

    whoami = subparsers.add_parser("whoami", help="Read /api/auth/me and show the detected role")
    whoami.set_defaults(handler=command_whoami)

    capabilities = subparsers.add_parser("capabilities", help="Show capabilities for the detected access level")
    capabilities.set_defaults(handler=command_capabilities)

    call = subparsers.add_parser("call", help="Preflight or execute one GEOrank API request")
    call.add_argument("method", choices=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
    call.add_argument("path", help="Relative /api path; query strings are allowed")
    body = call.add_mutually_exclusive_group()
    body.add_argument("--json-file", help="Read the JSON request body from a non-symlink file")
    body.add_argument("--json-stdin", action="store_true", help="Read the JSON request body from stdin")
    call.add_argument("--execute", action="store_true", help="Execute a non-read request after preflight")
    call.add_argument("--confirm", help="Exact administrator or deletion confirmation phrase")
    call.set_defaults(handler=command_call)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except ClientError as exc:
        emit({"ok": False, "error": str(exc)}, stream=sys.stderr)
        return 2
    except KeyboardInterrupt:
        emit({"ok": False, "error": "Interrupted"}, stream=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
