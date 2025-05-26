from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
import time
from app.utils.logging import get_logger
from typing import Dict, Any
import os
from dotenv import load_dotenv
from scripts.populate_chromadb import ScopeCollectionsManager

router = APIRouter()
logger = get_logger(__name__)


# @router.get("/health")
# async def health_check():
#     """
#     Check the health status of the application and its dependencies
#     """
#     start_time = time.time()
#
#     # Check ChromaDB connection
#     chroma_start_time = time.time()
#     chroma_status = check_chroma_connection()
#     chroma_duration = time.time() - chroma_start_time
#
#     # Determine overall health status
#     overall_status = "Healthy" if chroma_status.get("status") == "connected" else "Degraded"
#
#     if overall_status == "Healthy":
#         logger.info("Health check passed")
#     else:
#         logger.warning("Health check returned degraded status")
#
#     # Calculate total duration
#     total_duration = time.time() - start_time
#
#     # Format the durations as "00:00:00.0000000"
#     formatted_total_duration = format_duration(total_duration)
#     formatted_chroma_duration = format_duration(chroma_duration)
#
#     # Return comprehensive health information following the requested structure
#     return {
#         "status": overall_status,
#         "totalDuration": formatted_total_duration,
#         "entries": {
#             "chromadb": {
#                 "data": {},
#                 "description": "Ready" if chroma_status.get("status") == "connected" else "Unavailable",
#                 "duration": formatted_chroma_duration,
#                 "status": "Healthy" if chroma_status.get("status") == "connected" else "Unhealthy",
#                 "tags": ["ready", "chromadb"] if chroma_status.get("status") == "connected" else ["unavailable",
#                                                                                                   "chromadb"]
#             }
#         }
#     }

@router.get("/health")
async def health_check():
    """
    Check the health status of the application
    """

    logger.info("Healthy")
    return {"status": "ok"}

def check_chroma_connection() -> Dict[str, Any]:
    """
    Check the ChromaDB connection status using ScopeCollectionsManager

    Returns:
        Dict containing status and collection information
    """
    try:
        # Initialize ScopeCollectionsManager
        scope_manager = ScopeCollectionsManager()

        # Get client from manager
        client = scope_manager.client

        # Try to list collections just to verify connection works
        collection_names = client.list_collections()

        # Get heartbeat to verify server health
        heartbeat = client.heartbeat()

        return {
            "status": "connected",
            "heartbeat": heartbeat
        }
    except Exception as e:
        logger.error(f"ChromaDB connection error: {str(e)}")
        return {
            "status": "disconnected",
            "error": str(e)
        }


def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds to "00:00:00.0000000" format
    """
    # Convert seconds to timedelta
    td = timedelta(seconds=seconds)

    # Extract hours, minutes, seconds from timedelta
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Format the duration string
    return f"{hours:02}:{minutes:02}:{seconds:02}.{int(td.microseconds / 100):07d}"