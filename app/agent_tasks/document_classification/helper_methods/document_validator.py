"""
Helper methods for document validation and content assessment
"""
import os
import re
from pathlib import Path
from typing import Dict, Any, Tuple

def read_file_content(file_path: str) -> str:
    """
    Read content from a file, handling various encodings and errors gracefully.
    
    Args:
        file_path (str): Path to the file to read
        
    Returns:
        str: File content or empty string if unable to read
    """
    try:
        if not os.path.exists(file_path):
            return ""
        
        # Try reading with UTF-8 first
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Fall back to latin-1 if UTF-8 fails
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
                
    except Exception as e:
        print(f"Error reading file {file_path}: {str(e)}")
        return ""

def validate_document_content(content: str, min_word_count: int = 50) -> Dict[str, Any]:
    """
    Validate document content for quality and completeness
    
    Args:
        content (str): Document content to validate
        min_word_count (int): Minimum word count for valid document
        
    Returns:
        Dict containing validation results
    """
    if not content or not content.strip():
        return {
            "is_valid": False,
            "reason": "empty_document",
            "word_count": 0,
            "can_bypass": True
        }
    
    # Clean and count words
    cleaned_content = re.sub(r'\s+', ' ', content.strip())
    words = cleaned_content.split()
    word_count = len(words)
    
    # Check for minimum word count
    if word_count < min_word_count:
        return {
            "is_valid": False,
            "reason": "insufficient_content",
            "word_count": word_count,
            "can_bypass": True
        }
    
    # Check for repetitive content (might indicate OCR errors)
    unique_words = set(words)
    if len(unique_words) < word_count * 0.1:  # Less than 10% unique words
        return {
            "is_valid": False,
            "reason": "repetitive_content",
            "word_count": word_count,
            "can_bypass": True
        }
    
    # Check for meaningful content (not just OCR artifacts)
    meaningful_chars = re.findall(r'[a-zA-Z0-9]', content)
    if len(meaningful_chars) < len(content) * 0.5:  # Less than 50% meaningful characters
        return {
            "is_valid": False,
            "reason": "low_quality_content",
            "word_count": word_count,
            "can_bypass": True
        }
    
    return {
        "is_valid": True,
        "reason": "valid_content",
        "word_count": word_count,
        "can_bypass": False
    }

def should_bypass_analysis(content: str, file_size_bytes: int = None) -> Tuple[bool, str]:
    """
    Determine if document analysis should be bypassed for performance
    
    Args:
        content (str): Document content
        file_size_bytes (int): File size in bytes
        
    Returns:
        Tuple of (should_bypass: bool, reason: str)
    """
    # Check file size (very small files likely have no content)
    if file_size_bytes and file_size_bytes < 1000:  # Less than 1KB
        return True, "file_too_small"
    
    # Validate content
    validation = validate_document_content(content)
    if validation["can_bypass"]:
        return True, validation["reason"]
    
    # Check for very large documents that might need special handling
    if validation["word_count"] > 50000:  # More than 50k words
        return False, "large_document_needs_analysis"
    
    return False, "analysis_required"

def extract_basic_summary(content: str, max_chars: int = 500) -> str:
    """
    Extract a basic summary from document content
    
    Args:
        content (str): Document content
        max_chars (int): Maximum characters in summary
        
    Returns:
        String summary of the document
    """
    if not content:
        return "Empty document"
    
    # Clean content
    cleaned = re.sub(r'\s+', ' ', content.strip())
    
    # Take first few sentences or characters
    sentences = re.split(r'[.!?]+', cleaned)
    summary = ""
    
    for sentence in sentences:
        if len(summary + sentence) <= max_chars:
            summary += sentence.strip() + ". "
        else:
            break
    
    if not summary:
        summary = cleaned[:max_chars] + "..." if len(cleaned) > max_chars else cleaned
    
    return summary.strip()