<script lang="ts">
    import { tick } from 'svelte'; // Import tick
    import { authStore, acquireToken, logout } from './authStore'; // Import from authStore
    import { apiRequest } from './authService'; // Import apiRequest from authService
    import { logActivity, getUserLoggingInfo } from './activityLogger'; // Import logging utils
    import type { AccountInfo } from '@azure/msal-browser'; // For user type
    import { onMount } from 'svelte';
    import { API_SCOPE } from './authService';
    
    // Search mode and parameter controls
    let useVector: boolean = true;  // Vector search enabled by default
    let useKeyword: boolean = false; // Keyword search disabled by default
    let vectorWeight: number = 70;   // Vector weight as percentage (0-100)
    let useFuzzy: boolean = false;   // Fuzzy keyword matching
    let similarityThreshold: number = 30; // Fuzzy similarity threshold (0-100)
    let minScore: number = 10;       // Minimum relevance score (0-100)
    let showAdvanced: boolean = false; // Show/hide advanced options
    
    // Computed search mode
    $: searchMode = useVector && useKeyword ? 'hybrid' : useVector ? 'vector' : useKeyword ? 'keyword' : 'vector';
    $: keywordWeight = 100 - vectorWeight; // Auto-calculate keyword weight
    $: isHybridMode = useVector && useKeyword;
    
    // Local interface definitions
    let query: string = '';
    let results: any[] = []; // Will hold the search results (SourceDocument[])
    let isLoading: boolean = false;
    let errorMessage: string | null = null;
    let previewUrl: string | null = null;
    let showPreviewModal: boolean = false;
    let previewTitle: string = "Document Preview";
    let previewType: 'pdf' | 'html' | null = null;
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

    // Interface for API response
    interface ApiSearchResponse {
        query: string;
        results: SourceDoc[];
        search_mode: string;
        parameters: any;
        total_available_results?: number; // Optional: if API can tell us total matches
        error?: string | null;
    }

    // Validate search mode selection
    function validateSearchMode() {
        if (!useVector && !useKeyword) {
            // If nothing is selected, default to vector
            useVector = true;
        }
    }

    async function performSearch(page: number = 1) {
        if (!query.trim()) {
            errorMessage = 'Please enter a search query.';
            results = [];
            totalResults = 0;
            currentPage = 1;
            return;
        }

        // Validate search mode
        validateSearchMode();

        isLoading = true;
        errorMessage = null;
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
            search_mode: searchMode,
            ...userInfo 
        });

        try {
            // Acquire a token for our specific API scopes before calling it
            const tokenResponse = await acquireToken(apiRequest);
            if (!tokenResponse || !tokenResponse.accessToken) {
                throw new Error("Failed to acquire access token for API.");
            }
            const accessToken = tokenResponse.accessToken;

            // Build enhanced search request
            const searchRequest: any = {
                query: query,
                mode: searchMode,
                limit: currentApiLimit
            };

            // Add hybrid search weights if in hybrid mode
            if (isHybridMode) {
                searchRequest.vector_weight = vectorWeight / 100;
                searchRequest.keyword_weight = keywordWeight / 100;
            }

            // Add keyword search options
            if (useKeyword || isHybridMode) {
                searchRequest.fuzzy = useFuzzy;
                if (useFuzzy) {
                    searchRequest.similarity_threshold = similarityThreshold / 100;
                }
            }

            // Add general options
            searchRequest.min_score = minScore / 100;

            // Send the enhanced search request
            const response = await fetch(API_SEARCH_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`
                },
                body: JSON.stringify(searchRequest), 
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

            const data: ApiSearchResponse = await response.json();
            
            if (data.error) {
                errorMessage = data.error;
                results = [];
            } else if (data.results && data.results.length > 0) {
                results = data.results; 
                totalResults = results.length;
                if (data.total_available_results) {
                    // Future: handle server-side pagination
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
        if (!dateString) return "N/A";
        try {
            return new Date(dateString).toLocaleDateString();
        } catch (error) {
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

        try {
            // Get token for preview endpoint
            const tokenResponse = await acquireToken({
                scopes: ["api://b9d76cbb-9348-4b2e-a5cd-89eabcd59e73/access_as_user"]
            });
            if (!tokenResponse || !tokenResponse.accessToken) {
                throw new Error("Failed to acquire access token for preview.");
            }
            const accessToken = tokenResponse.accessToken;

            // Fetch the PDF through our proxy
            const response = await fetch(`${API_PREVIEW_PDF_ENDPOINT}?url=${encodeURIComponent(doc.public_url)}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${accessToken}`
                }
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch PDF: ${response.status}`);
            }

            const blob = await response.blob();
            previewUrl = URL.createObjectURL(blob);
            previewTitle = doc.cleaned_filename || doc.title || doc.original_filename || "PDF Document";
            previewType = 'pdf';
            showPreviewModal = true;
        } catch (error) {
            console.error('PDF preview error:', error);
            alert('Failed to load PDF preview.');
        }
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
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
            previewUrl = null;
        }
        previewType = null;
    }

    // Handle Escape key to close modal
    function handleGlobalKeydown(event: KeyboardEvent) {
        if (showPreviewModal && event.key === 'Escape') {
            closePreviewModal();
        }
    }

    async function handleLogout() {
        const user = $authStore.user;
        if (user) {
            const userInfo = getUserLoggingInfo(user);
            await logActivity({
                event_type: 'USER_LOGOUT_SUCCESS', 
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

<div class="container mx-auto p-4 max-w-4xl">
    <h1 class="text-2xl font-bold mb-6 text-center">Document Search</h1>

    <!-- Search Input -->
    <div class="search-bar mb-4 flex items-center space-x-2">
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

    <!-- Search Mode Controls -->
    <div class="search-controls mb-6 bg-gray-50 rounded-lg p-4 border border-gray-200">
        <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-medium text-gray-800">Search Mode</h3>
            <div class="flex items-center space-x-1">
                <span class={`px-2 py-1 text-xs font-medium rounded-full ${
                    searchMode === 'vector' ? 'bg-blue-100 text-blue-800' :
                    searchMode === 'keyword' ? 'bg-green-100 text-green-800' :
                    'bg-purple-100 text-purple-800'
                }`}>
                    {searchMode.toUpperCase()}
                </span>
            </div>
        </div>
        
        <!-- Mode Selection Checkboxes -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <label class="flex items-center space-x-3 p-3 bg-white rounded-lg border border-gray-200 hover:border-blue-300 transition-colors cursor-pointer">
                <input 
                    type="checkbox" 
                    bind:checked={useVector}
                    on:change={validateSearchMode}
                    class="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                />
                <div>
                    <div class="font-medium text-gray-900">Vector Search</div>
                    <div class="text-sm text-gray-600">Semantic similarity matching</div>
                </div>
            </label>
            
            <label class="flex items-center space-x-3 p-3 bg-white rounded-lg border border-gray-200 hover:border-green-300 transition-colors cursor-pointer">
                <input 
                    type="checkbox" 
                    bind:checked={useKeyword}
                    on:change={validateSearchMode}
                    class="w-4 h-4 text-green-600 rounded focus:ring-green-500"
                />
                <div>
                    <div class="font-medium text-gray-900">Keyword Search</div>
                    <div class="text-sm text-gray-600">Exact term and phrase matching</div>
                </div>
            </label>
        </div>

        <!-- Hybrid Weight Control (only shown when both are selected) -->
        {#if isHybridMode}
            <div class="hybrid-controls bg-purple-50 border border-purple-200 rounded-lg p-4 mb-4">
                <h4 class="font-medium text-purple-900 mb-3">Hybrid Search Balance</h4>
                <div class="space-y-3">
                    <div class="flex items-center justify-between">
                        <span class="text-sm text-purple-700">Vector Weight: {vectorWeight}%</span>
                        <span class="text-sm text-purple-700">Keyword Weight: {keywordWeight}%</span>
                    </div>
                    <input 
                        type="range" 
                        min="10" 
                        max="90" 
                        bind:value={vectorWeight}
                        class="w-full h-2 bg-gradient-to-r from-green-300 to-blue-300 rounded-lg appearance-none cursor-pointer slider"
                    />
                    <div class="flex justify-between text-xs text-gray-600">
                        <span>More Keyword</span>
                        <span>Balanced</span>
                        <span>More Vector</span>
                    </div>
                </div>
            </div>
        {/if}

        <!-- Advanced Options Toggle -->
        <div class="flex items-center justify-between">
            <button 
                on:click={() => showAdvanced = !showAdvanced}
                class="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center space-x-1"
            >
                <span>{showAdvanced ? 'Hide' : 'Show'} Advanced Options</span>
                <svg class={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                </svg>
            </button>
        </div>

        <!-- Advanced Options Panel -->
        {#if showAdvanced}
            <div class="advanced-options mt-4 pt-4 border-t border-gray-200 space-y-4">
                <!-- Fuzzy Search (only for keyword modes) -->
                {#if useKeyword}
                    <div class="bg-white rounded-lg p-3 border border-gray-200">
                        <label class="flex items-center space-x-3 mb-3">
                            <input 
                                type="checkbox" 
                                bind:checked={useFuzzy}
                                class="w-4 h-4 text-green-600 rounded focus:ring-green-500"
                            />
                            <div>
                                <div class="font-medium text-gray-900">Fuzzy Matching</div>
                                <div class="text-sm text-gray-600">Find similar words and handle typos</div>
                            </div>
                        </label>
                        
                        {#if useFuzzy}
                            <div class="ml-7 space-y-2">
                                <label class="block text-sm font-medium text-gray-700">
                                    Similarity Threshold: {similarityThreshold}%
                                </label>
                                <input 
                                    type="range" 
                                    min="10" 
                                    max="90" 
                                    bind:value={similarityThreshold}
                                    class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                                />
                                <div class="flex justify-between text-xs text-gray-500">
                                    <span>More Fuzzy</span>
                                    <span>More Strict</span>
                                </div>
                            </div>
                        {/if}
                    </div>
                {/if}

                <!-- Minimum Score Threshold -->
                <div class="bg-white rounded-lg p-3 border border-gray-200">
                    <label class="block text-sm font-medium text-gray-700 mb-2">
                        Minimum Relevance Score: {minScore}%
                    </label>
                    <input 
                        type="range" 
                        min="0" 
                        max="50" 
                        bind:value={minScore}
                        class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                    />
                    <div class="flex justify-between text-xs text-gray-500 mt-1">
                        <span>Include All</span>
                        <span>High Quality Only</span>
                    </div>
                </div>
            </div>
        {/if}
    </div>

    {#if errorMessage}
        <div 
            role="alert"
            class={`px-4 py-3 rounded-lg relative mb-4 shadow ${
                errorMessage !== "No documents found matching your query." 
                    ? "bg-red-100 border-red-400 text-red-700" 
                    : "bg-blue-100 border-blue-400 text-blue-700"
            }`}
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
            {#each paginatedResults as result, index}
                <div class="result-item bg-white p-6 rounded-lg shadow-lg border border-gray-200 hover:shadow-xl transition-shadow duration-150 ease-in-out">
                    <h3 class="text-lg font-semibold text-blue-700 mb-2 break-words">
                        {index + 1}. {result.cleaned_filename || result.title || result.original_filename || `Document ID: ${result.id}`}
                    </h3>

                    {#if result.document_summary}
                        <p class="text-gray-700 mb-3 summary"><strong>Summary:</strong> {result.document_summary.substring(0, 250)}{result.document_summary.length > 250 ? "..." : ""}</p>
                    {/if}

                    {#if result.analysis_notes}
                        <div class="analysis-notes mb-3">
                            <h4 class="font-semibold text-gray-700 mb-1">Analysis Notes:</h4>
                            <pre class="bg-gray-50 p-3 rounded-md text-sm text-gray-800 whitespace-pre-wrap font-sans break-words">{result.analysis_notes}</pre>
                        </div>
                    {/if}

                    {#if result.snippets && result.snippets.length > 0}
                        <div class="snippets-container mt-3 mb-3">
                            <h5 class="font-medium text-gray-600 text-sm mb-1">Relevant Snippets:</h5>
                            <ul class="list-disc list-inside space-y-2 pl-1">
                                {#each result.snippets as snippet}
                                    <li class="text-xs text-gray-700 bg-gray-100 p-2 rounded-md">
                                        <p class="font-semibold">
                                            Score: {snippet.similarity.toFixed(4)}
                                            {#if snippet.chunk_index !== null && snippet.chunk_index !== undefined}
                                                <span>(Chunk {snippet.chunk_index + 1})</span>
                                            {/if}
                                        </p>
                                        <p class="snippet-content">{snippet.content.substring(0, 300)}{snippet.content.length > 300 ? "..." : ""}</p>
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
                {#if previewType === 'pdf' && previewUrl}
                    <iframe src={previewUrl} class="w-full h-full border-0" title="Document Preview"></iframe>
                {:else if !previewUrl && showPreviewModal}
                    <p class="text-center p-8">Loading preview or no preview available...</p>
                {/if}
            </div>
        </div>
    </div>
{/if}

<style>
    .snippet-content {
        display: -webkit-box;
        -webkit-line-clamp: 3; /* Show 3 lines */
        -webkit-box-orient: vertical;  
        overflow: hidden;
        text-overflow: ellipsis;
        margin-top: 0.25rem;
    }
    
    /* Custom slider styling */
    .slider::-webkit-slider-thumb {
        appearance: none;
        height: 20px;
        width: 20px;
        border-radius: 50%;
        background: #8B5CF6;
        cursor: pointer;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }

    .slider::-moz-range-thumb {
        height: 20px;
        width: 20px;
        border-radius: 50%;
        background: #8B5CF6;
        cursor: pointer;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
</style> 