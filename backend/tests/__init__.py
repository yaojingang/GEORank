"""Test-package bootstrap for an explicitly configured integration database."""

import os

from tests.database_safety import bootstrap_test_database_environment


if os.environ.get("TEST_DATABASE_URL", "").strip():
    bootstrap_test_database_environment(os.environ)
