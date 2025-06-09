# Knowledge Base Search & RAG API

This project implements a sophisticated, multi-service application for building and querying a knowledge base using the Retrieval-Augmented Generation (RAG) pattern. It features separate services for document embedding, a RAG API for handling user queries, and a SvelteKit-based web interface for user interaction.

## Architecture Overview

The application is designed as a set of containerized microservices orchestrated by Docker Compose. This architecture separates concerns, allowing for independent development, scaling, and maintenance of each component.

```mermaid
graph TD
    subgraph "User's Local Machine"
        Browser[("Browser")]
    end

    subgraph "Docker Environment (app_network)"
        Frontend[frontend_nginx <br> Ports: 5173:80]
        RAG_API[rag_api_service <br> Ports: 8002:8002]
        Embedding[embedding_service <br> Ports: 8001:8001]
        Ollama[ollama_service <br> Ports: 11434:11434]
    end
    
    subgraph "Cloud Services"
        Supabase[Supabase <br> (Postgres, pgvector, Storage)]
    end

    Browser -- "Access UI @ localhost:5173" --> Frontend
    Browser -- "API Calls @ localhost:8002" --> RAG_API
    
    Frontend -- "Serves built SvelteKit App" --> Browser
    
    RAG_API -- "Embed search query" --> Embedding
    RAG_API -- "Generate response with context" --> Ollama
    RAG_API -- "Retrieve & store document chunks" --> Supabase

    style Browser fill:#fff,stroke:#333,stroke-width:2px
    style Supabase fill:#3ecf8e,stroke:#333,stroke-width:2px,color:#fff
```

## Features

- **Multi-Service Architecture**: Independent services for embedding, RAG logic, and frontend.
- **RAG Implementation**: Leverages LangChain to provide context-aware answers from a knowledge base.
- **Pluggable LLM**: Uses Ollama for local LLM inference, with support for OpenAI as an alternative.
- **Vector Storage**: Utilizes Supabase with `pgvector` for efficient similarity search on document embeddings.
- **Web Interface**: A modern and reactive search UI built with SvelteKit.
- **Containerized**: Fully containerized with Docker for consistent development and easy deployment.

## Technology Stack

- **Backend**: Python, FastAPI, LangChain
- **Frontend**: SvelteKit, TypeScript, Nginx
- **Database**: Supabase (PostgreSQL with pgvector)
- **LLM Engine**: Ollama (default), OpenAI
- **Containerization**: Docker, Docker Compose

## Project Structure

```
.
├── embedding_service/      # Handles text-to-vector embedding
│   ├── Dockerfile
│   └── main.py
├── rag_api_service/        # Core RAG logic and chat endpoints
│   ├── Dockerfile
│   └── main.py
├── search_ui/              # SvelteKit frontend application
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
├── .env                    # Local configuration (created by you)
├── create_venv.sh          # Utility script for local Python venv
├── docker-compose.yml      # Orchestrates all services for local dev
└── requirements.txt        # Root Python dependencies
```

## Prerequisites

Before you begin, ensure you have the following installed on your system:
- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/) (usually included with Docker Desktop)

## Getting Started

Follow these steps to get the application running locally.

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd <repository-directory>
```

### 2. Configure Environment Variables

Create a file named `.env` in the root of the project. Copy the contents below into the file and **fill in your Supabase credentials**.

```env
# ==================================
# === Supabase Configuration ===
# ==================================
# Found in your Supabase project's API settings
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_DB_PASSWORD=

# Table names (defaults are provided)
SUPABASE_DOCUMENTS_TABLE=documents
SUPABASE_CHUNKS_TABLE=document_chunks

# ==================================
# === Service URLs & Ports ===
# ==================================
# URLs used by services to communicate *inside* the Docker network
EMBEDDING_SERVICE_URL=http://embedding_service:8001
OLLAMA_BASE_URL=http://ollama:11434

# Host ports exposed on your local machine
EMBEDDING_SERVICE_PORT_HOST=8001
RAG_API_PORT_HOST=8002
FRONTEND_PORT_HOST=5173

# ==================================
# === Model Configuration ===
# ==================================
# Embedding Service Configuration
EMBEDDING_MODEL_NAME="BAAI/bge-large-en-v1.5"
EMBEDDING_MODEL_DEVICE=cpu # Options: cpu, cuda, mps
PGVECTOR_DIMENSION=1024 # Must match the dimension of the chosen embedding model

# RAG Service LLM Provider (ollama or openai)
LLM_PROVIDER=ollama
OLLAMA_MODEL=phi3:mini # The model to use with Ollama

# --- OpenAI (only needed if LLM_PROVIDER=openai) ---
OPENAI_API_KEY=
OPENAI_MODEL_NAME=gpt-4

# =====================================================================================
# === Vite Build-time Variables (passed as ARGs in docker-compose to search_ui) ===
# =====================================================================================
# These URLs are used by the frontend (in the browser) to talk to the backend.
VITE_RAG_API_URL=http://localhost:8002
# This is the redirect URL for MSAL authentication in a local environment.
VITE_MSAL_REDIRECT_URI=http://localhost:5173
```

### 3. Build and Run the Application

Open a terminal in the project root and run the following command:

```bash
docker-compose up --build
```

- `--build`: This flag forces a rebuild of the service images. It's important to use this the first time you start the app or after changing any source code or `Dockerfile`.
- The first launch will take several minutes as it needs to download base images and the specified AI/embedding models.

### 4. Access the Application

Once all services are running, you can access the web interface in your browser at:
**[http://localhost:5173](http://localhost:5173)**

## Service Details

### Embedding Service
- **Purpose**: Provides a simple API endpoint to convert text into vector embeddings.
- **Model**: Uses a `sentence-transformers` model (`BAAI/bge-large-en-v1.5` by default).
- **Endpoint**: `POST /embed`
- **Access**: Available at `http://localhost:8001` on the host machine.

### RAG API Service
- **Purpose**: The core of the application. It receives user queries, converts them to embeddings (using the `embedding_service`), retrieves relevant document chunks from Supabase, and uses an LLM (via Ollama) to generate a final answer.
- **Endpoints**:
    - `POST /chat`: Main endpoint for asking questions.
    - `POST /search`: Performs similarity search and returns source documents.
- **Access**: Available at `http://localhost:8002` on the host machine.

### Ollama Service
- **Purpose**: Runs the large language model for the RAG service.
- **Model**: Downloads and serves the model specified by `OLLAMA_MODEL` in the `.env` file.
- **Access**: The API is available at `http://localhost:11434`.

### Frontend Nginx Service
- **Purpose**: Serves the static, built SvelteKit frontend application.
- **Build Process**: The `Dockerfile` for this service first builds the SvelteKit app (injecting the `VITE_*` environment variables) and then copies the static assets into a lightweight Nginx container.
- **Access**: Serves the UI at `http://localhost:5173`.

## Deployment Notes

While this setup is configured for local development, it can be adapted for production. The key differences in the provided production configuration are:
- The `VITE_RAG_API_URL` is set to `/api`. This implies a reverse proxy is set up in front of the application that routes requests for `https://your-domain.com/api` to the RAG API service's container.
- `VITE_MSAL_REDIRECT_URI` points to the public domain name (`https://your-domain.com`). 