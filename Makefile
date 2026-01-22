# ==============================================================================
# CIVERS Full Stack - Management Commands
# ==============================================================================

.PHONY: dev prod stop restart-dev logs ps help network
.PHONY: test-deploy test-build test-logs test-stop test-ps
.PHONY: prod-deploy prod-build prod-logs prod-stop prod-ps

help:
	@echo "CIVERS Management Commands:"
	@echo ""
	@echo "  Local Development:"
	@echo "    make dev         - Start full stack in DEVELOPMENT mode (hot-reload + source mounts)"
	@echo "    make logs        - Follow all logs (development)"
	@echo "    make restart-dev - Restart only the application services in dev mode"
	@echo ""
	@echo "  Test Server (test.civers.de):"
	@echo "    make test-deploy - Build and deploy to test environment"
	@echo "    make test-build  - Build images only (no deploy)"
	@echo "    make test-logs   - Follow logs from test stack"
	@echo "    make test-stop   - Stop test environment"
	@echo "    make test-ps     - Show test environment status"
	@echo ""
	@echo "  Production Server (civers.de):"
	@echo "    make prod-deploy - Build and deploy to production"
	@echo "    make prod-build  - Build images only (no deploy)"
	@echo "    make prod-logs   - Follow logs from production stack"
	@echo "    make prod-stop   - Stop production environment"
	@echo "    make prod-ps     - Show production status"
	@echo ""
	@echo "  General:"
	@echo "    make network     - Create Docker network (run once per server)"
	@echo "    make stop        - Stop all running containers"
	@echo "    make ps          - Show status of all containers"

# ==============================================================================
# Network Setup (run once per server)
# ==============================================================================
network:
	@echo "🌐 Creating Docker network..."
	docker network create civers-network 2>/dev/null || echo "Network already exists"

# ==============================================================================
# Local Development
# ==============================================================================
dev:
	@echo "🚀 Starting CIVERS in standalone DEVELOPMENT mode..."
	docker compose -f docker-compose.dev.yml up -d

logs:
	@echo "Following logs from DEVELOPMENT stack..."
	docker compose -f docker-compose.dev.yml logs -f

restart-dev:
	@echo "🔄 Restarting app services in DEVELOPMENT stack..."
	docker compose -f docker-compose.dev.yml restart web-interface orchestrator archive-generator metadata-extractor

# ==============================================================================
# Test Server (test.civers.de)
# ==============================================================================
test-build:
	@echo "🔨 Building images for TEST environment..."
	docker compose -f docker-compose.yml -f docker-compose.test.yml build

test-deploy: network
	@echo "🚀 Deploying to TEST environment (test.civers.de)..."
	docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --build

test-logs:
	@echo "Following logs from TEST stack..."
	docker compose -f docker-compose.yml -f docker-compose.test.yml logs -f

test-stop:
	@echo "🛑 Stopping TEST environment..."
	docker compose -f docker-compose.yml -f docker-compose.test.yml down

test-ps:
	@echo "--- TEST ENVIRONMENT STATUS ---"
	docker compose -f docker-compose.yml -f docker-compose.test.yml ps

# ==============================================================================
# Production Server (civers.de)
# Note: Create docker-compose.prod.yml by copying docker-compose.test.yml
#       and replacing test.civers.de with civers.de
# ==============================================================================
prod-build:
	@echo "🔨 Building images for PRODUCTION environment..."
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

prod-deploy: network
	@echo "🚀 Deploying to PRODUCTION environment (civers.de)..."
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

prod-logs:
	@echo "Following logs from PRODUCTION stack..."
	docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

prod-stop:
	@echo "🛑 Stopping PRODUCTION environment..."
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down

prod-ps:
	@echo "--- PRODUCTION ENVIRONMENT STATUS ---"
	docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# ==============================================================================
# Legacy commands (for backwards compatibility)
# ==============================================================================
prod:
	@echo "🚀 Starting CIVERS in standalone PRODUCTION mode (local)..."
	docker compose -f docker-compose.yml up -d

stop:
	@echo "🛑 Stopping all CIVERS services..."
	-docker compose -f docker-compose.yml down 2>/dev/null
	-docker compose -f docker-compose.dev.yml down 2>/dev/null
	-docker compose -f docker-compose.yml -f docker-compose.test.yml down 2>/dev/null
	-docker compose -f docker-compose.yml -f docker-compose.prod.yml down 2>/dev/null

ps:
	@echo "--- LOCAL/PRODUCTION STATUS ---"
	-docker compose -f docker-compose.yml ps 2>/dev/null
	@echo "\n--- DEVELOPMENT STATUS ---"
	-docker compose -f docker-compose.dev.yml ps 2>/dev/null
	@echo "\n--- TEST ENVIRONMENT STATUS ---"
	-docker compose -f docker-compose.yml -f docker-compose.test.yml ps 2>/dev/null
