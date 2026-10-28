# syntax=docker/dockerfile:1
# Stage 1: build with uv
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.6.0 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY src/ src/
RUN uv sync --locked --no-dev

# Stage 2: runtime
FROM python:3.12-slim-bookworm AS runtime

RUN addgroup --system --gid 1001 appsec && \
    adduser --system --uid 1001 --gid 1001 appsec

COPY --from=builder /app /app
WORKDIR /app

USER appsec
EXPOSE 9101

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "--no-sync", "agent", "run"]
