import logging
from typing import Dict, Any, List
from app.services.vectordb_rabbitmq_communication.ai_engine import AIEngine

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VectorDBWrapper:
    """
    A wrapper around ChromaDB collections that intercepts calls and routes
    them through RabbitMQ to the VectorDB Service.
    """

    def __init__(self, collection_name):
        """
        Initialize the wrapper with a collection name.

        Args:
            collection_name: Name of the collection to wrap
        """
        self.collection_name = collection_name
        self.ai_engine = AIEngine()

    def get(self):
        """
        Get all documents from the collection through RabbitMQ.

        Returns:
            Dictionary with all documents in the collection
        """
        response = self.ai_engine.query_vectordb(
            query_text="",  # Not needed for get_all operation
            collection_name=self.collection_name,
            operation="get_all"
        )

        # Check if the response was successful
        if response.get("status") == "success":
            return response.get("result", {})
        else:
            error_msg = response.get("error", "Unknown error getting documents")
            logger.error(f"Error getting documents: {error_msg}")
            # Return empty structure to avoid breaking code that expects this format
            return {
                "ids": [],
                "documents": [],
                "metadatas": [],
                "embeddings": []
            }

    def query(self, query_texts: List[str], n_results: int = 5, **kwargs):
        """
        Query the collection through RabbitMQ.

        Args:
            query_texts: List of query texts
            n_results: Number of results to return
            **kwargs: Additional query parameters

        Returns:
            Dictionary with query results
        """
        # We only support one query text at a time with this wrapper
        query_text = query_texts[0] if query_texts else ""
        logger.info(f"VectorDBWrapper.query called with text: '{query_text}'")

        response = self.ai_engine.query_vectordb(
            query_text=query_text,
            collection_name=self.collection_name,
            operation="query",
            n_results=n_results,
            extra_params=kwargs
        )

        # Check if the response was successful
        if response.get("status") == "success":
            return response.get("result", {})
        else:
            error_msg = response.get("error", "Unknown error querying documents")
            logger.error(f"Error querying documents: {error_msg}")
            # Return empty structure to avoid breaking code that expects this format
            return {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }


class ChromaDBClientWrapper:
    """
    A wrapper around ChromaDB client that intercepts calls to get_collection
    and returns a wrapped collection.
    """

    def __init__(self):
        """Initialize the wrapper"""
        self.ai_engine = AIEngine()

    def get_collection(self, name, embedding_function=None):
        """
        Get a collection through RabbitMQ.

        Args:
            name: Name of the collection
            embedding_function: Not used in this wrapper

        Returns:
            Wrapped collection
        """
        return VectorDBWrapper(name)

    def list_collections(self):
        """
        List all collections through RabbitMQ.

        Returns:
            List of collection names
        """
        response = self.ai_engine.query_vectordb(
            query_text="",
            collection_name="system",  # Using a system collection for this operation
            operation="list_collections"
        )

        # Check if the response was successful
        if response.get("status") == "success":
            return response.get("collections", [])
        else:
            error_msg = response.get("error", "Unknown error listing collections")
            logger.error(f"Error listing collections: {error_msg}")
            return []
