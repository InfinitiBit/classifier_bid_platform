import os
import sys
from pathlib import Path

# Add project root to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

import uuid
import json
from typing import Dict, List, Union, Optional
from datetime import datetime
import argparse

# Project imports
from app.utils.logging import get_logger
from app.config import EXTRACTED_DIR
from app.services.contents_extraction.text_unstructured import TextExtractor

class PDFExtractor:
    """Main coordinator for PDF content extraction."""

    def __init__(self):
        """Initialize PDF extractor components."""
        self.logger = get_logger("PDFExtractor")
        self.text_extractor = TextExtractor()

    def process_pdf(self, pdf_path: str, task_id: Optional[str] = None, file_id: Optional[str] = None,
                    method: str = 'unstructured') -> Dict:
        """
        Process a single PDF file with proper directory structure verification.

        Args:
            pdf_path: Path to the PDF file
            task_id: Optional task identifier for organized storage
            file_id: Optional file identifier for organized storage
            method: Extraction method to use
        """
        try:
            # Validate input path
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")

            # Setup extraction directories
            if task_id and file_id:
                # Use task-based organization
                extract_dir = self._setup_task_directories(task_id, file_id, pdf_path.stem)
                doc_id = file_id
            else:

                # Fallback to UUID-based organization
                doc_id = str(uuid.uuid4())
                extract_dir = self._setup_directories(pdf_path.stem)

            # Configure text extractor with correct output directory
            self.text_extractor.output_dir = extract_dir

            # Save original PDF
            target_pdf = self._save_original_pdf(pdf_path, extract_dir)

            # Extract content
            results = self._extract_content(str(target_pdf), method, extract_dir)

            # Save results with verification
            self._save_content_file(results, extract_dir)
            self._save_metadata(results, extract_dir)

            # Verify required files and directories exist
            text_dir = extract_dir / "text"
            content_file = text_dir / "content.txt"
            metadata_dir = extract_dir / "metadata"

            # Check critical paths
            required_paths = {
                'text_directory': text_dir,
                'content_file': content_file,
                'metadata_directory': metadata_dir
            }

            for name, path in required_paths.items():
                if not path.exists():
                    raise IOError(f"Failed to create {name}: {path}")

            # Return successful results
            return {
                'doc_id': doc_id,
                'task_id': task_id,
                'file_id': file_id,
                'file_name': pdf_path.stem,
                'content': results,
                'paths': {
                    'original_pdf': str(target_pdf),
                    'extracted_dir': str(extract_dir),
                    'content_file': str(content_file),
                    'metadata_dir': str(metadata_dir)
                },
                'extraction_method': method,
                'stats': {
                    'text_elements': len(results.get('text', [])),
                    'total_elements': len(results.get('text', []))
                }
            }

        except Exception as e:
            self.logger.error(f"Failed to process PDF {pdf_path}: {str(e)}")
            raise

    def _verify_directory_structure(self, extract_dir: Path) -> bool:
        """Verify that all required directories and files exist."""
        required_structure = [
            extract_dir / "text" / "content.txt",
            extract_dir / "metadata"
            # Removed images and tables directories
        ]

        return all(path.exists() for path in required_structure)

    def _extract_content(self, pdf_path: str, method: str, extract_dir: Path) -> Dict:
        """Extract content using specified method."""
        results = {}

        try:
            # Set output directory for text extractor only
            self.text_extractor.output_dir = extract_dir

            # Extract text only
            self.logger.info("Starting text extraction...")
            results['text'] = self.text_extractor.extract(pdf_path, method)

            # Initialize empty lists for compatibility with existing code
            results['images'] = []
            results['tables'] = []

            return results

        except Exception as e:
            self.logger.error(f"Content extraction failed: {str(e)}")
            raise

    def process_directory(self, dir_path: Union[str, Path], method: str = 'unstructured') -> Dict[str, Dict]:
        """Process all PDFs in a directory."""
        # Method implementation unchanged
        dir_path = Path(dir_path)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        results = {}
        pdf_files = list(dir_path.glob("*.pdf"))

        if not pdf_files:
            self.logger.warning(f"No PDF files found in {dir_path}")
            return results

        total_files = len(pdf_files)
        self.logger.info(f"Processing {total_files} PDF files from {dir_path}")

        for index, pdf_file in enumerate(pdf_files, 1):
            try:
                self.logger.info(f"Processing file {index}/{total_files}: {pdf_file.name}")
                results[pdf_file.name] = self.process_pdf(str(pdf_file), method)
                self.logger.info(f"Successfully processed {pdf_file.name}")
            except Exception as e:
                self.logger.error(f"Error processing {pdf_file.name}: {str(e)}")
                results[pdf_file.name] = {'error': str(e)}

        return results

    def process_files(self, pdf_paths: List[Union[str, Path]], method: str = 'unstructured') -> Dict[str, Dict]:
        """Process a list of PDF files."""
        # Method implementation unchanged
        results = {}
        total_files = len(pdf_paths)

        self.logger.info(f"Processing {total_files} PDF files")

        for index, pdf_path in enumerate(pdf_paths, 1):
            pdf_path = Path(pdf_path)
            try:
                self.logger.info(f"Processing file {index}/{total_files}: {pdf_path.name}")
                results[pdf_path.name] = self.process_pdf(str(pdf_path), method)
                self.logger.info(f"Successfully processed {pdf_path.name}")
            except Exception as e:
                self.logger.error(f"Error processing {pdf_path.name}: {str(e)}")
                results[pdf_path.name] = {'error': str(e)}

        return results

    def _setup_task_directories(self, task_id: str, file_id: str, file_name: str) -> Path:
        """Setup directory structure for task-based organization."""
        try:
            # Create base directory structure
            extract_dir = EXTRACTED_DIR / task_id / file_id

            # Create necessary subdirectories - only text and metadata
            required_dirs = ['text', 'metadata']
            for subdir in required_dirs:
                (extract_dir / subdir).mkdir(parents=True, exist_ok=True)

            # Save basic file information
            info_file = extract_dir / "metadata" / "extraction_info.json"
            info_data = {
                "task_id": task_id,
                "file_id": file_id,
                "original_filename": file_name,
                "timestamp": datetime.now().isoformat()
            }

            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(info_data, f, indent=2)

            self.logger.info(f"Created task-based directory structure at {extract_dir}")
            return extract_dir

        except Exception as e:
            self.logger.error(f"Failed to setup task directories: {str(e)}")
            raise

    def _setup_directories(self, file_name: str) -> Path:
        """Setup directory structure for UUID-based organization."""
        try:
            # Generate UUID for unique folder
            extraction_id = str(uuid.uuid4())
            extract_dir = EXTRACTED_DIR / extraction_id

            # Create necessary subdirectories - only text and metadata
            required_dirs = ['text', 'metadata']
            for subdir in required_dirs:
                (extract_dir / subdir).mkdir(parents=True, exist_ok=True)

            # Save basic file information
            info_file = extract_dir / "metadata" / "extraction_info.json"
            info_data = {
                "original_filename": file_name,
                "extraction_id": extraction_id,
                "timestamp": datetime.now().isoformat()
            }

            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(info_data, f, indent=2)

            self.logger.info(f"Created UUID-based directory structure at {extract_dir}")
            return extract_dir

        except Exception as e:
            self.logger.error(f"Failed to setup directories: {str(e)}")
            raise

    def _save_original_pdf(self, pdf_path: Path, extract_dir: Path) -> Path:
        """Save the original PDF directly in the extraction directory."""
        try:
            # Save PDF directly in the UUID directory
            target_path = extract_dir / pdf_path.name
            target_path.write_bytes(pdf_path.read_bytes())

            self.logger.info(f"Saved original PDF {pdf_path.name}")
            return target_path

        except Exception as e:
            self.logger.error(f"Error saving original PDF: {str(e)}")
            raise

    def _save_content_file(self, results: Dict, extract_dir: Path):
        """Save extracted content with proper directory structure and error handling."""
        try:
            # Ensure text directory exists
            text_dir = extract_dir / "text"
            text_dir.mkdir(parents=True, exist_ok=True)

            # Save unified content.txt in the text directory
            content_file = text_dir / "content.txt"

            # Create parent directories if they don't exist
            content_file.parent.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"Saving content to {content_file}")

            with open(content_file, 'w', encoding='utf-8') as f:
                for content_type, elements in results.items():
                    if content_type in ['text'] and elements:  # Only process text elements
                        for element in elements:
                            f.write(f"\n{'=' * 80}\n")
                            f.write(f"Content Type: {content_type}\n")
                            f.write(f"Page Number: {element.metadata.get('page_number', 'N/A')}\n")
                            f.write(f"{'=' * 80}\n\n")
                            f.write(str(element.content))
                            f.write("\n\n")

            # Verify file was created successfully
            if not content_file.exists():
                raise IOError(f"Failed to create content file: {content_file}")

            self.logger.info(f"Successfully saved content to {content_file}")

            # Save individual elements using text extractor
            if results.get('text'):
                for text_elem in results['text']:
                    self.text_extractor._save_text_content(
                        text_elem.content,
                        text_elem.metadata,
                        str(extract_dir)
                    )

        except Exception as e:
            self.logger.error(f"Error saving content files: {str(e)}")
            raise

    def _save_metadata(self, results: Dict, extract_dir: Path):
        """Save metadata directly in metadata directory without creating additional folders."""
        try:
            # Create metadata directory if it doesn't exist
            metadata_dir = extract_dir / "metadata"
            metadata_dir.mkdir(parents=True, exist_ok=True)

            # Save metadata files directly in metadata directory
            for content_type, elements in results.items():
                if not elements or content_type not in ['text']:  # Only process text elements
                    continue

                # Create metadata list
                metadata_list = []
                for element in elements:
                    # Clean metadata to remove file paths that might create directories
                    metadata = element.metadata.copy() if hasattr(element.metadata, 'copy') else element.metadata
                    if isinstance(metadata, dict):
                        # Remove any keys that contain full file paths
                        metadata = {k: v for k, v in metadata.items()
                                    if not (isinstance(v, str) and ('\\' in v or '/' in v))}
                    metadata_list.append(metadata)

                # Save metadata file directly in metadata directory
                metadata_file = metadata_dir / f"{content_type}_metadata.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata_list, f, indent=2, ensure_ascii=False)

                self.logger.info(f"Saved metadata for {content_type} to {metadata_file}")

            # Save file mapping
            mapping_file = metadata_dir / "file_mapping.json"
            mapping_data = {
                "original_filename": extract_dir.name,
                "extraction_time": datetime.now().isoformat(),
                "content_types": ["text"]  # Only include text type
            }
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(mapping_data, f, indent=2)

        except Exception as e:
            self.logger.error(f"Error saving metadata: {str(e)}")
            raise

    def extract_text_content(self, file_path: str) -> Dict[str, str]:
        """
        Extract text content from a PDF file.
        
        This method provides a simplified interface that's compatible with 
        the document_processor helper method.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dict containing extracted text content
        """
        try:
            # Use the main process_pdf method
            result = self.process_pdf(file_path, method='unstructured')
            
            # Extract text content from the results
            text_elements = result.get('content', {}).get('text', [])
            
            # Combine all text content
            combined_text = ""
            for element in text_elements:
                if hasattr(element, 'content'):
                    combined_text += element.content + "\n\n"
                else:
                    combined_text += str(element) + "\n\n"
            
            return {
                'text': combined_text.strip(),
                'extraction_method': result.get('extraction_method', 'unstructured'),
                'file_name': result.get('file_name', ''),
                'stats': result.get('stats', {})
            }
            
        except Exception as e:
            self.logger.error(f"Text extraction failed for {file_path}: {str(e)}")
            return {
                'text': '',
                'error': str(e),
                'extraction_method': 'failed'
            }

    def get_extraction_stats(self, results: Dict) -> Dict:
        """Get statistics about the extraction process."""
        return {
            'text_elements': len(results.get('text', [])),
            'image_elements': 0,  # Set to 0 for compatibility
            'table_elements': 0,  # Set to 0 for compatibility
            'total_elements': len(results.get('text', [])),
            'timestamp': datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Setup argument parser
    parser = argparse.ArgumentParser(description='Extract content from PDF files')
    parser.add_argument('input', help='PDF file or directory path')
    parser.add_argument(
        '--method',
        choices=['pymupdf', 'gmft', 'nougat'],
        default='pymupdf',
        help='Extraction method to use'
    )
    parser.add_argument(
        '--batch',
        action='store_true',
        help='Process input as directory'
    )

    args = parser.parse_args()
    extractor = PDFExtractor()

    try:
        if args.batch:
            # Process directory
            print(f"\nProcessing directory: {args.input}")
            results = extractor.process_directory(args.input, method=args.method)

            # Print results for each file
            for filename, result in results.items():
                if 'error' in result:
                    print(f"\n{filename}: Failed - {result['error']}")
                else:
                    stats = extractor.get_extraction_stats(result['content'])
                    print(f"\n{filename}:")
                    print(f"- Text elements: {stats['text_elements']}")
                    print(f"- Total elements: {stats['total_elements']}")
                    print(f"- Output directory: {result['paths']['extracted_dir']}")

        else:
            # Process single file
            print(f"\nProcessing file: {args.input}")
            result = extractor.process_pdf(args.input, method=args.method)

            # Print results
            stats = extractor.get_extraction_stats(result['content'])
            print("\nExtraction Results:")
            print(f"Document ID: {result['doc_id']}")
            print(f"Method: {result['extraction_method']}")
            print(f"Text elements: {stats['text_elements']}")
            print(f"Total elements: {stats['total_elements']}")
            print(f"Output directory: {result['paths']['extracted_dir']}")

    except Exception as e:
        print(f"Error: {str(e)}")