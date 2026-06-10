# ==============================================================================
# CiVers Metadata Extractor - Dockerfile
# ==============================================================================
#
# Build context: repo root (required — civers_common is a workspace dependency)
#
#   docker build -t civers-metadata-extractor -f civers_metadata_extractor/Dockerfile .
#
# Or via docker-compose (context: . already set):
#   docker compose build metadata-extractor
#
# ==============================================================================

# Stage 1: Build — resolve workspace deps and install civers_common properly
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Use /workspace so the uv workspace layout matches the repo structure
WORKDIR /workspace

# Build the venv at its FINAL runtime path so console-script shebangs (e.g.
# watchfiles) point at /app/.venv/bin/python and stay valid after it is copied
# into the runtime stage.
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

# ---- Workspace metadata (cache layer: only changes when deps change) ----
COPY pyproject.toml uv.lock ./
# civers_common is a workspace dependency of ME — must be present for resolution
COPY civers_common/ ./civers_common/
# ME's own pyproject.toml inside the workspace
COPY civers_metadata_extractor/pyproject.toml ./civers_metadata_extractor/pyproject.toml

# Install ME's dependencies only (civers_common as a real package, not editable)
RUN uv sync --package civers-metadata-extractor --no-dev --no-install-project --no-editable

# ---- Copy full ME source ----
COPY civers_metadata_extractor/ ./civers_metadata_extractor/

# Install ME itself
RUN uv sync --package civers-metadata-extractor --no-dev --no-editable

# Install watchfiles into the venv (for dev hot-reload). Installing here — rather
# than as the non-root user at runtime — guarantees the `watchfiles` entrypoint
# lands in /app/.venv/bin and is on PATH after the venv is activated.
RUN uv pip install --python /app/.venv/bin/python watchfiles


# Stage 2: Runtime
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    CONFIG_ENVIRONMENT="docker"

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy virtual environment (civers_common is installed inside as a real package).
# Built at /app/.venv in the builder, so script shebangs are already correct.
COPY --from=builder /app/.venv /app/.venv

# Copy ME source files flat to /app/ (preserves import layout: configs.*, models.*, etc.)
COPY --from=builder /workspace/civers_metadata_extractor/configs /app/configs
COPY --from=builder /workspace/civers_metadata_extractor/models /app/models
COPY --from=builder /workspace/civers_metadata_extractor/metadata_extractors /app/metadata_extractors
COPY --from=builder /workspace/civers_metadata_extractor/metadata_extraction_services /app/metadata_extraction_services
COPY --from=builder /workspace/civers_metadata_extractor/transport_services /app/transport_services
COPY --from=builder /workspace/civers_metadata_extractor/storage_layer /app/storage_layer
COPY --from=builder /workspace/civers_metadata_extractor/main.py /app/main.py

# Final setup
RUN mkdir -p /app/output/metadata \
    && touch /app/metadata_extractor.log \
    && chown -R appuser:appgroup /app

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "-u", "main.py"]
