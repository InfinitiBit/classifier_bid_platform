"""
Image Extractor utility for extracting images from PDF files.
Modified to follow the task_id/file_id/images structure.
"""
import os
import io
import fitz  # PyMuPDF
import logging
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image
import numpy as np

from app.utils.logging import get_logger


class ImageExtractor:
    """Utility class for extracting images from PDF files."""

    def __init__(self, base_dir: str = None):
        """Initialize the image extractor.

        Args:
            base_dir: Base directory for output files
        """
        self.logger = get_logger("ImageExtractor")
        self.base_dir = Path(base_dir) if base_dir else Path("./extracted_images")

    def extract_images_from_pdf(self, pdf_path: str, project_path: Path,
                                filter_images: bool = True, min_size: int = 150,
                                file_id: Optional[str] = None) -> List[str]:
        """Extract images from a PDF file following the existing directory structure.

        Args:
            pdf_path: Path to the PDF file
            project_path: Path to the project directory (task_id)
            filter_images: Whether to filter images to keep only good ones
            min_size: Minimum width or height in pixels for filtering
            file_id: Optional file_id for maintaining directory structure

        Returns:
            List of paths to extracted images
        """
        try:
            self.logger.info(f"Extracting images from {pdf_path}")

            # Determine output directory based on file_id
            if file_id:
                # Follow existing structure: task_id/file_id/images
                images_dir = project_path / file_id / "images"
            else:
                # Fallback to simple structure: task_id/images
                images_dir = project_path / "images"

            images_dir.mkdir(parents=True, exist_ok=True)

            # Rest of the extraction code remains the same...
            # (keeping the existing extraction logic)

            # Temporary directory for filtering
            temp_dir = None
            if filter_images:
                temp_dir = project_path / "images_temp"
                temp_dir.mkdir(parents=True, exist_ok=True)

            output_dir = str(temp_dir) if temp_dir else str(images_dir)

            # Extract images from PDF
            pdf_document = fitz.open(pdf_path)
            image_count = 0

            self.logger.info(f"Processing PDF with {len(pdf_document)} pages")

            # Process each page
            for page_num, page in enumerate(pdf_document):
                self.logger.info(f"Processing page {page_num + 1}/{len(pdf_document)}")

                # Get image list
                image_list = page.get_images(full=True)

                if len(image_list) == 0:
                    continue

                self.logger.info(f"Found {len(image_list)} images on page {page_num + 1}")

                # Process each image
                for img_index, img in enumerate(image_list):
                    try:
                        # Get the XREF of the image
                        xref = img[0]

                        # Extract the image bytes
                        base_image = pdf_document.extract_image(xref)
                        image_bytes = base_image["image"]

                        # Get the image extension
                        image_ext = base_image["ext"]

                        # Load it to PIL
                        image = Image.open(io.BytesIO(image_bytes))

                        # Save it to output directory
                        image_filename = f"page{page_num + 1}_img{img_index + 1}.{image_ext}"
                        image_path = os.path.join(output_dir, image_filename)
                        image.save(image_path)

                        self.logger.info(f"Saved image: {image_filename} ({image.width}x{image.height})")
                        image_count += 1

                    except Exception as e:
                        self.logger.error(f"Error extracting image {img_index} from page {page_num + 1}: {str(e)}")
                        continue

            # Close PDF document
            pdf_document.close()

            # Filter images if requested
            final_image_paths = []
            if filter_images and image_count > 0:
                final_image_paths = self._filter_images(temp_dir, images_dir, min_size)

                # Remove temporary directory
                shutil.rmtree(temp_dir)
            else:
                # If no filtering, all images are considered good
                final_image_paths = [str(images_dir / f) for f in os.listdir(output_dir)
                                     if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'))]

            self.logger.info(f"Extracted {len(final_image_paths)} images to {images_dir}")
            return final_image_paths

        except Exception as e:
            self.logger.error(f"Error extracting images from PDF: {str(e)}")
            raise

    def _is_good_image(self, image_path: str, min_size: int = 150,
                      max_black_ratio: float = 0.95, min_std_dev: float = 5.0) -> bool:
        """Determine if an image is a good content-rich image.

        Args:
            image_path: Path to the image file
            min_size: Minimum width or height in pixels
            max_black_ratio: Maximum ratio of black/very dark pixels
            min_std_dev: Minimum standard deviation of pixel values

        Returns:
            True if the image passes all quality checks
        """
        try:
            # Open image
            img = Image.open(image_path)

            # Check 1: Minimum size
            width, height = img.size
            if width < min_size or height < min_size:
                self.logger.debug(f"Image {image_path} too small: {width}x{height}")
                return False

            # Convert to RGB if not already
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Get image data as array
            img_array = np.array(img)

            # Check 2: Not predominantly black
            avg_pixel_value = np.mean(img_array)
            if avg_pixel_value < 30:  # Very dark/black
                black_pixels = np.sum(np.all(img_array < 30, axis=2))
                total_pixels = width * height
                black_ratio = black_pixels / total_pixels
                if black_ratio > max_black_ratio:
                    self.logger.debug(f"Image {image_path} too dark: {black_ratio:.2f} black ratio")
                    return False

            # Check 3: Has sufficient variation (not a solid color)
            std_dev = np.std(img_array)
            if std_dev < min_std_dev:
                self.logger.debug(f"Image {image_path} too uniform: {std_dev:.2f} std dev")
                return False

            # Check 4: Aspect ratio (filter out very thin lines or bars)
            aspect_ratio = max(width, height) / min(width, height)
            if aspect_ratio > 10:  # Very elongated
                self.logger.debug(f"Image {image_path} bad aspect ratio: {aspect_ratio:.2f}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error checking image quality for {image_path}: {e}")
            return False

    def _filter_images(self, source_dir: Path, dest_dir: Path, min_size: int = 150) -> List[str]:
        """Filter images from source_dir and copy good ones to dest_dir.

        Args:
            source_dir: Directory containing source images
            dest_dir: Directory to copy good images to
            min_size: Minimum width or height in pixels for filtering

        Returns:
            List of paths to good images
        """
        # Create destination directory if it doesn't exist
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Get all image files
        image_files = []
        for ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff']:
            image_files.extend([f for f in os.listdir(source_dir)
                              if f.lower().endswith(f'.{ext}')])

        total_images = len(image_files)
        if total_images == 0:
            self.logger.warning(f"No images found in {source_dir}")
            return []

        # Process each image
        good_images = 0
        good_image_paths = []

        self.logger.info(f"Filtering {total_images} images...")

        for img_file in image_files:
            img_path = os.path.join(source_dir, img_file)
            if self._is_good_image(img_path, min_size):
                # Copy to destination
                dest_path = os.path.join(dest_dir, img_file)
                shutil.copy2(img_path, dest_path)
                good_images += 1
                good_image_paths.append(dest_path)
                self.logger.info(f"Good image: {img_file}")
            else:
                self.logger.info(f"Filtered out: {img_file}")

        self.logger.info(f"Filtering results: {good_images}/{total_images} good images")
        return good_image_paths