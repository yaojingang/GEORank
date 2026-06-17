"""
系统设置 Schemas
"""
from typing import Any, Optional

from pydantic import BaseModel


class SettingPublicResponse(BaseModel):
    """公开配置项（前端可读）"""
    # 动态 KV，直接返回 dict
    pass


class SettingAdminItem(BaseModel):
    value: Any
    category: str
    is_public: bool
    updated_at: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    """批量更新设置 — key: value 字典"""
    # 使用 dict 接收，因为 key 是动态的
    pass
