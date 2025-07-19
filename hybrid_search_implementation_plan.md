# Hybrid Search Implementation Plan

## Overview
This plan outlines the implementation of hybrid search functionality that combines:
- **Vector Similarity Search** (existing) - semantic understanding using embeddings
- **Keyword/BM25 Search** (new) - exact term matching and traditional relevance scoring
- **Hybrid Ranking** (new) - weighted combination of both approaches

### Why Hybrid Search?
Currently, the application uses **semantic search**, which excels at understanding *intent* and *context*. For example, it knows that "tax implications of selling a small company" relates to "small business CGT concessions."

However, semantic search can struggle with:
- **Specific keywords, acronyms, or codes** (e.g., "ATO", "section 180", "CGT")
- **Exact term matches** that users search for verbatim
- **Legal references** and specific document numbers

**Hybrid search** gives you the best of both worlds:
- **Semantic Search:** Finds conceptually related documents, even without shared keywords
- **Keyword Search:** Finds documents with exact term matches, critical for precision
- **Combined Power:** Documents that match both semantically AND contain exact terms rank highest

## Current State Analysis

### Existing Vector Search
- ✅ Supabase with pgvector extension
- ✅ Document embeddings stored in `document_chunks.embedding`
- ✅ Similarity search using cosine distance
- ✅ Embedding service (BAAI/bge-large-en-v1.5)

### What We Need to Add
- ❌ Full-text search capabilities
- ❌ BM25/keyword scoring
- ❌ Hybrid ranking algorithm
- ❌ Search mode selection (vector/keyword/hybrid)

## Implementation Strategy

### Phase 1: Database Schema Updates
**Objective**: Add full-text search capabilities to the database

#### 1.1 Add Full-Text Search Indexes
```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy/similarity search

-- Add GIN indexes for full-text search on document content
CREATE INDEX IF NOT EXISTS idx_document_chunks_fts 
ON document_chunks USING GIN (to_tsvector('english', chunk_text));

-- Add GIN index on document metadata for keyword search
CREATE INDEX IF NOT EXISTS idx_documents_fts_title 
ON documents USING GIN (to_tsvector('english', title));

CREATE INDEX IF NOT EXISTS idx_documents_fts_content 
ON documents USING GIN (to_tsvector('english', extracted_content));

-- Add trigram indexes for fuzzy keyword search
CREATE INDEX IF NOT EXISTS idx_document_chunks_trigram 
ON document_chunks USING GIN (chunk_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_documents_trigram_title 
ON documents USING GIN (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_documents_trigram_content 
ON documents USING GIN (extracted_content gin_trgm_ops);
```

#### 1.2 Add Search Configuration Support
```sql
-- Consider adding custom text search configurations for legal terminology
-- This can be done later as an optimization

-- Test fuzzy search functionality
SELECT 
    chunk_text,
    similarity(chunk_text, 'restraint of trade') as sim_score
FROM document_chunks 
WHERE similarity(chunk_text, 'restraint of trade') > 0.3
ORDER BY sim_score DESC;
```

#### 1.3 Fuzzy Search Benefits for Legal Documents
Fuzzy search is particularly valuable for legal documents because:

- **Acronym Variations**: "ATO" vs "A.T.O." vs "Australian Taxation Office"
- **Legal Term Variants**: "licence" vs "license", "judgement" vs "judgment"  
- **Citation Formats**: Different ways of citing the same case or legislation
- **Typo Tolerance**: "restraing" finds "restraint", "seperation" finds "separation"
- **Partial Matches**: "employ" matches "employment", "employer", "employee"
- **OCR Errors**: Documents scanned with OCR may have character recognition errors

### Phase 2: Backend API Enhancements
**Objective**: Extend the RAG API to support hybrid search

#### 2.1 Update Search Parameters
- Add `search_mode` parameter: `"vector"`, `"keyword"`, `"hybrid"`
- Add `vector_weight` and `keyword_weight` parameters for hybrid mode
- Maintain backward compatibility with existing vector search

