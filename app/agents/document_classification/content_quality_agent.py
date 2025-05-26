from crewai import Agent

class ContentQualityAgent(Agent):
    """Agent specialized in assessing document content quality and completeness"""
    
    def __init__(self):
        super().__init__(
            role="Content Quality Assessor",
            goal="Evaluate document content quality, completeness, and extract key summary information",
            backstory="""You are an expert in document quality assessment with deep experience 
            in evaluating technical documents for completeness, clarity, and information density. 
            You can quickly identify blank documents, low-quality scans, incomplete content, 
            and extract meaningful summaries from well-structured documents. You excel at 
            determining whether a document contains sufficient information for analysis.""",
            verbose=True,
            allow_delegation=False,
            llm="azure/gpt-4o-mini",
            max_iter=1,
            max_retry_limit=1,
        )