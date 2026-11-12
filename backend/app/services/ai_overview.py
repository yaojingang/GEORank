"""
Google AI Overview 证据源（GoAnyAPI）

现有诊断用 LLM 生成「AI 会怎么回答这个问题」，属于模拟回答；
这里补一条真实证据：直接取 Google AI Overview 的正文与引用链接，
用来判断目标品牌/域名有没有被 AI 概览引用、引用在第几位。

设计要点：
- 可选能力，GOANYAPI_API_KEY 未配置时抛 AIOverviewNotConfiguredError，
  调用方按「证据源未启用」降级，不影响原有诊断。
- 复用 provider_url_security 的出站校验与连接固定，避免把 Key 发到内网。
- 失败分类：402 余额不足/401 鉴权失败属于不可重试，429/502/504/网络错误可重试。
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.core.config import settings
from app.services.provider_url_security import (
    build_provider_api_url,
    build_provider_http_client,
)

ENDPOINT_PATH = "/api/v1/google-ai-overview"
DEFAULT_BASE_URL = "https://api.goanyapi.com"

# 这些查询参数只影响来源追踪，不影响被引用的页面身份，去重时丢弃。
TRACKING_QUERY_KEYS = {
    "gclid",
    "fbclid",
    "msclkid",
    "yclid",
    "ref",
    "referrer",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class AIOverviewNotConfiguredError(ValueError):
    """未配置 GoAnyAPI Key，AI Overview 证据源不可用。"""


class AIOverviewRequestError(RuntimeError):
    """调用 GoAnyAPI 失败，用 retryable 区分能否重试。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def is_configured() -> bool:
    """AI Overview 证据源是否已启用。"""
    return bool((settings.GOANYAPI_API_KEY or "").strip())


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def normalize_source_url(url: str) -> str:
    """归一化引用链接，用于跨 results / serp_features 去重。"""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        return url.strip()
    # www 与非 www 视为同一来源，否则同一页面会因收录差异被算成两条引用。
    host = host.removeprefix("www.")
    netloc = host if parts.port is None else f"{host}:{parts.port}"
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in TRACKING_QUERY_KEYS and not key.lower().startswith("utm_")
        ]
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower() or "https", netloc, path, query, ""))


def host_of(url: str) -> str:
    return (urlsplit(url.strip()).hostname or "").lower().rstrip(".")


def extract_answer(content: dict[str, Any] | None) -> str:
    """拼接 AI Overview 的回答正文（可能有多段）。"""
    paragraphs: list[str] = []
    for item in (content or {}).get("results") or []:
        if isinstance(item, dict):
            text = _text(item.get("text"))
            if text:
                paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_citations(content: dict[str, Any] | None) -> list[dict[str, Any]]:
    """提取引用来源，按归一化 URL 去重并保留首次出现顺序。"""
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for bucket in ("results", "serp_features"):
        for item in (content or {}).get(bucket) or []:
            if not isinstance(item, dict):
                continue
            for link in item.get("links") or []:
                if not isinstance(link, dict):
                    continue
                url = _text(link.get("url"))
                if not url:
                    continue
                key = normalize_source_url(url)
                if key in seen:
                    continue
                seen.add(key)
                citations.append(
                    {
                        "rank": len(citations) + 1,
                        "title": _text(link.get("title")),
                        "url": url,
                        "host": host_of(url),
                    }
                )
    return citations


def summarize(payload: dict[str, Any] | None, *, query: str = "") -> dict[str, Any]:
    """把 GoAnyAPI 原始响应压成诊断可用的结构。"""
    body = payload or {}
    data = body.get("data") or {}
    result = data.get("result") or {}
    content = result.get("content") or {}
    parameters = content.get("search_parameters") or {}
    available = parameters.get("feature_available")
    if available is None:
        # 老响应没有 feature_available 时，用正文是否存在判断。
        available = bool(content.get("results"))
    return {
        "query": _text(data.get("query")) or query,
        "available": bool(available),
        "answer": extract_answer(content),
        "citations": extract_citations(content),
        "country": _text(parameters.get("country")),
        "language": _text(parameters.get("language")),
        "device": _text(parameters.get("device")),
        "cost_credits": data.get("costCredits"),
        "remaining_credits": data.get("remainingCredits"),
    }


