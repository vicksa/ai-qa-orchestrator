"""Runs a natural-language test scenario end to end: the LLM plans and calls browser
tools via the standard Anthropic tool-use loop; broken selectors trigger one self-heal
retry before being reported back to the model as a normal tool error.
"""

from dataclasses import dataclass, field

from playwright.sync_api import Page

from aiqa.agent import llm_client
from aiqa.agent.healing import heal_and_retry
from aiqa.agent.tools import TOOL_DEFINITIONS, BrowserToolExecutor, SelectorNotFoundError
from aiqa.config import settings

SYSTEM_PROMPT = """You are a QA automation agent. You control a real web browser through \
the provided tools to execute a test scenario described in plain language.

Rules:
- Start by navigating to the target URL if you are not already there.
- Use get_dom to inspect the page before guessing at a selector you are not sure of.
- Prefer stable selectors: id, data-testid, name, and ARIA attributes over positional \
or deeply nested class selectors.
- Treat a failed assert_text as a definitive test failure, not something to retry around.
- Call finish_test exactly once, as your final tool call, with a clear pass/fail verdict \
and a one- or two-sentence summary of what happened.
"""


@dataclass
class StepRecord:
    index: int
    tool_name: str
    tool_input: dict
    result: str
    is_error: bool


@dataclass
class HealingRecord:
    index: int
    original_selector: str
    healed_selector: str
    reasoning: str


@dataclass
class RunResult:
    passed: bool
    summary: str
    steps: list[StepRecord] = field(default_factory=list)
    healing_events: list[HealingRecord] = field(default_factory=list)


def _execute_with_healing(
    executor: BrowserToolExecutor,
    tool_name: str,
    tool_input: dict,
    healing_events: list[HealingRecord],
    step_index: int,
):
    """Runs one tool call. On a locator timeout, attempts one self-heal retry.
    Returns (result, effective_input)."""
    try:
        result = executor.execute(tool_name, tool_input)
        return result, tool_input
    except SelectorNotFoundError as err:
        try:
            heal = heal_and_retry(executor, tool_name, tool_input, err)
        except SelectorNotFoundError as second_err:
            from aiqa.agent.tools import ToolResult

            failure = ToolResult(
                output=(
                    f"Could not locate element for {err.description!r}: original selector "
                    f"{err.selector!r} failed, and the healed selector {second_err.selector!r} "
                    "also failed."
                ),
                is_error=True,
            )
            return failure, tool_input

        healing_events.append(
            HealingRecord(
                index=step_index,
                original_selector=heal.original_selector,
                healed_selector=heal.healed_selector,
                reasoning=heal.reasoning,
            )
        )
        return heal.result, {**tool_input, "selector": heal.healed_selector}


def run_scenario(page: Page, scenario: str, target_url: str) -> RunResult:
    executor = BrowserToolExecutor(page)
    steps: list[StepRecord] = []
    healing_events: list[HealingRecord] = []

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                f"Target URL: {target_url}\n\nScenario:\n{scenario}\n\n"
                "Begin by navigating to the target URL."
            ),
        }
    ]

    for _turn in range(settings.max_agent_turns):
        response = llm_client.create_message(SYSTEM_PROMPT, messages, tools=TOOL_DEFINITIONS)
        messages.append({"role": "assistant", "content": response.content})

        tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
        if not tool_use_blocks:
            return RunResult(
                passed=False,
                summary="Agent stopped without calling finish_test.",
                steps=steps,
                healing_events=healing_events,
            )

        tool_results = []
        finished: RunResult | None = None
        for block in tool_use_blocks:
            index = len(steps)
            result, effective_input = _execute_with_healing(
                executor, block.name, block.input, healing_events, index
            )
            steps.append(
                StepRecord(
                    index=index,
                    tool_name=block.name,
                    tool_input=effective_input,
                    result=result.output,
                    is_error=result.is_error,
                )
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result.output,
                    "is_error": result.is_error,
                }
            )
            if block.name == "finish_test":
                finished = RunResult(
                    passed=bool(block.input["passed"]),
                    summary=str(block.input["summary"]),
                    steps=steps,
                    healing_events=healing_events,
                )

        messages.append({"role": "user", "content": tool_results})

        if finished:
            return finished

    return RunResult(
        passed=False,
        summary="Agent exceeded the maximum number of turns without finishing.",
        steps=steps,
        healing_events=healing_events,
    )
