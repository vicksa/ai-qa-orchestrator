from dataclasses import dataclass, field
from unittest.mock import patch

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from aiqa.agent import orchestrator
from aiqa.config import settings


@dataclass
class FakeBlock:
    type: str
    name: str = ""
    input: dict = field(default_factory=dict)
    id: str = ""
    text: str = ""


@dataclass
class FakeMessage:
    content: list
    stop_reason: str = "tool_use"


def test_run_scenario_happy_path(mock_page):
    responses = [
        FakeMessage(content=[FakeBlock(type="tool_use", name="navigate", id="t1", input={"url": "https://x.test"})]),
        FakeMessage(
            content=[
                FakeBlock(
                    type="tool_use",
                    name="click",
                    id="t2",
                    input={"selector": "#login", "description": "the login button"},
                )
            ]
        ),
        FakeMessage(
            content=[
                FakeBlock(
                    type="tool_use",
                    name="finish_test",
                    id="t3",
                    input={"passed": True, "summary": "Logged in successfully."},
                )
            ]
        ),
    ]

    with patch("aiqa.agent.orchestrator.llm_client.create_message", side_effect=responses):
        result = orchestrator.run_scenario(mock_page, "Log in as a user", "https://x.test")

    assert result.passed is True
    assert result.summary == "Logged in successfully."
    assert [s.tool_name for s in result.steps] == ["navigate", "click", "finish_test"]
    assert result.healing_events == []


def test_run_scenario_heals_broken_selector(mock_page):
    mock_page.locator.return_value.click.side_effect = [PlaywrightTimeoutError("timeout"), None]

    responses = [
        FakeMessage(
            content=[
                FakeBlock(
                    type="tool_use",
                    name="click",
                    id="t1",
                    input={"selector": "#old-id", "description": "the checkout button"},
                )
            ]
        ),
        FakeMessage(
            content=[
                FakeBlock(
                    type="tool_use",
                    name="finish_test",
                    id="t2",
                    input={"passed": True, "summary": "Checked out despite a selector change."},
                )
            ]
        ),
    ]

    with (
        patch("aiqa.agent.orchestrator.llm_client.create_message", side_effect=responses),
        patch(
            "aiqa.agent.healing.llm_client.propose_selector_fix",
            return_value={"selector": "[data-testid='checkout']", "reasoning": "stable attribute"},
        ),
    ):
        result = orchestrator.run_scenario(mock_page, "Check out", "https://x.test")

    assert result.passed is True
    assert len(result.healing_events) == 1
    assert result.healing_events[0].original_selector == "#old-id"
    assert result.healing_events[0].healed_selector == "[data-testid='checkout']"
    assert result.steps[0].tool_input["selector"] == "[data-testid='checkout']"


def test_run_scenario_stops_when_agent_gives_no_tool_call(mock_page):
    responses = [
        FakeMessage(
            content=[FakeBlock(type="text", text="I'm not sure what to do.")],
            stop_reason="end_turn",
        )
    ]

    with patch("aiqa.agent.orchestrator.llm_client.create_message", side_effect=responses):
        result = orchestrator.run_scenario(mock_page, "Do something vague", "https://x.test")

    assert result.passed is False
    assert "without calling finish_test" in result.summary


def test_run_scenario_exceeds_max_turns(mock_page, monkeypatch):
    monkeypatch.setattr(settings, "max_agent_turns", 2)

    def always_get_dom(*_args, **_kwargs):
        return FakeMessage(content=[FakeBlock(type="tool_use", name="get_dom", id="t", input={})])

    with patch("aiqa.agent.orchestrator.llm_client.create_message", side_effect=always_get_dom):
        result = orchestrator.run_scenario(mock_page, "Loop forever", "https://x.test")

    assert result.passed is False
    assert "exceeded the maximum number of turns" in result.summary
    assert len(result.steps) == 2
