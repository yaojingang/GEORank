"""
SQLAlchemy enum helpers.

PostgreSQL stores our enum labels in lowercase value form. These helpers keep
ORM writes aligned with the Alembic-created enum definitions.
"""
from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
