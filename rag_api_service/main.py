import os
import sys
import requests
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from datetime import datetime # Import datetime for timestamp fields
from typing import List, Optional, Any, Dict # For List, Optional, Any, and Dict fields

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client, Client as SupabaseClient # Rename to avoid confusion
from sqlalchemy import create_engine
from fastapi.middleware.cors import CORSMiddleware # Import CORS middleware
from fastapi.responses import StreamingResponse # Import StreamingResponse
import io # Import io for BytesIO

# LangChain imports
from langchain_core.embeddings import Embeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.messages import SystemMessage # Removed HumanMessage as template does both
from langchain_core.documents import Document # Import Document class
from langchain_ollama.chat_models import ChatOllama
from langchain_openai import ChatOpenAI # Import ChatOpenAI
from langchain_community.vectorstores import SupabaseVectorStore # Corrected import

# Import doppler_integration from current directory
from doppler_integration import load_environment

# Load environment variables from Doppler or fallback to .env
load_environment()

# --- Global Variables for RAG Components (initialized in lifespan) ---
global_rag_chain = None
global_supabase_client = None # For fetching document details
global_config = {}

# --- Pydantic Models for API ---
class ChatQueryRequest(BaseModel):
    query: str
    limit: Optional[int] = 10 # Default limit for results
    # conversation_id: str | None = None # Optional for future history

class ChunkSnippet(BaseModel):
    content: str
    similarity: float
    chunk_index: Optional[int] = None # Optional, but good to have

class SourceDocument(BaseModel):
    id: str | int 
    original_filename: Optional[str] = None
    public_url: Optional[str] = None
    title: Optional[str] = None
    author: Optional[List[str]] = None # Array of strings
    last_modified: Optional[datetime] = None
    created_date: Optional[datetime] = None
    file_type: Optional[str] = None
    document_summary: Optional[str] = None
    law_area: Optional[List[str]] = None # Array of strings
    document_category: Optional[str] = None
    cleaned_filename: Optional[str] = None
    analysis_notes: Optional[str] = None
    snippets: Optional[List[ChunkSnippet]] = None # Added for chunk details

class SearchQueryResponse(BaseModel):
    query: str
    results: list[SourceDocument]
    # We can add more details like chunk previews or similarity scores if needed
    error: str | None = None

class ChatQueryResponse(BaseModel):
    answer: str
    sources: list[SourceDocument]
    error: str | None = None

class LogEntryRequest(BaseModel):
    event_type: str
    user_id: Optional[str] = None # From authenticated user
    username: Optional[str] = None # From authenticated user
    search_term: Optional[str] = None
    document_id: Optional[str] = None # Using str for ID consistency from frontend
    document_filename: Optional[str] = None
    preview_type: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

# --- Custom Embedding Class (Copied from chatbot.py) ---
class ApiEmbeddings(Embeddings):
    """Custom LangChain Embeddings class to call our FastAPI embedding service."""
    def __init__(self, api_url: str, expected_dimension: int):
        self.api_url = f"{api_url.rstrip('/')}/embed"
        self.expected_dimension = expected_dimension

    def _embed(self, text: str) -> list[float]: # Changed return type annotation
        """Internal helper to call the API for a single text. Raises exception on failure."""
        try:
            response = requests.post(self.api_url, json={"text": text}, timeout=60)
            response.raise_for_status() # Raise HTTPError for bad status codes
            data = response.json()
            embedding = data.get('embedding')
            if embedding and len(embedding) == self.expected_dimension:
                return embedding
            else:
                err_msg = f"API returned invalid embedding (len: {len(embedding) if embedding else 'None'}, expected: {self.expected_dimension})"
                print(f"Error: {err_msg}")
                raise ValueError(err_msg) # Raise specific error
        except requests.exceptions.RequestException as e:
            err_msg = f"Error calling embedding API at {self.api_url}: {e}"
            print(err_msg)
            raise ConnectionError(err_msg) from e # Raise specific error for connection issues
        except Exception as e:
            err_msg = f"Unexpected error during API embedding call: {e}"
            print(err_msg)
            raise RuntimeError(err_msg) from e # Raise generic runtime error

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        results = []
        for i, text in enumerate(texts):
            try:
                embedding = self._embed(text)
                results.append(embedding)
            except Exception as e:
                # Log the error and append a zero vector, or re-raise?
                # Re-raising might stop a large indexing job, using zero vectors might pollute results.
                # For RAG, embed_query failure is more critical.
                print(f"Warning: Failed to embed document index {i}, using zero vector. Error: {e}. Text: {text[:100]}...")
                results.append([0.0] * self.expected_dimension)
        return results

    def embed_query(self, text: str) -> list[float]:
        print(f"Embedding query via API: '{text[:100]}...'")
        # _embed now raises exceptions on failure
        return self._embed(text)

