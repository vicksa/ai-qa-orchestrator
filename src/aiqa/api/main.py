from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, func, select

from aiqa.api.routers.runs import router as runs_router
from aiqa.api.templating import templates
from aiqa.db import get_session, init_db
from aiqa.models import HealingEvent, RunStatus, TestRun

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="AI QA Orchestrator", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(runs_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    runs = list(session.exec(select(TestRun).order_by(TestRun.created_at.desc()).limit(50)))
    finished = [r for r in runs if r.status in (RunStatus.passed, RunStatus.failed)]
    passed = sum(1 for r in finished if r.status == RunStatus.passed)
    pass_rate = round(100 * passed / len(finished)) if finished else None

    total_heals = session.exec(select(func.count(HealingEvent.id))).one()

    durations = [
        (r.finished_at - r.created_at).total_seconds()
        for r in finished
        if r.finished_at is not None
    ]
    avg_duration = round(sum(durations) / len(durations)) if durations else None

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "runs": runs,
            "total": len(runs),
            "pass_rate": pass_rate,
            "total_heals": total_heals,
            "avg_duration": avg_duration,
        },
    )
