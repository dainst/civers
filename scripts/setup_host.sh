#!/bin/bash
# setup_host.sh
# Automates setting up the entire CIVERS repository to run directly on the host machine.
# Runs uv sync for python workspace packages, configures Playwright, npm dependencies, and file permissions.

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}==== $1 ====${NC}"
}

# Error handling
handle_error() {
    log_error "Setup failed at step: $1"
    log_error "Check the logs above for details"
    exit 1
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Verify running from project root
log_step "Checking Directory Context"
if [[ ! -f "pyproject.toml" ]] || [[ ! -d "civers_archive_generator" ]]; then
    log_error "This script must be run from the root of the CIVERS repository."
    exit 1
fi
log_success "Running from CIVERS repository root: $(pwd)"

# 2. Check system prerequisites
log_step "Checking Host System Requirements"
if ! command_exists python3; then
    log_error "Python 3 is required but not installed."
    exit 1
fi

if ! command_exists uv; then
    log_error "uv package manager is required but not installed."
    log_error "Please install uv: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

if ! command_exists node; then
    log_error "Node.js is required but not installed."
    exit 1
fi

if ! command_exists npm; then
    log_error "npm is required but not installed."
    exit 1
fi

if ! command_exists docker; then
    log_warning "Docker is not installed. You will need a Kafka broker running elsewhere to connect."
fi
log_success "System requirements check passed"

# 3. Setup Python Workspace
log_step "Setting Up Python Workspace Environment"
log_info "Running uv sync to install and link workspace packages..."
uv sync || handle_error "Python workspace package installation"

log_info "Installing Playwright Chromium browser for Python..."
uv run playwright install chromium || handle_error "Playwright Chromium installation"
log_success "Python environment set up successfully"

# 4. Setup Scoop Node.js and Playwright
log_step "Setting Up Scoop dependencies (Archive Generator)"
if [[ ! -d "civers_archive_generator/lib/scoop" ]]; then
    log_error "civers_archive_generator/lib/scoop directory not found"
    exit 1
fi

log_info "Installing Scoop npm dependencies..."
(cd civers_archive_generator/lib/scoop && npm install) || handle_error "Scoop npm dependencies installation"

log_info "Installing Playwright Chromium browser for Scoop..."
(cd civers_archive_generator/lib/scoop && npx playwright install chromium) || handle_error "Scoop Playwright browser installation"
log_success "Scoop environment set up successfully"

# 5. Permissions and Directories Setup
log_step "Configuring Permissions and Directories"
singlefile_binary="civers_archive_generator/archive_generators/singlefile/single-file-x86_64-linux"
if [[ -f "$singlefile_binary" ]]; then
    chmod +x "$singlefile_binary" || handle_error "Making SingleFile binary executable"
    log_success "SingleFile binary set to executable"
else
    log_warning "SingleFile binary not found at $singlefile_binary"
fi

mkdir -p civers_archive_generator/archives
chmod 755 civers_archive_generator/archives
log_success "Local output folders configured"

# 6. Final Instructions
log_step "Host Setup Complete! 🎉"
echo "Next steps to run CIVERS directly on your host machine:"
echo "1. Start the Kafka broker and Kafka UI in Docker:"
echo "   make dev-host"
echo ""
echo "2. Run all Python services on your host:"
echo "   CONFIG_ENVIRONMENT=development make dev-host"
echo "   (This starts Kafka in Docker, and the Web Interface, Orchestrator, Generator, and Extractor on the host)"
echo ""
echo "3. Run verification check:"
echo "   uv run python scripts/verify_storage.py --upload"
echo ""
echo -e "${GREEN}Setup successful!${NC}"
