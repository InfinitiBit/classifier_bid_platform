from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# For report + subtask & failed status like rfq
class ReportDetailed(BaseModel):
    """Single report detail item"""
    attributeName: str
    attributeFriendlyName: str
    attributeValue: str


class ClassificationResult(BaseModel):
    """Classification result with completion report"""
    isValid: bool
    classificationReport: List[ReportDetailed]


class ClassificationStatusResponse(BaseModel):
    """Status update during workflow execution"""
    status: str
    message: str
    taskName: Optional[str] = Field(None, description="Task/step name or 'task_failed' for errors")


class ClassificationResultImmediate(BaseModel):
    """Immediate classification result for errors or quick responses"""
    taskId: str
    status: str
    message: str
    error: Optional[str] = None

    # Optional fields for completed classification results
    summaryDecision: Optional[str] = None  # 'relevant', 'irrelevant', 'invalid', 'not_enough_content'
    decisionDetails: Optional[str] = None  # Why AI thinks it's invalid/irrelevant/etc
    relevancyPercentage: Optional[int] = None  # 0-100%
