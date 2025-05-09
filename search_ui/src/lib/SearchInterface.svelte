<script lang="ts">
    let query: string = '';
    let results: any[] = []; // Will hold the search results (SourceDocument[])
    let isLoading: boolean = false;
    let errorMessage: string | null = null;

    // URL for your RAG API service - adjust if needed
    // This could also come from an environment variable in a more complex app
    const RAG_API_URL = 'http://127.0.0.1:8002'; // Default port for rag_api_service

    interface ChunkSnippetData {
        content: string;
        similarity: number;
        chunk_index?: number | null;
    }

    interface SourceDoc {
        id: string | number;
        original_filename?: string | null;
        public_url?: string | null;
        title?: string | null;
        author?: string[] | null;
        last_modified?: string | null; // Will be string from JSON, convert if needed
        created_date?: string | null;  // Will be string from JSON, convert if needed
        file_type?: string | null;
        document_summary?: string | null;
        law_area?: string[] | null;
        document_category?: string | null;
        cleaned_filename?: string | null;
        analysis_notes?: string | null;
        snippets?: ChunkSnippetData[] | null;
    }

    async function performSearch() {
        if (!query.trim()) {
            errorMessage = 'Please enter a search query.';
            results = [];
            return;
        }

        isLoading = true;
        errorMessage = null;
        results = [];

        try {
            // Choose between /search or /chat endpoint
            // For now, let's use /search which returns structured documents directly
            const response = await fetch(`${RAG_API_URL}/search`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query: query }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.error) {
                errorMessage = data.error;
            } else if (data.results && data.results.length > 0) {
                results = data.results;
            } else {
                results = []; // No results found
                errorMessage = "No documents found matching your query.";
            }

        } catch (err: any) {
            console.error('Search API call failed:', err);
            errorMessage = err.message || 'Failed to fetch search results. Is the API service running?';
            results = [];
        } finally {
            isLoading = false;
        }
    }

    function handleKeydown(event: KeyboardEvent) {
        if (event.key === 'Enter') {
            performSearch();
        }
    }

    // Helper to format dates (optional)
    function formatDate(dateString: string | null | undefined): string {
        if (!dateString) return 'N/A';
        try {
            return new Date(dateString).toLocaleDateString();
        } catch (e) {
            return dateString; // Return original if parsing fails
        }
    }
</script>

<div class="container mx-auto p-4 max-w-3xl">
    <h1 class="text-2xl font-bold mb-6 text-center">Document Search</h1>

    <div class="search-bar mb-6 flex items-center space-x-2">
        <input 
            type="text" 
            bind:value={query} 
            on:keydown={handleKeydown}
            placeholder="Enter your search query..." 
            class="flex-grow p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow"
            disabled={isLoading}
        />
        <button 
            on:click={performSearch} 
            class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg shadow-md hover:shadow-lg transition-all duration-150 ease-in-out disabled:opacity-50"
            disabled={isLoading}
        >
            {#if isLoading}
                <span>Searching...</span>
            {:else}
                <span>Search</span>
            {/if}
        </button>
    </div>

    {#if errorMessage}
        <div class="error-message bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg relative mb-4 shadow" role="alert">
            <strong class="font-bold">Error:</strong>
            <span class="block sm:inline">{errorMessage}</span>
        </div>
    {/if}

    <div class="results-area space-y-6">
        {#if results.length > 0}
            <h2 class="text-xl font-semibold mb-4">Results:</h2>
            {#each results as result, i (result.id)} 
                <div class="result-item bg-white p-6 rounded-lg shadow-lg border border-gray-200 hover:shadow-xl transition-shadow duration-150 ease-in-out">
                    <h3 class="text-lg font-semibold text-blue-700 mb-2 break-words">
                        {i + 1}. {result.cleaned_filename || result.title || result.original_filename || `Document ID: ${result.id}`}
                    </h3>
                    
                    {#if result.document_summary}
                        <p class="text-gray-700 mb-3 summary">
                            <strong>Summary:</strong> {result.document_summary.substring(0, 250)}{result.document_summary.length > 250 ? '...' : ''}
                        </p>
                    {/if}

                    {#if result.analysis_notes}
                        <div class="analysis-notes mb-3">
                            <h4 class="font-semibold text-gray-700 mb-1">Analysis Notes:</h4>
                            <pre class="bg-gray-50 p-3 rounded-md text-sm text-gray-800 whitespace-pre-wrap font-sans break-words">{result.analysis_notes}</pre>
                        </div>
                    {/if}

                    <!-- Display Snippets -->
                    {#if result.snippets && result.snippets.length > 0}
                        <div class="snippets-container mt-3 mb-3">
                            <h5 class="font-medium text-gray-600 text-sm mb-1">Relevant Snippets:</h5>
                            <ul class="list-disc list-inside space-y-2 pl-1">
                                {#each result.snippets as snippet}
                                    <li class="text-xs text-gray-700 bg-gray-100 p-2 rounded-md">
                                        <p class="font-semibold">Score: {snippet.similarity.toFixed(4)} {#if snippet.chunk_index !== null && snippet.chunk_index !== undefined}(Chunk {snippet.chunk_index + 1}){/if}</p>
                                        <p class="snippet-content">{snippet.content.substring(0, 300)}{snippet.content.length > 300 ? '...' : ''}</p>
                                    </li>
                                {/each}
                            </ul>
                        </div>
                    {/if}

                    <div class="metadata grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-2 text-sm text-gray-600 mb-4">
                        {#if result.original_filename && result.original_filename !== (result.cleaned_filename || result.title)}
                            <p><strong>Original Filename:</strong> {result.original_filename}</p>
                        {/if}
                        {#if result.author && result.author.length > 0}
                            <p><strong>Author(s):</strong> {result.author.join(', ')}</p>
                        {/if}
                        {#if result.file_type}
                            <p><strong>File Type:</strong> {result.file_type}</p>
                        {/if}
                        {#if result.last_modified}
                            <p><strong>Last Modified:</strong> {formatDate(result.last_modified)}</p>
                        {/if}
                        {#if result.created_date}
                            <p><strong>Created Date:</strong> {formatDate(result.created_date)}</p>
                        {/if}
                        {#if result.document_category}
                            <p><strong>Category:</strong> {result.document_category}</p>
                        {/if}
                        {#if result.law_area && result.law_area.length > 0}
                            <p><strong>Law Area(s):</strong> {result.law_area.join(', ')}</p>
                        {/if}
                    </div>
                    
                    {#if result.public_url}
                        <a 
                            href={result.public_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            class="inline-block bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded-md shadow hover:shadow-md transition-colors duration-150 ease-in-out text-sm"
                        >
                            Download/View Document
                        </a>
                    {/if}
                </div>
            {/each}
        {:else if !isLoading && !errorMessage}
            <p class="text-gray-600 text-center py-4">No results to display. Try a new search.</p>
        {/if}
    </div>
</div>

<style>
    /* Basic Tailwind directives if not globally included - SvelteKit usually handles this with app.css or layout */
    /* @tailwind base;
    @tailwind components;
    @tailwind utilities; */

    /* Add any component-specific styles here if needed, beyond Tailwind classes */
    /* For example, a custom class for summaries if Tailwind truncation isn't enough */
    /* .summary {
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;  
        overflow: hidden;
    } */
    .snippet-content {
        display: -webkit-box;
        -webkit-line-clamp: 3; /* Show 3 lines */
        -webkit-box-orient: vertical;  
        overflow: hidden;
        text-overflow: ellipsis;
        margin-top: 0.25rem;
    }
</style> 