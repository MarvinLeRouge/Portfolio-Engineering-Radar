from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from radar_core.enums import Confidence, ScoreLevel
from radar_core.types import UTCDateTime


class ScoringRun(SQLModel, table=True):
    __tablename__ = "scoring_run"
    __table_args__ = (
        UniqueConstraint(
            "audit_id", "methodology_version_id", name="uq_scoringrun_audit_methodology"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    audit_id: int = Field(foreign_key="audit.id", index=True)
    methodology_version_id: int = Field(foreign_key="methodology_version.id", index=True)
    scored_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_column=Column(UTCDateTime(), nullable=False)
    )
    global_score: float | None = None
    global_confidence: Confidence | None = Field(
        default=None,
        sa_column=Column(
            SAEnum(
                Confidence,
                create_constraint=True,
                validate_strings=True,
                name="ck_scoring_run_global_confidence_valid",
            ),
            nullable=True,
        ),
    )


class Score(SQLModel, table=True):
    __tablename__ = "score"

    id: int | None = Field(default=None, primary_key=True)
    scoring_run_id: int = Field(foreign_key="scoring_run.id", index=True)
    criterion_id: int | None = Field(default=None, foreign_key="criterion.id", index=True)
    category_id: int | None = Field(default=None, foreign_key="category.id", index=True)
    level: ScoreLevel = Field(
        sa_column=Column(
            SAEnum(
                ScoreLevel,
                create_constraint=True,
                validate_strings=True,
                name="ck_score_level_valid",
            ),
            nullable=False,
        )
    )
    value: float
    confidence: Confidence = Field(
        sa_column=Column(
            SAEnum(
                Confidence,
                create_constraint=True,
                validate_strings=True,
                name="ck_score_confidence_valid",
            ),
            nullable=False,
        )
    )
    na_reason: str | None = None
