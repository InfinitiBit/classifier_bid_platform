import base64
import aiohttp
from pathlib import Path
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional
import os

logger = logging.getLogger(__name__)


class FileDownloader:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self._ensure_base_dir()
        logger.info(f"Initialized FileDownloader with base directory: {self.base_dir}")

    def _ensure_base_dir(self) -> None:
        """Ensure base directory exists."""
        if not self.base_dir.exists():
            self.base_dir.mkdir(parents=True)
            logger.info(f"Created base directory: {self.base_dir}")
        else:
            logger.info(f"Using existing base directory: {self.base_dir}")

    def create_task_structure(self, task_id: str) -> Dict[str, Path]:
        """Create required folder structure for a task."""
        task_dir = self.base_dir / task_id
        logger.info(f"Creating task directory structure for task_id: {task_id}")

        # Create the content directory directly in task_dir
        content_dir = task_dir / 'content'
        content_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created/verified content directory: {content_dir}")

        folders = {
            'root': task_dir,
            'content': content_dir
        }

        return folders

    async def save_base64_file(self, base64_content: str, target_path: Path) -> Dict:
        """Save a base64 encoded file."""
        try:
            logger.info(f"Starting to decode base64 content for {target_path}")

            # Validate base64 content
            if not base64_content:
                raise ValueError("Empty base64 content provided")

            try:
                content = base64.b64decode(base64_content)
            except Exception as e:
                logger.error(f"Base64 decoding failed: {str(e)}")
                raise ValueError(f"Invalid base64 content: {str(e)}")

            logger.info(f"Decoded content size: {len(content)} bytes")

            # Ensure parent directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            target_path.write_bytes(content)
            logger.info(f"Successfully saved file to {target_path}")

            # Verify file was written
            if not target_path.exists():
                raise FileNotFoundError(f"File was not created at {target_path}")

            file_size = target_path.stat().st_size
            if file_size == 0:
                raise ValueError(f"File was created but is empty: {target_path}")

            logger.info(f"Verified file creation: {target_path}, size: {file_size} bytes")

            return {
                "status": "success",
                "path": str(target_path),
                "size": file_size
            }

        except Exception as e:
            logger.error(f"Error saving base64 content to {target_path}: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "path": str(target_path)
            }

    async def save_url_file(self, url: str, target_path: Path) -> Dict:
        """Save a file from URL."""
        try:
            logger.info(f"Starting to download file from {url} to {target_path}")

            async with aiohttp.ClientSession() as session:
                # Configure timeout for the request
                timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes timeout
                async with session.get(url, timeout=timeout) as response:
                    if response.status != 200:
                        raise ValueError(f"Failed to download file: HTTP {response.status}")

                    # Ensure parent directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    # Stream the file content to disk
                    with open(target_path, 'wb') as fd:
                        async for chunk in response.content.iter_chunked(1024 * 1024):  # 1MB chunks
                            fd.write(chunk)

                    logger.info(f"Successfully downloaded file to {target_path}")

                    # Verify file
                    if not target_path.exists():
                        raise FileNotFoundError(f"File was not created at {target_path}")

                    file_size = target_path.stat().st_size
                    if file_size == 0:
                        raise ValueError(f"File was downloaded but is empty: {target_path}")

                    logger.info(f"Verified file: {target_path}, size: {file_size} bytes")

                    return {
                        "status": "success",
                        "path": str(target_path),
                        "size": file_size
                    }

        except Exception as e:
            logger.error(f"Error downloading file from {url} to {target_path}: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "path": str(target_path)
            }

    async def process_task_files(self, task_id: str, project_id: str, files: List[Dict[str, str]]) -> Dict:
        """Process multiple files for a task."""
        try:
            logger.info(f"Starting to process {len(files)} files for task {task_id}")

            # Create task folder structure
            folders = self.create_task_structure(task_id)
            processed_files = []
            failed_files = []

            # Process each file
            for file_info in files:
                try:
                    file_id = file_info["fileId"]
                    file_link = file_info["fileLink"]
                    logger.info(f"Processing file {file_id} for task {task_id}")

                    target_path = folders['content'] / f"{file_id}.pdf"

                    # Check if the link is a URL (simple check)
                    if file_link.startswith(('http://', 'https://')):
                        save_result = await self.save_url_file(file_link, target_path)
                    else:
                        save_result = await self.save_base64_file(file_link, target_path)

                    if save_result["status"] == "success":
                        logger.info(f"Successfully processed file {file_id}")
                        processed_files.append({
                            "fileId": file_id,
                            "path": save_result["path"],
                            "size": save_result["size"]
                        })
                    else:
                        logger.error(f"Failed to process file {file_id}: {save_result.get('error')}")
                        failed_files.append({
                            "fileId": file_id,
                            "error": save_result.get("error", "Unknown error")
                        })

                except Exception as e:
                    logger.error(f"Error processing file {file_info.get('fileId', 'unknown')}: {str(e)}")
                    failed_files.append({
                        "fileId": file_info.get('fileId', 'unknown'),
                        "error": str(e)
                    })

            # Save task metadata
            metadata = {
                "taskId": task_id,
                "projectId": project_id,
                "timestamp": datetime.now().isoformat(),
                "processed_files": processed_files,
                "failed_files": failed_files,
                "total_files": len(files),
                "successful_files": len(processed_files)
            }

            metadata_path = folders['content'] / 'task_metadata.json'
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Saved task metadata to {metadata_path}")

            # Return detailed status
            result = {
                "status": "completed" if not failed_files else "partial",
                "taskId": task_id,
                "projectId": project_id,
                "folders": {k: str(v) for k, v in folders.items()},
                "processed_files": processed_files,
                "failed_files": failed_files,
                "metadata_path": str(metadata_path)
            }

            logger.info(f"Task {task_id} processing completed with status: {result['status']}")
            return result

        except Exception as e:
            error_msg = f"Error processing task {task_id}: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "taskId": task_id,
                "projectId": project_id,
                "error": error_msg
            }

    async def download_single_file(
        self, 
        task_id: str, 
        project_id: str, 
        file_url: str, 
        file_id: str = "document"
    ) -> Dict:
        """
        Download a single file for document classification.
        
        Args:
            task_id (str): Task identifier
            project_id (str): Project identifier  
            file_url (str): URL or base64 content of the file
            file_id (str): Identifier for the file
            
        Returns:
            Dict: Download result with file path
        """
        try:
            logger.info(f"Starting single file download for task {task_id}, file {file_id}")
            
            # Create task structure
            folders = self.create_task_structure(task_id)
            
            # Determine file extension based on URL or default to PDF
            file_extension = ".pdf"
            if file_url.startswith(('http://', 'https://')):
                # Try to extract extension from URL
                url_path = file_url.split('?')[0]  # Remove query parameters
                if '.' in url_path:
                    potential_ext = url_path.split('.')[-1].lower()
                    if potential_ext in ['pdf', 'doc', 'docx', 'txt']:
                        file_extension = f".{potential_ext}"
            
            target_path = folders['content'] / f"{file_id}{file_extension}"
            
            # Download the file
            if file_url.startswith(('http://', 'https://')):
                save_result = await self.save_url_file(file_url, target_path)
            else:
                save_result = await self.save_base64_file(file_url, target_path)
            
            if save_result["status"] == "success":
                logger.info(f"Successfully downloaded single file {file_id} to {save_result['path']}")
                
                # Save metadata for this single file
                metadata = {
                    "task_id": task_id,
                    "project_id": project_id,
                    "file_id": file_id,
                    "file_url": file_url,
                    "file_path": save_result["path"],
                    "file_size": save_result["size"],
                    "timestamp": datetime.now().isoformat(),
                    "download_type": "single_file_classification"
                }
                
                metadata_path = folders['content'] / f'{file_id}_metadata.json'
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)
                
                return {
                    "status": "success",
                    "file_path": save_result["path"],
                    "file_size": save_result["size"],
                    "metadata_path": str(metadata_path)
                }
            else:
                error_msg = f"Failed to download file: {save_result.get('error', 'Unknown error')}"
                logger.error(error_msg)
                return {
                    "status": "failed",
                    "error": error_msg
                }
                
        except Exception as e:
            error_msg = f"Error in download_single_file: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "error": error_msg
            }