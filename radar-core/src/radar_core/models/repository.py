from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, TypeDecorator
from sqlmodel import Field, SQLModel


class UTCDateTime(TypeDecorator):
    """DateTime type that ensures UTC timezone is preserved."""

    impl = DateTime
    cache_ok = True

    def __init__(self):
        super().__init__(timezone=False)

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is not None:
                # Convert to UTC if timezone-aware
                return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            # Add UTC timezone when retrieving from database
            return value.replace(tzinfo=UTC)
        return value


class Repository(SQLModel, table=True):
    __tablename__ = "repository"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    path: str = Field(unique=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime()),
    )
