# ai-qa-orchestrator

An AI agent that turns a plain-language test scenario into a real browser test run — plans
the steps, drives Playwright through tool calls, **self-heals selectors that break**, and
reports the whole run (including what it healed and why) through a FastAPI dashboard.

## Why this matters

Browser test suites rot the moment a `data-testid` gets renamed or a button moves inside a
new wrapper `<div>`. Traditional E2E suites fail hard on that kind of change even though the
underlying user flow still works — someone has to notice the red build, open the diff, and
manually update a selector. This project treats that as something an agent can do inline: when
a step's selector doesn't resolve, the agent takes a fresh DOM snapshot, asks the model for a
replacement selector grounded in the actual page, retries once, and — if that works — logs the
healing event instead of failing the run. You get a test suite that survives incidental UI
churn, with a full audit trail of every time it had to adapt.

It's also a small, complete example of an agentic system built directly on the Claude API
(not a framework): a manual tool-use loop, a constrained structured-output call for the
healing step, an async execution layer (FastAPI + Celery + Redis) so slow browser runs don't
block the API, and a persistence layer that turns each run into a reviewable report.

## Architecture

```
                    ┌─────────────────────────┐
   POST /runs  ───▶ │   FastAPI (aiqa.api)     │ ───▶ Postgres/SQLite
                    │   dashboard + REST API   │        (runs, steps,
                    └───────────┬─────────────┘         healing events)
                                │ enqueues
                                ▼
                    ┌─────────────────────────┐
                    │  Celery worker + Redis   │
                    │  aiqa.worker.tasks       │
                    └───────────┬─────────────┘
                                │ drives
                                ▼
                    ┌─────────────────────────┐        ┌───────────────────┐
                    │  Agent orchestrator      │ ─────▶ │  Claude (Opus 5)   │
                    │  aiqa.agent.orchestrator │ ◀───── │  tool-use loop     │
                    └───────────┬─────────────┘        └───────────────────┘
                                │ tool calls (navigate/click/fill/assert/get_dom)
                                ▼
                    ┌─────────────────────────┐
                    │  Playwright (Chromium)   │
                    └─────────────────────────┘
                                │ on a broken selector
                                ▼
                    ┌─────────────────────────┐        ┌───────────────────┐
                    │  Self-healing            │ ─────▶ │  Claude (structured │
                    │  aiqa.agent.healing      │ ◀───── │  output: new       │
                    │                          │        │  selector + why)    │
                    └─────────────────────────┘        └───────────────────┘
```

**Why an agent instead of a fixed script generator:** a codegen approach (turn NL into a
Playwright script once, run the script forever) has no path to recovering from a page that
changed under it. Running the model live during execution — with tools instead of generated
code — means the same agent that planned the flow can re-plan the one step that broke,
without re-deriving the whole test.

## Install

```bash
pip install -e ".[dev]"
playwright install --with-deps chromium
cp .env.example .env   # then set ANTHROPIC_API_KEY
```

## Run locally

Everything needed to execute a run: Redis (broker), the Celery worker, and the API.

```bash
docker compose up -d redis postgres   # or point DATABASE_URL at your own Postgres/SQLite
celery -A aiqa.worker.celery_app worker --loglevel=info &
uvicorn aiqa.api.main:app --reload
```

Then open `http://localhost:8000` for the dashboard, or submit a run directly:

```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
        "scenario": "Go to the login page, sign in with the demo account, and confirm the dashboard greeting shows the user'\''s name.",
        "target_url": "https://example.com/login"
      }'
```

`GET /runs/{id}` returns the run's JSON status; `GET /runs/{id}/report` renders it as an
HTML report with every step and any self-healing events.

See `examples/login_scenario.md` for a longer sample scenario.

## Docker

```bash
docker compose up --build
```

Brings up Postgres, Redis, the FastAPI app, and a Celery worker together. See
`docker-compose.yml` for service wiring and `.env.example` for the variables each one reads.

## Tests

```bash
pytest
ruff check .
```

Tests mock the LLM and the Playwright `Page` — no live browser, network access, or API key is
needed to run the suite.

## Project layout

```
src/aiqa/
  agent/         tool schemas, the Anthropic tool-use loop, self-healing
  api/           FastAPI app, routers, Jinja2 dashboard/report templates
  worker/        Celery task that runs a scenario and persists the result
  models.py      SQLModel tables (TestRun, TestStep, HealingEvent)
tests/           pytest suite (tools, healing, orchestrator, API, worker)
```

## License

MIT — see [LICENSE](./LICENSE).
