from typing import List, Optional
from pydantic import BaseModel, Field

class ClassificationResult(BaseModel):
    """Classification result details"""
    fileId: str
    summaryDecision: str  # 'Invalid', 'Irrelevant', 'Not Enough Content'
    decisionDetails: str  # Why AI thinks it's invalid/irrelevant/etc
    relevancyPercentage: float = Field(ge=0.0, le=100.0)  # 0-100%

class DocumentClassificationResponse(BaseModel):
    """Response model for document classification"""
    task_id: str
    project_id: str
    status: str
    message: str
    error: Optional[str] = None

class ClassificationStatusResponse(BaseModel):
    """Response model for classification status"""
    task_id: str
    project_id: str
    status: str
    is_relevant: Optional[bool] = None
    relevance_score: Optional[float] = None
    classification_reasons: Optional[List[str]] = None
    processing_method: Optional[str] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None