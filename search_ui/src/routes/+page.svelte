<script lang="ts">
    import SearchInterface from '$lib/SearchInterface.svelte';
</script>

<svelte:head>
    <title>Document Search</title>
    <meta name="description" content="Search and find relevant documents" />
</svelte:head>

<div class="min-h-screen bg-gray-100 py-8">
    <SearchInterface />
</div>

<style>
    /* You can add global styles here or in app.html / app.css if needed */
    /* Ensure Tailwind is processed. If you used the SvelteKit CLI option to add Tailwind,
       it should have set up src/app.css and imported it in your root +layout.svelte */
</style>
