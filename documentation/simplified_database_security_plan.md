# Simplified Database Security Plan

## Core Requirement
**Simple Binary Access Control**: Authenticated users can access everything, unauthenticated users get nothing.

## Design Decision: User Context for All Operations

### **Architectural Choice**
All operations, including automated system processes, will run under the context of the user who initiated them. There will be no separate "system user" or mixed permission contexts.

#### **Rationale:**
- **Simplified Security Model**: With "authenticated users access everything" policies, there's no functional difference between user and system operations
- **Clear Audit Trail**: Every operation traces back to the initiating user
- **Reduced Complexity**: No need to manage multiple permission contexts or service role switching
- **Future-Proof**: Scales naturally when adding document upload functionality

#### **Consequences:**
✅ **Benefits:**
- Single, consistent permission model
- Comprehensive audit trail (user responsible for all derived operations)
- Simpler RLS policies
- Easier debugging and compliance tracking
- Natural ownership model for uploaded documents

⚠️ **Considerations:**
- Long-running processes must maintain user context throughout
- Background jobs require different handling (rare in this application)
- User session management becomes critical for system operations

## Current Security Gap
- Database uses service role key (bypasses all Supabase auth)
- No protection against unauthenticated access if keys are compromised
- Need to track user identity for audit logs only

## Simplified Solution: Supabase Auth + Basic RLS

### Phase 1: Switch to Supabase Auth Integration

#### 1.1 Update Supabase Configuration
Instead of using the service role key for everything, use Supabase's built-in auth system:

```javascript
// Current approach (in your API):
const supabase = createClient(url, SERVICE_ROLE_KEY) // Bypasses all security

// New approach:
const supabase = createClient(url, ANON_KEY) // Respects RLS policies
```

#### 1.2 User Context Management
Since all operations run under user context, we need robust session management:

```python
# Enhanced user context function
def get_user_supabase_client(token_payload: dict):
    """Create Supabase client with user context for ALL operations"""
    
    # Create client with anon key (respects RLS)
    supabase = create_client(
        global_config["supabase_url"], 
        global_config["supabase_anon_key"]
    )
    
    # Set the user session for RLS policies
    user_email = token_payload.get('email')
    user_id = token_payload.get('sub')
    user_name = token_payload.get('name', '')
    
    # Set auth context (this makes user "authenticated" for RLS)
    supabase.auth.set_session({
        'access_token': f"azure_ad_token_{user_id}",  # Unique per user
        'refresh_token': 'refresh_placeholder',
        'user': {
            'id': user_id,
            'email': user_email,
            'name': user_name,
            'aud': 'authenticated',
            'role': 'authenticated'
        }
    })
    
    return supabase, user_email, user_id
```

### Phase 2: Simple RLS Policies

#### 2.1 Enable RLS (One Line Per Table)
```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_logs ENABLE ROW LEVEL SECURITY;
```

#### 2.2 Simple "Authenticated Only" Policies
```sql
-- Documents: Any authenticated user can read/write everything
CREATE POLICY "authenticated_users_all_access" ON documents
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- Document chunks: Any authenticated user can read/write everything  
-- This covers both user searches AND system chunk creation
CREATE POLICY "authenticated_users_all_access" ON document_chunks
    FOR ALL
    TO authenticated  
    USING (true)
    WITH CHECK (true);

-- Activity logs: Any authenticated user can read/write everything
-- System operations (like chunk creation) log under user context
CREATE POLICY "authenticated_users_all_access" ON activity_logs
    FOR ALL
    TO authenticated
    USING (true) 
    WITH CHECK (true);

-- Block all anonymous access to all tables
CREATE POLICY "block_anonymous_access" ON documents
    FOR ALL
    TO anon
    USING (false);

CREATE POLICY "block_anonymous_access" ON document_chunks
    FOR ALL
    TO anon
    USING (false);
    
CREATE POLICY "block_anonymous_access" ON activity_logs
    FOR ALL
    TO anon
    USING (false);
```

### Phase 3: Application Implementation with User Context

