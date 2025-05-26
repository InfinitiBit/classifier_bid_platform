"""
Helper methods for document processing in classification workflow
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional

def extract_document_content(file_path: str) -> Dict[str, Any]:
    """
    Extract content from document file
    
    Args:
        file_path (str): Path to document file
        
    Returns:
        Dict containing content and metadata
    """
    try:
        # Import PDF extractor from existing services
        import sys
        ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(ROOT_DIR))
        
        file_path_obj = Path(file_path)
        
        # Get file size
        file_size = file_path_obj.stat().st_size if file_path_obj.exists() else 0
        
        # Try full PDF extractor first
        try:
            from app.services.contents_extraction.pdf_extractor_service import PDFExtractor
            
            extractor = PDFExtractor()
            
            # Extract content using existing PDF extractor
            if file_path_obj.suffix.lower() == '.pdf':
                # Use existing PDF extraction method
                result = extractor.extract_text_content(str(file_path))
                content = result.get('text', '') if isinstance(result, dict) else str(result)
                extraction_method = result.get('extraction_method', 'pdf_extractor')
            else:
                # For other file types, read as text
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                extraction_method = 'text_file'
                
        except Exception as pdf_error:
            raise Exception(f"Extraction methods failed. PDF: {pdf_error}")
        
        return {
            "content": content,
            "file_size": file_size,
            "file_type": file_path_obj.suffix.lower(),
            "extraction_success": True,
            "extraction_method": extraction_method
        }
        
    except Exception as e:
        return {
            "content": "",
            "file_size": 0,
            "file_type": "unknown",
            "extraction_success": False,
            "error": str(e)
        }

def validate_project_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize project metadata
    
    Args:
        metadata (Dict): Project metadata
        
    Returns:
        Dict with validation results and normalized metadata
    """
    required_fields = ['project_type', 'industry']
    missing_fields = []
    
    for field in required_fields:
        if not metadata.get(field):
            missing_fields.append(field)
    
    # Normalize lists
    normalized_metadata = metadata.copy()
    for field in ['technologies', 'keywords', 'requirements']:
        if field in normalized_metadata and isinstance(normalized_metadata[field], str):
            normalized_metadata[field] = [normalized_metadata[field]]
        elif field not in normalized_metadata:
            normalized_metadata[field] = []
    
    return {
        "is_valid": len(missing_fields) == 0,
        "missing_fields": missing_fields,
        "metadata": normalized_metadata
    }

def format_classification_result(
    result: Dict[str, Any], 
    task_id: str, 
    project_id: str
) -> Dict[str, Any]:
    """
    Format classification result for API response
    
    Args:
        result (Dict): Raw classification result
        task_id (str): Task identifier
        project_id (str): Project identifier
        
    Returns:
        Dict formatted for API response
    """
    return {
        "task_id": task_id,
        "project_id": project_id,
        "status": result.get("status", "unknown"),
        "is_relevant": result.get("is_relevant", False),
        "relevance_score": result.get("relevance_score", 0.0),
        "classification_reasons": result.get("classification_reasons", []),
        "processing_method": result.get("bypass_reason", "full_agent_analysis"),
        "timestamp": result.get("metadata", {}).get("timestamp"),
        "error": result.get("error")
    }