# Digital Ocean Deployment Guide - Application Upgrade

## Overview

This guide documents the proven process for upgrading the KB Search API application on Digital Ocean with minimal downtime. Based on real deployment experience, this covers both standard deployment and advanced techniques like model preservation.

## Pre-Deployment Analysis

### 1. Check Current Deployment

First, understand your current setup:

```bash
# SSH to your droplet
ssh root@your-droplet-ip

# Check running containers
docker ps

# Identify model and cache locations
docker inspect ollama | grep -A 10 -B 10 Mounts
docker inspect embedding_service | grep -A 10 -B 10 Mounts
```

Expected output will show your model storage paths (e.g., `/home/andrew/apps/semantic_search_app/ollama_data`).

### 2. Environment Variables Required

For production deployment, you'll need these key environment variables:

```bash
# Production Frontend URLs (CRITICAL)
VITE_RAG_API_URL="/api"  # Must be /api for production nginx proxy
VITE_MSAL_REDIRECT_URI="https://your-domain.com"  # Your actual domain

# Authentication (Microsoft Azure AD)
VITE_MSAL_CLIENT_ID="your-client-id"
VITE_MSAL_TENANT_ID="your-tenant-id"
VITE_API_SCOPE="api://your-app-id/.default"
TENANT_ID="your-tenant-id" 
CLIENT_ID="your-client-id"
API_SCOPE="api://your-app-id/.default"

# Database (Supabase)
SUPABASE_URL="your-supabase-url"
SUPABASE_SERVICE_ROLE_KEY="your-service-key"
SUPABASE_DB_PASSWORD="your-db-password"

# Service Configuration
EMBEDDING_MODEL_NAME="BAAI/bge-large-en-v1.5"
OLLAMA_MODEL="phi3:mini"
LLM_PROVIDER="ollama"  # or "openai"
```

## Environment Separation Strategy (Recommended)

### Option A: Separate Configuration Files

Create environment-specific configurations:

**For Development:**
```bash
# doppler.dev.yaml
setup:
  project: kb-search-api
  config: dev

# docker-compose.dev.yml  
# Contains localhost URLs and development overrides
```

**For Production:**
```bash
# doppler.prd.yaml
setup:
  project: kb-search-api
  config: prd

# docker-compose.prd.yml
# Contains production URLs and optimizations
```

**Usage:**
```bash
# Development
doppler setup --config-file doppler.dev.yaml
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Production  
doppler setup --config-file doppler.prd.yaml
docker compose -f docker-compose.yml -f docker-compose.prd.yml up
```

### Option B: Single Configuration with Environment Switching

Keep current setup but document environment switching:

```bash
# Switch environments
doppler configure set config dev   # For development
doppler configure set config prd   # For production
```

## Deployment Process

### Phase 1: Preparation

```bash
# 1. SSH into your droplet
ssh root@your-droplet-ip

# 2. Create deployment directory
mkdir -p /opt/kb_search_api
cd /opt/kb_search_api

# 3. Clone your updated code
git clone https://github.com/your-username/kb_search_api.git .
```

### Phase 2: Environment Setup

#### Install and Configure Doppler

```bash
# Install Doppler CLI
curl -Ls https://cli.doppler.com/install.sh | sh

# Login (will provide URL and code for browser authentication)
doppler login

# Configure project (use repo config file)
doppler setup
# Answer "Y" to use settings from doppler.yaml

# Switch to production environment
doppler configure set config prd

# Verify configuration
doppler configure
doppler secrets  # Check all secrets are loaded
```

#### Critical Production Settings Verification

Ensure these are set correctly in Doppler:
```bash
# Must be exactly these values for production
VITE_RAG_API_URL="/api"
VITE_MSAL_REDIRECT_URI="https://your-actual-domain.com"
```

### Phase 3: Model Preservation (Recommended)

#### Option A: Use Pre-configured Model Preservation (Easiest)

For the tested deployment paths, use the ready-made configuration:

```bash
# No setup needed - just use the pre-configured file
# This preserves models from /home/andrew/apps/semantic_search_app/
```

#### Option B: Custom Model Preservation

If your model paths are different, create a custom override:

```bash
# Find current model locations
docker inspect ollama | grep -A 5 Mounts
docker inspect embedding_service | grep -A 5 Mounts

# Create docker-compose.override.yml to reuse existing models
cat > docker-compose.override.yml << 'EOF'
services:
  ollama:
    volumes:
      - /path/to/existing/ollama_data:/root/.ollama
      
  embedding_service:
    volumes:
      - /path/to/existing/embedding_cache:/root/.cache
EOF
```

#### Option C: No Model Preservation

Skip this phase to download fresh models (slower but clean setup).

### Phase 4: Pre-flight Validation

```bash
# Test configuration (important step!)
doppler run -- docker compose config

# Verify override file if using model preservation
cat docker-compose.override.yml

# Check disk space
df -h
docker system df
```

### Phase 5: Deployment Execution

#### Quick Replacement Method (Brief Downtime)

