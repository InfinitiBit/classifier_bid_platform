# app/utils/file_manager.py

import shutil
from pathlib import Path
from typing import Dict, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class FileManager:
    def __init__(self, documents_dir: str, extracted_dir: str):
        self.documents_dir = Path(documents_dir)
        self.extracted_dir = Path(extracted_dir)
        logger.info(f"Initialized FileManager with documents_dir: {documents_dir}, extracted_dir: {extracted_dir}")

    def ensure_directories(self, task_id: str) -> Dict[str, Path]:
        """Create all necessary directories for a task"""
        directories = {
            'documents_task': self.documents_dir / task_id / 'content',
            'extracted_task': self.extracted_dir / task_id,
            'extracted_content': self.extracted_dir / task_id / 'content',
            'extracted_metadata': self.extracted_dir / task_id / 'metadata',
            'merged': self.extracted_dir / task_id / 'merged'
        }

        for name, dir_path in directories.items():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created/verified directory {name}: {dir_path}")
            except Exception as e:
                logger.error(f"Error creating directory {name} at {dir_path}: {str(e)}")
                raise

        return directories

    def move_files_to_extracted(self, task_id: str, file_ids: List[str]) -> Dict[str, Dict[str, str]]:
        """Move files from documents directory to extracted directory"""
        results = {}

        try:
            # Ensure directories exist
            directories = self.ensure_directories(task_id)
            logger.info(f"Directories for task {task_id}:")
            for name, path in directories.items():
                logger.info(f"  {name}: {path}")

            for file_id in file_ids:
                try:
                    # Define source and destination paths
                    source_path = directories['documents_task'] / f"{file_id}.pdf"
                    dest_path = directories['extracted_content'] / f"{file_id}.pdf"

                    logger.info(f"Moving file {file_id}:")
                    logger.info(f"  From: {source_path}")
                    logger.info(f"  To: {dest_path}")

                    # Verify source file
                    if not source_path.exists():
                        error_msg = f"Source file not found: {source_path}"
                        logger.error(error_msg)
                        # Check if parent directory exists
                        if not source_path.parent.exists():
                            logger.error(f"Source parent directory doesn't exist: {source_path.parent}")
                        results[file_id] = {
                            "status": "error",
                            "message": error_msg
                        }
                        continue

                    # Create destination directory if needed
                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    # Copy file
                    logger.info(f"Copying file {file_id}")
                    shutil.copy2(source_path, dest_path)

                    # Verify copy
                    if not dest_path.exists():
                        error_msg = f"Failed to copy file to destination: {dest_path}"
                        logger.error(error_msg)
                        results[file_id] = {
                            "status": "error",
                            "message": error_msg
                        }
                        continue

                    # Compare file sizes
                    source_size = source_path.stat().st_size
                    dest_size = dest_path.stat().st_size
                    if source_size != dest_size:
                        error_msg = f"File size mismatch: source={source_size}, dest={dest_size}"
                        logger.error(error_msg)
                        results[file_id] = {
                            "status": "error",
                            "message": error_msg
                        }
                        continue

                    results[file_id] = {
                        "status": "success",
                        "source": str(source_path),
                        "destination": str(dest_path),
                        "size": source_size
                    }

                    logger.info(f"Successfully moved file {file_id}")

                except Exception as e:
                    error_msg = f"Error moving file {file_id}: {str(e)}"
                    logger.error(error_msg)
                    results[file_id] = {
                        "status": "error",
                        "message": error_msg
                    }

            return results

        except Exception as e:
            logger.error(f"Error in move_files_to_extracted: {str(e)}")
            raise