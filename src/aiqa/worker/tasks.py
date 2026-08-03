from datetime import UTC, datetime

from playwright.sync_api import sync_playwright
from sqlmodel import Session

from aiqa.agent.orchestrator import RunResult, run_scenario
from aiqa.config import settings
from aiqa.db import engine
from aiqa.models import HealingEvent, RunStatus, TestRun, TestStep
from aiqa.worker.celery_app import celery_app


def _persist_result(session: Session, run: TestRun, result: RunResult) -> None:
    for step in result.steps:
        session.add(
            TestStep(
                run_id=run.id,
                index=step.index,
                tool_name=step.tool_name,
                tool_input=str(step.tool_input),
                result=step.result,
                is_error=step.is_error,
            )
        )
    for heal in result.healing_events:
        session.add(
            HealingEvent(
                run_id=run.id,
                index=heal.index,
                original_selector=heal.original_selector,
                healed_selector=heal.healed_selector,
                reasoning=heal.reasoning,
            )
        )
    run.status = RunStatus.passed if result.passed else RunStatus.failed
    run.summary = result.summary
    run.finished_at = datetime.now(UTC)
    session.add(run)


@celery_app.task(name="aiqa.execute_test_run")
def execute_test_run(run_id: str) -> str:
    with Session(engine) as session:
        run = session.get(TestRun, run_id)
        if run is None:
            return f"run {run_id} not found"

        run.status = RunStatus.running
        session.add(run)
        session.commit()

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=settings.browser_headless)
                try:
                    page = browser.new_page()
                    result = run_scenario(page, run.scenario, run.target_url)
                finally:
                    browser.close()
        except Exception as exc:  # execution environment failure, not a test failure
            run.status = RunStatus.error
            run.summary = f"Run failed to execute: {exc}"
            run.finished_at = datetime.now(UTC)
            session.add(run)
            session.commit()
            raise

        _persist_result(session, run, result)
        session.commit()

    return run.status.value
