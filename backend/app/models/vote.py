"""
公司投票去重表
UNIQUE(company_id, user_id) — 每个用户对每家公司只能投票一次
"""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CompanyVote(Base):
    __tablename__ = "company_votes"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", name="uq_company_user_vote"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
