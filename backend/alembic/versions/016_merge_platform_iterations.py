"""Merge the release-hardening and quota-v2 migration branches.

Revision ID: 016_merge_platform_iterations
Revises: 014_builtin_homepage_release, 015_ensure_ai_reservation
Create Date: 2026-07-16
"""

from __future__ import annotations

from datetime import datetime
import json

from alembic import op
import sqlalchemy as sa


revision = "016_merge_platform_iterations"
down_revision = ("014_builtin_homepage_release", "015_ensure_ai_reservation")
branch_labels = None
depends_on = None


PREVIOUS_RELEASE_ID = "43a461f6-6be2-4931-9dbb-f1d56576292a"
MERGED_RELEASE_ID = "9fe4a087-42bc-423a-bc59-fc020018a6f9"
MERGED_MANIFEST = {
    "id": MERGED_RELEASE_ID,
    "title": "GEORankHub 导航与版权更新",
    "source_type": "zip_package",
    "entry_path": "index.html",
    "storage_path": f"/app/runtime/homepages/releases/{MERGED_RELEASE_ID}",
    "public_path": f"/app/runtime/homepages/public/releases/{MERGED_RELEASE_ID}",
    "file_count": 4,
    "compressed_size": 1467585,
    "extracted_size": 1523847,
    "sha256": "eacb70604d744ca87e9be11a92143cbf7d3cb73b051815c8744762e9c3f8c4cf",
    "files": [
        {
            "path": "css/style.css",
            "size": 34551,
            "sha256": "3ddcaea50bb52ad04cd5034bebaa7208f7e21c3f5f2b015422b4231650f2bc5a",
        },
        {
            "path": "favicon.svg",
            "size": 513,
            "sha256": "4ed02e3c7de9b2c1b2efd461eeec75fd7e56b6272bad3bc2a37bb8e56fb2bce8",
        },
        {
            "path": "images/ai-marketing-book.png",
            "size": 1456316,
            "sha256": "d797fe991235da5b9d7308db24fc78ca0d142456b707931caf9c6764e0f13636",
        },
        {
            "path": "index.html",
            "size": 31984,
            "sha256": "5e25c2648abaa6d289a6cfb1576dfe298225b706c4840f3f025693080ff081ef",
        },
    ],
    "created_at": "2026-07-16T07:52:23.775693Z",
}


def _migrate_builtin_selection() -> None:
    connection = op.get_bind()
    selected_previous = """
        EXISTS (
            SELECT 1
            FROM settings
            WHERE key = 'homepage_runtime'
              AND value ->> 'active_release_id' = CAST(CAST(:previous_id AS uuid) AS text)
        )
    """
    selected_merged = """
        EXISTS (
            SELECT 1
            FROM settings
            WHERE key = 'homepage_runtime'
              AND value ->> 'active_release_id' = CAST(CAST(:merged_id AS uuid) AS text)
        )
    """
    activate_merged = f"({selected_previous} OR {selected_merged})"
    params = {
        "previous_id": PREVIOUS_RELEASE_ID,
        "merged_id": MERGED_RELEASE_ID,
        "title": MERGED_MANIFEST["title"],
        "storage_path": MERGED_MANIFEST["storage_path"],
        "file_count": MERGED_MANIFEST["file_count"],
        "compressed_size": MERGED_MANIFEST["compressed_size"],
        "extracted_size": MERGED_MANIFEST["extracted_size"],
        "sha256": MERGED_MANIFEST["sha256"],
        "manifest": json.dumps(MERGED_MANIFEST, ensure_ascii=False),
        "created_at": datetime.fromisoformat(MERGED_MANIFEST["created_at"].removesuffix("Z")),
    }

    connection.execute(
        sa.text(
            f"""
            INSERT INTO homepage_releases (
                id, title, source_type, status, entry_path, storage_path,
                file_count, compressed_size, extracted_size, sha256, manifest,
                error_message, created_by, created_at, activated_at
            )
            SELECT
                CAST(:merged_id AS uuid), :title,
                CAST('zip_package' AS homepagesourcetype),
                CASE
                    WHEN {activate_merged}
                    THEN CAST('active' AS homepagereleasestatus)
                    ELSE CAST('archived' AS homepagereleasestatus)
                END,
                'index.html', :storage_path, :file_count, :compressed_size,
                :extracted_size, :sha256, CAST(:manifest AS jsonb), NULL, NULL,
                CAST(:created_at AS timestamp),
                CASE WHEN {activate_merged} THEN NOW() ELSE NULL END
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                source_type = EXCLUDED.source_type,
                status = EXCLUDED.status,
                entry_path = EXCLUDED.entry_path,
                storage_path = EXCLUDED.storage_path,
                file_count = EXCLUDED.file_count,
                compressed_size = EXCLUDED.compressed_size,
                extracted_size = EXCLUDED.extracted_size,
                sha256 = EXCLUDED.sha256,
                manifest = EXCLUDED.manifest,
                error_message = NULL,
                activated_at = CASE
                    WHEN EXCLUDED.status = CAST('active' AS homepagereleasestatus)
                    THEN COALESCE(homepage_releases.activated_at, EXCLUDED.activated_at)
                    ELSE NULL
                END
            """
        ),
        params,
    )
    connection.execute(
        sa.text(
            f"""
            UPDATE homepage_releases
            SET status = CAST('archived' AS homepagereleasestatus),
                activated_at = NULL
            WHERE id <> CAST(:merged_id AS uuid)
              AND status = CAST('active' AS homepagereleasestatus)
              AND {activate_merged}
            """
        ),
        params,
    )
    connection.execute(
        sa.text(
            """
            UPDATE settings
            SET value = jsonb_set(
                value,
                '{active_release_id}',
                to_jsonb(CAST(:merged_id AS text)),
                true
            )
            WHERE key = 'homepage_runtime'
              AND value ->> 'active_release_id' = CAST(CAST(:previous_id AS uuid) AS text)
            """
        ),
        params,
    )


def upgrade() -> None:
    _migrate_builtin_selection()


def downgrade() -> None:
    connection = op.get_bind()
    params = {
        "previous_id": PREVIOUS_RELEASE_ID,
        "merged_id": MERGED_RELEASE_ID,
    }
    selected_merged = """
        EXISTS (
            SELECT 1
            FROM settings
            WHERE key = 'homepage_runtime'
              AND value ->> 'active_release_id' = CAST(CAST(:merged_id AS uuid) AS text)
        )
    """
    connection.execute(
        sa.text(
            f"""
            UPDATE homepage_releases
            SET status = CASE
                    WHEN id = CAST(:previous_id AS uuid)
                    THEN CAST('active' AS homepagereleasestatus)
                    ELSE CAST('archived' AS homepagereleasestatus)
                END,
                activated_at = CASE
                    WHEN id = CAST(:previous_id AS uuid)
                    THEN COALESCE(activated_at, NOW())
                    ELSE NULL
                END
            WHERE (
                    id = CAST(:previous_id AS uuid)
                    OR status = CAST('active' AS homepagereleasestatus)
                )
              AND {selected_merged}
            """
        ),
        params,
    )
    connection.execute(
        sa.text(
            """
            UPDATE settings
            SET value = jsonb_set(
                value,
                '{active_release_id}',
                to_jsonb(CAST(:previous_id AS text)),
                true
            )
            WHERE key = 'homepage_runtime'
              AND value ->> 'active_release_id' = CAST(CAST(:merged_id AS uuid) AS text)
            """
        ),
        params,
    )
    connection.execute(
        sa.text("DELETE FROM homepage_releases WHERE id = CAST(:merged_id AS uuid)"),
        params,
    )
