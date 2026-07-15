"""Migrate the built-in homepage release without changing custom selections.

Revision ID: 014_builtin_homepage_release
Revises: 013_security_invariants
Create Date: 2026-07-15
"""

from __future__ import annotations

import json
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "014_builtin_homepage_release"
down_revision = "013_security_invariants"
branch_labels = None
depends_on = None


OLD_RELEASE_ID = "f7e16e7c-e1aa-4e39-951b-4c274dd05175"
NEW_RELEASE_ID = "43a461f6-6be2-4931-9dbb-f1d56576292a"

NEW_MANIFEST = {
    "id": NEW_RELEASE_ID,
    "title": "开源内置首页",
    "source_type": "zip_package",
    "entry_path": "index.html",
    "storage_path": f"/app/runtime/homepages/releases/{NEW_RELEASE_ID}",
    "public_path": f"/app/runtime/homepages/public/releases/{NEW_RELEASE_ID}",
    "file_count": 4,
    "compressed_size": 1467692,
    "extracted_size": 1524643,
    "sha256": "f4172e816fcc99dd337d4dadb809278601388d0dd438b7f4dfff44453057f376",
    "files": [
        {
            "path": "css/style.css",
            "size": 35442,
            "sha256": "8072bf21c8297c981a9ba83fbf05fee408f49e01bfa22cae23808f8fb740b927",
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
            "size": 31800,
            "sha256": "c96de65d35694f0ed49549c8fee23c67b2553db6854be167363c9f498e8e6803",
        },
    ],
    "created_at": "2026-07-15T07:33:21.725406Z",
}

OLD_MANIFEST = {
    "id": OLD_RELEASE_ID,
    "title": "首页 8 模块工作台入口 2026-06-16",
    "source_type": "zip_package",
    "entry_path": "index.html",
    "storage_path": f"/app/runtime/homepages/releases/{OLD_RELEASE_ID}",
    "public_path": f"/app/runtime/homepages/public/releases/{OLD_RELEASE_ID}",
    "file_count": 4,
    "compressed_size": 14105,
    "extracted_size": 1525609,
    "sha256": "8e03d99ce95cfffb003a48258eb76457aa75869297e0f7e16655a1c9b5eaba99",
    "files": [
        {
            "path": "css/style.css",
            "size": 35442,
            "sha256": "8072bf21c8297c981a9ba83fbf05fee408f49e01bfa22cae23808f8fb740b927",
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
            "size": 33338,
            "sha256": "0f7aa384c88a9b62930796dc38a4f02d9ddd950b67979240f26771f730ae5c88",
        },
    ],
    "created_at": "2026-06-16T06:58:21.368734Z",
}


def _migrate_selected_builtin(
    source_id: str,
    target_id: str,
    target_manifest: dict,
    *,
    activate_without_setting: bool = False,
) -> None:
    connection = op.get_bind()
    selected_source = """
        EXISTS (
            SELECT 1
            FROM settings
            WHERE key = 'homepage_runtime'
              AND value ->> 'active_release_id' = CAST(CAST(:source_id AS uuid) AS text)
        )
    """
    selected_target = """
        EXISTS (
            SELECT 1
            FROM settings
            WHERE key = 'homepage_runtime'
              AND value ->> 'active_release_id' = CAST(CAST(:target_id AS uuid) AS text)
        )
    """
    missing_runtime_setting = """
        NOT EXISTS (
            SELECT 1 FROM settings WHERE key = 'homepage_runtime'
        )
    """
    activate_target = f"({selected_source} OR {selected_target})"
    if activate_without_setting:
        activate_target = f"({activate_target} OR {missing_runtime_setting})"
    params = {
        "source_id": source_id,
        "target_id": target_id,
        "title": target_manifest["title"],
        "storage_path": target_manifest["storage_path"],
        "file_count": target_manifest["file_count"],
        "compressed_size": target_manifest["compressed_size"],
        "extracted_size": target_manifest["extracted_size"],
        "sha256": target_manifest["sha256"],
        "manifest": json.dumps(target_manifest, ensure_ascii=False),
        "created_at": datetime.fromisoformat(target_manifest["created_at"].removesuffix("Z")),
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
                CAST(:target_id AS uuid), :title,
                CAST('zip_package' AS homepagesourcetype),
                CASE
                    WHEN {activate_target}
                    THEN CAST('active' AS homepagereleasestatus)
                    ELSE CAST('archived' AS homepagereleasestatus)
                END,
                'index.html', :storage_path, :file_count, :compressed_size,
                :extracted_size, :sha256, CAST(:manifest AS jsonb), NULL, NULL,
                CAST(:created_at AS timestamp),
                CASE
                    WHEN {activate_target}
                    THEN NOW()
                    ELSE NULL
                END
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
        sa.text("DELETE FROM homepage_releases WHERE id = CAST(:source_id AS uuid)"),
        params,
    )
    connection.execute(
        sa.text(
            f"""
            UPDATE homepage_releases
            SET status = CAST('archived' AS homepagereleasestatus)
            WHERE id <> CAST(:target_id AS uuid)
              AND (
                  status = CAST('active' AS homepagereleasestatus)
                  OR id = CAST(:source_id AS uuid)
              )
              AND {activate_target}
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
                to_jsonb(CAST(:target_id AS text)),
                true
            )
            WHERE key = 'homepage_runtime'
              AND value ->> 'active_release_id' = :source_id
            """
        ),
        params,
    )


def upgrade() -> None:
    _migrate_selected_builtin(OLD_RELEASE_ID, NEW_RELEASE_ID, NEW_MANIFEST)


def downgrade() -> None:
    _migrate_selected_builtin(
        NEW_RELEASE_ID,
        OLD_RELEASE_ID,
        OLD_MANIFEST,
        activate_without_setting=True,
    )
