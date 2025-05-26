import re
from typing import Dict, List, Any


class ContentFormatter:
    """
    Handles content cleaning and formatting for PDF extraction results.
    Removes metadata, page numbers, image references, and other formatting artifacts.
    """

    @staticmethod
    def clean_text_content(text: str) -> str:
        """
        Clean the text content from PDFs by removing metadata, page numbers,
        image references, and other formatting artifacts.

        Args:
            text: Raw text extracted from PDF

        Returns:
            Cleaned text with only the meaningful content
        """
        if not text:
            return ""

        # Remove content type and page number headers
        cleaned = re.sub(
            r"={80,}\s*Content Type: [^\n]*\s*Page Number: \d+\s*={80,}",
            "",
            text
        )

        # Remove page number references
        cleaned = re.sub(r"Page \d+ of \d+", "", cleaned)

        # Remove image references
        cleaned = re.sub(r"Image: [^\n]+", "", cleaned)

        # Remove any lingering separator lines
        cleaned = re.sub(r"={40,}", "", cleaned)

        # Clean up whitespace - replace 3+ consecutive newlines with just 2
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        # Final cleanup
        return cleaned.strip()

    @staticmethod
    def clean_search_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean a single search result by removing formatting artifacts from the text.

        Args:
            result: A single search result dict with 'text' field

        Returns:
            Updated result with cleaned text
        """
        if not result or not isinstance(result, dict):
            return result

        if "text" in result and result["text"]:
            result["text"] = ContentFormatter.clean_text_content(result["text"])

        return result

    @staticmethod
    def clean_search_results(search_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process search results to clean up text in each result.

        Args:
            search_results: Dictionary containing search results

        Returns:
            Updated search results with cleaned text
        """
        # Make a copy of the results to avoid modifying the original
        cleaned_results = search_results.copy()

        # Clean each result's text
        if "results" in cleaned_results and isinstance(cleaned_results["results"], list):
            cleaned_results["results"] = [
                ContentFormatter.clean_search_result(result)
                for result in cleaned_results["results"]
            ]

        return cleaned_results

    @staticmethod
    def format_content_file(results: Dict[str, List], format_type: str = 'clean') -> str:
        """
        Format extracted content into a single string with appropriate separations.

        Args:
            results: Dictionary of extraction results
            format_type: 'clean' for clean output, 'full' for detailed output

        Returns:
            Formatted content as a string
        """
        output_lines = []

        # Process text elements first
        if 'text' in results and results['text']:
            for element in results['text']:
                page_num = element.metadata.get('page_number', 'N/A')

                if format_type == 'full':
                    # Include detailed metadata
                    output_lines.append(f"\n{'=' * 80}")
                    output_lines.append(f"Content Type: text")
                    output_lines.append(f"Page Number: {page_num}")
                    output_lines.append(f"{'=' * 80}\n")
                else:
                    # Clean format - just add page number as small header if needed
                    if page_num != 'N/A':
                        output_lines.append(f"\n--- Page {page_num} ---\n")

                # Add the actual content
                output_lines.append(str(element.content))
                output_lines.append("\n")

        # Process table elements next
        if 'tables' in results and results['tables']:
            for element in results['tables']:
                page_num = element.metadata.get('page_number', 'N/A')
                table_idx = element.metadata.get('table_index', 1)

                if format_type == 'full':
                    output_lines.append(f"\n{'=' * 80}")
                    output_lines.append(f"Content Type: table")
                    output_lines.append(f"Page Number: {page_num}")
                    output_lines.append(f"Table Index: {table_idx}")
                    output_lines.append(f"{'=' * 80}\n")
                else:
                    # Clean format - add small table header
                    output_lines.append(f"\n--- Table {table_idx} (Page {page_num}) ---\n")

                # Add the actual content
                output_lines.append(str(element.content))
                output_lines.append("\n")

        # We only include image references in full format
        if format_type == 'full' and 'images' in results and results['images']:
            for element in results['images']:
                page_num = element.metadata.get('page_number', 'N/A')
                image_path = element.metadata.get('file_path', '')
                image_name = image_path.split('/')[-1] if '/' in image_path else image_path

                output_lines.append(f"\n{'=' * 80}")
                output_lines.append(f"Content Type: images")
                output_lines.append(f"Page Number: {page_num}")
                output_lines.append(f"{'=' * 80}\n")
                output_lines.append(f"Image: {image_name}")
                output_lines.append("\n")

        return "\n".join(output_lines)


# Create a singleton instance for easy importing
formatter = ContentFormatter()