#### 2.2 Implement Keyword Search Function
```python
# Location: rag_api_service/main.py

async def keyword_search(
    query: str,
    limit: int = 10,
    min_score: float = 0.1,
    fuzzy: bool = False,
    similarity_threshold: float = 0.3
) -> List[Dict]:
    """
    Perform keyword search using PostgreSQL full-text search
    
    Args:
        query: Search terms
        limit: Maximum results to return
        min_score: Minimum relevance score threshold
        fuzzy: Enable fuzzy/similarity matching for typos and variations
        similarity_threshold: Minimum similarity score for fuzzy matches (0.0-1.0)
    """
    # Implementation to be added
```

#### 2.3 Implement Hybrid Search Function
```python
async def hybrid_search(
    query: str,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
    limit: int = 10
) -> List[Dict]:
    """
    Combine vector and keyword search results with weighted scoring
    """
    # Implementation to be added
```

#### 2.4 Update Existing Endpoints
- Modify `/search` endpoint to accept new parameters
- Add `/search/keyword` endpoint for pure keyword search
- Add `/search/hybrid` endpoint for hybrid search
- Maintain `/search/vector` for existing functionality

### Phase 3: Database Functions & Procedures
**Objective**: Implement efficient hybrid search at the database level

#### 3.1 Create Keyword Search Function
```sql
CREATE OR REPLACE FUNCTION search_documents_keyword(
    search_query TEXT,
    result_limit INTEGER DEFAULT 10,
    min_score FLOAT DEFAULT 0.1,
    use_fuzzy BOOLEAN DEFAULT FALSE,
    similarity_threshold FLOAT DEFAULT 0.3
)
RETURNS TABLE(
    document_id INTEGER,
    chunk_id INTEGER,
    chunk_text TEXT,
    keyword_score FLOAT,
    fuzzy_score FLOAT,
    combined_score FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF use_fuzzy THEN
        -- Combine exact keyword search with fuzzy trigram similarity
        RETURN QUERY
        WITH keyword_results AS (
            SELECT 
                dc.document_id,
                dc.id as chunk_id,
                dc.chunk_text,
                ts_rank(dc.search_vector, websearch_to_tsquery('english', search_query)) as kw_score,
                0.0 as fuzz_score
            FROM document_chunks dc
            WHERE dc.search_vector @@ websearch_to_tsquery('english', search_query)
            
            UNION ALL
            
            SELECT 
                dc.document_id,
                dc.id as chunk_id,
                dc.chunk_text,
                0.0 as kw_score,
                similarity(dc.chunk_text, search_query) as fuzz_score
            FROM document_chunks dc
            WHERE similarity(dc.chunk_text, search_query) > similarity_threshold
        ),
        combined_results AS (
            SELECT 
                document_id,
                chunk_id,
                chunk_text,
                MAX(kw_score) as keyword_score,
                MAX(fuzz_score) as fuzzy_score,
                GREATEST(MAX(kw_score), MAX(fuzz_score) * 0.8) as combined_score  -- Weight fuzzy slightly lower
            FROM keyword_results
            GROUP BY document_id, chunk_id, chunk_text
        )
        SELECT * FROM combined_results
        WHERE combined_score >= min_score
        ORDER BY combined_score DESC
        LIMIT result_limit;
    ELSE
        -- Standard exact keyword search only
        RETURN QUERY
        SELECT 
            dc.document_id,
            dc.id as chunk_id,
            dc.chunk_text,
            ts_rank(dc.search_vector, websearch_to_tsquery('english', search_query)) as keyword_score,
            0.0 as fuzzy_score,
            ts_rank(dc.search_vector, websearch_to_tsquery('english', search_query)) as combined_score
        FROM document_chunks dc
        WHERE dc.search_vector @@ websearch_to_tsquery('english', search_query)
          AND ts_rank(dc.search_vector, websearch_to_tsquery('english', search_query)) >= min_score
        ORDER BY keyword_score DESC
        LIMIT result_limit;
    END IF;
END;
$$;
```

#### 3.2 Create Hybrid Search Function
```sql
CREATE OR REPLACE FUNCTION search_documents_hybrid(
    search_query TEXT,
    query_embedding VECTOR(1024),
    vector_weight FLOAT DEFAULT 0.7,
    keyword_weight FLOAT DEFAULT 0.3,
    result_limit INTEGER DEFAULT 10
)
RETURNS TABLE(
    document_id INTEGER,
    chunk_id INTEGER,
    chunk_text TEXT,
    vector_score FLOAT,
    keyword_score FLOAT,
    hybrid_score FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Implementation combining both search methods
END;
$$;
```

