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


@router.get("/classification-status/{task_id}", response_model=ClassificationResultImmediate)
async def get_classification_status(task_id: str):
    """Get the status and results of a document classification task"""
    try:
        result = await LocalStorageManager.get_response(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="Task not found")

        # Map internal storage format to response model format
        response_data = {
            "taskId": result.get("taskId", result.get("task_id", task_id)),
            "status": result.get("status", "unknown"),
            "message": result.get("message", "Status retrieved"),
            "error": result.get("error")
        }

        # Add classification results if available (for completed tasks)
        if result.get("status") == "completed" and "classificationReport" in result:
            report = result.get("classificationReport", [])
            for item in report:
                if item.get("attributeName") == "summaryDecision":
                    response_data["summaryDecision"] = item.get("attributeValue")
                elif item.get("attributeName") == "decisionDetails":
                    response_data["decisionDetails"] = item.get("attributeValue")
                elif item.get("attributeName") == "relevancyPercentage":
                    response_data["relevancyPercentage"] = int(item.get("attributeValue", 0))

        return ClassificationResultImmediate(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting classification status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/classify-document-enhanced", response_model=ClassificationResultImmediate)
async def classify_document_enhanced(request: EnhancedClassificationRequest):
    """
    Enhanced document classifier using the new project metadata structure.

    This endpoint uses the structured project metadata format and extracts
    classification parameters automatically from the project data.
    """
    try:
        # Extract classification metadata from project structure
        project_metadata = request.project.extract_classification_metadata()

        logger.info(f"Enhanced classification request for task: {request.taskId}")
        logger.info(f"Project: {request.project.opportunityName}")
        logger.info(f"Extracted metadata: {project_metadata}")

        # Input validation
        if not request.document_url:
            raise HTTPException(status_code=400, detail="Document URL is required")

        if not request.project:
            raise HTTPException(status_code=400, detail="Project information is required")

        # Check thread pool capacity
        if not thread_manager.can_accept_task():
            raise HTTPException(
                status_code=503,
                detail="Server is at maximum capacity. Please try again later."
            )

        logger.info(f"Starting enhanced document classification for task: {request.taskId}")
        logger.info(f"Document URL: {request.document_url}")

        # Download document
        downloader = FileDownloader(base_dir=DOCUMENTS_DIR)
        download_result = await downloader.download_single_file(
            task_id=request.taskId,
            file_url=request.document_url,
            file_id="document_to_classify"
        )

        if download_result["status"] == "failed":
            error_msg = download_result.get("error", "Failed to download document")
            logger.error(f"Download failed for task {request.taskId}: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

        logger.info(f"Document downloaded successfully: {download_result['file_path']}")

        # Add task to thread manager
        thread_manager.add_task(request.taskId, "document-classification-enhanced")

        # Create workflow instance with extracted metadata
        workflow = DocumentClassificationWorkflow(
            task_id=request.taskId,
            project_id=request.project.id,
            backend_url=BACKEND_URL,
            file_path=download_result["file_path"],
            project_metadata=project_metadata,
            classification_threshold=request.classification_threshold
        )

        # Submit to thread pool
        thread_manager.submit_task(
            request.taskId,
            workflow.process_classification
        )

        # Create consistent response structure
        response_data = create_processing_response(
            task_id=request.taskId,
            message=f"Enhanced classification started for {request.project.opportunityName}"
        )

        # Save detailed status for later retrieval
        detailed_status = {
            **response_data,
            "project_id": request.project.id,
            "project_info": {
                "opportunity_name": request.project.opportunityName,
                "reference_number": request.project.referenceNumber,
                "amount": request.project.amountInEur,
                "stage": request.project.currentStage,
                "owner": request.project.opportunityOwner
            },
            "extracted_metadata": project_metadata,
            "classification_threshold": request.classification_threshold,
            "timestamp": datetime.now().isoformat()
        }

        await LocalStorageManager.save_response(request.taskId, detailed_status)

        logger.info(f"Enhanced classification task {request.taskId} submitted successfully")

        # Return immediate response
        return ClassificationResultImmediate(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in enhanced document classification: {str(e)}")
        error_response = create_error_response(
            task_id=request.taskId,
            error_msg=str(e)
        )
        await LocalStorageManager.save_response(request.taskId, error_response)
        return ClassificationResultImmediate(**error_response)


@router.get("/health")
async def health_check():
    """Health check endpoint for the classification service"""
    active_tasks = len(thread_manager.active_tasks)
    can_accept = thread_manager.can_accept_task()

    return {
        "status": "healthy",
        "service": "document-classification",
        "version": "2.0.0",
        "active_tasks": active_tasks,
        "can_accept_new_tasks": can_accept,
        "timestamp": datetime.now().isoformat()
    }