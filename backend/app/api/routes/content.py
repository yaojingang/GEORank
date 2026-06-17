"""
Wiki 内容 API — Markdown 文章列表 / 详情 / 导航树
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, update

from app.core.deps import DbSession
from app.models.content import Content, ContentStatus, ContentType
from app.services.content_render import render_markdown
from app.services.tutorial_enrichment import estimate_reading_time_minutes, get_public_markdown

router = APIRouter()


def _public_reading_time(article: Content) -> int | None:
    return estimate_reading_time_minutes(
        get_public_markdown(article),
        article.reading_time_minutes,
    )


def _serialize_content_summary(article: Content) -> dict:
    return {
        "id": str(article.id),
        "title": article.title,
        "slug": article.slug,
        "path_key": article.path_key,
        "content_type": article.content_type.value,
        "cover_image": article.cover_image,
        "reading_time_minutes": _public_reading_time(article),
        "tags": article.tags if isinstance(article.tags, list) else [],
        "view_count": article.view_count,
        "created_at": article.created_at.isoformat(),
        "updated_at": article.updated_at.isoformat(),
    }


def _serialize_content_detail(article: Content) -> dict:
    markdown_body = get_public_markdown(article)
    html_body = render_markdown(markdown_body)
    return {
        "id": str(article.id),
        "title": article.title,
        "slug": article.slug,
        "path_key": article.path_key,
        "content_type": article.content_type.value,
        "status": article.status.value,
        "markdown_body": markdown_body,
        "html_body": html_body,
        "cover_image": article.cover_image,
        "reading_time_minutes": _public_reading_time(article),
        "tags": article.tags if isinstance(article.tags, list) else [],
        "view_count": article.view_count,
        "created_at": article.created_at.isoformat(),
        "updated_at": article.updated_at.isoformat(),
    }


async def _get_published_content_by_identifier(identifier: str, db: DbSession) -> Content | None:
    normalized = (identifier or "").strip()
    if not normalized:
        return None

    if len(normalized) == 5 and normalized.isalpha():
        result = await db.execute(
            select(Content).where(
                Content.status == ContentStatus.PUBLISHED,
                Content.path_key == normalized.lower(),
            )
        )
        article = result.scalar_one_or_none()
        if article:
            return article

    result = await db.execute(
        select(Content).where(
            Content.status == ContentStatus.PUBLISHED,
            Content.slug == normalized,
        )
    )
    return result.scalar_one_or_none()


@router.get("/")
async def list_content(
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    content_type: Optional[str] = None,
    tag: Optional[str] = None,
):
    """文章列表 — 仅返回已发布的文章"""
    query = select(Content).where(Content.status == ContentStatus.PUBLISHED)

    if content_type:
        query = query.where(Content.content_type == content_type)
    if tag:
        # JSONB 包含查询：tags 数组包含指定标签
        query = query.where(Content.tags.contains([tag]))

    query = query.order_by(Content.created_at.desc())

    result = await db.execute(query.offset((page - 1) * size).limit(size))
    articles = result.scalars().all()

    return [_serialize_content_summary(a) for a in articles]


@router.get("/nav")
async def get_nav_tree(db: DbSession):
    """
    章节导航树 — 用于 tutorial.html 左侧目录和移动端横向 Tab
    按 tags 中的第一个 tag 作为分组依据
    """
    result = await db.execute(
        select(Content)
        .where(Content.status == ContentStatus.PUBLISHED, Content.content_type == "tutorial")
        .order_by(Content.created_at)
    )
    articles = result.scalars().all()

    # 按第一个 tag 分组
    groups: dict[str, list] = {}
    for a in articles:
        tags = a.tags if isinstance(a.tags, list) else []
        category = tags[0] if tags else "其他"
        if category not in groups:
            groups[category] = []
        groups[category].append({
            "title": a.title,
            "slug": a.slug,
            "path_key": a.path_key,
            "reading_time_minutes": _public_reading_time(a),
        })

    return [
        {"category": cat, "items": items}
        for cat, items in groups.items()
    ]


@router.get("/resolve/{identifier}")
async def resolve_content(identifier: str, db: DbSession):
    """根据公开短码或 slug 获取文章，并增加阅读计数"""
    article = await _get_published_content_by_identifier(identifier, db)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    await db.execute(
        update(Content).where(Content.id == article.id).values(view_count=Content.view_count + 1)
    )
    await db.commit()
    await db.refresh(article)
    return _serialize_content_detail(article)


@router.get("/{slug}")
async def get_content(slug: str, db: DbSession):
    """兼容旧 slug 详情接口，并增加阅读计数"""
    article = await _get_published_content_by_identifier(slug, db)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    await db.execute(
        update(Content).where(Content.id == article.id).values(view_count=Content.view_count + 1)
    )
    await db.commit()
    await db.refresh(article)
    return _serialize_content_detail(article)
