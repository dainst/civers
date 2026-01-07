# Stage 1: Builder
FROM python:3.12-slim AS builder

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency files and app
COPY pyproject.toml ./
COPY app/ ./app/

# Create venv and install dependencies
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install asgi-correlation-id fastapi itsdangerous jinja2 python-dotenv \
                python-multipart pyyaml requests uvicorn kafka-python pydantic

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

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy app code
COPY --chown=civers:civers . .

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

# Run app (use env vars for host/port)
CMD uvicorn app.main:app --host $HOST --port $PORT
