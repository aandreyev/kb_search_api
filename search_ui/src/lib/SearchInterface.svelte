<script lang="ts">
    import { tick } from 'svelte'; // Import tick
    import { authStore, acquireToken, logout } from './authStore'; // Import from authStore
    import { apiRequest } from './authService'; // Import apiRequest from authService
    import { logActivity, getUserLoggingInfo } from './activityLogger'; // Import logging utils
    import type { AccountInfo } from '@azure/msal-browser'; // For user type
    import { onMount } from 'svelte';
    // Local interface definitions
    let query: string = '';
    let results: any[] = []; // Will hold the search results (SourceDocument[])
    let isLoading: boolean = false;
    let errorMessage: string | null = null;
    let previewUrl: string | null = null;
    let showPreviewModal: boolean = false;
    let previewTitle: string = "Document Preview";
    let previewType: 'pdf' | 'html' | null = null;
    // let docxHtmlContent: string = ""; // No longer needed if not using Mammoth for DOCX
    // let mammoth: any = null; // Mammoth not needed
    let currentUserForLogging: AccountInfo | null = null;
    let currentAccessToken: string | null = null;
    authStore.subscribe(value => {
        currentUserForLogging = value.user;
        currentAccessToken = value.accessToken;
    });

    // API Endpoints - Get base URL from Vite environment variables for local dev
    const RAG_API_BASE_URL = import.meta.env.VITE_RAG_API_URL || ''; // Fallback to relative if not set
    const API_SEARCH_ENDPOINT = `${RAG_API_BASE_URL}/search`;
    const API_CHAT_ENDPOINT = '/api/chat';     // If you add chat functionality back here
    const API_PREVIEW_PDF_ENDPOINT = `${RAG_API_BASE_URL}/preview-pdf`;

    // Pagination state
    let currentPage: number = 1;
    const resultsPerPage: number = 5; // Show 5 documents per page
    let totalResults: number = 0; // Will be set by API if we get total count
    let currentApiLimit: number = 20; // How many results to fetch from API initially (can be more than resultsPerPage)

    interface ChunkSnippetData { // Defined locally
        content: string;
        similarity: number;
        chunk_index?: number | null;
    }

    interface SourceDoc { // Defined locally
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

    // onMount(async () => { // Mammoth not needed
    //     try {
    //         const module = await import('mammoth/mammoth.browser');
    //         mammoth = module; 
    //         console.log("Mammoth.js loaded successfully.");
    //     } catch (error) {
    //         console.error("Failed to load Mammoth.js:", error);
    //     }
    // });

    // Interface for API response (if it changes to include total)
    interface ApiSearchResponse {
        query: string;
        results: SourceDoc[];
        total_available_results?: number; // Optional: if API can tell us total matches
        error?: string | null;
    }

    async function performSearch(page: number = 1) {
        if (!query.trim()) {
            errorMessage = 'Please enter a search query.';
            results = [];
            totalResults = 0;
            currentPage = 1;
            return;
        }

        isLoading = true;
        errorMessage = null;
        // results = []; // Don't clear results immediately if paginating, unless it's a new search
        if (page === 1) {
            results = []; // Clear for a new search (first page)
            totalResults = 0;
        }
        currentPage = page;

        // Log search term submission
        const userInfo = getUserLoggingInfo(currentUserForLogging);
        logActivity({ 
            event_type: 'SEARCH_SUBMITTED', 
            search_term: query, 
            ...userInfo 
        });

        try {
            // *** CRITICAL FIX: Acquire a token for our specific API scopes before calling it ***
            const tokenResponse = await acquireToken(apiRequest);
            if (!tokenResponse || !tokenResponse.accessToken) {
                throw new Error("Failed to acquire access token for API.");
            }
            const accessToken = tokenResponse.accessToken;

            // We'll fetch a larger batch from API (currentApiLimit) 
            // and then paginate client-side for now. 
            // True server-side pagination would require API to accept offset/page.
            const response = await fetch(API_SEARCH_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`
                },
                // Send the increased limit to the API
                body: JSON.stringify({ query: query, limit: currentApiLimit }), 
            });

            if (!response.ok) {
                let errorDetail = "An unknown error occurred.";
                try {
                    const errorData = await response.json();
                    errorDetail = errorData.detail || JSON.stringify(errorData);
                } catch(e) {
                    errorDetail = response.statusText;
                }
                throw new Error(`API Error: ${response.status} - ${errorDetail}`);
            }

            const data: ApiSearchResponse = await response.json(); // Use new interface
            
            if (data.error) {
                errorMessage = data.error;
                results = [];
            } else if (data.results && data.results.length > 0) {
                // For now, assume API returns all requested (up to currentApiLimit)
                // and we do client-side pagination on this set.
                results = data.results; 
                totalResults = results.length; // If API doesn't give total, use length of returned set
                if (data.total_available_results) { // If API gives total for actual matches
                    // totalResults = data.total_available_results;
                    // This is complex if API limit is less than actual total.
                    // For now, our client-side pagination is on the `currentApiLimit` results.
                }
                 if (results.length === 0 && page === 1) {
                    errorMessage = "No documents found matching your query.";
                }
            } else {
                results = []; 
                totalResults = 0;
                if (page === 1) errorMessage = "No documents found matching your query.";
            }

        } catch (err: any) {
            console.error('Search API call failed:', err);
            errorMessage = err.message || 'Failed to fetch search results. Is the API service running?';
            results = [];
            totalResults = 0;
        } finally {
            isLoading = false;
        }
    }

    function handleSearchClick() {
        performSearch(1); // Always go to page 1 for a new manual search
    }

    function handleKeydown(event: KeyboardEvent) {
        if (event.key === 'Enter') {
            handleSearchClick();
        }
    }

    // Computed properties for pagination
    $: totalPages = Math.ceil(totalResults / resultsPerPage);
    $: paginatedResults = results.slice((currentPage - 1) * resultsPerPage, currentPage * resultsPerPage);

    async function goToPage(page: number) { // Make function async
        if (page >= 1 && page <= totalPages) {
            currentPage = page;
            
            // Wait for Svelte to update the DOM after currentPage change
            await tick(); 

            // Scroll to the top of the page
            window.scrollTo({ top: 0, behavior: 'smooth' }); 
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

    async function openPdfPreview(doc: SourceDoc) {
        if (!doc.public_url) {
            alert("No public URL available for this PDF document.");
            return;
        }

        // Log PDF preview event
        const userInfo = getUserLoggingInfo(currentUserForLogging);
        logActivity({ 
            event_type: 'DOC_PREVIEW', 
            document_id: String(doc.id), 
            document_filename: doc.cleaned_filename || doc.title || doc.original_filename,
            preview_type: 'PDF_PROXY',
            ...userInfo 
        });

        // Use the new proxied endpoint and pass the Supabase URL as a query parameter
        previewTitle = doc.cleaned_filename || doc.title || doc.original_filename || "PDF Document";
        previewUrl = `${API_PREVIEW_PDF_ENDPOINT}?url=${encodeURIComponent(doc.public_url)}`;
        previewType = 'pdf';
        showPreviewModal = true;
    }

    async function openDocxPreview(doc: SourceDoc) {
        if (!doc.public_url) {
            alert("No public URL available for this DOCX document to preview.");
            return;
        }
        // Log DOCX preview event
        const userInfo = getUserLoggingInfo(currentUserForLogging);
        logActivity({ 
            event_type: 'DOC_PREVIEW', 
            document_id: String(doc.id), 
            document_filename: doc.cleaned_filename || doc.title || doc.original_filename,
            preview_type: 'DOCX_MS_VIEWER',
            ...userInfo 
        });
        previewTitle = doc.cleaned_filename || doc.title || doc.original_filename || "Word Document";
        const viewerUrl = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(doc.public_url)}`;
        console.log("Using Office Viewer URL for DOCX:", viewerUrl);
        previewUrl = viewerUrl;
        previewType = 'pdf'; 
        showPreviewModal = true;
    }

    function closePreviewModal() {
        showPreviewModal = false;
        previewUrl = null;
        previewType = null;
        // docxHtmlContent = ""; // Not needed
    }

    // Handle Escape key to close modal
    function handleGlobalKeydown(event: KeyboardEvent) {
        if (showPreviewModal && event.key === 'Escape') {
            closePreviewModal();
        }
    }

    // Lifecycle: Add/remove keydown listener when modal mounts/unmounts
    // This is tricky if the modal itself is conditionally rendered with {#if}
    // A better way might be to add it when showPreviewModal becomes true
    // and remove when it becomes false, or attach to window and check if modal is active.

    // Let's use Svelte's <svelte:window on:keydown={...} /> for simplicity if modal is shown

    async function handleLogout() {
        const user = $authStore.user;
        if (user) {
            const userInfo = getUserLoggingInfo(user);
            await logActivity({
                event_type: 'USER_LOGOUT_SUCCESS', // Or just LOGOUT
                ...userInfo
            });
        }
        logout();
    }

    function clearSearch() {
        query = '';
        results = [];
        totalResults = 0;
        currentPage = 1;
        errorMessage = null;
    }

</script>

<svelte:window on:keydown={handleGlobalKeydown}/>

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
            on:click={handleSearchClick} 
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
        <div 
            class="px-4 py-3 rounded-lg relative mb-4 shadow"
            role="alert"
            class:bg-red-100={errorMessage !== "No documents found matching your query."}
            class:border-red-400={errorMessage !== "No documents found matching your query."}
            class:text-red-700={errorMessage !== "No documents found matching your query."}
            class:bg-blue-100={errorMessage === "No documents found matching your query."}
            class:border-blue-400={errorMessage === "No documents found matching your query."}
            class:text-blue-700={errorMessage === "No documents found matching your query."}
        >
            {#if errorMessage !== "No documents found matching your query."}
                <strong class="font-bold">Error:</strong>
            {/if}
            <span class="block sm:inline">{errorMessage}</span>
        </div>
    {/if}

    <div class="results-area space-y-6">
        {#if paginatedResults.length > 0}
            <h2 class="text-xl font-semibold mb-4">Results (Page {currentPage} of {totalPages}):</h2>
            {#each paginatedResults as result, i (result.id)} 
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
                    
                    <div class="actions mt-4 flex space-x-2">
                        {#if result.public_url}
                            <a 
                                href={result.public_url} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                class="inline-block bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded-md shadow hover:shadow-md transition-colors duration-150 ease-in-out text-sm"
                                on:click={() => {
                                    const userInfo = getUserLoggingInfo(currentUserForLogging);
                                    logActivity({ 
                                        event_type: 'DOC_DOWNLOAD_ATTEMPT', 
                                        document_id: String(result.id), 
                                        document_filename: result.cleaned_filename || result.title || result.original_filename,
                                        ...userInfo 
                                    });
                                }}
                            >
                                Download Document
                            </a>
                            {#if result.file_type?.toLowerCase() === 'pdf'}
                                <button 
                                    on:click={() => openPdfPreview(result)} 
                                    class="inline-block bg-purple-500 hover:bg-purple-600 text-white font-semibold py-2 px-4 rounded-md shadow hover:shadow-md transition-colors duration-150 ease-in-out text-sm"
                                >
                                    Preview PDF
                                </button>
                            {:else if result.file_type?.toLowerCase() === 'docx' || result.file_type?.toLowerCase() === 'doc' || result.original_filename?.toLowerCase().endsWith('.docx') || result.original_filename?.toLowerCase().endsWith('.doc')}
                                <button 
                                    on:click={() => openDocxPreview(result)} 
                                    class="inline-block bg-sky-500 hover:bg-sky-600 text-white font-semibold py-2 px-4 rounded-md shadow hover:shadow-md transition-colors duration-150 ease-in-out text-sm"
                                >
                                    Preview DOCX (Beta)
                                </button>
                            {/if}
                        {/if}
                    </div>
                </div>
            {/each}
        {:else if !isLoading && !errorMessage}
            <p class="text-gray-600 text-center py-4">No results to display. Try a new search.</p>
        {/if}
    </div>

    <!-- Pagination Controls -->
    {#if totalPages > 1}
        <div class="pagination-controls mt-8 flex justify-center items-center space-x-2">
            <button 
                on:click={() => goToPage(currentPage - 1)} 
                disabled={currentPage === 1 || isLoading}
                class="px-4 py-2 bg-gray-300 hover:bg-gray-400 text-gray-800 font-medium rounded-md disabled:opacity-50"
            >
                Previous
            </button>
            
            <span class="text-gray-700">
                Page {currentPage} of {totalPages}
            </span>
            
            <button 
                on:click={() => goToPage(currentPage + 1)} 
                disabled={currentPage === totalPages || isLoading}
                class="px-4 py-2 bg-gray-300 hover:bg-gray-400 text-gray-800 font-medium rounded-md disabled:opacity-50"
            >
                Next
            </button>
        </div>
    {/if}
</div>

<!-- Preview Modal -->
{#if showPreviewModal}
    <!-- Close on backdrop click -->
    <div 
        class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4"
        on:click|self={closePreviewModal} 
        role="presentation"
    >
        <div 
            class="bg-white p-2 rounded-lg shadow-2xl w-full max-w-4xl h-[90vh] flex flex-col"
            role="dialog" 
            aria-modal="true"
            aria-labelledby="previewModalTitle"
        >
            <div class="flex justify-between items-center p-2 border-b">
                <h2 class="text-xl font-semibold truncate pr-2" title={previewTitle} id="previewModalTitle">{previewTitle}</h2>
                <button 
                    on:click={closePreviewModal} 
                    class="text-gray-600 hover:text-gray-900 text-2xl font-bold"
                    aria-label="Close preview modal"
                >&times;</button>
            </div>
            <div class="flex-grow overflow-auto p-1 mt-1">
                {#if previewType === 'pdf' && previewUrl} <!-- Simplified condition -->
                    <iframe src={previewUrl} class="w-full h-full border-0" title="Document Preview"></iframe>
                <!-- {:else if previewType === 'html'} Removed Mammoth specific part
                    <div class="prose max-w-none p-4">{@html docxHtmlContent}</div> -->
                {:else if !previewUrl && showPreviewModal}
                    <p class="text-center p-8">Loading preview or no preview available...</p>
                {/if}
            </div>
        </div>
    </div>
{/if}

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
    /* :global(.prose pre) removed as it was part of the global prose styling */
</style> 