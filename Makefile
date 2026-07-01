# ==============================================================================
# CIVERS Full Stack - Management Commands
# ==============================================================================
.PHONY: dev stop restart-dev rebuild logs ps status help network setup_host run_host \
        web-start web-stop ag-start ag-stop orch-start orch-stop \
        me-start me-stop cd-start cd-stop kafka-start kafka-stop \
        kafka-ui-start kafka-ui-stop verify-storage status \
        test orch-test ag-test me-test awi-test cd-test common-test smoke

help:
	@echo "CIVERS Management Commands:"
	@echo ""
	@echo "  Full Stack Development:"
	@echo "    make dev                 - Start full stack in DEVELOPMENT mode (hot-reload + source mounts)"
	@echo "    make setup_host          - Setup all project host dependencies (uv, playwright, scoop)"
	@echo "    make run_host            - Setup host and start all Python services locally on host"
	@echo "    make dev-host            - Start Kafka in Docker and all Python services locally on host"
	@echo "    make logs                - Follow all logs (development)"
	@echo "    make restart-dev          - Restart application services"
	@echo "    make rebuild              - Rebuild containers from scratch without cache"
	@echo "    make stop                - Stop all running containers"
	@echo "    make <service>-stop      - Stop a specific service (e.g. web-stop, ag-stop)"
	@echo "    make status              - Show operational status of all CIVERS containers (or make ps)"
	@echo "    make network             - Create Docker network (run once)"
	@echo ""
	@echo "  Service-Specific Control (web, ag, orch, me, cd, kafka, kafka-ui):"
	@echo "    make <service>-start     - Start a specific container service (e.g. web-start, ag-start, kafka-start)"
	@echo "    make <service>-stop      - Stop a specific container service (e.g. web-stop, ag-stop, kafka-stop)"
	@echo "    make ag-dev-host         - Start Kafka in Docker and Archive Generator on host"
	@echo "    make ag-test             - Run Archive Generator unit tests"
	@echo "    make ag-run-direct URL=x - Run Archive Generator on host for a single URL (CLI)"
	@echo ""
	@echo "  Kafka Utilities:"
	@echo "    make send-kafka-archive-request URL=x REQUEST_TYPE=x [KAFKA_BOOTSTRAP_SERVERS=x] - Send test requests to Kafka"
	@echo "    make kafka-monitor                                                             - Follow Kafka workflow events"
	@echo ""
	@echo "  Verification Utilities:"
	@echo "    make verify-storage [UPLOAD=true]                                              - Verify storage backend health (passive or active upload)"
	@echo ""
	@echo "  Testing:"
	@echo "    make test                - Run ALL services' unit tests (no Kafka/broker needed)"
	@echo "    make <service>-test      - Run one service's unit tests (orch, ag, me, awi, cd, common)"
	@echo "    make smoke [URL=x]       - Run the full-stack end-to-end smoke test (stack must be running)"
	@echo ""

# ==============================================================================
# Network Setup (run once)
# ==============================================================================
network:
	@echo "🌐 Creating Docker network..."
	docker network create civers-network 2>/dev/null || echo "Network already exists"

# Default environment for development
CONFIG_ENVIRONMENT ?= development
KAFKA_BOOTSTRAP_SERVERS ?=
# ==============================================================================
# Local Development
# ==============================================================================
dev:
	@echo "🚀 Starting CIVERS in DEVELOPMENT mode (CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT))..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

setup_host:
	@echo "🛠️ Preparing host dependencies..."
	@chmod +x scripts/setup_host.sh
	@./scripts/setup_host.sh

run_host: setup_host dev-host

