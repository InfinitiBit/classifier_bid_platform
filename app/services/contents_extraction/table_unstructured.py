import os
import sys
from pathlib import Path

# Add project root to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from typing import Dict, List
from datetime import datetime
import time

# Unstructured imports
from unstructured.partition.pdf import partition_pdf
from unstructured_inference.models.tables import load_agent

# GMFT imports
# from gmft_pymupdf import PyMuPDFDocument
# from gmft.auto import (
#     TableDetector,
#     AutoTableFormatter,
#     AutoFormatConfig,
#     CroppedTable
# )

# Project imports
from app.utils.logging import get_logger
from app.config import DOCUMENTS_DIR, EXTRACTED_DIR
from .element import ContentElement


class TableExtractor:
    """Table content extractor with multiple methods."""

    def __init__(self, output_dir: Path = None):
        """Initialize table extractor."""
        self.logger = get_logger("TableExtractor")
        self.output_dir = output_dir or EXTRACTED_DIR
        load_agent()  # Load table detection model

    def extract(self, pdf_path: str, method: str = 'unstructured') -> List[ContentElement]:
        """Extract tables using specified method."""
        methods = {
            'unstructured': self._extract_unstructured,
            'gmft': self._extract_gmft
        }

        if method not in methods:
            raise ValueError(f"Unsupported method: {method}")

        try:
            return methods[method](pdf_path)
        except Exception as e:
            self.logger.error(f"Table extraction failed: {str(e)}")
            raise

    def _extract_unstructured(self, pdf_path: str) -> List[ContentElement]:
        """Extract tables using unstructured library."""
        self.logger.info(f"Starting unstructured table extraction from {pdf_path}")

        # Use tables directory directly under the UUID directory
        tables_dir = self.output_dir / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)

        elements = partition_pdf(
            filename=pdf_path,
            include_metadata=True,
            strategy="hi_res",
            infer_table_structure=True,
            include_table_data=True
        )

        valid_elements = []
        tables_by_page = {}

        # Filter tables from elements
        tables = [el for el in elements if el.category == "Table"]

        for table in tables:
            content = table.text.strip()
            if not content:
                continue

            # Access metadata attributes directly or via __dict__
            metadata_dict = table.metadata.__dict__ if hasattr(table.metadata, '__dict__') else {}
            page_num = getattr(table.metadata, 'page_number', None)

            # Track table index for this page
            if page_num not in tables_by_page:
                tables_by_page[page_num] = 0
            tables_by_page[page_num] += 1
            table_idx = tables_by_page[page_num]

            # Get HTML content
            html_content = getattr(table.metadata, 'text_as_html', "") or ""
            formatted_text = self._format_table_text(content)

            # Convert coordinates to dictionary
            coordinates = getattr(table.metadata, 'coordinates', None)
            coordinates_dict = self._convert_coordinates_to_dict(coordinates) if coordinates else {}

            # Save content to file
            file_path = self._save_table_content(
                content,
                html_content,
                formatted_text,
                page_num,
                table_idx,
                self.output_dir  # Pass the UUID directory directly
            )

            # Create enhanced metadata with serializable coordinates
            table_metadata = {
                'page_number': page_num,
                'table_index': table_idx,
                'element_id': f"table_page_{page_num}_idx_{table_idx}",
                'content_type': 'table',
                'extraction_method': 'unstructured',
                'coordinates': coordinates_dict,
                'table_structure': getattr(table.metadata, 'table_structure', {}),
                'html_content': html_content,
                'text_content': formatted_text,
                'raw_text': content,
                'file_path': str(file_path),
                'dimensions': {
                    'rows': len(content.split('\n')),
                    'columns': len(content.split('\n')[0].split()) if content else 0
                },
                'timestamp': datetime.now().isoformat()
            }

            valid_elements.append(ContentElement(content, "table", table_metadata))

        self.logger.success(f"Successfully extracted {len(valid_elements)} tables")
        return valid_elements

    def _extract_gmft(self, pdf_path: str) -> List[ContentElement]:
        """Extract tables using GMFT."""
        self.logger.info(f"Starting GMFT table extraction from {pdf_path}")

        # Initialize GMFT components
        detector = TableDetector()
        config = AutoFormatConfig()
        config.semantic_spanning_cells = True
        config.enable_multi_header = True
        formatter = AutoTableFormatter(config)

        # Create output directories
        tables_dir = self.output_dir / "tables" / "gmft"
        crops_dir = self.output_dir / "tables" / "crops"
        for dir_path in [tables_dir, crops_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        valid_elements = []
        timing_info = {}

        try:
            # Extract tables
            start_time = time.time()
            doc = PyMuPDFDocument(pdf_path)
            tables = []
            num_pages = 0

            # Process each page
            for page_idx, page in enumerate(doc, 1):
                if page is None:
                    continue
                num_pages = page_idx
                page_tables = detector.extract(page)
                if page_tables:
                    tables.extend(page_tables)

            detect_time = time.time() - start_time

            # Format and process tables
            format_start_time = time.time()
            for table_idx, table in enumerate(tables, 1):
                formatted_table = formatter.extract(table)
                if not formatted_table:
                    continue

                # Get table content
                table_content = str(formatted_table)

                # Save table content
                table_file = tables_dir / f"table_{table_idx}.txt"
                table_file.write_text(table_content)

                # Try to save as CSV
                try:
                    df = formatted_table.df()
                    if df is not None:
                        csv_path = tables_dir / f"table_{table_idx}.csv"
                        df.to_csv(str(csv_path), index=True)
                except Exception as e:
                    self.logger.warning(f"Failed to save CSV for table {table_idx}: {str(e)}")

                # Try to save table image
                try:
                    image = formatted_table.image()
                    if image:
                        image_path = crops_dir / f"table_{table_idx}.png"
                        image.save(str(image_path))
                except Exception as e:
                    self.logger.warning(f"Failed to save image for table {table_idx}: {str(e)}")

                # Get coordinates
                try:
                    coords = {
                        'x0': formatted_table.bbox[0] if hasattr(formatted_table, 'bbox') else 0,
                        'y0': formatted_table.bbox[1] if hasattr(formatted_table, 'bbox') else 0,
                        'x1': formatted_table.bbox[2] if hasattr(formatted_table, 'bbox') else 0,
                        'y1': formatted_table.bbox[3] if hasattr(formatted_table, 'bbox') else 0
                    }
                except:
                    coords = {'x0': 0, 'y0': 0, 'x1': 0, 'y1': 0}

                # Create metadata
                metadata = {
                    'page_number': page_idx,
                    'element_id': f"table_gmft_{table_idx}",
                    'content_type': 'table',
                    'extraction_method': 'gmft',
                    'coordinates': coords,
                    'table_file': str(table_file),
                    'timestamp': datetime.now().isoformat()
                }

                valid_elements.append(ContentElement(table_content, "table", metadata))

            # Calculate timing information
            format_time = time.time() - format_start_time
            total_time = time.time() - start_time

            timing_info = {
                'detection_time': detect_time,
                'format_time': format_time,
                'total_time': total_time,
                'pages': num_pages,
                'tables': len(tables),
                'avg_time_per_page': total_time / num_pages if num_pages else 0,
                'avg_time_per_table': format_time / len(tables) if tables else 0
            }

        finally:
            doc.close()

        self.logger.success(
            f"Successfully extracted {len(valid_elements)} tables using GMFT\n"
            f"Detection: {timing_info.get('detection_time', 0):.3f}s\n"
            f"Formatting: {timing_info.get('format_time', 0):.3f}s"
        )

        return valid_elements

    def _convert_coordinates_to_dict(self, coordinates):
        """Convert coordinates metadata to serializable dictionary."""
        if hasattr(coordinates, '__dict__'):
            # If it's an object with attributes, convert to dict
            coords_dict = {}
            for key, value in coordinates.__dict__.items():
                if key.startswith('_'):  # Skip private attributes
                    continue
                # Recursively convert nested objects
                if hasattr(value, '__dict__'):
                    coords_dict[key] = self._convert_coordinates_to_dict(value)
                else:
                    coords_dict[key] = value
            return coords_dict
        elif isinstance(coordinates, (list, tuple)):
            # If it's a list/tuple, convert each element
            return [self._convert_coordinates_to_dict(item) for item in coordinates]
        else:
            # If it's a basic type, return as is
            return coordinates

    def _convert_to_html(self, table_content: str) -> str:
        """Convert table content to HTML format."""
        rows = [row.strip() for row in table_content.split('\n') if row.strip()]
        if not rows:
            return ""

        html = ['<table class="table table-bordered">']

        # Add header row
        header = rows[0].split()
        html.append('<thead><tr>')
        for cell in header:
            html.append(f'<th>{cell}</th>')
        html.append('</tr></thead>')

        # Add data rows
        html.append('<tbody>')
        for row in rows[1:]:
            cells = row.split()
            html.append('<tr>')
            for cell in cells:
                html.append(f'<td>{cell}</td>')
            html.append('</tr>')
        html.append('</tbody>')
        html.append('</table>')

        return '\n'.join(html)

    def _format_table_text(self, table_content: str) -> str:
        """Format raw table text for better readability."""
        rows = [row.strip() for row in table_content.split('\n') if row.strip()]
        if not rows:
            return ""

        # Get maximum width for each column
        rows_data = [row.split() for row in rows]
        col_widths = [max(len(cell) for cell in column)
                      for column in zip(*rows_data)]

        # Format each row with proper spacing
        formatted_rows = []
        for row in rows_data:
            formatted_cells = [
                cell.ljust(width) for cell, width in zip(row, col_widths)
            ]
            formatted_rows.append(" | ".join(formatted_cells))

        # Add separator line after header
        separator = "-" * len(formatted_rows[0])
        formatted_rows.insert(1, separator)

        return "\n".join(formatted_rows)

    def _save_table_content(self, table_content: str, html_content: str, formatted_text: str,
                            page_num: int, table_idx: int, extract_dir: Path) -> Path:
        """Save table content in both formats."""
        # Create table directory directly under the UUID directory
        table_dir = extract_dir / "tables"
        table_dir.mkdir(parents=True, exist_ok=True)

        # Save both formats to file
        file_path = table_dir / f"table_page_{page_num}_idx_{table_idx}.txt"
        content = (
            f"FORMATTED TABLE TEXT:\n"
            f"{'=' * 80}\n"
            f"{formatted_text}\n\n"
            f"HTML VERSION:\n"
            f"{'=' * 80}\n"
            f"{html_content}\n\n"
            f"RAW TABLE TEXT:\n"
            f"{'=' * 80}\n"
            f"{table_content}"
        )

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return file_path

    def _validate_table(self, content: str) -> bool:
        """Validate table content."""
        if not content.strip():
            return False

        # Basic validation - check for minimum rows/columns
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        if len(lines) < 2:  # Need at least header and one data row
            return False

        # Check for consistent column count
        col_counts = [len(line.split()) for line in lines]
        return len(set(col_counts)) == 1  # All rows should have same number of columns

    def _format_table_content(self, content: str) -> str:
        """Format table content for better readability."""
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        if not lines:
            return ""

        # Normalize column widths
        rows = [line.split() for line in lines]
        col_widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]

        # Format rows with consistent spacing
        formatted_rows = []
        for row in rows:
            formatted_row = " | ".join(
                cell.ljust(width) for cell, width in zip(row, col_widths)
            )
            formatted_rows.append(formatted_row)

        return "\n".join(formatted_rows)