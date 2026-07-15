"""Verify the Playwright worker image and pinned requirements import together."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"crawler image must use Python 3.10, got {sys.version.split()[0]}")

from playwright.sync_api import sync_playwright  # noqa: E402, F401

from app.core.celery_app import celery_app  # noqa: E402, F401
from app.tasks import crawl  # noqa: E402, F401

print(f"Crawler import smoke passed on Python {sys.version.split()[0]}.")
