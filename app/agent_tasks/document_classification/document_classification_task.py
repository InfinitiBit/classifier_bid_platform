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

            # Notify backend of agent analysis start
            if self.backend_url and self.task_id:
                try:
                    requests.post(
                        f"{self.backend_url.rstrip('/')}/classifiers/{self.task_id}/subtasks",
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

                Based on the content quality analysis and document summary, DETERMINE document relevance for the project.

                ANALYZE alignment between document content and ALL project requirements:
                1. Review each metadata field and assess if the document addresses it
                2. Consider the project description, stage, and all custom metadata fields
                3. Evaluate how well the document fits the overall project needs
                4. Rate relevance on scale 1-10 with detailed justification

                Pay special attention to:
                - Project-specific requirements mentioned in metadata
                - Industry/domain alignment
                - Technical specifications or capabilities
                - Geographic/location requirements
                - Budget and timeline constraints
                - Any specialized criteria in the metadata

                Format your response as:
                RELEVANCE_SCORE: [1-10]
                ALIGNMENT: [high/medium/low]
                REASONING: [detailed explanation of the score]
                MATCHING_ASPECTS: [list specific matches between document and project metadata]
                GAPS: [list any project requirements not addressed in document]

                Project Information and Metadata:
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

                COMPARE document characteristics against project metadata criteria using the document summary and relevance analysis.

                EVALUATE matches between the document content and ALL project metadata fields provided below.

                For each metadata field:
                1. Check if the concept/requirement is mentioned or addressed in the document
                2. Assess how well the document aligns with that specific criterion
                3. Note any exact matches, partial matches, or relevant mentions

                Consider ALL aspects:
                - Direct mentions of metadata values in the document
                - Conceptual alignment even if exact terms aren't used
                - Industry/domain relevance based on metadata
                - Technical requirements or specifications matching
                - Budget/timeline compatibility if mentioned
                - Geographic or location relevance
                - Any other project-specific criteria

                Format your response as:
                METADATA_MATCHES: [List each metadata field and whether it matches]
                ALIGNMENT_SCORE: [0.0-1.0] - Overall alignment score
                KEY_MATCHES: [List the most important matches found]
                MISSING_ELEMENTS: [List important metadata criteria not found in document]
                FINAL_RECOMMENDATION: [RELEVANT/NOT_RELEVANT] - [detailed justification]

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
        # Start with basic project information
        formatted_lines = [
            f"Project Name: {metadata.get('project_name', 'Not specified')}",
            f"Project ID: {metadata.get('project_id', 'Not specified')}",
            f"Reference Number: {metadata.get('reference_number', 'Not specified')}",
            f"Bid Manager: {metadata.get('bid_manager', 'Not specified')}"
        ]

        # Add description if present
        if metadata.get('description'):
            formatted_lines.append(f"Description: {metadata.get('description')}")

        # Add all attribute items
        formatted_lines.append("\nProject Attributes:")

        # Exclude the basic fields we've already added
        basic_fields = {
            'project_id', 'project_name', 'description',
            'reference_number', 'bid_manager'
        }

        # Add all other metadata fields (from attributes)
        for key, value in metadata.items():
            if key not in basic_fields:
                formatted_lines.append(f"{key}: {value}")

        return "\n".join(formatted_lines).strip()

    def _process_agent_results(self, agents_dir: Path, threshold: float) -> Dict[str, Any]:
        """Process and combine results from all agents"""
        try:
            # Read agent outputs
            content_quality = read_file_content(str(agents_dir / "content_quality_analysis.txt"))
            document_summary = read_file_content(str(agents_dir / "document_summary.txt"))
            relevance = read_file_content(str(agents_dir / "relevance_analysis.txt"))
            metadata_matching = read_file_content(str(agents_dir / "metadata_matching.txt"))

            # Extract relevance score using regex patterns
            import re

            relevance_score = 0.5  # default

            # First try to extract alignment score from metadata matching (0-1 scale)
            alignment_score_match = re.search(r'ALIGNMENT_SCORE:\s*([\d.]+)', metadata_matching)
            if alignment_score_match:
                relevance_score = float(alignment_score_match.group(1))
                self.logger.info(f"Using alignment score: {relevance_score}")
            else:
                # Fallback to relevance score from relevance analysis (1-10 scale)
                score_match = re.search(r'RELEVANCE_SCORE:\s*(\d+)', relevance)
                if score_match:
                    relevance_score = float(score_match.group(1)) / 10.0  # Convert to 0-1 scale
                    self.logger.info(f"Using relevance score: {relevance_score}")

            # APPLY THE THRESHOLD - This is the key change
            is_relevant = relevance_score >= threshold

            # Also extract agent's text-based recommendation for comparison
            agent_recommendation = "RELEVANT" in metadata_matching.upper() and "NOT_RELEVANT" not in metadata_matching.upper()

            # Log if threshold decision differs from agent recommendation
            if is_relevant != agent_recommendation:
                self.logger.warning(
                    f"Threshold decision (relevant={is_relevant}, score={relevance_score:.2f}, threshold={threshold}) "
                    f"differs from agent text recommendation (relevant={agent_recommendation})"
                )

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

            # Add metadata matches
            if "KEY_MATCHES:" in metadata_matching:
                key_matches = metadata_matching.split("KEY_MATCHES:")[-1].split("\n")[0].strip()
                reasons.append(f"Key metadata matches: {key_matches[:150]}...")

            # Add threshold decision info
            reasons.append(f"Score: {relevance_score:.2f} {'≥' if is_relevant else '<'} threshold {threshold}")

            # Add final recommendation reasoning from agent
            if "FINAL_RECOMMENDATION:" in metadata_matching:
                recommendation_line = metadata_matching.split("FINAL_RECOMMENDATION:")[-1].split("\n")[0].strip()
                reasons.append(f"Agent recommendation: {recommendation_line[:150]}...")

            # Extract metadata matches and gaps
            metadata_matches = []
            missing_elements = []

            if "METADATA_MATCHES:" in metadata_matching:
                matches_section = metadata_matching.split("METADATA_MATCHES:")[-1].split("ALIGNMENT_SCORE:")[0].strip()
                metadata_matches = [line.strip() for line in matches_section.split("\n") if line.strip()]

            if "MISSING_ELEMENTS:" in metadata_matching:
                missing_section = metadata_matching.split("MISSING_ELEMENTS:")[-1].split("FINAL_RECOMMENDATION:")[
                    0].strip()
                missing_elements = [line.strip() for line in missing_section.split("\n") if line.strip()]

            # Extract gaps from relevance analysis
            gaps = []
            if "GAPS:" in relevance:
                gaps_section = relevance.split("GAPS:")[-1].strip()
                gaps = [line.strip() for line in gaps_section.split("\n") if line.strip()]

            return {
                "status": "completed",
                "is_relevant": is_relevant,  # Now based on threshold comparison
                "relevance_score": relevance_score,
                "classification_reasons": reasons,
                "processing_method": "full_agent_analysis",
                "threshold_applied": threshold,  # Add this for transparency
                "agent_recommendation": agent_recommendation,  # Include agent's text-based recommendation
                "agent_results": {
                    "content_quality": content_quality,
                    "document_summary": document_summary,
                    "relevance": relevance,
                    "metadata_matching": metadata_matching
                },
                "extracted_info": {
                    "metadata_matches": metadata_matches,
                    "missing_elements": missing_elements,
                    "gaps": gaps
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