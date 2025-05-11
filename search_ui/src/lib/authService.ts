import { PublicClientApplication, type Configuration, LogLevel, type AuthenticationResult, InteractionRequiredAuthError, BrowserAuthError } from '@azure/msal-browser';

// MSAL Configuration
// IMPORTANT: Replace placeholders with your actual Azure App Registration values
// These should ideally come from environment variables, especially for client ID.
const MSAL_CLIENT_ID = import.meta.env.VITE_MSAL_CLIENT_ID || 'YOUR_APPLICATION_CLIENT_ID_HERE';
const MSAL_TENANT_ID = import.meta.env.VITE_MSAL_TENANT_ID || 'YOUR_DIRECTORY_TENANT_ID_HERE';
const MSAL_REDIRECT_URI = import.meta.env.VITE_MSAL_REDIRECT_URI || 'http://localhost:5173'; // Must match one registered in Azure

if (MSAL_CLIENT_ID === 'YOUR_APPLICATION_CLIENT_ID_HERE' || MSAL_TENANT_ID === 'YOUR_DIRECTORY_TENANT_ID_HERE') {
    console.warn(
        'MSAL placeholders not replaced in authService.ts. Authentication will likely fail. \n' +
        'Ensure VITE_MSAL_CLIENT_ID, VITE_MSAL_TENANT_ID, and VITE_MSAL_REDIRECT_URI are set in your .env file for development, \n' +
        'or provide them as build arguments for production.'
    );
}

const msalConfig: Configuration = {
    auth: {
        clientId: MSAL_CLIENT_ID,
        authority: `https://login.microsoftonline.com/${MSAL_TENANT_ID}`,
        redirectUri: MSAL_REDIRECT_URI,
        postLogoutRedirectUri: MSAL_REDIRECT_URI, // Where to redirect after logout
        navigateToLoginRequestUrl: false, // If true, will navigate back to the original page after login.
    },
    cache: {
        cacheLocation: 'sessionStorage', // 'localStorage' or 'sessionStorage' or 'memoryStorage'
        storeAuthStateInCookie: false, // Set to true if you have issues with Safari ITP
    },
    system: {
        loggerOptions: {
            loggerCallback: (level, message, containsPii) => {
                if (containsPii) {
                    return;
                }
                switch (level) {
                    case LogLevel.Error:
                        console.error(message);
                        return;
                    case LogLevel.Info:
                        // console.info(message);
                        return;
                    case LogLevel.Verbose:
                        // console.debug(message);
                        return;
                    case LogLevel.Warning:
                        // console.warn(message);
                        return;
                }
            },
            piiLoggingEnabled: false
        },
        // allowNativeBroker: false // Recommended to keep false for web apps - Comment out if causing type errors
    }
};

let msalInstance: PublicClientApplication | null = null;
let msalInstancePromise: Promise<PublicClientApplication> | null = null;

export async function getInitializedMsalInstance(): Promise<PublicClientApplication> {
    if (msalInstance) {
        console.log("authService: Returning already fully initialized MSAL instance.");
        return msalInstance;
    }
    if (!msalInstancePromise) {
        console.log("authService: No existing init promise. Kicking off MSAL initialization process...");
        // Create a new promise that will manage the entire async initialization
        msalInstancePromise = new Promise(async (resolve, reject) => {
            try {
                console.log("authService: Constructing PublicClientApplication...");
                const newInstance = new PublicClientApplication(msalConfig);
                console.log("authService: PublicClientApplication constructed.");

                console.log("authService: Calling and awaiting newInstance.initialize()...");
                await newInstance.initialize(); // Explicitly call and await initialize()
                console.log("authService: newInstance.initialize() completed.");

                // Give MSAL a microtask tick to settle, then call handleRedirectPromise
                await new Promise(r => setTimeout(r, 0)); 
                console.log("authService: Microtask tick passed. Calling handleRedirectPromise...");

                const response = await newInstance.handleRedirectPromise();
                console.log("authService: handleRedirectPromise completed.");

                if (response) {
                    console.log("authService: handleRedirectPromise response received, calling setActiveAccount.");
                    newInstance.setActiveAccount(response.account);
                    console.log("authService: Active account set by handleRedirectPromise:", response.account?.username);
                } else {
                    console.log("authService: handleRedirectPromise: No response to process.");
                }
                msalInstance = newInstance; // Assign the fully ready instance
                console.log("authService: MSAL instance fully initialized and assigned.");
                resolve(newInstance);
            } catch (error) {
                console.error("authService: Error during MSAL initialization sequence (inside promise):", error);
                msalInstance = null; // Ensure it's not considered initialized
                msalInstancePromise = null; // Allow retry on next call to getInitializedMsalInstance
                reject(error);
            }
        });
    } else {
        console.log("authService: Initialization promise already exists, awaiting it.");
    }
    return msalInstancePromise;
}

// Define the scopes your application needs.
// For Microsoft Graph, use 'https://graph.microsoft.com/.default' or specific permissions like 'User.Read'.
// For custom APIs (like your RAG API), you'll define scopes when you expose that API in Azure AD.
// For now, basic OpenID Connect scopes are usually enough for login and ID token.
export const loginRequest = {
    scopes: ['openid', 'profile', 'User.Read'] // User.Read allows fetching basic profile info
};

export const silentRequest = {
    scopes: ['openid', 'profile', 'User.Read'],
    forceRefresh: false
};

// Function to acquire token silently or with redirect
export async function acquireToken(): Promise<AuthenticationResult | null> {
    console.log("authService.acquireToken: Attempting to get initialized MSAL instance...");
    const currentMsalInstance = await getInitializedMsalInstance();
    console.log("authService.acquireToken: Got instance. Calling getAllAccounts.");
    const accounts = currentMsalInstance.getAllAccounts();
    if (accounts.length === 0) {
        console.log("authService.acquireToken: No accounts found.");
        return null;
    }
    
    const account = currentMsalInstance.getActiveAccount() || accounts[0];
    console.log(`authService.acquireToken: Using account: ${account?.username}. Calling acquireTokenSilent.`);
    const request = { scopes: ['openid', 'profile', 'User.Read'], account, forceRefresh: false };

    try {
        const tokenResponse = await currentMsalInstance.acquireTokenSilent(request);
        console.log("authService.acquireToken: acquireTokenSilent success.");
        return tokenResponse;
    } catch (error) {
        console.warn('Silent token acquisition failed in authService.acquireToken', error);
        if (error instanceof InteractionRequiredAuthError || error instanceof BrowserAuthError) {
            // Don't automatically redirect here; let the caller decide.
        } else {
            console.error('Unhandled error during token acquisition in authService:', error);
        }
        return null;
    }
}

// Initialize MSAL after the first JS code has loaded (on client side)
// This can help avoid issues if MSAL is initialized too early during SSR in SvelteKit
// though for SPA mode with adapter-static, it's less of an issue.
// We will call handleRedirectPromise on app load in authStore.ts instead.
/*
msalInstance.handleRedirectPromise()
    .then((response: AuthenticationResult | null) => {
        if (response) {
            msalInstance.setActiveAccount(response.account);
            // You can store response.accessToken and response.idToken if needed
            // Or dispatch an event / update a Svelte store to notify other components of login
            console.log("MSAL handleRedirectPromise success:", response.account?.username);
        }
    })
    .catch((error) => {
        console.error("MSAL handleRedirectPromise error:", error);
    });
*/

console.log("authService.ts loaded. Call getInitializedMsalInstance() to init and get MSAL."); 