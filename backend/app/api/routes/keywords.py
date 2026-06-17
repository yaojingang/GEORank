"""
拓词 API
"""
import json

from fastapi import APIRouter, HTTPException, Request

from app.core.deps import DbSession, OptionalUser
from app.schemas.keyword import KeywordExpandRequest, KeywordExpandResponse
from app.services.keyword_expansion import expand_keywords
from app.services.ai_usage import record_ai_usage, resolve_ai_access

router = APIRouter()


@router.post("/expand", response_model=KeywordExpandResponse)
async def expand_keyword_pack(payload: KeywordExpandRequest, request: Request, db: DbSession, current_user: OptionalUser):
    access = None
    try:
        access = await resolve_ai_access(
            db=db,
            request=request,
            current_user=current_user,
            module="keywords",
            prompt_text="\n".join(payload.seeds or []),
        )
        result = await expand_keywords(payload.seeds, provider_override=access.provider_override)
        await record_ai_usage(
            db,
            access,
            output_text=json.dumps(result.get("summary", {}), ensure_ascii=False),
            metadata={"seeds": result.get("seeds", [])},
        )
        await db.commit()
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if access and access.provider_override is not None:
            raise HTTPException(
                status_code=502,
                detail="自定义 API Key 调用失败，请检查供应商、Base URL、模型和 Key。",
            ) from exc
        raise
