-- Quick fix for column ambiguity in search_documents_keyword_enhanced

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
                d.id as document_id,  -- Changed from doc_id to avoid conflict
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
            fr.document_id::bigint as doc_id,  -- Use explicit table alias
            fr.chunk_id,
            fr.snippet,
            fr.title,
            fr.fuzzy_score as score,
            fr.source
        FROM fuzzy_results fr
        ORDER BY fr.fuzzy_score DESC
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

-- Fix test function as well
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
        'normal'::text as test_type,
        test_query as query_used,
        COUNT(*)::bigint as result_count,
        COALESCE(MAX(skr.score), 0.0)::real as first_result_score
    FROM search_documents_keyword_enhanced(test_query, 5, false) skr;
    
    -- Test 2: Fuzzy search with original query
    RETURN QUERY
    SELECT 
        'fuzzy_original'::text as test_type,
        test_query as query_used,
        COUNT(*)::bigint as result_count,
        COALESCE(MAX(skr.score), 0.0)::real as first_result_score
    FROM search_documents_keyword_enhanced(test_query, 5, true, 0.3) skr;
    
    -- Test 3: Fuzzy search with typo (if provided)
    IF test_typo IS NOT NULL THEN
        RETURN QUERY
        SELECT 
            'fuzzy_typo'::text as test_type,
            test_typo as query_used,
            COUNT(*)::bigint as result_count,
            COALESCE(MAX(skr.score), 0.0)::real as first_result_score
        FROM search_documents_keyword_enhanced(test_typo, 5, true, 0.3) skr;
    END IF;
END;
$$; 