### Phase 4: Frontend Integration
**Objective**: Add hybrid search controls to the UI

#### 4.1 Search Interface Updates
- Add search mode selector (Vector/Keyword/Hybrid)
- Add weight sliders for hybrid mode
- Add advanced search options panel
- Update results display to show relevance indicators

#### 4.2 Results Enhancement
- Show why results were matched (vector similarity vs keyword match)
- Add relevance score visualization
- Highlight matched keywords in results
- Add search mode indicator for each result

### Phase 5: Testing & Optimization
**Objective**: Ensure hybrid search works effectively

#### 5.1 Test Scenarios
- **Vector-strong queries**: "employment law termination procedures"
- **Keyword-strong queries**: "section 180", "ATO ruling", "CGT"  
- **Hybrid queries**: "small business tax concessions"
- **Fuzzy keyword queries**: "restraing trade" (typo), "A.T.O." vs "ATO", "licence" vs "license"
- **Edge cases**: very short queries, very long queries, no results

#### 5.2 Performance Optimization
- Index optimization
- Query performance tuning
- Caching strategies for common searches
- Batch processing for multiple search modes

## Implementation Details

### Database Schema Changes

#### New Columns (Recommended)
```sql
-- Add tsvector column for optimized full-text search
-- tsvector is an optimized representation stripped of stop words with stemming
ALTER TABLE document_chunks 
ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Also add to documents table for title/metadata search
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Create function to update search vectors automatically
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    -- For document_chunks table
    IF TG_TABLE_NAME = 'document_chunks' THEN
        NEW.search_vector = to_tsvector('english', NEW.chunk_text);
    -- For documents table  
    ELSIF TG_TABLE_NAME = 'documents' THEN
        NEW.search_vector = to_tsvector('english', 
            COALESCE(NEW.title, '') || ' ' || 
            COALESCE(NEW.extracted_content, '') || ' ' ||
            COALESCE(NEW.law_area::text, '') || ' ' ||
            COALESCE(NEW.document_category, '')
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers to auto-update search vectors
CREATE TRIGGER update_document_chunks_search_vector
    BEFORE INSERT OR UPDATE ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

CREATE TRIGGER update_documents_search_vector
    BEFORE INSERT OR UPDATE ON documents  
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- Create GIN indexes for fast full-text search
CREATE INDEX IF NOT EXISTS idx_document_chunks_search_vector 
ON document_chunks USING GIN (search_vector);

CREATE INDEX IF NOT EXISTS idx_documents_search_vector 
ON documents USING GIN (search_vector);

-- Populate existing data
UPDATE document_chunks SET search_vector = to_tsvector('english', chunk_text);
UPDATE documents SET search_vector = to_tsvector('english', 
    COALESCE(title, '') || ' ' || 
    COALESCE(extracted_content, '') || ' ' ||
    COALESCE(law_area::text, '') || ' ' ||
    COALESCE(document_category, '')
);
```

### API Endpoint Specifications

#### Updated Search Endpoint
```python
@app.post("/search")
async def search_documents(
    request: SearchRequest
):
    """
    SearchRequest model:
    - query: str
    - mode: Literal["vector", "keyword", "hybrid"] = "vector"
    - vector_weight: float = 0.7  # for hybrid mode
    - keyword_weight: float = 0.3  # for hybrid mode
    - limit: int = 10
    - min_score: float = 0.1
    - fuzzy: bool = False  # enable fuzzy keyword matching
    - similarity_threshold: float = 0.3  # for fuzzy matching (0.0-1.0)
    """
```

### Hybrid Scoring Algorithm

#### Simple Weighted Combination
```python
def calculate_hybrid_score(
    vector_score: float,
    keyword_score: float,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3
) -> float:
    # Normalize scores to 0-1 range
    normalized_vector = min(1.0, max(0.0, vector_score))
    normalized_keyword = min(1.0, max(0.0, keyword_score))
    
    return (normalized_vector * vector_weight) + (normalized_keyword * keyword_weight)
```

