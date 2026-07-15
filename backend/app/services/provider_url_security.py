"""Shared outbound URL policy for server-held AI provider credentials."""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

import httpx
from httpcore._backends.auto import AutoBackend

from app.core.config import settings


class ProviderURLValidationError(ValueError):
    """Raised when a provider URL could expose credentials or internal services."""


def provider_endpoint_identity(base_url: str) -> tuple[str, str, int | None, str]:
    parsed = urlsplit((base_url or "").strip())
    try:
        port = parsed.port
    except ValueError as exc:
        raise ProviderURLValidationError("API Base URL 端口不合法") from exc
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    normalized_port = None if port in {None, default_port} else port
    return (
        parsed.scheme.lower(),
        (parsed.hostname or "").lower().rstrip("."),
        normalized_port,
        (parsed.path or "").rstrip("/"),
    )


def _require_global_address(value: str) -> str:
    address = ipaddress.ip_address(value)
    if not address.is_global:
        raise ProviderURLValidationError("API Base URL 不能指向本机或非公网网络")
    return address.compressed


def validate_provider_url_shape(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        raise ProviderURLValidationError("API Base URL 不能为空")
    parsed = urlsplit(normalized)
    allowed_schemes = {"https"}
    if settings.ALLOW_PRIVATE_LLM_PROVIDER_URLS:
        allowed_schemes.add("http")
    if parsed.scheme.lower() not in allowed_schemes:
        raise ProviderURLValidationError("API Base URL 必须使用 HTTPS")
    if parsed.username or parsed.password:
        raise ProviderURLValidationError("API Base URL 不能包含凭据")
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        raise ProviderURLValidationError("API Base URL 缺少主机名")
    if parsed.query or parsed.fragment:
        raise ProviderURLValidationError("API Base URL 不能包含查询参数或片段")
    if not settings.ALLOW_PRIVATE_LLM_PROVIDER_URLS:
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ProviderURLValidationError("API Base URL 不能指向本机或非公网网络")
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            _require_global_address(address.compressed)
    return normalized


async def _resolve_validated_addresses(host: str, port: int) -> list[str]:
    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo,
            host,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ProviderURLValidationError("API Base URL 无法解析") from exc
    addresses: list[str] = []
    for record in records:
        address = record[4][0]
        normalized = _require_global_address(address)
        if normalized not in addresses:
            addresses.append(normalized)
    if not addresses:
        raise ProviderURLValidationError("API Base URL 无法解析")
    return addresses


async def validate_provider_base_url(base_url: str) -> str:
    normalized = validate_provider_url_shape(base_url)
    if settings.ALLOW_PRIVATE_LLM_PROVIDER_URLS:
        return normalized
    parsed = urlsplit(normalized)
    await _resolve_validated_addresses(parsed.hostname or "", parsed.port or 443)
    return normalized


def build_provider_api_url(base_url: str, suffix: str = "chat/completions") -> str:
    normalized = validate_provider_url_shape(base_url)
    normalized_suffix = suffix.strip("/")
    if normalized.endswith(f"/{normalized_suffix}"):
        return normalized
    return f"{normalized}/{normalized_suffix}"


class PinnedAsyncNetworkBackend(AutoBackend):
    """Resolve once per connection, validate, then connect to the approved IP literal."""

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        addresses = await _resolve_validated_addresses(host, port)
        last_error: Exception | None = None
        for address in addresses:
            try:
                return await super().connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception as exc:  # pragma: no cover - exercised by live network failures
                last_error = exc
        assert last_error is not None
        raise last_error


class PinnedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    def __init__(self):
        super().__init__(trust_env=False)
        self._pool._network_backend = PinnedAsyncNetworkBackend()


def build_provider_http_client(*, timeout: float) -> httpx.AsyncClient:
    transport = None
    if not settings.ALLOW_PRIVATE_LLM_PROVIDER_URLS:
        transport = PinnedAsyncHTTPTransport()
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
        transport=transport,
    )
