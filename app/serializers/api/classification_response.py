from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    """Classification result details"""
    fileId: str
    summaryDecision: str  # 'Invalid', 'Irrelevant', 'Not Enough Content'
    decisionDetails: str  # Why AI thinks it's invalid/irrelevant/etc
    relevancyPercentage: float = Field(ge=0.0, le=100.0)  # 0-100%