import os, sys
from pathlib import Path

# Add project root to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from typing import Dict, List
from datetime import datetime
import subprocess

# Main extraction libraries
from unstructured.partition.pdf import partition_pdf
import fitz
# from gmft_pymupdf import PyMuPDFDocument

# Project imports
from app.utils.logging import get_logger
from app.config import DOCUMENTS_DIR, EXTRACTED_DIR
from .element import ContentElement


class TextExtractor:
    """Text content extractor with multiple methods."""

    def __init__(self, output_dir: Path = None):
        self.logger = get_logger("TextExtractor")
        self.output_dir = output_dir or EXTRACTED_DIR

    def extract(self, pdf_path: str, method: str = 'unstructured') -> List[ContentElement]:
        """Extract text using specified method."""
        methods = {
            'unstructured': self._extract_unstructured,
            'pymupdf': self._extract_pymupdf,
            'nougat': self._extract_nougat
        }

        if method not in methods:
            raise ValueError(f"Unsupported method: {method}")

        try:
            return methods[method](pdf_path)
        except Exception as e:
            self.logger.error(f"Text extraction failed: {str(e)}")
            raise

    def _extract_unstructured(self, pdf_path: str) -> List[ContentElement]:
        """Extract text using unstructured library."""
        self.logger.info(f"Starting unstructured text extraction from {pdf_path}")

        # Use extraction directory directly
        extraction_dir = self.output_dir
        text_dir = extraction_dir / "text"
        text_dir.mkdir(parents=True, exist_ok=True)

        elements = partition_pdf(
            filename=pdf_path,
            include_metadata=True,
            strategy="fast",
            extract_images_in_pdf=False
        )

        # Group by page and store raw elements
        pages = {}
        for element in elements:
            element_dict = element.to_dict() if hasattr(element, 'to_dict') else {}
            content = element_dict.get('text', '').strip()
            page_number = element_dict.get('metadata', {}).get('page_number')

            # Skip non-text elements
            if not content or element_dict.get('type') == 'Image' or element_dict.get('category') == 'Image':
                continue

            if page_number not in pages:
                pages[page_number] = {
                    'texts': [],
                    'raw_elements': []
                }

            pages[page_number]['texts'].append(content)
            pages[page_number]['raw_elements'].append({
                'text': content,
                'type': element_dict.get('type', ''),
                'category': element_dict.get('category', ''),
                'coordinates': element_dict.get('metadata', {}).get('coordinates', {}),
            })

        # Create content elements with enhanced metadata
        valid_elements = []
        all_text = []  # Collect all text for full context

        for page_number in sorted(pages.keys()):
            page_data = pages[page_number]
            combined_text = "\n\n".join(page_data['texts'])
            all_text.append(combined_text)

            # Group elements by type
            type_counts = {}
            for elem in page_data['raw_elements']:
                elem_type = elem['type']
                type_counts[elem_type] = type_counts.get(elem_type, 0) + 1

            metadata = {
                'page_number': page_number,
                'element_type': 'text',
                'category': '',
                'element_count': len(page_data['raw_elements']),
                'element_types': type_counts,
                'text_length': len(combined_text),
                'raw_elements': page_data['raw_elements'],
                'extraction_method': 'unstructured'
            }

            # Save individual page content
            save_paths = self._save_text_content(combined_text, metadata, str(extraction_dir))
            metadata['file_paths'] = save_paths

            valid_elements.append(ContentElement(combined_text, "text", metadata))

        # Save full context
        if all_text:
            full_context = "\n\n".join(all_text)
            full_context_metadata = {
                'page_number': 'all',
                'element_type': 'text',
                'extraction_method': 'unstructured'
            }
            self._save_text_content(full_context, full_context_metadata, str(extraction_dir))

        self.logger.success(f"Successfully extracted {len(valid_elements)} text elements")
        return valid_elements

    def _extract_pymupdf(self, pdf_path: str) -> List[ContentElement]:
        """Extract text using PyMuPDF."""
        self.logger.info(f"Starting PyMuPDF text extraction from {pdf_path}")
        valid_elements = []

        doc = fitz.open(pdf_path)
        try:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                text = page.get_text("text")
                blocks = page.get_text("blocks")

                if text.strip():
                    metadata = {
                        'page_number': page_idx + 1,
                        'element_type': 'text',
                        'category': '',
                        'text_length': len(text),
                        'block_count': len(blocks),
                        'raw_elements': blocks,  # Store raw block data
                        'page_dimensions': {
                            'width': page.rect.width,
                            'height': page.rect.height
                        },
                        'extraction_method': 'pymupdf'
                    }
                    valid_elements.append(ContentElement(text, "text", metadata))
        finally:
            doc.close()

        return valid_elements

    def _extract_nougat(self, pdf_path: str) -> List[ContentElement]:
        """Extract text using Nougat OCR."""
        self.logger.info(f"Starting Nougat text extraction from {pdf_path}")

        valid_elements = []
        output_dir = self.output_dir / "nougat" / Path(pdf_path).stem
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run Nougat command...
        command = [
            "nougat",
            str(pdf_path),
            "-o", str(output_dir),
            "--markdown",
            "--no-skipping",
            "-m", "0.1.0-base"
        ]

        try:
            process = subprocess.run(command, capture_output=True, text=True, check=True)
            mmd_files = list(output_dir.glob("*.mmd"))
            if not mmd_files:
                raise FileNotFoundError("No .mmd files found")

            content = mmd_files[0].read_text(encoding='utf-8')
            current_page = ""
            current_page_num = 1

            for line in content.split('\n'):
                if line.strip().startswith('[Page ') and line.strip().endswith(']'):
                    if current_page:
                        metadata = {
                            'page_number': current_page_num,
                            'element_type': 'text',
                            'category': '',
                            'text_length': len(current_page),
                            'raw_content': current_page,
                            'model': '0.1.0-base',
                            'markdown_enabled': True,
                            'extraction_method': 'nougat'
                        }
                        valid_elements.append(ContentElement(current_page, "text", metadata))

                    current_page = ""
                    try:
                        current_page_num = int(line.strip()[6:-1])
                    except ValueError:
                        current_page_num += 1
                else:
                    current_page += line + '\n'

            # Handle last page
            if current_page:
                metadata = {
                    'page_number': current_page_num,
                    'element_type': 'text',
                    'category': '',
                    'text_length': len(current_page),
                    'raw_content': current_page,
                    'model': '0.1.0-base',
                    'markdown_enabled': True,
                    'extraction_method': 'nougat'
                }
                valid_elements.append(ContentElement(current_page, "text", metadata))

        except Exception as e:
            self.logger.error(f"Nougat extraction error: {e}")
            raise

        return valid_elements

    # def _save_text_content(self, content: str, metadata: Dict, pdf_name: str) -> Dict[str, str]:
    #     """Save text content in organized directory structure."""
    #     # Create main text directory
    #     text_dir = self.output_dir / pdf_name / "text"
    #     pages_dir = text_dir / "page_contents"
    #
    #     # Create directories
    #     for dir_path in [text_dir, pages_dir]:
    #         dir_path.mkdir(parents=True, exist_ok=True)
    #
    #     if metadata.get('page_number') == 'all':
    #         # Save full context
    #         full_context_path = text_dir / "complete_text.txt"
    #         with open(full_context_path, 'w', encoding='utf-8') as f:
    #             # Remove ================ lines and headers, keep only content
    #             contents = content.split(
    #                 "================================================================================")
    #             filtered_contents = []
    #
    #             for section in contents:
    #                 if not section.strip():
    #                     continue
    #
    #                 lines = section.strip().split('\n')
    #                 # Skip Content Type and Page Number lines
    #                 content_lines = [line for line in lines
    #                                  if not line.startswith('Content Type:') and
    #                                  not line.startswith('Page Number:')]
    #
    #                 if content_lines:
    #                     filtered_text = '\n'.join(line for line in content_lines if line.strip())
    #                     filtered_contents.append(filtered_text)
    #
    #             cleaned_text = '\n\n'.join(filtered_contents)
    #             f.write(cleaned_text)
    #
    #         return {'full_context_path': str(full_context_path)}
    #     else:
    #         # Save individual page content
    #         page_path = pages_dir / f"page_{metadata['page_number']}.txt"
    #         with open(page_path, 'w', encoding='utf-8') as f:
    #             f.write(content)
    #
    #         return {'page_path': str(page_path)}

    def _save_text_content(self, content: str, metadata: Dict, extraction_dir: str) -> Dict[str, str]:
        """Save text content in organized directory structure."""
        # Create text directory in the extraction directory
        text_dir = Path(extraction_dir) / "text"
        pages_dir = text_dir / "page_contents"

        # Create directories
        for dir_path in [text_dir, pages_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        try:
            if metadata.get('page_number') == 'all':
                # Save full context
                full_context_path = text_dir / "complete_text.txt"
                with open(full_context_path, 'w', encoding='utf-8') as f:
                    # Remove ================ lines and headers, keep only content
                    contents = content.split("=" * 80)
                    filtered_contents = []

                    for section in contents:
                        if not section.strip():
                            continue

                        lines = section.strip().split('\n')
                        # Skip Content Type and Page Number lines
                        content_lines = [line for line in lines
                                         if not line.startswith('Content Type:') and
                                         not line.startswith('Page Number:')]

                        if content_lines:
                            filtered_text = '\n'.join(line for line in content_lines if line.strip())
                            filtered_contents.append(filtered_text)

                    cleaned_text = '\n\n'.join(filtered_contents)
                    f.write(cleaned_text)

                return {'full_context_path': str(full_context_path.relative_to(Path(extraction_dir)))}
            else:
                # Save individual page content
                page_path = pages_dir / f"page_{metadata['page_number']}.txt"
                with open(page_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                return {'page_path': str(page_path.relative_to(Path(extraction_dir)))}

        except Exception as e:
            self.logger.error(f"Failed to save text content: {str(e)}")
            return {}

    def _normalize_text(self, text: str) -> str:
        """Normalize extracted text content."""
        text = ' '.join(text.split())
        text = text.replace('\u2028', '\n').replace('\u2029', '\n')
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        return text.strip()