# --- Helper to Fetch Document Details (Adapted from chatbot.py) ---
# Make function synchronous as Supabase client is sync
def get_document_details_api(supabase_client: SupabaseClient, documents_table: str, document_ids: list):
    if not document_ids:
        return {}
    try:
        # Remove await, use synchronous execute()
        doc_response = supabase_client.table(documents_table)\
                               .select("id, original_filename, public_url, title, author, last_modified, created_date, file_type, document_summary, law_area, document_category, cleaned_filename, analysis_notes")\
                               .in_('id', document_ids)\
                               .execute()
        if doc_response.data:
            return {doc['id'] : doc for doc in doc_response.data}
        else:
            print("Warning: API could not fetch details for parent documents.")
            return {}
    except Exception as e:
        print(f"Error in API fetching document details: {e}")
        return {}


# --- FastAPI Lifespan Management (Initialize RAG components) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global global_rag_chain, global_supabase_client, global_config
    print("RAG API Service starting up...")

    # 1. Load Configuration
    global_config = {
        "supabase_url": os.getenv("SUPABASE_URL"),
        "supabase_key": os.getenv("SUPABASE_SERVICE_ROLE_KEY"), # Use service key
        "documents_table": os.getenv("SUPABASE_DOCUMENTS_TABLE", "documents"),
        "chunks_table": os.getenv("SUPABASE_CHUNKS_TABLE", "document_chunks"),
        "embedding_service_url": os.getenv("EMBEDDING_SERVICE_URL"),
        "pgvector_dimension": int(os.getenv("PGVECTOR_DIMENSION", 1024)),
        # LLM Provider Configuration
        "llm_provider": os.getenv("LLM_PROVIDER", "ollama").lower(), # Default to ollama
        "ollama_model": os.getenv("OLLAMA_MODEL", "phi3:mini"),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_model_name": os.getenv("OPENAI_MODEL_NAME", "gpt-4"),
        "db_pass": os.getenv('SUPABASE_DB_PASSWORD'),
        # Removed db_host as they are not needed for SupabaseVectorStore
    }
    # Updated check to remove db_pass/db_host
    if not all([global_config["supabase_url"], global_config["supabase_key"], 
                global_config["embedding_service_url"]]):
        print("Error: Critical configurations (Supabase URL/Key, Embedding URL) missing.")
        raise RuntimeError("Critical configurations missing.")

    print(f"Selected LLM Provider: {global_config['llm_provider']}")

    # Initialize Supabase client 
    try:
        global_supabase_client = create_client(global_config["supabase_url"], global_config["supabase_key"])
        print("Supabase client initialized.")
    except Exception as e:
        print(f"FATAL: Failed to initialize Supabase client: {e}")
        raise RuntimeError(f"Could not initialize Supabase client: {e}") from e

    # 2. Initialize RAG Components
    try:
        print("Initializing RAG components...")
        embeddings = ApiEmbeddings(global_config["embedding_service_url"], global_config["pgvector_dimension"])
        print("Custom embeddings handler initialized.")

        # Initialize SupabaseVectorStore
        vectorstore = SupabaseVectorStore(
            client=global_supabase_client,
            embedding=embeddings,
            table_name=global_config["chunks_table"],
            query_name="match_chunks_for_rag", # This query name isn't strictly needed by the manual RPC call below, but keep for consistency
        )
        print("SupabaseVectorStore interface initialized using 'match_chunks_for_rag'.")

        retriever = vectorstore.as_retriever(search_kwargs={'k': 5})
        print("Retriever initialized.")

        # Initialize LLM based on provider
        llm = None
        if global_config["llm_provider"] == "ollama":
            try:
                llm = ChatOllama(
                    model=global_config['ollama_model'],
                    base_url=global_config['ollama_base_url'] # Ensure this is used
                )
                print(f"Checking Ollama model ({global_config['ollama_model']}) availability...")
                llm.invoke("Hi") # Simple test invoke
                print(f"Ollama model ({global_config['ollama_model']}) initialized and appears reachable.")
            except Exception as e:
                print(f"FATAL: Failed to initialize or connect to Ollama model '{global_config['ollama_model']}': {e}")
                raise RuntimeError(f"Ollama connection failed: {e}") from e
        elif global_config["llm_provider"] == "openai":
            if not global_config["openai_api_key"]:
                print("FATAL: LLM_PROVIDER is 'openai' but OPENAI_API_KEY is not set.")
                raise RuntimeError("OPENAI_API_KEY is required for OpenAI LLM.")
            try:
                llm = ChatOpenAI(
                    openai_api_key=global_config["openai_api_key"],
                    model_name=global_config["openai_model_name"]
                )
                print(f"Checking OpenAI model ({global_config['openai_model_name']}) availability...")
                llm.invoke("Hi") # Simple test invoke
                print(f"OpenAI model ({global_config['openai_model_name']}) initialized and appears reachable.")
            except Exception as e:
                print(f"FATAL: Failed to initialize or connect to OpenAI model '{global_config['openai_model_name']}': {e}")
                raise RuntimeError(f"OpenAI connection failed: {e}") from e
        else:
            print(f"FATAL: Unsupported LLM_PROVIDER: {global_config['llm_provider']}. Supported: ollama, openai")
            raise RuntimeError(f"Unsupported LLM_PROVIDER: {global_config['llm_provider']}")
        
        if llm is None: # Should be caught by earlier raises, but as a safeguard
            raise RuntimeError("LLM could not be initialized.")

        # RAG Prompt (Adapted from chatbot.py)
        system_prompt_text = """You are an intelligent research assistant focused on Australia. 
Provide clear and accurate answers to the questions you are asked. 
Your answers should be derived *only* from the provided context. 
When answering, prioritize and synthesize information specifically relevant to Australia, even if the context mentions other locations.
If the context contains no information relevant to Australia that can answer the question, state that.
"""
        human_template_text = """Context:
{context}

Based on the context above, answer the following question, focusing only on aspects relevant to Australia:
Question: {question}
Answer:"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt_text),
            ("human", human_template_text)
        ])
        print("RAG prompt template created with system message and Australia focus.")

        # --- Custom Retrieval and Chain Definition ---
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        # Function to perform manual retrieval via RPC
        def retrieve_documents(query_input: dict) -> list[Document]: # Takes a dict now to get query and limit
            query = query_input["query"]
            # Get limit from query_input if provided, else use a default from config or hardcoded
            # For now, let's assume the RAG chain itself might not pass a limit directly through RunnablePassthrough() this way
            # So, we might use a default. Or, if using for /search, it would be passed.
            # Let's use a default for now, can be refined.
            retrieval_limit = query_input.get("limit", global_config.get("search_limit_rag_default", 5))

            print(f"Manually retrieving top {retrieval_limit} documents via RPC for query: '{query[:50]}...'")
            if not global_supabase_client:
                 print("ERROR: Supabase client not available for retrieval.")
                 return [] # Or raise an error
            try:
                # 1. Embed the query using our custom class
                query_embedding = embeddings.embed_query(query)

                # 2. Call the RPC function directly
                rpc_params = {
                    'query_embedding': query_embedding,
                    'match_count': retrieval_limit # Pass the limit to the SQL function
                }
                match_response = global_supabase_client.rpc(
                    'match_chunks_for_rag',
                    rpc_params
                ).execute()

                retrieved_docs = []
                if match_response.data:
                    print(f"RPC call returned {len(match_response.data)} chunks.")
                    # 3. Manually construct LangChain Document objects with metadata
                    for row in match_response.data:
                        metadata = {
                            'id': row.get('id'), # Chunk ID
                            'document_id': row.get('document_id'), # PARENT DOCUMENT ID
                            'chunk_index': row.get('chunk_index'),
                            'similarity': row.get('similarity')
                        }
                        # Filter out None values from metadata before creating Document
                        filtered_metadata = {k: v for k, v in metadata.items() if v is not None}
                        doc = Document(
                            page_content=row.get('content', ''), 
                            metadata=filtered_metadata
                        )
                        retrieved_docs.append(doc)
                else:
                     print("RPC call returned no matching chunks.")
                     if hasattr(match_response, 'error') and match_response.error:
                          print(f"Supabase RPC error during retrieval: {match_response.error}")
                
                return retrieved_docs

            except Exception as e:
                print(f"Error during manual retrieval process: {e}")
                import traceback
                traceback.print_exc()
                return [] # Return empty list on error

        # Define the chain using the manual retrieval function
        rag_processing = RunnableParallel(
            # Pass the raw question dict to retrieve_documents, then format the result
            context=(RunnablePassthrough() | retrieve_documents | format_docs),
            question=RunnablePassthrough(lambda x: x["query"]), # Extract query string for prompt
            # Pass the raw question dict to retrieve_documents again to get the source Document objects
            source_documents=(RunnablePassthrough() | retrieve_documents)
        )

        global_rag_chain = (
             rag_processing
             # Pass source_documents through again
             | {"answer": prompt | llm | StrOutputParser(), "source_documents": (lambda x: x["source_documents"])} 
        )
        print("RAG components initialized and chain created with manual retrieval.")

    except Exception as e:
        print(f"FATAL: Error during RAG API service initialization: {e}")
        import traceback
        traceback.print_exc() # Print full stack trace for init errors
        global_rag_chain = None 
        # Raise error to potentially stop service startup if init fails badly
        raise RuntimeError(f"RAG component initialization failed: {e}") from e

    yield # FastAPI app runs after this

    print("RAG API Service shutting down...")
    # Cleanup if needed (e.g., close db connections if not handled by SQLAlchemy engine)


# --- FastAPI App Instance ---
app = FastAPI(lifespan=lifespan)

# --- Add CORS Middleware ---
# Define allowed origins (your frontend URL)
# For development, allowing localhost with common Vite/SvelteKit ports is typical.
# For production, be more specific.
origins = [
    "http://localhost:5173", # Default SvelteKit/Vite dev port
    "http://127.0.0.1:5173",
    # Add other origins if needed, e.g., your deployed frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # List of origins that are allowed to make requests
    allow_credentials=True, # Allows cookies to be included in requests (not strictly needed for this API yet)
    allow_methods=["GET", "POST", "OPTIONS"], # Allow specific HTTP methods (OPTIONS is crucial for preflight)
    allow_headers=["Content-Type", "Authorization"], # Allow specific headers (Content-Type is needed for our JSON body)
)


# --- API Endpoints ---
@app.post("/chat", response_model=ChatQueryResponse)
async def chat_endpoint(request: ChatQueryRequest):
    if not global_rag_chain:
        raise HTTPException(status_code=503, detail="RAG service not initialized. Please check server logs.")
    
    print(f"Received query for RAG API: {request.query[:100]}... Retrieval Limit: {request.limit}")
    try:
        # Chain now returns dict including source_documents with proper metadata
        result = global_rag_chain.invoke({"query": request.query, "limit": request.limit})
        answer_str = result.get("answer") 
        source_docs_lc = result.get("source_documents") # LangChain Document objects

        if answer_str is None:
            print("Error: RAG chain did not return an 'answer'.")
            raise HTTPException(status_code=500, detail="Failed to get answer from RAG chain.")

        # --- Restore Source Processing Logic --- 
        sources_api = [] 
        if source_docs_lc:
            # Debug: Check the metadata again now that we construct Documents manually
            print(f"DEBUG (Post-Manual): Metadata of first source doc: {source_docs_lc[0].metadata}")
            
            # Fetch original filenames for better source display
            # Extract valid document IDs from metadata
            source_doc_ids = list(set([doc.metadata.get('document_id') for doc in source_docs_lc if doc.metadata.get('document_id') is not None]))
            
            if source_doc_ids:
                if global_supabase_client:
                    # Use the async helper function for non-blocking IO
                    document_details = get_document_details_api(
                        global_supabase_client,
                        global_config["documents_table"],
                        source_doc_ids
                    )
                else:
                    print("Warning: Supabase client not available to fetch source details.")
                    document_details = {}
            else:
                 document_details = {}

            # Create unique list of sources for API response
            unique_sources_dict = {}
            for doc_lc in source_docs_lc:
                doc_id = doc_lc.metadata.get('document_id')
                original_filename = "Unknown"
                public_url_val = None
                title_val = None
                author_val = None
                last_modified_val = None
                created_date_val = None
                file_type_val = None
                document_summary_val = None
                law_area_val = None
                document_category_val = None
                cleaned_filename_val = None
                analysis_notes_val = None

                if doc_id and doc_id in document_details:
                    doc_data = document_details[doc_id]
                    original_filename = doc_data.get('original_filename', f"ID {doc_id}")
                    public_url_val = doc_data.get('public_url')
                    title_val = doc_data.get('title')
                    author_val = doc_data.get('author')
                    last_modified_val = doc_data.get('last_modified')
                    created_date_val = doc_data.get('created_date')
                    file_type_val = doc_data.get('file_type')
                    document_summary_val = doc_data.get('document_summary')
                    law_area_val = doc_data.get('law_area')
                    document_category_val = doc_data.get('document_category')
                    cleaned_filename_val = doc_data.get('cleaned_filename')
                    analysis_notes_val = doc_data.get('analysis_notes')
                
                sources_api.append(SourceDocument(
                    id=str(doc_id) if doc_id else "N/A", 
                    original_filename=original_filename,
                    public_url=public_url_val,
                    title=title_val,
                    author=author_val,
                    last_modified=last_modified_val,
                    created_date=created_date_val,
                    file_type=file_type_val,
                    document_summary=document_summary_val,
                    law_area=law_area_val,
                    document_category=document_category_val,
                    cleaned_filename=cleaned_filename_val,
                    analysis_notes=analysis_notes_val
                ))
        # --- End Restore Source Processing Logic --- 
        
        return ChatQueryResponse(answer=answer_str, sources=sources_api) 

    except ConnectionError as ce:
        # Specific error from embedding service connection failure
        print(f"ConnectionError during RAG chain invocation: {ce}")
        raise HTTPException(status_code=503, detail=f"Could not connect to embedding service: {ce}")
    except ValueError as ve:
        # Specific error from embedding service returning bad data or query embed failure
        print(f"ValueError during RAG chain invocation: {ve}")
        raise HTTPException(status_code=500, detail=f"Error processing embedding: {ve}")
    except Exception as e:
        # Catch-all for other potential errors (retrieval, LLM call, etc.)
        print(f"Unexpected error processing chat query in API: {e}")
        import traceback
        traceback.print_exc() # Log full traceback for unexpected errors
        # Check if error message indicates Ollama connection issue
        if "connection refused" in str(e).lower() or "ollama" in str(e).lower():
             raise HTTPException(status_code=503, detail=f"Could not connect to Ollama LLM service: {e}")
        else:
             raise HTTPException(status_code=500, detail=f"Error processing your request.") # Avoid leaking details

@app.get("/health")
async def health_check():
    return {"status": "RAG API Service is running", "rag_initialized": global_rag_chain is not None}

@app.get("/preview-pdf")
async def preview_pdf_endpoint(url: str): # url will be the Supabase public_url
    if not url:
        raise HTTPException(status_code=400, detail="Missing PDF URL")
    
    print(f"Proxying PDF from URL: {url}")
    try:
        # Make the request to the external URL
        # Using a timeout for robustness
        pdf_response = requests.get(url, timeout=30, stream=True) # stream=True is good practice
        pdf_response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        # For simplicity, load content into BytesIO. For very large files, 
        # a true async generator with StreamingResponse would be more memory efficient.
        pdf_content_stream = io.BytesIO(pdf_response.content)
        
        # Ensure headers are correctly set for inline display
        response_headers = {
            "Content-Disposition": "inline",
            "Content-Type": "application/pdf" # Explicitly set Content-Type
        }
        
        return StreamingResponse(pdf_content_stream, headers=response_headers, media_type="application/pdf")

    except requests.exceptions.Timeout:
        print(f"Timeout when fetching PDF from URL ({url})")
        raise HTTPException(status_code=504, detail="Timeout when fetching PDF from source.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PDF from URL ({url}): {e}")
        # Check if the error response from Supabase was JSON (e.g., for 404s with details)
        try:
            error_detail = e.response.json() if e.response else str(e)
        except ValueError: # If response is not JSON
            error_detail = str(e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch PDF from source: {error_detail}")
    except Exception as e:
        print(f"Unexpected error proxying PDF ({url}): {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error processing PDF preview")

@app.post("/search", response_model=SearchQueryResponse)
async def search_endpoint(request: ChatQueryRequest): # Uses limit from request
    print(f"Received query for Search API: {request.query[:100]}... Limit: {request.limit}")
    
    retrieved_docs_lc = []
    try:
        # 1. Embed the query using our custom class
        embeddings = ApiEmbeddings(global_config["embedding_service_url"], global_config["pgvector_dimension"])
        query_embedding = embeddings.embed_query(request.query)

        # 2. Call the RPC function directly
        rpc_params = {
            'query_embedding': query_embedding,
            'match_count': request.limit # Use limit from request
        }
        if not global_supabase_client:
             raise RuntimeError("Supabase client not initialized for search endpoint.")

        match_response = global_supabase_client.rpc(
            'match_chunks_for_rag', # This function returns doc_id, content, similarity etc.
            rpc_params
        ).execute()

        if match_response.data:
            print(f"Search RPC call returned {len(match_response.data)} chunks.")
            # Manually construct LangChain Document objects to extract metadata easily
            for row in match_response.data:
                metadata = {
                    'id': row.get('id'), # Chunk ID
                    'document_id': row.get('document_id'),
                    'chunk_index': row.get('chunk_index'),
                    'similarity': row.get('similarity')
                }
                filtered_metadata = {k: v for k, v in metadata.items() if v is not None}
                doc = Document( # Need to import Document from langchain_core.documents
                    page_content=row.get('content', ''), 
                    metadata=filtered_metadata
                )
                retrieved_docs_lc.append(doc)
        else:
             print("Search RPC call returned no matching chunks.")
             if hasattr(match_response, 'error') and match_response.error:
                  print(f"Supabase RPC error during search: {match_response.error}")

    except ValueError as ve: # Catch specific error from embed_query
        print(f"ValueError during Search API query embedding: {ve}")
        return SearchQueryResponse(query=request.query, results=[], error=str(ve))
    except ConnectionError as ce:
        print(f"ConnectionError during Search API query embedding: {ce}")
        return SearchQueryResponse(query=request.query, results=[], error=f"Could not connect to embedding service: {ce}")
    except Exception as e:
        print(f"Error processing search query in API: {e}")
        import traceback
        traceback.print_exc()
        return SearchQueryResponse(query=request.query, results=[], error=f"Error processing your request: {e}")

    search_results_api = []
    if retrieved_docs_lc:
        source_doc_ids = list(set([doc.metadata.get('document_id') for doc in retrieved_docs_lc if doc.metadata.get('document_id') is not None]))
        document_details = {}
        if source_doc_ids and global_supabase_client:
            document_details = get_document_details_api(
                global_supabase_client,
                global_config["documents_table"],
                source_doc_ids
            )
        
        unique_sources_dict = {}
        for doc_lc in retrieved_docs_lc: # doc_lc is a LangChain Document object for a chunk
            doc_id = doc_lc.metadata.get('document_id')
            similarity = doc_lc.metadata.get('similarity', 0.0)
            chunk_content = doc_lc.page_content
            chunk_idx = doc_lc.metadata.get('chunk_index')

            if doc_id:
                if doc_id not in unique_sources_dict:
                    doc_info = document_details.get(doc_id, {
                        'original_filename': f'Unknown ID {doc_id}',
                        # Initialize all other fields to None or sensible defaults
                        'public_url': None, 'title': None, 'author': None, 
                        'last_modified': None, 'created_date': None, 'file_type': None,
                        'document_summary': None, 'law_area': None, 'document_category': None,
                        'cleaned_filename': None, 'analysis_notes': None
                    })
                    unique_sources_dict[doc_id] = {
                        "id": str(doc_id),
                        "original_filename": doc_info.get('original_filename', f'Document ID {doc_id}'),
                        "public_url": doc_info.get('public_url'),
                        "title": doc_info.get('title'),
                        "author": doc_info.get('author'),
                        "last_modified": doc_info.get('last_modified'),
                        "created_date": doc_info.get('created_date'),
                        "file_type": doc_info.get('file_type'),
                        "document_summary": doc_info.get('document_summary'),
                        "law_area": doc_info.get('law_area'),
                        "document_category": doc_info.get('document_category'),
                        "cleaned_filename": doc_info.get('cleaned_filename'),
                        "analysis_notes": doc_info.get('analysis_notes'),
                        "max_similarity": 0.0, # Initialize max_similarity
                        "snippets": [] # Initialize list for snippets
                    }
                
                # Add snippet to this document's list
                unique_sources_dict[doc_id]["snippets"].append(
                    ChunkSnippet(content=chunk_content, similarity=similarity, chunk_index=chunk_idx)
                )
                # Update max_similarity for the document
                if similarity > unique_sources_dict[doc_id]["max_similarity"]:
                    unique_sources_dict[doc_id]["max_similarity"] = similarity
        
        # Convert to list and sort by max_similarity if desired
        sorted_sources_data = sorted(unique_sources_dict.values(), key=lambda x: x["max_similarity"], reverse=True)
        
        search_results_api = []
        for source_data in sorted_sources_data:
            # Sort snippets within each document by similarity, highest first
            sorted_snippets = sorted(source_data["snippets"], key=lambda s: s.similarity, reverse=True)
            search_results_api.append(SourceDocument(
                id=source_data["id"], 
                original_filename=source_data["original_filename"],
                public_url=source_data["public_url"],
                title=source_data["title"],
                author=source_data["author"],
                last_modified=source_data["last_modified"],
                created_date=source_data["created_date"],
                file_type=source_data["file_type"],
                document_summary=source_data["document_summary"],
                law_area=source_data["law_area"],
                document_category=source_data["document_category"],
                cleaned_filename=source_data["cleaned_filename"],
                analysis_notes=source_data["analysis_notes"],
                snippets=sorted_snippets # Add sorted snippets
            ))
    
    return SearchQueryResponse(query=request.query, results=search_results_api)

@app.post("/log-activity")
async def log_activity_endpoint(log_entry: LogEntryRequest):
    if not global_supabase_client:
        print("ERROR (log-activity): Supabase client not available.")
        # Don't crash the calling function, just log error and return success-ish
        # Or raise HTTPException(status_code=503, detail="Logging service temporarily unavailable")
        return {"status": "logging_error", "detail": "Supabase client unavailable"}

    print(f"Logging activity: {log_entry.event_type}, User: {log_entry.username or log_entry.user_id or 'Anonymous'}")
    try:
        log_data = {
            "user_id": log_entry.user_id,
            "username": log_entry.username,
            "event_type": log_entry.event_type,
            "search_term": log_entry.search_term,
            "document_id": str(log_entry.document_id) if log_entry.document_id is not None else None,
            "document_filename": log_entry.document_filename,
            "preview_type": log_entry.preview_type,
            "details": log_entry.details or {}
        }
        # Filter out None values before inserting
        log_data_to_insert = {k: v for k, v in log_data.items() if v is not None}

        response = global_supabase_client.table("activity_logs").insert(log_data_to_insert).execute()
        
        # For supabase-python v1.x and v2.x, .execute() on insert usually returns an APIResponse object.
        # Successful inserts often have data in response.data (list of inserted records).
        # Errors would be in response.error or an exception might be raised by .execute() itself on failure.

        if hasattr(response, 'error') and response.error:
            print(f"Error logging activity to Supabase: {response.error}")
            return {"status": "logging_error", "detail": str(response.error)}
        elif response.data: 
            log_id = response.data[0].get('id') if response.data and len(response.data)>0 else 'N/A'
            print(f"Activity logged successfully: ID {log_id}")
            return {"status": "success", "log_id": log_id }
        else:
            # This case might indicate success but no data returned, or an unhandled error prior to execute raising one.
            print("Activity logging to Supabase: insert executed, no data in response and no explicit error attribute.")
            return {"status": "success_no_data_or_unclear_error"}

    except Exception as e:
        print(f"Exception during logging activity: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise HTTPException here to avoid breaking client flow for logging failure
        return {"status": "logging_exception", "detail": str(e)}

# --- Main Block (for running with uvicorn if desired, e.g., python main.py) ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("RAG_API_PORT", 8002)) # Reads from .env
    host = "0.0.0.0" # Essential for Docker
    print(f"Starting Uvicorn server on {host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=False) # reload=False for prod
            