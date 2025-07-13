"""
Doppler integration module for loading environment variables from Doppler.
This module provides a fallback to .env files if Doppler is not available.
"""

import os
import subprocess
from typing import Optional, Dict, Any
from dotenv import load_dotenv

def load_doppler_secrets() -> Dict[str, str]:
    """
    Load secrets from Doppler CLI.
    Returns a dictionary of environment variables.
    """
    try:
        # Run doppler secrets command
        result = subprocess.run(
            ['doppler', 'secrets', 'download', '--format=env', '--no-file'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse the output
        secrets = {}
        for line in result.stdout.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                secrets[key] = value
        
        print("✅ Successfully loaded secrets from Doppler")
        return secrets
        
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Doppler CLI error: {e}")
        return {}
    except FileNotFoundError:
        print("⚠️  Doppler CLI not found. Falling back to .env file")
        return {}
    except Exception as e:
        print(f"⚠️  Error loading Doppler secrets: {e}")
        return {}

def load_environment() -> None:
    """
    Load environment variables from Doppler or fallback to .env file.
    This function should be called at the start of each service.
    """
    # Try to load from Doppler first
    doppler_secrets = load_doppler_secrets()
    
    if doppler_secrets:
        # Set environment variables from Doppler
        for key, value in doppler_secrets.items():
            os.environ[key] = value
        print("✅ Environment variables loaded from Doppler")
    else:
        # Fallback to .env file
        print("📁 Loading environment from .env file")
        
        # Try to load from parent directory first (for services)
        if os.path.exists('../.env'):
            load_dotenv(dotenv_path='../.env')
            print("✅ Loaded .env from parent directory")
        elif os.path.exists('.env'):
            load_dotenv()
            print("✅ Loaded .env from current directory")
        else:
            print("⚠️  No .env file found - using system environment variables")

def get_doppler_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a specific secret from Doppler or environment.
    
    Args:
        key: The secret key to retrieve
        default: Default value if not found
        
    Returns:
        The secret value or default
    """
    # First try to get from current environment
    value = os.getenv(key)
    if value is not None:
        return value
    
    # If not in environment, try to load from Doppler
    doppler_secrets = load_doppler_secrets()
    if doppler_secrets and key in doppler_secrets:
        return doppler_secrets[key]
    
    return default

def is_doppler_available() -> bool:
    """
    Check if Doppler CLI is available and configured.
    
    Returns:
        True if Doppler is available, False otherwise
    """
    try:
        result = subprocess.run(
            ['doppler', 'configure', 'info'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False 