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
DROP TRIGGER IF EXISTS update_document_chunks_search_vector ON document_chunks;
CREATE TRIGGER update_document_chunks_search_vector
    BEFORE INSERT OR UPDATE ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

DROP TRIGGER IF EXISTS update_documents_search_vector ON documents;
CREATE TRIGGER update_documents_search_vector
    BEFORE INSERT OR UPDATE ON documents  
    FOR EACH ROW EXECUTE FUNCTION update_search_vector(); 