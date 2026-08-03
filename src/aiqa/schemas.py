from datetime import datetime

from pydantic import BaseModel, Field

from aiqa.models import RunStatus


class RunCreateRequest(BaseModel):
    scenario: str = Field(..., min_length=1, description="Natural-language test scenario")
    target_url: str = Field(..., min_length=1, description="URL the scenario runs against")


class RunCreateResponse(BaseModel):
    id: str
    status: RunStatus


class StepOut(BaseModel):
    index: int
    tool_name: str
    tool_input: str
    result: str
    is_error: bool
    screenshot_path: str | None


class HealingEventOut(BaseModel):
    index: int
    original_selector: str
    healed_selector: str
    reasoning: str


class RunOut(BaseModel):
    id: str
    scenario: str
    target_url: str
    status: RunStatus
    summary: str | None
    created_at: datetime
    finished_at: datetime | None
    steps: list[StepOut] = []
    healing_events: list[HealingEventOut] = []
