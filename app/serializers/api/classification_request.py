from typing import List, Optional
from pydantic import BaseModel, Field


class MetaDataItem(BaseModel):
    attributeName: str
    attributeFriendlyName: str
    attributeValue: str


class Project(BaseModel):
    id: str
    referenceNo: Optional[str] = None
    opportunityName: Optional[str] = None
    description: Optional[str] = None
    projectName: Optional[str] = None
    bidManager: Optional[str] = None
    attributes: List[MetaDataItem] = []


class UploadedFile(BaseModel):
    """Document information for classification"""
    Reference: str
    FileUrl: str


class DocumentClassificationRequest(BaseModel):
    """Request model for document classification"""
    taskId: str
    project: Project
    document: UploadedFile
