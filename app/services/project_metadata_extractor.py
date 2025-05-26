"""
Project metadata models matching the new structure provided
"""
from typing import List, Optional
from pydantic import BaseModel, Field

class MetaDataItem(BaseModel):
    """Individual metadata attribute"""
    attributeName: str = Field(..., description="Name of the attribute")
    attributeFriendlyName: str = Field(..., description="Human-readable name of the attribute")
    attributeValue: str = Field(..., description="Value of the attribute")

class UserData(BaseModel):
    """User-specific data key-value pairs"""
    dataKey: str = Field(..., description="Data key identifier")
    dataValue: str = Field(..., description="Data value")

class BidManager(BaseModel):
    """Bid manager information"""
    firstName: str = Field(..., description="Bid manager first name")
    lastName: str = Field(..., description="Bid manager last name")
    email: str = Field(..., description="Bid manager email address")
    userData: List[UserData] = Field(default=[], description="Additional user data")

class Project(BaseModel):
    """Project information for document classification"""
    id: str = Field(..., description="Unique project identifier")
    referenceNumber: Optional[str] = Field(None, description="Project reference number")
    opportunityName: Optional[str] = Field(None, description="Name of the opportunity")
    description: Optional[str] = Field(None, description="Project description")
    projectName: Optional[str] = Field(None, description="Project name")
    status: Optional[int] = Field(None, description="Project status code")
    bidManager: Optional[BidManager] = Field(None, description="Bid manager details")
    currentStage: Optional[str] = Field(None, description="Current project stage")
    opportunityOwner: Optional[str] = Field(None, description="Opportunity owner")
    amountInEur: Optional[str] = Field(None, description="Project amount in EUR")
    metaData: List[MetaDataItem] = Field(default=[], description="Project metadata attributes")

    def extract_classification_metadata(self) -> dict:
        """
        Extract metadata for document classification from project data
        """
        # Helper function to get metadata value by attribute name
        def get_metadata_value(attr_name: str) -> Optional[str]:
            for item in self.metaData:
                if item.attributeName.lower() == attr_name.lower():
                    return item.attributeValue
            return None

        # Extract common classification fields
        industry = get_metadata_value("Industry") or get_metadata_value("Vertical 1") or "Unknown"
        project_type = get_metadata_value("Product Type") or get_metadata_value("Project Type") or "Unknown"
        country_customer = get_metadata_value("Country of Customer")
        country_installation = get_metadata_value("Country of Installation")
        execution_unit = get_metadata_value("Execution Unit")
        
        # Extract technologies and keywords from various metadata fields
        technologies = []
        keywords = []
        
        # Add project-related terms
        if self.opportunityName:
            keywords.extend(self.opportunityName.lower().split())
        if self.description:
            keywords.extend(self.description.lower().split()[:10])  # First 10 words
            
        # Add metadata values as keywords
        for item in self.metaData:
            if item.attributeName in ["Product Type", "Execution Unit", "Industry"]:
                keywords.extend(item.attributeValue.lower().split())
                
        # Add technical terms based on industry and product type
        if "power" in industry.lower() or "energy" in industry.lower():
            technologies.extend(["power systems", "electrical engineering", "energy"])
            keywords.extend(["power", "energy", "electrical", "grid", "generation"])
            
        if "grid" in project_type.lower():
            technologies.extend(["grid analysis", "power grid", "electrical grid"])
            keywords.extend(["grid", "analysis", "planning", "electrical"])
            
        # Build location string
        location_parts = []
        if country_customer:
            location_parts.append(f"Customer: {country_customer}")
        if country_installation:
            location_parts.append(f"Installation: {country_installation}")
        location = ", ".join(location_parts) if location_parts else None
        
        # Build requirements from metadata
        requirements = []
        for item in self.metaData:
            if item.attributeName in ["Requirements", "Compliance", "Standards"]:
                requirements.append(item.attributeValue)
                
        return {
            "project_type": project_type,
            "industry": industry,
            "technologies": list(set(technologies)),  # Remove duplicates
            "keywords": list(set(keywords)),  # Remove duplicates
            "budget_range": self.amountInEur,
            "timeline": get_metadata_value("Timeline") or get_metadata_value("Close Date"),
            "location": location,
            "requirements": requirements,
            "execution_unit": execution_unit,
            "opportunity_owner": self.opportunityOwner,
            "project_stage": self.currentStage
        }

class AnalysisDetail(BaseModel):
    """Analysis detail information"""
    detailedReportId: str = Field(..., description="Detailed report identifier")
    area: str = Field(..., description="Analysis area")
    decision: Optional[str] = Field(None, description="Decision made")
    description: str = Field(..., description="Analysis description")

class AnalysisReportItem(BaseModel):
    """Analysis report item"""
    metaDataId: str = Field(..., description="Metadata identifier")
    attributeName: str = Field(..., description="Attribute name")
    attributeFriendlyName: Optional[str] = Field(None, description="Friendly attribute name")
    reference: Optional[str] = Field(None, description="Reference information")
    analysisSummary: Optional[str] = Field(None, description="Analysis summary")
    analysisDetails: List[AnalysisDetail] = Field(default=[], description="Detailed analysis")

class Question(BaseModel):
    """Question and answer pair"""
    question: str = Field(..., description="Question text")
    answer: str = Field(..., description="Answer text")

class EnhancedClassificationRequest(BaseModel):
    """Enhanced request model using the new project structure"""
    taskId: str = Field(..., description="Unique task identifier")
    project: Project = Field(..., description="Project information")
    document_url: str = Field(..., description="URL to the document to classify")
    classification_threshold: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="Classification threshold")
    analysisReport: List[AnalysisReportItem] = Field(default=[], description="Analysis report data")
    questions: List[Question] = Field(default=[], description="Questions and answers")

    class Config:
        json_schema_extra = {
            "example": {
                "taskId": "GC25_047_classification_001",
                "project": {
                    "id": "GC25_047",
                    "referenceNumber": "GC25_047_Amiral_FRTDraft",
                    "opportunityName": "Plant Controller and Voltage Compliance for Antwerp Zandvliet",
                    "projectName": "Antwerp Zandvliet Power Project",
                    "amountInEur": "€10,000.00",
                    "currentStage": "Bid Preparation",
                    "opportunityOwner": "Ara Panosyan",
                    "metaData": [
                        {
                            "attributeName": "Country of Customer",
                            "attributeFriendlyName": "Customer Country",
                            "attributeValue": "Germany"
                        },
                        {
                            "attributeName": "Country of Installation", 
                            "attributeFriendlyName": "Installation Country",
                            "attributeValue": "Saudi Arabia"
                        },
                        {
                            "attributeName": "Vertical 1",
                            "attributeFriendlyName": "Primary Industry",
                            "attributeValue": "Conventional Power Generation"
                        },
                        {
                            "attributeName": "Product Type",
                            "attributeFriendlyName": "Product Category",
                            "attributeValue": "Grid Analysis and Planning"
                        }
                    ]
                },
                "document_url": "https://example.com/technical-specification.pdf",
                "classification_threshold": 0.7
            }
        }