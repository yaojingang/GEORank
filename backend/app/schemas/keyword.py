"""
拓词模块 Schemas
"""
from typing import List

from pydantic import BaseModel, Field


class KeywordExpandRequest(BaseModel):
    seeds: List[str] = Field(default_factory=list, min_length=1, max_length=8)


class KeywordItemResponse(BaseModel):
    keyword: str
    recommendation_score: int
    business_score: int
    reason: str | None = None


class KeywordDimensionResponse(BaseModel):
    key: str
    name: str
    icon: str
    description: str
    count: int
    items: List[KeywordItemResponse]


class KeywordSummaryResponse(BaseModel):
    total_keywords: int
    average_recommendation_score: int
    average_business_score: int
    high_recommendation_ratio: int
    high_business_ratio: int


class KeywordProfileResponse(BaseModel):
    name: str
    company_hint: str
    business_model: str
    target_users: List[str]
    keyword_strategy: str


class KeywordExpandResponse(BaseModel):
    seeds: List[str]
    profile: KeywordProfileResponse
    dimensions: List[KeywordDimensionResponse]
    summary: KeywordSummaryResponse