#### 3.1 Update Search Endpoints (Existing Functionality)
```python
@app.post("/search", response_model=SearchResponse)
async def search_endpoint(
    request: SearchRequest, 
    token_payload: dict = Depends(verify_token)
):
    # Get user-specific client 
    user_supabase, user_email, user_id = get_user_supabase_client(token_payload)
    
    # All search operations run under user context
    # This includes vector search, keyword search, and hybrid search
    # RLS automatically allows access since user is authenticated
    
    # Your existing search logic stays the same!
    # Just replace global_supabase_client with user_supabase
    
    # Log search activity under user context
    user_supabase.table("activity_logs").insert({
        "authenticated_user_email": user_email,
        "authenticated_user_id": user_id,
        "event_type": "SEARCH_SUBMITTED",
        "search_term": request.query,
        "details": {
            "search_type": "hybrid" if request.vector_search and request.keyword_search else "vector",
            "response_time_ms": response_time
        }
    }).execute()
```

#### 3.2 Document Upload with System Operations Under User Context
```python
@app.post("/upload-document")
async def upload_document(
    file: UploadFile,
    token_payload: dict = Depends(verify_token)
):
    # Single user context for entire upload pipeline
    user_supabase, user_email, user_id = get_user_supabase_client(token_payload)
    
    try:
        # 1. User creates document record
        doc_response = user_supabase.table("documents").insert({
            "original_filename": file.filename,
            "title": extract_title(file.filename),
            "uploaded_by_email": user_email,  # Audit trail
            "uploaded_by_user_id": user_id,   # Audit trail
            "file_type": file.content_type,
            "created_date": datetime.utcnow(),
            "document_category": "user_upload"
        }).execute()
        
        doc_id = doc_response.data[0]["id"]
        
        # 2. System processes file (under user context)
        content = await extract_text_from_file(file)
        chunks = chunk_text(content, max_size=1000)
        
        # 3. System creates chunks (under user context)
        chunk_records = []
        for i, chunk_text in enumerate(chunks):
            chunk_record = user_supabase.table("document_chunks").insert({
                "document_id": doc_id,
                "chunk_index": i,
                "content": chunk_text,
                # No embedding yet - will be added in next step
            }).execute()
            chunk_records.append(chunk_record.data[0])
        
        # 4. System generates embeddings (under user context)
        embeddings = await generate_embeddings([chunk["content"] for chunk in chunk_records])
        
        # 5. System updates chunks with embeddings (under user context)
        for chunk_record, embedding in zip(chunk_records, embeddings):
            user_supabase.table("document_chunks").update({
                "embedding": embedding
            }).eq("id", chunk_record["id"]).execute()
        
        # 6. Log the complete process (under user context)
        user_supabase.table("activity_logs").insert({
            "authenticated_user_email": user_email,
            "authenticated_user_id": user_id,
            "event_type": "DOCUMENT_UPLOADED",
            "document_id": doc_id,
            "document_filename": file.filename,
            "details": {
                "chunks_created": len(chunks),
                "file_size_bytes": file.size,
                "processing_duration_seconds": processing_time,
                "embedding_model": "BAAI/bge-large-en-v1.5"
            }
        }).execute()
        
        return {
            "document_id": doc_id,
            "chunks_created": len(chunks),
            "status": "success"
        }
        
    except Exception as e:
        # Error logging also under user context
        user_supabase.table("activity_logs").insert({
            "authenticated_user_email": user_email,
            "authenticated_user_id": user_id,
            "event_type": "DOCUMENT_UPLOAD_FAILED",
            "document_filename": file.filename,
            "details": {
                "error": str(e),
                "processing_stage": "chunk_creation"  # or wherever it failed
            }
        }).execute()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
```

