from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from radar_core.enums import RoadmapStatus
from radar_core.types import UTCDateTime


class ImprovementTask(SQLModel, table=True):
    __tablename__ = "improvement_task"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime(), nullable=False),
    )


class RoadmapItem(SQLModel, table=True):
    __tablename__ = "roadmap_item"

    id: int | None = Field(default=None, primary_key=True)
    improvement_task_id: int = Field(foreign_key="improvement_task.id", unique=True, index=True)
    status: RoadmapStatus = Field(
        default=RoadmapStatus.TODO,
        sa_column=Column(
            SAEnum(
                RoadmapStatus,
                create_constraint=True,
                validate_strings=True,
                name="ck_roadmap_item_status_valid",
            ),
            nullable=False,
        ),
    )
    priority: int
    estimated_effort: str | None = None
    estimated_impact: str | None = None
    promoted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime(), nullable=False),
    )
    done_at: datetime | None = Field(default=None, sa_column=Column(UTCDateTime()))
    done_evidence_id: int | None = Field(default=None, foreign_key="evidence.id")
