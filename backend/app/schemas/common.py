"""
通用分页响应模型
"""
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """通用分页 envelope"""
    items: list[T]
    total: int
    page: int
    size: int
    pages: int
