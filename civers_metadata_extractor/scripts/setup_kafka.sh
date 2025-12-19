#!/bin/bash
# Setup Kafka infrastructure - complete setup script

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

log "🚀 Starting Kafka infrastructure setup..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    error "Docker is not running. Please start Docker and try again."
fi

# Check if docker compose is available
if ! command -v "docker" &> /dev/null; then
    error "Docker is not installed. Please install Docker and try again."
fi

log "✅ Docker is running and available"

# Start Kafka infrastructure
log "📦 Starting Kafka infrastructure..."
if ! docker compose up -d; then
    error "Failed to start Kafka infrastructure"
fi

log "⏳ Waiting for services to be ready..."
sleep 15

# Check if services are running
if ! docker compose ps | grep -q "Up"; then
    warn "Some services might not be running properly"
    docker compose ps
fi

log "📋 Creating required topics..."
# Create topics using Python script with UV environment
if command -v uv &> /dev/null; then
    uv run python3 scripts/create_topics.py
elif command -v python3 &> /dev/null; then
    warn "UV not available, trying direct Python execution (may have import issues)"
    python3 scripts/create_topics.py
else
    warn "Neither UV nor Python3 available, skipping topic creation via script"
fi

log "🔍 Testing connectivity..."
# Test connectivity using UV command for proper module resolution
if command -v uv &> /dev/null; then
    uv run civers-health-check
elif command -v python3 &> /dev/null; then
    # Fallback to direct Python execution (may have import issues)
    warn "UV not available, trying direct Python execution"
    cd "$(dirname "$0")/.." && python3 -m scripts.civers_health_check
else
    warn "Neither UV nor Python3 available, skipping connectivity test"
fi

log "📊 Current status:"
docker compose ps

log "🎉 Kafka infrastructure setup completed!"
log "📋 Services available:"
log "   Kafka Broker: localhost:29092"
log "   Kafka UI: http://localhost:8088"

log "🔧 Management commands:"
log "   View logs: docker compose logs -f"
log "   Stop services: docker compose down"
log "   List topics: docker exec broker /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list"