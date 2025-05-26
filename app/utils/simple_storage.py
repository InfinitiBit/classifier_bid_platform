"""
Simple storage manager for testing without dependencies
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

class SimpleStorageManager:
    """Simple file-based storage for testing"""
    
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent / "uploads" / "responses"
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_response(self, task_id: str, response_data: Dict[str, Any]) -> bool:
        """Save response data to file"""
        try:
            file_path = self.base_dir / f"{task_id}_response.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, default=str)
            return True
        except Exception as e:
            print(f"Error saving response: {e}")
            return False
    
    async def get_response(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get response data from file"""
        try:
            file_path = self.base_dir / f"{task_id}_response.json"
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"Error loading response: {e}")
            return None
    
    async def cleanup_responses(self) -> Dict[str, Any]:
        """Cleanup old response files"""
        try:
            files_removed = 0
            for file_path in self.base_dir.glob("*_response.json"):
                # Remove files older than 24 hours
                if (datetime.now().timestamp() - file_path.stat().st_mtime) > 86400:
                    file_path.unlink()
                    files_removed += 1
            
            return {
                "files_removed": files_removed,
                "status": "completed"
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": "failed"
            }