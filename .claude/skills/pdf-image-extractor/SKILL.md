---
name: pdf-image-extractor
description: Extract figures and images from PDF files for analysis. Use this skill when you need to extract charts, diagrams, or visualizations from academic papers.
---

# PDF Image Extractor

Extract figures, charts, and images from PDF files for visual analysis.

## When to Use

- Extract charts, graphs, and plots from academic papers
- Get diagrams and flowcharts for methodology understanding
- Capture tables rendered as images
- Preserve visual results and visualizations

## Usage

### Python API

```python
from pdf_image_extractor import extract_images

# Extract all images from a PDF
images = extract_images("paper.pdf", output_dir="images/")

# Returns list of extracted image paths
# images/figure_1.png
# images/figure_2.png
# ...
```

### Command Line

```bash
python scripts/extract_images.py paper.pdf -o images/
```

## Output

- PNG format images
- Named by page and index: `page_N_figure_M.png`
- Metadata JSON with image positions and sizes

## Limitations

- Some PDFs have embedded images that cannot be extracted
- Vector graphics may be rasterized
- Image quality depends on source PDF