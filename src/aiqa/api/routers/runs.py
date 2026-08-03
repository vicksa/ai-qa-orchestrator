from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from aiqa.api.templating import templates
from aiqa.db import get_session
from aiqa.models import RunStatus, TestRun
from aiqa.schemas import RunCreateRequest, RunCreateResponse, RunOut
from aiqa.worker.tasks import execute_test_run

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunCreateResponse, status_code=201)
def create_run(
    payload: RunCreateRequest, session: Session = Depends(get_session)
) -> RunCreateResponse:
    run = TestRun(scenario=payload.scenario, target_url=payload.target_url)
    session.add(run)
    session.commit()
    session.refresh(run)

    async_result = execute_test_run.delay(run.id)
    run.celery_task_id = async_result.id
    session.add(run)
    session.commit()

    return RunCreateResponse(id=run.id, status=run.status)


@router.get("", response_model=list[RunOut])
def list_runs(limit: int = 50, session: Session = Depends(get_session)) -> list[TestRun]:
    statement = select(TestRun).order_by(TestRun.created_at.desc()).limit(limit)
    return list(session.exec(statement))


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, session: Session = Depends(get_session)) -> TestRun:
    run = session.get(TestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{run_id}/report", response_class=HTMLResponse)
def get_run_report(
    run_id: str, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    run = session.get(TestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return templates.TemplateResponse(
        request=request,
        name="report.html",
        context={"run": run, "RunStatus": RunStatus},
    )
