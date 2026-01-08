# ==============================================================================
# CIVERS Full Stack - Management Commands
# ==============================================================================

.PHONY: dev prod stop restart-dev logs ps help

help:
	@echo "CIVERS Management Commands:"
	@echo "  make dev         - Start full stack in DEVELOPMENT mode (hot-reload + source mounts)"
	@echo "  make prod        - Start full stack in PRODUCTION mode (base images only)"
	@echo "  make stop        - Stop all running containers"
	@echo "  make ps          - Show status of all containers"
	@echo "  make logs        - Follow all logs"
	@echo "  make restart-dev - Restart only the application services in dev mode"

dev:
	@echo "🚀 Starting CIVERS in standalone DEVELOPMENT mode..."
	docker compose -f docker-compose.dev.yml up -d

prod:
	@echo "🚀 Starting CIVERS in standalone PRODUCTION mode..."
	docker compose -f docker-compose.yml up -d

stop:
	@echo "🛑 Stopping all CIVERS services (Dev and Prod)..."
	docker compose -f docker-compose.yml down
	docker compose -f docker-compose.dev.yml down

ps:
	@echo "--- PRODUCTION STATUS ---"
	docker compose -f docker-compose.yml ps
	@echo "\n--- DEVELOPMENT STATUS ---"
	docker compose -f docker-compose.dev.yml ps

logs:
	@echo "Following logs from DEVELOPMENT stack..."
	docker compose -f docker-compose.dev.yml logs -f

restart-dev:
	@echo "🔄 Restarting app services in DEVELOPMENT stack..."
	docker compose -f docker-compose.dev.yml restart web-interface orchestrator archive-generator metadata-extractor
