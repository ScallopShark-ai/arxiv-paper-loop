"""
PDF Image Extractor
Extract figures, images, and tables from PDF files.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import fitz  # PyMuPDF

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def detect_table_regions(page, min_rows: int = 3, min_cols: int = 2) -> List[Tuple[float, float, float, float]]:
    """
    Detect potential table regions on a page based on text structure.

    Args:
        page: PyMuPDF page object
        min_rows: Minimum number of rows to consider as table
        min_cols: Minimum number of columns to consider as table

    Returns:
        List of rectangles (x0, y0, x1, y1) representing table regions
    """
    tables = []

    # Get text blocks with position info
    blocks = page.get_text("dict")["blocks"]

    # Filter to text blocks only
    text_blocks = [b for b in blocks if b.get("type") == 0]

    if len(text_blocks) < min_rows:
        return tables

    # Group blocks by approximate y-position (rows)
    rows = {}
    y_tolerance = 5  # pixels

    for block in text_blocks:
        y = block["bbox"][1]
        # Find existing row or create new one
        found_row = None
        for row_y in rows:
            if abs(row_y - y) < y_tolerance:
                found_row = row_y
                break
        if found_row:
            rows[found_row].append(block)
        else:
            rows[y] = [block]

    # Filter rows that have multiple columns
    potential_table_rows = []
    for row_y, row_blocks in sorted(rows.items()):
        if len(row_blocks) >= min_cols:
            potential_table_rows.append((row_y, row_blocks))

    # Group consecutive rows into tables
    if len(potential_table_rows) >= min_rows:
        # Find bounding box for all table rows
        x0, y0, x1, y1 = float('inf'), float('inf'), float('-inf'), float('-inf')

        for row_y, row_blocks in potential_table_rows:
            for block in row_blocks:
                bbox = block["bbox"]
                x0 = min(x0, bbox[0])
                y0 = min(y0, bbox[1])
                x1 = max(x1, bbox[2])
                y1 = max(y1, bbox[3])

        # Add some padding
        padding = 10
        tables.append((x0 - padding, y0 - padding, x1 + padding, y1 + padding))

    return tables


def extract_tables_as_images(
    pdf_path: str,
    output_dir: str = "tables/",
    min_rows: int = 3,
    min_cols: int = 2,
    zoom: int = 2
) -> List[Dict]:
    """
    Extract tables from PDF pages as images.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted table images
        min_rows: Minimum rows to detect as table
        min_cols: Minimum columns to detect as table
        zoom: Zoom factor for rendering (higher = better quality)

    Returns:
        List of dicts with table metadata
    """
    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    pdf_name = Path(pdf_path).stem

    extracted = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Detect table regions
        table_regions = detect_table_regions(page, min_rows, min_cols)

        for table_idx, rect in enumerate(table_regions):
            try:
                # Create a clip rectangle
                clip = fitz.Rect(rect)

                # Render the region as image
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, clip=clip)

                # Save image
                image_name = f"{pdf_name}_page{page_num + 1}_table{table_idx + 1}.png"
                image_path = os.path.join(output_dir, image_name)
                pix.save(image_path)

                metadata = {
                    "filename": image_name,
                    "page": page_num + 1,
                    "index": table_idx + 1,
                    "type": "table",
                    "width": pix.width,
                    "height": pix.height,
                    "position": {
                        "x": rect[0],
                        "y": rect[1],
                        "width": rect[2] - rect[0],
                        "height": rect[3] - rect[1]
                    }
                }

                extracted.append(metadata)
                logger.info(f"Extracted table: {image_name} ({pix.width}x{pix.height})")

            except Exception as e:
                logger.warning(f"Failed to extract table {table_idx} on page {page_num}: {e}")
                continue

    doc.close()

    logger.info(f"Extracted {len(extracted)} tables from {pdf_path}")
    return extracted


def extract_images(
    pdf_path: str,
    output_dir: str = "images/",
    min_width: int = 100,
    min_height: int = 100,
    min_area: int = 10000,
    extract_tables: bool = True
) -> List[Dict]:
    """
    Extract images and tables from a PDF file.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted images
        min_width: Minimum image width in pixels
        min_height: Minimum image height in pixels
        min_area: Minimum image area in pixels squared
        extract_tables: Whether to also extract tables as images

    Returns:
        List of dicts with image/table metadata
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Open PDF
    doc = fitz.open(pdf_path)
    pdf_name = Path(pdf_path).stem

    extracted = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        logger.info(f"Page {page_num + 1}: found {len(image_list)} images")

        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]

            try:
                # Extract image
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                # Get image dimensions
                img_pixmap = fitz.Pixmap(image_bytes)
                width = img_pixmap.width
                height = img_pixmap.height

                # Filter small images (likely icons or decorations)
                if width < min_width or height < min_height:
                    continue
                if width * height < min_area:
                    continue

                # Save image
                image_name = f"{pdf_name}_page{page_num + 1}_fig{img_idx + 1}.{image_ext}"
                image_path = os.path.join(output_dir, image_name)

                with open(image_path, "wb") as f:
                    f.write(image_bytes)

                # Get image position on page
                rect = None
                for block in page.get_text("dict")["blocks"]:
                    if block["type"] == 1:  # Image block
                        if block.get("image") == xref:
                            rect = fitz.Rect(block["bbox"])
                            break

                metadata = {
                    "filename": image_name,
                    "page": page_num + 1,
                    "index": img_idx + 1,
                    "width": width,
                    "height": height,
                    "format": image_ext,
                    "position": {
                        "x": rect.x0 if rect else None,
                        "y": rect.y0 if rect else None,
                        "width": rect.width if rect else None,
                        "height": rect.height if rect else None
                    } if rect else None
                }

                extracted.append(metadata)
                logger.info(f"Extracted: {image_name} ({width}x{height})")

            except Exception as e:
                logger.warning(f"Failed to extract image {img_idx} on page {page_num}: {e}")
                continue

    # Extract tables as images
    if extract_tables:
        logger.info("Extracting tables as images...")
        tables = extract_tables_as_images(
            pdf_path,
            output_dir,
            min_rows=3,
            min_cols=2,
            zoom=2
        )
        extracted.extend(tables)

    # Save metadata
    metadata_path = os.path.join(output_dir, f"{pdf_name}_images.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)

    logger.info(f"Extracted {len(extracted)} items (images + tables) from {pdf_path}")
    return extracted


def extract_images_from_directory(
    input_dir: str,
    output_dir: str = "images/"
) -> Dict[str, List[Dict]]:
    """
    Extract images from all PDFs in a directory.

    Args:
        input_dir: Directory containing PDF files
        output_dir: Base directory for extracted images

    Returns:
        Dict mapping PDF names to their extracted images
    """
    results = {}

    for pdf_file in Path(input_dir).glob("*.pdf"):
        pdf_name = pdf_file.stem
        pdf_output_dir = os.path.join(output_dir, pdf_name)

        images = extract_images(str(pdf_file), pdf_output_dir)
        results[pdf_name] = images

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract images from PDF files")
    parser.add_argument("pdf_path", help="Path to PDF file or directory")
    parser.add_argument("-o", "--output", default="images/", help="Output directory")
    parser.add_argument("--min-width", type=int, default=100, help="Minimum image width")
    parser.add_argument("--min-height", type=int, default=100, help="Minimum image height")

    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)

    if pdf_path.is_file():
        extract_images(str(pdf_path), args.output, args.min_width, args.min_height)
    elif pdf_path.is_dir():
        extract_images_from_directory(str(pdf_path), args.output)
    else:
        print(f"Error: {args.pdf_path} not found")