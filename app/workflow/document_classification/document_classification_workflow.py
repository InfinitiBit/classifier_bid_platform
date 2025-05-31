"""
Main workflow processor for document classification.
Orchestrates the entire workflow from document download to relevance classification.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import sys
from datetime import datetime

# Add project root to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.utils.storage import LocalStorageManager
from app.utils.backend_notify_completion import notify_backend_completion
from app.utils.backend_notify_status import notify_backend_status
from app.utils.logging import setup_logging
from app.agent_tasks.document_classification.document_classification_task import DocumentClassificationTask
from app.config import EXTRACTED_DIR
from app.serializers.api.classification_request import Project

# Import workflow helpers
from app.workflow.document_classification.helper_methods.document_processor import (
    extract_document_content,
    format_classification_result
)

# Import models
from app.serializers.api.classification_response import ClassificationStatusResponse, ClassificationResult, ReportDetailed

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
        project: Project,  # Changed from project_metadata dict to Project object
        classification_threshold: float
    ):
        """
        Initialize the document classification workflow.

        Args:
            task_id (str): Task identifier for backend communication
            project_id (str): Project identifier
            backend_url (str): URL for backend API
            file_path (str): Path to the document file
            project (Project): Project object containing all project data
            classification_threshold (float): Threshold for relevance classification
        """
        self.task_id = task_id
        self.project_id = project_id
        self.backend_url = backend_url
        self.file_path = file_path
        self.project = project
        self.classification_threshold = classification_threshold
        self.base_dir = EXTRACTED_DIR

        # Extract metadata from project object
        self.project_metadata = self._extract_project_metadata(project)
        logger.info(f"Extracted project metadata: {self.project_metadata}")

        # Track workflow data for final report
        self.workflow_data = {
            "start_time": datetime.utcnow(),
            "steps_completed": [],
            "file_size": None,
            "content_length": None,
            "classification_method": None,
            "classification_result": None,
            "relevance_score": None,
            "bypass_reason": None,
            "errors": []
        }

        # Initialize classification task
        self.classification_task = DocumentClassificationTask(
            output_base_dir=str(EXTRACTED_DIR),
            task_id=task_id,
            backend_url=backend_url
        )

        logger.info(f"Initialized DocumentClassificationWorkflow for task: {task_id}")

    def _extract_project_metadata(self, project: Project) -> Dict[str, Any]:
        """Extract metadata from project for classification"""
        # Start with basic project information
        metadata = {
            "project_id": project.id,
            "project_name": project.projectName or project.opportunityName or "Unnamed Project",
            "description": project.description or "",
            "reference_number": project.referenceNo or "",
            "bid_manager": project.bidManager or ""
        }

        # Add all attributes (previously metaData)
        if project.attributes:
            for item in project.attributes:
                # Use attributeFriendlyName as the key for agent analysis
                metadata[item.attributeFriendlyName] = item.attributeValue

        return metadata

    async def _send_status_update(self, taskFriendlyName: str, message: str, task_name: str = None):
        """
        Send real-time status update using classificationStatusResponse model.

        Args:
            status (str): Status code (e.g., "processing", "completed", "failed")
            message (str): Human-readable status message
            task_name (str): Task/step name or "task_failed" for errors
        """
        # Prepare status update data
        status_data = {
            "taskFriendlyName": taskFriendlyName,
            "message": message
        }

        # Add taskName if provided
        if task_name:
            status_data["taskName"] = task_name

        # Send status update to backend
        await notify_backend_status(
            self.backend_url,
            self.task_id,
            status_data
        )

        logger.info(f"Status update sent: {taskFriendlyName} - {message} (taskName: {task_name})")

    def _build_completion_report(self, is_fast_bypass: bool = False) -> List[Dict[str, str]]:
        """
        Build the final completion report based on workflow execution.

        Args:
            is_fast_bypass (bool): Whether this is a fast bypass completion

        Returns:
            List[Dict]: List of ReportDetailed entries as dictionaries
        """
        report_items = []

        # 1. Summary Decision
        if is_fast_bypass:
            summary_decision = "Not Enough Content"
        else:
            # Determine based on classification result
            is_relevant = self.workflow_data.get("classification_result", False)
            is_valid = self.workflow_data.get("is_valid", True)

            if not is_valid:
                summary_decision = "Invalid"
            elif is_relevant:
                summary_decision = "Relevant"
            else:
                summary_decision = "Irrelevant"

        report_items.append(ReportDetailed(
            attributeName="summaryDecision",
            attributeFriendlyName="Summary Decision",
            attributeValue=summary_decision
        ).dict())

        # 2. Decision Details
        if is_fast_bypass:
            decision_details = "Document contains insufficient content for meaningful analysis"
        else:
            # Get decision details from classification result or workflow data
            decision_details = self.workflow_data.get(
                "decision_details",
                self.workflow_data.get(
                    "classification_reasons",
                    f"Document was analyzed and determined to be {summary_decision.lower()}"
                )
            )

        report_items.append(ReportDetailed(
            attributeName="decisionDetails",
            attributeFriendlyName="Decision Details",
            attributeValue=decision_details
        ).dict())

        # 3. Relevancy Percentage
        if is_fast_bypass:
            relevancy_percentage = 0
        else:
            # Convert relevance score to percentage (0-100)
            relevance_score = self.workflow_data.get("relevance_score", 0.0)
            relevancy_percentage = int(relevance_score * 100) if relevance_score else 0

        report_items.append(ReportDetailed(
            attributeName="relevancyPercentage",
            attributeFriendlyName="Relevancy Percentage",
            attributeValue=str(relevancy_percentage)
        ).dict())

        return report_items

    async def process_classification(self) -> Dict[str, Any]:
        """
        Process the complete document classification workflow.

        Returns:
            Dict: Workflow result with classification decision
        """
        try:
            logger.info(f"Starting document classification workflow for task: {self.task_id}")

            # Send initial status
            await self._send_status_update(
                taskFriendlyName="processing",
                message="Document classification workflow started",
                task_name="workflow_start"
            )

            steps = {}

            # Step 1: Extract document content
            try:
                logger.info("Step 1: Extracting document content")

                # Send status update
                await self._send_status_update(
                    taskFriendlyName="processing",
                    message="Extracting content from document",
                    task_name="content_extraction"
                )

                content_result = extract_document_content(self.file_path, task_id=self.task_id)

                if not content_result["extraction_success"]:
                    error_msg = f"Content extraction failed: {content_result.get('error', 'Unknown error')}"

                    # Status update for failure
                    await self._send_status_update(
                        taskFriendlyName="failed",
                        message=f"Error in content_extraction: {content_result.get('error')}",
                        task_name="task_failed"
                    )

                    self.workflow_data["errors"].append(error_msg)
                    return await self._handle_workflow_error(error_msg, "content_extraction")

                document_content = content_result["content"]
                file_size = content_result["file_size"]

                # print("content result --------- ", content_result)

                # Update workflow data
                self.workflow_data["file_size"] = file_size
                self.workflow_data["content_length"] = len(document_content)
                self.workflow_data["steps_completed"].append("content_extraction")

                steps["content_extraction"] = {
                    "status": "completed",
                    "content_length": len(document_content),
                    "file_size": file_size
                }

                # Status update for success
                await self._send_status_update(
                    taskFriendlyName="processing",
                    message=f"Content extracted successfully: {len(document_content)} characters",
                    task_name="content_extraction_completed"
                )

            except Exception as e:
                error_msg = f"Content extraction failed: {str(e)}"
                logger.error(error_msg)

                await self._send_status_update(
                    taskFriendlyName="failed",
                    message=f"Error in content_extraction: {str(e)}",
                    task_name="task_failed"
                )

                self.workflow_data["errors"].append(error_msg)
                return await self._handle_workflow_error(error_msg, "content_extraction")

            # Step 2: Fast bypass check
            try:
                logger.info("Step 2: Performing fast bypass check")

                await self._send_status_update(
                    taskFriendlyName="processing",
                    message="Checking document size for fast bypass",
                    task_name="fast_bypass_check"
                )

                # Check if document is too small or empty (fast bypass)
                if file_size < 1000 or len(document_content.strip()) < 50:
                    logger.info("Document bypassed due to insufficient content")

                    # Update workflow data for fast bypass
                    self.workflow_data["classification_method"] = "fast_bypass"
                    self.workflow_data["classification_result"] = False
                    self.workflow_data["bypass_reason"] = "insufficient_content"
                    self.workflow_data["steps_completed"].append("fast_bypass")

                    # Build completion report for fast bypass
                    completion_report = self._build_completion_report(is_fast_bypass=True)

                    # Create final result
                    final_result = ClassificationResult(
                        isValid=False,
                        attributes=completion_report
                    )

                    # Format for backend
                    formatted_result = final_result.dict()
                    # formatted_result.update({
                    #     "task_id": self.task_id,
                    #     "project_id": self.project_id
                    # })

                    # Save and notify completion
                    await LocalStorageManager.save_response(self.task_id, formatted_result)
                    await notify_backend_completion(self.backend_url, self.task_id, formatted_result)

                    # Send final status
                    await self._send_status_update(
                        taskFriendlyName="completed",
                        message="Document classified via fast bypass: insufficient content",
                        task_name="fast_bypass_completed"
                    )

                    return {
                        "status": "completed",
                        "message": "Document classification completed (fast bypass)",
                        "steps": steps,
                        "results": {
                            "is_relevant": False,
                            "isValid": False,
                            "bypass_reason": "insufficient_content",
                            "processing_method": "fast_bypass"
                        }
                    }

                # Fast bypass not applied
                steps["fast_bypass"] = {"status": "skipped", "reason": "document_needs_analysis"}

                await self._send_status_update(
                    taskFriendlyName="processing",
                    message="Fast bypass skipped - proceeding to full analysis",
                    task_name="fast_bypass_skipped"
                )

            except Exception as e:
                logger.warning(f"Fast bypass check failed, continuing with full analysis: {str(e)}")

            # Step 3: Agent-based classification
            try:
                logger.info("Step 3: Running agent-based classification")

                await self._send_status_update(
                    taskFriendlyName="processing",
                    message="AI agents analyzing document relevance",
                    task_name="agent_classification"
                )

                # print("document_content", document_content[:50])
                classification_result = await self.classification_task.classify_document(
                    content=document_content,
                    project_metadata=self.project_metadata,
                    file_path=self.file_path,
                    classification_threshold=self.classification_threshold
                )
                # logger.info("classification_result ------------------------- ", classification_result)

                if classification_result.get("status") != "completed":
                    error_msg = f"Classification failed: {classification_result.get('error', 'Unknown error')}"

                    await self._send_status_update(
                        taskFriendlyName="failed",
                        message=f"Error in agent_classification: {classification_result.get('error')}",
                        task_name="task_failed"
                    )

                    self.workflow_data["errors"].append(error_msg)
                    return await self._handle_workflow_error(error_msg, "agent_classification")

                # Update workflow data
                self.workflow_data["classification_method"] = "agent_classification"
                self.workflow_data["classification_result"] = classification_result.get("is_relevant", False)
                self.workflow_data["is_valid"] = classification_result.get("isValid", True)
                self.workflow_data["relevance_score"] = classification_result.get("relevance_score")
                self.workflow_data["decision_details"] = classification_result.get(
                    "classification_reasons",
                    classification_result.get("decision_details", "")
                )
                if isinstance(self.workflow_data["decision_details"], list):
                    self.workflow_data["decision_details"] = "; ".join(self.workflow_data["decision_details"])
                self.workflow_data["steps_completed"].append("agent_classification")

                steps["agent_classification"] = {
                    "status": "completed",
                    "is_relevant": classification_result.get("is_relevant"),
                    "relevance_score": classification_result.get("relevance_score")
                }

                # Status update
                relevance_status = "relevant" if classification_result.get("is_relevant") else "not relevant"
                await self._send_status_update(
                    taskFriendlyName="processing",
                    message=f"Document classified as {relevance_status}",
                    task_name="classification_completed"
                )

            except Exception as e:
                error_msg = f"Agent classification failed: {str(e)}"
                logger.error(error_msg)

                await self._send_status_update(
                    taskFriendlyName="failed",
                    message=f"Error in agent_classification: {str(e)}",
                    task_name="task_failed"
                )

                self.workflow_data["errors"].append(error_msg)
                return await self._handle_workflow_error(error_msg, "agent_classification")

            # Step 4: Complete workflow and send final report
            try:
                logger.info("Step 4: Finalizing classification results")

                await self._send_status_update(
                    taskFriendlyName="processing",
                    message="Finalizing classification results",
                    task_name="finalization"
                )

                # Mark final step as completed
                self.workflow_data["steps_completed"].append("finalization")

                # Build completion report for full workflow
                completion_report = self._build_completion_report(is_fast_bypass=False)

                # Create final classification result
                final_result = ClassificationResult(
                    isValid=classification_result.get("isValid", classification_result.get("is_relevant", False)),
                    attributes=completion_report
                )

                # Format for backend
                formatted_result = final_result.dict()
                # formatted_result.update({
                #     "task_id": self.task_id,
                #     "project_id": self.project_id
                # })

                # Save to storage
                await LocalStorageManager.save_response(self.task_id, formatted_result)

                # Send completion notification
                await notify_backend_completion(self.backend_url, self.task_id, formatted_result)

                # Send final status update
                await self._send_status_update(
                    taskFriendlyName="completed",
                    message="Document classification completed successfully",
                    task_name="workflow_completed"
                )

                return {
                    "status": "completed",
                    "message": "Document classification workflow completed successfully",
                    "steps": steps,
                    "results": classification_result
                }

            except Exception as e:
                error_msg = f"Result formatting failed: {str(e)}"
                logger.error(error_msg)

                await self._send_status_update(
                    taskFriendlyName="failed",
                    message=f"Error in result_formatting: {str(e)}",
                    task_name="task_failed"
                )

                self.workflow_data["errors"].append(error_msg)
                return await self._handle_workflow_error(error_msg, "result_formatting")

        except Exception as e:
            error_msg = f"Document Classification Workflow execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            await self._send_status_update(
                taskFriendlyName="failed",
                message=f"Error in workflow_execution: {str(e)}",
                task_name="task_failed"
            )

            self.workflow_data["errors"].append(error_msg)
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

        # Note: Error status update is already sent before calling this method
        # No completion report for errors - only status update with taskName: "task_failed"

        # Create error result
        error_result = {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "status": "failed",
            "error_stage": stage,
            "error_message": error_msg
        }

        # Save error to local storage
        if self.backend_url and self.task_id:
            try:
                await LocalStorageManager.save_response(self.task_id, error_result)
                logger.info(f"Saved error result for task: {self.task_id}")
            except Exception as notify_error:
                logger.error(f"Error saving failure result: {str(notify_error)}")
        
        return error_result