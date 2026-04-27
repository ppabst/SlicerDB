# syntax=docker/dockerfile:1.7

# ---------- Stage 1: assets (Tailwind v4 + HTMX, no Node) ----------
FROM debian:bookworm-slim AS assets

ARG TAILWIND_VERSION=v4.1.13
ARG HTMX_VERSION=2.0.4
ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /assets
COPY app/static/css/input.css /assets/input.css
COPY app/templates /assets/templates

RUN set -eux; \
    case "${TARGETARCH}" in \
      amd64) TW_ARCH=x64 ;; \
      arm64) TW_ARCH=arm64 ;; \
      *) echo "Unsupported arch: ${TARGETARCH}"; exit 1 ;; \
    esac; \
    curl -fsSL -o /usr/local/bin/tailwindcss \
      "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${TW_ARCH}"; \
    chmod +x /usr/local/bin/tailwindcss; \
    curl -fsSL -o /assets/htmx.min.js \
      "https://unpkg.com/htmx.org@${HTMX_VERSION}/dist/htmx.min.js"

RUN tailwindcss -i /assets/input.css -o /assets/output.css --minify

# ---------- Stage 2: builder (uv + deps into /app/.venv) ----------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-install-project --no-dev

# ---------- Stage 3: runtime ----------
FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    SLICERDB_DATA_DIR=/data \
    SLICERDB_BIND_HOST=0.0.0.0 \
    SLICERDB_BIND_PORT=8080

RUN groupadd --system --gid 1001 slicerdb && \
    useradd --system --uid 1001 --gid 1001 --home /app slicerdb && \
    mkdir -p /data && chown -R slicerdb:slicerdb /data

WORKDIR /app

COPY --from=builder --chown=slicerdb:slicerdb /app/.venv /app/.venv
COPY --chown=slicerdb:slicerdb app /app/app
COPY --chown=slicerdb:slicerdb alembic /app/alembic
COPY --chown=slicerdb:slicerdb alembic.ini /app/alembic.ini
COPY --from=assets --chown=slicerdb:slicerdb /assets/output.css /app/app/static/css/output.css
COPY --from=assets --chown=slicerdb:slicerdb /assets/htmx.min.js /app/app/static/js/htmx.min.js

USER slicerdb

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