#### Advanced RRF (Reciprocal Rank Fusion)
RRF is the industry-standard solution for combining multiple result sets. Instead of looking at the *scores* of the results, it looks only at their *rank* in each list, making it perfect for combining different search types.

**Formula:** For each document, its RRF score is the sum of the reciprocal of its rank in each result list.

```
RRF Score(d) = Σ(1 / (k + rank_i(d)))
```

Where:
- `d` is a specific document
- `rank_i(d)` is the rank of document `d` in result list `i`
- `k` is a constant (commonly 60) to prevent over-penalization of lower-ranked items

**Example:**
Search query: "restraint of trade clause"

Vector Search Results:
1. doc_A (Employment contracts guide)
2. doc_B (What is restraint of trade?)
3. doc_C (Non-compete examples)

Keyword Search Results:
1. doc_B (Title contains "restraint of trade")
2. doc_D (Post-employment clauses case study)
3. doc_A (Mentions "clause" frequently)

RRF Calculation (k=60):
- Score(doc_A): 1/(60+1) + 1/(60+3) = 0.0164 + 0.0159 = 0.0323
- Score(doc_B): 1/(60+2) + 1/(60+1) = 0.0161 + 0.0164 = 0.0325
- Score(doc_C): 1/(60+3) = 0.0159
- Score(doc_D): 1/(60+2) = 0.0161

Final Ranking: doc_B, doc_A, doc_D, doc_C

```python
def reciprocal_rank_fusion(
    vector_results: List[SearchResult],
    keyword_results: List[SearchResult],
    k: int = 60
) -> List[SearchResult]:
    """
    Combine search results using Reciprocal Rank Fusion algorithm
    """
    rrf_scores = {}
    
    # Calculate RRF scores for vector results
    for rank, result in enumerate(vector_results, 1):
        doc_id = result.document_id
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + (1 / (k + rank))
    
    # Add RRF scores for keyword results
    for rank, result in enumerate(keyword_results, 1):
        doc_id = result.document_id
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + (1 / (k + rank))
    
    # Sort by RRF score and return combined results
    return sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
```

## Migration Strategy

### Step 1: Database Migration
1. Apply schema changes to hybrid-search branch
2. Test full-text search indexes
3. Verify existing functionality still works

### Step 2: Backend Development
1. Implement keyword search functions
2. Add hybrid search logic
3. Update API endpoints with backward compatibility
4. Add comprehensive testing

### Step 3: Frontend Updates
1. Add search mode controls
2. Update results display
3. Add search analytics/feedback

### Step 4: Testing & Deployment
1. Test with real data in hybrid-search branch
2. Performance testing and optimization
3. User acceptance testing
4. Deploy to production

## Success Metrics

### Functional Requirements
- ✅ All existing vector search functionality preserved
- ✅ Keyword search returns relevant results for exact terms
- ✅ Hybrid search combines both effectively
- ✅ Performance acceptable for typical queries (<2 seconds)

### User Experience
- ✅ Intuitive search mode selection
- ✅ Clear indication of result relevance
- ✅ Better results for both semantic and exact queries
- ✅ Backward compatibility maintained

## Risk Mitigation

### Performance Risks
- **Risk**: Full-text search slower than vector search
- **Mitigation**: Optimize indexes, use materialized views if needed

### Data Consistency Risks
- **Risk**: Search vectors out of sync with text content
- **Mitigation**: Database triggers and regular consistency checks

### User Experience Risks
- **Risk**: Too many options confuse users
- **Mitigation**: Smart defaults, progressive disclosure of advanced options

## Timeline Estimate

- **Phase 1** (Database): 2-3 days
- **Phase 2** (Backend): 4-5 days  
- **Phase 3** (Database Functions): 3-4 days
- **Phase 4** (Frontend): 3-4 days
- **Phase 5** (Testing): 2-3 days

**Total**: ~2-3 weeks with proper testing

## Next Steps

1. ✅ Complete data migration to hybrid-search branch
2. 🔄 Review and approve this implementation plan
3. ⏳ Begin Phase 1: Database schema updates
4. ⏳ Implement and test keyword search functionality
5. ⏳ Develop hybrid ranking algorithm
6. ⏳ Update frontend interface
7. ⏳ Comprehensive testing and optimization

---

*This plan will be updated as implementation progresses and requirements are refined.* 