dev-host:
	@echo "🚀 Starting Kafka and Kafka-UI in Docker..."
	docker compose -f docker-compose.yml up -d kafka kafka-ui
	@echo "⏳ Waiting for Kafka to be ready..."
	@sleep 5
	@echo "🚀 Starting Python services on host..."
	@echo "⚠️ Press Ctrl+C to stop all services"
	@bash -c '\
		trap "trap - SIGINT SIGTERM EXIT; kill 0" SIGINT SIGTERM EXIT; \
		export CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT); \
		export CONFIG_DIR="$(PWD)/configs"; \
		export KAFKA_BOOTSTRAP_SERVERS=localhost:29092; \
		export CIVERS_API_URL=http://localhost:8000; \
		export CALLBACK_BASE_URL=http://localhost:8000; \
		export PYTHONUNBUFFERED=1; \
		echo "👉 Starting web interface..."; \
		(cd civers_archive_web_interface && uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload 2>&1 | awk '\''{print "\033[92m[WEB]\033[0m " $$0; fflush()}'\'') & \
		echo "👉 Starting orchestrator..."; \
		(cd civers_orchestrator && uv run python main.py 2>&1 | awk '\''{print "\033[94m[ORCH]\033[0m " $$0; fflush()}'\'') & \
		echo "👉 Starting archive generator..."; \
		(cd civers_archive_generator && uv run python main.py 2>&1 | awk '\''{print "\033[95m[GEN]\033[0m " $$0; fflush()}'\'') & \
		echo "👉 Starting metadata extractor..."; \
		(cd civers_metadata_extractor && uv run python main.py 2>&1 | awk '\''{print "\033[96m[ME]\033[0m " $$0; fflush()}'\'') & \
		wait \
	'

rebuild:
	@echo "🔨 Rebuilding CIVERS containers from scratch with no cache (CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT))..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache
	@echo "🚀 Starting CIVERS after rebuild..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

logs:
	@echo "Following logs from DEVELOPMENT stack (CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT))..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

restart-dev:
	@echo "🔄 Restarting app services in DEVELOPMENT stack (CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT))..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) docker compose -f docker-compose.yml -f docker-compose.dev.yml restart web-interface orchestrator archive-generator metadata-extractor

stop:
	@echo "🛑 Stopping all CIVERS services..."
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

ps: status

status:
	@uv run python scripts/status_info.py

# ==============================================================================
# CLI Direct Execution
# ==============================================================================
ag-run-direct:
	@if [ -z "$(URL)" ]; then echo "❌ Please specify URL=... (e.g., make ag-run-direct URL=https://example.com)"; exit 1; fi
	@echo "🚀 Running CLI transport for $(URL) directly on host Archive Generator..."
	(cd civers_archive_generator && CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) uv run python main.py --transport cli --url "$(URL)")

web-start:
	@echo "🚀 Starting Web Interface and Kafka in Docker (CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT))..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d web-interface

ag-start:
	@echo "🚀 Starting Archive Generator and Kafka in Docker (CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT))..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d archive-generator

orch-start:
	@echo "🚀 Starting Orchestrator in Docker (CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT))..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d orchestrator

me-start:
	@echo "🚀 Starting Metadata Extractor in Docker (CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT))..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d metadata-extractor

cd-start:
	@echo "🚀 Starting Change Detection in Docker (CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT))..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d change-detection

kafka-start:
	@echo "🚀 Starting Kafka broker in Docker..."
	docker compose -f docker-compose.yml up -d kafka

kafka-stop:
	@echo "🛑 Stopping Kafka broker container..."
	docker compose -f docker-compose.yml stop kafka

kafka-ui-start:
	@echo "🚀 Starting Kafka UI in Docker..."
	docker compose -f docker-compose.yml up -d kafka-ui

kafka-ui-stop:
	@echo "🛑 Stopping Kafka UI container..."
	docker compose -f docker-compose.yml stop kafka-ui

ag-dev-host:
	@echo "🚀 Starting Kafka in Docker and Archive Generator locally on host (CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT))..."
	(cd civers_archive_generator && CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) make dev-host)

ag-test:
	@echo "🧪 Running Archive Generator unit tests..."
	(cd civers_archive_generator && CONFIG_ENVIRONMENT=testing uv run --extra dev pytest tests/unit/)

