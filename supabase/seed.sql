-- Main seed file for Supabase development branch
-- This file runs all seed scripts in the correct order to populate the development database
-- 
-- Usage: 
-- 1. Via Supabase CLI: supabase db seed
-- 2. Via SQL editor in Supabase dashboard: Copy and paste this file
-- 3. Via API call: Execute this file against your development branch

-- Note: This seed data is designed for testing hybrid search functionality
-- It includes documents covering Australian legal topics with realistic content and metadata

BEGIN;

-- Clear existing data (use carefully - this will delete all data!)
-- Uncomment these lines if you want to reset the database completely
-- TRUNCATE TABLE activity_logs CASCADE;
-- TRUNCATE TABLE document_chunks CASCADE;  
-- TRUNCATE TABLE documents CASCADE;

-- Reset sequences to start from 1 (optional, for clean ID numbering)
-- ALTER SEQUENCE documents_id_seq RESTART WITH 1;
-- ALTER SEQUENCE document_chunks_id_seq RESTART WITH 1;
-- ALTER SEQUENCE activity_logs_id_seq RESTART WITH 1;

-- Execute seed files in order
\i seed/001_sample_documents.sql
\i seed/002_sample_document_chunks.sql
\i seed/003_sample_activity_logs.sql

COMMIT;

-- Verification queries (optional - these will show what was inserted)
SELECT 
    COUNT(*) as document_count,
    COUNT(DISTINCT law_area) as unique_law_areas,
    COUNT(DISTINCT document_category) as unique_categories
FROM documents;

SELECT 
    COUNT(*) as chunk_count,
    COUNT(DISTINCT document_id) as documents_with_chunks,
    AVG(LENGTH(content)) as avg_chunk_length
FROM document_chunks;

SELECT 
    COUNT(*) as activity_count,
    COUNT(DISTINCT event_type) as unique_event_types,
    COUNT(DISTINCT username) as unique_users
FROM activity_logs;

-- Show sample data for verification
SELECT 'Sample Documents:' as info;
SELECT id, title, law_area, document_category FROM documents LIMIT 3;

SELECT 'Sample Chunks:' as info;
SELECT document_id, chunk_index, LEFT(content, 100) || '...' as content_preview 
FROM document_chunks LIMIT 3;

SELECT 'Sample Activity Logs:' as info;
SELECT username, event_type, search_term, created_at 
FROM activity_logs 
WHERE event_type = 'SEARCH_SUBMITTED' 
LIMIT 3; 