"""
用户与认证 Schemas
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.schemas.common import PaginatedResponse


class RegisterRequest(BaseModel):
    phone: Optional[str] = Field(default=None, min_length=6, max_length=30)
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(default=None, min_length=2, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    remember_me: bool = True

    @model_validator(mode="after")
    def validate_identifier_fields(self):
        if not self.phone and (not self.email or not self.username):
            raise ValueError("请提供手机号，或同时提供邮箱和用户名")
        return self


class LoginRequest(BaseModel):
    account: Optional[str] = None
    username: Optional[str] = None  # 兼容旧版字段
    phone: Optional[str] = Field(default=None, min_length=6, max_length=30)
    password: str
    remember_me: bool = True

    @model_validator(mode="after")
    def validate_login_identifier(self):
        if not (self.phone or self.account or self.username):
            raise ValueError("请提供手机号或账号")
        return self


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    username: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class UserListResponse(PaginatedResponse[UserOut]):
    """用户列表分页响应"""
    pass


class RoleUpdateRequest(BaseModel):
    role: str = Field(pattern="^(admin|enterprise|user)$")
