"""
自定义首页运行时资产处理。

MVP 只发布静态 HTML/CSS/图片/字体等公开资源，并阻断上传包脚本在主站同源执行。
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import html as html_module
import io
import json
import os
import posixpath
import re
import shutil
import stat
import uuid
import zipfile
from pathlib import Path
from typing import Iterable


class HomepageAssetError(ValueError):
    """首页资产校验或处理失败。"""


@dataclass(frozen=True)
class HomepageAssetLimits:
    max_compressed_size: int = 20 * 1024 * 1024
    max_extracted_size: int = 80 * 1024 * 1024
    max_files: int = 500
    max_path_depth: int = 8


DEFAULT_LIMITS = HomepageAssetLimits()
ENTRY_PATH = "index.html"
ALLOWED_EXTENSIONS = {
    ".html",
    ".css",
    ".json",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
}
TEXT_EXTENSIONS = {".html", ".css", ".json", ".txt", ".svg"}
MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".ico": (b"\x00\x00\x01\x00", b"\x00\x00\x02\x00"),
    ".woff": (b"wOFF",),
    ".woff2": (b"wOF2",),
    ".ttf": (b"\x00\x01\x00\x00", b"true", b"typ1"),
    ".otf": (b"OTTO",),
}
SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.IGNORECASE | re.DOTALL)
SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*?/?>", re.IGNORECASE | re.DOTALL)
SCRIPT_LINE_INDENT_RE = re.compile(r"^[ \t]+(?=<script\b)", re.IGNORECASE | re.MULTILINE)
CSP_META_RE = re.compile(
    r"\s*<meta\b(?=[^>]*\bhttp-equiv\s*=\s*([\"']?)content-security-policy\1)[^>]*>",
    re.IGNORECASE,
)
EVENT_ATTR_RE = re.compile(
    r"\s+on[a-zA-Z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)
SRCDOC_ATTR_RE = re.compile(
    r"\s+srcdoc\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)
URL_ATTR_RE = re.compile(
    r"\s+(?P<attr>src|href|poster|action|formaction|xlink:href)\s*=\s*(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.IGNORECASE,
)
UNQUOTED_URL_ATTR_RE = re.compile(
    r"\s+(?P<attr>src|href|poster|action|formaction|xlink:href)\s*=\s*(?P<value>[^\s>]+)",
    re.IGNORECASE,
)
ASSET_ATTR_RE = re.compile(
    r"(?P<prefix>\b(?:src|href|poster)\s*=\s*)(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.IGNORECASE,
)
CSP_META = (
    '<meta http-equiv="Content-Security-Policy" '
    'content="script-src \'none\'; object-src \'none\'; base-uri \'self\'">'
)
CHARSET_META = '<meta charset="utf-8">'
ANALYTICS_BLOCK_START = "<!-- GEORANK_ANALYTICS_START -->"
ANALYTICS_BLOCK_END = "<!-- GEORANK_ANALYTICS_END -->"
OVERLAY_METADATA_PATH = ".georank-overlay.json"
ANALYTICS_BLOCK_RE = re.compile(
    rf"\s*{re.escape(ANALYTICS_BLOCK_START)}.*?{re.escape(ANALYTICS_BLOCK_END)}",
    re.IGNORECASE | re.DOTALL,
)
_ANALYTICS_UNSET = object()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def homepage_root() -> Path:
    return Path(os.environ.get("GEORANK_HOMEPAGE_ROOT", "/app/runtime/homepages")).expanduser()


def source_release_path(root: Path, release_id: str) -> Path:
    return root / "releases" / release_id / "source"


def public_release_path(root: Path, release_id: str) -> Path:
    return root / "public" / "releases" / release_id


def public_active_path(root: Path) -> Path:
    return root / "public" / "active"


def public_overlay_root(root: Path) -> Path:
    return root / "public" / "active-overlays"


def _ensure_release_id(release_id: str) -> str:
    normalized = str(release_id or "").strip()
    if not normalized or "/" in normalized or "\\" in normalized or normalized in {".", ".."}:
        raise HomepageAssetError("首页版本 ID 不合法")
    return normalized


def _is_ignored_path(path: str) -> bool:
    parts = [part for part in path.split("/") if part]
    return any(part == "__MACOSX" or part == ".DS_Store" for part in parts)


def _normalize_zip_member_name(raw_name: str) -> str | None:
    name = str(raw_name or "").replace("\\", "/").strip()
    if not name or name.endswith("/"):
        return None
    if _is_ignored_path(name):
        return None
    if name.startswith("/") or name.startswith("~"):
        raise HomepageAssetError("压缩包不能包含绝对路径")
    normalized = posixpath.normpath(name)
    if normalized in {"", "."}:
        return None
    if normalized.startswith("../") or normalized == ".." or "/../" in f"/{normalized}/":
        raise HomepageAssetError("压缩包不能包含目录穿越路径")
    return normalized


def _strip_common_root(names: list[str]) -> dict[str, str]:
    if ENTRY_PATH in names:
        return {name: name for name in names}
    roots = {name.split("/", 1)[0] for name in names if "/" in name}
    if len(roots) != 1:
        return {name: name for name in names}
    root = next(iter(roots))
    stripped = {
        name: name.split("/", 1)[1]
        for name in names
        if name.startswith(f"{root}/") and name.split("/", 1)[1]
    }
    return stripped if ENTRY_PATH in stripped.values() else {name: name for name in names}


def _validate_public_path(path: str, limits: HomepageAssetLimits) -> None:
    parts = [part for part in path.split("/") if part]
    if len(parts) > limits.max_path_depth:
        raise HomepageAssetError("文件路径层级过深")
    if any(part in {"", ".", ".."} for part in parts):
        raise HomepageAssetError("文件路径不合法")
    suffix = Path(path).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HomepageAssetError(f"不支持的首页文件类型：{suffix or '无扩展名'}")
    if suffix == ".html" and path != ENTRY_PATH:
        raise HomepageAssetError("首页包只能包含一个 index.html 入口文件")


def _validate_asset_content(path: str, data: bytes) -> None:
    suffix = Path(path).suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HomepageAssetError(f"{path} 内容不是有效的 UTF-8 文本") from exc
        return

    if suffix == ".webp":
        if not (len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"):
            raise HomepageAssetError(f"{path} 内容与文件扩展名不匹配")
        return

    signatures = MAGIC_SIGNATURES.get(suffix)
    if signatures and not any(data.startswith(signature) for signature in signatures):
        raise HomepageAssetError(f"{path} 内容与文件扩展名不匹配")


def _render_public_homepage_file(path: str, data: bytes) -> bytes:
    if path == ENTRY_PATH:
        normalized = normalize_homepage_html(data.decode("utf-8", errors="replace"))
        return normalized.encode("utf-8")
    if Path(path).suffix.lower() == ".svg":
        sanitized = sanitize_markup_scripts(data.decode("utf-8", errors="replace"))
        return sanitized.encode("utf-8")
    return data


def _prepare_release_dirs(root: Path, release_id: str) -> tuple[Path, Path]:
    source_dir = source_release_path(root, release_id)
    public_dir = public_release_path(root, release_id)
    if source_dir.exists() or public_dir.exists():
        raise HomepageAssetError("首页版本目录已存在，请重新生成版本")
    source_dir.parent.mkdir(parents=True, exist_ok=True)
    public_dir.parent.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True)
    public_dir.mkdir(parents=True)
    return source_dir, public_dir


def _clean_release_dirs(root: Path, release_id: str) -> None:
    shutil.rmtree(root / "releases" / release_id, ignore_errors=True)
    shutil.rmtree(public_release_path(root, release_id), ignore_errors=True)


def _looks_like_local_asset(value: str) -> bool:
    value = value.strip()
    if not value or value.startswith("#"):
        return False
    lowered = value.lower()
    if lowered.startswith(("http://", "https://", "//", "mailto:", "tel:", "data:", "blob:", "javascript:")):
        return False
    path = re.split(r"[?#]", value, maxsplit=1)[0]
    if not path or path.endswith("/"):
        return False
    asset_path = path.lstrip("/")
    suffix = Path(asset_path).suffix.lower()
    return suffix in ALLOWED_EXTENSIONS and suffix != ".html"


def _rewrite_asset_value(value: str, base_path: str) -> str:
    value = value.strip()
    path_part = re.split(r"([?#])", value, maxsplit=1)
    asset_path = path_part[0].replace("\\", "/")
    suffix = "".join(path_part[1:])
    if asset_path.startswith("./"):
        asset_path = asset_path[2:]
    asset_path = asset_path.lstrip("/")
    normalized = posixpath.normpath(asset_path)
    if normalized.startswith("../") or normalized == "..":
        return value
    return f"{base_path.rstrip('/')}/{normalized}{suffix}"


def normalize_homepage_html(html: str, *, base_path: str = "/_custom_homepage/active") -> str:
    cleaned = sanitize_markup_scripts(html or "")

    def replace_asset(match: re.Match) -> str:
        value = match.group("value")
        if not _looks_like_local_asset(value):
            return match.group(0)
        rewritten = _rewrite_asset_value(value, base_path)
        return f"{match.group('prefix')}{match.group('quote')}{rewritten}{match.group('quote')}"

    cleaned = ASSET_ATTR_RE.sub(replace_asset, cleaned)
    if not re.search(r"<meta\b[^>]*charset\s*=", cleaned, re.IGNORECASE):
        if re.search(r"<head[^>]*>", cleaned, re.IGNORECASE):
            cleaned = re.sub(r"<head[^>]*>", lambda m: f"{m.group(0)}\n    {CHARSET_META}", cleaned, count=1, flags=re.IGNORECASE)
        else:
            cleaned = f"{CHARSET_META}\n{cleaned}"
    if re.search(r"</head\s*>", cleaned, re.IGNORECASE):
        cleaned = re.sub(r"</head\s*>", f"    {CSP_META}\n</head>", cleaned, count=1, flags=re.IGNORECASE)
    elif re.search(r"<head[^>]*>", cleaned, re.IGNORECASE):
        cleaned = re.sub(r"<head[^>]*>", lambda m: f"{m.group(0)}\n    {CSP_META}", cleaned, count=1, flags=re.IGNORECASE)
    else:
        cleaned = f"{CSP_META}\n{cleaned}"
    return cleaned


def _is_dangerous_url(value: str) -> bool:
    decoded = html_module.unescape(value or "")
    compact = re.sub(r"[\x00-\x20]+", "", decoded).lower()
    return compact.startswith(("javascript:", "vbscript:"))


def _remove_dangerous_url_attr(match: re.Match) -> str:
    value = match.groupdict().get("value") or ""
    return "" if _is_dangerous_url(value) else match.group(0)


def sanitize_markup_scripts(markup: str) -> str:
    cleaned = SCRIPT_LINE_INDENT_RE.sub("", markup or "")
    cleaned = SCRIPT_BLOCK_RE.sub("", cleaned)
    cleaned = SCRIPT_TAG_RE.sub("", cleaned)
    cleaned = CSP_META_RE.sub("", cleaned)
    cleaned = EVENT_ATTR_RE.sub("", cleaned)
    cleaned = SRCDOC_ATTR_RE.sub("", cleaned)
    cleaned = URL_ATTR_RE.sub(_remove_dangerous_url_attr, cleaned)
    return UNQUOTED_URL_ATTR_RE.sub(_remove_dangerous_url_attr, cleaned)


def inject_analytics_code(html: str, analytics_code: str | None) -> str:
    """Inject trusted admin analytics snippet into a custom homepage HTML file.

    Uploaded homepage packages are still sanitized separately. This function is only
    for the platform-level analytics snippet saved by an administrator.
    """
    cleaned = ANALYTICS_BLOCK_RE.sub("", html or "")
    code = (analytics_code or "").strip()
    if not code:
        if CSP_META_RE.search(cleaned):
            return cleaned
        if re.search(r"</head\s*>", cleaned, re.IGNORECASE):
            return re.sub(r"</head\s*>", f"    {CSP_META}\n</head>", cleaned, count=1, flags=re.IGNORECASE)
        if re.search(r"<head[^>]*>", cleaned, re.IGNORECASE):
            return re.sub(r"<head[^>]*>", lambda m: f"{m.group(0)}\n    {CSP_META}", cleaned, count=1, flags=re.IGNORECASE)
        return f"{CSP_META}\n{cleaned}"
    # The original custom-homepage CSP blocks scripts by design. Admin analytics is
    # a trusted platform setting, while uploaded scripts have already been stripped.
    cleaned = CSP_META_RE.sub("", cleaned)
    block = f"\n{ANALYTICS_BLOCK_START}\n{code}\n{ANALYTICS_BLOCK_END}\n"
    if re.search(r"</head\s*>", cleaned, re.IGNORECASE):
        return re.sub(r"</head\s*>", f"{block}</head>", cleaned, count=1, flags=re.IGNORECASE)
    if re.search(r"</body\s*>", cleaned, re.IGNORECASE):
        return re.sub(r"</body\s*>", f"{block}</body>", cleaned, count=1, flags=re.IGNORECASE)
    return f"{cleaned}{block}"


@contextmanager
def _active_homepage_lock(root: Path):
    public_root = Path(root) / "public"
    if public_root.is_symlink():
        raise HomepageAssetError("首页 public 根目录不能是符号链接")
    public_root.mkdir(parents=True, exist_ok=True)
    if not public_root.is_dir():
        raise HomepageAssetError("首页 public 根目录不可用")
    lock_path = public_root / ".active.lock"
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _validated_public_directory(root: Path, name: str, *, create: bool = False) -> Path:
    public_root = Path(root) / "public"
    if public_root.is_symlink() or not public_root.is_dir():
        raise HomepageAssetError("首页 public 根目录不安全")
    directory = public_root / name
    if directory.is_symlink():
        raise HomepageAssetError(f"首页 {name} 目录不能是符号链接")
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir():
        raise HomepageAssetError(f"首页 {name} 目录不存在")
    return directory.resolve()


def _active_target_parts(root: Path) -> tuple[str, str] | None:
    active_path = public_active_path(root)
    if not active_path.is_symlink():
        if active_path.exists():
            raise HomepageAssetError("当前首页指针必须是符号链接")
        return None
    target = active_path.readlink()
    if target.is_absolute() or len(target.parts) != 2:
        raise HomepageAssetError("当前首页指针目标不安全")
    category, release_id = target.parts
    if category not in {"releases", "active-overlays"}:
        raise HomepageAssetError("当前首页指针目标不安全")
    return category, _ensure_release_id(release_id)


def _resolve_active_tree(root: Path) -> Path | None:
    target_parts = _active_target_parts(root)
    if target_parts is None:
        return None
    category, release_id = target_parts
    allowed_root = _validated_public_directory(root, category)
    candidate = (allowed_root / release_id).resolve()
    try:
        candidate.relative_to(allowed_root)
    except ValueError as exc:
        raise HomepageAssetError("当前首页指针目标越出允许目录") from exc
    if not candidate.is_dir():
        raise HomepageAssetError("当前首页指针目标不存在")
    return candidate


def _overlay_source_release_id(overlay_tree: Path) -> str:
    metadata_path = overlay_tree / OVERLAY_METADATA_PATH
    if metadata_path.is_symlink() or not metadata_path.is_file():
        raise HomepageAssetError("当前 active overlay 缺少来源版本信息")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HomepageAssetError("当前 active overlay 来源版本信息无效") from exc
    return _ensure_release_id(str(metadata.get("source_release_id") or ""))


def _current_overlay_path(root: Path) -> Path | None:
    target_parts = _active_target_parts(root)
    if target_parts is None or target_parts[0] != "active-overlays":
        return None
    overlay_root = _validated_public_directory(root, "active-overlays")
    candidate = (overlay_root / target_parts[1]).resolve()
    try:
        candidate.relative_to(overlay_root)
    except ValueError as exc:
        raise HomepageAssetError("当前首页 overlay 越出允许目录") from exc
    return candidate if candidate.is_dir() else None


def _assert_symlink_free_tree(root: Path) -> None:
    if root.is_symlink():
        raise HomepageAssetError("首页运行时目录不能包含符号链接")
    for current_root, directories, files in os.walk(root, followlinks=False):
        current = Path(current_root)
        for name in [*directories, *files]:
            if (current / name).is_symlink():
                raise HomepageAssetError("首页运行时目录不能包含符号链接")


def _replace_active_pointer(root: Path, target: Path) -> Path:
    if target.is_absolute() or len(target.parts) != 2:
        raise HomepageAssetError("首页指针目标不安全")
    active_path = public_active_path(root)
    active_path.parent.mkdir(parents=True, exist_ok=True)
    if active_path.exists() and not active_path.is_symlink():
        raise HomepageAssetError("当前首页指针必须是符号链接")
    pending_pointer = active_path.parent / f".active-{uuid.uuid4().hex}"
    try:
        os.symlink(target.as_posix(), pending_pointer)
        os.replace(pending_pointer, active_path)
    except Exception:
        _remove_path(pending_pointer)
        raise
    return active_path


def _remove_stale_overlay(path: Path | None) -> None:
    if path is None:
        return
    try:
        _remove_path(path)
    except OSError:
        # The active pointer has already committed. A stale directory is safer
        # than rolling back the new pointer into a dangling symlink.
        return


def _publish_active_overlay(
    root: Path,
    source_tree: Path,
    next_html: str,
    *,
    source_release_id: str,
    cleanup_previous_overlay: bool = True,
) -> Path:
    source_release_id = _ensure_release_id(source_release_id)
    _assert_symlink_free_tree(source_tree)
    previous_overlay = _current_overlay_path(root)
    overlay_root = _validated_public_directory(root, "active-overlays", create=True)
    overlay_id = uuid.uuid4().hex
    pending_overlay = overlay_root / f".pending-{overlay_id}"
    published_overlay = overlay_root / overlay_id
    try:
        shutil.copytree(source_tree, pending_overlay)
        (pending_overlay / ENTRY_PATH).write_text(next_html, encoding="utf-8")
        (pending_overlay / OVERLAY_METADATA_PATH).write_text(
            json.dumps({"source_release_id": source_release_id}),
            encoding="utf-8",
        )
        os.replace(pending_overlay, published_overlay)
        active_path = _replace_active_pointer(root, Path("active-overlays") / overlay_id)
    except Exception:
        _remove_path(pending_overlay)
        _remove_path(published_overlay)
        raise
    if cleanup_previous_overlay and previous_overlay != published_overlay:
        _remove_stale_overlay(previous_overlay)
    return active_path


def apply_analytics_to_active_homepage(
    root: Path,
    analytics_code: str | None,
    *,
    cleanup_previous_overlay: bool = True,
) -> bool:
    """Publish analytics through an isolated overlay, leaving releases immutable."""
    root = Path(root)
    with _active_homepage_lock(root):
        target_parts = _active_target_parts(root)
        active_tree = _resolve_active_tree(root)
        if active_tree is None:
            return False
        if target_parts is None:
            return False
        source_release_id = (
            target_parts[1]
            if target_parts[0] == "releases"
            else _overlay_source_release_id(active_tree)
        )
        index_path = active_tree / ENTRY_PATH
        if not index_path.is_file() or index_path.is_symlink():
            return False
        current = index_path.read_text(encoding="utf-8")
        next_html = inject_analytics_code(current, analytics_code)
        if next_html == current:
            return False
        _publish_active_overlay(
            root,
            active_tree,
            next_html,
            source_release_id=source_release_id,
            cleanup_previous_overlay=cleanup_previous_overlay,
        )
        return True


def _write_manifest(root: Path, release_id: str, manifest: dict) -> None:
    manifest_path = root / "releases" / release_id / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _file_entries(public_dir: Path) -> list[dict]:
    entries = []
    for path in sorted(public_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(public_dir).as_posix()
        entries.append(
            {
                "path": rel,
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return entries


def _build_manifest(
    root: Path,
    release_id: str,
    *,
    title: str,
    source_type: str,
    compressed_size: int,
    extracted_size: int,
    sha256: str | None,
) -> dict:
    public_dir = public_release_path(root, release_id)
    files = _file_entries(public_dir)
    manifest = {
        "id": release_id,
        "title": title,
        "source_type": source_type,
        "entry_path": ENTRY_PATH,
        "storage_path": str(root / "releases" / release_id),
        "public_path": str(public_dir),
        "file_count": len(files),
        "compressed_size": compressed_size,
        "extracted_size": extracted_size,
        "sha256": sha256,
        "files": files,
        "created_at": _utc_now_iso(),
    }
    _write_manifest(root, release_id, manifest)
    return manifest


def build_single_html_release(
    root: Path,
    release_id: str,
    title: str,
    html: str,
    *,
    limits: HomepageAssetLimits = DEFAULT_LIMITS,
) -> dict:
    release_id = _ensure_release_id(release_id)
    root = Path(root)
    html_bytes = (html or "").encode("utf-8")
    if not html_bytes.strip():
        raise HomepageAssetError("请填写首页 HTML")
    if len(html_bytes) > limits.max_extracted_size:
        raise HomepageAssetError("HTML 内容超过大小限制")

    source_dir, public_dir = _prepare_release_dirs(root, release_id)
    try:
        (source_dir / ENTRY_PATH).write_bytes(html_bytes)
        normalized = normalize_homepage_html(html)
        (public_dir / ENTRY_PATH).write_text(normalized, encoding="utf-8")
        return _build_manifest(
            root,
            release_id,
            title=title,
            source_type="single_html",
            compressed_size=len(html_bytes),
            extracted_size=len(html_bytes),
            sha256=hashlib.sha256(html_bytes).hexdigest(),
        )
    except Exception:
        _clean_release_dirs(root, release_id)
        raise


def _validate_zip_infos(infos: Iterable[zipfile.ZipInfo], limits: HomepageAssetLimits) -> list[tuple[zipfile.ZipInfo, str]]:
    validated: list[tuple[zipfile.ZipInfo, str]] = []
    total_size = 0
    raw_names: list[str] = []
    pending: list[tuple[zipfile.ZipInfo, str]] = []
    for info in infos:
        normalized = _normalize_zip_member_name(info.filename)
        if not normalized:
            continue
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise HomepageAssetError("压缩包不能包含符号链接")
        raw_names.append(normalized)
        pending.append((info, normalized))

    name_map = _strip_common_root(raw_names)
    for info, raw_name in pending:
        public_name = name_map.get(raw_name)
        if not public_name:
            continue
        _validate_public_path(public_name, limits)
        total_size += info.file_size
        if total_size > limits.max_extracted_size:
            raise HomepageAssetError("解压后文件总大小超过限制")
        validated.append((info, public_name))

    if len(validated) > limits.max_files:
        raise HomepageAssetError("首页文件数量超过限制")
    if not any(public_name == ENTRY_PATH for _, public_name in validated):
        raise HomepageAssetError("首页包必须包含 index.html")
    return validated


def build_zip_homepage_release(
    root: Path,
    release_id: str,
    title: str,
    filename: str,
    content: bytes,
    *,
    limits: HomepageAssetLimits = DEFAULT_LIMITS,
) -> dict:
    release_id = _ensure_release_id(release_id)
    root = Path(root)
    payload = content or b""
    if not str(filename or "").lower().endswith(".zip"):
        raise HomepageAssetError("请上传 .zip 首页包")
    if not payload:
        raise HomepageAssetError("上传包为空")
    if len(payload) > limits.max_compressed_size:
        raise HomepageAssetError("压缩包超过大小限制")

    source_dir, public_dir = _prepare_release_dirs(root, release_id)
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            validated = _validate_zip_infos(archive.infolist(), limits)
            extracted_size = sum(info.file_size for info, _ in validated)
            for info, public_name in validated:
                _validate_public_path(public_name, limits)
                source_target = source_dir / public_name
                public_target = public_dir / public_name
                source_target.parent.mkdir(parents=True, exist_ok=True)
                public_target.parent.mkdir(parents=True, exist_ok=True)
                data = archive.read(info)
                _validate_asset_content(public_name, data)
                source_target.write_bytes(data)
                public_target.write_bytes(_render_public_homepage_file(public_name, data))
    except zipfile.BadZipFile as exc:
        _clean_release_dirs(root, release_id)
        raise HomepageAssetError("首页包不是有效的 zip 文件") from exc
    except Exception:
        _clean_release_dirs(root, release_id)
        raise

    return _build_manifest(
        root,
        release_id,
        title=title,
        source_type="zip_package",
        compressed_size=len(payload),
        extracted_size=extracted_size,
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def _validated_source_releases_root(root: Path) -> Path:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise HomepageAssetError("首页存储根目录不安全")
    releases_root = root / "releases"
    if releases_root.is_symlink():
        raise HomepageAssetError("首页 source releases 目录不能是符号链接")
    if not releases_root.is_dir():
        raise HomepageAssetError("首页 source releases 目录不存在")
    resolved_root = root.resolve()
    resolved_releases = releases_root.resolve()
    try:
        resolved_releases.relative_to(resolved_root)
    except ValueError as exc:
        raise HomepageAssetError("首页 source releases 目录越出存储根目录") from exc
    return resolved_releases


@dataclass
class HomepageReleaseDeletion:
    root: Path
    release_id: str
    source_quarantine_name: str
    public_quarantine_name: str
    finalized: bool = False

    def commit(self) -> None:
        if self.finalized:
            return
        try:
            with _active_homepage_lock(self.root):
                source_root = _validated_source_releases_root(self.root)
                public_root = _validated_public_directory(self.root, "releases")
                for quarantine in (
                    source_root / self.source_quarantine_name,
                    public_root / self.public_quarantine_name,
                ):
                    try:
                        _remove_path(quarantine)
                    except OSError:
                        # The database row is already committed. A quarantine
                        # cleanup failure must not turn that success into a 500.
                        continue
        except (HomepageAssetError, OSError):
            # Root validation and lock failures have the same post-commit
            # cleanup semantics. The unpredictable quarantine remains inert.
            pass
        finally:
            self.finalized = True

    def rollback(self) -> None:
        if self.finalized:
            return
        with _active_homepage_lock(self.root):
            source_root = _validated_source_releases_root(self.root)
            public_root = _validated_public_directory(self.root, "releases")
            source_original = source_root / self.release_id
            public_original = public_root / self.release_id
            source_quarantine = source_root / self.source_quarantine_name
            public_quarantine = public_root / self.public_quarantine_name
            if source_original.exists() or public_original.exists():
                raise HomepageAssetError("首页版本回滚目标已存在")
            os.replace(source_quarantine, source_original)
            try:
                os.replace(public_quarantine, public_original)
            except Exception:
                os.replace(source_original, source_quarantine)
                raise
            self.finalized = True


def stage_homepage_release_deletion(root: Path, release_id: str) -> HomepageReleaseDeletion:
    root = Path(root)
    release_id = _ensure_release_id(release_id)
    with _active_homepage_lock(root):
        source_root = _validated_source_releases_root(root)
        public_root = _validated_public_directory(root, "releases")
        active_target = _active_target_parts(root)
        if active_target is not None:
            active_category, active_id = active_target
            if active_category == "releases" and active_id == release_id:
                raise HomepageAssetError("当前 active 指针指向该首页版本，不能删除")
            if active_category == "active-overlays":
                active_tree = _resolve_active_tree(root)
                if active_tree is None or _overlay_source_release_id(active_tree) == release_id:
                    raise HomepageAssetError("当前 active overlay 来源于该首页版本，不能删除")
        source_target = source_root / release_id
        public_target = public_root / release_id
        for target in (source_target, public_target):
            if target.is_symlink() or not target.is_dir():
                raise HomepageAssetError("首页版本删除目标不是受控目录")
        manifest_path = source_target / "manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise HomepageAssetError("首页版本删除目标缺少受控 manifest")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise HomepageAssetError("首页版本 manifest 无法验证") from exc
        if str(manifest.get("id") or "") != release_id:
            raise HomepageAssetError("首页版本 manifest ID 不匹配")

        quarantine_token = uuid.uuid4().hex
        source_quarantine_name = f".delete-{release_id}-{quarantine_token}"
        public_quarantine_name = f".delete-{release_id}-{quarantine_token}"
        source_quarantine = source_root / source_quarantine_name
        public_quarantine = public_root / public_quarantine_name
        os.replace(source_target, source_quarantine)
        try:
            os.replace(public_target, public_quarantine)
        except Exception:
            os.replace(source_quarantine, source_target)
            raise
        return HomepageReleaseDeletion(
            root=root,
            release_id=release_id,
            source_quarantine_name=source_quarantine_name,
            public_quarantine_name=public_quarantine_name,
        )


def activate_homepage_release(
    root: Path,
    release_id: str,
    *,
    analytics_code: str | None | object = _ANALYTICS_UNSET,
    cleanup_previous_overlay: bool = True,
) -> Path:
    release_id = _ensure_release_id(release_id)
    root = Path(root)
    with _active_homepage_lock(root):
        release_public = _validated_public_directory(root, "releases") / release_id
        if not (release_public / ENTRY_PATH).is_file():
            raise HomepageAssetError("首页版本缺少可发布入口文件")
        _assert_symlink_free_tree(release_public)
        try:
            previous_overlay = _current_overlay_path(root)
        except HomepageAssetError:
            previous_overlay = None
        if analytics_code is not _ANALYTICS_UNSET:
            current = (release_public / ENTRY_PATH).read_text(encoding="utf-8")
            next_html = inject_analytics_code(current, analytics_code)
            if next_html != current:
                return _publish_active_overlay(
                    root,
                    release_public,
                    next_html,
                    source_release_id=release_id,
                    cleanup_previous_overlay=cleanup_previous_overlay,
                )
        active_path = _replace_active_pointer(root, Path("releases") / release_id)
        if cleanup_previous_overlay:
            _remove_stale_overlay(previous_overlay)
        return active_path


def reset_active_homepage(root: Path, *, cleanup_previous_overlay: bool = True) -> None:
    root = Path(root)
    with _active_homepage_lock(root):
        try:
            previous_overlay = _current_overlay_path(root)
        except HomepageAssetError:
            previous_overlay = None
        _remove_path(public_active_path(root))
        if cleanup_previous_overlay:
            _remove_stale_overlay(previous_overlay)


def snapshot_active_homepage_target(root: Path) -> Path | None:
    root = Path(root)
    with _active_homepage_lock(root):
        target_parts = _active_target_parts(root)
        if target_parts is None:
            return None
        _resolve_active_tree(root)
        return Path(*target_parts)


def cleanup_inactive_homepage_overlay(root: Path, target: Path | None) -> None:
    if target is None or len(target.parts) != 2 or target.parts[0] != "active-overlays":
        return
    root = Path(root)
    with _active_homepage_lock(root):
        current_parts = _active_target_parts(root)
        if current_parts == target.parts:
            return
        overlay_root = _validated_public_directory(root, "active-overlays")
        stale_overlay = (overlay_root / _ensure_release_id(target.parts[1])).resolve()
        try:
            stale_overlay.relative_to(overlay_root)
        except ValueError as exc:
            raise HomepageAssetError("待清理 overlay 越出允许目录") from exc
        _remove_stale_overlay(stale_overlay)


def restore_active_homepage_target(root: Path, target: Path | None) -> None:
    root = Path(root)
    with _active_homepage_lock(root):
        current_parts = _active_target_parts(root)
        current_target = Path(*current_parts) if current_parts is not None else None
        current_overlay = _current_overlay_path(root)
        if target is None:
            _remove_path(public_active_path(root))
        else:
            if target.is_absolute() or len(target.parts) != 2:
                raise HomepageAssetError("待恢复首页指针目标不安全")
            category, release_id = target.parts
            if category not in {"releases", "active-overlays"}:
                raise HomepageAssetError("待恢复首页指针目标不安全")
            allowed_root = _validated_public_directory(root, category)
            restored_tree = (allowed_root / _ensure_release_id(release_id)).resolve()
            try:
                restored_tree.relative_to(allowed_root)
            except ValueError as exc:
                raise HomepageAssetError("待恢复首页指针越出允许目录") from exc
            if not (restored_tree / ENTRY_PATH).is_file():
                raise HomepageAssetError("待恢复首页版本缺少入口文件")
            _assert_symlink_free_tree(restored_tree)
            _replace_active_pointer(root, target)
        if current_target != target:
            _remove_stale_overlay(current_overlay)
