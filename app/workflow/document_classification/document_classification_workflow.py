"""
Main workflow processor for document classification.
Orchestrates the entire workflow from document download to relevance classification.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
import sys

# Add project root to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.utils.storage import LocalStorageManager
from app.utils.backend_notify_completion import notify_backend_completion
from app.utils.backend_notify_status import notify_backend_status
from app.utils.logging import setup_logging
from app.agent_tasks.document_classification.document_classification_task import DocumentClassificationTask
from app.config import EXTRACTED_DIR

# Import workflow helpers
from app.workflow.document_classification.helper_methods.document_processor import (
    extract_document_content,
    validate_project_metadata, 
    format_classification_result
)

logger = setup_logging()


class DocumentClassificationWorkflow:
    """
    Workflow processor for document classification based on project metadata.
    Orchestrates the complete process from content extraction to relevance determination.
    """

    def __init__(
        self, 
        task_id: str, 
        project_id: str, 
        backend_url: str, 
        file_path: str,
        project_metadata: Dict[str, Any],
        classification_threshold: float = 0.7
    ):
        """
        Initialize the document classification workflow.

        Args:
            task_id (str): Task identifier for backend communication
            project_id (str): Project identifier
            backend_url (str): URL for backend API
            file_path (str): Path to the document file
            project_metadata (Dict): Project metadata for comparison
            classification_threshold (float): Threshold for relevance classification
        """
        self.task_id = task_id
        self.project_id = project_id
        self.backend_url = backend_url
        self.file_path = file_path
        self.project_metadata = project_metadata
        self.classification_threshold = classification_threshold
        self.base_dir = EXTRACTED_DIR

        # Initialize classification task
        self.classification_task = DocumentClassificationTask(
            output_base_dir=str(EXTRACTED_DIR),
            task_id=task_id,
            backend_url=backend_url
        )

        logger.info(f"Initialized DocumentClassificationWorkflow for task: {task_id}")

    async def process_classification(self) -> Dict[str, Any]:
        """
        Process the complete document classification workflow.

        Returns:
            Dict: Workflow result with classification decision
        """
        try:
            logger.info(f"Starting document classification workflow for task: {self.task_id}")
            steps = {}

            # Step 1: Extract document content
            try:
                logger.info("Step 2: Extracting document content")
                
                await notify_backend_status(
                    self.backend_url,
                    self.task_id,
                    {
                        "taskName": "Document Content Extraction Started",
                        "taskFriendlyName": "Extracting content from document",
                    }
                )
                
                content_result = extract_document_content(self.file_path)
                
                if not content_result["extraction_success"]:
                    error_msg = f"Content extraction failed: {content_result.get('error', 'Unknown error')}"
                    return await self._handle_workflow_error(error_msg, "content_extraction")
                
                document_content = content_result["content"]
                file_size = content_result["file_size"]
                
                steps["content_extraction"] = {
                    "status": "completed",
                    "content_length": len(document_content),
                    "file_size": file_size
                }
                
                await notify_backend_status(
                    self.backend_url,
                    self.task_id,
                    {
                        "taskName": "Document Content Extracted",
                        "taskFriendlyName": f"Extracted {len(document_content)} characters",
                    }
                )
                
            except Exception as e:
                error_msg = f"Content extraction failed: {str(e)}"
                logger.error(error_msg)
                return await self._handle_workflow_error(error_msg, "content_extraction")

            # Step 3: Fast bypass check
            try:
                logger.info("Step 3: Performing fast bypass check")
                
                # Check if document is too small or empty (fast bypass)
                if file_size < 1000 or len(document_content.strip()) < 50:
                    logger.info("Document bypassed due to insufficient content")
                    
                    bypass_result = {
                        "status": "completed",
                        "is_relevant": False,
                        "relevance_score": 0.0,
                        "classification_reasons": ["Document contains insufficient content for meaningful analysis"],
                        "bypass_reason": "insufficient_content",
                        "processing_method": "fast_bypass"
                    }
                    
                    steps["fast_bypass"] = {"status": "applied", "reason": "insufficient_content"}
                    
                    # Format and save result
                    formatted_result = format_classification_result(bypass_result, self.task_id, self.project_id)
                    await LocalStorageManager.save_response(self.task_id, formatted_result)
                    
                    # Notify completion
                    await notify_backend_completion(self.backend_url, self.task_id, formatted_result)
                    
                    return {
                        "status": "completed",
                        "message": "Document classification completed (fast bypass)",
                        "steps": steps,
                        "results": bypass_result
                    }
                
                steps["fast_bypass"] = {"status": "skipped", "reason": "document_needs_analysis"}
                
            except Exception as e:
                logger.warning(f"Fast bypass check failed, continuing with full analysis: {str(e)}")

            # Step 4: Agent-based classification
            try:
                logger.info("Step 4: Running agent-based classification")
                
                await notify_backend_status(
                    self.backend_url,
                    self.task_id,
                    {
                        "taskName": "AI Agent Classification Started",
                        "taskFriendlyName": "AI agents analyzing document relevance",
                    }
                )
                
                classification_result = await self.classification_task.classify_document(
                    content=document_content,
                    project_metadata=self.project_metadata,
                    file_path=self.file_path,
                    classification_threshold=self.classification_threshold
                )
                
                if classification_result.get("status") != "completed":
                    error_msg = f"Classification failed: {classification_result.get('error', 'Unknown error')}"
                    return await self._handle_workflow_error(error_msg, "agent_classification")
                
                steps["agent_classification"] = {
                    "status": "completed",
                    "is_relevant": classification_result.get("is_relevant"),
                    "relevance_score": classification_result.get("relevance_score")
                }
                
                await notify_backend_status(
                    self.backend_url,
                    self.task_id,
                    {
                        "taskName": "AI Agent Classification Completed",
                        "taskFriendlyName": f"Document classified as {'relevant' if classification_result.get('is_relevant') else 'not relevant'}",
                    }
                )
                
            except Exception as e:
                error_msg = f"Agent classification failed: {str(e)}"
                logger.error(error_msg)
                return await self._handle_workflow_error(error_msg, "agent_classification")

            # Step 5: Format and save final results
            try:
                logger.info("Step 5: Formatting and saving results")
                
                # Format result for API response
                formatted_result = format_classification_result(
                    classification_result, 
                    self.task_id, 
                    self.project_id
                )
                
                # Save to storage
                await LocalStorageManager.save_response(self.task_id, formatted_result)
                
                # Send completion notification
                await notify_backend_completion(self.backend_url, self.task_id, formatted_result)
                
                return {
                    "status": "completed",
                    "message": "Document classification workflow completed successfully",
                    "steps": steps,
                    "results": classification_result
                }
                
            except Exception as e:
                error_msg = f"Result formatting failed: {str(e)}"
                logger.error(error_msg)
                return await self._handle_workflow_error(error_msg, "result_formatting")

        except Exception as e:
            error_msg = f"Document Classification Workflow execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return await self._handle_workflow_error(error_msg, "workflow_execution")

    async def _handle_workflow_error(self, error_msg: str, stage: str) -> Dict[str, Any]:
        """
        Handle workflow errors with consistent error response format
        
        Args:
            error_msg (str): Error message
            stage (str): Stage where error occurred
            
        Returns:
            Dict: Error result
        """
        logger.error(f"Workflow error in {stage}: {error_msg}")
        
        # Create error result
        error_result = {
            "status": "failed",
            "message": error_msg,
            "stage": stage,
            "task_id": self.task_id,
            "project_id": self.project_id
        }
        
        # Notify backend of workflow failure
        if self.backend_url and self.task_id:
            try:
                # Save error to local storage
                await LocalStorageManager.save_response(self.task_id, error_result)
                
                # Send error notification
                await notify_backend_status(
                    self.backend_url,
                    self.task_id,
                    {
                        "taskName": "classification_failed",
                        "message": error_msg
                    }
                )
                
                logger.info(f"Sent classification_failed notification for task: {self.task_id}")
            except Exception as notify_error:
                logger.error(f"Error sending failure notification: {str(notify_error)}")
        
        return error_result