---
name: pdf-image-extractor
description: Extract figures, images, and tables from PDF files for analysis. Use this skill when you need to extract charts, diagrams, visualizations, or tables from academic papers.
---

# PDF Image Extractor

Extract figures, charts, images, and tables from PDF files for visual analysis.

## When to Use

- Extract charts, graphs, and plots from academic papers
- Get diagrams and flowcharts for methodology understanding
- Capture tables rendered as images
- Preserve visual results and visualizations

## Usage

### Python API

```python
from pdf_image_extractor import extract_images

# Extract all images and tables from a PDF
images = extract_images("paper.pdf", output_dir="images/")

# Returns list of extracted image/table paths with metadata
# images/paper_page1_fig1.png (type: image)
# images/paper_page2_table1.png (type: table)
# ...
```

### Command Line

```bash
python scripts/extract_images.py paper.pdf -o images/
```

## Output

- PNG format images
- Named by type: `page_N_figure_M.png` or `page_N_table_M.png`
- Metadata JSON with image positions, sizes, and types

## Features

- **Embedded images**: Extract images embedded in PDF
- **Tables as images**: Detect and render tables as PNG images
- **Size filtering**: Skip small icons and decorations
- **Position metadata**: Record location on page

## Limitations

- Some PDFs have embedded images that cannot be extracted
- Vector graphics may be rasterized
- Image quality depends on source PDF
- Table detection uses heuristics (may miss some tables)