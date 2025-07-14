# Embedding Service Overview

## Purpose
The Embedding Service is a FastAPI-based microservice that provides an API for generating semantic embeddings from text inputs. It uses the Sentence Transformers library to create vector representations of text, which are useful for tasks like similarity search in RAG (Retrieval-Augmented Generation) systems. This service is part of the larger KB Search API project, likely used by the RAG API to embed queries and documents.

## Key Components
The service consists of the following main files:

- **main.py**: The core application script that sets up the FastAPI app, loads the embedding model, and defines API endpoints.
- **Dockerfile**: Defines the Docker image for containerizing the service, based on Python 3.11-slim.
- **Procfile**: Specifies the command to run the service (e.g., for Heroku deployment): `web: uvicorn main:app --host 0.0.0.0 --port $PORT`.
- **requirements.txt**: Lists dependencies including FastAPI, Uvicorn, python-dotenv, Sentence Transformers, and Torch.
- **doppler_integration.py**: A utility for loading environment variables from Doppler (secrets management) with fallback to .env files.
- **.dockerignore**: Specifies files/directories to ignore when building the Docker image (e.g., .git, .venv, etc.).

## Configuration
- **Environment Variables**:
  - `EMBEDDING_MODEL_NAME`: Specifies the model (defaults to "BAAI/bge-large-en-v1.5").
  - `EMBEDDING_MODEL_DEVICE`: Sets the device (e.g., "cpu", "cuda", "mps"; defaults to "cpu" with fallbacks if unavailable).
  - `EMBEDDING_SERVICE_PORT`: The port for the Uvicorn server (defaults to 8001).
- Variables are loaded preferentially from Doppler, falling back to .env files or system environment.

## How It Works
1. **Startup and Model Loading**:
   - The service uses FastAPI's lifespan context manager to load the SentenceTransformer model during application startup.
   - It prints the model name and device being used.
   - If the device is "mps" (Apple Silicon), it performs a warmup encoding to initialize.
   - If loading fails, it raises a RuntimeError to prevent the service from starting.

2. **API Endpoints**:
   - **GET /**: A health check endpoint that returns the service status, model name, and device.
   - **POST /embed**: Accepts a JSON payload with a "text" field, generates an embedding using the loaded model, and returns it as a list of floats.
     - Validates input (non-empty text).
     - Handles errors like model not loaded (HTTP 500) or empty input (HTTP 400).

3. **Embedding Generation**:
   - Uses `model.encode(text, convert_to_tensor=False)` to generate a NumPy array, converted to a list.
   - Logs the text snippet and embedding dimension (typically 1024 for the default model).

4. **Running the Service**:
   - Locally: `python main.py` (runs Uvicorn on 0.0.0.0:8001 or specified port).
   - In Docker: Built via Dockerfile, runs `python main.py`.
   - In production (e.g., Heroku): Uses Procfile to run Uvicorn on the provided $PORT.

5. **Shutdown**:
   - On shutdown, the lifespan manager sets the model to None and prints a shutdown message.

## Dependencies
- **FastAPI**: For the web framework.
- **Uvicorn**: ASGI server to run the app.
- **Sentence Transformers**: For loading and using pre-trained embedding models.
- **Torch**: Backend for model computations, with device support.
- **python-dotenv**: For .env fallback.
- **Pydantic**: For request/response models.

## Potential Improvements
- Add batch embedding support for multiple texts in one request.
- Implement caching for frequently used embeddings.
- Add more robust error handling or metrics logging.
- Support dynamic model switching via API.

This service integrates with the broader project by providing embeddings on demand, likely called by the RAG API for query processing. 