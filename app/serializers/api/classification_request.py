from typing import List, Optional
from pydantic import BaseModel, Field


class MetaDataAttribute(BaseModel):
    """Generic metadata attribute structure"""
    attributeName: str
    attributeFriendlyName: Optional[str] = None
    attributeValue: str


class DocumentInfo(BaseModel):
    """Document information for classification"""
    documentId: str
    documentUrl: str  # URL or base64 encoded content
    documentName: Optional[str] = None
    documentType: Optional[str] = None
    fileSize: Optional[int] = None


class ProjectInfo(BaseModel):
    """Project information for document relevance comparison"""
    projectId: str
    projectName: str
    projectDescription: Optional[str] = None
    metaData: List[MetaDataAttribute] = []


class ClassificationResult(BaseModel):
    """Classification result structure"""
    isRelevant: bool
    relevanceScore: float = Field(ge=0.0, le=1.0)
    classificationReasons: List[str] = []
    processingMethod: str = "agent_classification"
    confidenceLevel: Optional[str] = None  # high, medium, low


class DocumentClassificationRequest(BaseModel):
    """Request model for document classification"""
    taskId: str
    project: ProjectInfo
    document: DocumentInfo
    classificationThreshold: float = Field(default=0.7, ge=0.0, le=1.0)