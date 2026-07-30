#!/usr/bin/env python3
"""
Run Agent Script
Loads agent configuration and calls Claude API.
"""

import os
import sys
import argparse
import glob
import shutil
from datetime import datetime
from pathlib import Path

import anthropic


def load_agent_config(agent_name: str) -> dict:
    """Load agent configuration from TOML file."""
    import tomllib

    config_path = Path(f".claude/agents/{agent_name}.toml")
    if not config_path.exists():
        raise FileNotFoundError(f"Agent config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split on --- and only parse the TOML part
    if "---" in content:
        toml_part = content.split("---", 1)[0]
    else:
        toml_part = content

    config = tomllib.loads(toml_part)
    return config


def get_system_prompt(config: dict) -> str:
    """Extract system prompt from agent config."""
    # The TOML file content after --- separator is the prompt
    config_path = Path(f".claude/agents/{config['name']}.toml")

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the --- separator and extract prompt
    if "---" in content:
        parts = content.split("---", 1)
        if len(parts) > 1:
            return parts[1].strip()

    return ""


def read_papers(input_dir: str) -> list:
    """Read PDF files from input directory."""
    papers = []
    pdf_files = glob.glob(f"{input_dir}/*.pdf")

    for pdf_path in pdf_files:
        papers.append({
            "path": pdf_path,
            "filename": os.path.basename(pdf_path)
        })

    return papers


def read_analysis_files(input_dir: str) -> list:
    """Read analysis files from input directory."""
    analyses = []
    md_files = glob.glob(f"{input_dir}/*.md")

    for md_path in md_files:
        with open(md_path, "r", encoding="utf-8") as f:
            analyses.append({
                "path": md_path,
                "filename": os.path.basename(md_path),
                "content": f.read()
            })

    return analyses


def call_claude(system_prompt: str, user_message: str, model: str, max_retries: int = 2) -> str:
    """Call Claude API with specified model."""
    import time

    # Set longer timeout for large content processing (10 minutes)
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
        timeout=600.0  # 10 minutes timeout
    )

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=16000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            # Handle both regular text blocks and thinking blocks
            result_parts = []
            for block in message.content:
                if hasattr(block, 'text'):
                    result_parts.append(block.text)
                # Skip thinking blocks - do not include in output
                elif hasattr(block, 'thinking'):
                    continue
                else:
                    result_parts.append(str(block))

            return "\n".join(result_parts)

        except anthropic.InternalServerError as e:
            last_error = e
            if "524" in str(e) or "timeout" in str(e).lower():
                print(f"Timeout error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    time.sleep(5)
                    continue
            raise
        except Exception as e:
            last_error = e
            raise

    raise last_error


def call_claude_with_images(system_prompt: str, text_content: str, images: list, model: str, max_retries: int = 2) -> str:
    """Call Claude API with multimodal content (text + images)."""
    import time
    import base64

    # Set longer timeout for large content processing (10 minutes)
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
        timeout=600.0  # 10 minutes timeout
    )

    # Build content blocks
    content_blocks = [{"type": "text", "text": text_content}]

    # Add images (limit to first 20 to avoid token limits)
    for img_info in images[:20]:
        img_path = img_info["path"]
        try:
            with open(img_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            # Determine media type
            ext = os.path.splitext(img_path)[1].lower()
            media_type = "image/png" if ext == ".png" else "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"

            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data
                }
            })
            # Add label for the image
            content_blocks.append({
                "type": "text",
                "text": f"\n<图/表：{img_info['filename']} (第{img_info['page']}页)>\n"
            })
        except Exception as e:
            print(f"Warning: Failed to read image {img_path}: {e}")
            continue

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=16000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": content_blocks}
                ]
            )

            # Handle both regular text blocks and thinking blocks
            result_parts = []
            for block in message.content:
                if hasattr(block, 'text'):
                    result_parts.append(block.text)
                # Skip thinking blocks - do not include in output
                elif hasattr(block, 'thinking'):
                    continue
                else:
                    result_parts.append(str(block))

            return "\n".join(result_parts)

        except anthropic.InternalServerError as e:
            last_error = e
            if "524" in str(e) or "timeout" in str(e).lower():
                print(f"Timeout error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    time.sleep(5)
                    continue
            raise
        except Exception as e:
            last_error = e
            raise

    raise last_error


def run_analyze_pri(output_dir: str, temp_dir: str, start_date: str = None, end_date: str = None, save_temp: bool = False, paper_ids: str = None):
    """Run analyze_pri agent - search and download papers."""
    sys.path.insert(0, ".claude/skills/arxiv-connect/scripts")
    from arxiv_client import ArxivClient

    config = load_agent_config("analyze_pri")
    system_prompt = get_system_prompt(config)
    model = config.get("model", "claude-sonnet-4-20250514")

    # Create directories
    os.makedirs(output_dir, exist_ok=True)
    if save_temp:
        os.makedirs(temp_dir, exist_ok=True)

    client = ArxivClient()

    # Direct download mode: skip search, just download specified papers
    if paper_ids:
        print(f"Direct download mode: {paper_ids}")
        downloaded = []
        for arxiv_id in paper_ids.split(","):
            arxiv_id = arxiv_id.strip()
            if arxiv_id:
                print(f"Downloading: {arxiv_id}")
                client.download(arxiv_id, output_dir)
                if save_temp:
                    client.download(arxiv_id, temp_dir)
                downloaded.append(arxiv_id)
        print(f"Downloaded {len(downloaded)} papers")
        return downloaded

    # Normal search mode
    # Use provided date range or default to yesterday
    if start_date is None or end_date is None:
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        start_date = yesterday
        end_date = yesterday

    print(f"Searching papers for date range: {start_date} to {end_date}")
    print(f"Using model: {model}")

    # Search by keywords relevant to RL, Agent, RLHF, etc.
    keywords = [
        "reinforcement learning",
        "RLHF",
        "preference learning",
        "human feedback",
        "reward learning",
        "reward model",
        "LLM agent",
        "autonomous agent",
        "game AI",
        "self-play"
    ]

    print("Searching with keywords...")
    papers = client.search(
        categories=["cs.LG", "cs.AI", "cs.CL", "cs.NE"],
        keywords=keywords,
        max_results=50
    )

    # Filter papers by submission date locally
    if papers and start_date and end_date:
        from datetime import datetime as dt
        start_dt = dt.strptime(start_date, "%Y-%m-%d")
        end_dt = dt.strptime(end_date, "%Y-%m-%d")

        filtered_papers = []
        for paper in papers:
            try:
                pub_date_str = paper.published.split("T")[0]
                pub_date = dt.strptime(pub_date_str, "%Y-%m-%d")
                if start_dt <= pub_date <= end_dt:
                    filtered_papers.append(paper)
            except:
                continue

        papers = filtered_papers
        print(f"Filtered to {len(papers)} papers in date range {start_date} to {end_date}")

    # Create directories
    os.makedirs(output_dir, exist_ok=True)
    if save_temp:
        os.makedirs(temp_dir, exist_ok=True)

    # Handle no papers found
    if not papers:
        print("No papers found for the given criteria")
        with open(f"{output_dir}/no_papers.txt", "w", encoding="utf-8") as f:
            f.write(f"No papers found for date range {start_date} to {end_date}")
        return []

    # Filter papers using Claude - check up to 20 papers, download max 5
    downloaded = []

    for paper in papers[:20]:
        # Stop if we already have 5 papers
        if len(downloaded) >= 5:
            print(f"Reached limit of 5 papers, stopping")
            break

        user_message = f"""
        Evaluate this paper based on the screening criteria:

        Title: {paper.title}
        Abstract: {paper.abstract}
        Categories: {', '.join(paper.categories)}

        Should this paper be downloaded? Answer YES or NO with a brief reason.
        """

        response = call_claude(system_prompt, user_message, model)

        if "YES" in response.upper():
            print(f"Downloading: {paper.arxiv_id}")
            # Download to output_dir (always)
            client.download(paper.arxiv_id, output_dir)
            # Download to temp_dir only if save_temp is True
            if save_temp:
                client.download(paper.arxiv_id, temp_dir)
            downloaded.append(paper)

    return downloaded


def extract_images_from_pdfs(input_dir: str, output_dir: str) -> dict:
    """Extract images from all PDFs in input directory."""
    import sys
    sys.path.insert(0, ".claude/skills/pdf-image-extractor/scripts")
    from pdf_image_extractor import extract_images

    image_info = {}
    pdf_files = glob.glob(f"{input_dir}/*.pdf")

    for pdf_path in pdf_files:
        pdf_name = os.path.basename(pdf_path).replace(".pdf", "")
        image_output_dir = f"{output_dir}/images/{pdf_name}"
        os.makedirs(image_output_dir, exist_ok=True)

        try:
            images = extract_images(pdf_path, image_output_dir, extract_tables=True)
            image_info[pdf_name] = {
                "path": image_output_dir,
                "images": images
            }
            print(f"Extracted {len(images)} images from {pdf_name}")
        except Exception as e:
            print(f"Warning: Failed to extract images from {pdf_name}: {e}")
            image_info[pdf_name] = {"path": image_output_dir, "images": []}

    return image_info


def run_analyze_agent(agent_name: str, input_dir: str, output_dir: str, temp_dir: str, save_temp: bool = False):
    """Run an analysis agent (analyze_acc, experiment_analyze)."""
    config = load_agent_config(agent_name)
    system_prompt = get_system_prompt(config)
    model = config.get("model", "claude-sonnet-4-20250514")

    papers = read_papers(input_dir)
    os.makedirs(output_dir, exist_ok=True)
    if save_temp:
        os.makedirs(temp_dir, exist_ok=True)

    print(f"Running {agent_name} with model: {model}")

    # Extract images from PDFs first
    print("Extracting images from PDFs...")
    image_info = extract_images_from_pdfs(input_dir, output_dir)

    # Handle no papers found
    if not papers:
        print("No papers to analyze")
        date_str = datetime.now().strftime("%Y-%m-%d")
        suffix = "acc" if agent_name == "analyze_acc" else "exp"
        output_file = f"{output_dir}/{date_str}-{suffix}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# 无相关论文\n\n昨日没有相关论文。\n")
        return output_file

    all_analyses = []
    date_str = datetime.now().strftime("%Y-%m-%d")
    suffix = "acc" if agent_name == "analyze_acc" else "exp"

    for paper in papers:
        print(f"Analyzing: {paper['filename']}")
        paper_name = paper['filename'].replace(".pdf", "")

        # Read PDF content
        sys.path.insert(0, ".claude/skills/pdf-reader/scripts")
        from pdf_reader import read_pdf
        content = read_pdf(paper['path'])

        # Build image list if images were extracted
        image_list = []
        if paper_name in image_info and image_info[paper_name]["images"]:
            images = image_info[paper_name]["images"]
            image_dir = image_info[paper_name]["path"]
            # Build list of images with full paths
            for img in images[:20]:  # Limit to 20 images to avoid token limits
                img_path = os.path.join(image_dir, img['filename'])
                if os.path.exists(img_path):
                    image_list.append({
                        "path": img_path,
                        "filename": img['filename'],
                        "page": img.get('page', '?'),
                        "type": img.get('type', 'image')
                    })
            print(f"  Including {len(image_list)} images for analysis")

        # Build text content
        text_content = f"""
        Analyze this paper:

        Filename: {paper['filename']}

        Content:
        {content}
        """

        # Use multimodal API if images are available
        if image_list:
            print(f"  Using multimodal API with {len(image_list)} images")
            analysis = call_claude_with_images(system_prompt, text_content, image_list, model)
        else:
            analysis = call_claude(system_prompt, text_content, model)

        all_analyses.append(f"## {paper['filename']}\n\n{analysis}")

    # Write output to output_dir (always)
    output_file = f"{output_dir}/{date_str}-{suffix}.md"
    content = "\n\n---\n\n".join(all_analyses)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)

    # Write to temp_dir only if save_temp is True
    if save_temp:
        temp_file = f"{temp_dir}/{date_str}-{suffix}.md"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"Wrote analysis to: {output_file}")
    return output_file


