---
name: multimodal-analysis
description: Analyze content with images using Claude multimodal API. Use this skill when you need to analyze images, charts, diagrams, or combine text and visual content for analysis.
---

## Purpose

Provide multimodal analysis capability for agents. Send images and text together to Claude API for comprehensive analysis.

## Dependencies

Required Python packages:
- `anthropic` - Claude API client
- `base64` (built-in) - Image encoding

Install:
```bash
pip install anthropic
```

## Usage

### Method 1: Use the bundled script (Recommended)

```python
from scripts.multimodal_client import MultimodalAnalyzer

analyzer = MultimodalAnalyzer()

# Analyze text only
result = analyzer.analyze_text(system_prompt, text_content, model)

# Analyze text with images
result = analyzer.analyze_with_images(
    system_prompt=system_prompt,
    text_content=text_content,
    images=[
        {"path": "images/fig1.png", "filename": "fig1.png", "page": 1},
        {"path": "images/table1.png", "filename": "table1.png", "page": 2, "type": "table"}
    ],
    model="claude-opus-5"
)
```

### Method 2: Use convenience functions

```python
from scripts.multimodal_client import analyze, analyze_with_images

# Simple text analysis
result = analyze(system_prompt, text_content)

# Multimodal analysis with images
result = analyze_with_images(
    system_prompt,
    text_content,
    image_paths=["fig1.png", "table1.png"]
)
```

## Functions

| Function | Description |
|----------|-------------|
| `analyze_text(system_prompt, text, model, max_retries)` | Analyze text only |
| `analyze_with_images(system_prompt, text, images, model, max_retries)` | Analyze text + images |
| `encode_image(path)` | Encode image to base64 |
| `get_media_type(path)` | Get MIME type for image |

## Image Format

Images should be provided as a list of dicts:

```python
images = [
    {
        "path": "/path/to/image.png",  # Required: absolute path
        "filename": "fig1.png",         # Required: display name
        "page": 1,                      # Optional: source page
        "type": "image"                 # Optional: "image" or "table"
    }
]
```

## Output

Returns analysis text in the same language as the system prompt.

## API Configuration

Uses environment variables:
- `ANTHROPIC_API_KEY` - API key (required)
- `ANTHROPIC_BASE_URL` - Base URL (optional, for proxies)

## Performance

| Content Size | Typical Time |
|--------------|--------------|
| Text only (10k tokens) | ~30 seconds |
| Text + 5 images | ~60 seconds |
| Text + 20 images | ~3 minutes |

Note: Large images are processed at native resolution.

## Limitations

- Maximum 20 images per request (to avoid token limits)
- Supports PNG, JPEG, GIF, WebP formats
- Images are not stored or cached by the API
- Timeout set to 10 minutes for large content

## Error Handling

| Error | Handling |
|-------|----------|
| API Timeout | Retry up to 2 times with delay |
| Rate Limited | Exponential backoff |
| Invalid Image | Skip and log warning |
| Token Limit | Reduce image count |