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
