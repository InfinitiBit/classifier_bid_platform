from crewai import Agent

class MetadataMatchingAgent(Agent):
    """Agent specialized in matching document characteristics with project metadata"""
    
    def __init__(self):
        super().__init__(
            role="Metadata Matching Specialist",
            goal="Compare document characteristics against project metadata to determine compatibility",
            backstory="""You are a specialist in project metadata analysis and document 
            classification. You have extensive experience in matching technical requirements, 
            industry standards, and project specifications. You excel at identifying alignment 
            between document content and project metadata including technologies, industry focus, 
            budget constraints, and timeline requirements.""",
            verbose=True,
            allow_delegation=False,
            llm="azure/gpt-4o-mini",
            max_iter=1,
            max_retry_limit=1,
        )