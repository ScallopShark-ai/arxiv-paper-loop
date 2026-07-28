"""
PDF Image Extractor
Extract figures and images from PDF files.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import fitz  # PyMuPDF

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_images(
    pdf_path: str,
    output_dir: str = "images/",
    min_width: int = 100,
    min_height: int = 100,
    min_area: int = 10000
) -> List[Dict]:
    """
    Extract images from a PDF file.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted images
        min_width: Minimum image width in pixels
        min_height: Minimum image height in pixels
        min_area: Minimum image area in pixels squared

    Returns:
        List of dicts with image metadata
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

    # Save metadata
    metadata_path = os.path.join(output_dir, f"{pdf_name}_images.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)

    logger.info(f"Extracted {len(extracted)} images from {pdf_path}")
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