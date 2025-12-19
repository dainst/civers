#!/bin/bash
# Cleanup Kafka infrastructure - stops services and optionally removes data

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Parse command line arguments
REMOVE_DATA=false
if [[ "${1:-}" == "--remove-data" ]]; then
    REMOVE_DATA=true
fi

log "🛑 Starting Kafka infrastructure cleanup..."

# Stop services
log "🔽 Stopping Kafka services..."
if docker compose ps | grep -q "Up"; then
    docker compose down
    log "✅ Services stopped"
else
    log "ℹ️ Services already stopped"
fi

# Remove data if requested
if [[ "$REMOVE_DATA" == true ]]; then
    warn "⚠️ Removing all Kafka data and volumes..."
    read -p "Are you sure you want to remove all data? (yes/no): " -r
    if [[ $REPLY == "yes" ]]; then
        log "🗑️ Removing volumes..."
        docker compose down -v
        docker volume prune -f
        log "✅ Data volumes removed"
    else
        log "ℹ️ Data removal cancelled"
    fi
fi

# Clean up any orphaned containers
log "🧹 Cleaning up containers..."
if docker ps -a | grep -E "(broker|kafka-ui)" | grep -q "Exited"; then
    docker ps -a | grep -E "(broker|kafka-ui)" | awk '{print $1}' | xargs docker rm -f
    log "✅ Orphaned containers removed"
fi

# Clean up unused images (optional)
log "🧹 Cleaning up unused images..."
docker image prune -f

log "✅ Kafka infrastructure cleanup completed!"

if [[ "$REMOVE_DATA" == true ]]; then
    log "⚠️ All data has been removed. Next startup will be a fresh installation."
else
    log "ℹ️ Data preserved. Use '--remove-data' flag to remove all data."
fi

log "🔧 To restart services: ./scripts/setup_kafka.sh"