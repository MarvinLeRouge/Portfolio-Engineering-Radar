from __future__ import annotations

from sqlmodel import Field, SQLModel


class FindingImprovementTaskLink(SQLModel, table=True):
    __tablename__ = "finding_improvement_task_link"

    finding_id: int = Field(foreign_key="finding.id", primary_key=True)
    improvement_task_id: int = Field(foreign_key="improvement_task.id", primary_key=True)
