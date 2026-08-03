"""Self-healing: when a selector can't be located, ask the model for a replacement
using a fresh DOM snapshot, then retry the failed tool call once with the new selector.
"""

from dataclasses import dataclass

from aiqa.agent import llm_client
from aiqa.agent.tools import MAX_DOM_CHARS, BrowserToolExecutor, SelectorNotFoundError, ToolResult


@dataclass
class HealAttempt:
    original_selector: str
    healed_selector: str
    reasoning: str
    result: ToolResult


def heal_and_retry(
    executor: BrowserToolExecutor,
    tool_name: str,
    tool_input: dict,
    error: SelectorNotFoundError,
) -> HealAttempt:
    """Propose a replacement selector for `error` and re-run the same tool call with it.

    Raises SelectorNotFoundError again if the healed selector also fails to locate.
    """
    dom = executor.page.content()
    if len(dom) > MAX_DOM_CHARS:
        dom = dom[:MAX_DOM_CHARS] + "\n<!-- truncated -->"

    fix = llm_client.propose_selector_fix(
        description=error.description,
        dom_snapshot=dom,
        broken_selector=error.selector,
    )

    healed_input = dict(tool_input)
    healed_input["selector"] = fix["selector"]
    result = executor.execute(tool_name, healed_input)

    return HealAttempt(
        original_selector=error.selector,
        healed_selector=fix["selector"],
        reasoning=fix["reasoning"],
        result=result,
    )