def run_summarize_and_publish(input_dir: str, temp_dir: str, save_temp: bool = False, image_url_map: dict = None):
    """Run summarize_and_publish agent - translate and create two sub-pages.

    Args:
        input_dir: Directory containing analysis files
        temp_dir: Directory for temporary files
        save_temp: Whether to save intermediate files
        image_url_map: Dict mapping local image paths to GitHub URLs
    """
    config = load_agent_config("summarize_and_publish")
    system_prompt = get_system_prompt(config)
    model = config.get("model", "claude-sonnet-4-20250514")

    print(f"Running summarize_and_publish with model: {model}")

    # Read all analysis files
    analyses = read_analysis_files(input_dir)

    # Separate analyses by type
    acc_analyses = [a for a in analyses if '-acc.' in a['filename']]
    exp_analyses = [a for a in analyses if '-exp.' in a['filename']]

    print(f"Found: {len(acc_analyses)} acc, {len(exp_analyses)} exp analyses")

    # Import notion functions
    sys.path.insert(0, ".claude/skills/notion-connector/scripts")
    from notion_publisher import create_child_page, write_to_page, get_client

    # Initialize client with image URL map if provided
    if image_url_map:
        client = get_client(image_url_map)
        print(f"Notion client initialized with {len(image_url_map)} image URL mappings")

    date_str = datetime.now().strftime("%Y-%m-%d")

    # Handle no analyses found
    if not analyses:
        print("No analysis files found")

        # Create parent page
        print(f"Creating parent page: {date_str}")
        parent_page_id = create_child_page(date_str)

        # Write empty state to parent
        empty_content = f"""# 论文日报 - {date_str}

## 📚 每日论文分析

昨日没有发现符合筛选条件的相关论文。

---
*自动生成*
"""
        write_to_page(parent_page_id, empty_content)
        print(f"Published empty state to Notion! Page ID: {parent_page_id}")
        return

    # Build input for LLM translation
    combined_input = "# 输入分析报告\n\n"

    if acc_analyses:
        combined_input += "## ACC 分析报告\n\n"
        for a in acc_analyses:
            combined_input += f"### {a['filename']}\n\n{a['content']}\n\n"

    if exp_analyses:
        combined_input += "## EXP 分析报告\n\n"
        for a in exp_analyses:
            combined_input += f"### {a['filename']}\n\n{a['content']}\n\n"

    # Call LLM to translate and format
    print("Translating and formatting content...")
    user_message = f"""请将以下分析报告翻译为中文，并正确处理公式格式：

{combined_input}

要求：
1. 所有内容翻译为中文
2. LaTeX 公式转换为可读文本
3. 保持表格结构
4. 输出格式：
=== ACC 内容 ===
[翻译后的内容]

=== EXP 内容 ===
[翻译后的内容]
"""

    translated_content = call_claude(system_prompt, user_message, model)

    # Debug: save translated content
    if save_temp:
        date_str = datetime.now().strftime("%Y-%m-%d")
        temp_translated_file = f"{temp_dir}/{date_str}-translated.md"
        os.makedirs(temp_dir, exist_ok=True)
        with open(temp_translated_file, "w", encoding="utf-8") as f:
            f.write(translated_content)
        print(f"Saved translated content to: {temp_translated_file}")

    # Parse translated content with new markers
    acc_content = ""
    exp_content = ""

    if "<<<ACC_START>>>" in translated_content and "<<<ACC_END>>>" in translated_content:
        acc_start = translated_content.find("<<<ACC_START>>>") + len("<<<ACC_START>>>")
        acc_end = translated_content.find("<<<ACC_END>>>")
        acc_content = translated_content[acc_start:acc_end].strip()
        print("Successfully parsed ACC content")
    else:
        print("Warning: ACC markers not found")

    if "<<<EXP_START>>>" in translated_content and "<<<EXP_END>>>" in translated_content:
        exp_start = translated_content.find("<<<EXP_START>>>") + len("<<<EXP_START>>>")
        exp_end = translated_content.find("<<<EXP_END>>>")
        exp_content = translated_content[exp_start:exp_end].strip()
        print("Successfully parsed EXP content")
    else:
        print("Warning: EXP markers not found")

    # Fallback if parsing failed
    if not acc_content and acc_analyses:
        print("Warning: Using raw ACC content (no translation)")
        acc_content = "\n\n---\n\n".join([a['content'] for a in acc_analyses])
    if not exp_content and exp_analyses:
        print("Warning: Using raw EXP content (no translation)")
        exp_content = "\n\n---\n\n".join([a['content'] for a in exp_analyses])

    # Create parent page (date)
    print(f"Creating parent page: {date_str}")
    parent_page_id = create_child_page(date_str)

    # Create and populate 论文详解 sub-page
    if acc_content:
        print("Creating 论文详解 sub-page...")
        acc_page_id = create_child_page("论文详解", parent_id=parent_page_id)
        write_to_page(acc_page_id, acc_content)
        print(f"Written acc content to: {acc_page_id}")

    # Create and populate 实验报告 sub-page
    if exp_content:
        print("Creating 实验报告 sub-page...")
        exp_page_id = create_child_page("实验报告", parent_id=parent_page_id)
        write_to_page(exp_page_id, exp_content)
        print(f"Written exp content to: {exp_page_id}")

    # Update parent page with index
    index_content = f"""# 论文日报 - {date_str}

## 📚 每日论文分析

- 论文详解 - 综合评价分析
- 实验报告 - 实验方法与结果分析

---
*自动生成*
"""
    write_to_page(parent_page_id, index_content)

    print(f"Published to Notion! Parent Page ID: {parent_page_id}")
    return parent_page_id


