from typing import List, Optional
from pydantic import BaseModel, Field


class MetaDataItem(BaseModel):
    attributeName: str
    attributeFriendlyName: str
    attributeValue: str


class UserData(BaseModel):
    dataKey: str
    dataValue: str


class BidManager(BaseModel):
    firstName: str
    lastName: str
    email: str
    userData: List[UserData] = []


class Project(BaseModel):
    id: str
    referenceNumber: Optional[str] = None
    opportunityName: Optional[str] = None
    description: Optional[str] = None
    projectName: Optional[str] = None
    status: Optional[int] = None
    bidManager: Optional[BidManager] = None
    currentStage: Optional[str] = None
    opportunityOwner: Optional[str] = None
    amountInEur: Optional[str] = None
    metaData: List[MetaDataItem] = []


class UploadedFile(BaseModel):
    """Document information for classification"""
    Reference: str
    FileUrl: str


class DocumentClassificationRequest(BaseModel):
    """Request model for document classification"""
    taskId: str
    project: Project
    document: UploadedFile