```bash
# 1. Stop old containers (get exact names from docker ps)
docker stop rag_api_service frontend_nginx embedding_service ollama

# 2. Remove old containers to free names
docker rm rag_api_service frontend_nginx embedding_service ollama

# 3. Start new version
# Option A: With model preservation (recommended)
doppler run -- docker compose -f docker-compose.yml -f docker-compose.prd-with-models.yml up -d --build

# Option B: Basic deployment (may re-download models)
# doppler run -- docker compose up -d --build

# 4. Monitor startup
docker compose ps
docker compose logs -f
```

**Note:** Use `docker compose` (with space) not `docker-compose` on newer Docker installations.

### Phase 6: Verification and Testing

```bash
# 1. Check all containers are running
docker compose ps

# 2. Test health endpoints
curl http://localhost:8002/health
curl http://localhost:8001/health

# 3. Test frontend serving
curl -I http://localhost:5173

# 4. CRITICAL: Test API proxy (what frontend actually uses)
curl http://localhost:5173/api/health

# 5. Check logs for errors
docker compose logs --tail=50
```

Expected successful responses:
- Health check: `{"status":"RAG API Service is running","rag_initialized":true}`
- Frontend: `HTTP/1.1 200 OK`
- API proxy: Same health check response through nginx

### Phase 7: Cleanup

```bash
# Remove old images to free space
docker image prune -f

# Check final disk usage
df -h
docker system df
```

## Common Issues and Solutions

### Container Name Conflicts
**Problem:** `Error: container name already in use`
**Solution:** 
```bash
docker rm container_name  # Remove stopped container
```

### Environment Variable Warnings
**Problem:** Warnings about unset variables during `docker compose ps`
**Solution:** These are normal when running without Doppler context. The containers themselves have correct environment variables.

### Docker Compose Command Not Found
**Problem:** `docker-compose: command not found`
**Solution:** Use `docker compose` (space, not hyphen) on newer Docker installations.

### Model Re-download
**Problem:** Ollama downloading models again
**Solution:** Ensure docker-compose.override.yml correctly maps existing model directory.

## Rollback Procedure

If deployment fails:

```bash
# Quick rollback to previous working directory
cd /home/andrew/apps/semantic_search_app
docker compose up -d

# Or start individual old containers if they still exist
docker start old_container_names
```

## Performance Considerations

- **Model Reuse:** Saves 1-3GB download and 5-10 minutes startup time
- **Embedding Cache:** Faster model loading on first embedding request
- **Build Caching:** Docker layer caching speeds up subsequent builds
- **Network:** Brief downtime during container swap (~30-60 seconds)

## Security Notes

- **Doppler Production:** Use separate 'prd' environment for production secrets
- **Container Names:** New deployment uses cleaner names without app prefix
- **Port Exposure:** Same ports as before, minimal attack surface change
- **Volume Permissions:** Existing volumes maintain correct permissions

## Future Improvements

### 1. Environment-Specific Configurations

Create separate config files for better environment isolation:

```bash
# Create development-specific config
cp doppler.yaml doppler.dev.yaml
# Edit to use 'dev' config and localhost URLs

# Create production-specific config  
cp doppler.yaml doppler.prd.yaml
# Edit to use 'prd' config and production URLs

# Remove original generic doppler.yaml
rm doppler.yaml
```

### 2. Deployment-Specific Docker Compose

```bash
# Create docker-compose.dev.yml with development overrides
# Create docker-compose.prd.yml with production optimizations
# Keep base docker-compose.yml for common services
```

### 3. Automated Health Checks

Add monitoring to verify deployment success:
```bash
# Add to deployment script
wait_for_health() {
  echo "Waiting for services to be healthy..."
  for i in {1..30}; do
    if curl -sf http://localhost:8002/health > /dev/null; then
      echo "✅ Services healthy!"
      return 0
    fi
    sleep 10
  done
  echo "❌ Health check failed"
  return 1
}
```

## Tested Configuration

This guide is based on a successful deployment with:
- **Domain:** `https://kb.adlvlaw.au`
- **Droplet:** 2vCPU, 4GB RAM, Sydney region
- **Docker:** Modern version with `docker compose` command
- **Models:** Existing Ollama phi3:mini model preserved
- **Downtime:** ~60 seconds total
- **Environment:** Doppler-managed production secrets

The deployment process took approximately 5 minutes total, with most time spent on Docker builds rather than model downloads.

## Configuration Files Reference

### docker-compose.prd-with-models.yml

Ready-to-use production configuration with model preservation for the tested deployment setup:

**Features:**
- Preserves existing models from `/home/andrew/apps/semantic_search_app/`
- Production resource limits and restart policies
- Log rotation configured
- Zero model download time

**Usage:**
```bash
doppler run -- docker compose -f docker-compose.yml -f docker-compose.prd-with-models.yml up -d --build
```

### Environment-Specific Configurations

For advanced environment management, see:
- `doppler.dev.yaml` / `doppler.prd.yaml` - Environment-specific Doppler configs
- `docker-compose.dev.yml` / `docker-compose.prd.yml` - Environment-specific Docker overrides
- `ENVIRONMENT_SETUP.md` - Comprehensive environment management guide 