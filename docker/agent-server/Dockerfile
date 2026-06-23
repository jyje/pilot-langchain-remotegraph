# Standalone single-agent FastAPI server (src/remotegraph/agent_server.py).
# Unlike the aegra/open-langgraph backends, this needs no Postgres/Redis -- it
# serves exactly one graph statelessly over the slice of the LangGraph
# Platform API that RemoteGraph uses. Build context is the repo root (see
# docker/agent-server/docker-compose.yml) so it can pick up agents/ + src/.
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # remotegraph (src/) + agents (repo root) both importable.
    PYTHONPATH=/app/src:/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Agent runtime: LangGraph/LangChain + each agent's tools (requests for the
# researcher's web_search, ruff for the reviewer's lint_python) + the FastAPI
# server stack. No backend framework, no database driver.
RUN pip install --no-cache-dir \
    "fastapi>=0.138.0" \
    "uvicorn[standard]>=0.49.0" \
    "langchain>=1.3.10" \
    "langchain-openai>=1.3.2" \
    "langgraph>=1.2.6" \
    "requests>=2.34.2" \
    "ruff>=0.15.18" \
    "python-dotenv>=1.2.2"

COPY agents/ ./agents/
COPY src/ ./src/

# AGENT_GRAPH (e.g. agents/researcher/graph.py:graph) and PORT are supplied per
# service by docker-compose; HOST defaults to 0.0.0.0 inside the container.
CMD ["python", "-m", "remotegraph.agent_server"]
