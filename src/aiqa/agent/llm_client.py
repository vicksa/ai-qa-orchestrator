"""Thin wrapper around the Anthropic SDK used by both the orchestrator and the healer."""

import json
from typing import Any

import anthropic

from aiqa.config import settings

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
    return _client


def create_message(
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> anthropic.types.Message:
    kwargs: dict[str, Any] = {
        "model": settings.anthropic_model,
        "max_tokens": 4096,
        "system": system,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
    return get_client().messages.create(**kwargs)


SELECTOR_FIX_SCHEMA = {
    "type": "object",
    "properties": {
        "selector": {
            "type": "string",
            "description": "A new CSS selector that should locate the element",
        },
        "reasoning": {
            "type": "string",
            "description": "One sentence on why this selector should work",
        },
    },
    "required": ["selector", "reasoning"],
    "additionalProperties": False,
}


def propose_selector_fix(
    description: str, dom_snapshot: str, broken_selector: str
) -> dict[str, str]:
    """Ask the model for a replacement CSS selector given a DOM snapshot.

    Returns {"selector": ..., "reasoning": ...}.
    """
    response = get_client().messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        output_config={"format": {"type": "json_schema", "schema": SELECTOR_FIX_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": (
                    "A browser test step failed because this CSS selector did not match "
                    f"any element: {broken_selector!r}\n\n"
                    f"The element it was supposed to target is described as: {description!r}\n\n"
                    "Here is the current page HTML (possibly truncated):\n"
                    f"```html\n{dom_snapshot}\n```\n\n"
                    "Propose a new CSS selector that will match the described element in this "
                    "HTML. Prefer stable attributes (id, data-testid, name, role) over brittle "
                    "positional or class-based selectors."
                ),
            }
        ],
    )
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)
