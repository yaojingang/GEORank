"""
公司官网入库规划服务
- 归一化用户输入 URL
- 从首页链接中提取一级候选页面
- 在 AI 不可用时按启发式选择关键页面
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Iterable
from urllib.parse import urlparse, urlunparse
import re


_ASSET_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".xml",
    ".json",
    ".txt",
    ".css",
    ".js",
)

_POSITIVE_KEYWORDS = {
    "about": 90,
    "about-us": 90,
    "company": 84,
    "team": 80,
    "leadership": 72,
    "founders": 68,
    "story": 64,
    "mission": 60,
    "platform": 58,
    "product": 56,
    "products": 56,
    "solution": 52,
    "solutions": 52,
    "technology": 48,
    "ai": 44,
    "overview": 42,
}

_NEGATIVE_KEYWORDS = {
    "login": -120,
    "signin": -120,
    "sign-in": -120,
    "signup": -120,
    "sign-up": -120,
    "register": -120,
    "privacy": -70,
    "terms": -70,
    "cookie": -70,
    "careers": -20,
    "career": -20,
    "blog": -18,
    "news": -14,
    "press": -12,
    "docs": -18,
}

_ROLE_PATTERNS = [
    ("about", ("about", "about-us", "company", "story", "mission", "who-we-are")),
    ("team", ("team", "leadership", "founders", "people")),
    ("product", ("product", "products", "platform", "solution", "solutions", "technology")),
]

_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain"}


def _validate_public_hostname(hostname: str) -> None:
    normalized = hostname.rstrip(".").lower()
    if (
        normalized in _BLOCKED_HOSTNAMES
        or normalized.endswith(".localhost")
        or normalized.endswith(".local")
        or normalized.endswith(".internal")
    ):
        raise ValueError("公司官网必须使用可公开访问的互联网地址")

    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("公司官网不能指向内网、回环或保留地址")


def normalize_company_url(raw_url: str) -> str:
    value = (raw_url or "").strip()
    if not value:
        raise ValueError("请输入公司官网地址")

    if value.startswith("//"):
        value = f"https:{value}"
    elif "://" not in value:
        value = f"https://{value}"

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("仅支持 http 或 https 网站地址")
    if not parsed.netloc:
        raise ValueError("请输入有效的公司官网地址")
    if parsed.username or parsed.password:
        raise ValueError("公司官网地址不能包含登录凭据")
    if not parsed.hostname:
        raise ValueError("请输入有效的公司官网地址")
    _validate_public_hostname(parsed.hostname)

    path = parsed.path or ""
    normalized_path = path.rstrip("/")
    if normalized_path == "":
        normalized_path = ""

    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            normalized_path,
            "",
            "",
            "",
        )
    )


def validate_public_crawl_url(raw_url: str) -> str:
    normalized_url = normalize_company_url(raw_url)
    parsed = urlparse(normalized_url)
    hostname = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        resolved = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"公司官网域名解析失败：{hostname}") from exc
    if not resolved:
        raise ValueError(f"公司官网域名没有可用地址：{hostname}")

    for family, _, _, _, sockaddr in resolved:
        if family not in {socket.AF_INET, socket.AF_INET6}:
            continue
        address = ipaddress.ip_address(sockaddr[0])
        if not address.is_global:
            raise ValueError("公司官网解析到了内网、回环或保留地址")
    return normalized_url


def _same_domain(left: str, right: str) -> bool:
    return urlparse(left).netloc.lower() == urlparse(right).netloc.lower()


def _path_depth(path: str) -> int:
    parts = [part for part in path.split("/") if part]
    return len(parts)


def _clean_anchor_title(title: str | None, href: str) -> str:
    text = re.sub(r"\s+", " ", (title or "").strip())
    if text:
        return text[:80]

    path = urlparse(href).path.strip("/")
    if not path:
        return "主页"
    return path.split("/")[-1][:80]


def build_candidate_links(base_url: str, anchors: Iterable[dict], *, limit: int = 12) -> list[dict]:
    normalized_base = normalize_company_url(base_url)
    seen: set[str] = set()
    items: list[dict] = []

    for anchor in anchors:
        try:
            href = normalize_company_url(anchor.get("url") or "")
        except ValueError:
            continue
        parsed = urlparse(href)

        if href in seen or href == normalized_base:
            continue
        if not _same_domain(normalized_base, href):
            continue
        if parsed.path.lower().endswith(_ASSET_EXTENSIONS):
            continue
        if parsed.query or parsed.fragment:
            continue
        if _path_depth(parsed.path) > 1:
            continue

        title = _clean_anchor_title(anchor.get("title"), href)
        items.append(
            {
                "url": href,
                "title": title,
                "path": parsed.path or "/",
            }
        )
        seen.add(href)
        if len(items) >= limit:
            break

    return items


def _classify_role(candidate: dict) -> str:
    haystack = f"{candidate.get('url', '')} {candidate.get('title', '')}".lower()
    for role, patterns in _ROLE_PATTERNS:
        if any(pattern in haystack for pattern in patterns):
            return role
    return "supporting"


def fallback_select_company_pages(
    base_url: str,
    homepage_title: str,
    candidate_links: list[dict],
    *,
    limit: int = 3,
) -> list[dict]:
    homepage = {
        "url": normalize_company_url(base_url),
        "title": (homepage_title or "主页").strip() or "主页",
        "role": "homepage",
        "reason": "主页通常包含公司定位、产品摘要与核心导航，是企业知识库的主入口。",
    }

    ranked: list[tuple[float, dict]] = []
    for candidate in candidate_links:
        haystack = f"{candidate.get('url', '')} {candidate.get('title', '')}".lower()
        score = 0.0
        for keyword, weight in _POSITIVE_KEYWORDS.items():
            if keyword in haystack:
                score += weight
        for keyword, weight in _NEGATIVE_KEYWORDS.items():
            if keyword in haystack:
                score += weight
        score -= _path_depth(candidate.get("path") or "/") * 4.0
        ranked.append((score, candidate))

    selected = [homepage]
    used = {homepage["url"]}
    for _, candidate in sorted(ranked, key=lambda item: item[0], reverse=True):
        if len(selected) >= limit:
            break
        if candidate["url"] in used:
            continue
        role = _classify_role(candidate)
        if role == "supporting" and len(selected) == 1 and candidate_links:
            # 仍允许补一个非典型高分页面，但优先 about/team/product。
            pass
        selected.append(
            {
                "url": candidate["url"],
                "title": candidate["title"],
                "role": role,
                "reason": {
                    "about": "该页面通常集中描述公司背景、愿景与服务范围，适合抽取企业介绍。",
                    "team": "该页面通常披露创始团队或管理层信息，适合补足信任与团队结构。",
                    "product": "该页面通常说明核心产品、解决方案和能力边界，适合抽取业务与技术信息。",
                }.get(role, "该页面与公司核心介绍高度相关，可补充主页未覆盖的信息。"),
            }
        )
        used.add(candidate["url"])

    return selected[:limit]
