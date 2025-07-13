#!/bin/bash

# Alternative script that generates .env file from Doppler for Docker Compose
# This approach creates a .env file that Docker Compose can read
# Use this if you prefer the .env file approach over direct Doppler integration

set -e  # Exit on any error

echo "🚀 Starting application with Doppler (using .env file approach)..."

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

# Backup existing .env file if it exists
if [ -f ".env" ]; then
    echo "📦 Backing up existing .env file to .env.backup"
    cp .env .env.backup
fi

# Generate .env file from Doppler
echo "📥 Generating .env file from Doppler secrets..."
if doppler secrets download --format=env --no-file > .env; then
    echo "✅ .env file generated successfully from Doppler"
else
    echo "❌ Failed to generate .env file from Doppler"
    # Restore backup if it exists
    if [ -f ".env.backup" ]; then
        echo "🔄 Restoring .env file from backup"
        mv .env.backup .env
    fi
    exit 1
fi

# Verify the .env file was created and has content
if [ ! -s ".env" ]; then
    echo "❌ Generated .env file is empty"
    exit 1
fi

# Check if required environment variables are in the .env file
echo "🔍 Checking for required variables in .env file..."
required_vars=("SUPABASE_URL" "SUPABASE_SERVICE_ROLE_KEY" "VITE_MSAL_CLIENT_ID" "VITE_MSAL_TENANT_ID")
missing_vars=()

for var in "${required_vars[@]}"; do
    if ! grep -q "^${var}=" .env; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ Missing required environment variables in .env file: ${missing_vars[*]}"
    echo "Please ensure these are set in your Doppler project"
    exit 1
fi

echo "✅ All required environment variables are present in .env file"

# Show some stats about the .env file
env_count=$(grep -c "^[A-Z]" .env || echo "0")
echo "📊 Generated .env file contains $env_count environment variables"

# Clean up any existing containers for a fresh start
echo "🧹 Cleaning up existing containers..."
docker-compose down --remove-orphans 2>/dev/null || true

# Start the application with Docker Compose
echo "🐳 Starting services with Docker Compose (using .env file)..."
if docker-compose up --build; then
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

# Cleanup function to remove .env file on exit
cleanup() {
    echo ""
    echo "🧹 Cleaning up generated .env file..."
    if [ -f ".env" ]; then
        rm -f .env
        echo "✅ .env file removed"
    fi
    
    # Restore backup if it exists
    if [ -f ".env.backup" ]; then
        echo "🔄 Restoring original .env file from backup"
        mv .env.backup .env
    fi
}

# Set up cleanup on script exit
trap cleanup EXIT 