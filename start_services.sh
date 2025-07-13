#!/bin/bash

# Comprehensive startup script for kb_search_api
# This script provides multiple startup options:
# 1. Docker Compose with Doppler integration (recommended)
# 2. Docker Compose with .env file generation from Doppler
# 3. Local Python services with Doppler/env fallback
# 4. Automatic mode selection based on available tools

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check if Doppler is available and configured
check_doppler() {
    # Add Doppler to PATH if it's installed in common locations
    if [ -f "/opt/homebrew/bin/doppler" ]; then
        export PATH="/opt/homebrew/bin:$PATH"
    elif [ -f "/usr/local/bin/doppler" ]; then
        export PATH="/usr/local/bin:$PATH"
    fi
    
    if command -v doppler &> /dev/null; then
        if doppler configure debug &> /dev/null; then
            if doppler secrets --silent &> /dev/null; then
                return 0  # Doppler is available and configured
            fi
        fi
    fi
    return 1  # Doppler is not available or not configured
}

# Function to check if Docker is available
check_docker() {
    if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
        if docker info &> /dev/null; then
            return 0  # Docker is available and running
        fi
    fi
    return 1  # Docker is not available or not running
}

# Function to validate required environment variables
validate_environment() {
    log_info "Validating required environment variables..."
    
    required_vars=("SUPABASE_URL" "SUPABASE_SERVICE_ROLE_KEY")
    missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        log_error "Missing required environment variables: ${missing_vars[*]}"
        return 1
    fi
    
    log_success "All required environment variables are present"
    return 0
}

# Function to start with Docker Compose and Doppler
start_docker_doppler() {
    log_info "Starting with Docker Compose and Doppler integration..."
    
    # Clean up any existing containers
    log_info "Cleaning up existing containers..."
    docker-compose down --remove-orphans 2>/dev/null || true
    
    log_info "Starting services with Doppler secrets injection..."
    if doppler run -- docker-compose up --build; then
        log_success "Application started successfully with Docker and Doppler!"
        return 0
    else
        log_error "Failed to start application with Docker and Doppler"
        docker-compose down --remove-orphans 2>/dev/null || true
        return 1
    fi
}

# Function to start with Docker Compose and .env file from Doppler
start_docker_env() {
    log_info "Starting with Docker Compose using .env file from Doppler..."
    
    # Backup existing .env file if it exists
    if [ -f ".env" ]; then
        log_info "Backing up existing .env file to .env.backup"
        cp .env .env.backup
    fi
    
    # Generate .env file from Doppler
    log_info "Generating .env file from Doppler secrets..."
    if doppler secrets download --format=env --no-file > .env; then
        log_success ".env file generated successfully from Doppler"
    else
        log_error "Failed to generate .env file from Doppler"
        if [ -f ".env.backup" ]; then
            log_info "Restoring .env file from backup"
            mv .env.backup .env
        fi
        return 1
    fi
    
    # Validate the generated .env file
    if ! validate_environment; then
        return 1
    fi
    
    # Clean up any existing containers
    log_info "Cleaning up existing containers..."
    docker-compose down --remove-orphans 2>/dev/null || true
    
    # Start with Docker Compose
    log_info "Starting services with Docker Compose..."
    if docker-compose up --build; then
        log_success "Application started successfully with Docker and .env file!"
        return 0
    else
        log_error "Failed to start application with Docker"
        docker-compose down --remove-orphans 2>/dev/null || true
        return 1
    fi
}

# Function to start local Python services
start_local_python() {
    log_info "Starting local Python services..."
    
    # Check if virtual environment exists
    if [ ! -f "$ROOT_DIR/.venv/bin/activate" ]; then
        log_error "Virtual environment not found. Please run ./create_venv.sh first"
        return 1
    fi
    
    # Run the original start_api_services.sh script
    log_info "Running local Python services with environment variable injection..."
    exec "$ROOT_DIR/start_api_services.sh"
}

