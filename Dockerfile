FROM python:3.13-alpine3.23 AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy instead of linking since the .venv is copied across stages
ENV UV_LINK_MODE=copy

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

COPY uv.lock pyproject.toml ./

RUN uv sync --locked --no-install-project --no-dev

FROM python:3.13-alpine3.23

WORKDIR /app

# Copy generated .venv dir from builder
COPY --from=builder /app /app

COPY ./ /app/

RUN apk add --no-cache tzdata

ENV TZ=Europe/Oslo

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Add src to Python path so padelbot package is importable
ENV PYTHONPATH="/app/src"

# Create logs directory and non-root user
RUN mkdir -p /app/logs && \
    addgroup -S appgroup && \
    adduser -S appuser -G appgroup && \
    chown -R appuser:appgroup /app/logs

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:8000/ || exit 1

CMD ["uvicorn", "webapp:app", "--host", "0.0.0.0", "--port", "8000"]
