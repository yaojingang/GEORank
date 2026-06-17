"""
公司资料抽取与修复服务
"""
from __future__ import annotations

from datetime import date
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from sqlalchemy import update

from app.models.company import Company
from app.services.ai_client import ai_client
from app.services.storage import storage
from app.tasks.diagnose import (
    _check_citations,
    _check_content,
    _check_meta,
    _check_schema,
    _calculate_overall_score,
)

_KNOWN_TECH_TERMS = [
    "OpenAI API",
    "Claude",
    "DeepSeek",
    "Firecrawl",
    "Ahrefs API",
    "Qdrant",
    "Neo4j",
    "Pinecone",
    "LangChain",
    "Next.js",
    "React",
    "Postgres",
    "Redis",
    "Playwright",
    "Python",
]

_COMPANY_NAME_SPLIT_PATTERN = re.compile(r"\s*[|｜丨]\s*|\s+[—–-]\s+")
_COMPANY_NAME_NOISE_SUFFIXES = (
    "官方网站",
    "官网首页",
    "官网",
    "首页",
    "主页",
)
_COMPANY_NAME_NOISE_EXACT = {
    "官网",
    "官方网站",
    "首页",
    "主页",
    "关于我们",
    "about us",
}


def company_profile_needs_hydration(company: Company) -> bool:
    return (
        not bool((company.short_description or "").strip() or (company.description or "").strip())
        or not bool(company.tags)
        or not bool(company.tech_stack)
        or company.geo_details is None
        or company.geo_score is None
    )


def load_company_source_html(company: Company) -> str:
    page_keys: list[str] = []
    for page in company.crawl_pages or []:
        if page.get("key"):
            page_keys.append(page["key"])

    if not page_keys:
        page_keys = [key for key in [company.raw_html_key, company.about_html_key] if key]

    html_parts: list[str] = []
    for key in page_keys:
        raw = storage.get(key)
        if raw:
            html_parts.append(raw.decode("utf-8", errors="replace"))
    return "\n".join(html_parts)


def load_company_homepage_html(company: Company) -> str:
    homepage_key = None
    for page in company.crawl_pages or []:
        if page.get("role") == "homepage" and page.get("key"):
            homepage_key = page["key"]
            break
    homepage_key = homepage_key or company.raw_html_key
    if not homepage_key:
        return ""
    raw = storage.get(homepage_key)
    if not raw:
        return ""
    return raw.decode("utf-8", errors="replace")


def _clean_text(value: str | None, limit: int | None = None) -> str | None:
    text = re.sub(r"\s+", " ", (value or "").strip())
    if not text:
        return None
    if limit is not None:
        return text[:limit]
    return text


def _pick_first(*values: str | None, limit: int | None = None) -> str | None:
    for value in values:
        cleaned = _clean_text(value, limit=limit)
        if cleaned:
            return cleaned
    return None


