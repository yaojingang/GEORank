"""
Pydantic Schemas — 请求/响应模型
"""
from app.schemas.common import PaginatedResponse
from app.schemas.user import (
    RegisterRequest, LoginRequest, TokenResponse, UserOut, UserListResponse,
)
from app.schemas.company import (
    SubmitCompanyRequest, CompanyBrief, CompanyDetail,
    PaginatedCompanies, PipelineStatusResponse, VoteResponse, SimilarCompanyItem,
)
from app.schemas.diagnostic import (
    DiagnoseRequest, DiagnoseResponse, DiagnosticReportResponse, DiagnosticHistoryItem,
)
from app.schemas.conversation import (
    ChatRequest, ChatResponse, ConversationListItem, ConversationDetail, MessageOut,
)
from app.schemas.content import (
    ContentListItem, ContentDetail, ContentCreateRequest, ContentUpdateRequest, NavGroup,
)
from app.schemas.settings import SettingPublicResponse, SettingsUpdateRequest

__all__ = [
    "PaginatedResponse",
    "RegisterRequest", "LoginRequest", "TokenResponse", "UserOut", "UserListResponse",
    "SubmitCompanyRequest", "CompanyBrief", "CompanyDetail",
    "PaginatedCompanies", "PipelineStatusResponse", "VoteResponse", "SimilarCompanyItem",
    "DiagnoseRequest", "DiagnoseResponse", "DiagnosticReportResponse", "DiagnosticHistoryItem",
    "ChatRequest", "ChatResponse", "ConversationListItem", "ConversationDetail", "MessageOut",
    "ContentListItem", "ContentDetail", "ContentCreateRequest", "ContentUpdateRequest", "NavGroup",
    "SettingPublicResponse", "SettingsUpdateRequest",
]
