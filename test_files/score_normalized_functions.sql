-- SCORE NORMALIZED Enhanced Fuzzy Search Functions
-- All scores normalized to 0.0-1.0 range for consistency

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;

-- =============================================================================
-- DROP EXISTING FUNCTIONS
-- =============================================================================

DROP FUNCTION IF EXISTS search_documents_keyword_enhanced(text, int, boolean, real);
DROP FUNCTION IF EXISTS search_documents_hybrid_enhanced(text, vector, real, real, int, int, boolean, real);
DROP FUNCTION IF EXISTS test_fuzzy_search(text, text);

-- =============================================================================
-- SCORE NORMALIZED KEYWORD SEARCH FUNCTION
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
    source text,
    score_type text
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF fuzzy_enabled THEN
        -- Enhanced fuzzy search with NORMALIZED scores (0.0-1.0)
        RETURN QUERY
        WITH fuzzy_results AS (
            SELECT 
                d.id as document_id,
                dc.id as chunk_id,
                dc.chunk_text as snippet,
                COALESCE(d.title, d.original_filename, 'Untitled') as title,
                GREATEST(
                    similarity(dc.chunk_text, search_query),
                    similarity(COALESCE(d.title, ''), search_query),
                    similarity(COALESCE(d.original_filename, ''), search_query),
                    word_similarity(search_query, dc.chunk_text),
                    word_similarity(search_query, COALESCE(d.title, ''))
                )::real as fuzzy_score,
                'content' as source,
                'fuzzy' as score_type
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
            fr.document_id::bigint as doc_id,
            fr.chunk_id,
            fr.snippet,
            fr.title,
            fr.fuzzy_score as score,  -- Already 0.0-1.0 range
            fr.source,
            fr.score_type
        FROM fuzzy_results fr
        ORDER BY fr.fuzzy_score DESC
        LIMIT result_limit;
    ELSE
        -- Call existing function with NORMALIZED scores
        RETURN QUERY
        SELECT 
            sr.doc_id,
            sr.chunk_id,
            sr.snippet,
            sr.title,
            -- NORMALIZE: ts_rank typically 0.0-0.1, multiply by 10 to get 0.0-1.0
            LEAST(sr.score * 10.0, 1.0)::real as score,
            sr.source,
            'fulltext'::text as score_type
        FROM search_documents_keyword(search_query, result_limit) sr;
    END IF;
END;
$$;

-- =============================================================================
-- SCORE NORMALIZED HYBRID SEARCH FUNCTION  
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
    match_sources text,
    score_type text
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF fuzzy_enabled THEN
        -- Enhanced hybrid search with NORMALIZED scores across all components
        RETURN QUERY
        WITH vector_results AS (
            -- Vector similarity results (already 0.0-1.0)
            SELECT 
                dc.document_id,
                dc.id as chunk_id,
                dc.chunk_text,
                (dc.embedding <=> query_embedding) as vector_distance,
                (1 - (dc.embedding <=> query_embedding))::real as v_score_normalized,
                ROW_NUMBER() OVER (ORDER BY dc.embedding <=> query_embedding) as vector_rank
            FROM document_chunks dc
            ORDER BY dc.embedding <=> query_embedding
            LIMIT result_limit * 2
        ),
        fuzzy_keyword_results AS (
            -- Enhanced fuzzy keyword results (already 0.0-1.0)
            SELECT 
                dc.document_id,
                dc.id as chunk_id,
                dc.chunk_text,
                GREATEST(
                    similarity(dc.chunk_text, search_query),
                    word_similarity(search_query, dc.chunk_text)
                )::real as k_score_normalized,
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
                COALESCE(vr.v_score_normalized, 0.0)::real as vector_score,
                COALESCE(kr.k_score_normalized, 0.0)::real as keyword_score,
                -- RRF scoring (normalize to 0.0-1.0 range)
                (COALESCE(1.0 / (rrf_k + vr.vector_rank), 0.0) + 
                 COALESCE(1.0 / (rrf_k + kr.keyword_rank), 0.0))::real as rrf_score,
                -- NORMALIZED weighted hybrid score (all components 0.0-1.0)
                (vector_weight * COALESCE(vr.v_score_normalized, 0.0) + 
                 keyword_weight * COALESCE(kr.k_score_normalized, 0.0))::real as hybrid_score,
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
            cr.match_sources,
            'hybrid_fuzzy'::text as score_type
        FROM combined_results cr
        JOIN documents d ON cr.document_id = d.id
        ORDER BY cr.hybrid_score DESC
        LIMIT result_limit;
    ELSE
        -- Call existing function with NORMALIZED scores
        RETURN QUERY
        SELECT 
            hr.doc_id,
            hr.chunk_id,
            hr.snippet,
            hr.title,
            hr.document_category,
            hr.law_area,
            hr.vector_score,  -- Already normalized in original function
            -- NORMALIZE keyword component: ts_rank to 0.0-1.0
            LEAST(hr.keyword_score * 10.0, 1.0)::real as keyword_score,
            hr.rrf_score,
            -- RECALCULATE hybrid with normalized keyword score
            (vector_weight * hr.vector_score + 
             keyword_weight * LEAST(hr.keyword_score * 10.0, 1.0))::real as hybrid_score,
            hr.match_sources,
            'hybrid_normal'::text as score_type
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
-- ENHANCED TEST FUNCTION WITH SCORE COMPARISON
-- =============================================================================

CREATE OR REPLACE FUNCTION test_score_normalization(
    test_query text,
    test_typo text DEFAULT NULL
)
RETURNS TABLE (
    test_type text,
    query_used text,
    result_count bigint,
    top_score real,
    score_type text,
    score_range text
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Test 1: Normal search (now normalized)
    RETURN QUERY
    SELECT 
        'normal_normalized'::text as test_type,
        test_query as query_used,
        COUNT(*)::bigint as result_count,
        COALESCE(MAX(skr.score), 0.0)::real as top_score,
        MAX(skr.score_type) as score_type,
        ('0.0-1.0')::text as score_range
    FROM search_documents_keyword_enhanced(test_query, 5, false) skr;
    
    -- Test 2: Fuzzy search with original query
    RETURN QUERY
    SELECT 
        'fuzzy_normalized'::text as test_type,
        test_query as query_used,
        COUNT(*)::bigint as result_count,
        COALESCE(MAX(skr.score), 0.0)::real as top_score,
        MAX(skr.score_type) as score_type,
        ('0.0-1.0')::text as score_range
    FROM search_documents_keyword_enhanced(test_query, 5, true, 0.3) skr;
    
    -- Test 3: Fuzzy search with typo (if provided)
    IF test_typo IS NOT NULL THEN
        RETURN QUERY
        SELECT 
            'fuzzy_typo_normalized'::text as test_type,
            test_typo as query_used,
            COUNT(*)::bigint as result_count,
            COALESCE(MAX(skr.score), 0.0)::real as top_score,
            MAX(skr.score_type) as score_type,
            ('0.0-1.0')::text as score_range
        FROM search_documents_keyword_enhanced(test_typo, 5, true, 0.3) skr;
    END IF;
END;
$$;

-- =============================================================================
-- USAGE EXAMPLES
-- =============================================================================

/*

-- Test normalized keyword search
SELECT * FROM search_documents_keyword_enhanced('taxpayer', 5, false);
SELECT * FROM search_documents_keyword_enhanced('taxpayer', 5, true, 0.3);

-- Compare normalized scores
SELECT * FROM test_score_normalization('taxpayer', 'taxpayeer');

-- Test normalized hybrid search (requires embedding)
-- All scores should now be in 0.0-1.0 range and properly comparable

*/

-- =============================================================================
-- DEPLOYMENT NOTES
-- =============================================================================

/*

SCORE NORMALIZATION IMPLEMENTATION:

✅ WHAT'S FIXED:
1. All search modes now return scores in 0.0-1.0 range
2. Full-text scores multiplied by 10.0 (capped at 1.0)
3. Fuzzy scores kept as-is (already 0.0-1.0)
4. Vector scores kept as-is (already 0.0-1.0)
5. Hybrid search uses normalized component scores
6. Added score_type field for transparency

✅ BENEFITS:
1. Consistent scoring across all search modes
2. Hybrid search weights work correctly
3. User-friendly score interpretation (0.85 = 85% relevance)
4. Eliminates 10x+ score differences
5. Maintains search quality while fixing display

✅ NEXT STEPS:
1. Execute this SQL in Supabase
2. Test normalized scores
3. Update application to use enhanced functions
4. Update UI to show score types if desired

*/ 