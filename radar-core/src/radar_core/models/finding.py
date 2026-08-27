from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from radar_core.enums import Confidence, EvidenceType, FindingSeverity, FindingStatus, HumanVerdict
from radar_core.types import UTCDateTime


class Finding(SQLModel, table=True):
    __tablename__ = "finding"

    id: int | None = Field(default=None, primary_key=True)
    scoring_run_id: int = Field(foreign_key="scoring_run.id", index=True)
    criterion_id: int = Field(foreign_key="criterion.id", index=True)
    tool_result_id: int | None = Field(default=None, foreign_key="tool_result.id", index=True)
    severity: FindingSeverity = Field(
        sa_column=Column(
            SAEnum(
                FindingSeverity,
                create_constraint=True,
                validate_strings=True,
                name="ck_finding_severity_valid",
            ),
            nullable=False,
        )
    )
    description: str
    file: str | None = None
    line: int | None = None
    estimated_effort: str | None = None
    confidence: Confidence = Field(
        sa_column=Column(
            SAEnum(
                Confidence,
                create_constraint=True,
                validate_strings=True,
                name="ck_finding_confidence_valid",
            ),
            nullable=False,
        )
    )
    status: FindingStatus = Field(
        default=FindingStatus.OPEN,
        sa_column=Column(
            SAEnum(
                FindingStatus,
                create_constraint=True,
                validate_strings=True,
                name="ck_finding_status_valid",
            ),
            nullable=False,
        ),
    )
    human_verdict: HumanVerdict = Field(
        default=HumanVerdict.UNREVIEWED,
        sa_column=Column(
            SAEnum(
                HumanVerdict,
                create_constraint=True,
                validate_strings=True,
                name="ck_finding_human_verdict_valid",
            ),
            nullable=False,
        ),
    )
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime(), nullable=False),
    )


class Evidence(SQLModel, table=True):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "(finding_id IS NOT NULL) + (score_id IS NOT NULL) = 1",
            name="ck_evidence_exactly_one_parent",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    finding_id: int | None = Field(default=None, foreign_key="finding.id", index=True)
    score_id: int | None = Field(default=None, foreign_key="score.id", index=True)
    evidence_type: EvidenceType = Field(
        sa_column=Column(
            SAEnum(
                EvidenceType,
                create_constraint=True,
                validate_strings=True,
                name="ck_evidence_evidence_type_valid",
            ),
            nullable=False,
        )
    )
    content: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime(), nullable=False),
    )


class Recommendation(SQLModel, table=True):
    __tablename__ = "recommendation"

    id: int | None = Field(default=None, primary_key=True)
    finding_id: int = Field(foreign_key="finding.id", index=True)
    text: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime(), nullable=False),
    )
