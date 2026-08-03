"""Browser tool schemas and the executor that binds them to a live Playwright page.

Selector-locating tools (click/fill/assert_text/wait_for) raise SelectorNotFoundError
on timeout instead of the raw Playwright error — the orchestrator catches that specific
exception to trigger self-healing.
"""

from dataclasses import dataclass
from typing import Any

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

DEFAULT_TIMEOUT_MS = 5000

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "navigate",
        "description": "Navigate the browser to a URL (absolute, or relative to the current page).",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "click",
        "description": "Click an element located by a CSS selector.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the element"},
                "description": {
                    "type": "string",
                    "description": "Plain-language description of the element, used to "
                    "re-locate it if the selector breaks (e.g. 'the blue Submit button').",
                },
            },
            "required": ["selector", "description"],
        },
    },
    {
        "name": "fill",
        "description": "Type a value into an input/textarea located by a CSS selector.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the field"},
                "value": {"type": "string"},
                "description": {
                    "type": "string",
                    "description": "Plain-language description of the field, used to "
                    "re-locate it if the selector breaks (e.g. 'the Username field').",
                },
            },
            "required": ["selector", "value", "description"],
        },
    },
    {
        "name": "assert_text",
        "description": "Assert that an element's visible text contains the expected substring. "
        "Fails the test step if it does not.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "expected_text": {"type": "string"},
                "description": {
                    "type": "string",
                    "description": "Plain-language description of the element.",
                },
            },
            "required": ["selector", "expected_text", "description"],
        },
    },
    {
        "name": "get_dom",
        "description": "Return a trimmed HTML snapshot of the current page (or a subtree), "
        "for inspecting available elements and selectors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "Optional CSS selector to scope the snapshot to a subtree.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "finish_test",
        "description": "Signal that the scenario is complete. Call this exactly once, as the "
        "last tool call, with the final pass/fail verdict.",
        "input_schema": {
            "type": "object",
            "properties": {
                "passed": {"type": "boolean"},
                "summary": {
                    "type": "string",
                    "description": "One or two sentences on the outcome.",
                },
            },
            "required": ["passed", "summary"],
        },
    },
]

MAX_DOM_CHARS = 8000


class SelectorNotFoundError(Exception):
    """Raised when a Playwright locator times out — the healing-eligible failure mode."""

    def __init__(self, selector: str, description: str):
        self.selector = selector
        self.description = description
        super().__init__(f"Element not found for selector {selector!r} ({description})")


@dataclass
class ToolResult:
    output: str
    is_error: bool = False


class BrowserToolExecutor:
    """Dispatches tool_use blocks to Playwright actions against a single page."""

    def __init__(self, page: Page, timeout_ms: int = DEFAULT_TIMEOUT_MS):
        self.page = page
        self.timeout_ms = timeout_ms

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        handler = getattr(self, f"_tool_{tool_name}", None)
        if handler is None:
            return ToolResult(output=f"Unknown tool: {tool_name}", is_error=True)
        return handler(tool_input)

    def _tool_navigate(self, tool_input: dict[str, Any]) -> ToolResult:
        self.page.goto(tool_input["url"], timeout=self.timeout_ms * 2)
        return ToolResult(output=f"Navigated to {self.page.url}")

    def _tool_click(self, tool_input: dict[str, Any]) -> ToolResult:
        selector, description = tool_input["selector"], tool_input["description"]
        try:
            self.page.locator(selector).click(timeout=self.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise SelectorNotFoundError(selector, description) from exc
        return ToolResult(output=f"Clicked {selector!r}")

    def _tool_fill(self, tool_input: dict[str, Any]) -> ToolResult:
        selector = tool_input["selector"]
        value = tool_input["value"]
        description = tool_input["description"]
        try:
            self.page.locator(selector).fill(value, timeout=self.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise SelectorNotFoundError(selector, description) from exc
        return ToolResult(output=f"Filled {selector!r} with {value!r}")

    def _tool_assert_text(self, tool_input: dict[str, Any]) -> ToolResult:
        selector = tool_input["selector"]
        expected = tool_input["expected_text"]
        description = tool_input["description"]
        try:
            actual = self.page.locator(selector).inner_text(timeout=self.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise SelectorNotFoundError(selector, description) from exc
        if expected not in actual:
            return ToolResult(
                output=(
                    f"Assertion failed: expected {selector!r} to contain "
                    f"{expected!r}, got {actual!r}"
                ),
                is_error=True,
            )
        return ToolResult(output=f"Assertion passed: {selector!r} contains {expected!r}")

    def _tool_get_dom(self, tool_input: dict[str, Any]) -> ToolResult:
        selector = tool_input.get("selector")
        html = self.page.locator(selector).first.inner_html() if selector else self.page.content()
        if len(html) > MAX_DOM_CHARS:
            html = html[:MAX_DOM_CHARS] + "\n<!-- truncated -->"
        return ToolResult(output=html)

    def _tool_finish_test(self, tool_input: dict[str, Any]) -> ToolResult:
        verdict = "PASSED" if tool_input["passed"] else "FAILED"
        return ToolResult(output=f"{verdict}: {tool_input['summary']}")
