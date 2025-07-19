# AI Architecture Summary: Knowledge Base Search & RAG API

## Overview

This application implements a sophisticated AI-powered knowledge base search system using the Retrieval-Augmented Generation (RAG) pattern. It combines semantic embeddings, vector similarity search, and large language models to provide intelligent document search and question-answering capabilities, with a specific focus on Australian legal contexts.

**Important Note**: This project focuses on the **search and retrieval** aspects of a knowledge base system. It operates on documents and text chunks that are already processed and stored in the database. Document upload, text extraction, and content processing functionality is implemented in a separate, related project.

## AI Architecture Components

### 1. Embedding Service (`embedding_service/`)

**Purpose**: Converts text into high-dimensional vector representations for semantic similarity search.

**Key Technologies**:
- **Model**: BAAI/bge-large-en-v1.5 (default)
  - A state-of-the-art sentence transformer model
  - Produces 1024-dimensional embeddings
  - Optimized for English text semantic understanding
- **Framework**: Sentence Transformers library
- **Hardware Support**: CPU, CUDA (NVIDIA GPUs), MPS (Apple Silicon)
- **Infrastructure**: FastAPI microservice architecture

**Implementation Details**:
```python
# Model Configuration
MODEL_NAME = "BAAI/bge-large-en-v1.5"  # 1024-dimensional embeddings
DEVICE = "cpu"  # Fallback to CPU if GPU unavailable

# Core functionality
model = SentenceTransformer(MODEL_NAME, device=DEVICE)
embedding = model.encode(text, convert_to_tensor=False).tolist()
```

**API Endpoints**:
- `POST /embed`: Generate embedding for input text
- `GET /`: Health check with model status

**Features**:
- Automatic device detection and fallback
- Warmup functionality for MPS devices
- Error handling and validation
- Containerized deployment

### 2. Large Language Model Integration (Ollama)

**Purpose**: Provides the generative AI capabilities for the RAG system to synthesize answers from retrieved context.

**Ollama Configuration**:
- **Default Model**: phi3:mini
  - Lightweight yet capable model suitable for resource-constrained environments
  - Good balance of performance and efficiency
- **Container**: Official Ollama Docker image
- **API Endpoint**: http://ollama:11434
- **Health Monitoring**: Built-in healthcheck with connection verification

**LLM Provider Flexibility**:
The system supports two LLM providers:

1. **Ollama (Default)**:
   ```python
   llm = ChatOllama(
       model="phi3:mini",
       base_url="http://ollama:11434"
   )
   ```

2. **OpenAI (Alternative)**:
   ```python
   llm = ChatOpenAI(
       api_key=openai_api_key,
       model="gpt-4"
   )
   ```

**Model Management**:
- Automatic model downloading on first startup
- Persistent model storage via Docker volumes
- GPU support configuration available (NVIDIA)

### 3. RAG (Retrieval-Augmented Generation) Implementation

**Purpose**: Combines document retrieval with language generation to provide accurate, context-aware answers.

**LangChain Integration**:
The system uses LangChain for orchestrating the RAG pipeline:

```python
# Core LangChain components
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_ollama.chat_models import ChatOllama
from langchain_community.vectorstores import SupabaseVectorStore
```

**RAG Pipeline Architecture**:

1. **Query Processing**:
   - User query → Embedding Service → Query vector

2. **Document Retrieval**:
   - Vector similarity search in Supabase pgvector
   - Custom RPC function: `match_chunks_for_rag`
   - Configurable result limits (default: 5 chunks)

3. **Context Assembly**:
   - Retrieved document chunks formatted as context
   - Document metadata enrichment

4. **Answer Generation**:
   - LLM processes query + context through specialized prompt
   - Focus on Australian legal relevance
   - Source attribution and citation

**Custom RAG Chain**:
```python
rag_processing = RunnableParallel(
    context=(RunnablePassthrough() | retrieve_documents | format_docs),
    question=RunnablePassthrough(lambda x: x["query"]),
    source_documents=(RunnablePassthrough() | retrieve_documents)
)

global_rag_chain = (
    rag_processing
    | {"answer": prompt | llm | StrOutputParser(), "source_documents": lambda x: x["source_documents"]}
)
```

**Specialized Prompt Engineering**:
```python
system_prompt = """You are an intelligent research assistant focused on Australia. 
Provide clear and accurate answers to the questions you are asked. 
Your answers should be derived *only* from the provided context. 
When answering, prioritize and synthesize information specifically relevant to Australia, 
even if the context mentions other locations."""
```

### 4. Advanced Search Capabilities

**Multi-Modal Search System**:
The application implements three complementary search approaches:

#### Vector Search
- **Method**: Semantic similarity using embeddings
- **Use Case**: Conceptual and meaning-based queries
- **Implementation**: Direct embedding comparison with pgvector

#### Keyword Search
- **Method**: Full-text search with PostgreSQL
- **Use Case**: Exact term matching and traditional search
- **Implementation**: Supabase RPC function `search_documents_keyword`

#### Hybrid Search
- **Method**: Combines vector and keyword approaches using Reciprocal Rank Fusion (RRF)
- **Configurable Weights**: Vector (0.7) + Keyword (0.3) by default
- **Implementation**: Advanced scoring algorithm balancing semantic and lexical relevance

```python
# Hybrid search configuration
class EnhancedSearchRequest(BaseModel):
    mode: str = "vector"  # "vector", "keyword", or "hybrid"
    vector_weight: float = 0.7
    keyword_weight: float = 0.3
    rrf_k: int = 60  # RRF constant for rank fusion
```

