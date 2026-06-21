# Build context is the repo root (see docker/open-langgraph/docker-compose.yml).
# Based on vendor/open-langgraph-platform/deployments/docker/Dockerfile, with
# `requests` (researcher's web_search tool) and `ruff` (reviewer's lint_python
# tool) added, and our own agents/ + open_langgraph.json baked in instead of
# their example graphs.
FROM python:3.13-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY vendor/open-langgraph-platform/pyproject.toml ./
COPY vendor/open-langgraph-platform/README.md ./
COPY vendor/open-langgraph-platform/src/ ./src/

RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir "." "requests>=2.34.2" "ruff>=0.15.18" \
    "a2a-sdk[http-server]==0.3.22"

FROM base AS final

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

COPY vendor/open-langgraph-platform/alembic.ini ./alembic.ini
COPY vendor/open-langgraph-platform/alembic/ ./alembic/
COPY vendor/open-langgraph-platform/auth.py ./auth.py
COPY vendor/open-langgraph-platform/src/ ./src/
COPY docker/open-langgraph/open_langgraph.json ./open_langgraph.json
COPY agents/ ./agents/

EXPOSE 8000

USER app

CMD ["sh", "-c", "alembic upgrade head && uvicorn src.agent_server.main:app --host 0.0.0.0 --port 8000"]
