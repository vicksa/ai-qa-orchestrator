from unittest.mock import patch

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from aiqa.agent.healing import heal_and_retry
from aiqa.agent.tools import BrowserToolExecutor, SelectorNotFoundError


def test_heal_and_retry_succeeds_with_new_selector(mock_page):
    mock_page.content.return_value = "<html><button data-testid='submit-btn'>Submit</button></html>"
    executor = BrowserToolExecutor(mock_page)
    error = SelectorNotFoundError(selector="#submit", description="the submit button")

    with patch(
        "aiqa.agent.healing.llm_client.propose_selector_fix",
        return_value={
            "selector": "[data-testid='submit-btn']",
            "reasoning": "Element has a stable data-testid attribute.",
        },
    ) as mock_fix:
        attempt = heal_and_retry(
            executor,
            "click",
            {"selector": "#submit", "description": "the submit button"},
            error,
        )

    mock_fix.assert_called_once()
    assert mock_fix.call_args.kwargs["broken_selector"] == "#submit"
    assert mock_fix.call_args.kwargs["description"] == "the submit button"

    assert attempt.original_selector == "#submit"
    assert attempt.healed_selector == "[data-testid='submit-btn']"
    assert not attempt.result.is_error
    mock_page.locator.assert_called_with("[data-testid='submit-btn']")


def test_heal_and_retry_reraises_when_healed_selector_also_fails(mock_page):
    mock_page.content.return_value = "<html></html>"
    mock_page.locator.return_value.click.side_effect = PlaywrightTimeoutError("timeout")
    executor = BrowserToolExecutor(mock_page)
    error = SelectorNotFoundError(selector="#submit", description="the submit button")

    with patch(
        "aiqa.agent.healing.llm_client.propose_selector_fix",
        return_value={"selector": "#still-wrong", "reasoning": "best guess"},
    ):
        with pytest.raises(SelectorNotFoundError) as exc_info:
            heal_and_retry(
                executor,
                "click",
                {"selector": "#submit", "description": "the submit button"},
                error,
            )

    assert exc_info.value.selector == "#still-wrong"
