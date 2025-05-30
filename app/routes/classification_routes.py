from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Dict, Any

from app.utils.file_downloader import FileDownloader
from app.config import DOCUMENTS_DIR, BACKEND_URL
from app.utils.logging import get_logger
from app.utils.thread_manager import thread_manager
from app.utils.storage import LocalStorageManager
from app.workflow.document_classification.document_classification_workflow import DocumentClassificationWorkflow
from app.serializers.api.classification_request import DocumentClassificationRequest
from app.serializers.api.classification_response import ClassificationResultImmediate
from app.services.project_metadata_extractor import EnhancedClassificationRequest

router = APIRouter()
logger = get_logger(__name__)


def create_error_response(task_id: str, error_msg: str) -> dict:
    """Helper function to create consistent error responses"""
    return {
        "taskId": task_id,
        "status": "error",
        "message": "Failed to initialize document classification",
        "error": error_msg,
    }


def create_processing_response(task_id: str, message: str) -> dict:
    """Helper function to create consistent processing responses"""
    return {
        "taskId": task_id,
        "status": "processing",
        "message": message,
        "error": None,
    }


def extract_project_metadata(project) -> Dict[str, Any]:
    """Extract metadata from project for classification"""
    metadata = {
        "project_id": project.id,
        "project_name": project.projectName or project.opportunityName,
        "description": project.description,
        "status": project.status,
        "current_stage": project.currentStage,
        "opportunity_owner": project.opportunityOwner,
        "amount": project.amountInEur,
    }

    # Add metadata items
    if project.metaData:
        for item in project.metaData:
            metadata[item.attributeName] = item.attributeValue

    # Add bid manager info if available
    if project.bidManager:
        metadata["bid_manager"] = f"{project.bidManager.firstName} {project.bidManager.lastName}"
        metadata["bid_manager_email"] = project.bidManager.email

    return metadata


@router.post("/classify-document", response_model=ClassificationResultImmediate)
async def classify_document(request: DocumentClassificationRequest):
    """
    Enhanced document classifier with PDF download, summarization, and metadata matching.

    This endpoint:
    1. Downloads the document from the provided URL
    2. Performs fast bypass for blank/minimal documents
    3. Extracts and summarizes content using AI agents
    4. Compares against project metadata using specialized agents
    5. Returns relevance classification with detailed reasoning

    Uses ThreadPool for parallel processing and CrewAI for multi-agent workflow.
    """
    try:
        # Check thread pool capacity
        if not thread_manager.can_accept_task():
            raise HTTPException(
                status_code=503,
                detail="Server is at maximum capacity. Please try again later."
            )

        logger.info(f"Starting document classification for task: {request.taskId}")
        logger.info(f"Document URL: {request.document.FileUrl}")
        logger.info(f"Document Reference: {request.document.Reference}")
        logger.info(f"Project: {request.project.opportunityName or request.project.projectName}")

        # Extract project metadata
        project_metadata = extract_project_metadata(request.project)
        logger.info(f"Extracted project metadata: {project_metadata}")

        # Download document with enhanced error handling
        downloader = FileDownloader(base_dir=DOCUMENTS_DIR)
        download_result = await downloader.download_single_file(
            task_id=request.taskId,
            file_url=request.document.FileUrl,
            file_id=request.document.Reference or "document_to_classify"
        )

        if download_result["status"] == "failed":
            error_msg = download_result.get("error", "Failed to download document")
            logger.error(f"Download failed for task {request.taskId}: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

        logger.info(f"Document downloaded successfully: {download_result['file_path']}")
        logger.info(f"File size: {download_result.get('file_size', 'unknown')} bytes")

        # Add task to thread manager for tracking
        thread_manager.add_task(request.taskId, "document-classification")

        # Create enhanced workflow instance
        # Default classification threshold if not provided
        classification_threshold = 0.7

        workflow = DocumentClassificationWorkflow(
            task_id=request.taskId,
            project_id=request.project.id,
            backend_url=BACKEND_URL,
            file_path=download_result["file_path"],
            project_metadata=project_metadata,
            classification_threshold=classification_threshold
        )

        # Submit to thread pool for parallel processing
        thread_manager.submit_task(
            request.taskId,
            workflow.process_classification
        )

        # Create consistent response structure
        response_data = create_processing_response(
            task_id=request.taskId,
            message="Document classification started - downloading and analyzing content"
        )

        # Save detailed status for later retrieval
        detailed_status = {
            **response_data,
            "project_id": request.project.id,
            "document_info": {
                "reference": request.document.Reference,
                "url": request.document.FileUrl,
                "path": download_result["file_path"],
                "size": download_result.get("file_size")
            },
            "project_metadata": project_metadata,
            "classification_threshold": classification_threshold,
            "timestamp": datetime.now().isoformat()
        }

        await LocalStorageManager.save_response(request.taskId, detailed_status)

        logger.info(f"Document classification task {request.taskId} submitted successfully")

        # Return immediate response
        return ClassificationResultImmediate(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error initializing document classification: {str(e)}")
        error_response = create_error_response(
            task_id=request.taskId,
            error_msg=str(e)
        )
        await LocalStorageManager.save_response(request.taskId, error_response)
        return ClassificationResultImmediate(**error_response)

