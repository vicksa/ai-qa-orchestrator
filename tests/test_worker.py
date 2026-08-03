from sqlmodel import select

from aiqa.agent.orchestrator import HealingRecord, RunResult, StepRecord
from aiqa.models import HealingEvent, RunStatus, TestRun, TestStep
from aiqa.worker.tasks import _persist_result


def test_persist_result_writes_steps_and_healing_events(session):
    run = TestRun(scenario="Log in", target_url="https://x.test")
    session.add(run)
    session.commit()
    session.refresh(run)

    result = RunResult(
        passed=True,
        summary="All good.",
        steps=[
            StepRecord(
                index=0,
                tool_name="navigate",
                tool_input={"url": "https://x.test"},
                result="ok",
                is_error=False,
            ),
            StepRecord(
                index=1,
                tool_name="finish_test",
                tool_input={"passed": True},
                result="PASSED",
                is_error=False,
            ),
        ],
        healing_events=[
            HealingRecord(
                index=0,
                original_selector="#a",
                healed_selector="#b",
                reasoning="better selector",
            ),
        ],
    )

    _persist_result(session, run, result)
    session.commit()

    steps = list(session.exec(select(TestStep).where(TestStep.run_id == run.id)))
    heals = list(session.exec(select(HealingEvent).where(HealingEvent.run_id == run.id)))

    assert len(steps) == 2
    assert len(heals) == 1
    assert run.status == RunStatus.passed
    assert run.summary == "All good."
    assert run.finished_at is not None
