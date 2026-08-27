from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from radar_core.enums import ScoringModel
from radar_core.types import UTCDateTime


class MethodologyVersion(SQLModel, table=True):
    __tablename__ = "methodology_version"

    id: int | None = Field(default=None, primary_key=True)
    version_label: str = Field(unique=True, index=True)
    frozen_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime()),
    )
    notes: str | None = None


class Category(SQLModel, table=True):
    __tablename__ = "category"

    id: int | None = Field(default=None, primary_key=True)
    methodology_version_id: int = Field(foreign_key="methodology_version.id", index=True)
    name: str
    weight: float
    order: int


class Criterion(SQLModel, table=True):
    __tablename__ = "criterion"

    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    name: str
    description: str
    weight: float
    scoring_model: ScoringModel = Field(sa_column=Column(SAEnum(ScoringModel), nullable=False))
