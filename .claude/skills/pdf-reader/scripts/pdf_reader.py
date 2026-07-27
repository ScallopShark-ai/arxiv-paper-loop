"""
PDF Reader for arxiv-paper-loop
Extracts text, tables, figures, and equations from PDF files using AI.
"""

import os
import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Figure:
    """Represents a figure in the PDF."""
    page: int
    figure_type: str
    caption: str
    description: str = ""


@dataclass
class Equation:
    """Represents an equation in the PDF."""
    page: int
    latex: str
    number: Optional[str] = None


@dataclass
class Table:
    """Represents a table in the PDF."""
    page: int
    markdown: str
    caption: str = ""


class PDFReader:
    """PDF reader with AI-powered content extraction."""

    def __init__(self):
        """Initialize PDF reader."""
        self._marker = None

    def _get_marker(self):
        """Lazy load marker to avoid heavy imports."""
        if self._marker is None:
            try:
                from marker.converters.pdf import PdfConverter
                from marker.models import create_model_dict
                from marker.output import text_from_rendered
                self._marker_converter_class = PdfConverter
                self._create_model_dict = create_model_dict
                self._text_from_rendered = text_from_rendered
                logger.info("Marker PDF loaded successfully")
            except ImportError:
                logger.warning("marker-pdf not installed. Falling back to pymupdf.")
                self._marker = "pymupdf"
        return self._marker

    def read(self, pdf_path: str) -> str:
        """
        Read entire PDF and return Markdown content.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Markdown-formatted content
        """
        if not os.path.exists(pdf_path):
            logger.error(f"PDF not found: {pdf_path}")
            return ""

        logger.info(f"Reading PDF: {pdf_path}")

        # Try marker first
        content = self._read_with_marker(pdf_path)

        if not content:
            # Fallback to pymupdf
            content = self._read_with_pymupdf(pdf_path)

        return content

    def read_pages(self, pdf_path: str, start: int, end: int) -> str:
        """
        Read specific page range from PDF.

        Args:
            pdf_path: Path to PDF file
            start: Start page (1-indexed)
            end: End page (inclusive)

        Returns:
            Markdown-formatted content for the page range
        """
        import fitz  # pymupdf

        if not os.path.exists(pdf_path):
            logger.error(f"PDF not found: {pdf_path}")
            return ""

        logger.info(f"Reading pages {start}-{end} from {pdf_path}")

        doc = fitz.open(pdf_path)
        content_parts = []

        for page_num in range(start - 1, min(end, len(doc))):
            page = doc[page_num]
            text = page.get_text()
            content_parts.append(f"## Page {page_num + 1}\n\n{text}")

        return "\n\n".join(content_parts)

    def extract_figures(self, pdf_path: str) -> List[Figure]:
        """
        Extract figures from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of Figure objects
        """
        import fitz

        if not os.path.exists(pdf_path):
            return []

        logger.info(f"Extracting figures from {pdf_path}")

        doc = fitz.open(pdf_path)
        figures = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()

            # Find figure captions using regex
            figure_pattern = r"Figure\s*(\d+)[:.]?\s*(.+?)(?=\n\n|\nFigure|\Z)"
            matches = re.findall(figure_pattern, text, re.DOTALL | re.IGNORECASE)

            for match in matches:
                figure = Figure(
                    page=page_num + 1,
                    figure_type="figure",
                    caption=f"Figure {match[0]}: {match[1].strip()}"
                )
                figures.append(figure)

        return figures

    def extract_equations(self, pdf_path: str) -> List[Equation]:
        """
        Extract equations from PDF (requires marker).

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of Equation objects
        """
        content = self.read(pdf_path)
        equations = []

        # Find LaTeX equations in the content
        # Inline: $...$
        inline_pattern = r"\$([^$]+)\$"
        # Block: $$...$$
        block_pattern = r"\$\$([^$]+)\$\$"

        page_num = 1  # Approximate

        for match in re.finditer(block_pattern, content, re.DOTALL):
            eq = Equation(
                page=page_num,
                latex=match.group(1).strip()
            )
            equations.append(eq)

        return equations

    def extract_tables(self, pdf_path: str) -> List[Table]:
        """
        Extract tables from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of Table objects
        """
        import pdfplumber

        if not os.path.exists(pdf_path):
            return []

        logger.info(f"Extracting tables from {pdf_path}")

        tables = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()

                for table_data in page_tables:
                    # Convert to Markdown
                    if table_data:
                        markdown = self._table_to_markdown(table_data)
                        table = Table(
                            page=page_num + 1,
                            markdown=markdown
                        )
                        tables.append(table)

        return tables

    def _read_with_marker(self, pdf_path: str) -> str:
        """Read PDF using marker (AI-powered)."""
        try:
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict
            from marker.output import text_from_rendered

            logger.info("Using marker for PDF conversion...")

            # Create model dict (downloads models on first run)
            model_dict = create_model_dict()

            # Convert PDF
            converter = PdfConverter(model_dict)
            rendered = converter(pdf_path)

            # Extract text
            text, _, _ = text_from_rendered(rendered)

            return text

        except ImportError:
            return ""
        except Exception as e:
            logger.error(f"Marker error: {e}")
            return ""

    def _read_with_pymupdf(self, pdf_path: str) -> str:
        """Read PDF using pymupdf (fallback)."""
        import fitz

        logger.info("Using pymupdf for PDF extraction...")

        doc = fitz.open(pdf_path)
        content_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()

            # Add page header
            content_parts.append(f"## Page {page_num + 1}\n\n{text}")

        return "\n\n---\n\n".join(content_parts)

    def _table_to_markdown(self, table_data: List[List[str]]) -> str:
        """Convert table data to Markdown format."""
        if not table_data:
            return ""

        lines = []

        # Header
        header = table_data[0]
        lines.append("| " + " | ".join(str(cell) if cell else "" for cell in header) + " |")

        # Separator
        lines.append("| " + " | ".join("---" for _ in header) + " |")

        # Rows
        for row in table_data[1:]:
            lines.append("| " + " | ".join(str(cell) if cell else "" for cell in row) + " |")

        return "\n".join(lines)


# Convenience functions
_reader = None


def get_reader() -> PDFReader:
    """Get or create PDF reader instance."""
    global _reader
    if _reader is None:
        _reader = PDFReader()
    return _reader


def read_pdf(pdf_path: str) -> str:
    """Read entire PDF as Markdown."""
    return get_reader().read(pdf_path)


def read_pages(pdf_path: str, start: int, end: int) -> str:
    """Read specific page range from PDF."""
    return get_reader().read_pages(pdf_path, start, end)


def extract_figures(pdf_path: str) -> List[Figure]:
    """Extract figures from PDF."""
    return get_reader().extract_figures(pdf_path)


def extract_equations(pdf_path: str) -> List[Equation]:
    """Extract equations from PDF."""
    return get_reader().extract_equations(pdf_path)


def extract_tables(pdf_path: str) -> List[Table]:
    """Extract tables from PDF."""
    return get_reader().extract_tables(pdf_path)