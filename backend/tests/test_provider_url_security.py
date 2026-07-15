import socket
import unittest
from unittest.mock import AsyncMock, patch

from app.services.provider_url_security import (
    PinnedAsyncNetworkBackend,
    ProviderURLValidationError,
    validate_provider_base_url,
    validate_provider_url_shape,
)
from app.core.config import settings


class ProviderURLSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_private_override_explicitly_allows_http_private_targets(self):
        with patch.object(settings, "ALLOW_PRIVATE_LLM_PROVIDER_URLS", True):
            self.assertEqual(
                validate_provider_url_shape("http://127.0.0.1:11434/v1"),
                "http://127.0.0.1:11434/v1",
            )

    async def test_cgnat_address_is_rejected(self):
        resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.64.0.1", 443)),
        ]
        with patch("app.services.provider_url_security.socket.getaddrinfo", return_value=resolution):
            with self.assertRaises(ProviderURLValidationError):
                await validate_provider_base_url("https://provider.example/v1")

    async def test_connect_backend_revalidates_dns_and_never_connects_to_rebound_private_ip(self):
        public_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ]
        private_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]
        backend = PinnedAsyncNetworkBackend()

        with (
            patch(
                "app.services.provider_url_security.socket.getaddrinfo",
                side_effect=[public_resolution, private_resolution],
            ),
            patch(
                "app.services.provider_url_security.AutoBackend.connect_tcp",
                new=AsyncMock(),
            ) as connect_tcp,
        ):
            await validate_provider_base_url("https://provider.example/v1")
            with self.assertRaises(ProviderURLValidationError):
                await backend.connect_tcp("provider.example", 443)

        connect_tcp.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
