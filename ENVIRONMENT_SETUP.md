# Environment Management Guide

This document explains how to manage different environments (development, production) using environment-specific configuration files.

## Overview

The project now supports clean environment separation using:
- **doppler.dev.yaml** / **doppler.prd.yaml**: Environment-specific Doppler configurations
- **docker-compose.dev.yml** / **docker-compose.prd.yml**: Environment-specific Docker overrides
- **Base docker-compose.yml**: Shared service definitions

## Environment Configurations

### Development Environment

**Characteristics:**
- Direct API calls (`VITE_RAG_API_URL="http://localhost:8002"`)
- Local redirect URI (`VITE_MSAL_REDIRECT_URI="http://localhost:5173"`)
- Hot reload support for code changes
- Debug logging enabled
- Minimal resource constraints

**Configuration Files:**
- `doppler.dev.yaml`: Doppler config pointing to 'dev' environment
- `docker-compose.dev.yml`: Development overrides

### Production Environment

**Characteristics:**
- Nginx proxy routing (`VITE_RAG_API_URL="/api"`)
- Production domain (`VITE_MSAL_REDIRECT_URI="https://kb.adlvlaw.au"`)
- Model preservation for faster deployments
- Resource limits and logging
- Always restart policies

**Configuration Files:**
- `doppler.prd.yaml`: Doppler config pointing to 'prd' environment  
- `docker-compose.prd.yml`: Production optimizations

## Setup Instructions

### Initial Setup (One-time)

1. **Create environment-specific secrets in Doppler:**
   ```bash
   # Configure dev environment
   doppler setup --config-file doppler.dev.yaml
   doppler secrets set SUPABASE_URL="your-dev-url"
   # ... set other dev secrets
   
   # Configure production environment
   doppler setup --config-file doppler.prd.yaml
   doppler secrets set SUPABASE_URL="your-prod-url"
   # ... set other production secrets
   ```

2. **Update model paths in production override:**
   ```bash
   # Edit docker-compose.prd.yml to update volume paths
   # Change /opt/kb_search_api_models/* to your actual model paths
   ```

### Development Workflow

```bash
# Switch to development configuration
doppler setup --config-file doppler.dev.yaml

# Start development environment
doppler run -- docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Or for hot reload development
doppler run -- docker compose -f docker-compose.yml -f docker-compose.dev.yml up embedding_service rag_api_service ollama
cd search_ui && npm run dev  # Run frontend separately for hot reload
```

### Production Deployment

```bash
# Switch to production configuration
doppler setup --config-file doppler.prd.yaml

# Deploy production environment
doppler run -- docker compose -f docker-compose.yml -f docker-compose.prd.yml up -d --build
```

### Quick Environment Switching

```bash
# Switch to development
ln -sf doppler.dev.yaml doppler.yaml
ln -sf docker-compose.dev.yml docker-compose.override.yml

# Switch to production
ln -sf doppler.prd.yaml doppler.yaml
ln -sf docker-compose.prd.yml docker-compose.override.yml

# Then use standard commands
doppler run -- docker compose up
```

## Migration Guide

### From Current Single-Environment Setup

1. **Backup current configuration:**
   ```bash
   cp doppler.yaml doppler.yaml.backup
   ```

2. **Determine your current environment:**
   ```bash
   doppler configure  # Check if using 'dev' or 'prd'
   ```

3. **Create environment-specific configs:**
   ```bash
   # If currently using 'dev'
   cp doppler.yaml doppler.dev.yaml
   
   # Create production config
   cp doppler.dev.yaml doppler.prd.yaml
   # Edit doppler.prd.yaml to change config: prd and update URLs
   ```

4. **Set up production secrets:**
   ```bash
   doppler setup --config-file doppler.prd.yaml
   # Copy secrets from dev or set new ones
   ```

5. **Update deployment scripts:**
   ```bash
   # Update start_with_doppler.sh to use specific config files
   # Update deployment_guide.md examples
   ```

### Model Path Configuration

Update the volume paths in `docker-compose.prd.yml` based on your actual setup:

```yaml
# For existing deployments, find current paths:
docker inspect ollama | grep -A 5 Mounts
docker inspect embedding_service | grep -A 5 Mounts

# Then update docker-compose.prd.yml volumes section
services:
  ollama:
    volumes:
      - /your/actual/ollama/path:/root/.ollama
  embedding_service:
    volumes:
      - /your/actual/cache/path:/root/.cache
```

## Environment Variables Reference

### Development-Specific Variables

```bash
VITE_RAG_API_URL="http://localhost:8002"  # Direct API access
VITE_MSAL_REDIRECT_URI="http://localhost:5173"  # Local redirect
NODE_ENV="development"
PYTHONUNBUFFERED="1"
OLLAMA_DEBUG="1"
```

### Production-Specific Variables

```bash
VITE_RAG_API_URL="/api"  # Nginx proxy route
VITE_MSAL_REDIRECT_URI="https://kb.adlvlaw.au"  # Production domain
NODE_ENV="production"
```

## Best Practices

1. **Never commit secrets:** Environment-specific .yaml files should only contain structure, not actual secret values
2. **Test locally first:** Always test changes in development before deploying to production
3. **Version control:** Keep environment-specific configs in version control, but use .gitignore for any files with secrets
4. **Backup before changes:** Always backup working configurations before making changes
5. **Document custom paths:** Update this guide when you change model storage paths

## Troubleshooting

### Common Issues

**Wrong environment active:**
```bash
doppler configure  # Check current config
doppler setup --config-file doppler.prd.yaml  # Switch to production
```

**Volume path errors:**
```bash
# Check actual paths
docker inspect ollama | grep Mounts
# Update docker-compose.prd.yml accordingly
```

**Build cache issues:**
```bash
docker compose build --no-cache
```

**Environment variable warnings:**
```bash
# These are normal when running docker compose commands without doppler context
# Actual containers get correct environment variables
```

## Future Enhancements

1. **Automated environment detection:** Script to auto-detect and configure appropriate environment
2. **Environment validation:** Scripts to verify environment-specific configurations
3. **Secrets synchronization:** Tools to help sync secrets between environments
4. **CI/CD integration:** GitHub Actions workflows for different environments 