def main():
    parser = argparse.ArgumentParser(description="Run an agent")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--input-dir", help="Input directory")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--temp-dir", default="temp", help="Temp directory for intermediate files")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--save-temp", action="store_true", help="Save intermediate files to temp folder")
    parser.add_argument("--publish-notion", action="store_true", help="Publish to Notion")
    parser.add_argument("--paper-ids", help="Direct download: comma-separated arxiv IDs")
    parser.add_argument("--image-urls", help="JSON file with image URL mappings")

    args = parser.parse_args()

    # Add skills to path
    sys.path.insert(0, ".")

    if args.agent == "analyze_pri":
        run_analyze_pri(args.output_dir or "papers/", args.temp_dir, args.start_date, args.end_date, args.save_temp, args.paper_ids)

    elif args.agent == "analyze_acc":
        run_analyze_agent("analyze_acc", args.input_dir or "papers/", args.output_dir or "analysis/", args.temp_dir, args.save_temp)

    elif args.agent == "experiment_analyze":
        run_analyze_agent("experiment_analyze", args.input_dir or "papers/", args.output_dir or "analysis/", args.temp_dir, args.save_temp)

    elif args.agent == "summarize_and_publish":
        image_url_map = None
        if args.image_urls:
            import json
            with open(args.image_urls, "r", encoding="utf-8") as f:
                image_url_map = json.load(f)
            print(f"Loaded {len(image_url_map)} image URL mappings")
        run_summarize_and_publish(args.input_dir or "analysis/", args.temp_dir, args.save_temp, image_url_map)

    else:
        print(f"Unknown agent: {args.agent}")
        sys.exit(1)


if __name__ == "__main__":
    main()