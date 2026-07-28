"""
Notion Client for arxiv-paper-loop
Provides stable connection to Notion API with error handling and rate limiting.
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional
from notion_client import Client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NotionClient:
    """Notion client with retry and rate limiting support."""

    def __init__(self):
        """Initialize Notion client with environment variables."""
        self.api_key = os.environ.get("NOTION_API_KEY")
        self.page_id = os.environ.get("NOTION_PAGE_ID")

        if not self.api_key:
            raise ValueError("NOTION_API_KEY environment variable not set")
        if not self.page_id:
            raise ValueError("NOTION_PAGE_ID environment variable not set")

        self.client = Client(auth=self.api_key)
        self._request_count = 0
        self._last_request_time = 0

    def _rate_limit(self):
        """Ensure we don't exceed Notion's rate limit (3 requests/second)."""
        min_interval = 0.35  # 350ms between requests
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()
        self._request_count += 1

    def _retry(self, func, *args, max_retries=3, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_error = None
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                error_str = str(e)

                # Don't retry on auth errors
                if "Unauthorized" in error_str or "invalid" in error_str.lower():
                    logger.error(f"Authentication error: {e}")
                    raise

                # Rate limit - wait and retry
                if "429" in error_str or "rate limit" in error_str.lower():
                    wait_time = 1 * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                # Network error - retry
                if attempt < max_retries - 1:
                    logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                    time.sleep(1 * (2 ** attempt))
                    continue

        logger.error(f"All retries failed: {last_error}")
        raise last_error

    def read_page(self) -> List[Dict]:
        """
        Read all content blocks from the designated page.

        Returns:
            List of content blocks
        """
        logger.info(f"Reading page: {self.page_id}")

        response = self._retry(
            self.client.blocks.children.list,
            block_id=self.page_id
        )

        blocks = response.get("results", [])
        logger.info(f"Read {len(blocks)} blocks")
        return blocks

    def write_page(self, content: str) -> bool:
        """
        Write content to the page (appends to existing content).

        Args:
            content: Markdown content to write

        Returns:
            True if successful
        """
        logger.info(f"Writing to page: {self.page_id}")

        blocks = self._markdown_to_blocks(content)

        self._retry(
            self.client.blocks.children.append,
            block_id=self.page_id,
            children=blocks
        )

        logger.info(f"Wrote {len(blocks)} blocks")
        return True

    def clear_page(self) -> bool:
        """
        Remove all content blocks from the page.

        Returns:
            True if successful
        """
        logger.info(f"Clearing page: {self.page_id}")

        blocks = self.read_page()

        for block in blocks:
            block_id = block.get("id")
            self._retry(
                self.client.blocks.delete,
                block_id=block_id
            )

        logger.info(f"Cleared {len(blocks)} blocks")
        return True

    def create_child_page(self, title: str) -> str:
        """
        Create a new child page under the designated parent page.

        Args:
            title: Title for the new page

        Returns:
            ID of the newly created page
        """
        logger.info(f"Creating child page: {title}")

        # Create the page
        response = self._retry(
            self.client.pages.create,
            parent={"page_id": self.page_id},
            properties={
                "title": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            }
        )

        new_page_id = response.get("id")
        logger.info(f"Created page: {new_page_id}")
        return new_page_id

    def write_to_page(self, page_id: str, content: str) -> bool:
        """
        Write content to a specific page.

        Args:
            page_id: ID of the page to write to
            content: Markdown content to write

        Returns:
            True if successful
        """
        logger.info(f"Writing to page: {page_id}")

        blocks = self._markdown_to_blocks(content)

        # Split into batches of 100 (Notion API limit)
        batch_size = 100
        total_blocks = len(blocks)

        for i in range(0, total_blocks, batch_size):
            batch = blocks[i:i + batch_size]
            logger.info(f"Uploading batch {i // batch_size + 1} ({len(batch)} blocks)")
            self._retry(
                self.client.blocks.children.append,
                block_id=page_id,
                children=batch
            )

        logger.info(f"Wrote {total_blocks} blocks in {(total_blocks + batch_size - 1) // batch_size} batches")
        return True

    def _markdown_to_blocks(self, markdown: str) -> List[Dict]:
        """
        Convert Markdown text to Notion block format.

        Args:
            markdown: Markdown text

        Returns:
            List of Notion block objects
        """
        blocks = []
        lines = markdown.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # Heading 1
            if line.startswith('# '):
                blocks.append({
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                    }
                })

            # Heading 2
            elif line.startswith('## '):
                blocks.append({
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": line[3:]}}]
                    }
                })

            # Heading 3
            elif line.startswith('### '):
                blocks.append({
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": line[4:]}}]
                    }
                })

            # Bullet list
            elif line.startswith('- '):
                blocks.append({
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                    }
                })

            # Numbered list
            elif line.startswith(('1. ', '2. ', '3. ', '4. ', '5. ', '6. ', '7. ', '8. ', '9. ')):
                blocks.append({
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": line[3:]}}]
                    }
                })

            # Code block
            elif line.startswith('```'):
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                blocks.append({
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": '\n'.join(code_lines)}}],
                        "language": "plain text"
                    }
                })

            # Quote
            elif line.startswith('> '):
                blocks.append({
                    "type": "quote",
                    "quote": {
                        "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                    }
                })

            # Divider
            elif line == '---':
                blocks.append({"type": "divider", "divider": {}})

            # Paragraph (default)
            else:
                blocks.append({
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": line}}]
                    }
                })

            i += 1

        return blocks


# Convenience functions for direct import
_client = None

def get_client() -> NotionClient:
    """Get or create Notion client instance."""
    global _client
    if _client is None:
        _client = NotionClient()
    return _client

def read_page() -> List[Dict]:
    """Read all content from the designated page."""
    return get_client().read_page()

def write_page(content: str) -> bool:
    """Write content to the designated page."""
    return get_client().write_page(content)

def clear_page() -> bool:
    """Clear all content from the designated page."""
    return get_client().clear_page()

def create_child_page(title: str) -> str:
    """
    Create a new child page under the designated parent page.

    Args:
        title: Title for the new page

    Returns:
        ID of the newly created page
    """
    return get_client().create_child_page(title)

def write_to_page(page_id: str, content: str) -> bool:
    """
    Write content to a specific page.

    Args:
        page_id: ID of the page to write to
        content: Markdown content to write

    Returns:
        True if successful
    """
    return get_client().write_to_page(page_id, content)