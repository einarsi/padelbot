FROM python:3.13-alpine3.22 AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Ensure installed tools can be executed out of the box
ENV UV_TOOL_BIN_DIR=/usr/local/bin

# Install uv
RUN apk add uv

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

FROM python:3.13-alpine3.22

WORKDIR /app

# Copy generated .venv dir from builder
COPY --from=builder /app /app

COPY ./ /app/

RUN apk add --no-cache tzdata

ENV TZ=Europe/Oslo

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT []

CMD ["python3", "src/main.py"]
