from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from radar_core.types import UTCDateTime


class Repository(SQLModel, table=True):
    __tablename__ = "repository"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    path: str = Field(unique=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime()),
    )
