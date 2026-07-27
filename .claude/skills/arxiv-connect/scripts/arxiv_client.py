"""
arXiv Client for arxiv-paper-loop
Provides connection to arXiv API for searching and downloading papers.
"""

import os
import time
import logging
import requests
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Paper:
    """Represents an arXiv paper."""
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    categories: List[str]
    published: str
    pdf_url: str

    def __repr__(self):
        return f"Paper({self.arxiv_id}: {self.title[:50]}...)"


class ArxivClient:
    """arXiv API client with rate limiting and retry support."""

    BASE_URL = "http://export.arxiv.org/api/query"

    def __init__(self, rate_limit: float = 3.0):
        """
        Initialize arXiv client.

        Args:
            rate_limit: Minimum seconds between requests (default: 3.0)
        """
        self.rate_limit = rate_limit
        self._last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "arxiv-paper-loop/1.0"
        })

    def _wait_for_rate_limit(self):
        """Ensure we don't exceed arXiv rate limit."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    def _retry_request(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """Make request with retry logic."""
        last_error = None
        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response
            except Exception as e:
                last_error = e
                wait_time = self.rate_limit * (2 ** attempt)
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)

        logger.error(f"All retries failed: {last_error}")
        return None

    def search(
        self,
        categories: List[str] = None,
        keywords: List[str] = None,
        date: str = None,
        max_results: int = 50
    ) -> List[Paper]:
        """
        Search for papers on arXiv.

        Args:
            categories: List of arXiv categories (e.g., ["cs.LG", "cs.AI"])
            keywords: List of search keywords
            date: Date in YYYY-MM-DD format (searches papers from this date)
            max_results: Maximum number of results to return

        Returns:
            List of Paper objects
        """
        # Build query
        query_parts = []

        if categories:
            cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
            query_parts.append(f"({cat_query})")

        if keywords:
            kw_query = " OR ".join([f"all:{kw}" for kw in keywords])
            query_parts.append(f"({kw_query})")

        if date:
            # arXiv uses submission date, search for papers on that date
            query_parts.append(f"submittedDate:[{date} TO {date}]")

        query = " AND ".join(query_parts) if query_parts else "all:*"

        # Build URL
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }

        url = f"{self.BASE_URL}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
        logger.info(f"Searching arXiv: {query}")

        # Make request
        response = self._retry_request(url)
        if not response:
            return []

        # Parse response
        papers = self._parse_response(response.text)
        logger.info(f"Found {len(papers)} papers")
        return papers

    def get_paper_info(self, arxiv_id: str) -> Optional[Paper]:
        """
        Get information about a specific paper.

        Args:
            arxiv_id: arXiv identifier (e.g., "2307.12345")

        Returns:
            Paper object or None if not found
        """
        url = f"{self.BASE_URL}?search_query=id:{arxiv_id}&max_results=1"
        logger.info(f"Fetching paper: {arxiv_id}")

        response = self._retry_request(url)
        if not response:
            return None

        papers = self._parse_response(response.text)
        return papers[0] if papers else None

    def download(self, arxiv_id: str, output_dir: str = "papers/") -> Optional[str]:
        """
        Download a paper PDF.

        Args:
            arxiv_id: arXiv identifier
            output_dir: Directory to save PDF

        Returns:
            Path to downloaded file or None on failure
        """
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Construct PDF URL
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        output_path = os.path.join(output_dir, f"{arxiv_id}.pdf")

        # Check if already downloaded
        if os.path.exists(output_path):
            logger.info(f"Paper already downloaded: {output_path}")
            return output_path

        logger.info(f"Downloading {arxiv_id}...")

        response = self._retry_request(pdf_url)
        if not response:
            return None

        # Save PDF
        with open(output_path, "wb") as f:
            f.write(response.content)

        logger.info(f"Downloaded to: {output_path}")
        return output_path

    def _parse_response(self, xml_text: str) -> List[Paper]:
        """Parse arXiv API XML response."""
        import xml.etree.ElementTree as ET

        papers = []

        try:
            root = ET.fromstring(xml_text)

            # Define namespace
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "arxiv": "http://arxiv.org/schemas/atom"
            }

            for entry in root.findall("atom:entry", ns):
                # Get arXiv ID
                id_url = entry.find("atom:id", ns)
                if id_url is None:
                    continue
                arxiv_id = id_url.text.split("/")[-1]

                # Get title
                title_elem = entry.find("atom:title", ns)
                title = title_elem.text.strip() if title_elem is not None else ""

                # Get authors
                authors = []
                for author in entry.findall("atom:author", ns):
                    name = author.find("atom:name", ns)
                    if name is not None:
                        authors.append(name.text)

                # Get abstract
                abstract_elem = entry.find("atom:summary", ns)
                abstract = abstract_elem.text.strip() if abstract_elem is not None else ""

                # Get categories
                categories = []
                for cat in entry.findall("atom:category", ns):
                    term = cat.get("term")
                    if term:
                        categories.append(term)

                # Get published date
                published_elem = entry.find("atom:published", ns)
                published = published_elem.text if published_elem is not None else ""

                # Construct PDF URL
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

                paper = Paper(
                    arxiv_id=arxiv_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    categories=categories,
                    published=published,
                    pdf_url=pdf_url
                )
                papers.append(paper)

        except Exception as e:
            logger.error(f"Error parsing response: {e}")

        return papers


# Convenience functions
_client = None


def get_client() -> ArxivClient:
    """Get or create arXiv client instance."""
    global _client
    if _client is None:
        _client = ArxivClient()
    return _client


def search_papers(
    categories: List[str] = None,
    keywords: List[str] = None,
    date: str = None,
    max_results: int = 50
) -> List[Paper]:
    """Search for papers on arXiv."""
    return get_client().search(categories, keywords, date, max_results)


def get_paper_info(arxiv_id: str) -> Optional[Paper]:
    """Get information about a specific paper."""
    return get_client().get_paper_info(arxiv_id)


def download_paper(arxiv_id: str, output_dir: str = "papers/") -> Optional[str]:
    """Download a paper PDF."""
    return get_client().download(arxiv_id, output_dir)