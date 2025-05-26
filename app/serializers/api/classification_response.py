"""
Response models for document classification API
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class DocumentClassificationResponse(BaseModel):
    """Response model for document classification"""
    task_id: str = Field(..., description="Task identifier")
    project_id: str = Field(..., description="Project identifier")
    status: str = Field(..., description="Classification status ('processing', 'completed', 'failed', 'error')")
    message: str = Field(..., description="Status message")
    is_relevant: Optional[bool] = Field(None, description="Whether document is relevant to project")
    relevance_score: Optional[float] = Field(None, description="Relevance score (0.0-1.0)")
    classification_reasons: Optional[List[str]] = Field(None, description="List of reasons for classification decision")
    processing_method: Optional[str] = Field(None, description="Processing method used ('fast_bypass' or 'full_agent_analysis')")
    timestamp: Optional[str] = Field(None, description="Processing timestamp")
    error: Optional[str] = Field(None, description="Error message if classification failed")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "classify_2025_001",
                "project_id": "healthcare_ai_project",
                "status": "completed",
                "message": "Document classification completed successfully",
                "is_relevant": True,
                "relevance_score": 0.85,
                "classification_reasons": [
                    "Document summary: Healthcare AI system for medical diagnosis and patient management...",
                    "Relevance analysis: Strong alignment with healthcare AI development project scope...",
                    "Matching aspects: python, tensorflow, medical, diagnosis, healthcare technologies found",
                    "Final decision: RELEVANT - High technology and keyword match with project requirements"
                ],
                "processing_method": "full_agent_analysis",
                "timestamp": "2025-01-20T10:30:00Z",
                "error": None
            }
        }

class ClassificationStatusResponse(BaseModel):
    """Response model for classification status queries"""
    task_id: str = Field(..., description="Task identifier")
    project_id: Optional[str] = Field(None, description="Project identifier")
    status: str = Field(..., description="Current task status")
    is_relevant: Optional[bool] = Field(None, description="Whether document is relevant (available when completed)")
    relevance_score: Optional[float] = Field(None, description="Relevance score (available when completed)")
    classification_reasons: Optional[List[str]] = Field(None, description="Classification reasoning (available when completed)")
    processing_method: Optional[str] = Field(None, description="Processing method used")
    file_info: Optional[Dict[str, Any]] = Field(None, description="Information about the processed file")
    project_metadata: Optional[Dict[str, Any]] = Field(None, description="Project metadata used for classification")
    extracted_info: Optional[Dict[str, Any]] = Field(None, description="Information extracted during classification")
    timestamp: Optional[str] = Field(None, description="Last update timestamp")
    error: Optional[str] = Field(None, description="Error message if failed")

class ClassificationSummaryResponse(BaseModel):
    """Response model for classification summary/statistics"""
    total_classifications: int = Field(..., description="Total number of classifications performed")
    relevant_documents: int = Field(..., description="Number of documents classified as relevant")
    irrelevant_documents: int = Field(..., description="Number of documents classified as irrelevant")
    fast_bypass_count: int = Field(..., description="Number of documents processed via fast bypass")
    full_analysis_count: int = Field(..., description="Number of documents requiring full agent analysis")
    average_relevance_score: float = Field(..., description="Average relevance score across all classifications")
    common_technologies: List[str] = Field(default=[], description="Most commonly found technologies")
    common_industries: List[str] = Field(default=[], description="Most commonly found industries")