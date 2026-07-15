"""
API 路由汇总
"""
from fastapi import APIRouter

from app.api.routes import auth, companies, diagnostics, solutions, content, admin, settings, keywords, experts, usage

router = APIRouter()

router.include_router(auth.router,        prefix="/auth",        tags=["认证"])
router.include_router(companies.router,   prefix="/companies",   tags=["公司"])
router.include_router(diagnostics.router,  prefix="/diagnostics", tags=["诊断"])
router.include_router(solutions.router,    prefix="/solutions",   tags=["方案"])
router.include_router(content.router,      prefix="/content",     tags=["内容"])
router.include_router(keywords.router,     prefix="/keywords",    tags=["拓词"])
router.include_router(experts.router,      prefix="/experts",     tags=["专家"])
router.include_router(usage.router,        prefix="/usage",       tags=["AI 用量"])
router.include_router(admin.router,        prefix="/admin",       tags=["后台管理"])
router.include_router(settings.router,     prefix="/settings",    tags=["站点配置"])
