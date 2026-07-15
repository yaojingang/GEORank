"""
内容模块 Schemas
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import PaginatedResponse


class ContentListItem(BaseModel):
    id: str
    title: str
    slug: str
    path_key: str
    content_type: str
    cover_image: Optional[str] = None
    reading_time_minutes: Optional[int] = None
    tags: list = Field(default_factory=list)
    view_count: int = 0
    created_at: str


class ContentDetail(ContentListItem):
    status: str
    markdown_body: Optional[str] = None
    updated_at: Optional[str] = None


class ContentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content_type: str = "tutorial"
    markdown_body: str = ""
    status: Optional[str] = None
    cover_image: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    reading_time_minutes: Optional[int] = None


class ContentUpdateRequest(ContentCreateRequest):
    """更新请求，字段与创建相同"""
    pass


class NavItem(BaseModel):
    title: str
    slug: str
    path_key: str
    reading_time_minutes: Optional[int] = None


class NavGroup(BaseModel):
    category: str
    items: list[NavItem]


class PaginatedContents(PaginatedResponse[ContentListItem]):
    """内容列表分页响应（后台）"""
    pass