#### 3.3 Activity Logging with User Context
```python
@app.post("/log-activity")
async def log_activity_endpoint(
    log_entry: LogEntryRequest,
    token_payload: dict = Depends(verify_token)
):
    # Get user client
    user_supabase, user_email, user_id = get_user_supabase_client(token_payload)
    
    # All logs automatically include user context
    log_data = {
        **log_entry.dict(),
        "authenticated_user_email": user_email,  # Always present
        "authenticated_user_id": user_id,        # Always present
        "created_at": datetime.utcnow()
    }
    
    # Remove None values
    log_data = {k: v for k, v in log_data.items() if v is not None}
    
    response = user_supabase.table("activity_logs").insert(log_data).execute()
    return {"status": "success", "log_id": response.data[0]["id"]}
```

### Phase 4: Environment Configuration

#### 4.1 Add New Environment Variables
```bash
# Add to your Doppler configuration
SUPABASE_ANON_KEY="your-anon-key-here"  # From Supabase dashboard

# Keep existing variables
SUPABASE_URL="your-url"
SUPABASE_SERVICE_ROLE_KEY="your-service-key"  # Only for rare admin operations
```

#### 4.2 Database Schema Additions
```sql
-- Add user tracking columns to activity_logs
ALTER TABLE activity_logs ADD COLUMN IF NOT EXISTS 
    authenticated_user_email TEXT NOT NULL;
ALTER TABLE activity_logs ADD COLUMN IF NOT EXISTS 
    authenticated_user_id TEXT NOT NULL;

-- Add user tracking to documents (for upload audit trail)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS 
    uploaded_by_email TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS 
    uploaded_by_user_id TEXT;

-- Add indexes for user lookups
CREATE INDEX idx_activity_logs_user_email ON activity_logs(authenticated_user_email);
CREATE INDEX idx_activity_logs_user_id ON activity_logs(authenticated_user_id);
CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by_email);
```

## Exception: Service Role for Admin Operations

While 99% of operations use user context, there are rare cases requiring service role:

```python
# Admin-only operations that bypass normal user restrictions
def get_service_supabase_client():
    """Only for admin operations - use sparingly"""
    return create_client(
        global_config["supabase_url"], 
        global_config["supabase_service_role_key"]
    )

@app.delete("/admin/documents/{doc_id}")
async def admin_delete_document(
    doc_id: int,
    token_payload: dict = Depends(verify_admin_token)  # Separate admin check
):
    # Admin operations use service role to bypass RLS
    service_supabase = get_service_supabase_client()
    
    # Delete document and all chunks (bypasses normal user restrictions)
    service_supabase.table("document_chunks").delete().eq("document_id", doc_id).execute()
    service_supabase.table("documents").delete().eq("id", doc_id).execute()
    
    # Log admin action with service context
    service_supabase.table("activity_logs").insert({
        "authenticated_user_email": token_payload.get('email'),
        "authenticated_user_id": token_payload.get('sub'),
        "event_type": "ADMIN_DOCUMENT_DELETED",
        "document_id": doc_id,
        "details": {"admin_action": True, "bypass_rls": True}
    }).execute()
```

## Summary of Changes

### What Changes ✏️
1. **Use anon key instead of service key** for all user operations
2. **Add 6 simple RLS policies** (3 tables × 2 policies each)
3. **All system operations inherit user context** from initiating user
4. **Comprehensive user tracking** in audit logs
5. **Service role reserved for admin operations only**

### What Stays the Same ✅
- Your existing Azure AD authentication (no changes to `security.py`)
- Your search logic and database queries (just change client)
- Your frontend code
- Your vector search and hybrid search functionality
- All users can access all documents (firm-wide knowledge base)

### Security Benefits 🔒
- **Unauthenticated users**: Blocked at database level
- **Authenticated users**: Full access to everything
- **Complete audit trail**: Every operation traceable to a user
- **Compromised anon key**: Still requires valid authentication
- **System operations**: Protected by user authentication

### Migration Steps
1. **Add anon key** to environment variables
2. **Enable RLS and create policies** (5 minutes)
3. **Update API endpoints** to use user context pattern
4. **Add user tracking columns** to database
5. **Test with existing functionality**

This design provides enterprise-grade security with a simple, predictable model where every operation in the system can be traced back to the authenticated user who initiated it. 