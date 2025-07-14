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
- **Authentication**: Microsoft Entra ID (Azure AD) integration with MSAL in frontend and JWT validation in backend (see limitations below).
- **Containerized**: Fully containerized with Docker for consistent development and easy deployment.
- **Secret Management**: Doppler integration for secure environment variable handling.

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

The project uses Doppler for secret management. Install the Doppler CLI and configure it for the project (see doppler.yaml).

Alternatively, create a `.env` file in the root with required variables (see example in README or doppler.yaml).

For authentication, ensure MSAL variables are set (VITE_MSAL_CLIENT_ID, etc.).

### 3. Build and Run the Application

Use the startup scripts for easy launch:

```bash
./start_services.sh  # Auto-detects best mode (Docker with Doppler recommended)
```

See STARTUP_SCRIPTS.md for detailed options.

The first run downloads models and may take time.

### 4. Access the Application

UI: http://localhost:5173 (requires login via Microsoft account).

API: http://localhost:8002 (protected endpoints require valid token).

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

## Authentication

The app uses Azure AD for authentication:
- Frontend: MSAL acquires tokens with specific scopes.
- Backend: Validates JWTs (signature, issuer, audience) but does not enforce scopes currently.

For details and limitations, see [authentication_implementation.md](authentication_implementation.md).

## Limitations
- No scope checking in backend – any valid token from the app can access APIs.
- Local dev may require manual .env if Doppler not set up.
- First startup is slow due to model downloads.

## Recent Changes
- Extensive Azure AD authentication debugging and refactoring.
- Doppler integration for secrets.
- Startup scripts for flexible launching.
- UI improvements and logging.

See git log for full history. 