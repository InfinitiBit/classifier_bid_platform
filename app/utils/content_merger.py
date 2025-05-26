# app/utils/content_merger.py

from pathlib import Path
import json
import logging
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class ContentMerger:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

    async def merge_task_contents(self, task_id: str) -> Dict[str, str]:
        """Merge contents from all files in the task."""
        try:
            task_dir = self.base_dir / task_id
            merged_data = {
                'texts': [],
                'tables': [],
                'images': [],
                'metadata': {
                    'task_id': task_id,
                    'timestamp': datetime.now().isoformat(),
                    'processed_files': []
                }
            }

            logger.info(f"Starting content merge for task: {task_id}")

            # Process each file directory in the task
            for file_dir in task_dir.glob("*"):
                if not file_dir.is_dir() or file_dir.name in ['merged', 'agents']:
                    continue

                file_id = file_dir.name
                logger.info(f"Processing file: {file_id}")

                # Collect text content
                text_file = file_dir / "text" / "content.txt"
                if text_file.exists():
                    content = text_file.read_text(encoding='utf-8')
                    merged_data['texts'].append({
                        'file_id': file_id,
                        'content': content
                    })

                # Collect tables
                tables_file = file_dir / "metadata" / "tables_metadata.json"
                if tables_file.exists():
                    with open(tables_file, 'r', encoding='utf-8') as f:
                        tables = json.load(f)
                        for table in tables:
                            table['source_file'] = file_id
                        merged_data['tables'].extend(tables)

                # Collect images
                images_file = file_dir / "metadata" / "images_metadata.json"
                if images_file.exists():
                    with open(images_file, 'r', encoding='utf-8') as f:
                        images = json.load(f)
                        for image in images:
                            image['source_file'] = file_id
                        merged_data['images'].extend(images)

                merged_data['metadata']['processed_files'].append(file_id)

            # Create merged directory
            merged_dir = task_dir / "merged"
            merged_dir.mkdir(exist_ok=True)

            # Save merged metadata
            metadata_file = merged_dir / "merged_content.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(merged_data, f, indent=2, ensure_ascii=False)

            # Create combined text file
            combined_text = "\n\n".join([
                f"=== Content from {text['file_id']} ===\n{text['content']}"
                for text in merged_data['texts']
            ])
            combined_text_file = merged_dir / "combined_text.txt"
            combined_text_file.write_text(combined_text, encoding='utf-8')

            logger.info(f"Successfully merged content for task {task_id}")

            return {
                'status': 'success',
                'task_id': task_id,
                'metadata': merged_data['metadata'],
                'files': {
                    'merged_content': str(metadata_file),
                    'combined_text': str(combined_text_file)
                }
            }

        except Exception as e:
            error_msg = f"Error merging content for task {task_id}: {str(e)}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'task_id': task_id
            }