-- Step 1: Drop all existing versions of the function
DROP FUNCTION IF EXISTS search_documents_hybrid(TEXT, VECTOR, INTEGER);
DROP FUNCTION IF EXISTS search_documents_hybrid(TEXT, VECTOR, REAL, REAL, INTEGER, INTEGER);
DROP FUNCTION IF EXISTS public.search_documents_hybrid;

-- Step 2: Create the correct version with all parameters
CREATE OR REPLACE FUNCTION search_documents_hybrid(
    search_query TEXT,
    query_embedding VECTOR(1024),
    vector_weight REAL DEFAULT 0.7,
    keyword_weight REAL DEFAULT 0.3,
    result_limit INTEGER DEFAULT 10,
    rrf_k INTEGER DEFAULT 60
)
RETURNS TABLE(
    doc_id BIGINT,
    chunk_id UUID,
    snippet TEXT,
    title TEXT,
    document_category TEXT,
    law_area TEXT[],
    vector_score REAL,
    keyword_score REAL,
    rrf_score REAL,
    hybrid_score REAL,
    match_sources TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH 
    -- Vector search results with ranks
    vector_results AS (
        SELECT 
            dc.document_id,
            dc.id as chunk_id,
            LEFT(dc.chunk_text, 200) as snippet,
            d.title,
            d.document_category,
            d.law_area,
            (1 - (dc.embedding <=> query_embedding)) as v_score,
            ROW_NUMBER() OVER (ORDER BY dc.embedding <=> query_embedding) as v_rank
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE dc.embedding IS NOT NULL
        ORDER BY dc.embedding <=> query_embedding
        LIMIT result_limit * 3  -- Get more results for better RRF fusion
    ),
    
    -- Keyword search results with ranks  
    keyword_results AS (
        SELECT 
            dc.document_id,
            dc.id as chunk_id,
            LEFT(dc.chunk_text, 200) as snippet,
            d.title,
            d.document_category,
            d.law_area,
            ts_rank(dc.search_vector, websearch_to_tsquery('english', search_query)) as k_score,
            ROW_NUMBER() OVER (ORDER BY ts_rank(dc.search_vector, websearch_to_tsquery('english', search_query)) DESC) as k_rank
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE dc.search_vector @@ websearch_to_tsquery('english', search_query)
        ORDER BY ts_rank(dc.search_vector, websearch_to_tsquery('english', search_query)) DESC
        LIMIT result_limit * 3  -- Get more results for better RRF fusion
    ),
    
    -- Combine results with RRF scoring
    combined_results AS (
        SELECT 
            COALESCE(vr.document_id, kr.document_id) as doc_id,
            COALESCE(vr.chunk_id, kr.chunk_id) as chunk_id,
            COALESCE(vr.snippet, kr.snippet) as snippet,
            COALESCE(vr.title, kr.title) as title,
            COALESCE(vr.document_category, kr.document_category) as document_category,
            COALESCE(vr.law_area, kr.law_area) as law_area,
            COALESCE(vr.v_score, 0.0) as vector_score,
            COALESCE(kr.k_score, 0.0) as keyword_score,
            -- Calculate RRF score: sum of 1/(k + rank) for each search type
            COALESCE(1.0 / (rrf_k + vr.v_rank), 0.0) + COALESCE(1.0 / (rrf_k + kr.k_rank), 0.0) as rrf_score,
            -- Calculate weighted hybrid score
            (COALESCE(vr.v_score, 0.0) * vector_weight + COALESCE(kr.k_score, 0.0) * keyword_weight) as hybrid_score,
            -- Track which search methods found this result
            CASE 
                WHEN vr.chunk_id IS NOT NULL AND kr.chunk_id IS NOT NULL THEN 'vector+keyword'
                WHEN vr.chunk_id IS NOT NULL THEN 'vector'
                WHEN kr.chunk_id IS NOT NULL THEN 'keyword'
                ELSE 'unknown'
            END as match_sources
        FROM vector_results vr 
        FULL OUTER JOIN keyword_results kr ON vr.chunk_id = kr.chunk_id
    ),
    
    -- Final ranking (prefer RRF but fall back to hybrid score)
    final_results AS (
        SELECT 
            cr.doc_id,
            cr.chunk_id,
            cr.snippet,
            cr.title,
            cr.document_category,
            cr.law_area,
            cr.vector_score,
            cr.keyword_score,
            cr.rrf_score,
            cr.hybrid_score,
            cr.match_sources,
            -- Use RRF as primary score, hybrid as secondary
            (cr.rrf_score * 1000 + cr.hybrid_score) as final_score
        FROM combined_results cr
        WHERE cr.vector_score > 0.0 OR cr.keyword_score > 0.0  -- At least one search found it
    )
    
    SELECT 
        fr.doc_id,
        fr.chunk_id,
        fr.snippet,
        fr.title,
        fr.document_category,
        fr.law_area,
        fr.vector_score::REAL,
        fr.keyword_score::REAL,
        fr.rrf_score::REAL,
        fr.hybrid_score::REAL,
        fr.match_sources
    FROM final_results fr
    ORDER BY fr.final_score DESC
    LIMIT result_limit;
END;
$$;

-- Step 3: Verify the function was created correctly
SELECT 
    proname, 
    oidvectortypes(proargtypes) as argument_types
FROM pg_proc 
WHERE proname = 'search_documents_hybrid'; 