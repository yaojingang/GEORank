"""
公司公开链接与短码解析
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.company import Company


def company_public_identifier(company: Company) -> str:
    return getattr(company, "path_key", None) or str(company.id)


def company_public_path(company: Company) -> str:
    return f"/c/{company_public_identifier(company)}"


async def get_company_by_identifier(db, identifier: str) -> Company | None:
    normalized = str(identifier or "").strip()
    if not normalized:
        return None

    try:
        company_uuid = uuid.UUID(normalized)
    except ValueError:
        company_uuid = None

    if company_uuid is not None:
        result = await db.execute(select(Company).where(Company.id == company_uuid))
        company = result.scalar_one_or_none()
        if company:
            return company

    result = await db.execute(select(Company).where(Company.path_key == normalized.lower()))
    return result.scalar_one_or_none()
