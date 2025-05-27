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
BACKEND_URL = os.getenv("BACKEND_URL")


# Azure OpenAI Configuration (for AI agents)
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")


# Logging settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = BASE_DIR / "logs" / "app.log"
LOG_FILE.parent.mkdir(exist_ok=True)