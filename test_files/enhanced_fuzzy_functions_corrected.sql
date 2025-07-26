-- CORRECTED Enhanced Fuzzy Search Functions for KB Search API
-- Fixed based on actual database schema investigation

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;

-- =============================================================================
-- DROP EXISTING FUNCTIONS (if they exist with different signatures)
-- =============================================================================

-- Drop existing functions to avoid signature conflicts
DROP FUNCTION IF EXISTS search_documents_keyword_enhanced(text, int, boolean, real);
DROP FUNCTION IF EXISTS search_documents_keyword_enhanced(text, int, boolean, double precision);
DROP FUNCTION IF EXISTS search_documents_hybrid_enhanced(text, vector, real, real, int, int, boolean, real);
DROP FUNCTION IF EXISTS search_documents_hybrid_enhanced(text, vector, double precision, double precision, int, int, boolean, double precision);
DROP FUNCTION IF EXISTS test_fuzzy_search(text, text);
DROP FUNCTION IF EXISTS test_fuzzy_search(text);

-- =============================================================================
-- ENHANCED KEYWORD SEARCH FUNCTION (CORRECTED)
-- =============================================================================

CREATE OR REPLACE FUNCTION search_documents_keyword_enhanced(
    search_query text,
    result_limit int DEFAULT 10,
    fuzzy_enabled boolean DEFAULT false,
    similarity_threshold real DEFAULT 0.3
)
RETURNS TABLE (
    doc_id bigint,
    chunk_id uuid,
    snippet text,
    title text,
    score real,
    source text
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF fuzzy_enabled THEN
        -- Enhanced fuzzy search using pg_trgm trigram similarity
        RETURN QUERY
        WITH fuzzy_results AS (
            SELECT 
                d.id as doc_id,
                dc.id as chunk_id,
                dc.chunk_text as snippet,
                COALESCE(d.title, d.original_filename, 'Untitled') as title,
                GREATEST(
                    similarity(dc.chunk_text, search_query),
                    similarity(COALESCE(d.title, ''), search_query),
                    similarity(COALESCE(d.original_filename, ''), search_query),
                    -- Also check word-level similarity for better matching
                    word_similarity(search_query, dc.chunk_text),
                    word_similarity(search_query, COALESCE(d.title, ''))
                )::real as fuzzy_score,
                'content' as source
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE (
                similarity(dc.chunk_text, search_query) >= similarity_threshold OR
                similarity(COALESCE(d.title, ''), search_query) >= similarity_threshold OR
                similarity(COALESCE(d.original_filename, ''), search_query) >= similarity_threshold OR
                word_similarity(search_query, dc.chunk_text) >= similarity_threshold OR
                word_similarity(search_query, COALESCE(d.title, '')) >= similarity_threshold
            )
        )
        SELECT 
            doc_id,
            chunk_id,
            snippet,
            title,
            fuzzy_score as score,
            source
        FROM fuzzy_results
        ORDER BY fuzzy_score DESC
        LIMIT result_limit;
    ELSE
        -- Call existing function for non-fuzzy search
        -- This preserves existing behavior when fuzzy is disabled
        RETURN QUERY
        SELECT 
            sr.doc_id,
            sr.chunk_id,
            sr.snippet,
            sr.title,
            sr.score,
            sr.source
        FROM search_documents_keyword(search_query, result_limit) sr;
    END IF;
END;
$$;

-- =============================================================================
-- ENHANCED HYBRID SEARCH FUNCTION (CORRECTED)
-- =============================================================================

CREATE OR REPLACE FUNCTION search_documents_hybrid_enhanced(
    search_query text,
    query_embedding vector(1024),
    vector_weight real DEFAULT 0.7,
    keyword_weight real DEFAULT 0.3,
    result_limit int DEFAULT 10,
    rrf_k int DEFAULT 60,
    fuzzy_enabled boolean DEFAULT false,
    similarity_threshold real DEFAULT 0.3
)
RETURNS TABLE (
    doc_id bigint,
    chunk_id uuid,
    snippet text,
    title text,
    document_category text,
    law_area text[],
    vector_score real,
    keyword_score real,
    rrf_score real,
    hybrid_score real,
    match_sources text
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF fuzzy_enabled THEN
        -- Enhanced hybrid search with fuzzy keyword matching
        RETURN QUERY
        WITH vector_results AS (
            -- Vector similarity results
            SELECT 
                dc.document_id,
                dc.id as chunk_id,
                dc.chunk_text,
                (dc.embedding <=> query_embedding) as vector_distance,
                (1 - (dc.embedding <=> query_embedding))::real as v_score,
                ROW_NUMBER() OVER (ORDER BY dc.embedding <=> query_embedding) as vector_rank
            FROM document_chunks dc
            ORDER BY dc.embedding <=> query_embedding
            LIMIT result_limit * 2
        ),
        fuzzy_keyword_results AS (
            -- Enhanced fuzzy keyword results
            SELECT 
                dc.document_id,
                dc.id as chunk_id,
                dc.chunk_text,
                GREATEST(
                    similarity(dc.chunk_text, search_query),
                    word_similarity(search_query, dc.chunk_text)
                )::real as k_score,
                ROW_NUMBER() OVER (
                    ORDER BY GREATEST(
                        similarity(dc.chunk_text, search_query),
                        word_similarity(search_query, dc.chunk_text)
                    ) DESC
                ) as keyword_rank
            FROM document_chunks dc
            WHERE (
                similarity(dc.chunk_text, search_query) >= similarity_threshold OR
                word_similarity(search_query, dc.chunk_text) >= similarity_threshold
            )
            LIMIT result_limit * 2
        ),
        combined_results AS (
            SELECT 
                COALESCE(vr.document_id, kr.document_id) as document_id,
                COALESCE(vr.chunk_id, kr.chunk_id) as chunk_id,
                COALESCE(vr.chunk_text, kr.chunk_text) as chunk_text,
                COALESCE(vr.v_score, 0.0)::real as vector_score,
                COALESCE(kr.k_score, 0.0)::real as keyword_score,
                -- RRF (Reciprocal Rank Fusion) scoring
                (COALESCE(1.0 / (rrf_k + vr.vector_rank), 0.0) + 
                 COALESCE(1.0 / (rrf_k + kr.keyword_rank), 0.0))::real as rrf_score,
                -- Weighted hybrid score
                (vector_weight * COALESCE(vr.v_score, 0.0) + 
                 keyword_weight * COALESCE(kr.k_score, 0.0))::real as hybrid_score,
                CASE 
                    WHEN vr.chunk_id IS NOT NULL AND kr.chunk_id IS NOT NULL THEN 'vector+keyword+fuzzy'
                    WHEN vr.chunk_id IS NOT NULL THEN 'vector'
                    ELSE 'keyword+fuzzy'
                END as match_sources
            FROM vector_results vr
            FULL OUTER JOIN fuzzy_keyword_results kr ON vr.chunk_id = kr.chunk_id
        )
        SELECT 
            d.id::bigint as doc_id,
            cr.chunk_id,
            cr.chunk_text as snippet,
            COALESCE(d.title, d.original_filename, 'Untitled') as title,
            d.document_category,
            d.law_area,
            cr.vector_score,
            cr.keyword_score,
            cr.rrf_score,
            cr.hybrid_score,
            cr.match_sources
        FROM combined_results cr
        JOIN documents d ON cr.document_id = d.id
        ORDER BY cr.hybrid_score DESC
        LIMIT result_limit;
    ELSE
        -- Call existing function for non-fuzzy hybrid search
        RETURN QUERY
        SELECT 
            hr.doc_id,
            hr.chunk_id,
            hr.snippet,
            hr.title,
            hr.document_category,
            hr.law_area,
            hr.vector_score,
            hr.keyword_score,
            hr.rrf_score,
            hr.hybrid_score,
            hr.match_sources
        FROM search_documents_hybrid(
            search_query, 
            query_embedding, 
            vector_weight, 
            keyword_weight, 
            result_limit, 
            rrf_k
        ) hr;
    END IF;
END;
$$;

-- =============================================================================
-- TEST FUNCTION (CORRECTED)
-- =============================================================================

-- Test function to compare fuzzy vs non-fuzzy results
CREATE OR REPLACE FUNCTION test_fuzzy_search(
    test_query text,
    test_typo text DEFAULT NULL
)
RETURNS TABLE (
    test_type text,
    query_used text,
    result_count bigint,
    first_result_score real
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Test 1: Normal search
    RETURN QUERY
    SELECT 
        'normal' as test_type,
        test_query as query_used,
        COUNT(*) as result_count,
        MAX(score) as first_result_score
    FROM search_documents_keyword_enhanced(test_query, 5, false);
    
    -- Test 2: Fuzzy search with original query
    RETURN QUERY
    SELECT 
        'fuzzy_original' as test_type,
        test_query as query_used,
        COUNT(*) as result_count,
        MAX(score) as first_result_score
    FROM search_documents_keyword_enhanced(test_query, 5, true, 0.3);
    
    -- Test 3: Fuzzy search with typo (if provided)
    IF test_typo IS NOT NULL THEN
        RETURN QUERY
        SELECT 
            'fuzzy_typo' as test_type,
            test_typo as query_used,
            COUNT(*) as result_count,
            MAX(score) as first_result_score
        FROM search_documents_keyword_enhanced(test_typo, 5, true, 0.3);
    END IF;
END;
$$;

-- =============================================================================
-- USAGE EXAMPLES
-- =============================================================================

/*

-- Test enhanced keyword search
SELECT * FROM search_documents_keyword_enhanced('taxpayer', 5, true, 0.3);

-- Test with typo
SELECT * FROM search_documents_keyword_enhanced('taxpayeer', 5, true, 0.3);

-- Compare fuzzy vs normal search
SELECT * FROM test_fuzzy_search('taxpayer', 'taxpayeer');

-- Test enhanced hybrid search (requires embedding)
-- SELECT * FROM search_documents_hybrid_enhanced(
--     'taxpayer', 
--     '[your-1024-dimensional-embedding-vector]'::vector(1024),
--     0.7, 0.3, 10, 60, true, 0.3
-- );

*/

-- =============================================================================
-- MIGRATION INSTRUCTIONS
-- =============================================================================

/*

STEP-BY-STEP IMPLEMENTATION:

1. ✅ COPY THIS CORRECTED SQL to Supabase SQL Editor

2. ✅ EXECUTE the SQL to create the enhanced functions

3. ✅ TEST the functions using the test script:
   python test_enhanced_fuzzy.py

4. 🔄 ONCE WORKING: Update application to use enhanced functions

5. 🔄 UPDATE application code to call:
   - search_documents_keyword_enhanced (instead of search_documents_keyword)
   - search_documents_hybrid_enhanced (instead of search_documents_hybrid)

*/ 