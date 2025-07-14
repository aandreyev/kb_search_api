import os
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import torch
from contextlib import asynccontextmanager

# # Import doppler_integration from current directory
# from doppler_integration import load_environment

# # Load environment variables from Doppler or fallback to .env
# load_environment()

# --- Configuration ---
MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-large-en-v1.5")
# Determine the device dynamically, defaulting to 'cpu' if not specified or invalid
DEVICE = os.getenv("EMBEDDING_MODEL_DEVICE", "cpu")
if DEVICE == "mps" and not torch.backends.mps.is_available():
    print("Warning: MPS device requested but not available. Falling back to CPU.")
    DEVICE = "cpu"
elif DEVICE == "cuda" and not torch.cuda.is_available():
    print("Warning: CUDA device requested but not available. Falling back to CPU.")
    DEVICE = "cpu"

print(f"Using embedding model: {MODEL_NAME}")
print(f"Using device: {DEVICE}")

# --- Global Variables ---
# Will hold the loaded model instance
model = None

# --- Pydantic Models ---
class EmbeddingRequest(BaseModel):
    text: str

class EmbeddingResponse(BaseModel):
    embedding: list[float]

# --- FastAPI Lifespan Management ---
# Load the model during startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    print("Loading Sentence Transformer model...")
    try:
        model = SentenceTransformer(MODEL_NAME, device=DEVICE)
        # If using MPS, a dummy forward pass can sometimes help initialize it.
        if DEVICE == 'mps':
             # Add a check to ensure model is loaded before encoding
             if model:
                 model.encode("warmup")
             else:
                  print("Model object not created, skipping warmup.") # Should ideally not happen if above didn't raise
        print("Model loaded successfully.")
    except Exception as e:
        print(f"FATAL: Error loading Sentence Transformer model: {e}")
        # Raise error to prevent FastAPI from starting with a non-functional model
        raise RuntimeError(f"Could not load Sentence Transformer model: {e}") from e
    yield
    # Clean up resources if needed on shutdown (optional here)
    print("Shutting down Embedding Service...")
    model = None


# --- FastAPI App Instance ---
app = FastAPI(lifespan=lifespan)

# --- API Endpoints ---
@app.get("/")
async def read_root():
    """Root endpoint for health check."""
    return {"status": "Embedding Service is running", "model_name": MODEL_NAME, "device": DEVICE}

@app.post("/embed", response_model=EmbeddingResponse)
async def get_embedding(request: EmbeddingRequest):
    """Generate embedding for the input text."""
    global model
    if model is None:
        raise HTTPException(status_code=500, detail="Model not loaded. Service might be initializing or encountered an error.")

    if not request.text:
        raise HTTPException(status_code=400, detail="Input text cannot be empty.")

    try:
        print(f"Generating embedding for text snippet: '{request.text[:100]}...'") # Log snippet
        embedding = model.encode(request.text, convert_to_tensor=False).tolist() # Get numpy array then convert to list
        print(f"Generated embedding of dimension: {len(embedding)}") # Log dimension
        return EmbeddingResponse(embedding=embedding)
    except AttributeError as ae:
        # This might happen if model is None despite lifespan checks
        print(f"Error: Model object not available during embedding generation: {ae}")
        raise HTTPException(status_code=503, detail="Model is not available. Service may be initializing or encountered an error.")
    except Exception as e:
        print(f"Error during embedding generation for text '{request.text[:50]}...': {e}")
        # Consider adding more specific exception types if needed
        raise HTTPException(status_code=500, detail=f"Failed to generate embedding: {e}")

# --- Main Block (for running with uvicorn) ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("EMBEDDING_SERVICE_PORT", 8001)) # Reads from .env
    host = "0.0.0.0" # Essential for Docker
    print(f"Starting Uvicorn server on {host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=False) # reload=False for prod

