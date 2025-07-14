import os
import requests
from functools import lru_cache
from typing import Dict, List, Optional

from fastapi import HTTPException, Security
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

# --- Configuration ---
# Prioritize Doppler/container env vars, then fall back to Vite-prefixed vars for local dev.
TENANT_ID = os.getenv("TENANT_ID") or os.getenv("VITE_MSAL_TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID") or os.getenv("VITE_MSAL_CLIENT_ID")
API_SCOPE = os.getenv("API_SCOPE") or os.getenv("VITE_API_SCOPE")

# Final check to ensure all required variables are loaded.
missing_vars = []
if not TENANT_ID:
    missing_vars.append("TENANT_ID or VITE_MSAL_TENANT_ID")
if not CLIENT_ID:
    missing_vars.append("CLIENT_ID or VITE_MSAL_CLIENT_ID")
if not API_SCOPE:
    missing_vars.append("API_SCOPE or VITE_API_SCOPE")

if missing_vars:
    raise RuntimeError(f"Required environment variables are not set: {', '.join(missing_vars)}")

print("[SECURITY] Configuration loaded successfully.")

# This check is redundant due to the check above, but it satisfies the linter.
assert API_SCOPE is not None
assert CLIENT_ID is not None

# Use both the Application ID URI and client ID as valid audiences.
# Azure AD v2.0 tokens often use the client ID as audience.
# The API_SCOPE must exist at this point due to the check above.
AUDIENCE = API_SCOPE.rsplit("/", 1)[0]
VALID_AUDIENCES: List[str] = [
    AUDIENCE,
    CLIENT_ID,
    "00000003-0000-0000-c000-000000000000",  # MS Graph API, for tokens acquired via /.default scope
]

JWKS_URL_V2 = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
JWKS_URL_V1 = f"https://login.windows.net/common/discovery/keys"

# OIDC discovery URLs for both v1 and v2 endpoints
OIDC_DISCOVERY_URL_V2 = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration"
OIDC_DISCOVERY_URL_V1 = f"https://login.microsoftonline.com/{TENANT_ID}/.well-known/openid-configuration"


# Azure AD can issue tokens from two different endpoints (v1 and v2).
# The tenant ID in the issuer URL ensures we only accept tokens from our directory.
VALID_ISSUERS = [
    f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
    f"https://sts.windows.net/{TENANT_ID}/",
]


print(f"[SECURITY] VALID_AUDIENCES: {VALID_AUDIENCES}")
print(f"[SECURITY] VALID_ISSUERS: {VALID_ISSUERS}")


# --- Helper Functions & Caching ---
@lru_cache(maxsize=1)
def get_jwks_v1():
    """Fetches and caches JWKS from the v1 endpoint."""
    try:
        print(f"[SECURITY] Fetching JWKS from v1 endpoint: {JWKS_URL_V1}")
        response = requests.get(JWKS_URL_V1, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[SECURITY] ERROR: Could not fetch JWKS from v1 endpoint: {e}")
        return None

@lru_cache(maxsize=1)
def get_jwks_v2():
    """Fetches and caches JWKS from the v2 endpoint."""
    try:
        print(f"[SECURITY] Fetching JWKS from v2 endpoint: {JWKS_URL_V2}")
        response = requests.get(JWKS_URL_V2, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[SECURITY] ERROR: Could not fetch JWKS from v2 endpoint: {e}")
        return None

# --- FastAPI Security Dependency ---

# This scheme will look for an "Authorization: Bearer <token>" header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

credentials_exception = HTTPException(
    status_code=401,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def verify_token(token: str = Security(oauth2_scheme)):
    """
    Decodes and verifies a JWT token from Azure AD.
    
    It handles tokens from both v1.0 and v2.0 endpoints by checking the issuer
    and selecting the appropriate JSON Web Key Set (JWKS) for signature verification.
    """
    if not token:
        print("[SECURITY] No token provided in Authorization header.")
        raise credentials_exception

    try:
        # 1. Get the unverified header to find the correct signing key
        unverified_header = jwt.get_unverified_header(token)
        unverified_claims = jwt.get_unverified_claims(token)
        
        # Print the unverified payload for debugging
        print("--- UNVERIFIED TOKEN PAYLOAD ---", flush=True)
        for k, v in unverified_claims.items():
            print(f"{k}: {v}", flush=True)
        print("-------------------------------", flush=True)

        # Determine which JWKS to use based on the issuer
        issuer = unverified_claims.get("iss")
        print(f"[SECURITY] Token 'iss' claim: {issuer}", flush=True)

        if issuer and f"https://sts.windows.net/{TENANT_ID}/" in issuer:
            jwks = get_jwks_v1()
            print("[SECURITY] Identified issuer as v1. Using v1 JWKS.", flush=True)
        else:
            jwks = get_jwks_v2()
            print("[SECURITY] Identified issuer as v2 (or default). Using v2 JWKS.", flush=True)

        if not jwks:
            print("[SECURITY] CRITICAL: Could not retrieve JWKS.", flush=True)
            raise JWTError("Could not retrieve JWKS.")

        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                print(f"[SECURITY] Found matching signing key with kid: {unverified_header['kid']}", flush=True)
                break
        
        if not rsa_key:
            print(f"[SECURITY] CRITICAL: Signing key with kid '{unverified_header['kid']}' not found in JWKS.", flush=True)
            raise JWTError("Signing key not found in JWKS.")

        print(f"[SECURITY] Decoding token with signature and issuer...", flush=True)
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            # Issuer and audience are validated manually below.
            options={"verify_signature": True, "verify_aud": False, "verify_iss": False},
        )

        # Manually validate the issuer.
        token_issuer = payload.get("iss")
        if not token_issuer or token_issuer not in VALID_ISSUERS:
            print(f"[SECURITY] ERROR: Token issuer '{token_issuer}' is not in the valid list: {VALID_ISSUERS}", flush=True)
            raise JWTError("Invalid issuer")

        # Manually validate the audience.
        token_audience = payload.get("aud")
        if not token_audience or token_audience not in VALID_AUDIENCES:
            print(f"[SECURITY] ERROR: Token audience '{token_audience}' is not in the valid list: {VALID_AUDIENCES}", flush=True)
            raise JWTError("Invalid audience")

        print("[SECURITY] Token decoded and audience validated successfully.", flush=True)
        return payload
    except JWTError as e:
        print(f"JWT Validation Error: {str(e)}")
        raise credentials_exception from e
    except Exception as e:
        print(f"An unexpected error occurred during token validation: {e}")
        raise credentials_exception from e