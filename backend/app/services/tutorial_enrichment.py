"""Public tutorial rendering helpers.

Published tutorial text comes from the content model. This module only removes
legacy navigation markers and provides a deterministic reading-time estimate.
"""
from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.content import Content


def strip_legacy_navigation_markers(markdown_body: str | None) -> str:
    text = (markdown_body or "").strip()
    lines = []
    for line in text.splitlines():
        normalized = line.strip()
        if normalized.startswith("下一篇《") or normalized.startswith("上一篇《"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def enrich_tutorial_markdown(title: str | None, markdown_body: str | None) -> str:
    del title
    return strip_legacy_navigation_markers(markdown_body)


def get_public_markdown(article: "Content") -> str:
    content_type = getattr(article, "content_type", None)
    content_type_value = getattr(content_type, "value", content_type)
    if content_type_value == "tutorial":
        return enrich_tutorial_markdown(article.title, article.markdown_body)
    return article.markdown_body or ""


def estimate_reading_time_minutes(markdown_body: str | None, fallback: int | None = None) -> int:
    source = markdown_body or ""
    source = re.sub(r"```.*?```", " ", source, flags=re.S)
    source = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", source)
    source = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", source)
    source = re.sub(r"[#>*`|_-]", " ", source)
    compact = re.sub(r"\s+", "", source)
    estimated = max(1, math.ceil(len(compact) / 320))
    return max(int(fallback or 0), estimated)
