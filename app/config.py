import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# API Configuration
API_V1_STR = "/api/v1"
PROJECT_NAME = "AI Application"

# ChromaDB Configuration
CHROMADB_HOST = os.getenv("CHROMADB_HOST", "localhost")
CHROMADB_PORT = int(os.getenv("CHROMADB_PORT", 8000))
CHROMADB_PERSIST_DIR = os.getenv("CHROMADB_PERSIST_DIR", str(BASE_DIR / "data" / "chromadb"))


# Upload directories
DOCUMENTS_DIR = BASE_DIR / "uploads" / "documents"
EXTRACTED_DIR = BASE_DIR / "uploads" / "extracted"

# Create base directories
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "app.log"))


# Rate Limiting
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", 60))

# Backend Url
BACKEND_URL = os.getenv("BACKEND_URL")
