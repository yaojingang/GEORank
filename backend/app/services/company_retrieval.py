"""
公司检索降级服务
在 Embedding / 向量检索不可用时，提供基于结构化字段的推荐与相似度排序。
"""
from __future__ import annotations

import math
import re
import uuid
from typing import Iterable

from sqlalchemy import select

from app.models.company import Company, PublishStatus
from app.models.diagnostic import DiagnosticReport


def _stringify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return " ".join(_stringify(item) for item in value if item)
    if isinstance(value, dict):
        return " ".join(_stringify(v) for v in value.values() if v)
    return str(value)


def _tokenize_query(text: str) -> list[str]:
    latin = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9#+.\-]{1,}", text.lower())
    cjk = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    tokens = []
    seen = set()
    for token in [*latin, *cjk]:
        normalized = token.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            tokens.append(normalized)
    return tokens


def _company_search_blob(company: Company) -> str:
    return " ".join(
        filter(
            None,
            [
                _stringify(company.name).lower(),
                _stringify(company.category).lower(),
                _stringify(company.tags).lower(),
                _stringify(company.tech_stack).lower(),
                _stringify(company.short_description).lower(),
                _stringify(company.description).lower(),
                _stringify(company.tech_level).lower(),
                _stringify(company.funding_stage).lower(),
            ],
        )
    )


def _match_score(company: Company, tokens: list[str], *, preferred_company_id: str | None = None) -> float:
    blob = _company_search_blob(company)
    name = _stringify(company.name).lower()
    category = _stringify(company.category).lower()
    tags = [_stringify(tag).lower() for tag in (company.tags or [])]
    tech_stack = [_stringify(item).lower() for item in (company.tech_stack or [])]

    score = 0.0
    if preferred_company_id and str(company.id) == preferred_company_id:
        score += 120.0

    for token in tokens:
        if token == name:
            score += 60.0
        elif token in name:
            score += 34.0

        if token and token == category:
            score += 26.0
        elif token and token in category:
            score += 18.0

        for tag in tags:
            if token == tag:
                score += 20.0
            elif token in tag or tag in token:
                score += 12.0

        for tech in tech_stack:
            if token == tech:
                score += 16.0
            elif token in tech or tech in token:
                score += 10.0

        if token and token in blob:
            score += 5.0

    if company.is_geo_certified:
        score += 2.0
    if company.geo_score:
        score += min(company.geo_score / 25.0, 4.0)
    return score


async def _get_published_companies(db) -> list[Company]:
    result = await db.execute(
        select(Company).where(Company.publish_status == PublishStatus.PUBLISHED)
    )
    return result.scalars().all()


async def fallback_company_recommendations(
    db,
    query: str,
    *,
    diagnostic_report_id: str | None = None,
    limit: int = 5,
) -> list[Company]:
    """无 embedding 时的公司推荐。"""
    preferred_company_id: str | None = None
    if diagnostic_report_id:
        try:
            report_id = uuid.UUID(diagnostic_report_id)
            result = await db.execute(
                select(DiagnosticReport.company_id).where(DiagnosticReport.id == report_id)
            )
            preferred = result.scalar_one_or_none()
            preferred_company_id = str(preferred) if preferred else None
        except Exception:
            preferred_company_id = None

    companies = await _get_published_companies(db)
    tokens = _tokenize_query(query)
    ranked = sorted(
        companies,
        key=lambda company: (
            _match_score(company, tokens, preferred_company_id=preferred_company_id),
            company.geo_score or 0,
            company.upvotes or 0,
        ),
        reverse=True,
    )
    return ranked[:limit]


def _shared_terms(a: Iterable[str], b: Iterable[str]) -> int:
    left = {item for item in a if item}
    right = {item for item in b if item}
    return len(left & right)


def _similarity_score(base: Company, candidate: Company) -> float:
    score = 0.0

    if base.category and candidate.category and base.category == candidate.category:
        score += 28.0

    base_tags = [_stringify(tag).lower() for tag in (base.tags or [])]
    candidate_tags = [_stringify(tag).lower() for tag in (candidate.tags or [])]
    score += _shared_terms(base_tags, candidate_tags) * 14.0

    base_stack = [_stringify(item).lower() for item in (base.tech_stack or [])]
    candidate_stack = [_stringify(item).lower() for item in (candidate.tech_stack or [])]
    score += _shared_terms(base_stack, candidate_stack) * 10.0

    if base.is_geo_certified and candidate.is_geo_certified:
        score += 4.0

    if base.geo_score and candidate.geo_score:
        score += max(0.0, 12.0 - abs(base.geo_score - candidate.geo_score) / 5.0)

    base_blob = _company_search_blob(base)
    candidate_blob = _company_search_blob(candidate)
    for token in _tokenize_query(base_blob):
        if token in candidate_blob:
            score += 1.2

    return score


async def fallback_similar_companies(db, company: Company, *, limit: int = 3) -> list[Company]:
    companies = await _get_published_companies(db)
    ranked = sorted(
        [candidate for candidate in companies if candidate.id != company.id],
        key=lambda candidate: (
            _similarity_score(company, candidate),
            candidate.geo_score or 0,
            candidate.upvotes or 0,
        ),
        reverse=True,
    )
    return ranked[:limit]


async def _get_published_companies_by_ids(db, company_ids: list[str]) -> list[Company]:
    valid_ids: list[uuid.UUID] = []
    for company_id in company_ids:
        try:
            valid_ids.append(uuid.UUID(company_id))
        except (TypeError, ValueError, AttributeError):
            continue
    if not valid_ids:
        return []
    result = await db.execute(
        select(Company).where(
            Company.id.in_(valid_ids),
            Company.publish_status == PublishStatus.PUBLISHED,
        )
    )
    return result.scalars().all()


async def rank_similar_companies(db, company: Company, *, limit: int = 3) -> list[Company]:
    """优先使用 Qdrant 公司向量，相邻结果不足时用结构化相似度补齐。"""
    ranked: list[Company] = []
    try:
        from app.services.vector_store import vector_store

        vector_ids = await vector_store.get_similar_company_ids(
            str(company.id),
            top_k=limit + 1,
        )
        ordered_ids = [
            company_id
            for company_id in vector_ids
            if company_id != str(company.id)
        ][:limit]
        candidates = await _get_published_companies_by_ids(db, ordered_ids)
        candidate_map = {str(candidate.id): candidate for candidate in candidates}
        ranked = [candidate_map[company_id] for company_id in ordered_ids if company_id in candidate_map]
    except Exception:
        ranked = []

    if len(ranked) < limit:
        fallback = await fallback_similar_companies(db, company, limit=limit + len(ranked))
        seen = {company.id, *(candidate.id for candidate in ranked)}
        ranked.extend(candidate for candidate in fallback if candidate.id not in seen)
    return ranked[:limit]
