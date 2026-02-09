# ==============================================================================
# CIVERS Full Stack - Management Commands
# ==============================================================================

.PHONY: dev stop restart-dev logs ps help network

help:
	@echo "CIVERS Management Commands:"
	@echo ""
	@echo "  Local Development:"
	@echo "    make dev         - Start full stack in DEVELOPMENT mode (hot-reload + source mounts)"
	@echo "    make logs        - Follow all logs (development)"
	@echo "    make restart-dev  - Restart application services"
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
