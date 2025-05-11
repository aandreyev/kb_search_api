<script lang="ts">
    import { authStore, login, logout } from './authStore';
    import type { AccountInfo } from '@azure/msal-browser';

    // Subscribe to the auth store
    let currentUser: AccountInfo | null = null;
    let isAuthenticated: boolean = false;
    let isLoading: boolean = true;
    let authError: string | null = null;

    authStore.subscribe(value => {
        currentUser = value.user;
        isAuthenticated = value.isAuthenticated;
        isLoading = value.isLoading;
        authError = value.error;
    });

    async function handleLogin() {
        await login();
    }

    async function handleLogout() {
        await logout();
    }
</script>

<div class="auth-controls">
    {#if isLoading}
        <button class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 rounded-md cursor-wait" disabled>Loading...</button>
    {:else if isAuthenticated && currentUser}
        <div class="flex items-center space-x-3">
            <span class="text-sm text-gray-700">Welcome, {currentUser.name || currentUser.username}</span>
            <button 
                on:click={handleLogout} 
                class="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md shadow-sm transition-colors"
            >
                Logout
            </button>
        </div>
    {:else}
        <button 
            on:click={handleLogin} 
            class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md shadow-sm transition-colors"
        >
            Login with Microsoft
        </button>
    {/if}

    {#if authError && !isAuthenticated}
        <p class="text-xs text-red-500 mt-1">Error: {authError}</p>
    {/if}
</div> 