# Azure AD Authentication Issue Summary

## 1. Executive Summary

We are attempting to secure a web application using Microsoft Entra ID (Azure AD) for authentication. The application consists of a SvelteKit frontend and a Python FastAPI backend, containerized with Docker.

The core problem is that the backend API consistently rejects valid authentication tokens obtained by the frontend after a user successfully logs in. The validation fails with two distinct errors under different circumstances: `JWT Validation Error: Invalid audience` and `JWT Validation Error: Signature verification failed.`. Our attempts to make the backend validation more flexible to handle variations in Azure AD tokens have not resolved the issue.

## 2. System Architecture

-   **Frontend:** SvelteKit single-page application (SPA) using `@azure/msal-browser` for authentication against Azure AD.
-   **Backend:** Python FastAPI service providing a REST API (`/search`). This service is responsible for validating the JWT bearer token on protected endpoints.
-   **Deployment:** Both services are containerized and run via `docker-compose`.
-   **Secrets Management:** Environment variables (Client ID, Tenant ID, etc.) are injected into the containers via Doppler. The logs confirm these variables are being loaded correctly by the services.

## 3. The Problem in Detail

When the frontend makes an authenticated request to the backend's `/search` endpoint, the `Authorization: Bearer <token>` header is sent. The FastAPI service attempts to validate this token, but it fails, returning a `401 Unauthorized` error.

The failure manifests in two ways, depending on the exact token presented.

### Scenario A: "Invalid audience" Error

This is the most common failure. The frontend acquires a token where the audience (`aud` claim) is the **Application's Client ID**. The backend, despite being configured to accept this Client ID as a valid audience, rejects it.

**Example Token Payload (from logs):**

```json
{
  "aud": "b9d76cbb-9348-4b2e-a5cd-89eabcd59e73",
  "iss": "https://login.microsoftonline.com/65350b5c-f824-4876-bcaf-e550d6686f79/v2.0",
  "name": "Andrew Andreyev",
  "scp": "access_as_user",
  "ver": "2.0"
}
```

**Resulting Error (from logs):**

```
JWT Validation Error: Invalid audience
INFO:     172.64.149.246:56245 - "POST /search HTTP/1.1" 401 Unauthorized
```

### Scenario B: "Signature verification failed" Error

Less frequently, we see a token where the audience is for **Microsoft Graph**, and the issuer is `sts.windows.net`. This token is rejected with a signature failure. This suggests the keys we're using for validation are incorrect for this type of token.

**Example Token Payload (from logs):**

```json
{
  "aud": "00000003-0000-0000-c000-000000000000",
  "iss": "https://sts.windows.net/65350b5c-f824-4876-bcaf-e550d6686f79/",
  ...
}
```

**Resulting Error (from logs):**

```
JWT Validation Error: Signature verification failed.
INFO:     172.64.149.246:54408 - "POST /search HTTP/1.1" 401 Unauthorized
```

---

## 4. Code & Configuration

### Frontend MSAL Configuration

The SvelteKit frontend is configured in `search_ui/src/lib/authService.ts` to request the specific API scope.

```typescript
// search_ui/src/lib/authService.ts

// This is the scope required to call your backend API.
const API_SCOPE = import.meta.env.VITE_API_SCOPE || `api://${MSAL_CLIENT_ID}/access_as_user`;

export const msalConfig: Configuration = {
    auth: {
        clientId: import.meta.env.VITE_MSAL_CLIENT_ID,
        authority: `https://login.microsoftonline.com/${import.meta.env.VITE_MSAL_TENANT_ID}/v2.0`,
        redirectUri: import.meta.env.VITE_MSAL_REDIRECT_URI || window.location.origin,
        // ...
    },
    // ...
};

// ...

// When acquiring a token for the API, we use the specific scope.
export const apiRequest = {
    scopes: [API_SCOPE] 
};

export async function acquireToken(request: { scopes: string[] }): Promise<AuthenticationResult | null> {
    // ... standard MSAL acquireTokenSilent flow ...
}
```

### Backend Token Validation Logic

We have modified the `rag_api_service/security.py` file multiple times to be more flexible. The current version attempts to validate against a list of known-good audiences and issuers.

```python
# rag_api_service/security.py

import os
import requests
from functools import lru_cache
from typing import Dict, List

from fastapi import HTTPException, Security
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

# --- Configuration ---
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
API_SCOPE = os.getenv("API_SCOPE")

# Ensure all required variables are present
if not all([TENANT_ID, CLIENT_ID, API_SCOPE]):
    raise RuntimeError(
        "Required environment variables TENANT_ID, CLIENT_ID, or API_SCOPE are not set."
    )

# --- Azure AD Configuration ---
# The App ID URI, extracted from the full scope
AUDIENCE = API_SCOPE.rsplit("/", 1)[0]
VALID_AUDIENCES = [
    AUDIENCE,    # e.g., "api://b9d76cbb-9348-4b2e-a5cd-89eabcd59e73"
    CLIENT_ID,   # e.g., "b9d76cbb-9348-4b2e-a5cd-89eabcd59e73"
    "00000003-0000-0000-c000-000000000000"  # MS Graph API
]

VALID_ISSUERS = [
    f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
    f"https://sts.windows.net/{TENANT_ID}/"
]

JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

# ... (caching for JWKS) ...

# --- Verification Function ---
async def verify_token(token: str = Security(oauth2_scheme)):
    # ...
    try:
        # Debugging: Print the unverified claims
        unverified_payload = jwt.get_unverified_claims(token)
        print("--- UNVERIFIED TOKEN PAYLOAD ---")
        for k, v in unverified_payload.items():
            print(f"{k}: {v}")
        print("-------------------------------")

        # ... (code to find the correct signing key from JWKS) ...

        # THE POINT OF FAILURE:
        # This decode call fails even when the token's 'aud' and 'iss'
        # appear to be in the VALID_AUDIENCES and VALID_ISSUERS lists.
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
        raise credentials_exception # 401 Error
    # ...
```

---

## 5. Key Questions for the Architect

1.  **Why does `jwt.decode` fail on "Invalid audience"?** Given the code and the token payload in "Scenario A", the audience `b9d76cbb-9348-4b2e-a5cd-89eabcd59e73` is clearly present in the `VALID_AUDIENCES` list. Is there a known bug or a subtle configuration issue with the `python-jose` library that would cause it to reject a valid audience from a list?

2.  **Why does the signature verification fail?** For "Scenario B", the error is "Signature verification failed". We are fetching keys from the v2.0 endpoint (`.../discovery/v2.0/keys`). Is it possible that tokens issued by `sts.windows.net/{tenant}` must be validated against a different JWKS URL (e.g., a v1 endpoint)?

3.  **Is the frontend configuration optimal?** Is there a way to configure `@azure/msal-browser` to *guarantee* that the token it requests for our backend always has the `aud` claim set to our API's Application ID URI (`api://...`)? This would simplify the backend validation logic significantly.

4.  **Is there a better overall approach?** Are we missing a fundamental concept in Azure AD token validation? Is there a more robust pattern or library for handling the variations in tokens issued by Azure? 