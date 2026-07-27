---
name: notion-connector
description: Connect to Notion via API and write/read content to/from a specific page reliably. Use this skill when you need to publish content to Notion, read from a Notion page, or integrate Notion into a workflow. Handles authentication, rate limiting, and error recovery automatically.
---

## Purpose

Provide stable Notion connection capability for agents. Allow reading from and writing to a specific page reliably. Restrict operations to the designated page only.

## Authentication

### Setup (One-time)

How to obtain credentials:
1. Go to https://www.notion.so/my-integrations
2. Create a new integration
3. Copy the Internal Integration Token
4. In Notion, open the target page → Share → Invite the integration
5. Copy the Page ID from the page URL (32-character string after the last `/`)

### Required Environment Variables

- `NOTION_API_KEY`: Notion Integration Token (stored in GitHub Secrets)
- `NOTION_PAGE_ID`: Target Page ID (stored in GitHub Secrets)

These are stored in GitHub Secrets and automatically injected at runtime.

## Dependencies

Required Python packages:
- `notion-client` - Official Notion SDK for Python

Install:
```bash
pip install notion-client
```

## Usage

### Method 1: Use the bundled script (Recommended)

```python
from scripts.notion_client import write_page, read_page, clear_page

# Write content (Markdown format)
write_page("# Title\nContent here...")

# Read page content
blocks = read_page()

# Clear page
clear_page()
```

### Method 2: Use the class directly

```python
from scripts.notion_client import NotionClient

client = NotionClient()

# Write content
client.write_page("# Paper Analysis\n\nSummary of today's papers...")

# Read content
blocks = client.read_page()

# Clear page
client.clear_page()
```

## Features

| Function | Description |
|----------|-------------|
| `write_page(content)` | Append Markdown content to the page |
| `read_page()` | Read all blocks from the page |
| `clear_page()` | Remove all content from the page |

## Markdown Support

The script converts Markdown to Notion blocks:

| Markdown | Notion Block |
|----------|--------------|
| `# Title` | Heading 1 |
| `## Title` | Heading 2 |
| `### Title` | Heading 3 |
| `- item` | Bullet list |
| `1. item` | Numbered list |
| `> quote` | Quote |
| ` ```code``` ` | Code block |
| `---` | Divider |
| Plain text | Paragraph |

## Error Handling

### Retry Strategy
- Maximum retries: 3
- Retry delay: 1 second (exponential backoff)
- Retry on: Network errors, rate limit errors (HTTP 429)

### Error Types

| Error | Handling |
|-------|----------|
| Invalid API Key | Log error and stop |
| Page Not Found | Log error and stop |
| Rate Limit (429) | Wait and retry |
| Network Error | Retry up to 3 times |
| Permission Denied | Log error and stop |

## Rate Limits

Notion API limits:
- 3 requests per second
- No burst allowance

The script automatically:
- Adds 350ms delay between requests
- Handles rate limit responses (HTTP 429)
- Implements exponential backoff