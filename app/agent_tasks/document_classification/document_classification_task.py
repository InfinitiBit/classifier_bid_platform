"""
Main class for document classification tasks.
Handles the execution of agent tasks to classify document relevance based on project metadata.
"""
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import logging
import sys
from datetime import datetime
from crewai import Agent, Task, Crew, Process
import requests

# Add project root to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Import agents
from app.agents.document_classification.content_quality_agent import ContentQualityAgent
from app.agents.document_classification.document_summarizer_agent import DocumentSummarizerAgent
from app.agents.document_classification.document_relevance_agent import DocumentRelevanceAgent
from app.agents.document_classification.metadata_matching_agent import MetadataMatchingAgent

# Import helpers
from app.agent_tasks.document_classification.helper_methods.classification_scorer import should_bypass_analysis, combine_agent_results
from app.agent_tasks.document_classification.helper_methods.document_validator import read_file_content

from dotenv import load_dotenv
load_dotenv()

# Configure logging
from app.utils.logging import setup_logging
logger = setup_logging()


class DocumentClassificationTask:
    """
    Task executor for document classification based on project metadata.
    Uses specialized agents to analyze content quality, extract summaries,
    and determine relevance to project requirements.
    """

    def __init__(self, output_base_dir: str, task_id: str = None, backend_url: str = None):
        """
        Initialize document classification task.

        Args:
            output_base_dir (str): Base directory for output files
            task_id (str, optional): Task identifier for backend communication
            backend_url (str, optional): URL for backend API
        """
        self.output_base_dir = Path(output_base_dir).resolve()
        self.task_id = task_id
        self.backend_url = backend_url
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized DocumentClassificationTask with output dir: {self.output_base_dir}")
        self._setup_agents()

    def _setup_agents(self):
        """Initialize agents for classification"""
        try:
            self.content_quality_agent = ContentQualityAgent()
            self.summarizer_agent = DocumentSummarizerAgent()
            self.relevance_agent = DocumentRelevanceAgent()
            self.metadata_matching_agent = MetadataMatchingAgent()
            
            self.logger.info("Successfully initialized document classification agents")
        except Exception as e:
            self.logger.error(f"Error initializing agents: {str(e)}")
            raise

    async def classify_document(
        self, 
        content: str, 
        project_metadata: Dict[str, Any], 
        file_path: str = None,
        classification_threshold: float = 0.7
    ) -> Dict:
        """
        Classify document relevance using specialized agents.

        Args:
            content (str): Document content to analyze
            project_metadata (Dict): Project metadata for comparison
            file_path (str): Path to the document file
            classification_threshold (float): Threshold for relevance classification

        Returns:
            Dict: Results of document classification
        """
        try:
            self.logger.info(f"Starting document classification for task: {self.task_id}")

            # Quick bypass check for low-quality documents
            file_size = None
            if file_path:
                try:
                    file_size = Path(file_path).stat().st_size
                except:
                    pass

            should_bypass, bypass_reason, quick_result = should_bypass_analysis(content, file_size)
            
            if should_bypass:
                self.logger.info(f"Bypassing analysis: {bypass_reason}")
                return {
                    "status": "completed",
                    "bypass_reason": bypass_reason,
                    "is_relevant": quick_result["is_relevant"],
                    "relevance_score": quick_result["relevance_score"],
                    "classification_reasons": quick_result["classification_reasons"],
                    "processing_time": "fast_bypass"
                }

            # Notify backend of agent analysis start
            if self.backend_url and self.task_id:
                try:
                    requests.post(
                        f"{self.backend_url.rstrip('/')}/analyzers/{self.task_id}/subtasks",
                        json={"taskName": "Document Classification Analysis Started",
                              "taskFriendlyName": "AI agents analyzing document relevance"},
                        auth=("admin", "pass123"),
                        timeout=30
                    )
                except Exception as e:
                    self.logger.error(f"Error sending initial status: {str(e)}")

            # Setup directories
            agents_dir = self.output_base_dir / self.task_id / "agents" / "document_classification"
            agents_dir.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"Working with directory: {agents_dir}")

            # Format project metadata for agents
            metadata_str = self._format_project_metadata(project_metadata)
            current_time_str = datetime.now().strftime("%B %d, %Y")

            # Task 1: Content Quality Assessment
            content_quality_task = Task(
                agent=self.content_quality_agent,
                description=f"""
                TODAY'S DATE: {current_time_str}
                
                ANALYZE the document content quality and provide basic assessment:
                1. Content quality assessment (good/fair/poor)
                2. Document readability and structure assessment
                3. Document type classification (RFP, technical spec, proposal, etc.)
                4. Initial content validation
                
                Format your response as:
                QUALITY: [good/fair/poor]
                READABILITY: [high/medium/low]
                DOC_TYPE: [document type]
                VALIDATION: [valid/invalid] - [reason if invalid]
                
                Document Content (first 3000 chars): {content[:3000]}...
                """,
                output_file=str(agents_dir / "content_quality_analysis.txt"),
                expected_output="Structured quality assessment with document type and validation"
            )

            # Task 2: Document Summarization and Key Information Extraction
            summarization_task = Task(
                agent=self.summarizer_agent,
                description=f"""
                TODAY'S DATE: {current_time_str}
                
                Based on the content quality assessment, CREATE a comprehensive summary:
                1. Executive summary (3-4 sentences capturing main purpose and scope)
                2. Key topics and themes identified (list main subjects)
                3. Technologies mentioned (programming languages, frameworks, tools)
                4. Industry focus and domain (healthcare, finance, etc.)
                5. Project requirements and objectives identified
                6. Budget/timeline information if mentioned
                
                Format your response as:
                EXECUTIVE_SUMMARY: [3-4 sentence comprehensive summary]
                KEY_TOPICS: [comma-separated list of main topics]
                TECHNOLOGIES: [comma-separated list of technologies mentioned]
                INDUSTRY_FOCUS: [industry/domain identified]
                REQUIREMENTS: [key requirements identified]
                BUDGET_TIMELINE: [any budget/timeline info found or "Not specified"]
                
                Document Content: {content[:8000]}...
                """,
                output_file=str(agents_dir / "document_summary.txt"),
                expected_output="Comprehensive document summary with extracted key information",
                context=[content_quality_task]
            )

            # Task 3: Document Relevance Analysis
            relevance_task = Task(
                agent=self.relevance_agent,
                description=f"""
                TODAY'S DATE: {current_time_str}
                
                Based on the content quality analysis and document summary, DETERMINE document relevance for our project needs.
                
                ANALYZE alignment between document content and project requirements:
                1. How well does this document match our project scope?
                2. What specific aspects make it relevant or irrelevant?
                3. Rate relevance on scale 1-10 with justification
                4. Consider technology alignment, industry relevance, and project scope matching
                
                Format your response as:
                RELEVANCE_SCORE: [1-10]
                ALIGNMENT: [high/medium/low]
                REASONING: [specific reasons for the score]
                MATCHING_ASPECTS: [list what matches between document and project]
                
                Project Requirements:
                {metadata_str}
                
                Use the document summary for analysis rather than full content.
                """,
                output_file=str(agents_dir / "relevance_analysis.txt"),
                expected_output="Relevance score with detailed reasoning and matching aspects",
                context=[content_quality_task, summarization_task]
            )

            # Task 4: Metadata Matching Analysis
            metadata_matching_task = Task(
                agent=self.metadata_matching_agent,
                description=f"""
                TODAY'S DATE: {current_time_str}
                
                COMPARE document characteristics against specific project metadata criteria using the document summary and relevance analysis.
                
                EVALUATE matches for:
                1. Technology alignment (how many of our technologies are mentioned in the summary?)
                2. Industry relevance (does it fit our industry focus?)
                3. Project type compatibility (matches our project type?)
                4. Keyword presence (how many keywords found in summary?)
                5. Budget and timeline compatibility if specified
                
                Format your response as:
                TECHNOLOGY_MATCH: [percentage]% - [list matched technologies]
                INDUSTRY_MATCH: [high/medium/low] - [explanation]
                PROJECT_TYPE_MATCH: [yes/no] - [reasoning]
                KEYWORD_MATCH: [count]/[total] keywords found - [list found keywords]
                BUDGET_TIMELINE_MATCH: [compatible/not_specified/incompatible] - [explanation]
                OVERALL_SCORE: [0.0-1.0] - [calculated based on all matches]
                FINAL_RECOMMENDATION: [RELEVANT/NOT_RELEVANT] - [justification]
                
                Project Metadata:
                {metadata_str}
                
                Use the document summary and previous analyses for evaluation.
                """,
                output_file=str(agents_dir / "metadata_matching.txt"),
                expected_output="Detailed metadata comparison with final recommendation and overall score",
                context=[content_quality_task, summarization_task, relevance_task]
            )

            # Create crew with all tasks
            crew = Crew(
                agents=[
                    self.content_quality_agent,
                    self.summarizer_agent,
                    self.relevance_agent,
                    self.metadata_matching_agent
                ],
                tasks=[
                    content_quality_task,
                    summarization_task,
                    relevance_task,
                    metadata_matching_task
                ],
                process=Process.sequential,
                verbose=True
            )

            # Execute all tasks
            self.logger.info("Executing document classification tasks")
            results = crew.kickoff()

            # Process and combine results
            classification_result = self._process_agent_results(agents_dir, classification_threshold)

            # Save results
            self._save_results(agents_dir, classification_result)

            return classification_result

        except Exception as e:
            error_msg = f"Error in document classification: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            return {
                "status": "failed",
                "error": error_msg,
                "details": {
                    "stage": "document_classification",
                    "task_id": self.task_id
                }
            }

    def _format_project_metadata(self, metadata: Dict[str, Any]) -> str:
        """Format project metadata for agent consumption"""
        formatted = f"""
Project Type: {metadata.get('project_type', 'Not specified')}
Industry: {metadata.get('industry', 'Not specified')}
Technologies: {', '.join(metadata.get('technologies', []))}
Keywords: {', '.join(metadata.get('keywords', []))}
Budget Range: {metadata.get('budget_range', 'Not specified')}
Timeline: {metadata.get('timeline', 'Not specified')}
Location: {metadata.get('location', 'Not specified')}
Requirements: {', '.join(metadata.get('requirements', []))}
        """
        return formatted.strip()

    def _process_agent_results(self, agents_dir: Path, threshold: float) -> Dict[str, Any]:
        """Process and combine results from all agents"""
        try:
            # Read agent outputs
            content_quality = read_file_content(str(agents_dir / "content_quality_analysis.txt"))
            document_summary = read_file_content(str(agents_dir / "document_summary.txt"))
            relevance = read_file_content(str(agents_dir / "relevance_analysis.txt"))
            metadata_matching = read_file_content(str(agents_dir / "metadata_matching.txt"))

            # Extract final recommendation from metadata matching agent
            is_relevant = "RELEVANT" in metadata_matching.upper() and "NOT_RELEVANT" not in metadata_matching.upper()
            
            # Extract scores using regex patterns
            import re
            
            # Extract relevance score (look for RELEVANCE_SCORE: X pattern)
            relevance_score = 0.5  # default
            score_match = re.search(r'RELEVANCE_SCORE:\s*(\d+)', relevance)
            if score_match:
                relevance_score = float(score_match.group(1)) / 10.0  # Convert to 0-1 scale
            
            # Try to extract overall score from metadata matching
            overall_score_match = re.search(r'OVERALL_SCORE:\s*([\d.]+)', metadata_matching)
            if overall_score_match:
                relevance_score = float(overall_score_match.group(1))

            # Extract classification reasons
            reasons = []
            
            # Add summary information
            if "EXECUTIVE_SUMMARY:" in document_summary:
                summary = document_summary.split("EXECUTIVE_SUMMARY:")[-1].split("\n")[0].strip()
                reasons.append(f"Document summary: {summary[:150]}...")
            
            # Add relevance reasoning
            if "REASONING:" in relevance:
                reasoning = relevance.split("REASONING:")[-1].split("\n")[0].strip()
                reasons.append(f"Relevance analysis: {reasoning[:150]}...")
            
            # Add matching aspects
            if "MATCHING_ASPECTS:" in relevance:
                matching = relevance.split("MATCHING_ASPECTS:")[-1].split("\n")[0].strip()
                reasons.append(f"Matching aspects: {matching[:150]}...")
            
            # Add final recommendation reasoning
            if "FINAL_RECOMMENDATION:" in metadata_matching:
                recommendation_line = metadata_matching.split("FINAL_RECOMMENDATION:")[-1].split("\n")[0].strip()
                reasons.append(f"Final decision: {recommendation_line[:150]}...")
            
            # Extract technologies and keywords found
            tech_matches = []
            keyword_matches = []
            
            if "TECHNOLOGY_MATCH:" in metadata_matching:
                tech_line = metadata_matching.split("TECHNOLOGY_MATCH:")[-1].split("\n")[0].strip()
                tech_matches.append(tech_line)
            
            if "KEYWORD_MATCH:" in metadata_matching:
                keyword_line = metadata_matching.split("KEYWORD_MATCH:")[-1].split("\n")[0].strip()
                keyword_matches.append(keyword_line)

            return {
                "status": "completed",
                "is_relevant": is_relevant,
                "relevance_score": relevance_score,
                "classification_reasons": reasons,
                "processing_method": "full_agent_analysis",
                "agent_results": {
                    "content_quality": content_quality,
                    "document_summary": document_summary,
                    "relevance": relevance,
                    "metadata_matching": metadata_matching
                },
                "extracted_info": {
                    "technology_matches": tech_matches,
                    "keyword_matches": keyword_matches
                },
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "task_id": self.task_id,
                    "threshold_used": threshold
                }
            }

        except Exception as e:
            self.logger.error(f"Error processing agent results: {str(e)}")
            return {
                "status": "failed",
                "error": f"Failed to process agent results: {str(e)}"
            }

    def _save_results(self, agents_dir: Path, result: Dict[str, Any]):
        """Save classification results to files"""
        try:
            # Save as JSON
            json_path = agents_dir / "classification_result.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=4)

            # Save as formatted text
            text_path = agents_dir / "classification_summary.txt"
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(f"# Document Classification Summary\n\n")
                f.write(f"Classification Date: {result.get('metadata', {}).get('timestamp', 'Unknown')}\n")
                f.write(f"Task ID: {self.task_id}\n\n")
                f.write(f"## Result\n")
                f.write(f"Relevant: {'Yes' if result.get('is_relevant') else 'No'}\n")
                f.write(f"Relevance Score: {result.get('relevance_score', 0):.2f}\n\n")
                f.write(f"## Reasons\n")
                for reason in result.get('classification_reasons', []):
                    f.write(f"- {reason}\n")

            self.logger.info(f"Results saved to {json_path} and {text_path}")

        except Exception as e:
            self.logger.error(f"Error saving results: {str(e)}")