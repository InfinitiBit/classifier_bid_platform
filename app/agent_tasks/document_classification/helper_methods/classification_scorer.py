"""
Helper methods for classification scoring and bypass logic
"""
from typing import Dict, Any, Tuple

def should_bypass_analysis(content: str, file_size_bytes: int = None) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Enhanced quick check to determine if document should bypass full agent analysis
    
    Args:
        content (str): Document content
        file_size_bytes (int): File size in bytes
        
    Returns:
        Tuple of (should_bypass: bool, reason: str, quick_result: Dict)
    """
    import re
    
    # Very small file (less than 1KB)
    if file_size_bytes and file_size_bytes < 1000:
        return True, "file_too_small", {
            "is_relevant": False,
            "relevance_score": 0.0,
            "classification_reasons": [f"Document too small ({file_size_bytes} bytes) to contain meaningful content"],
            "processing_method": "fast_bypass"
        }
    
    # Empty or minimal content
    if not content or len(content.strip()) < 50:
        return True, "empty_or_minimal_content", {
            "is_relevant": False,
            "relevance_score": 0.0,
            "classification_reasons": ["Document contains insufficient content for analysis"],
            "processing_method": "fast_bypass"
        }
    
    # Check word count
    words = content.split()
    if len(words) < 20:
        return True, "insufficient_words", {
            "is_relevant": False,
            "relevance_score": 0.0,
            "classification_reasons": [f"Document contains only {len(words)} words - insufficient for analysis"],
            "processing_method": "fast_bypass"
        }
    
    # Check for repetitive/garbage content
    unique_words = set(word.lower() for word in words if word.isalpha())
    if len(unique_words) < len(words) * 0.1:  # Less than 10% unique words
        return True, "repetitive_content", {
            "is_relevant": False,
            "relevance_score": 0.0,
            "classification_reasons": ["Document contains repetitive or low-quality content"],
            "processing_method": "fast_bypass"
        }
    
    # Check for blank document patterns (common OCR failures)
    if _is_blank_document(content):
        return True, "blank_document", {
            "is_relevant": False,
            "relevance_score": 0.0,
            "classification_reasons": ["Document appears to be blank or contains only formatting/OCR artifacts"],
            "processing_method": "fast_bypass"
        }
    
    # Check for non-meaningful content ratio
    meaningful_chars = len(re.findall(r'[a-zA-Z0-9]', content))
    total_chars = len(content)
    if total_chars > 0 and meaningful_chars / total_chars < 0.5:
        return True, "low_meaningful_content", {
            "is_relevant": False,
            "relevance_score": 0.0,
            "classification_reasons": ["Document contains insufficient meaningful content (mostly symbols/formatting)"],
            "processing_method": "fast_bypass"
        }
    
    # Document passes all bypass checks - needs agent analysis
    return False, "analysis_required", {}

def _is_blank_document(content: str) -> bool:
    """
    Check if document appears to be blank based on common patterns
    """
    import re
    
    # Remove common OCR artifacts and formatting
    cleaned = re.sub(r'[\n\r\t\s]+', ' ', content).strip()
    cleaned = re.sub(r'[^\w\s]', '', cleaned)
    
    # Check for very short cleaned content
    if len(cleaned) < 30:
        return True
        
    # Check for repetitive patterns (common in blank scans)
    words = cleaned.split()
    if len(words) > 0:
        most_common_word = max(set(words), key=words.count)
        if words.count(most_common_word) > len(words) * 0.8:
            return True
    
    return False

def combine_agent_results(
    content_quality_result: str,
    relevance_result: str, 
    metadata_matching_result: str
) -> Dict[str, Any]:
    """
    Combine results from all classification agents
    
    Args:
        content_quality_result: Result from content quality agent
        relevance_result: Result from relevance agent  
        metadata_matching_result: Result from metadata matching agent
        
    Returns:
        Combined classification result
    """
    # Parse agent results and combine them
    # This will be implemented based on agent output formats
    return {
        "status": "completed",
        "agents_results": {
            "content_quality": content_quality_result,
            "relevance": relevance_result,
            "metadata_matching": metadata_matching_result
        }
    }