# Function to display usage information
show_usage() {
    echo "Usage: $0 [MODE]"
    echo ""
    echo "Modes:"
    echo "  docker-doppler    Start with Docker Compose and Doppler integration (recommended)"
    echo "  docker-env        Start with Docker Compose using .env file from Doppler"
    echo "  local            Start local Python services with Doppler/env fallback"
    echo "  auto             Automatically select the best available mode (default)"
    echo ""
    echo "Environment Requirements:"
    echo "  - For docker modes: Docker and Docker Compose must be installed and running"
    echo "  - For Doppler integration: Doppler CLI must be installed and configured"
    echo "  - For local mode: Python virtual environment must be created"
    echo ""
    echo "Examples:"
    echo "  $0                    # Auto mode (recommended)"
    echo "  $0 docker-doppler     # Force Docker with Doppler"
    echo "  $0 local             # Force local Python services"
}

# Function to auto-select the best mode
auto_select_mode() {
    log_info "Auto-selecting the best startup mode..."
    
    if check_docker; then
        log_success "Docker is available and running"
        if check_doppler; then
            log_success "Doppler is available and configured"
            log_info "Selected mode: Docker Compose with Doppler integration"
            return 0  # docker-doppler
        else
            log_warning "Doppler is not available or not configured"
            if [ -f ".env" ]; then
                log_info "Found .env file, using Docker Compose with .env"
                return 2  # docker-env (but without Doppler generation)
            else
                log_error "No .env file found and Doppler not available"
                return 3  # error
            fi
        fi
    else
        log_warning "Docker is not available or not running"
        if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
            log_info "Virtual environment found, using local Python services"
            return 1  # local
        else
            log_error "No virtual environment found and Docker not available"
            return 3  # error
        fi
    fi
}

# Main execution
main() {
    echo "🚀 KB Search API Startup Script"
    echo "================================"
    echo ""
    
    # Parse command line arguments
    MODE=${1:-auto}
    
    case $MODE in
        docker-doppler)
            if ! check_docker; then
                log_error "Docker is not available or not running"
                exit 1
            fi
            if ! check_doppler; then
                log_error "Doppler is not available or not configured"
                exit 1
            fi
            start_docker_doppler
            ;;
        docker-env)
            if ! check_docker; then
                log_error "Docker is not available or not running"
                exit 1
            fi
            if ! check_doppler; then
                log_error "Doppler is not available or not configured"
                exit 1
            fi
            start_docker_env
            ;;
        local)
            start_local_python
            ;;
        auto)
            auto_select_mode
            case $? in
                0) start_docker_doppler ;;
                1) start_local_python ;;
                2) 
                    # Docker available but no Doppler, use existing .env
                    log_info "Starting Docker Compose with existing .env file..."
                    docker-compose down --remove-orphans 2>/dev/null || true
                    docker-compose up --build
                    ;;
                3) 
                    log_error "No suitable startup mode available"
                    echo ""
                    echo "Please ensure one of the following:"
                    echo "  1. Docker is installed and running, and either:"
                    echo "     - Doppler is configured, or"
                    echo "     - A .env file exists"
                    echo "  2. A Python virtual environment is created (./create_venv.sh)"
                    exit 1
                    ;;
            esac
            ;;
        help|--help|-h)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown mode: $MODE"
            echo ""
            show_usage
            exit 1
            ;;
    esac
    
    # Display application URLs
    echo ""
    echo "📱 Application URLs:"
    echo "  Frontend: http://localhost:${FRONTEND_PORT_HOST:-5173}"
    echo "  RAG API: http://localhost:${RAG_API_PORT_HOST:-8002}"
    echo "  Embedding Service: http://localhost:${EMBEDDING_SERVICE_PORT_HOST:-8001}"
    echo "  Ollama: http://localhost:11434"
    echo ""
    echo "💡 To stop the application, press Ctrl+C"
}

# Cleanup function
cleanup() {
    echo ""
    log_info "Cleaning up..."
    
    # Remove generated .env file if it exists and we have a backup
    if [ -f ".env" ] && [ -f ".env.backup" ]; then
        log_info "Restoring original .env file from backup"
        mv .env.backup .env
    fi
}

# Set up cleanup on script exit
trap cleanup EXIT

# Run main function
main "$@" 