# Authentication Implementation in KB Search API

This document provides a detailed explanation of how authentication is implemented in the KB Search API application. The system uses Microsoft Entra ID (Azure AD) for authentication, with a SvelteKit frontend and a FastAPI backend. The implementation focuses on token-based authentication using JWTs, but has some limitations, particularly around scope validation.

## Overview
- **Frontend**: Uses the Microsoft Authentication Library (MSAL) to handle user login and acquire access tokens.
- **Backend**: Validates the JWT access tokens sent in API requests using the `python-jose` library. Validation includes signature verification, issuer check, and audience check, but does **not** currently enforce specific scopes.
- **Key Limitation**: The backend does not check for specific scopes (e.g., `access_as_user`). It relies on the audience claim and the token's validity, which means any valid token from the correct issuer and audience can access protected endpoints, as long as it was issued for the application.

This setup is a workaround due to challenges with Azure AD token formats and library behaviors. For production, consider adding scope checks to enhance security.

## Frontend Authentication (MSAL Integration)
The frontend uses `@azure/msal-browser` to authenticate users and acquire tokens. The configuration is in `search_ui/src/lib/authService.ts`.

### Key Code Excerpt
```typescript
// search_ui/src/lib/authService.ts (excerpt)
import { PublicClientApplication, InteractionType } from '@azure/msal-browser';

const msalConfig = {
  auth: {
    clientId: import.meta.env.VITE_MSAL_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_MSAL_TENANT_ID}`,
    redirectUri: import.meta.env.VITE_MSAL_REDIRECT_URI,
  },
  cache: {
    cacheLocation: 'localStorage',
    storeAuthStateInCookie: false,
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);

export async function getAccessToken() {
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length === 0) {
    return null;
  }

  const request = {
    scopes: [import.meta.env.VITE_API_SCOPE],
    account: accounts[0],
  };

  try {
    const response = await msalInstance.acquireTokenSilent(request);
    return response.accessToken;
  } catch (error) {
    // Fallback to interactive login if silent acquisition fails
    const response = await msalInstance.acquireTokenPopup(request);
    return response.accessToken;
  }
}
```

### How It Works
1. **Login**: The user clicks a login button, triggering MSAL to handle authentication via popup or redirect.
2. **Token Acquisition**: Tokens are acquired silently (if possible) or via popup. The requested scope is `api://<client-id>/access_as_user` (stored in `VITE_API_SCOPE`).
3. **Token Usage**: The acquired access token is attached to API requests in the `Authorization` header as `Bearer <token>`.

The frontend requests a specific scope, but the backend does not enforce it (see limitations below).

## Backend Token Validation
The backend validates tokens in `rag_api_service/security.py`. Protected endpoints (e.g., `/search`) depend on the `verify_token` function.

### Key Code Excerpt
```python
# rag_api_service/security.py (excerpt)
from jose import jwt, JWTError

# Configuration
VALID_AUDIENCES = [AUDIENCE, CLIENT_ID, "00000003-0000-0000-c000-000000000000"]  # App URI, Client ID, MS Graph
VALID_ISSUERS = [
    f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
    f"https://sts.windows.net/{TENANT_ID}/",
]

@lru_cache(maxsize=1)
def get_jwks_v2() -> Dict:
    response = requests.get(JWKS_URL_V2)
    return response.json()

@lru_cache(maxsize=1)
def get_jwks_v1() -> Dict:
    response = requests.get(JWKS_URL_V1)
    return response.json()

def verify_token(authorization: str = Security(oauth2_scheme)) -> Dict:
    if not authorization:
        raise credentials_exception

    token = authorization.split(" ")[1]  # Extract Bearer token

    try:
        unverified_claims = jwt.get_unverified_claims(token)
        unverified_header = jwt.get_unverified_header(token)

        # Determine JWKS based on issuer
        issuer = unverified_claims.get("iss")
        if issuer and f"https://sts.windows.net/{TENANT_ID}/" in issuer:
            jwks = get_jwks_v1()
        else:
            jwks = get_jwks_v2()

        # Find matching RSA key
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }

        if not rsa_key:
            raise JWTError("Signing key not found in JWKS.")

        # Decode token with minimal validation
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            options={"verify_signature": True, "verify_aud": False, "verify_iss": False},
        )

        # Manual issuer validation
        token_issuer = payload.get("iss")
        if not token_issuer or token_issuer not in VALID_ISSUERS:
            raise JWTError("Invalid issuer")

        # Manual audience validation
        token_audience = payload.get("aud")
        if not token_audience or token_audience not in VALID_AUDIENCES:
            raise JWTError("Invalid audience")

        return payload

    except JWTError as e:
        print(f"JWT Validation Error: {str(e)}")
        raise credentials_exception
```

### How It Works
1. **Token Extraction**: Extract the JWT from the `Authorization` header.
2. **JWKS Selection**: Choose the correct signing keys based on the token's issuer (v1 or v2 endpoint).
3. **Decoding**: Decode the token, verifying only the signature.
4. **Manual Checks**:
   - **Issuer**: Ensure it's from the trusted Azure AD tenant.
   - **Audience**: Ensure it matches the app's URI, client ID, or MS Graph (workaround for Azure behaviors).
5. **No Scope Check**: The `scp` claim (scopes) is present in the token but not validated.

If validation fails, a 401 error is returned.

## Limitations
- **No Scope Validation**: The backend does not check the `scp` claim for specific permissions (e.g., `access_as_user`). This means any valid token from the correct issuer/audience can access the API, even if it lacks the intended scope. This is a security limitation and should be addressed by adding a scope check in `verify_token` (e.g., `if "access_as_user" not in payload.get("scp", "").split(" "): raise JWTError("Missing required scope")`).
- **Manual Validation Workaround**: Due to issues with `python-jose` rejecting valid tokens, we manually validate issuer and audience after decoding. This works but is less elegant than using library features.
- **Environment Variables**: Relies on `TENANT_ID`, `CLIENT_ID`, `API_SCOPE` being set correctly via Doppler or `.env`. Fallbacks to `VITE_*` prefixes exist for local dev.
- **Token Variability**: Azure AD tokens can vary (v1 vs v2), requiring dual JWKS support.

## Recommendations for Improvement
- Add scope checking to `verify_token` for finer-grained access control.
- Consider switching to a library like `pyjwt` if `python-jose` issues persist.
- Test with different Azure AD configurations (e.g., multi-tenant) to ensure robustness.

Last updated: [Insert Date] 