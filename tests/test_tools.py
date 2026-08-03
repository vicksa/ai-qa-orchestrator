
import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from aiqa.agent.tools import BrowserToolExecutor, SelectorNotFoundError


def test_navigate(mock_page):
    mock_page.url = "https://example.test/dashboard"
    executor = BrowserToolExecutor(mock_page)

    result = executor.execute("navigate", {"url": "https://example.test/dashboard"})

    mock_page.goto.assert_called_once_with("https://example.test/dashboard", timeout=10000)
    assert not result.is_error
    assert "https://example.test/dashboard" in result.output


def test_click_success(mock_page):
    executor = BrowserToolExecutor(mock_page)

    result = executor.execute("click", {"selector": "#submit", "description": "the submit button"})

    mock_page.locator.assert_called_once_with("#submit")
    mock_page.locator.return_value.click.assert_called_once_with(timeout=5000)
    assert not result.is_error


def test_click_missing_selector_raises_selector_not_found(mock_page):
    mock_page.locator.return_value.click.side_effect = PlaywrightTimeoutError("timeout")
    executor = BrowserToolExecutor(mock_page)

    with pytest.raises(SelectorNotFoundError) as exc_info:
        executor.execute("click", {"selector": "#missing", "description": "the missing button"})

    assert exc_info.value.selector == "#missing"
    assert exc_info.value.description == "the missing button"


def test_fill_success(mock_page):
    executor = BrowserToolExecutor(mock_page)

    result = executor.execute(
        "fill", {"selector": "#username", "value": "victoria", "description": "the username field"}
    )

    mock_page.locator.return_value.fill.assert_called_once_with("victoria", timeout=5000)
    assert "username" in result.output


def test_assert_text_pass(mock_page):
    mock_page.locator.return_value.inner_text.return_value = "Welcome, Victoria!"
    executor = BrowserToolExecutor(mock_page)

    result = executor.execute(
        "assert_text",
        {"selector": "h1", "expected_text": "Welcome", "description": "the welcome banner"},
    )

    assert not result.is_error


def test_assert_text_fail(mock_page):
    mock_page.locator.return_value.inner_text.return_value = "Something else"
    executor = BrowserToolExecutor(mock_page)

    result = executor.execute(
        "assert_text",
        {"selector": "h1", "expected_text": "Welcome", "description": "the welcome banner"},
    )

    assert result.is_error
    assert "Assertion failed" in result.output


def test_get_dom_full_page(mock_page):
    mock_page.content.return_value = "<html><body>hi</body></html>"
    executor = BrowserToolExecutor(mock_page)

    result = executor.execute("get_dom", {})

    assert result.output == "<html><body>hi</body></html>"


def test_get_dom_truncates_long_output(mock_page):
    mock_page.content.return_value = "x" * 20000
    executor = BrowserToolExecutor(mock_page)

    result = executor.execute("get_dom", {})

    assert len(result.output) < 20000
    assert result.output.endswith("<!-- truncated -->")


def test_finish_test(mock_page):
    executor = BrowserToolExecutor(mock_page)

    result = executor.execute("finish_test", {"passed": True, "summary": "all good"})

    assert not result.is_error
    assert "PASSED" in result.output


def test_unknown_tool_returns_error(mock_page):
    executor = BrowserToolExecutor(mock_page)

    result = executor.execute("teleport", {})

    assert result.is_error
