---
name: pdf-reader
description: Read PDF files and extract text, tables, figures, and mathematical formulas using AI. Use this skill when you need to read academic papers, extract equations, or analyze PDF content with charts and formulas.
---

## Purpose

Provide PDF reading capability for agents. Extract structured content from academic papers including text, tables, figures, and mathematical formulas in LaTeX format.

## Dependencies

Required Python packages:
- `marker-pdf` - AI-powered PDF to Markdown converter
- `pymupdf` - PDF processing backend

Install:
```bash
pip install marker-pdf pymupdf
```

Note: marker uses local AI models (PyTorch). First run will download models (~1GB).

## Usage

### Method 1: Use the bundled script (Recommended)

```python
from scripts.pdf_reader import PDFReader

reader = PDFReader()

# Read entire PDF
content = reader.read("papers/2307.12345.pdf")

# Read specific pages
content = reader.read_pages("papers/2307.12345.pdf", start=1, end=10)

# Extract figures
figures = reader.extract_figures("papers/2307.12345.pdf")

# Extract equations
equations = reader.extract_equations("papers/2307.12345.pdf")
```

### Method 2: Use convenience functions

```python
from scripts.pdf_reader import read_pdf, read_pages, extract_figures

# Read PDF
content = read_pdf("papers/2307.12345.pdf")

# Read specific pages
content = read_pages("papers/2307.12345.pdf", 1, 10)

# Extract figures
figures = extract_figures("papers/2307.12345.pdf")
```

## Functions

| Function | Description |
|----------|-------------|
| `read_pdf(path)` | Read entire PDF as Markdown |
| `read_pages(path, start, end)` | Read specific page range |
| `extract_figures(path)` | Extract figures with descriptions |
| `extract_equations(path)` | Extract LaTeX equations |
| `extract_tables(path)` | Extract tables as Markdown |

## Output Format

### Text Content
Returns Markdown-formatted text:
```markdown
# Section Title

Paragraph content...

## Subsection

More content with **bold** and *italic*.

### Equation
$$E = mc^2$$

### Table
| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |
```

### Figures
Returns list of figure objects:
```python
[
    {
        "page": 3,
        "type": "figure",
        "caption": "Figure 1: Architecture diagram",
        "description": "Shows the neural network architecture..."
    }
]
```

### Equations
Returns list of equations:
```python
[
    {
        "page": 5,
        "latex": "\\frac{\\partial L}{\\partial w} = \\nabla_w L",
        "number": "Equation 1"
    }
]
```

## Processing Details

### marker Pipeline
1. Parse PDF structure (pages, blocks)
2. Detect layout (text, titles, figures, tables)
3. OCR for scanned documents
4. Convert equations to LaTeX
5. Output as Markdown

### Supported Content
- ✅ Text (paragraphs, headings)
- ✅ Mathematical equations (LaTeX)
- ✅ Tables (Markdown format)
- ✅ Figures (description + location)
- ️ Code blocks
- ✅ References/bibliography

## Error Handling

| Error | Handling |
|-------|----------|
| File Not Found | Return None, log error |
| Corrupted PDF | Attempt recovery, log warning |
| Model Not Downloaded | Auto-download on first run |
| Memory Error | Process in chunks |

## Performance

| PDF Size | Processing Time |
|----------|----------------|
| 5 pages | ~30 seconds |
| 20 pages | ~2 minutes |
| 50 pages | ~5 minutes |

Note: First run is slower due to model loading.

## Limitations

- Handwritten text may not be recognized
- Complex figures need manual interpretation
- Very large PDFs may need chunking
- Non-English text may have lower accuracy