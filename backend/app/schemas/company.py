"""
公司模块 Schemas
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import PaginatedResponse


class SubmitCompanyRequest(BaseModel):
    url: str = Field(description="公司官网 URL")


class CompanyBrief(BaseModel):
    id: str
    path_key: Optional[str] = None
    name: str
    url: str
    logo_url: Optional[str] = None
    short_description: Optional[str] = None
    category: Optional[str] = None
    tags: list = Field(default_factory=list)
    geo_score: Optional[float] = None
    is_geo_certified: bool = False
    tech_level: Optional[str] = None
    funding_stage: Optional[str] = None
    headquarters: Optional[str] = None
    pipeline_status: str
    publish_status: str
    upvotes: int = 0

    model_config = {"from_attributes": True}


class CompanyDetail(CompanyBrief):
    description: Optional[str] = None
    employee_count: Optional[str] = None
    founded_date: Optional[str] = None
    geo_details: Optional[dict] = None
    tech_stack: list = Field(default_factory=list)
    team_members: list = Field(default_factory=list)
    pipeline_error: Optional[str] = None

    model_config = {"from_attributes": True}


class PaginatedCompanies(PaginatedResponse[CompanyBrief]):
    """公司列表分页响应"""
    pass


class CompanyAdminBrief(BaseModel):
    """后台公司列表项（含 pipeline_error）"""
    id: str
    name: str
    url: str
    short_description: Optional[str] = None
    category: Optional[str] = None
    pipeline_status: str
    pipeline_error: Optional[str] = None
    publish_status: str
    geo_score: Optional[float] = None
    created_at: str


class PaginatedCompaniesAdmin(PaginatedResponse[CompanyAdminBrief]):
    """后台公司列表分页响应"""
    pass


class SubmitCompanyResponse(BaseModel):
    company_id: str
    status: str
    message: str
    normalized_url: Optional[str] = None
    publish_status: Optional[str] = None
    resumed: bool = False


class PipelineSelectedPage(BaseModel):
    url: str
    title: Optional[str] = None
    role: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None


class PipelineStatusResponse(BaseModel):
    company_id: str
    status: str
    progress: int
    error: Optional[str] = None
    current_activity: Optional[str] = None
    publish_status: Optional[str] = None
    company_name: Optional[str] = None
    company_summary: Optional[str] = None
    selected_pages: list[PipelineSelectedPage] = Field(default_factory=list)


class VoteResponse(BaseModel):
    upvotes: int


class SimilarCompanyItem(BaseModel):
    id: str
    path_key: Optional[str] = None
    name: str
    short_description: Optional[str] = None
    logo_url: Optional[str] = None
    geo_score: Optional[float] = None
    category: Optional[str] = None
