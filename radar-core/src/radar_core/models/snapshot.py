from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from radar_core.enums import Confidence
from radar_core.types import UTCDateTime


class Snapshot(SQLModel, table=True):
    __tablename__ = "snapshot"

    id: int | None = Field(default=None, primary_key=True)
    taken_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime()),
    )
    portfolio_global_score: float
    portfolio_global_confidence: Confidence = Field(
        sa_column=Column(SAEnum(Confidence), nullable=False)
    )
    details: dict = Field(sa_column=Column(JSON))
