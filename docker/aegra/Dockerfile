# Build context is the repo root (see docker/aegra/docker-compose.yml) so this
# can pick up the shared agents/ directory.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "aegra-cli>=0.9.22" \
    "langchain>=1.3.10" \
    "langchain-openai>=1.3.2" \
    "langgraph>=1.2.6" \
    "requests>=2.34.2" \
    "python-dotenv>=1.2.2"

COPY agents/ ./agents/
COPY docker/aegra/aegra.json ./aegra.json

EXPOSE 2026

CMD ["aegra", "serve"]
