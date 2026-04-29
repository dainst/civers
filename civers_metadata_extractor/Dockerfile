# ==============================================================================
# CiVers Metadata Extractor - Dockerfile
# ==============================================================================
#
# Multi-stage build for minimal production image.
#
# Build:
#   docker build -t civers-metadata-extractor .
#
# Run standalone:
#   docker run --env-file .env civers-metadata-extractor
#
# Run with docker-compose:
#   docker compose up -d metadata-extractor
#
# ==============================================================================

# Stage 1: Build stage with uv
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files first (for better caching)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-dev --no-install-project

# Copy source code
COPY . .

# Install the project
RUN uv sync --no-dev

# Stage 2: Runtime stage
FROM python:3.12-slim AS runtime

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Copy virtual environment and source code from builder
COPY --from=builder /app/.venv /app/.venv

# Install watchfiles for hot-reload in development
RUN . /app/.venv/bin/activate && pip install watchfiles
COPY --from=builder /app/configs /app/configs
COPY --from=builder /app/models /app/models
COPY --from=builder /app/metadata_extractors /app/metadata_extractors
COPY --from=builder /app/metadata_extraction_services /app/metadata_extraction_services
COPY --from=builder /app/transport_services /app/transport_services
COPY --from=builder /app/storage_layer /app/storage_layer
COPY --from=builder /app/main.py /app/main.py

# Create output directory
RUN mkdir -p /app/output/metadata && chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CONFIG_ENVIRONMENT="docker"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
CMD ["python", "main.py"]
