from typing import Dict
from datetime import datetime

class ContentElement:
    """Class to hold content with metadata."""

    def __init__(self, content: str, content_type: str, metadata: Dict = None):
        self.content = content
        self.content_type = content_type
        self.metadata = metadata or {
            'content_type': content_type,
            'length': len(content),
            'timestamp': datetime.now().isoformat()
        }

    def __str__(self):
        return f"{self.content_type}: {self.content[:100]}..."

    def to_dict(self) -> Dict:
        """Convert element to dictionary."""
        return {
            'content': self.content,
            'content_type': self.content_type,
            'metadata': self.metadata
        }