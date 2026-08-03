import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, Relationship, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RunStatus(StrEnum):
    pending = "pending"
    running = "running"
    passed = "passed"
    failed = "failed"
    error = "error"


class TestRun(SQLModel, table=True):
    __test__ = False  # not a pytest test case — this is the "test run" domain model

    id: str = Field(default_factory=_uuid, primary_key=True)
    scenario: str
    target_url: str
    status: RunStatus = Field(default=RunStatus.pending)
    summary: str | None = Field(default=None)
    celery_task_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = Field(default=None)

    steps: list["TestStep"] = Relationship(
        back_populates="run",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "TestStep.index"},
    )
    healing_events: list["HealingEvent"] = Relationship(
        back_populates="run",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "HealingEvent.index"},
    )


class TestStep(SQLModel, table=True):
    __test__ = False  # not a pytest test case

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(foreign_key="testrun.id", index=True)
    index: int
    tool_name: str
    tool_input: str
    result: str
    is_error: bool = Field(default=False)
    screenshot_path: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)

    run: TestRun = Relationship(back_populates="steps")


class HealingEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(foreign_key="testrun.id", index=True)
    index: int
    original_selector: str
    healed_selector: str
    reasoning: str
    created_at: datetime = Field(default_factory=_utcnow)

    run: TestRun = Relationship(back_populates="healing_events")
