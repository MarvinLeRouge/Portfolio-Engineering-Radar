from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, Index, text
from sqlmodel import Field, SQLModel

from radar_core.types import UTCDateTime


class Audit(SQLModel, table=True):
    __tablename__ = "audit"
    __table_args__ = (
        Index(
            "ix_audit_repo_commit_clean",
            "repository_id",
            "commit_sha",
            unique=True,
            sqlite_where=text("is_dirty = 0"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    repository_id: int = Field(foreign_key="repository.id", index=True)
    commit_sha: str = Field(index=True)
    is_dirty: bool = False
    audited_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime()),
    )
    network_flags: dict = Field(default_factory=dict, sa_column=Column(JSON))


class ToolResult(SQLModel, table=True):
    __tablename__ = "tool_result"

    id: int | None = Field(default=None, primary_key=True)
    audit_id: int = Field(foreign_key="audit.id", index=True)
    tool_name: str = Field(index=True)
    tool_version: str
    command: str
    raw_output: dict = Field(sa_column=Column(JSON))
    exit_code: int
    ran_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(UTCDateTime()),
    )
    duration_ms: int
