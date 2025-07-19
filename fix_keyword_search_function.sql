-- Drop and recreate the function with fixed column references
DROP FUNCTION IF EXISTS search_documents_keyword(TEXT, INTEGER, FLOAT, BOOLEAN, FLOAT);

CREATE OR REPLACE FUNCTION search_documents_keyword(
    search_query TEXT,
    result_limit INTEGER DEFAULT 10,
    min_score FLOAT DEFAULT 0.1,
    use_fuzzy BOOLEAN DEFAULT FALSE,
    similarity_threshold FLOAT DEFAULT 0.3
)
RETURNS TABLE(
    doc_id INTEGER,
    chunk_id UUID,
    chunk_text TEXT,
    document_title TEXT,
    document_category TEXT,
    law_area TEXT[],
    keyword_score FLOAT,
    fuzzy_score FLOAT,
    combined_score FLOAT,
    match_source TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF use_fuzzy THEN
        -- Combine exact keyword search with fuzzy trigram similarity
        RETURN QUERY
        WITH keyword_results AS (
            -- Search in document chunks (content)
            SELECT 
                dc.document_id as doc_id,
                dc.id as chunk_id,
                dc.chunk_text,
                d.title as document_title,
                d.document_category,
                d.law_area,
                ts_rank(dc.search_vector, websearch_to_tsquery('english', search_query)) as kw_score,
                0.0 as fuzz_score,
                'content' as match_source
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE dc.search_vector @@ websearch_to_tsquery('english', search_query)
            
            UNION ALL
            
            -- Search in document metadata
            SELECT 
                d.id as doc_id,
                dc.id as chunk_id,
                dc.chunk_text,
                d.title as document_title,
                d.document_category,
                d.law_area,
                ts_rank(d.search_vector, websearch_to_tsquery('english', search_query)) as kw_score,
                0.0 as fuzz_score,
                'metadata' as match_source
            FROM documents d
            JOIN document_chunks dc ON d.id = dc.document_id
            WHERE d.search_vector @@ websearch_to_tsquery('english', search_query)
            
            UNION ALL
            
            -- Fuzzy search in document chunks
            SELECT 
                dc.document_id as doc_id,
                dc.id as chunk_id,
                dc.chunk_text,
                d.title as document_title,
                d.document_category,
                d.law_area,
                0.0 as kw_score,
                similarity(dc.chunk_text, search_query) as fuzz_score,
                'fuzzy_content' as match_source
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE similarity(dc.chunk_text, search_query) > similarity_threshold
            
            UNION ALL
            
            -- Fuzzy search in document titles
            SELECT 
                d.id as doc_id,
                dc.id as chunk_id,
                dc.chunk_text,
                d.title as document_title,
                d.document_category,
                d.law_area,
                0.0 as kw_score,
                similarity(d.title, search_query) as fuzz_score,
                'fuzzy_title' as match_source
            FROM documents d
            JOIN document_chunks dc ON d.id = dc.document_id
            WHERE similarity(d.title, search_query) > similarity_threshold
        ),
        combined_results AS (
            SELECT 
                kr.doc_id,
                kr.chunk_id,
                kr.chunk_text,
                kr.document_title,
                kr.document_category,
                kr.law_area,
                MAX(kr.kw_score) as keyword_score,
                MAX(kr.fuzz_score) as fuzzy_score,
                -- Combine scores: exact matches weighted higher than fuzzy
                GREATEST(MAX(kr.kw_score), MAX(kr.fuzz_score) * 0.8) as combined_score,
                string_agg(DISTINCT kr.match_source, ', ') as match_source
            FROM keyword_results kr
            GROUP BY kr.doc_id, kr.chunk_id, kr.chunk_text, kr.document_title, kr.document_category, kr.law_area
        )
        SELECT * FROM combined_results
        WHERE combined_results.combined_score >= min_score
        ORDER BY combined_results.combined_score DESC
        LIMIT result_limit;
    ELSE
        -- Standard exact keyword search only
        RETURN QUERY
        WITH exact_results AS (
            -- Search in document chunks (content)
            SELECT 
                dc.document_id as doc_id,
                dc.id as chunk_id,
                dc.chunk_text,
                d.title as document_title,
                d.document_category,
                d.law_area,
                ts_rank(dc.search_vector, websearch_to_tsquery('english', search_query)) as kw_score,
                'content' as match_source
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE dc.search_vector @@ websearch_to_tsquery('english', search_query)
            
            UNION ALL
            
            -- Search in document metadata  
            SELECT 
                d.id as doc_id,
                dc.id as chunk_id,
                dc.chunk_text,
                d.title as document_title,
                d.document_category,
                d.law_area,
                ts_rank(d.search_vector, websearch_to_tsquery('english', search_query)) as kw_score,
                'metadata' as match_source
            FROM documents d
            JOIN document_chunks dc ON d.id = dc.document_id
            WHERE d.search_vector @@ websearch_to_tsquery('english', search_query)
        ),
        combined_exact AS (
            SELECT 
                er.doc_id,
                er.chunk_id,
                er.chunk_text,
                er.document_title,
                er.document_category,
                er.law_area,
                MAX(er.kw_score) as keyword_score,
                0.0 as fuzzy_score,
                MAX(er.kw_score) as combined_score,
                string_agg(DISTINCT er.match_source, ', ') as match_source
            FROM exact_results er
            GROUP BY er.doc_id, er.chunk_id, er.chunk_text, er.document_title, er.document_category, er.law_area
        )
        SELECT * FROM combined_exact
        WHERE combined_exact.combined_score >= min_score
        ORDER BY combined_exact.combined_score DESC
        LIMIT result_limit;
    END IF;
END;
$$; 