def normalize_company_name(value: str | None, fallback_name: str | None = None) -> str | None:
    primary = _clean_text(value, limit=200)
    fallback = _clean_text(fallback_name, limit=200)
    if not primary:
        return fallback

    candidates = [segment.strip(" -_|｜丨—–·•:：") for segment in _COMPANY_NAME_SPLIT_PATTERN.split(primary)]
    if not candidates:
        candidates = [primary]

    normalized_candidates: list[str] = []
    for candidate in candidates:
        cleaned = _clean_text(candidate, limit=200)
        if not cleaned:
            continue
        for suffix in _COMPANY_NAME_NOISE_SUFFIXES:
            if cleaned.endswith(suffix) and len(cleaned) > len(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        cleaned = cleaned.strip(" -_|｜丨—–·•:：")
        if not cleaned:
            continue
        if cleaned.lower() in _COMPANY_NAME_NOISE_EXACT:
            continue
        normalized_candidates.append(cleaned)

    for candidate in normalized_candidates:
        if 1 < len(candidate) <= 60:
            return candidate

    return fallback or primary


def fallback_company_profile_from_html(html: str, fallback_name: str | None = None) -> dict:
    soup = BeautifulSoup(html or "", "lxml")

    title = _pick_first(
        soup.title.string if soup.title and soup.title.string else None,
        fallback_name,
        limit=200,
    )
    title = normalize_company_name(title, fallback_name=fallback_name)
    meta_description = _pick_first(
        soup.find("meta", attrs={"name": "description"}) and soup.find("meta", attrs={"name": "description"}).get("content"),
        soup.find("meta", attrs={"property": "og:description"}) and soup.find("meta", attrs={"property": "og:description"}).get("content"),
        limit=600,
    )

    body_text = _clean_text(soup.get_text(separator=" ", strip=True), limit=4000) or ""
    snippet_source = meta_description or body_text
    short_description = _pick_first(snippet_source, limit=120)
    description = _pick_first(snippet_source, limit=320)
    keyword_meta = _pick_first(
        soup.find("meta", attrs={"name": "keywords"}) and soup.find("meta", attrs={"name": "keywords"}).get("content"),
        limit=500,
    )
    tags = []
    if keyword_meta:
        tags = [
            item.strip()[:24]
            for item in re.split(r"[,，/|]+", keyword_meta)
            if item.strip()
        ][:6]

    joined_text = " ".join([title or "", meta_description or "", body_text])
    tech_stack = []
    seen_terms = set()
    lowered = joined_text.lower()
    for term in _KNOWN_TECH_TERMS:
        if term.lower() in lowered and term not in seen_terms:
            tech_stack.append(term)
            seen_terms.add(term)

    team_members = []

    return {
        "name": title,
        "description": description,
        "short_description": short_description,
        "category": None,
        "headquarters": None,
        "funding_stage": None,
        "employee_count": None,
        "founded_date": None,
        "tags": tags,
        "tech_stack": tech_stack,
        "team_members": team_members,
    }


async def extract_company_profile(html: str, fallback_name: str | None = None) -> dict:
    profile = fallback_company_profile_from_html(html, fallback_name=fallback_name)
    try:
        extracted = await ai_client.extract_company_info(html)
    except Exception:
        extracted = {}

    for key in (
        "name",
        "description",
        "short_description",
        "category",
        "headquarters",
        "funding_stage",
        "employee_count",
        "founded_date",
        "tags",
        "tech_stack",
        "team_members",
    ):
        if extracted.get(key) not in (None, "", []):
            profile[key] = extracted[key]

    profile["name"] = normalize_company_name(profile.get("name"), fallback_name=fallback_name)

    return profile


def calculate_company_geo_profile(company: Company, homepage_html: str) -> dict:
    if not homepage_html:
        return {}
    soup = BeautifulSoup(homepage_html, "lxml")
    base_domain = urlparse(company.url).netloc.lower()
    schema = _check_schema(soup)
    meta = _check_meta(soup)
    content = _check_content(soup)
    citation = _check_citations(soup, base_domain)
    score = _calculate_overall_score(
        schema["score"],
        content["score"],
        meta["score"],
        citation["score"],
    )
    return {
        "geo_score": score,
        "geo_details": {
            "schema": schema["score"],
            "content": content["score"],
            "meta": meta["score"],
            "citation": citation["score"],
        },
    }


def build_company_profile_values(company: Company, profile: dict) -> dict:
    values: dict = {}
    normalized_name = normalize_company_name(profile.get("name"), fallback_name=company.name)

    if normalized_name and normalized_name != company.name:
        values["name"] = normalized_name[:200]
    if profile.get("description"):
        values["description"] = profile["description"]
    if profile.get("short_description"):
        values["short_description"] = profile["short_description"][:300]
    if profile.get("category"):
        values["category"] = profile["category"][:50]
    if profile.get("headquarters"):
        values["headquarters"] = profile["headquarters"][:200]
    if profile.get("funding_stage"):
        values["funding_stage"] = profile["funding_stage"][:50]
    if profile.get("employee_count"):
        values["employee_count"] = profile["employee_count"][:50]
    if profile.get("founded_date"):
        try:
            founded_date = str(profile["founded_date"]).strip()
            if len(founded_date) == 7:
                founded_date += "-01"
            values["founded_date"] = date.fromisoformat(founded_date)
        except Exception:
            pass
    if profile.get("tags") is not None:
        values["tags"] = list(profile["tags"])[:6]
    if profile.get("tech_stack") is not None:
        values["tech_stack"] = list(profile["tech_stack"])[:8]
    if profile.get("team_members") is not None:
        values["team_members"] = list(profile["team_members"])[:6]
    if profile.get("geo_details"):
        values["geo_details"] = profile["geo_details"]
    if profile.get("geo_score") is not None:
        values["geo_score"] = float(profile["geo_score"])

    return values


async def ensure_company_profile(db, company: Company, *, force: bool = False) -> dict:
    if not force and not company_profile_needs_hydration(company):
        return {}

    html = load_company_source_html(company)
    if not html:
        return {}

    profile = await extract_company_profile(html, fallback_name=company.name)
    profile.update(calculate_company_geo_profile(company, load_company_homepage_html(company)))
    values = build_company_profile_values(company, profile)
    if not values:
        return {}

    await db.execute(
        update(Company)
        .where(Company.id == company.id)
        .values(**values)
    )
    await db.commit()
    await db.refresh(company)
    return values
