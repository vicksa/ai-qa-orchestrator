from types import SimpleNamespace

from aiqa.api.routers import runs as runs_module
from aiqa.models import RunStatus, TestRun


def _stub_dispatch(monkeypatch):
    """Replace the Celery dispatch so API tests never touch Redis/Playwright/the LLM."""
    calls = []

    def fake_delay(run_id):
        calls.append(run_id)
        return SimpleNamespace(id="fake-task-id")

    monkeypatch.setattr(runs_module.execute_test_run, "delay", fake_delay)
    return calls


def test_create_run_returns_pending_and_dispatches(client, monkeypatch):
    calls = _stub_dispatch(monkeypatch)

    response = client.post(
        "/runs", json={"scenario": "Log in and check the dashboard loads", "target_url": "https://x.test"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["id"]
    assert calls == [body["id"]]


def test_get_run_not_found(client):
    response = client.get("/runs/does-not-exist")
    assert response.status_code == 404


def test_get_run_returns_details(client, session, monkeypatch):
    _stub_dispatch(monkeypatch)
    run = TestRun(
        scenario="Sign up flow", target_url="https://x.test", status=RunStatus.passed, summary="ok"
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    response = client.get(f"/runs/{run.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["scenario"] == "Sign up flow"
    assert body["status"] == "passed"


def test_list_runs(client, session, monkeypatch):
    _stub_dispatch(monkeypatch)
    session.add(TestRun(scenario="A", target_url="https://x.test"))
    session.add(TestRun(scenario="B", target_url="https://y.test"))
    session.commit()

    response = client.get("/runs")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_run_report_page_renders(client, session):
    run = TestRun(
        scenario="Checkout flow",
        target_url="https://x.test",
        status=RunStatus.failed,
        summary="oops",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    response = client.get(f"/runs/{run.id}/report")

    assert response.status_code == 200
    assert "Checkout flow" in response.text
    assert "failed" in response.text


def test_dashboard_renders_with_no_runs(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "AI QA Orchestrator" in response.text


def test_dashboard_renders_with_runs(client, session):
    session.add(TestRun(scenario="A", target_url="https://x.test", status=RunStatus.passed))
    session.add(TestRun(scenario="B", target_url="https://y.test", status=RunStatus.failed))
    session.commit()

    response = client.get("/")

    assert response.status_code == 200
    assert "50%" in response.text
