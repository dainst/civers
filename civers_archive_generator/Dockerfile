# Build from the repository root; civers_common is a workspace dependency.
#   docker build --target runtime -t civers-archive-generator \
#     -f civers_archive_generator/Dockerfile .
#   docker compose build archive-generator
# runtime: application and capture tools, running as a non-root user.
# dev: runtime plus watchfiles for source reloads.
# Pass --target explicitly; dev is the last stage.

# Install Python dependencies and packages.
FROM python:3.12-slim AS builder

# Pin uv to a known version.
COPY --from=ghcr.io/astral-sh/uv:0.9.6 /uv /usr/local/bin/uv

# Match the repository workspace layout.
WORKDIR /workspace

COPY pyproject.toml uv.lock ./
# Include the shared package required by the archive generator.
COPY civers_common/ ./civers_common/
COPY civers_archive_generator/pyproject.toml ./civers_archive_generator/pyproject.toml

# Install locked dependencies without updating uv.lock.
RUN uv sync --frozen --package archive-generator --no-dev --no-install-project --no-editable

COPY civers_archive_generator/ ./civers_archive_generator/

# Install the archive generator package.
RUN uv sync --frozen --package archive-generator --no-dev --no-editable


# Runtime image.
FROM python:3.12-slim AS runtime

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NODE_ENV=production \
    DEBIAN_FRONTEND=noninteractive \
    PATH="/app/.venv/bin:/home/appuser/.local/bin:$PATH" \
    PYTHONPATH="/app" \
    CONFIG_ENVIRONMENT="docker"

# Browser and capture tool dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg bash tar wget unzip \
    fonts-liberation \
    libglib2.0-0 libnss3 libnspr4 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdbus-1-3 libx11-6 libx11-xcb1 libxcb1 libxext6 libgbm1 \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Scoop requires Node.js 22 or newer.
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home appuser

WORKDIR /app

# The virtual environment includes the shared Python package.
COPY --from=builder /workspace/.venv /app/.venv

# Keep the application modules directly under /app for their imports.
COPY --from=builder /workspace/civers_archive_generator/configs /app/configs
COPY --from=builder /workspace/civers_archive_generator/archive_generators /app/archive_generators
COPY --from=builder /workspace/civers_archive_generator/archive_services /app/archive_services
COPY --from=builder /workspace/civers_archive_generator/domain /app/domain
COPY --from=builder /workspace/civers_archive_generator/transport_services /app/transport_services
COPY --from=builder /workspace/civers_archive_generator/storage_layer /app/storage_layer
COPY --from=builder /workspace/civers_archive_generator/lib/scoop /app/lib/scoop
COPY --from=builder /workspace/civers_archive_generator/main.py /app/main.py

# Create writable capture folders; application logs go to stdout.
RUN mkdir -p /app/archives /app/lib/scoop/tmp \
    && chown -R appuser:appgroup /app

COPY configs/data/archive_generator/ /etc/civers/archive_generator/
ENV CONFIG_DIR=/etc/civers/archive_generator

USER appuser

# Install Scoop dependencies.
WORKDIR /app/lib/scoop
RUN npm ci --omit=dev

# Install Chromium for Playwright.
RUN npx playwright install chromium

WORKDIR /app

CMD ["python", "-u", "main.py"]


# Add source reloads to the development image.
FROM runtime AS dev

# Use uv to install watchfiles in the application virtual environment.
COPY --from=ghcr.io/astral-sh/uv:0.9.6 /uv /usr/local/bin/uv
USER root
RUN uv pip install --python /app/.venv/bin/python --no-cache watchfiles \
    && chown -R appuser:appgroup /app/.venv

USER appuser
