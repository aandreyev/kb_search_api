#!/bin/bash

# Enhanced startup script with Doppler integration and .env fallback
# This script will:
# 1. Try to load environment variables from Doppler first
# 2. Fall back to .env file if Doppler is not available
# 3. Start services with proper environment variable injection

# Get the absolute path of the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
EMBEDDING_SERVICE_DIR="$ROOT_DIR/embedding_service"
RAG_API_SERVICE_DIR="$ROOT_DIR/rag_api_service"
VENV_ACTIVATOR="$ROOT_DIR/.venv/bin/activate"

EMBEDDING_PID=""

# Function to clean up background processes on exit
cleanup() {
  echo -e "\n>>> Cleaning up background services... <<<" # Use -e for newline
  # Use the PID captured when the port was confirmed listening
  if [ -n "$EMBEDDING_PID" ]; then
    # Check if the process still exists before trying to kill
    if ps -p "$EMBEDDING_PID" > /dev/null; then
        echo "Stopping Embedding Service (PID: $EMBEDDING_PID)..."
        # Send SIGTERM first for graceful shutdown
        kill -s TERM "$EMBEDDING_PID" 2>/dev/null
        # Wait a moment
        sleep 2
        # Force kill if still running
        if ps -p "$EMBEDDING_PID" > /dev/null; then
           echo "Embedding Service did not stop gracefully, sending SIGKILL..."
           kill -s KILL "$EMBEDDING_PID" 2>/dev/null
        fi
         echo "Embedding Service stop signal sent."
    else
        echo "Embedding Service process (PID: $EMBEDDING_PID) already stopped."
    fi
  else
    echo "Embedding Service PID was not captured."
  fi
  echo ">>> Cleanup finished <<<"
}

# Function to load environment variables from Doppler or .env
load_environment() {
    echo "🔧 Loading environment variables..."
    
    # Add Doppler to PATH if it's installed in common locations
    if [ -f "/opt/homebrew/bin/doppler" ]; then
        export PATH="/opt/homebrew/bin:$PATH"
    elif [ -f "/usr/local/bin/doppler" ]; then
        export PATH="/usr/local/bin:$PATH"
    fi
    
    # Check if Doppler CLI is available and configured
    if command -v doppler &> /dev/null && doppler configure debug &> /dev/null && doppler secrets --silent &> /dev/null; then
        echo "✅ Doppler is available and configured, loading secrets..."
        
        # Load environment variables from Doppler
        eval "$(doppler secrets download --format=env-no-quotes --no-file)"
        
        # Verify critical variables are loaded
        if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
            echo "✅ Successfully loaded environment variables from Doppler"
            return 0
        else
            echo "⚠️  Doppler secrets loaded but missing critical variables, falling back to .env"
        fi
    else
        echo "⚠️  Doppler not available or not configured, falling back to .env file"
    fi
    
    # Fallback to .env file
    if [ -f "$ROOT_DIR/.env" ]; then
        echo "📄 Loading environment variables from .env file..."
        set -o allexport # Export variables defined from now on
        source "$ROOT_DIR/.env"
        set +o allexport # Stop exporting
        echo "✅ Successfully loaded environment variables from .env file"
    else
        echo "❌ Neither Doppler nor .env file is available"
        echo "Please either:"
        echo "  1. Configure Doppler with 'doppler configure' and 'doppler login'"
        echo "  2. Create a .env file with required environment variables"
        exit 1
    fi
}

# Function to validate required environment variables
validate_environment() {
    echo "🔍 Validating required environment variables..."
    
    required_vars=("SUPABASE_URL" "SUPABASE_SERVICE_ROLE_KEY")
    missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        echo "❌ Missing required environment variables: ${missing_vars[*]}"
        exit 1
    fi
    
    echo "✅ All required environment variables are present"
}

# Trap signals to ensure cleanup runs
trap cleanup SIGINT SIGTERM EXIT

# Load environment variables (Doppler first, then .env fallback)
load_environment

# Validate environment variables
validate_environment

# --- Activate Venv for the whole script ---
if [ -f "$VENV_ACTIVATOR" ]; then
  echo "🐍 Activating virtual environment..."
  source "$VENV_ACTIVATOR"
else
  echo "⚠️  Warning: Virtual environment not found at $VENV_ACTIVATOR."
  echo "Please run ./create_venv.sh first"
  exit 1
fi

# Use defaults if not set in environment
EMBEDDING_PORT=${EMBEDDING_SERVICE_PORT:-8001}
RAG_PORT=${RAG_API_PORT:-8002}

echo "🚀 Starting services with environment variables loaded..."
echo "   Embedding Service Port: $EMBEDDING_PORT"
echo "   RAG API Port: $RAG_PORT"

# --- Start Embedding Service ---
echo "🔧 Starting Embedding Service in background on port $EMBEDDING_PORT..."
(
  # cd into the directory is still good practice for the process
  cd "$EMBEDDING_SERVICE_DIR" || exit 1
  # Run python directly; relies on venv being active from parent script
  python main.py &
)

# --- Wait for Port and Find PID ---
echo "⏳ Checking if Embedding Service is listening on port $EMBEDDING_PORT..."
attempts=0
max_attempts=15 # Increased wait time for better reliability
while ! nc -z 127.0.0.1 "$EMBEDDING_PORT" && [ $attempts -lt $max_attempts ]; do
  attempts=$((attempts+1))
  echo "  Port $EMBEDDING_PORT not listening yet, waiting (attempt $attempts/$max_attempts)..."
  sleep 2
done

if ! nc -z 127.0.0.1 "$EMBEDDING_PORT"; then
  echo "❌ ERROR: Embedding Service did not start listening on port $EMBEDDING_PORT after waiting." >&2
  echo "Check logs in embedding_service directory if possible."
  exit 1
fi
echo "✅ Embedding Service is listening."

# Now that the port is listening, find the PID using lsof
EMBEDDING_PID=$(lsof -t -i TCP:"$EMBEDDING_PORT" -sTCP:LISTEN | head -n 1)

if [ -z "$EMBEDDING_PID" ]; then
    echo "❌ ERROR: Port $EMBEDDING_PORT is listening, but could not find PID using lsof." >&2
    exit 1
fi
echo "✅ Embedding Service found listening (PID: $EMBEDDING_PID)."

# --- Start RAG API Service ---
echo "----------------------------------------------------"
echo "🔧 Starting RAG API Service in foreground on port $RAG_PORT..."
# cd into the directory for this one too
cd "$RAG_API_SERVICE_DIR" || exit 1
# Run directly in foreground; relies on venv activated earlier
python main.py

# --- Script End / Cleanup Trigger ---
echo "----------------------------------------------------"
echo "RAG API Service has exited."
# Cleanup will be triggered automatically by EXIT trap 