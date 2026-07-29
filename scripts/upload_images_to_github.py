#!/usr/bin/env python3
"""
Upload Images to GitHub
Extract images from PDFs and commit to GitHub for public URLs.
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict


def extract_images_from_pdfs(input_dir: str, output_dir: str) -> Dict[str, List[str]]:
    """Extract images from all PDFs in a directory."""
    sys.path.insert(0, ".claude/skills/pdf-image-extractor/scripts")
    from pdf_image_extractor import extract_images

    results = {}

    for pdf_file in Path(input_dir).glob("*.pdf"):
        pdf_name = pdf_file.stem
        pdf_output_dir = os.path.join(output_dir, pdf_name)

        images = extract_images(str(pdf_file), pdf_output_dir)
        results[pdf_name] = [img["filename"] for img in images]

    return results


def get_repo_info() -> Dict[str, str]:
    """Get GitHub repo owner and name."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True
    )

    url = result.stdout.strip()

    # Parse URL: https://github.com/owner/repo.git or git@github.com:owner/repo.git
    if url.startswith("https://"):
        parts = url.replace("https://github.com/", "").replace(".git", "").split("/")
    else:
        parts = url.replace("git@github.com:", "").replace(".git", "").split("/")

    return {"owner": parts[0], "repo": parts[1]}


def upload_to_github(
    images_dir: str,
    branch: str = "images",
    message: str = None
) -> Dict[str, str]:
    """
    Upload images to GitHub by committing to a branch.

    Returns dict mapping image filename to GitHub raw URL.
    """
    # Get current branch
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True
    )
    original_branch = result.stdout.strip()

    # Get repo info
    repo_info = get_repo_info()
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Create or switch to images branch
    subprocess.run(["git", "checkout", "-B", branch], capture_output=True)

    # Add images directory
    subprocess.run(["git", "add", "-f", images_dir], capture_output=True)

    # Commit
    commit_message = message or f"Add images {date_str}"
    result = subprocess.run(
        ["git", "commit", "-m", commit_message],
        capture_output=True,
        text=True
    )

    if "nothing to commit" in result.stdout:
        print("No new images to commit")
    else:
        # Push to remote
        subprocess.run(
            ["git", "push", "-f", "origin", branch],
            capture_output=True
        )
        print(f"Pushed images to {branch} branch")

    # Switch back to original branch
    subprocess.run(["git", "checkout", original_branch], capture_output=True)

    # Generate URLs for all images
    url_map = {}
    for root, dirs, files in os.walk(images_dir):
        for f in files:
            if f.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                rel_path = os.path.relpath(os.path.join(root, f), images_dir)
                url = f"https://raw.githubusercontent.com/{repo_info['owner']}/{repo_info['repo']}/{branch}/{images_dir}/{rel_path}"
                url_map[f] = url

    return url_map


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Upload images to GitHub")
    parser.add_argument("--input-dir", default="papers/", help="PDF input directory")
    parser.add_argument("--output-dir", default="extracted_images/", help="Image output directory")
    parser.add_argument("--branch", default="images", help="Git branch for images")
    parser.add_argument("--output-json", help="Output JSON file with URL mappings")

    args = parser.parse_args()

    # Extract images
    print(f"Extracting images from {args.input_dir}...")
    results = extract_images_from_pdfs(args.input_dir, args.output_dir)

    total_images = sum(len(imgs) for imgs in results.values())
    print(f"Extracted {total_images} images")

    if total_images == 0:
        print("No images to upload")
        return

    # Upload to GitHub
    print(f"Uploading to {args.branch} branch...")
    url_map = upload_to_github(args.output_dir, args.branch)

    print(f"\nGenerated {len(url_map)} URLs:")
    for name, url in url_map.items():
        print(f"  {name}: {url}")

    # Save URL mapping
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(url_map, f, indent=2)
        print(f"\nSaved URL mapping to {args.output_json}")


if __name__ == "__main__":
    main()