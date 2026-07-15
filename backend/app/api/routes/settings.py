"""
站点公开配置 API — GET /api/settings/public
前端加载时调用，动态获取站点名称等公开配置
"""
from fastapi import APIRouter, Response
from sqlalchemy import select

from app.core.deps import DbSession
from app.models.settings import Setting
from app.services.runtime_settings import get_frontend_module_config, get_homepage_runtime_config
from app.services.settings_security import decrypt_setting_value, is_sensitive_setting

router = APIRouter()


@router.get("/public")
async def get_public_settings(db: DbSession, response: Response):
    """
    返回 is_public=True 的配置项
    前端 common.js 用于动态替换 Header Logo / 页面 Title / Footer 版权信息
    """
    result = await db.execute(
        select(Setting).where(Setting.is_public == True)  # noqa: E712
    )
    settings = result.scalars().all()

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return {
        s.key: decrypt_setting_value(s.value, s.key, s.category)
        for s in settings
        if not is_sensitive_setting(s.key, s.category)
    }


@router.get("/frontend-modules")
async def get_frontend_modules():
    """返回前台频道模块开关配置。"""
    config = await get_frontend_module_config()
    default_module = config.get("default_module")
    return {
        "default_module": default_module,
        "modules": [
            {
                "key": module.get("key"),
                "name": module.get("name"),
                "path": module.get("path"),
                "description": module.get("description"),
                "enabled": module.get("enabled", True),
                "protected_paths": module.get("protected_paths") or [],
                "is_default": module.get("key") == default_module,
            }
            for module in config.get("modules") or []
        ],
    }


@router.get("/homepage")
async def get_homepage_settings(response: Response):
    """返回公开首页运行时状态。"""
    config = await get_homepage_runtime_config()
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return {
        "mode": config.get("mode", "default"),
        "active": config.get("mode") == "custom" and bool(config.get("active_release_id")),
        "active_release_id": config.get("active_release_id"),
        "company_list_path": config.get("company_list_path") or "/companies",
        "fallback_enabled": config.get("fallback_enabled", True),
    }
