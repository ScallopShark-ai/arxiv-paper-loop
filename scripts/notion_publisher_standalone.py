#!/usr/bin/env python3
"""
Notion Publisher Script
Directly write content to Notion pages with proper formatting.
"""

import os
import re
import sys
from typing import List, Dict, Any, Optional
from notion_client import Client


class NotionPublisher:
    """Publish content to Notion with proper block formatting."""

    def __init__(self, api_key: str = None, page_id: str = None, image_url_map: Dict = None):
        """Initialize with API credentials.

        Args:
            api_key: Notion API key
            page_id: Parent page ID
            image_url_map: Dict mapping local image paths to GitHub URLs
        """
        self.api_key = api_key or os.environ.get("NOTION_API_KEY")
        self.page_id = page_id or os.environ.get("NOTION_PAGE_ID")
        self.image_url_map = image_url_map or {}

        if not self.api_key:
            raise ValueError("NOTION_API_KEY not set")
        if not self.page_id:
            raise ValueError("NOTION_PAGE_ID not set")

        self.client = Client(auth=self.api_key)

    def create_page(self, title: str, parent_id: str = None) -> str:
        """Create a new page."""
        response = self.client.pages.create(
            parent={"page_id": parent_id or self.page_id},
            properties={
                "title": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            }
        )
        print(f"Created page: {title} ({response['id']})")
        return response["id"]

    def append_blocks(self, page_id: str, blocks: List[Dict], batch_size: int = 100):
        """Append blocks to a page with batching."""
        total = len(blocks)
        for i in range(0, total, batch_size):
            batch = blocks[i:i + batch_size]
            self.client.blocks.children.append(
                block_id=page_id,
                children=batch
            )
            print(f"  Uploaded batch {i // batch_size + 1} ({len(batch)} blocks)")
        print(f"Total: {total} blocks written")

    def parse_markdown(self, markdown: str) -> List[Dict]:
        """Parse markdown to Notion blocks."""
        blocks = []
        lines = markdown.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Skip empty lines
            if not line.strip():
                i += 1
                continue

            # Heading 1
            if line.startswith('# ') and not line.startswith('## '):
                blocks.append(self._heading(line[2:], 1))

            # Heading 2
            elif line.startswith('## ') and not line.startswith('### '):
                blocks.append(self._heading(line[3:], 2))

            # Heading 3
            elif line.startswith('### ') and not line.startswith('#### '):
                blocks.append(self._heading(line[4:], 3))

            # Heading 4
            elif line.startswith('#### '):
                blocks.append(self._heading(line[5:], 4))

            # Bullet list
            elif line.startswith('- '):
                blocks.append(self._bullet(line[2:]))

            # Numbered list
            elif re.match(r'^\d+\.\s', line):
                content = re.sub(r'^\d+\.\s', '', line)
                blocks.append(self._numbered(content))

            # Code block
            elif line.startswith('```'):
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                blocks.append(self._code('\n'.join(code_lines)))

            # Quote
            elif line.startswith('> '):
                blocks.append(self._quote(line[2:]))

            # Divider
            elif line.strip() == '---':
                blocks.append({"type": "divider", "divider": {}})

            # LaTeX block equation ($$...$$)
            elif line.strip().startswith('$$'):
                eq_lines = [line.strip()[2:]] if line.strip().startswith('$$') else []
                i += 1
                while i < len(lines) and not lines[i].strip().endswith('$$'):
                    eq_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    eq_lines.append(lines[i].rstrip('$'))
                blocks.append(self._equation('\n'.join(eq_lines)))

            # Callout (::: tip ...)
            elif line.strip().startswith(':::'):
                callout_type = line.strip()[3:].strip() or 'info'
                callout_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith(':::'):
                    callout_lines.append(lines[i])
                    i += 1
                blocks.append(self._callout('\n'.join(callout_lines), callout_type))

            # Image: ![alt](url) or ![alt](path)
            elif line.strip().startswith('!['):
                img_match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line.strip())
                if img_match:
                    alt_text = img_match.group(1)
                    img_url = img_match.group(2)
                    blocks.append(self._image(img_url, alt_text))
                else:
                    blocks.append(self._paragraph(line))

            # Paragraph (default)
            else:
                blocks.append(self._paragraph(line))

            i += 1

        return blocks

    def _split_text(self, text: str, max_len: int = 2000) -> List[str]:
        """Split text into chunks within Notion's limit."""
        if len(text) <= max_len:
            return [text]

        chunks = []
        while text:
            if len(text) <= max_len:
                chunks.append(text)
                break

            # Find a good break point
            break_point = max_len
            for j in range(max_len - 1, max_len // 2, -1):
                if text[j] in ' \n,.;':
                    break_point = j + 1
                    break

            chunks.append(text[:break_point])
            text = text[break_point:]

        return chunks

    def _parse_inline_equations(self, text: str) -> List[Dict]:
        """Parse text and convert inline LaTeX $...$ to equation objects."""
        import re
        result = []
        remaining = text

        # Pattern to match $...$ (non-greedy)
        pattern = r'\$([^$]+)\$'

        while remaining:
            match = re.search(pattern, remaining)
            if match:
                # Add text before the equation
                if match.start() > 0:
                    before = remaining[:match.start()]
                    result.append({"type": "text", "text": {"content": before}})

                # Add the equation
                eq_content = match.group(1)
                result.append({"type": "equation", "equation": {"expression": eq_content}})

                # Move past the match
                remaining = remaining[match.end():]
            else:
                # No more equations, add remaining text
                if remaining:
                    result.append({"type": "text", "text": {"content": remaining}})
                break

        return result

    def _rich_text(self, content: str) -> List[Dict]:
        """Create rich_text array with proper splitting and inline equation support."""
        # First parse inline equations
        parsed = self._parse_inline_equations(content)

        # Now handle splitting for long text segments
        result = []
        for item in parsed:
            if item["type"] == "text":
                text = item["text"]["content"]
                if len(text) > 1900:
                    chunks = self._split_text(text)
                    for chunk in chunks:
                        result.append({"type": "text", "text": {"content": chunk}})
                else:
                    result.append(item)
            else:
                # Equations don't need splitting
                result.append(item)

        return result

    def _heading(self, content: str, level: int) -> Dict:
        """Create heading block."""
        return {
            "type": f"heading_{level}",
            f"heading_{level}": {
                "rich_text": self._rich_text(content.strip())
            }
        }

    def _paragraph(self, content: str) -> Dict:
        """Create paragraph block."""
        return {
            "type": "paragraph",
            "paragraph": {
                "rich_text": self._rich_text(content.strip())
            }
        }

    def _bullet(self, content: str) -> Dict:
        """Create bullet list item."""
        return {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": self._rich_text(content.strip())
            }
        }

    def _numbered(self, content: str) -> Dict:
        """Create numbered list item."""
        return {
            "type": "numbered_list_item",
            "numbered_list_item": {
                "rich_text": self._rich_text(content.strip())
            }
        }

    def _code(self, content: str) -> Dict:
        """Create code block."""
        return {
            "type": "code",
            "code": {
                "rich_text": self._rich_text(content),
                "language": "plain text"
            }
        }

    def _quote(self, content: str) -> Dict:
        """Create quote block."""
        return {
            "type": "quote",
            "quote": {
                "rich_text": self._rich_text(content.strip())
            }
        }

    def _equation(self, expression: str) -> Dict:
        """Create equation block (LaTeX)."""
        return {
            "type": "equation",
            "equation": {
                "expression": expression.strip()
            }
        }

    def _callout(self, content: str, callout_type: str = 'info') -> Dict:
        """Create callout block."""
        emoji_map = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌',
            'success': '✅',
            'tip': '💡',
        }
        return {
            "type": "callout",
            "callout": {
                "rich_text": self._rich_text(content.strip()),
                "icon": {"type": "emoji", "emoji": emoji_map.get(callout_type, '📌')}
            }
        }

    def _image(self, url: str, alt_text: str = "") -> Dict:
        """Create image block.

        Args:
            url: Image URL (external) or local path
            alt_text: Alternative text for the image

        Returns:
            Notion image block dict
        """
        # Check if it's an external URL
        if url.startswith('http://') or url.startswith('https://'):
            return {
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {
                        "url": url
                    }
                }
            }

        # Check if we have a mapping for this local path
        if url in self.image_url_map:
            mapped_url = self.image_url_map[url]
            print(f"Mapped local image '{url}' to '{mapped_url}'")
            return {
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {
                        "url": mapped_url
                    }
                }
            }

        # Try to match by filename
        filename = os.path.basename(url)
        if filename in self.image_url_map:
            mapped_url = self.image_url_map[filename]
            print(f"Mapped local image '{filename}' to '{mapped_url}'")
            return {
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {
                        "url": mapped_url
                    }
                }
            }

        # No mapping available - create placeholder
        print(f"Warning: No URL mapping for local image '{url}'")
        return {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": f"[图片: {alt_text or url}]"}}]
            }
        }

    def publish_file(self, file_path: str, page_title: str = None, parent_id: str = None) -> str:
        """Read a markdown file and publish to Notion."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Create page
        title = page_title or os.path.basename(file_path).replace('.md', '')
        page_id = self.create_page(title, parent_id)

        # Parse and upload
        blocks = self.parse_markdown(content)
        self.append_blocks(page_id, blocks)

        return page_id

    def publish_string(self, content: str, page_title: str, parent_id: str = None) -> str:
        """Publish a string content to Notion."""
        page_id = self.create_page(page_title, parent_id)
        blocks = self.parse_markdown(content)
        self.append_blocks(page_id, blocks)
        return page_id


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Publish content to Notion")
    parser.add_argument("file", help="Markdown file to publish")
    parser.add_argument("--title", help="Page title (default: filename)")
    parser.add_argument("--parent", help="Parent page ID")

    args = parser.parse_args()

    publisher = NotionPublisher()
    page_id = publisher.publish_file(args.file, args.title, args.parent)
    print(f"\nPublished to: https://notion.so/{page_id.replace('-', '')}")


if __name__ == "__main__":
    main()