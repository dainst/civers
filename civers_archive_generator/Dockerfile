# ==============================================================================
# CiVers Archive Generator - Dockerfile
# ==============================================================================
#
# Multi-stage build for minimal production image with Playwright support.
#
# Build:
#   docker build -t civers-archive-generator .
#
# Run standalone:
#   docker run --env-file .env civers-archive-generator
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

# Install dependencies (ensure lockfile is updated if needed)
RUN uv sync --no-dev --no-install-project

# Copy source code
COPY . .

# Install the project
RUN uv sync --no-dev

# Stage 2: Runtime stage
FROM python:3.12-slim AS runtime

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    DEBIAN_FRONTEND=noninteractive \
    PATH="/app/.venv/bin:/home/appuser/.local/bin:$PATH" \
    PYTHONPATH="/app" \
    CONFIG_ENVIRONMENT="docker"

# 1. Install System Dependencies (keep this stable at top)
# Base OS packages and Chromium deps used by Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg bash tar wget unzip \
    fonts-liberation \
    libglib2.0-0 libnss3 libnspr4 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdbus-1-3 libx11-6 libx11-xcb1 libxcb1 libxext6 libgbm1 \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Node.js 20.x
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# 3. Copy Application Code & Artifacts
# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code (explicitly copying required directories/files)
COPY --from=builder /app/configs /app/configs
COPY --from=builder /app/archive_generators /app/archive_generators
COPY --from=builder /app/archive_services /app/archive_services
COPY --from=builder /app/transport_services /app/transport_services
COPY --from=builder /app/storage_layer /app/storage_layer
COPY --from=builder /app/lib/scoop /app/lib/scoop
COPY --from=builder /app/main.py /app/main.py

# 4. Final Setup & Permissions
# Create necessary directories
RUN mkdir -p /app/archives /app/lib/scoop/tmp \
    && touch /app/archive_generator.log \
    && chown -R appuser:appgroup /app

# Switch to non-root user for npm/playwright install
USER appuser

# Install watchfiles for development/hot-reload
RUN pip install --no-warn-script-location watchfiles

# 5. Install Scoop Dependencies (npm)
WORKDIR /app/lib/scoop
RUN npm ci --omit=dev

# 6. Install Playwright Browsers
# This MUST happen as the user who runs the app to be found correctly in default paths
RUN npx playwright install chromium

# Reset workdir
WORKDIR /app

# Health check (basic python import check)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
CMD ["python", "-u", "main.py"]
