import os
import sys
from pathlib import Path

# Add project root to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from typing import Dict, List
from datetime import datetime

# Unstructured imports
from unstructured.partition.pdf import partition_pdf
from PIL import Image

# Project imports
from app.utils.logging import get_logger
from app.config import EXTRACTED_DIR
from app.services.contents_extraction.element import ContentElement


class ImageExtractor:
    """Image content extractor from PDFs."""

    def __init__(self, output_dir: Path = None):
        """Initialize image extractor."""
        self.logger = get_logger("ImageExtractor")
        self.output_dir = output_dir or EXTRACTED_DIR

    def extract(self, pdf_path: str, method: str = 'unstructured') -> List[ContentElement]:
        """Extract images from PDF."""
        if method != 'unstructured':
            self.logger.warning(f"Method {method} not supported for images, using unstructured")

        try:
            return self._extract_unstructured(pdf_path)
        except Exception as e:
            self.logger.error(f"Image extraction failed: {str(e)}")
            raise

    def _extract_unstructured(self, pdf_path: str) -> List[ContentElement]:
        """Extract images using unstructured library with correct page number extraction."""
        self.logger.info(f"Starting image extraction from {pdf_path}")

        # Use the provided output directory directly
        image_dir = self.output_dir / "images"
        image_dir.mkdir(parents=True, exist_ok=True)

        # Extract images
        elements = partition_pdf(
            filename=pdf_path,
            include_metadata=True,
            strategy="hi_res",
            hi_res_model_name="yolox",
            extract_images_in_pdf=True,
            extract_image_block_output_dir=str(image_dir),
            extract_image_block_types=["Image", "Figure"],
            include_image_data=True
        )

        valid_elements = []
        image_files = sorted(list(image_dir.glob("*.*")))

        for image_file in image_files:
            try:
                if self._validate_image(image_file):
                    # Extract page number and figure number from filename
                    # Pattern: figure-{page}-{index}.jpg
                    page_num = 1  # Default value
                    fig_num = None
                    try:
                        filename_parts = image_file.stem.split('-')
                        if len(filename_parts) >= 3:
                            # Extract page number from the second part
                            page_num = int(filename_parts[1])
                            # Extract figure number from first part + second part
                            fig_num = f"Figure {filename_parts[1]}"
                    except (ValueError, IndexError) as e:
                        self.logger.warning(f"Failed to parse page/figure number from {image_file.name}: {str(e)}")

                    # Create metadata with relative path
                    image_metadata = {
                        'page_number': page_num,  # Now correctly extracted from filename
                        'figure_number': fig_num,
                        'filename': image_file.name,
                        'element_id': f"img_{len(valid_elements) + 1}",
                        'extraction_method': 'unstructured'
                    }

                    # Add image properties
                    try:
                        with Image.open(image_file) as img:
                            image_metadata['properties'] = {
                                'width': img.width,
                                'height': img.height,
                                'format': img.format,
                                'mode': img.mode
                            }
                    except Exception as e:
                        self.logger.warning(f"Failed to get image properties: {str(e)}")

                    valid_elements.append(ContentElement(
                        f"Image: {image_file.name}",
                        "image",
                        image_metadata
                    ))

                    self.logger.debug(f"Processed image: {image_file.name}")

            except Exception as e:
                self.logger.warning(f"Failed to process image {image_file.name}: {str(e)}")

        self.logger.success(f"Successfully extracted {len(valid_elements)} images")
        return valid_elements

    def _is_image_element(self, category: str, element_type: str) -> bool:
        """Check if element is an image."""
        return (
                category == "Image" or
                element_type == "Image" or
                "Figure" in str(element_type)
        )

    def _validate_image(self, image_path: Path) -> bool:
        """Validate extracted image."""
        try:
            with Image.open(image_path) as img:
                # Check image size
                if img.size[0] < 10 or img.size[1] < 10:
                    return False

                # Check if image is empty or corrupted
                if img.getbbox() is None:
                    return False

                # Basic format validation
                if img.format not in ['JPEG', 'PNG', 'TIFF']:
                    return False

                return True
        except Exception as e:
            self.logger.warning(f"Image validation failed for {image_path}: {str(e)}")
            return False


if __name__ == "__main__":
    import argparse

    # Simple argument parser just for PDF path
    parser = argparse.ArgumentParser(description='Extract images from PDF')
    parser.add_argument('pdf_path', type=str, help='Path to the PDF file')

    args = parser.parse_args()

    # Create extractor using default output directory
    extractor = ImageExtractor()

    try:
        # Extract images
        elements = extractor.extract(args.pdf_path)
        print(f"Successfully extracted {len(elements)} images")

    except Exception as e:
        print(f"Error: {str(e)}")