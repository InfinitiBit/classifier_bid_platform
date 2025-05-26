import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import json
from datetime import datetime
from typing import Dict, Any, List
import logging
from pathlib import Path
import os
from openai import OpenAI
from dotenv import load_dotenv
import asyncio

load_dotenv()


class ScopeCollectionsManager:
    def __init__(self):
        host = os.getenv("CHROMADB_HOST")
        token = os.getenv("CHROMADB_TOKEN")

        if not all([host, token]):
            raise ValueError("Missing environment variables")

        self.client = chromadb.HttpClient(
            host=host,
            port=8000,
            settings=Settings(
                chroma_client_auth_provider="chromadb.auth.token_authn.TokenAuthClientProvider",
                chroma_client_auth_credentials=token,
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name="text-embedding-3-small"  # Using 384 dimensions
        )

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)



class ChromaDBQueryTester:
    def __init__(self, scope_manager: ScopeCollectionsManager):
        self.client = scope_manager.client
        self.logger = logging.getLogger(__name__)
        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("AZURE_API_KEY"),
            api_base=os.getenv("AZURE_API_BASE"),
            api_type="azure",
            api_version=os.getenv("AZURE_API_VERSION"),
            model_name="text-embedding-3-small",
        )













