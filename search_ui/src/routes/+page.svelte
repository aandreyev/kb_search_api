<!-- search_ui/src/routes/+page.svelte (Temporary Ultra-Simple Test) -->
<script lang="ts">
	import SearchInterface from '$lib/SearchInterface.svelte';
	import LoginButton from '$lib/LoginButton.svelte';
	import { authStore } from '$lib/authStore';
	// import type { AccountInfo } from '@azure/msal-browser'; // Not directly used in this component's script

	let isAuthenticated: boolean = false;
	let isLoadingAuth: boolean = true;
	let authError: string | null = null;

	authStore.subscribe(value => {
		isAuthenticated = value.isAuthenticated;
		isLoadingAuth = value.isLoading;
		authError = value.error;
		if(typeof window !== 'undefined') { 
			// console.log("Page: authStore subscription update - isLoadingAuth:", isLoadingAuth, "isAuthenticated:", isAuthenticated, "Error:", authError);
		}
	});

	// onMount(() => { // Simple onMount log kept from diagnostic
	// 	console.log("Page: onMount HAS BEEN EXECUTED (Client Side).");
	// });
</script>

<svelte:head>
	<title>Document Search</title>
	<meta name="description" content="Search and find relevant documents" />
</svelte:head>

<!-- This div will be part of the <main> slot from +layout.svelte -->
<div class="w-full flex flex-col items-center">
	{#if isLoadingAuth}
		<div class="p-6 mt-8 bg-white shadow-md rounded-lg text-center w-full max-w-md">
			<p class="text-gray-600">Loading authentication status...</p>
		</div>
	{:else if isAuthenticated}
		<!-- SearchInterface will take full width available from layout -->
		<SearchInterface />
	{:else}
		<div class="p-6 mt-8 bg-white shadow-md rounded-lg text-center w-full max-w-md">
			<h1 class="text-xl font-semibold mb-4">Welcome to Knowledge Base</h1>
			<p class="text-gray-700 mb-6">Please log in with your Microsoft account to access the document search functionality.</p>
			<LoginButton /> 
			{#if authError}
				<p class="text-red-500 text-sm mt-4">Authentication Error: {authError}</p>
			{/if}
		</div>
	{/if}
</div>

<style>
	/* Add any global styles here or in app.html / app.css if needed */
</style>
