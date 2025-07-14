# RAG API Service Overview

## Purpose
The RAG API Service is a FastAPI-based microservice that provides endpoints for semantic search, RAG-based chat queries, PDF previews, and activity logging. It integrates with Supabase for vector storage and retrieval, an embedding service for vector generation, and an LLM (Ollama or OpenAI) for generating responses. The service handles authentication via Azure AD JWT tokens and is designed for a knowledge base search application focused on Australian legal contexts.

## Key Components
The service consists of the following main files:

- **main.py**: The core application script that sets up the FastAPI app, initializes RAG components (embeddings, vector store, retriever, LLM, prompt, and chain), and defines API endpoints.
- **security.py**: Handles JWT token validation for Azure AD, including fetching JWKS and verifying signatures, issuers, and audiences.
- **Dockerfile**: Defines the Docker image based on Python 3.11-slim, installs dependencies, and runs `python main.py`.
- **Procfile**: Specifies the command for deployment (e.g., Heroku): `web: uvicorn main:app --host 0.0.0.0 --port $PORT`.
- **requirements.txt**: Lists dependencies including FastAPI, Uvicorn, python-dotenv, requests, Supabase, LangChain (core, community, Ollama, OpenAI), and python-jose for JWT handling.

## Configuration
- **Environment Variables**:
  - Supabase: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DOCUMENTS_TABLE` (default: "documents"), `SUPABASE_CHUNKS_TABLE` (default: "document_chunks"), `PGVECTOR_DIMENSION` (default: 1024).
  - Embedding: `EMBEDDING_SERVICE_URL`.
  - LLM: `LLM_PROVIDER` ("ollama" or "openai"), `OLLAMA_MODEL` (default: "phi3:mini"), `OLLAMA_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL_NAME` (default: "gpt-4").
  - Auth: `TENANT_ID`, `CLIENT_ID`, `API_SCOPE` (with fallbacks to VITE_ prefixes for local dev).
  - Port: `RAG_API_PORT` (default: 8002).
- Variables are loaded from environment (e.g., Doppler or .env).

## How It Works
1. **Startup and Initialization**:
   - Uses FastAPI's lifespan to load config, initialize Supabase client, custom embeddings (API wrapper), SupabaseVectorStore, retriever, LLM (Ollama or OpenAI with availability check), prompt template (with Australia focus), and RAG chain.
   - The chain uses manual RPC calls to Supabase for retrieval to handle custom logic.
   - Adds CORS middleware for frontend integration.

2. **Authentication**:
   - All endpoints (except /health) depend on `verify_token`, which decodes/validates JWTs using python-jose.
   - Supports v1/v2 issuers, multiple audiences (API URI, client ID, MS Graph).
   - Fetches JWKS dynamically with caching.

3. **API Endpoints**:
   - **POST /search**: Embeds query, retrieves chunks via Supabase RPC, fetches document details, returns results with snippets sorted by similarity.
   - **POST /chat**: Similar to /search but invokes RAG chain with LLM to generate an answer, includes sources.
   - **GET /preview-pdf?url=...**: Proxies PDF from Supabase URL with auth, streams as inline PDF.
   - **POST /log-activity**: Logs user activities (e.g., login, search) to Supabase.
   - **GET /health**: Checks service status and RAG initialization.

4. **RAG Process**:
   - Embeds query via external service.
   - Retrieves chunks using custom RPC (`match_chunks_for_rag`).
   - Formats context, invokes LLM with prompt focusing on Australian relevance.
   - Enriches sources with document metadata from Supabase.

5. **Running the Service**:
   - Locally: `python main.py` (Uvicorn on 0.0.0.0:8002).
   - In Docker: Built via Dockerfile, runs `python main.py`.
   - In production: Uses Procfile for Uvicorn on dynamic port.

6. **Shutdown**:
   - Lifespan prints shutdown message; no explicit cleanup needed.

## Dependencies
- **FastAPI & Uvicorn**: Web framework and server.
- **LangChain**: For embeddings, vector store, LLM integration, prompts, and chains.
- **Supabase**: Client for database and vector operations.
- **python-jose**: JWT validation.
- **Requests**: For embedding API and PDF proxy.

## Potential Improvements
- Add batch search/chat support.
- Implement caching for embeddings/retrievals.
- Enhance error handling with retries.
- Add pagination for large result sets.
- Integrate more LLM providers.

This service acts as the backend for the search UI, handling authenticated queries and integrating with storage/embedding/LLM components. 