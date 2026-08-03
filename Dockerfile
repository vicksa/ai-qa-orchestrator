# The playwright/python image tag must match the pinned "playwright" version in
# pyproject.toml — the Python package and the bundled browser build are versioned
# together and mismatches fail at runtime, not at build time.
FROM mcr.microsoft.com/playwright/python:v1.62.0-jammy

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "aiqa.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
