<script lang="ts">
	import { onMount } from 'svelte';
	import { initializeAuth, authStore, logout } from '$lib/authStore';
	import type { AccountInfo } from '@azure/msal-browser';
	import '../app.css'; // Keep global styles

	let appIsInitializing: boolean = true; 
	let authErrorToDisplay: string | null = null;
    let isAuthenticated: boolean = false;
    let currentUser: AccountInfo | null = null;

	console.log("Layout: Script block executing (TOP LEVEL).");

	authStore.subscribe(value => {
	    console.log("Layout: authStore subscription update - isLoading:", value.isLoading, "Error:", value.error);
	    appIsInitializing = value.isLoading; // Driven by the store now
	    authErrorToDisplay = value.error;
        isAuthenticated = value.isAuthenticated;
        currentUser = value.user;
	});

	onMount(async () => {
		console.log("Layout: onMount - BEGIN.");
		try {
            console.log("Layout: onMount - Calling await initializeAuth()...");
			await initializeAuth(); 
			console.log("Layout: onMount - initializeAuth() awaited successfully.");
		} catch (e) {
			console.error("Layout: onMount - Error explicitly caught from initializeAuth() call:", e);
            // This catch might not be hit if initializeAuth handles its own errors and updates store
		} 
        // appIsInitializing is now primarily driven by the store's isLoading state
		console.log("Layout: onMount - END.");
	});

    async function handleLogout() {
        await logout();
    }
</script>

{#if appIsInitializing}
	<div class="flex justify-center items-center min-h-screen">
		<p class="text-xl text-gray-600">Initializing Application...</p>
		{#if authErrorToDisplay}
			<p class="text-red-500 mt-2">Auth Error: {authErrorToDisplay}</p>
		{/if}
	</div>
{:else}
	<div class="app-container min-h-screen flex flex-col">
		<header class="w-full p-4 bg-white shadow-sm sticky top-0 z-10">
			<div class="max-w-5xl mx-auto flex justify-between items-center">
				<div class="text-lg font-semibold text-gray-700">Knowledge Base</div>
				{#if isAuthenticated && currentUser}
					<div class="user-info text-xs text-gray-600 flex items-center">
						<span>Logged in as: {currentUser.name || currentUser.username}</span>
						<button 
							on:click={handleLogout} 
							class="ml-3 text-blue-600 hover:text-blue-800 hover:underline"
						>
							(Logout)
						</button>
					</div>
				{/if}
			</div>
		</header>

		<main class="flex-grow w-full">
			<slot />
		</main>

		<footer class="w-full p-4 text-center text-xs text-gray-500 border-t bg-white">
			{#if isAuthenticated && currentUser && currentUser.username}
				User: {currentUser.username}
			{/if}
			&copy; {new Date().getFullYear()} ADLV Law
		</footer>
	</div>
{/if}

<style>
	/* Add any global layout styles here if needed */
</style>