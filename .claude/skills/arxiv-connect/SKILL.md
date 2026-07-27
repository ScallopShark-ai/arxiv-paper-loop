---
name: arxiv-connect
description: Connect to arXiv API to search papers, retrieve paper information, and download PDFs. Use this skill when you need to search for papers on arXiv, get paper metadata, or download paper PDFs.
---

## Purpose

Provide arXiv API connection capability for agents. Allow searching papers by date and categories, retrieving paper metadata (title, authors, abstract), and downloading PDFs.

## API Information

- Base URL: `http://export.arxiv.org/api/query`
- Format: XML (Atom feed)
- Rate Limit: 3 seconds between requests (recommended)
- No API Key required

## Dependencies

Required Python packages:
- `requests` - HTTP requests
- `feedparser` - Parse Atom/XML feed
- `arxiv` - Official arXiv SDK (optional, provides cleaner interface)

Install:
```bash
pip install requests feedparser arxiv
```

## Usage

### Method 1: Use the bundled script (Recommended)

```python
from scripts.arxiv_client import ArxivClient

client = ArxivClient()

# Search papers
papers = client.search(
    categories=["cs.LG", "cs.AI"],
    keywords=["reinforcement learning", "agent"],
    date="2025-07-23"
)

# Get paper info
for paper in papers:
    print(paper.title)
    print(paper.abstract)

# Download PDF
client.download(paper.arxiv_id, "papers/")
```

### Method 2: Use convenience functions

```python
from scripts.arxiv_client import search_papers, download_paper, get_paper_info

# Search papers
papers = search_papers(categories=["cs.LG", "cs.AI"], date="2025-07-23")

# Get specific paper info
info = get_paper_info("2307.12345")

# Download paper
download_paper("2307.12345", "papers/")
```

## Functions

| Function | Description |
|----------|-------------|
| `search_papers(categories, keywords, date, max_results)` | Search papers by criteria |
| `get_paper_info(arxiv_id)` | Get metadata for a specific paper |
| `download_paper(arxiv_id, output_dir)` | Download PDF to directory |

## Search Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `categories` | List[str] | arXiv categories (e.g., cs.LG, cs.AI) |
| `keywords` | List[str] | Search keywords (optional) |
| `date` | str | Date in YYYY-MM-DD format |
| `max_results` | int | Maximum number of results (default: 50) |

## Paper Object

Each paper returned contains:

| Field | Type | Description |
|-------|------|-------------|
| `arxiv_id` | str | arXiv identifier (e.g., 2307.12345) |
| `title` | str | Paper title |
| `authors` | List[str] | Author names |
| `abstract` | str | Paper abstract |
| `categories` | List[str] | arXiv categories |
| `published` | str | Publication date |
| `pdf_url` | str | Direct PDF download URL |

## Error Handling

| Error | Handling |
|-------|----------|
| Network Error | Retry up to 3 times with exponential backoff |
| Rate Limited | Wait 3 seconds before retry |
| Paper Not Found | Return None, log warning |
| Download Failed | Retry up to 3 times |

## Rate Limits

arXiv API recommendations:
- Wait at least 3 seconds between requests
- Batch requests when possible
- Use session for multiple requests

The script automatically:
- Adds 3 second delay between requests
- Implements retry logic with backoff
- Limits max results to prevent overloading