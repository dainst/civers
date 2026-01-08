#!/bin/bash

# Archive Generator Application Setup Script
# Automates the installation process with comprehensive error checking
# Based on the installation steps in README.md

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
    log_error "Check the error messages above for details"
    exit 1
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if we're in the right directory
check_project_directory() {
    log_step "Checking Project Directory"
    
    if [[ ! -f "main.py" ]] || [[ ! -f "pyproject.toml" ]] || [[ ! -d "archive_generators" ]]; then
        log_error "This doesn't appear to be the archive_generator project directory"
        log_error "Please run this script from the root of the civers_archive_generator project"
        exit 1
    fi
    
    log_success "Running in correct project directory: $(pwd)"
}

# Check system requirements
check_system_requirements() {
    log_step "Checking System Requirements"
    
    # Check if we have curl for downloads
    if ! command_exists curl; then
        log_error "curl is required but not installed. Please install curl first."
        exit 1
    fi
    
    # Check if we have docker and docker-compose
    if ! command_exists docker; then
        log_error "Docker is required but not installed. Please install Docker first."
        log_error "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! command_exists docker-compose && ! docker compose version >/dev/null 2>&1; then
        log_error "Docker Compose is required but not installed."
        log_error "Install docker-compose or ensure 'docker compose' command works"
        exit 1
    fi
    
    # Check if docker daemon is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running. Please start Docker first."
        exit 1
    fi
    
    log_success "System requirements check passed"
}

# Install Node.js v20 using nvm
install_nodejs() {
    log_step "Installing Node.js v20"
    
    # Check if node is already installed and correct version
    if command_exists node; then
        NODE_VERSION=$(node --version)
        if [[ "$NODE_VERSION" =~ ^v20\. ]]; then
            log_success "Node.js v20 already installed: $NODE_VERSION"
            return 0
        else
            log_warning "Node.js version $NODE_VERSION detected, but v20.x is required"
        fi
    fi
    
    # Install nvm if not present
    if [[ ! -f "$HOME/.nvm/nvm.sh" ]]; then
        log_info "Installing Node Version Manager (nvm)..."
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash || handle_error "nvm installation"
    fi
    
    # Source nvm
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
    
    # Verify nvm is available
    if ! command_exists nvm; then
        log_error "nvm installation failed or not available in current shell"
        log_error "Try running: source ~/.bashrc"
        exit 1
    fi
    
    # Install and use Node.js v20
    log_info "Installing Node.js v20 via nvm..."
    nvm install 20 || handle_error "Node.js v20 installation"
    nvm use 20 || handle_error "Switching to Node.js v20"
    nvm alias default 20 || handle_error "Setting Node.js v20 as default"
    
    # Verify installation
    NODE_VERSION=$(node --version)
    if [[ ! "$NODE_VERSION" =~ ^v20\. ]]; then
        log_error "Node.js v20 installation failed. Current version: $NODE_VERSION"
        exit 1
    fi
    
    log_success "Node.js v20 installed successfully: $NODE_VERSION"
}

# Install uv package manager
install_uv() {
    log_step "Installing uv Package Manager"
    
    if command_exists uv; then
        UV_VERSION=$(uv --version)
        log_success "uv already installed: $UV_VERSION"
        return 0
    fi
    
    log_info "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh || handle_error "uv installation"
    
    # Add uv to PATH for current session
    export PATH="$HOME/.local/bin:$PATH"
    
    # Verify installation
    if ! command_exists uv; then
        log_error "uv installation failed"
        log_error "Try adding ~/.local/bin to your PATH and run the script again"
        exit 1
    fi
    
    UV_VERSION=$(uv --version)
    log_success "uv installed successfully: $UV_VERSION"
}

# Install Python dependencies
install_python_dependencies() {
    log_step "Installing Python Dependencies"

    log_info "Installing Python dependencies via uv..."
    uv sync || handle_error "Python dependencies installation"

    log_info "Installing Playwright Chromium browser for SingleFile..."
    uv run playwright install chromium || handle_error "Playwright Chromium installation"

    log_success "Python dependencies installed successfully"
}

# Install Scoop dependencies
install_scoop_dependencies() {
    log_step "Installing Scoop Dependencies"
    
    if [[ ! -d "lib/scoop" ]]; then
        log_error "lib/scoop directory not found"
        exit 1
    fi
    
    log_info "Installing Scoop npm dependencies..."
    cd lib/scoop
    npm install || handle_error "Scoop npm dependencies installation"
    
    log_info "Installing Playwright Chromium browser for Scoop..."
    npx playwright install chromium || handle_error "Scoop Playwright browser installation"
    
    cd ../..
    
    # Verify Scoop installation
    log_info "Verifying Scoop installation..."
    SCOOP_VERSION=$(node lib/scoop/bin/cli.js --version 2>/dev/null || echo "")
    if [[ -z "$SCOOP_VERSION" ]]; then
        log_error "Scoop CLI verification failed"
        exit 1
    fi
    
    log_success "Scoop dependencies installed successfully. Version: $SCOOP_VERSION"
}

