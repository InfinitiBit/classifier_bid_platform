from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# For report + subtask & failed status like rfq


class ReportDetailed(BaseModel):
    attributeName: str
    attributeFriendlyName: str
    attributeValue: str


class ClassificationResult(BaseModel):
    """Classification result details"""
    isValid: bool
    classificationReport: List[ReportDetailed]


class ClassificationResultImmediate(BaseModel):
    """Classification result details"""
    task_id = str
    status = str
    message = str
    error = str

    # summaryDecision: str  # 'Invalid', 'Irrelevant', 'Not Enough Content', 'relevent'
    # decisionDetails: str  # Why AI thinks it's invalid/irrelevant/etc
    # relevancyPercentage: int # 0-100%
