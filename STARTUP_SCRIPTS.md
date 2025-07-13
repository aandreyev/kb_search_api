# Startup Scripts Documentation

This document explains the different startup scripts available for the KB Search API project and how to use them.

## Overview

The project provides multiple startup scripts to accommodate different development environments and preferences:

1. **`start_services.sh`** - Comprehensive startup script with auto-detection (recommended)
2. **`start_with_doppler.sh`** - Docker Compose with direct Doppler integration
3. **`start_with_doppler_env.sh`** - Docker Compose with .env file generation from Doppler
4. **`start_api_services.sh`** - Local Python services with Doppler/env fallback

## Quick Start

For most users, the simplest approach is:

```bash
./start_services.sh
```

This script will automatically detect your environment and choose the best startup method.

## Script Details

### 1. `start_services.sh` (Recommended)

**Purpose**: Comprehensive startup script that automatically selects the best available method.

**Features**:
- Auto-detects Docker, Doppler, and virtual environment availability
- Provides multiple startup modes with fallback options
- Colored output and detailed logging
- Proper cleanup on exit

**Usage**:
```bash
./start_services.sh [MODE]
```

**Modes**:
- `auto` (default) - Automatically select the best mode
- `docker-doppler` - Force Docker with Doppler integration
- `docker-env` - Force Docker with .env file from Doppler
- `local` - Force local Python services

**Examples**:
```bash
./start_services.sh                    # Auto mode
./start_services.sh docker-doppler     # Force Docker with Doppler
./start_services.sh local             # Force local Python services
./start_services.sh --help            # Show help
```

### 2. `start_with_doppler.sh`

**Purpose**: Start Docker Compose services with direct Doppler integration.

**Features**:
- Validates Doppler configuration before starting
- Injects secrets directly into Docker containers
- Comprehensive environment variable validation
- Automatic cleanup on failure

**Requirements**:
- Docker and Docker Compose installed
- Doppler CLI installed and configured
- Access to Doppler secrets

**Usage**:
```bash
./start_with_doppler.sh
```

### 3. `start_with_doppler_env.sh`

**Purpose**: Generate .env file from Doppler secrets and start Docker Compose.

**Features**:
- Creates .env file from Doppler secrets
- Backs up existing .env file
- Validates generated environment variables
- Cleans up generated .env file on exit

**Requirements**:
- Docker and Docker Compose installed
- Doppler CLI installed and configured
- Access to Doppler secrets

**Usage**:
```bash
./start_with_doppler_env.sh
```

### 4. `start_api_services.sh`

**Purpose**: Start Python services locally with environment variable injection.

**Features**:
- Tries Doppler first, falls back to .env file
- Starts embedding service in background
- Starts RAG API service in foreground
- Proper process management and cleanup

**Requirements**:
- Python virtual environment created (run `./create_venv.sh`)
- Either Doppler configured or .env file present

**Usage**:
```bash
./start_api_services.sh
```

## Environment Requirements

### For Docker-based startup:
- Docker and Docker Compose installed and running
- Either:
  - Doppler CLI configured with access to secrets, or
  - A valid .env file with required variables

### For local Python startup:
- Python virtual environment created (`./create_venv.sh`)
- Either:
  - Doppler CLI configured with access to secrets, or
  - A valid .env file with required variables

### Required Environment Variables:
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
- `VITE_MSAL_CLIENT_ID` - Microsoft Azure AD client ID
- `VITE_MSAL_TENANT_ID` - Microsoft Azure AD tenant ID
- Additional variables as defined in your Doppler project or .env file

## Troubleshooting

### Doppler Issues:
```bash
# Check if Doppler is installed
doppler --version

# Check configuration
doppler configure debug

# Login if needed
doppler login

# Test access to secrets
doppler secrets
```

### Docker Issues:
```bash
# Check Docker status
docker info

# Check Docker Compose
docker-compose --version

# Clean up containers
docker-compose down --remove-orphans
```

### Virtual Environment Issues:
```bash
# Create virtual environment
./create_venv.sh

# Activate manually
source .venv/bin/activate

# Check Python path
which python
```

## Application URLs

Once started, the application will be available at:

- **Frontend**: http://localhost:5173
- **RAG API**: http://localhost:8002
- **Embedding Service**: http://localhost:8001
- **Ollama**: http://localhost:11434

## Stopping the Application

For all startup methods, press `Ctrl+C` to stop the application. The scripts will handle proper cleanup automatically.

## Best Practices

1. **Use `start_services.sh`** for most development work - it's the most flexible and user-friendly
2. **Use Doppler integration** when available for better security and secret management
3. **Keep .env files as fallback** for environments where Doppler isn't available
4. **Run cleanup commands** if you encounter issues with containers or processes

## Security Notes

- The scripts handle secrets securely and avoid exposing them in logs
- Generated .env files are automatically cleaned up after use
- Doppler integration is preferred over .env files for production environments
- Always ensure your Doppler project has appropriate access controls 