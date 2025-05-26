from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body, Query, Path
from typing import Dict, Any
import logging

# Import ChromaDB components
from app.services.vectordb_rabbitmq_communication.hybrid_retriever_reciprocal_rank_fusion import HybridRetriever
from app.services.vectordb_rabbitmq_communication.vectordb_rabbitmq_wrapper import ChromaDBClientWrapper
from app.serializers.api.vector_search_request import VectorSearchRequest


from dotenv import load_dotenv
load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)


def query_vector_store_sync(
        query: str,
        project_name: str,
        top_k: int = 5,
        enable_contextual: bool = True,
        vector_weight: float = 0.7,
        use_rrf: bool = True  # Default to True to use RRF for all searches
) -> Dict[str, Any]:
    """
    Query the vector store with RabbitMQ communication pattern.

    Args:
        query: User query string
        project_name: Name of the project
        top_k: Number of results to return
        enable_contextual: Whether to use contextual retrieval approach
        vector_weight: Weight for vector similarity (1-weight for keyword matching)
        use_rrf: Whether to use Reciprocal Rank Fusion (default: True)

    Returns:
        Dictionary with search results
    """
    try:
        # Create a wrapper that will intercept calls to ChromaDB
        # and route them through RabbitMQ
        wrapped_client = ChromaDBClientWrapper()

        # Create a scope manager with our wrapped client
        # NOTE: We're creating a simple object to mimic ScopeCollectionsManager
        scope_manager = type('', (), {})()  # Create an empty object
        scope_manager.client = wrapped_client
        scope_manager.openai_ef = None  # Not needed as embedding happens in VectorDB Service

        # Create the retriever with RRF enabled by default
        retriever = HybridRetriever(
            scope_manager=scope_manager,
            project_name=project_name,
            vector_weight=vector_weight,
            enable_contextual=enable_contextual,
            use_rrf=use_rrf,    # Default to RRF
            rrf_k=60            # Use default RRF k value
        )

        # Perform retrieval - this will automatically use RabbitMQ
        # for calls to collection.get() and collection.query()
        results = retriever.retrieve(
            query=query,
            top_k=top_k
        )

        return results

    except Exception as e:
        logger.error(f"Error querying vector store: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.post("/search")
def search_vector_store_sync_endpoint(request: VectorSearchRequest):
    """
    Search vectorized PDF content with a natural language query.
    Results are automatically cleaned to remove formatting artifacts.

    Parameters:
        - query: Natural language query
        - project_name: Name of the project
        - top_k: Number of results to return (default: 5, max: 20)
    """
    enable_contextual = True
    try:
        # Process the query directly with contextual support and RRF enabled internally
        result = query_vector_store_sync(
            query=request.query,
            project_name=request.project_name,
            top_k=request.top_k,
            enable_contextual=enable_contextual,
            # use_rrf=True is now the default in query_vector_store_sync
        )

        # We don't need to clean again since query_vector_store_sync already cleans each result
        return result

    except Exception as e:
        logger.exception(f"Error processing vector search: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

