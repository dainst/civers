# Stage 1: Build — resolve workspace deps and install civers_common properly
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Use /workspace so the uv workspace layout matches the repo structure
WORKDIR /workspace

# Build the venv at its FINAL runtime path so console-script shebangs (e.g.
# watchfiles, uvicorn) point at /app/.venv/bin/python and stay valid
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

# ---- Workspace metadata (cache layer: only changes when deps change) ----
COPY pyproject.toml uv.lock ./
# civers_common is a workspace dependency — must be present for resolution
COPY civers_common/ ./civers_common/
# AWI's own pyproject.toml inside the workspace
COPY civers_archive_web_interface/pyproject.toml ./civers_archive_web_interface/pyproject.toml

# Install AWI's dependencies only
RUN uv sync --package civers-archive-web-interface --no-dev --no-install-project --no-editable

# ---- Copy full AWI source ----
COPY civers_archive_web_interface/ ./civers_archive_web_interface/

# Install AWI itself
RUN uv sync --package civers-archive-web-interface --no-dev --no-editable

# Install watchfiles into the venv (for dev hot-reload)
RUN uv pip install --python /app/.venv/bin/python watchfiles


# Stage 2: Runtime
FROM python:3.12-slim AS runtime

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 civers && \
    useradd --uid 1000 --gid civers --shell /bin/bash --create-home civers

# Set workdir
WORKDIR /app

# Copy virtual environment
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy AWI source files flat to /app/
COPY --from=builder /workspace/civers_archive_web_interface/configs /app/configs
COPY --from=builder /workspace/civers_archive_web_interface/app /app/app
COPY --from=builder /workspace/civers_archive_web_interface/templates /app/templates
COPY --from=builder /workspace/civers_archive_web_interface/static /app/static

# Prepare dirs
RUN mkdir -p /app/logs /app/archives /app/data && \
    chown -R civers:civers /app

# Switch to non-root
USER civers

# Expose app port
EXPOSE 8000

# Default environment
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Run app
CMD uvicorn app.main:app --host $HOST --port $PORT

