import os
import requests
from functools import lru_cache
from typing import Dict

from fastapi import HTTPException, Security
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

# --- Configuration ---
# These values need to be present in your environment (loaded from Doppler/env)
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
API_SCOPE = os.getenv("API_SCOPE")

if not TENANT_ID or not CLIENT_ID or not API_SCOPE:
    print(f"[SECURITY] TENANT_ID: {TENANT_ID}")
    print(f"[SECURITY] CLIENT_ID: {CLIENT_ID}")
    print(f"[SECURITY] API_SCOPE: {API_SCOPE}")
    raise RuntimeError(
        "Required environment variables TENANT_ID, CLIENT_ID, or API_SCOPE are not set."
    )

print(f"[SECURITY] Configuration loaded:")
print(f"[SECURITY] TENANT_ID: {TENANT_ID}")
print(f"[SECURITY] CLIENT_ID: {CLIENT_ID}")
print(f"[SECURITY] API_SCOPE: {API_SCOPE}")
print(f"[SECURITY] AUDIENCE (calculated): {API_SCOPE.rsplit('/', 1)[0]}")

# Use both the Application ID URI and client ID as valid audiences
# Azure AD v2.0 tokens often use client ID as audience even when requesting API scopes
AUDIENCE = API_SCOPE.rsplit("/", 1)[0]  # Extract "api://client-id" from "api://client-id/access_as_user"
VALID_AUDIENCES = [
    AUDIENCE, 
    CLIENT_ID,
    "00000003-0000-0000-c000-000000000000"  # MS Graph API
]
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
OIDC_DISCOVERY_URL = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration"

# Azure AD can issue tokens from two different endpoints (v1 and v2).
# The tenant ID in the issuer URL ensures we only accept tokens from our directory.
VALID_ISSUERS = [
    f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
    f"https://sts.windows.net/{TENANT_ID}/"
]


print(f"[SECURITY] VALID_AUDIENCES: {VALID_AUDIENCES}")
print(f"[SECURITY] VALID_ISSUERS: {VALID_ISSUERS}")


# --- Helper Functions & Caching ---

@lru_cache(maxsize=1)
def get_oidc_config() -> Dict:
    """Fetches and caches the OIDC discovery configuration."""
    try:
        response = requests.get(OIDC_DISCOVERY_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch OIDC configuration: {e}") from e

@lru_cache(maxsize=1)
def get_jwks() -> Dict:
    """Fetches and caches the JSON Web Key Set (JWKS) from the jwks_uri in the OIDC config."""
    oidc_config = get_oidc_config()
    jwks_uri = oidc_config.get("jwks_uri")
    if not jwks_uri:
        raise RuntimeError("jwks_uri not found in OIDC configuration.")
    
    try:
        response = requests.get(jwks_uri, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch JWKS: {e}") from e

# --- FastAPI Security Dependency ---

# This scheme will look for an "Authorization: Bearer <token>" header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


async def verify_token(token: str = Security(oauth2_scheme)) -> Dict:
    """
    Decodes and validates an MSAL JWT access token.
    This is the core security dependency for protected endpoints.
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        print("[SECURITY] No token provided in Authorization header.")
        raise credentials_exception

    try:
        # 1. Get the unverified header to find the correct signing key
        unverified_header = jwt.get_unverified_header(token)
        
        # Print the unverified payload for debugging
        unverified_payload = jwt.get_unverified_claims(token)
        print("--- UNVERIFIED TOKEN PAYLOAD ---")
        for k, v in unverified_payload.items():
            print(f"{k}: {v}")
        print("-------------------------------")
        
        rsa_key = {}
        jwks = get_jwks()
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break
        if not rsa_key:
            print("[SECURITY] Signing key not found in JWKS.")
            raise JWTError("Signing key not found in JWKS.")

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            issuer=VALID_ISSUERS,
            audience=VALID_AUDIENCES,
        )
        
        return payload
    except JWTError as e:
        print(f"JWT Validation Error: {str(e)}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    except Exception as e:
        print(f"An unexpected error occurred during token validation: {str(e)}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")