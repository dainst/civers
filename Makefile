# ==============================================================================
# CIVERS Full Stack - Management Commands
# ==============================================================================
.PHONY: dev stop restart-dev rebuild logs ps help network

help:
	@echo "CIVERS Management Commands:"
	@echo ""
	@echo "  Local Development:"
	@echo "    make dev         - Start full stack in DEVELOPMENT mode (hot-reload + source mounts)"
	@echo "    make dev-host    - Start Kafka in Docker and all Python services locally on host"
	@echo "    make logs        - Follow all logs (development)"
	@echo "    make restart-dev  - Restart application services"
	@echo "    make rebuild      - Rebuild containers from scratch without cache"
	@echo "    make stop        - Stop all running containers"
	@echo "    make ps          - Show status of all containers"
	@echo "    make network     - Create Docker network (run once)"
	@echo ""

# ==============================================================================
# Network Setup (run once)
# ==============================================================================
network:
	@echo "🌐 Creating Docker network..."
	docker network create civers-network 2>/dev/null || echo "Network already exists"

# Default environment for development
ENV ?= docker

# ==============================================================================
# Local Development
# ==============================================================================
dev:
	@echo "🚀 Starting CIVERS in DEVELOPMENT mode (ENV=$(ENV))..."
	CONFIG_ENVIRONMENT=$(ENV) docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

dev-host:
	@echo "🚀 Starting Kafka and Kafka-UI in Docker..."
	docker compose -f docker-compose.yml up -d kafka kafka-ui
	@echo "⏳ Waiting for Kafka to be ready..."
	@sleep 5
	@echo "🚀 Starting Python services on host..."
	@echo "⚠️ Press Ctrl+C to stop all services"
	@bash -c '\
		trap "kill 0" SIGINT SIGTERM EXIT; \
		export CONFIG_ENVIRONMENT=development; \
		export CONFIG_DIR="$(PWD)/configs"; \
		export KAFKA_BOOTSTRAP_SERVERS=localhost:29092; \
		export CIVERS_API_URL=http://localhost:8000; \
		export CALLBACK_BASE_URL=http://localhost:8000; \
		echo "👉 Starting web interface..."; \
		(cd civers_archive_web_interface && uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) & \
		echo "👉 Starting orchestrator..."; \
		(cd civers_orchestrator && uv run python main.py) & \
		echo "👉 Starting archive generator..."; \
		(cd civers_archive_generator && uv run python main.py) & \
		echo "👉 Starting metadata extractor..."; \
		(cd civers_metadata_extractor && uv run python main.py) & \
		wait \
	'

rebuild:
	@echo "🔨 Rebuilding CIVERS containers from scratch with no cache (ENV=$(ENV))..."
	CONFIG_ENVIRONMENT=$(ENV) docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache
	@echo "🚀 Starting CIVERS after rebuild..."
	CONFIG_ENVIRONMENT=$(ENV) docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

logs:
	@echo "Following logs from DEVELOPMENT stack (ENV=$(ENV))..."
	CONFIG_ENVIRONMENT=$(ENV) docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

restart-dev:
	@echo "🔄 Restarting app services in DEVELOPMENT stack (ENV=$(ENV))..."
	CONFIG_ENVIRONMENT=$(ENV) docker compose -f docker-compose.yml -f docker-compose.dev.yml restart web-interface orchestrator archive-generator metadata-extractor

stop:
	@echo "🛑 Stopping all CIVERS services..."
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

ps:
	@echo "--- CIVERS STACK STATUS ---"
	docker compose ps
