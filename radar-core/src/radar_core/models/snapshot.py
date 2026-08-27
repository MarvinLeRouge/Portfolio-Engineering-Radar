from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
        sa_column=Column(UTCDateTime(), nullable=False),
    )
    portfolio_global_score: float
    portfolio_global_confidence: Confidence = Field(
        sa_column=Column(
            SAEnum(
                Confidence,
                create_constraint=True,
                validate_strings=True,
                name="ck_snapshot_portfolio_global_confidence_valid",
            ),
            nullable=False,
        )
    )
    details: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
