"""
Configuration settings for the document classification system
"""
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent
DOCUMENTS_DIR = BASE_DIR / "uploads" / "documents"
EXTRACTED_DIR = BASE_DIR / "uploads" / "extracted"
RESPONSES_DIR = BASE_DIR / "uploads" / "responses"

# Create directories if they don't exist
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
RESPONSES_DIR.mkdir(parents=True, exist_ok=True)

# Backend configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3000")

# API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Authentication
API_USERNAME = os.getenv("API_USERNAME", "admin")
API_PASSWORD = os.getenv("API_PASSWORD", "password123")

# Azure OpenAI Configuration (for AI agents)
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "your-api-key-here")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://your-endpoint.openai.azure.com/")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")

# Thread pool settings
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))

# Classification settings
DEFAULT_CLASSIFICATION_THRESHOLD = float(os.getenv("DEFAULT_CLASSIFICATION_THRESHOLD", "0.7"))

# Logging settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = BASE_DIR / "logs" / "app.log"
LOG_FILE.parent.mkdir(exist_ok=True)