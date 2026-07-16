import unittest
import socket
from unittest.mock import patch

from app.services.company_ingest import (
    build_candidate_links,
    fallback_select_company_pages,
    normalize_company_url,
    validate_public_crawl_url,
)


class CompanyIngestTests(unittest.TestCase):
    def test_normalize_company_url_adds_https_for_bare_domain(self):
        self.assertEqual(
            normalize_company_url("example.com"),
            "https://example.com",
        )

    def test_normalize_company_url_rejects_credentials_and_private_hosts(self):
        for value in (
            "https://user:password@example.com",
            "http://localhost:8000",
            "http://127.0.0.1/admin",
            "http://169.254.169.254/latest/meta-data",
            "http://[::1]/",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_company_url(value)

    @patch("app.services.company_ingest.socket.getaddrinfo")
    def test_validate_public_crawl_url_rejects_hostname_resolving_to_private_ip(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443)),
        ]

        with self.assertRaises(ValueError):
            validate_public_crawl_url("https://example.com")

    @patch("app.services.company_ingest.socket.getaddrinfo")
    def test_validate_public_crawl_url_accepts_hostname_resolving_to_public_ip(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ]

        self.assertEqual(validate_public_crawl_url("https://example.com"), "https://example.com")

    def test_build_candidate_links_keeps_same_domain_shallow_pages(self):
        candidates = build_candidate_links(
            "https://example.com",
            [
                {"url": "https://example.com/about", "title": "About"},
                {"url": "https://example.com/team", "title": "Team"},
                {"url": "https://example.com/blog/post-1", "title": "Blog"},
                {"url": "https://another.com/about", "title": "External"},
            ],
        )
        urls = [item["url"] for item in candidates]
        self.assertIn("https://example.com/about", urls)
        self.assertIn("https://example.com/team", urls)
        self.assertNotIn("https://example.com/blog/post-1", urls)
        self.assertNotIn("https://another.com/about", urls)

    def test_fallback_select_company_pages_prioritizes_about_and_team(self):
        selected = fallback_select_company_pages(
            "https://example.com",
            "Example",
            [
                {"url": "https://example.com/about", "title": "About", "path": "/about"},
                {"url": "https://example.com/team", "title": "Team", "path": "/team"},
                {"url": "https://example.com/blog", "title": "Blog", "path": "/blog"},
            ],
        )
        self.assertEqual(selected[0]["role"], "homepage")
        selected_urls = [page["url"] for page in selected]
        self.assertIn("https://example.com/about", selected_urls)
        self.assertIn("https://example.com/team", selected_urls)
