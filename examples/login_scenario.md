# Example scenario

A scenario is just plain language — the agent plans out the actual tool calls
(`navigate`, `click`, `fill`, `assert_text`, `get_dom`) itself.

```json
{
  "target_url": "https://example.com/login",
  "scenario": "Go to the login page. Fill in the email field with 'demo@example.com' and the password field with 'demo-password-123'. Click the Log In button. Once the page loads, confirm the dashboard heading contains the word 'Welcome'."
}
```

Submit it:

```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d @- <<'JSON'
{
  "target_url": "https://example.com/login",
  "scenario": "Go to the login page. Fill in the email field with 'demo@example.com' and the password field with 'demo-password-123'. Click the Log In button. Once the page loads, confirm the dashboard heading contains the word 'Welcome'."
}
JSON
```

The response carries the run's `id`. Track it with:

```bash
curl http://localhost:8000/runs/<id>
```

Or open `http://localhost:8000/runs/<id>/report` for the human-readable report,
including any selectors the agent had to self-heal along the way.

## What "self-healing" looks like in practice

If the login form's submit button is renamed from `#login-btn` to
`data-testid="submit-login"` between when the scenario was written and when it
runs, a naive selector-based test breaks. This agent instead:

1. Tries `#login-btn`, gets a locator timeout.
2. Takes a fresh DOM snapshot of the page as it exists right now.
3. Asks the model for a new selector, given the element's plain-language
   description ("the Log In button") and the live HTML.
4. Retries the click with the new selector.
5. Logs the substitution as a `HealingEvent` — visible on the report page —
   instead of silently failing the run.

If the healed selector also fails, the step is reported as a normal failure;
healing gets exactly one retry, not an unbounded loop.
