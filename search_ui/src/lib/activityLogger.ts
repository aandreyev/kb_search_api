import type { AccountInfo } from '@azure/msal-browser';

// Get base URL from Vite environment variables for local dev, fallback for build/other envs
const RAG_API_BASE_URL = import.meta.env.VITE_RAG_API_URL || ''; // Empty string fallback makes it a relative path if var not set
const LOG_API_ENDPOINT = `${RAG_API_BASE_URL}/log-activity`;

interface LogPayload {
    event_type: string;
    user_id?: string | null; // OID or sub from MSAL AccountInfo
    username?: string | null; // Preferred username or name from MSAL AccountInfo
    search_term?: string | null;
    document_id?: string | number | null;
    document_filename?: string | null;
    preview_type?: string | null;
    details?: Record<string, any> | null;
}

export async function logActivity(payload: LogPayload): Promise<void> {
    if (!payload.event_type) {
        console.error("logActivity: event_type is required.");
        return;
    }

    // Only attempt to log via API if in a browser environment
    if (typeof window === 'undefined') {
        console.log("logActivity: Skipping API call (not in browser environment). Event:", payload.event_type, "Target URL would be:", LOG_API_ENDPOINT);
        return;
    }

    console.log("Logging activity (browser):", payload.event_type, payload);

    try {
        const response = await fetch(LOG_API_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // No Authorization header needed here if the logging endpoint itself is not protected
                // Or, if it IS protected, you'd need to acquire and send a token.
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            console.error('Failed to log activity to API:', response.status, errorData.detail || response.statusText);
        } else {
            const responseData = await response.json();
            if (responseData.status !== 'success' && responseData.status !== 'success_nodata') {
                console.warn('Activity logging API reported an issue:', responseData);
            }
            // console.log('Activity logged via API:', responseData);
        }
    } catch (error) {
        console.error('Error calling activity logging API:', error);
    }
}

// Helper to get user info from MSAL account for logging
export function getUserLoggingInfo(account: AccountInfo | null): { user_id: string | null; username: string | null } {
    if (!account) {
        return { user_id: null, username: 'Anonymous' };
    }
    return {
        user_id: account.idTokenClaims?.oid || account.idTokenClaims?.sub || account.localAccountId, // Object ID or Subject
        username: account.name || account.username, // Display name or username
    };
} 