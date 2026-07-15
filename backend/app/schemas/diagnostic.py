"""
诊断模块 Schemas
"""
from typing import Optional

from pydantic import BaseModel


class DiagnoseRequest(BaseModel):
    url: str
    company_id: Optional[str] = None


class DiagnoseResponse(BaseModel):
    report_id: str
    status: str


class DiagnosticHistoryItem(BaseModel):
    report_id: str
    url: str
    status: str
    overall_score: Optional[float] = None
    created_at: str


class DiagnosticReportResponse(BaseModel):
    report_id: str
    url: str
    company_id: Optional[str] = None
    status: str
    overall_score: Optional[float] = None
    schema_analysis: Optional[dict] = None
    content_analysis: Optional[dict] = None
    meta_analysis: Optional[dict] = None
    citation_analysis: Optional[dict] = None
    recommendations: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: str
