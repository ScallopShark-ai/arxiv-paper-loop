"""
Multimodal Analysis Client
Analyze content with images using Claude multimodal API.
"""

import os
import base64
import time
from typing import List, Dict, Optional, Union
from pathlib import Path

import anthropic


class MultimodalAnalyzer:
    """Client for multimodal analysis using Claude API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 600.0,
        max_tokens: int = 16000
    ):
        """
        Initialize the multimodal analyzer.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            base_url: Base URL for API (defaults to ANTHROPIC_BASE_URL env var)
            timeout: Request timeout in seconds
            max_tokens: Maximum tokens in response
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL")
        self.timeout = timeout
        self.max_tokens = max_tokens

        self._client = None

    @property
    def client(self) -> anthropic.Anthropic:
        """Get or create the Anthropic client."""
        if self._client is None:
            self._client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self._client

    @staticmethod
    def get_media_type(path: str) -> str:
        """
        Get MIME type for an image file.

        Args:
            path: Path to image file

        Returns:
            MIME type string
        """
        ext = Path(path).suffix.lower()
        media_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return media_types.get(ext, 'image/png')

    @staticmethod
    def encode_image(path: str) -> str:
        """
        Encode an image file to base64.

        Args:
            path: Path to image file

        Returns:
            Base64 encoded string
        """
        with open(path, 'rb') as f:
            return base64.standard_b64encode(f.read()).decode('utf-8')

    def _create_image_block(self, path: str) -> Dict:
        """
        Create an image content block for the API.

        Args:
            path: Path to image file

        Returns:
            Content block dict
        """
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": self.get_media_type(path),
                "data": self.encode_image(path)
            }
        }

    def analyze_text(
        self,
        system_prompt: str,
        text_content: str,
        model: str = "claude-sonnet-4-20250514",
        max_retries: int = 2
    ) -> str:
        """
        Analyze text content using Claude API.

        Args:
            system_prompt: System prompt for the analysis
            text_content: Text content to analyze
            model: Claude model to use
            max_retries: Maximum number of retries on failure

        Returns:
            Analysis result text
        """
        return self.analyze_with_images(
            system_prompt=system_prompt,
            text_content=text_content,
            images=[],
            model=model,
            max_retries=max_retries
        )

    def analyze_with_images(
        self,
        system_prompt: str,
        text_content: str,
        images: List[Dict],
        model: str = "claude-sonnet-4-20250514",
        max_retries: int = 2,
        max_images: int = 20
    ) -> str:
        """
        Analyze text and images using Claude multimodal API.

        Args:
            system_prompt: System prompt for the analysis
            text_content: Text content to analyze
            images: List of image dicts with 'path', 'filename', 'page', 'type' keys
            model: Claude model to use
            max_retries: Maximum number of retries on failure
            max_images: Maximum number of images to include

        Returns:
            Analysis result text
        """
        # Build content blocks
        content_blocks = [{"type": "text", "text": text_content}]

        # Add images (limited to max_images)
        included_images = images[:max_images]
        skipped_count = len(images) - len(included_images)

        if skipped_count > 0:
            print(f"Warning: Skipping {skipped_count} images (max {max_images})")

        for img_info in included_images:
            img_path = img_info.get("path")
            if not img_path or not os.path.exists(img_path):
                print(f"Warning: Image not found: {img_path}")
                continue

            try:
                # Add image block
                content_blocks.append(self._create_image_block(img_path))

                # Add label for the image
                filename = img_info.get("filename", "unknown")
                page = img_info.get("page", "?")
                img_type = img_info.get("type", "image")

                label = f"\n<{img_type}: {filename} (page {page})>\n"
                content_blocks.append({"type": "text", "text": label})

            except Exception as e:
                print(f"Warning: Failed to process image {img_path}: {e}")
                continue

        # Call API with retries
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                message = self.client.messages.create(
                    model=model,
                    max_tokens=self.max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": content_blocks}]
                )

                # Extract text from response
                result_parts = []
                for block in message.content:
                    if hasattr(block, 'text'):
                        result_parts.append(block.text)
                    # Skip thinking blocks
                    elif hasattr(block, 'thinking'):
                        continue

                return "\n".join(result_parts)

            except anthropic.InternalServerError as e:
                last_error = e
                if "524" in str(e) or "timeout" in str(e).lower():
                    print(f"Timeout error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    if attempt < max_retries:
                        time.sleep(5)
                        continue
                raise

            except anthropic.RateLimitError as e:
                last_error = e
                wait_time = 2 ** attempt
                print(f"Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries + 1})")
                if attempt < max_retries:
                    time.sleep(wait_time)
                    continue
                raise

            except Exception as e:
                last_error = e
                raise

        raise last_error or Exception("Unknown error in multimodal analysis")


# Convenience functions
_analyzer = None


def get_analyzer() -> MultimodalAnalyzer:
    """Get or create the default analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = MultimodalAnalyzer()
    return _analyzer


def analyze(
    system_prompt: str,
    text_content: str,
    model: str = "claude-sonnet-4-20250514"
) -> str:
    """
    Analyze text content.

    Args:
        system_prompt: System prompt
        text_content: Text to analyze
        model: Claude model

    Returns:
        Analysis result
    """
    return get_analyzer().analyze_text(system_prompt, text_content, model)


def analyze_with_images(
    system_prompt: str,
    text_content: str,
    images: List[Dict],
    model: str = "claude-sonnet-4-20250514"
) -> str:
    """
    Analyze text with images.

    Args:
        system_prompt: System prompt
        text_content: Text to analyze
        images: List of image dicts
        model: Claude model

    Returns:
        Analysis result
    """
    return get_analyzer().analyze_with_images(
        system_prompt, text_content, images, model
    )


def analyze_with_image_paths(
    system_prompt: str,
    text_content: str,
    image_paths: List[str],
    model: str = "claude-sonnet-4-20250514"
) -> str:
    """
    Analyze text with images from paths.

    Args:
        system_prompt: System prompt
        text_content: Text to analyze
        image_paths: List of image file paths
        model: Claude model

    Returns:
        Analysis result
    """
    images = [
        {"path": p, "filename": os.path.basename(p), "page": "?"}
        for p in image_paths
    ]
    return get_analyzer().analyze_with_images(
        system_prompt, text_content, images, model
    )


if __name__ == "__main__":
    # Test the analyzer
    import sys

    if len(sys.argv) < 2:
        print("Usage: python multimodal_client.py <text>")
        print("       python multimodal_client.py <text> <image1> [image2] ...")
        sys.exit(1)

    text = sys.argv[1]
    image_paths = sys.argv[2:] if len(sys.argv) > 2 else []

    analyzer = MultimodalAnalyzer()

    if image_paths:
        images = [
            {"path": p, "filename": os.path.basename(p), "page": "?"}
            for p in image_paths
        ]
        result = analyzer.analyze_with_images(
            system_prompt="Analyze the provided content.",
            text_content=text,
            images=images
        )
    else:
        result = analyzer.analyze_text(
            system_prompt="Analyze the provided content.",
            text_content=text
        )

    print(result)