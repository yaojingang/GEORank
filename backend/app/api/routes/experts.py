"""
专家频道公开 API
"""
from typing import Optional

from fastapi import APIRouter
from sqlalchemy import String, cast, func, or_, select

from app.core.deps import DbSession
from app.models.expert import ExpertProfile


router = APIRouter()


def serialize_expert(expert: ExpertProfile) -> dict:
    return {
        "id": str(expert.id),
        "display_name": expert.display_name,
        "avatar_initials": expert.avatar_initials,
        "title": expert.title,
        "category": expert.category,
        "specialty_label": expert.specialty_label,
        "summary": expert.summary or "",
        "expertise": expert.expertise if isinstance(expert.expertise, list) else [],
        "consultation": expert.consultation or "",
        "keywords": expert.keywords if isinstance(expert.keywords, list) else [],
        "sort_order": expert.sort_order or 100,
        "is_featured": bool(expert.is_featured),
        "is_published": bool(expert.is_published),
        "created_at": expert.created_at.isoformat() if expert.created_at else None,
        "updated_at": expert.updated_at.isoformat() if expert.updated_at else None,
    }


@router.get("")
async def list_public_experts(
    db: DbSession,
    category: Optional[str] = None,
    search: Optional[str] = None,
):
    """公开专家频道列表，仅返回已发布专家。"""
    query = select(ExpertProfile).where(ExpertProfile.is_published == True)
    if category:
        query = query.where(ExpertProfile.category == category)
    if search:
        like = f"%{search.strip()}%"
        query = query.where(
            or_(
                ExpertProfile.display_name.ilike(like),
                ExpertProfile.title.ilike(like),
                ExpertProfile.specialty_label.ilike(like),
                ExpertProfile.summary.ilike(like),
                ExpertProfile.consultation.ilike(like),
                cast(ExpertProfile.expertise, String).ilike(like),
                cast(ExpertProfile.keywords, String).ilike(like),
            )
        )

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query
        .order_by(ExpertProfile.sort_order.asc(), ExpertProfile.created_at.desc())
        .limit(100)
    )
    experts = result.scalars().all()
    return {
        "items": [serialize_expert(expert) for expert in experts],
        "total": total or 0,
    }
