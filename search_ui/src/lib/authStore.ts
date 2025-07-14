import { writable, type Writable, get } from 'svelte/store';
import { 
    loginRequest as MsalLoginRequest, 
    acquireToken as msalAcquireTokenInternal, 
    getInitializedMsalInstance,
    apiRequest // Add this import
} from './authService';
import type { AccountInfo, AuthenticationResult, InteractionRequiredAuthError, BrowserAuthError } from '@azure/msal-browser';
import { logActivity, getUserLoggingInfo } from './activityLogger'; // Import logging utils

export interface AuthStore {
    isAuthenticated: boolean;
    user: AccountInfo | null;
    accessToken: string | null;
    error: string | null;
    isLoading: boolean;
}

const initialAuthState: AuthStore = {
    isAuthenticated: false,
    user: null,
    accessToken: null,
    error: null,
    isLoading: true, // Start in loading state to check for active account
};

export const authStore: Writable<AuthStore> = writable(initialAuthState);

let authInitializedPromise: Promise<void> | null = null;

async function _initializeAuthInternal(): Promise<void> {
    console.log("authStore: _initializeAuthInternal called. Setting isLoading to true.");
    authStore.update(s => ({...s, isLoading: true, error: null }));
    try {
        console.log("authStore: Calling getInitializedMsalInstance()...");
        const currentMsalInstance = await getInitializedMsalInstance(); // Get initialized instance
        console.log("authStore: getInitializedMsalInstance() completed. Attempting to get active account...");

        const activeAccount = currentMsalInstance.getActiveAccount();

        if (activeAccount) {
            console.log("authStore: Active account found after init:", activeAccount.username);
            const tokenResponse = await msalAcquireTokenInternal(apiRequest); // Pass the correct API scopes
            if (tokenResponse && tokenResponse.accessToken) {
                const userInfo = getUserLoggingInfo(activeAccount);
                authStore.set({
                    isAuthenticated: true,
                    user: activeAccount,
                    accessToken: tokenResponse.accessToken,
                    error: null,
                    isLoading: false,
                });
                console.log("authStore: User is authenticated (active account and token acquired).");
                logActivity({ event_type: 'USER_LOGIN_SUCCESS', ...userInfo });
            } else {
                 console.log("authStore: Active account found, but silent token acquisition failed.");
                 const userInfo = getUserLoggingInfo(activeAccount);
                 authStore.set({
                    isAuthenticated: false,
                    user: activeAccount,
                    accessToken: null,
                    error: "Silent token refresh failed.",
                    isLoading: false,
                });
                logActivity({ event_type: 'USER_SESSION_VALID_NEEDS_INTERACTION', ...userInfo });
            }
        } else {
            console.log("authStore: No active account found after MSAL initialization.");
            authStore.set({...initialAuthState, isLoading: false});
        }
    } catch (e) {
        console.error("authStore: Error during _initializeAuthInternal sequence:", e);
        const errorInfo = getUserLoggingInfo(null); // No user on init error
        logActivity({ event_type: 'USER_LOGIN_INIT_FAILURE', ...errorInfo, details: { error: (e as Error).message } });
        authStore.set({ isAuthenticated: false, user: null, accessToken: null, error: (e as Error).message || String(e), isLoading: false });
    } 
}

// Function to be called from app root to ensure initialization happens once
export function initializeAuth(): Promise<void> {
    if (!authInitializedPromise) {
        if (typeof window !== 'undefined') {
            authInitializedPromise = _initializeAuthInternal();
        } else {
            // Should not happen in SPA context for this logic path, but good to have
            authInitializedPromise = Promise.resolve(); 
        }
    }
    return authInitializedPromise;
}

// Auto-initialize when the store module is first loaded in a browser context.
// if (typeof window !== 'undefined') { // <<<< COMMENT THIS BLOCK OUT
//     console.log("authStore: Module loaded in browser, calling initializeAuth().");
//     initializeAuth(); 
// } // <<<< COMMENT THIS BLOCK OUT

export async function login(): Promise<void> {
    authStore.update(store => ({ ...store, isLoading: true, error: null }));
    try {
        const currentMsalInstance = await getInitializedMsalInstance();
        const preLoginUserInfo = getUserLoggingInfo(currentMsalInstance.getActiveAccount()); // Log with current (likely null) user
        logActivity({ event_type: 'USER_LOGIN_ATTEMPT', ...preLoginUserInfo });
        await currentMsalInstance.loginRedirect(MsalLoginRequest);
    } catch (error) {
        console.error("Login failed before redirect:", error);
        const userInfo = getUserLoggingInfo(null);
        logActivity({ event_type: 'USER_LOGIN_START_FAILURE', ...userInfo, details: { error: (error as Error).message } });
        authStore.set({ isAuthenticated: false, user: null, accessToken: null, error: (error as Error).message || String(error), isLoading: false });
    }
}

export async function logout(): Promise<void> {
    const currentUserInfo = getUserLoggingInfo(get(authStore).user); // Use get() for immediate store value
    
    authStore.update(store => ({ ...store, isLoading: true }));
    try {
        const currentMsalInstance = await getInitializedMsalInstance();
        logActivity({ event_type: 'USER_LOGOUT_ATTEMPT', ...currentUserInfo });
        const currentAccount = currentMsalInstance.getActiveAccount();
        if (currentAccount) {
            await currentMsalInstance.logoutRedirect({ account: currentAccount });
        } else {
            await currentMsalInstance.logoutRedirect();
        }
    } catch (error) {
        console.error("Logout failed:", error);
        logActivity({ event_type: 'USER_LOGOUT_FAILURE', ...currentUserInfo, details: { error: (error as Error).message } });
        authStore.update(store => ({ ...store, error: (error as Error).message || String(error), isLoading: false }));
    }
}

// Re-export acquireToken for components to use
export const acquireToken = msalAcquireTokenInternal; 