### 5. Vector Storage and Database Integration

**Supabase + pgvector**:
- **Database**: PostgreSQL with pgvector extension
- **Vector Dimensions**: 1024 (matching embedding model)
- **Tables**: 
  - `documents`: Document metadata (populated by separate ingestion system)
  - `document_chunks`: Text chunks with embeddings (populated by separate ingestion system)
- **Custom Functions**: 
  - `match_chunks_for_rag`: Vector similarity search
  - `search_documents_hybrid`: Combined search approach

**Data Model**:
The system operates on pre-processed data with the following structure:
- Documents have metadata including titles, authors, law areas, categories
- Text chunks contain content with associated embeddings and similarity scores
- Document relationships and metadata are maintained for source attribution

### 6. Custom Embedding Integration

**API-Based Embedding Class**:
The system implements a custom LangChain-compatible embedding class:

```python
class ApiEmbeddings(Embeddings):
    def __init__(self, api_url: str, expected_dimension: int):
        self.api_url = f"{api_url.rstrip('/')}/embed"
        self.expected_dimension = expected_dimension
    
    def embed_query(self, text: str) -> list[float]:
        # Calls external embedding service
        response = requests.post(self.api_url, json={"text": text})
        return response.json()['embedding']
```

**Benefits**:
- Microservice isolation for embedding logic
- Independent scaling and deployment
- Model flexibility without affecting RAG service
- Error handling and retry logic

### 7. AI-Powered Search Features

**Search Enhancement**:
- Query expansion and interpretation through semantic embedding
- Context-aware result ranking with multiple similarity factors
- Relevance scoring combining vector and keyword approaches
- Source document attribution with snippet highlighting

**User Experience**:
- Real-time semantic search with immediate results
- Result snippet generation with similarity scores
- PDF preview integration with contextual access
- Activity logging for search analytics and usage patterns

**Document Metadata Integration**:
The system leverages rich document metadata for enhanced search results:
- Document titles, authors, and publication dates
- Law area classifications and document categories
- File type information and original filenames
- Analysis notes and document summaries (when available)

## Performance and Scalability

**Resource Optimization**:
- CPU-optimized embedding model deployment
- Efficient vector storage with pgvector indexing
- Configurable batch processing for search results
- Memory-efficient text chunking and retrieval

**Error Handling and Reliability**:
- Graceful degradation on service failures
- Comprehensive error logging and monitoring
- Health checks for all AI services
- Timeout handling for external API calls

**Monitoring and Observability**:
- Detailed logging for embedding generation
- RAG chain execution tracking
- Search performance metrics
- User activity analytics

## Configuration and Deployment

**Environment Variables**:
```bash
# Embedding Configuration
EMBEDDING_MODEL_NAME=BAAI/bge-large-en-v1.5
EMBEDDING_MODEL_DEVICE=cpu
PGVECTOR_DIMENSION=1024

# LLM Configuration
LLM_PROVIDER=ollama
OLLAMA_MODEL=phi3:mini
OLLAMA_BASE_URL=http://ollama:11434

# Alternative OpenAI Configuration
OPENAI_API_KEY=your_key_here
OPENAI_MODEL_NAME=gpt-4
```

**Docker Compose Architecture**:
- Isolated services for embedding, RAG, and LLM
- Shared network for inter-service communication
- Persistent volumes for model storage
- Health check dependencies

## Security and Authentication

**AI Service Security**:
- JWT-based authentication for all endpoints
- Azure AD integration for user verification
- Service-to-service authentication
- API rate limiting and abuse prevention

**Data Privacy**:
- User context isolation
- Audit trails for AI interactions
- Secure embedding storage
- Document access controls

## Integration Points

**External Dependencies**:
This project integrates with:
- **Document Ingestion System** (separate project): Provides processed documents and embeddings
- **Supabase**: Vector storage and document metadata
- **Azure AD**: User authentication and authorization
- **Frontend Application**: SvelteKit-based search interface

**API Endpoints**:
- `POST /search`: Multi-modal search with vector, keyword, and hybrid options
- `POST /chat`: RAG-based question answering with source attribution
- `GET /preview-pdf`: Secure PDF document preview
- `POST /log-activity`: User activity tracking
- `GET /health`: Service health monitoring

## Future Enhancement Opportunities

**Model Improvements**:
- Support for domain-specific embedding models
- Multi-language embedding capabilities
- Fine-tuned models for legal document understanding
- Model versioning and A/B testing

**Performance Optimizations**:
- GPU acceleration for embedding generation
- Embedding caching strategies
- Advanced vector index optimization
- Parallel search processing

**Advanced AI Features**:
- Query suggestion and auto-completion
- Conversation history and context retention
- Advanced result reranking algorithms
- Multi-turn conversation support

## Conclusion

This application represents a sophisticated implementation of modern AI technologies for knowledge base search and retrieval. The microservice architecture provides flexibility and scalability, while the combination of semantic search, traditional keyword matching, and language generation creates a powerful tool for intelligent document exploration. The specific focus on Australian legal contexts, combined with robust error handling and authentication, makes it suitable for professional knowledge work environments.

The use of open-source models (via Ollama) alongside commercial alternatives (OpenAI) provides flexibility in deployment scenarios, while the custom embedding service allows for future model upgrades without disrupting the broader system architecture. The clear separation between document ingestion (handled by a separate system) and search/retrieval (this project) enables focused development and independent scaling of each component. 