def brand_visibility(
    citations: Sequence[dict[str, Any]],
    brand: str,
    *,
    domains: Iterable[str] = (),
) -> dict[str, Any]:
    """判断品牌/域名是否被引用，并给出引用位次与占比。

    domains 优先匹配（更可靠），其次才退化为引用标题里包含品牌名。
    """
    brand_key = (brand or "").strip().lower()
    domain_keys = [
        item.strip().lower().lstrip(".").removeprefix("www.")
        for item in domains
        if item and item.strip()
    ]
    total = len(citations)

    for item in citations:
        host = (item.get("host") or host_of(str(item.get("url") or ""))).removeprefix("www.")
        for domain in domain_keys:
            if domain and (host == domain or host.endswith(f".{domain}")):
                return {
                    "cited": True,
                    "matched_by": "domain",
                    "position": item.get("rank"),
                    "url": item.get("url"),
                    "title": item.get("title"),
                    "citation_count": total,
                    "share": round(1 / total, 4) if total else 0.0,
                }

    if brand_key:
        for item in citations:
            if brand_key in (item.get("title") or "").lower():
                return {
                    "cited": True,
                    "matched_by": "title",
                    "position": item.get("rank"),
                    "url": item.get("url"),
                    "title": item.get("title"),
                    "citation_count": total,
                    "share": round(1 / total, 4) if total else 0.0,
                }

    return {
        "cited": False,
        "matched_by": None,
        "position": None,
        "url": None,
        "title": None,
        "citation_count": total,
        "share": 0.0,
    }


def _build_payload(
    query: str,
    *,
    country: str | None,
    language: str | None,
    device: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"query": query.strip(), "output": "json"}
    if country:
        payload["country"] = country.strip().lower()
    if language:
        payload["language"] = language.strip()
    if device:
        payload["device"] = device.strip().lower()
    return payload


async def fetch_ai_overview(
    query: str,
    *,
    country: str | None = None,
    language: str | None = None,
    device: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """取一次真实 AI Overview：正文 + 引用来源。

    单次约 3 credits（约 $0.003），调用方需要自行控制频率。
    """
    if not query or not query.strip():
        raise ValueError("AI Overview 查询词不能为空")
    api_key = (settings.GOANYAPI_API_KEY or "").strip()
    if not api_key:
        raise AIOverviewNotConfiguredError("未配置 GOANYAPI_API_KEY，AI Overview 证据源已关闭")

    url = build_provider_api_url(settings.GOANYAPI_BASE_URL or DEFAULT_BASE_URL, ENDPOINT_PATH)
    payload = _build_payload(query, country=country, language=language, device=device)
    owns_client = client is None
    http = client or build_provider_http_client(timeout=settings.GOANYAPI_TIMEOUT_SECONDS)

    try:
        response = await http.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
    except httpx.HTTPError as exc:
        raise AIOverviewRequestError(
            f"AI Overview 请求失败：{exc.__class__.__name__}",
            retryable=True,
        ) from exc
    finally:
        if owns_client:
            await http.aclose()

    if response.status_code >= 400:
        retryable = response.status_code in RETRYABLE_STATUS
        if response.status_code == 402:
            message = "GoAnyAPI 余额不足（AI Overview 无法继续调用）"
        elif response.status_code in {401, 403}:
            message = "GoAnyAPI 鉴权失败，请检查 GOANYAPI_API_KEY"
        else:
            message = f"GoAnyAPI 返回 HTTP {response.status_code}"
        raise AIOverviewRequestError(
            message,
            status_code=response.status_code,
            retryable=retryable,
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise AIOverviewRequestError("GoAnyAPI 返回了非 JSON 响应", retryable=True) from exc

    code = _text(body.get("code"))
    if code and code.lower() not in {"ok", "success"}:
        raise AIOverviewRequestError(f"GoAnyAPI 业务错误：{code}", retryable=False)

    return summarize(body, query=query)