# Set up proper permissions
setup_permissions() {
    log_step "Setting Up Permissions"
    
    log_info "Setting up project folder permissions..."
    
    # Check if SingleFile binary exists
    if [[ ! -f "archive_generators/single-file-x86_64-linux" ]]; then
        log_error "SingleFile binary not found at archive_generators/single-file-x86_64-linux"
        exit 1
    fi
    
    # Make SingleFile binary executable
    chmod +x archive_generators/single-file-x86_64-linux || handle_error "Making SingleFile binary executable"
    
    # Create archives directory
    mkdir -p archives || handle_error "Creating archives directory"
    chmod 755 archives || handle_error "Setting archives directory permissions"
    
    log_success "Permissions set up successfully"
}

# Start Kafka infrastructure
start_kafka() {
    log_step "Starting Kafka Infrastructure"
    
    log_info "Starting Kafka broker and Zookeeper..."
    docker compose up -d || handle_error "Starting Kafka infrastructure"
    
    # Wait for Kafka to be ready
    log_info "Waiting for Kafka to be ready..."
    local max_wait=60
    local wait_time=0
    
    while [[ $wait_time -lt $max_wait ]]; do
        if docker compose logs broker 2>/dev/null | grep -q "started"; then
            break
        fi
        sleep 2
        wait_time=$((wait_time + 2))
        echo -n "."
    done
    echo ""
    
    if [[ $wait_time -ge $max_wait ]]; then
        log_error "Kafka failed to start within $max_wait seconds"
        log_error "Check Docker logs: docker compose logs broker"
        exit 1
    fi
    
    log_success "Kafka infrastructure started successfully"
}

# Verify installation
verify_installation() {
    log_step "Verifying Installation"
    
    # Verify Node.js version
    NODE_VERSION=$(node --version)
    if [[ ! "$NODE_VERSION" =~ ^v20\. ]]; then
        log_error "Node.js v20 verification failed. Current version: $NODE_VERSION"
        exit 1
    fi
    log_success "Node.js v20 verified: $NODE_VERSION"
    
    # Verify Scoop is working
    if ! node lib/scoop/bin/cli.js --version >/dev/null 2>&1; then
        log_error "Scoop CLI verification failed"
        exit 1
    fi
    log_success "Scoop CLI verified"
    
    # Verify Python dependencies
    if ! uv run python -c "import playwright; print('Playwright OK')" >/dev/null 2>&1; then
        log_error "Python/Playwright verification failed"
        exit 1
    fi
    log_success "Python dependencies verified"
    
    # Verify SingleFile binary permissions
    if [[ ! -x "archive_generators/single-file-x86_64-linux" ]]; then
        log_error "SingleFile binary not executable"
        exit 1
    fi
    log_success "SingleFile binary verified"
    
    # Verify Docker containers are running
    if ! docker compose ps | grep -q "Up"; then
        log_error "Docker containers not running properly"
        exit 1
    fi
    log_success "Docker containers verified"
}

# Run a quick test
run_quick_test() {
    log_step "Running Quick Test"
    
    log_info "Starting application for quick test..."
    # Start application in background
    uv run python main.py > /tmp/archive_app.log 2>&1 &
    APP_PID=$!
    
    # Wait a moment for startup
    sleep 5
    
    # Check if app is still running
    if ! kill -0 $APP_PID 2>/dev/null; then
        log_error "Application failed to start"
        log_error "Check logs: tail /tmp/archive_app.log"
        exit 1
    fi
    
    log_info "Sending test request..."
    # Send a test request
    if uv run python send_test_requests.py https://example.com >/dev/null 2>&1; then
        log_success "Test request sent successfully"
    else
        log_warning "Test request failed, but application is running"
    fi
    
    # Stop the application
    kill $APP_PID 2>/dev/null || true
    wait $APP_PID 2>/dev/null || true
    
    # Check if any archives were created
    if [[ -d "archives/example_com" ]]; then
        log_success "Archive generation test completed successfully"
    else
        log_warning "No archives generated in quick test"
    fi
}

# Print final instructions
print_final_instructions() {
    log_step "Setup Complete!"
    
    echo -e "${GREEN}"
    echo "🎉 Archive Generator setup completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Start the application:"
    echo "   uv run python main.py"
    echo ""
    echo "2. In another terminal, send test requests:"
    echo "   uv run python send_test_requests.py"
    echo ""
    echo "3. Or archive specific URLs:"
    echo "   uv run python send_test_requests.py https://example.com"
    echo ""
    echo "4. Check generated archives in:"
    echo "   ls -la archives/"
    echo ""
    echo "For more information, see:"
    echo "- README.md - Complete documentation"
    echo "- QUICK_START.md - Quick start guide"
    echo "- TROUBLESHOOTING.md - Common issues"
    echo -e "${NC}"
}

# Main execution
main() {
    log_info "Archive Generator Application Setup Script"
    log_info "This script will set up the complete development environment"
    echo ""
    
    # Run all setup steps
    check_project_directory
    check_system_requirements
    install_nodejs
    install_uv
    install_python_dependencies
    install_scoop_dependencies
    setup_permissions
    start_kafka
    verify_installation
    run_quick_test
    print_final_instructions
}

# Handle script interruption
trap 'log_error "Setup interrupted by user"; exit 1' INT TERM

# Run main function
main "$@"
