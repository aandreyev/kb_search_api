#!/bin/bash

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

# Trap signals to ensure cleanup runs
trap cleanup SIGINT SIGTERM EXIT

# --- Activate Venv for the whole script ---
if [ -f "$VENV_ACTIVATOR" ]; then
  echo "Activating virtual environment..."
  source "$VENV_ACTIVATOR"
else
  echo "Warning: Virtual environment not found at $VENV_ACTIVATOR."
  # Decide if you want to exit if venv not found
  # exit 1
fi

# --- Read Ports from .env ---
# Load .env file variables into the current shell
set -o allexport # Export variables defined from now on
if [ -f "$ROOT_DIR/.env" ]; then
  source "$ROOT_DIR/.env"
else
  echo "Warning: .env file not found."
fi
set +o allexport # Stop exporting

# Use defaults if not set in .env
EMBEDDING_PORT=${EMBEDDING_SERVICE_PORT:-8001}
RAG_PORT=${RAG_API_PORT:-8002}

# --- Start Embedding Service ---
echo "Starting Embedding Service in background on port $EMBEDDING_PORT..."
(
  # cd into the directory is still good practice for the process
  cd "$EMBEDDING_SERVICE_DIR" || exit 1
  # Run python directly; relies on venv being active from parent script
  python main.py &
)

# --- Wait for Port and Find PID ---
echo "Checking if Embedding Service is listening on port $EMBEDDING_PORT..."
attempts=0
max_attempts=10 # Increase wait time slightly (10 * 2 = 20 seconds)
while ! nc -z 127.0.0.1 "$EMBEDDING_PORT" && [ $attempts -lt $max_attempts ]; do
  attempts=$((attempts+1))
  echo "  Port $EMBEDDING_PORT not listening yet, waiting (attempt $attempts)..."
  sleep 2
done

if ! nc -z 127.0.0.1 "$EMBEDDING_PORT"; then
  echo "ERROR: Embedding Service did not start listening on port $EMBEDDING_PORT after waiting." >&2
  echo "Check logs in embedding_service directory if possible."
  # PID variable is now set, so cleanup will try to kill it
  exit 1
fi
echo "Embedding Service is listening."

# Now that the port is listening, find the PID using lsof
# -t gives terse output (only PID)
# -i TCP:$EMBEDDING_PORT finds processes with TCP IPv4/6 socket on that port
# -sTCP:LISTEN filters for listening sockets
# head -n 1 takes the first PID found (usually sufficient)
EMBEDDING_PID=$(lsof -t -i TCP:"$EMBEDDING_PORT" -sTCP:LISTEN | head -n 1)

if [ -z "$EMBEDDING_PID" ]; then
    echo "ERROR: Port $EMBEDDING_PORT is listening, but could not find PID using lsof." >&2
    # This case is less likely but possible
    exit 1
fi
echo "Embedding Service found listening (PID: $EMBEDDING_PID)."

# --- Start RAG API Service ---
echo "----------------------------------------------------"
echo "Starting RAG API Service in foreground on port $RAG_PORT..."
# cd into the directory for this one too
cd "$RAG_API_SERVICE_DIR" || exit 1
# Run directly in foreground; relies on venv activated earlier
python main.py

# --- Script End / Cleanup Trigger ---
echo "----------------------------------------------------"
echo "RAG API Service has exited."
# Cleanup will be triggered automatically by EXIT trap 