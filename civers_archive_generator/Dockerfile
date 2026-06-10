# ==============================================================================
# CiVers Archive Generator - Dockerfile
# ==============================================================================
#
# Build context: repo root (required — civers_common is a workspace dependency)
#
#   docker build -t civers-archive-generator -f civers_archive_generator/Dockerfile .
#
# Or via docker-compose (context: . already set):
#   docker compose build archive-generator
#
# ==============================================================================

# Stage 1: Build — resolve workspace deps and install civers_common properly
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Use /workspace so the uv workspace layout matches the repo structure
WORKDIR /workspace

# ---- Workspace metadata (cache layer: only changes when deps change) ----
COPY pyproject.toml uv.lock ./
# civers_common is a workspace dependency of AG — must be present for resolution
COPY civers_common/ ./civers_common/
# AG's own pyproject.toml inside the workspace
COPY civers_archive_generator/pyproject.toml ./civers_archive_generator/pyproject.toml

# Install AG's dependencies only (civers_common as a real package, not editable)
RUN uv sync --package archive-generator --no-dev --no-install-project --no-editable

# ---- Copy full AG source ----
COPY civers_archive_generator/ ./civers_archive_generator/

# Install AG itself
RUN uv sync --package archive-generator --no-dev --no-editable


# Stage 2: Runtime
FROM python:3.12-slim AS runtime

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    DEBIAN_FRONTEND=noninteractive \
    PATH="/app/.venv/bin:/home/appuser/.local/bin:$PATH" \
    PYTHONPATH="/app" \
    CONFIG_ENVIRONMENT="docker"

# 1. System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg bash tar wget unzip \
    fonts-liberation \
    libglib2.0-0 libnss3 libnspr4 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdbus-1-3 libx11-6 libx11-xcb1 libxcb1 libxext6 libgbm1 \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Node.js 20.x
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home appuser

WORKDIR /app

# 3. Copy virtual environment (civers_common is installed inside as a real package)
COPY --from=builder /workspace/.venv /app/.venv

# 4. Copy AG source files flat to /app/ (preserves import layout: configs.*, archive_generators.*, etc.)
COPY --from=builder /workspace/civers_archive_generator/configs /app/configs
COPY --from=builder /workspace/civers_archive_generator/archive_generators /app/archive_generators
COPY --from=builder /workspace/civers_archive_generator/archive_services /app/archive_services
COPY --from=builder /workspace/civers_archive_generator/transport_services /app/transport_services
COPY --from=builder /workspace/civers_archive_generator/storage_layer /app/storage_layer
COPY --from=builder /workspace/civers_archive_generator/lib/scoop /app/lib/scoop
COPY --from=builder /workspace/civers_archive_generator/main.py /app/main.py

# 5. Final setup
RUN mkdir -p /app/archives /app/lib/scoop/tmp \
    && touch /app/archive_generator.log \
    && chown -R appuser:appgroup /app

USER appuser

# Install watchfiles for development hot-reload
RUN pip install --no-warn-script-location watchfiles

# 6. Scoop npm dependencies
WORKDIR /app/lib/scoop
RUN npm ci --omit=dev

# 7. Playwright browser
RUN npx playwright install chromium

WORKDIR /app

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "-u", "main.py"]
