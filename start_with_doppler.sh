#!/bin/bash

# Script to start the application with Doppler integration
# This script will:
# 1. Check if Doppler CLI is available
# 2. Validate Doppler configuration
# 3. Load environment variables from Doppler
# 4. Start the application with Docker Compose

set -e  # Exit on any error

echo "🚀 Starting application with Doppler integration..."

# Add Doppler to PATH if it's installed in common locations
if [ -f "/opt/homebrew/bin/doppler" ]; then
    export PATH="/opt/homebrew/bin:$PATH"
elif [ -f "/usr/local/bin/doppler" ]; then
    export PATH="/usr/local/bin:$PATH"
fi

# Check if Doppler CLI is available
if ! command -v doppler &> /dev/null; then
    echo "❌ Doppler CLI is not installed or not in PATH"
    echo "Please install Doppler CLI first:"
    echo "  - Visit https://cli.doppler.com/install"
    echo "  - Or use: curl -Ls --tlsv1.2 --proto '=https' --retry 3 https://cli.doppler.com/install.sh | sh"
    exit 1
fi

echo "✅ Doppler CLI is available"

# Check if Doppler is configured and authenticated
echo "🔍 Checking Doppler configuration..."
if ! doppler configure debug &> /dev/null; then
    echo "❌ Doppler is not configured properly"
    echo "Please run 'doppler configure' to set up your project and environment"
    exit 1
fi

# Validate that we can access secrets
echo "🔐 Validating Doppler secrets access..."
if ! doppler secrets --silent &> /dev/null; then
    echo "❌ Cannot access Doppler secrets"
    echo "Please ensure you're authenticated with 'doppler login' and have access to the project"
    exit 1
fi

echo "✅ Doppler is configured and secrets are accessible"

# Verify critical environment variables are available in Doppler
echo "🔍 Checking for required environment variables in Doppler..."
required_vars=("SUPABASE_URL" "SUPABASE_SERVICE_ROLE_KEY" "VITE_MSAL_CLIENT_ID" "VITE_MSAL_TENANT_ID")
missing_vars=()

for var in "${required_vars[@]}"; do
    if ! doppler secrets get "$var" --silent &> /dev/null; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ Missing required environment variables in Doppler: ${missing_vars[*]}"
    echo "Please add these secrets to your Doppler project"
    exit 1
fi

echo "✅ All required environment variables are available in Doppler"

# Load environment variables from Doppler and export them for docker-compose
echo "📥 Loading environment variables from Doppler..."

# Clean up any existing containers and images for a fresh start
echo "🧹 Cleaning up existing containers..."
docker-compose down --remove-orphans 2>/dev/null || true

# Use Doppler's official Docker Compose integration
echo "🐳 Starting services with Docker Compose using Doppler..."
echo "   This will inject all secrets from Doppler into the containers..."

# Run with doppler to ensure all environment variables are injected
if doppler run -- docker-compose up --build; then
    echo "🎉 Application started successfully!"
else
    echo "❌ Failed to start application"
    echo "🧹 Cleaning up failed containers..."
    docker-compose down --remove-orphans 2>/dev/null || true
    exit 1
fi

echo ""
echo "📱 Application URLs:"
echo "  Frontend: http://localhost:${FRONTEND_PORT_HOST:-5173}"
echo "  RAG API: http://localhost:${RAG_API_PORT_HOST:-8002}"
echo "  Embedding Service: http://localhost:${EMBEDDING_SERVICE_PORT_HOST:-8001}"
echo "  Ollama: http://localhost:11434"
echo ""
echo "💡 To stop the application, press Ctrl+C" 