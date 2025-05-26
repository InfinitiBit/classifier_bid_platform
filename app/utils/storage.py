from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import json
import os
import time
import shutil
from app.utils.logging import setup_logging

logger = setup_logging()


class LocalStorageManager:
    base_path = Path("./uploads/extracted")
    response_dir = Path("./uploads/responses")
    document_dir = Path("./uploads/documents")

    @classmethod
    def _init_storage(cls):
        """Initialize storage directories"""
        cls.base_path.mkdir(parents=True, exist_ok=True)
        cls.response_dir.mkdir(parents=True, exist_ok=True)
        cls.document_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _get_response_path(cls, task_id: str) -> Path:
        """Get path for response JSON file"""
        cls._init_storage()
        return cls.response_dir / f"{task_id}_response.json"

    @staticmethod
    def _safe_remove_file(file_path: str, max_retries: int = 3) -> bool:
        """Safely remove a file with retries"""
        for attempt in range(max_retries):
            try:
                os.remove(file_path)
                return True
            except (PermissionError, OSError) as e:
                logger.warning(f"Attempt {attempt + 1} failed to delete {file_path}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return False
        return False

    @staticmethod
    def _serialize_content_element(element: Any) -> Dict[str, Any]:
        """Specifically handle ContentElement objects"""
        serialized = {}

        if hasattr(element, 'content'):
            serialized['content'] = str(element.content)
        if hasattr(element, 'page_number'):
            serialized['page_number'] = element.page_number
        if hasattr(element, 'source_file'):
            serialized['source_file'] = str(element.source_file)
        if hasattr(element, 'element_type'):
            serialized['element_type'] = str(element.element_type)
        if hasattr(element, 'confidence'):
            serialized['confidence'] = float(element.confidence)
        if hasattr(element, 'metadata'):
            serialized['metadata'] = LocalStorageManager._serialize_content(element.metadata)

        for key, value in element.__dict__.items():
            if not key.startswith('_') and key not in serialized:
                serialized[key] = LocalStorageManager._serialize_content(value)

        return serialized

    @staticmethod
    def _serialize_content(obj: Any) -> Any:
        """Convert objects to JSON-serializable format"""
        try:
            if obj is None:
                return None

            if hasattr(obj, 'element_type') and hasattr(obj, 'content'):
                return LocalStorageManager._serialize_content_element(obj)

            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            elif isinstance(obj, (str, int, float, bool)):
                return obj
            elif isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, bytes):
                return obj.decode('utf-8', errors='replace')
            elif isinstance(obj, (list, tuple)):
                return [LocalStorageManager._serialize_content(item) for item in obj]
            elif isinstance(obj, dict):
                return {str(k): LocalStorageManager._serialize_content(v) for k, v in obj.items()}
            elif isinstance(obj, set):
                return list(obj)
            elif hasattr(obj, '__dict__'):
                return {k: LocalStorageManager._serialize_content(v) for k, v in obj.__dict__.items()
                        if not k.startswith('_')}
            else:
                return str(obj)

        except Exception as e:
            logger.error(f"Error serializing object of type {type(obj)}: {str(e)}")
            return str(obj)

    @classmethod
    async def save_response(cls, task_id: str, response_data: Dict[str, Any]) -> str:
        """Save response data as JSON file"""
        try:
            logger.info(f"Starting to save response for task {task_id}")
            response_file = cls._get_response_path(task_id)

            logger.debug(f"Response data structure: {type(response_data)}")
            for key, value in response_data.items():
                logger.debug(f"Key: {key}, Type: {type(value)}")

            serialized_data = cls._serialize_content(response_data)
            response_with_metadata = {
                "data": serialized_data,
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "task_id": task_id,
                    "version": "1.0"
                }
            }

            temp_file = response_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(response_with_metadata, f, indent=2)

            if not temp_file.exists() or temp_file.stat().st_size == 0:
                raise ValueError("Failed to write temporary file or file is empty")

            if response_file.exists():
                os.remove(str(response_file))
            os.rename(str(temp_file), str(response_file))

            logger.info(f"Successfully saved response for task {task_id} at {response_file}")
            return str(response_file)

        except Exception as e:
            logger.error(f"Error saving response for task {task_id}: {str(e)}")
            if 'temp_file' in locals() and temp_file.exists():
                try:
                    os.remove(str(temp_file))
                except:
                    pass
            raise

    @classmethod
    async def get_response(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """Get response data for a task"""
        try:
            response_file = cls._get_response_path(task_id)
            if not response_file.exists():
                return None

            with open(response_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("data")

        except Exception as e:
            logger.error(f"Error reading response for task {task_id}: {str(e)}")
            return None

    @classmethod
    async def cleanup_responses(cls) -> Dict[str, Any]:
        """Clean up responses directory (manual trigger only)"""
        try:
            logger.info("Starting manual response cleanup")
            cleaned_count = 0
            bytes_cleaned = 0
            failed_deletes = []

            for response_file in cls.response_dir.glob("*"):
                file_path = str(response_file)
                try:
                    if response_file.is_file():
                        file_size = os.path.getsize(file_path)
                        if cls._safe_remove_file(file_path):
                            cleaned_count += 1
                            bytes_cleaned += file_size
                            logger.info(f"Successfully deleted response: {file_path}")
                        else:
                            failed_deletes.append(file_path)
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {str(e)}")
                    failed_deletes.append(file_path)

            cleanup_result = {
                "operation": "responses_cleanup",
                "cleanup_time": datetime.now().isoformat(),
                "directory": str(cls.response_dir),
                "cleaned_files": cleaned_count,
                "bytes_cleaned": bytes_cleaned,
                "failed_deletes": failed_deletes
            }

            logger.info(f"Response cleanup completed: {cleanup_result}")
            return cleanup_result

        except Exception as e:
            error_result = {
                "operation": "responses_cleanup",
                "error": str(e),
                "cleanup_time": datetime.now().isoformat()
            }
            logger.error(f"Error during responses cleanup: {error_result}")
            return error_result

    @classmethod
    async def cleanup_extracted(cls) -> Dict[str, Any]:
        """Clean up extracted folder and document folder contents (manual and scheduled)"""
        try:
            logger.info("Starting extracted and document folders cleanup")

            # Track cleanup stats for each directory
            stats = {
                "extracted": {"cleaned_count": 0, "bytes_cleaned": 0, "failed_deletes": []},
                "document": {"cleaned_count": 0, "bytes_cleaned": 0, "failed_deletes": []}
            }

            # Clean extracted directory
            for item in cls.base_path.glob('*'):
                try:
                    if item.is_file():
                        file_size = os.path.getsize(str(item))
                        if cls._safe_remove_file(str(item)):
                            stats["extracted"]["cleaned_count"] += 1
                            stats["extracted"]["bytes_cleaned"] += file_size
                        else:
                            stats["extracted"]["failed_deletes"].append(str(item))
                    elif item.is_dir():
                        dir_size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                        try:
                            shutil.rmtree(str(item))
                            stats["extracted"]["cleaned_count"] += 1
                            stats["extracted"]["bytes_cleaned"] += dir_size
                        except Exception as e:
                            stats["extracted"]["failed_deletes"].append(str(item))
                            logger.error(f"Failed to remove directory {item}: {e}")
                except Exception as e:
                    stats["extracted"]["failed_deletes"].append(str(item))
                    logger.error(f"Error processing {item}: {e}")

            # Clean document directory
            for item in cls.document_dir.glob('*'):
                try:
                    if item.is_file():
                        file_size = os.path.getsize(str(item))
                        if cls._safe_remove_file(str(item)):
                            stats["document"]["cleaned_count"] += 1
                            stats["document"]["bytes_cleaned"] += file_size
                        else:
                            stats["document"]["failed_deletes"].append(str(item))
                    elif item.is_dir():
                        dir_size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                        try:
                            shutil.rmtree(str(item))
                            stats["document"]["cleaned_count"] += 1
                            stats["document"]["bytes_cleaned"] += dir_size
                        except Exception as e:
                            stats["document"]["failed_deletes"].append(str(item))
                            logger.error(f"Failed to remove directory {item}: {e}")
                except Exception as e:
                    stats["document"]["failed_deletes"].append(str(item))
                    logger.error(f"Error processing {item}: {e}")

            cleanup_result = {
                "operation": "folder_cleanup",
                "cleanup_time": datetime.now().isoformat(),
                "extracted_folder": {
                    "directory": str(cls.base_path),
                    "cleaned_items": stats["extracted"]["cleaned_count"],
                    "bytes_cleaned": stats["extracted"]["bytes_cleaned"],
                    "failed_deletes": stats["extracted"]["failed_deletes"]
                },
                "document_folder": {
                    "directory": str(cls.document_dir),
                    "cleaned_items": stats["document"]["cleaned_count"],
                    "bytes_cleaned": stats["document"]["bytes_cleaned"],
                    "failed_deletes": stats["document"]["failed_deletes"]
                },
                "total_cleaned_items": (stats["extracted"]["cleaned_count"] +
                                        stats["document"]["cleaned_count"]),
                "total_bytes_cleaned": (stats["extracted"]["bytes_cleaned"] +
                                        stats["document"]["bytes_cleaned"])
            }

            logger.info(f"Folders cleanup completed: {cleanup_result}")
            return cleanup_result

        except Exception as e:
            error_result = {
                "operation": "folder_cleanup",
                "error": str(e),
                "cleanup_time": datetime.now().isoformat()
            }
            logger.error(f"Error during folder cleanup: {error_result}")
            return error_result