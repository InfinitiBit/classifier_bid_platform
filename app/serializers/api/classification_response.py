from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """File information from processing"""
    fileName: str
    fileSize: int
    fileType: str
    extractedLength: Optional[int] = None


class ClassificationResult(BaseModel):
    """Classification result details"""
    isRelevant: bool
    relevanceScore: float = Field(ge=0.0, le=1.0)
    classificationReasons: List[str] = []
    processingMethod: str  # 'fast_bypass' or 'agent_classification'
    confidenceLevel: Optional[str] = None  # high, medium, low


class DocumentClassificationResponse(BaseModel):
    """Response model for document classification"""
    taskId: str
    projectId: str
    status: str  # 'processing', 'completed', 'failed', 'error'
    message: str
    classificationResult: Optional[ClassificationResult] = None
    fileInfo: Optional[FileInfo] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None


class ClassificationStatusResponse(BaseModel):
    """Response model for classification status queries"""
    taskId: str
    projectId: Optional[str] = None
    status: str
    classificationResult: Optional[ClassificationResult] = None
    fileInfo: Optional[FileInfo] = None
    projectMetaData: Optional[List[Dict[str, Any]]] = None
    extractedInfo: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None


class ClassificationSummaryResponse(BaseModel):
    """Response model for classification summary/statistics"""
    totalClassifications: int
    relevantDocuments: int
    irrelevantDocuments: int
    fastBypassCount: int
    fullAnalysisCount: int
    averageRelevanceScore: float = Field(ge=0.0, le=1.0)
    commonTechnologies: List[str] = []
    commonIndustries: List[str] = []