web-stop:
	@echo "🛑 Stopping Web Interface container..."
	docker compose -f docker-compose.yml -f docker-compose.dev.yml stop web-interface

ag-stop:
	@echo "🛑 Stopping Archive Generator container..."
	docker compose -f docker-compose.yml -f docker-compose.dev.yml stop archive-generator

orch-stop:
	@echo "🛑 Stopping Orchestrator container..."
	docker compose -f docker-compose.yml -f docker-compose.dev.yml stop orchestrator

me-stop:
	@echo "🛑 Stopping Metadata Extractor container..."
	docker compose -f docker-compose.yml -f docker-compose.dev.yml stop metadata-extractor

cd-stop:
	@echo "🛑 Stopping Change Detection container..."
	docker compose -f docker-compose.yml -f docker-compose.dev.yml stop change-detection

send-kafka-archive-request:
# url and request_type are required
	@if [ -z "$(URL)" ]; then echo "❌ Please specify URL=... (e.g., make send-kafka-archive-request URL=https://example.com)"; exit 1; fi
	@if [ -z "$(REQUEST_TYPE)" ]; then echo "❌ Please specify REQUEST_TYPE=... (e.g., make send-kafka-archive-request REQUEST_TYPE=archive)"; exit 1; fi
	@echo "🚀 Sending Kafka request for $(URL)..."	
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) uv run python scripts/send_kafka_request.py --urls $(URL) --request-type "$(REQUEST_TYPE)" $(if $(KAFKA_BOOTSTRAP_SERVERS),--kafka-bootstrap-servers "$(KAFKA_BOOTSTRAP_SERVERS)",) $(ARGS)

kafka-monitor:
	@echo "🚀 Starting CIVERS Kafka Flow Monitor (CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT))..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) uv run python scripts/kafka_flow_monitor.py

verify-storage:
	@echo "🔍 Running storage verification checks..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) uv run python scripts/verify_storage.py $(if $(filter-out false,$(UPLOAD)),--upload,) $(ARGS)

# ==============================================================================
# Unit Testing (per service; no Kafka/broker required)
# ==============================================================================
# `make test` runs every service's unit suite. Each service uses its own correct
# unit command (dir- or marker-scoped) so integration tests requiring a broker
# are excluded. Run a single service with e.g. `make orch-test`.
test: orch-test ag-test me-test awi-test cd-test common-test
	@echo "✅ All unit test suites passed."

orch-test:
	@echo "🧪 Orchestrator unit tests..."
	(cd civers_orchestrator && CONFIG_ENVIRONMENT=testing uv run pytest tests/unit/)

me-test:
	@echo "🧪 Metadata Extractor unit tests..."
	(cd civers_metadata_extractor && CONFIG_ENVIRONMENT=testing uv run pytest -m "not integration")

awi-test:
	@echo "🧪 Web Interface unit tests..."
	(cd civers_archive_web_interface && CONFIG_ENVIRONMENT=testing uv run pytest)

cd-test:
	@echo "🧪 Change Detection unit tests..."
	(cd civers_change_detection && CONFIG_ENVIRONMENT=testing uv run pytest tests/unit/)

common-test:
	@echo "🧪 civers_common base-class tests..."
	(cd civers_common && uv run pytest)

# ==============================================================================
# Smoke / End-to-End
# ==============================================================================
# Exercises the whole pipeline (AWI -> ORCH -> AG -> ME -> AWI) against a running
# stack. Start it first with `make dev` (or `make dev-host`). Optional: URL=<url>
# and ARGS='--timeout 300 --web-url http://localhost:8000'.
smoke:
	@echo "💨 Running full-stack smoke test (the stack must already be running)..."
	CONFIG_ENVIRONMENT=$(CONFIG_ENVIRONMENT) uv run python scripts/full_stack_test.py $(if $(URL),--test-url $(URL),) $(ARGS)