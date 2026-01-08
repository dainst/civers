# Dockerfile for civers_archive_generator with Scoop installed
FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    DEBIAN_FRONTEND=noninteractive

# Base OS packages and Chromium deps used by Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg bash tar wget unzip \
    fonts-liberation \
    libglib2.0-0 libnss3 libnspr4 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdbus-1-3 libx11-6 libx11-xcb1 libxcb1 libxext6 libgbm1 \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy application source files (project structure is in the current directory)
COPY requirements.txt ./
COPY main_app.py ./
COPY configs/ ./configs/
COPY archive_generators/ ./archive_generators/
COPY archive_services/ ./archive_services/
COPY transport_services/ ./transport_services/
COPY storage_layer/ ./storage_layer/
COPY lib/scoop/ ./lib/scoop/

# Python dependencies
RUN pip install --no-cache-dir -r requirements.txt watchfiles

# Install Scoop dependencies (but not Playwright browsers yet)
WORKDIR /app/lib/scoop
RUN npm ci --omit=dev

# Back to app directory
WORKDIR /app

# Set Docker environment for configuration
ENV ARCHIVE_ENV=docker
ENV PYTHONPATH="/app"

# Ensure writable paths and create log file
RUN mkdir -p /app/archives /app/lib/scoop/tmp \
    && touch /app/archive_generator.log \
    && groupadd -g 1000 appgroup || true \
    && useradd -m -u 1000 -g 1000 appuser || true \
    && chown -R appuser:appgroup /app

USER appuser

# Install Playwright Chromium as the appuser so it's in the correct location
WORKDIR /app/lib/scoop
RUN npx playwright install chromium

# Run from the app folder so relative config path resolves
WORKDIR /app

CMD ["python", "-u", "main_app.py"]
