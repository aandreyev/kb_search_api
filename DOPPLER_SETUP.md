# Doppler Setup Guide

This guide covers how to set up Doppler secrets management for both local development and production environments.

## Prerequisites

- A Doppler account (sign up at [doppler.com](https://doppler.com))
- A project created in Doppler dashboard

## Local Development Setup

### 1. Install Doppler CLI

**macOS (Homebrew):**
```bash
brew install doppler
```

**Linux/WSL:**
```bash
# Install via script
curl -Ls https://cli.doppler.com/install.sh | sh

# Or via package manager (Ubuntu/Debian)
sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates curl gnupg
curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | sudo apt-key add -
echo "deb https://packages.doppler.com/public/cli/deb/debian any-version main" | sudo tee /etc/apt/sources.list.d/doppler-cli.list
sudo apt-get update && sudo apt-get install doppler
```

### 2. Authenticate with Doppler

```bash
# Login to Doppler
doppler login

# Verify authentication
doppler me
```

### 3. Configure Project

```bash
# Navigate to your project directory
cd /path/to/your/project

# Configure Doppler for this project
doppler setup

# Select your project and environment (e.g., "dev")
# This creates a .doppler.yaml file in your project
```

### 4. Verify Configuration

```bash
# Check current configuration
doppler configure

# View available secrets
doppler secrets

# Test secret retrieval
doppler secrets get SECRET_NAME
```

### 5. Run Your Application

```bash
# Method 1: Direct command execution
doppler run -- docker-compose up --build

# Method 2: Generate .env file (for compatibility)
doppler secrets download --no-file --format env > .env
docker-compose up --build
```

## Production Server Setup

### 1. Install Doppler CLI on Server

**Ubuntu/Debian:**
```bash
sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates curl gnupg
curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | sudo apt-key add -
echo "deb https://packages.doppler.com/public/cli/deb/debian any-version main" | sudo tee /etc/apt/sources.list.d/doppler-cli.list
sudo apt-get update && sudo apt-get install doppler
```

**CentOS/RHEL:**
```bash
sudo rpm --import 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key'
echo '[doppler]
name=Doppler packages
baseurl=https://packages.doppler.com/public/cli/rpm/any-version/
enabled=1
gpgcheck=1
gpgkey=https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | sudo tee /etc/yum.repos.d/doppler-cli.repo
sudo yum update && sudo yum install doppler
```

### 2. Create Service Token

**In Doppler Dashboard:**
1. Go to your project → environment (e.g., "prd")
2. Navigate to "Access" → "Service Tokens"
3. Click "Generate Service Token"
4. Copy the token (starts with `dp.st.`)

### 3. Configure Authentication on Server

```bash
# Method 1: Environment variable (recommended for containers)
export DOPPLER_TOKEN="dp.st.your-token-here"

# Method 2: Configure via CLI
echo "dp.st.your-token-here" | doppler configure set token --scope /path/to/project

# Method 3: Store in file (for systemd services)
echo "dp.st.your-token-here" | sudo tee /etc/doppler/token
sudo chmod 600 /etc/doppler/token
```

### 4. Set Up Project Configuration

```bash
# Navigate to project directory
cd /path/to/your/project

# Configure project and environment
doppler setup --project your-project --config prd

# Verify configuration
doppler configure
```

### 5. Production Deployment Options

#### Option A: Direct Command Execution
```bash
# Run application with Doppler
doppler run -- docker-compose up -d --build
```

#### Option B: Systemd Service
Create `/etc/systemd/system/your-app.service`:
```ini
[Unit]
Description=Your Application
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/your/project
Environment=DOPPLER_TOKEN=dp.st.your-token-here
ExecStart=/usr/bin/doppler run -- docker-compose up --build
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable your-app
sudo systemctl start your-app
```

#### Option C: Environment File Generation
```bash
# Generate .env file for production
doppler secrets download --no-file --format env > .env

# Use with Docker Compose
docker-compose up -d --build
```

## Security Best Practices

### Local Development
- ✅ Use `doppler login` for authentication
- ✅ Keep `.doppler.yaml` in version control
- ❌ Never commit `.env` files with secrets
- ✅ Use separate "dev" environment in Doppler

### Production
- ✅ Use service tokens, not personal tokens
- ✅ Rotate service tokens regularly
- ✅ Use separate "prd" environment in Doppler
- ✅ Limit service token permissions
- ✅ Store tokens securely (environment variables, not files)
- ✅ Use HTTPS for all Doppler API calls

## Troubleshooting

### Common Issues

**1. "Doppler CLI not found"**
```bash
# Check PATH
echo $PATH
# Add to PATH if needed
export PATH="/opt/homebrew/bin:$PATH"  # macOS
```

**2. "Authentication failed"**
```bash
# Re-authenticate
doppler logout
doppler login
```

**3. "Project not found"**
```bash
# Check available projects
doppler projects
# Reconfigure
doppler setup
```

**4. "No secrets found"**
```bash
# Check current configuration
doppler configure
# Verify environment
doppler secrets
```

### Debugging Commands

```bash
# Check Doppler status
doppler configure

# Test secret retrieval
doppler secrets get SECRET_NAME

# View all secrets (be careful in production)
doppler secrets

# Check token validity
doppler me
```

## Migration from .env Files

### 1. Upload Existing Secrets
```bash
# Upload from .env file
doppler secrets upload .env

# Or upload individual secrets
doppler secrets set SECRET_NAME=value
```

### 2. Update Application Code
Ensure your application uses the Doppler integration:

```python
# Python example
from doppler_integration import load_environment

# Load environment variables from Doppler or fallback to .env
load_environment()
```

### 3. Remove .env Files
```bash
# Add to .gitignore
echo ".env" >> .gitignore
echo ".env.*" >> .gitignore

# Remove from repository
git rm .env
git commit -m "Remove .env files, now using Doppler"
```

## Environment Management

### Recommended Structure
- **dev**: Local development environment
- **stg**: Staging/testing environment  
- **prd**: Production environment

### Promoting Secrets
```bash
# Copy secrets from dev to staging
doppler secrets download --project your-project --config dev --format json | \
doppler secrets upload --project your-project --config stg

# Or use Doppler dashboard for visual management
```

## Monitoring and Logging

### Enable Audit Logging
- Monitor secret access in Doppler dashboard
- Set up alerts for unauthorized access
- Review audit logs regularly

### Application Logging
```python
# Log when Doppler is used vs fallback
print("✅ Successfully loaded secrets from Doppler")
print("📁 Loading environment from .env file")
```

This setup ensures secure, scalable secret management across all your environments while maintaining compatibility with existing Docker and application workflows. 