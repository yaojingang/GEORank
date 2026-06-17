"""
方案对话 Schemas
"""
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    diagnostic_report_id: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    recommended_companies: list = Field(default_factory=list)


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    recommended_companies: Optional[list] = None
    created_at: str


class ConversationListItem(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: str
    messages: list[MessageOut]
