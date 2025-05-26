from crewai import Agent

class DocumentRelevanceAgent(Agent):
    """Agent specialized in determining document relevance based on content analysis"""
    
    def __init__(self):
        super().__init__(
            role="Document Relevance Analyst",
            goal="Analyze document content to determine relevance for project requirements",
            backstory="""You are an expert document analyst with years of experience in 
            evaluating technical documents, proposals, and project specifications. You excel 
            at quickly identifying key themes, technologies, and project scopes within documents 
            to determine their relevance to specific project requirements.""",
            verbose=True,
            allow_delegation=False,
            llm="azure/gpt-4o-mini",
            max_iter=1,
            max_retry_limit=1,
        )