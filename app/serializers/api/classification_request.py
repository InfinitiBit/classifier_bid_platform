"""
Request models for document classification API
"""
from typing import List, Optional
from pydantic import BaseModel, Field

class ProjectMetadata(BaseModel):
    """Project metadata for document classification"""
    project_type: str = Field(..., description="Type of project (e.g., 'AI Development', 'Web Development')")
    industry: str = Field(..., description="Target industry (e.g., 'healthcare', 'finance', 'technology')")
    technologies: List[str] = Field(default=[], description="List of relevant technologies")
    keywords: List[str] = Field(default=[], description="List of important keywords")
    budget_range: Optional[str] = Field(None, description="Budget constraints (e.g., '€50K-100K')")
    timeline: Optional[str] = Field(None, description="Project timeline (e.g., '6 months')")
    location: Optional[str] = Field(None, description="Project location")
    requirements: Optional[List[str]] = Field(default=[], description="Special requirements")

class DocumentClassificationRequest(BaseModel):
    """Request model for document classification"""
    task_id: str = Field(..., description="Unique task identifier")
    project_id: str = Field(..., description="Project identifier")
    document_url: str = Field(..., description="URL to the document to classify or base64 encoded content")
    project_metadata: ProjectMetadata = Field(..., description="Project metadata for comparison")
    classification_threshold: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="Threshold for relevance classification (0.0-1.0)")