from fastapi import APIRouter, HTTPException
from datetime import datetime

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


def create_error_response(task_id: str, project_id: str, error_msg: str) -> dict:
    """Helper function to create consistent error responses"""
    return {
        "task_id": task_id,
        "project_id": project_id,
        "status": "error",
        "message": "Failed to initialize document classification",
        "error": error_msg,
        "timestamp": datetime.now().isoformat()
    }


def create_processing_response(task_id: str, message: str) -> dict:
    """Helper function to create consistent processing responses"""
    return {
        "task_id": task_id,
        "status": "processing",
        "message": message,
        "error": None,
    }


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

        logger.info(f"Starting document classification for task: {request.task_id}")
        logger.info(f"Document URL: {request.document_url}")
        logger.info(f"Project metadata: {request.project_metadata.dict()}")

        # Download document with enhanced error handling
        downloader = FileDownloader(base_dir=DOCUMENTS_DIR)
        download_result = await downloader.download_single_file(
            task_id=request.task_id,
            project_id=request.project_id,
            file_url=request.document_url,
            file_id="document_to_classify"
        )

        if download_result["status"] == "failed":
            error_msg = download_result.get("error", "Failed to download document")
            logger.error(f"Download failed for task {request.task_id}: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

        logger.info(f"Document downloaded successfully: {download_result['file_path']}")
        logger.info(f"File size: {download_result.get('file_size', 'unknown')} bytes")

        # Add task to thread manager for tracking
        thread_manager.add_task(request.task_id, "document-classification")

        # Create enhanced workflow instance
        workflow = DocumentClassificationWorkflow(
            task_id=request.task_id,
            project_id=request.project_id,
            backend_url=BACKEND_URL,
            file_path=download_result["file_path"],
            project_metadata=request.project_metadata.dict(),
            classification_threshold=request.classification_threshold
        )

        # Submit to thread pool for parallel processing
        thread_manager.submit_task(
            request.task_id,
            workflow.process_classification
        )

        # Create consistent response structure
        response_data = create_processing_response(
            task_id=request.task_id,
            project_id=request.project_id,
            message="Document classification started - downloading and analyzing content"
        )

        # Save detailed status for later retrieval
        detailed_status = {
            **response_data,
            "file_info": {
                "url": request.document_url,
                "path": download_result["file_path"],
                "size": download_result.get("file_size")
            },
            "project_metadata": request.project_metadata.dict(),
            "classification_threshold": request.classification_threshold
        }

        await LocalStorageManager.save_response(request.task_id, detailed_status)

        logger.info(f"Document classification task {request.task_id} submitted successfully")

        # Return immediate response
        return ClassificationResultImmediate(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error initializing document classification: {str(e)}")
        error_response = create_error_response(
            task_id=request.task_id,
            project_id=request.project_id,
            error_msg=str(e)
        )
        await LocalStorageManager.save_response(request.task_id, error_response)
        return ClassificationResultImmediate(**error_response)


@router.get("/classification-status/{task_id}", response_model=ClassificationResultImmediate)
async def get_classification_status(task_id: str):
    """Get the status and results of a document classification task"""
    try:
        result = await LocalStorageManager.get_response(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="Task not found")

        # Ensure all required fields are present for the response model
        response_data = {
            "task_id": result.get("task_id", task_id),
            "status": result.get("status", "unknown"),
            "message": result.get("message", "Status retrieved"),
            "error": result.get("error"),
            "project_id": result.get("project_id"),
            "timestamp": result.get("timestamp")
        }

        # Add classification results if available (for completed tasks)
        if result.get("status") == "completed" and "classification_result" in result:
            classification = result["classification_result"]
            response_data.update({
                "summaryDecision": classification.get("summaryDecision"),
                "decisionDetails": classification.get("decisionDetails"),
                "relevancyPercentage": classification.get("relevancyPercentage")
            })

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
            project_id=request.project.id,
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
            "project_info": {
                "opportunity_name": request.project.opportunityName,
                "reference_number": request.project.referenceNumber,
                "amount": request.project.amountInEur,
                "stage": request.project.currentStage,
                "owner": request.project.opportunityOwner
            },
            "extracted_metadata": project_metadata,
            "classification_threshold": request.classification_threshold
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