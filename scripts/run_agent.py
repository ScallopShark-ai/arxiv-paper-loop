#!/usr/bin/env python3
"""
Run Agent Script
Loads agent configuration and calls Claude API.
"""

import os
import sys
import argparse
import glob
from datetime import datetime
from pathlib import Path

import anthropic


def load_agent_config(agent_name: str) -> dict:
    """Load agent configuration from TOML file."""
    import tomllib

    config_path = Path(f".claude/agents/{agent_name}.toml")
    if not config_path.exists():
        raise FileNotFoundError(f"Agent config not found: {config_path}")

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

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


def call_claude(system_prompt: str, user_message: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Call Claude API."""
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("ANTHROPIC_BASE_URL")
    )

    message = client.messages.create(
        model=model,
        max_tokens=16000,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_message}
        ]
    )

    return message.content[0].text


def run_analyze_pri(output_dir: str, paper_date: str = None):
    """Run analyze_pri agent - search and download papers."""
    sys.path.insert(0, ".claude/skills/arxiv-connect")
    from arxiv_client import ArxivClient

    config = load_agent_config("analyze_pri")
    system_prompt = get_system_prompt(config)

    # Use provided date or default to yesterday
    if paper_date is None:
        from datetime import timedelta
        paper_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"Searching papers for date: {paper_date}")

    # Search papers
    client = ArxivClient()
    papers = client.search(
        categories=["cs.LG", "cs.AI", "cs.CL", "cs.NE"],
        date=paper_date,
        max_results=50
    )

    # Filter papers using Claude
    os.makedirs(output_dir, exist_ok=True)
    downloaded = []

    for paper in papers[:20]:  # Limit to 20
        # Ask Claude to evaluate the paper
        user_message = f"""
        Evaluate this paper based on the screening criteria:

        Title: {paper.title}
        Abstract: {paper.abstract}
        Categories: {', '.join(paper.categories)}

        Should this paper be downloaded? Answer YES or NO with a brief reason.
        """

        response = call_claude(system_prompt, user_message)

        if "YES" in response.upper():
            print(f"Downloading: {paper.arxiv_id}")
            client.download(paper.arxiv_id, output_dir)
            downloaded.append(paper)

    # Update state
    with open("state.md", "a", encoding="utf-8") as f:
        f.write(f"\n## {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"- Papers screened: {len(papers)}\n")
        f.write(f"- Papers downloaded: {len(downloaded)}\n")

    return downloaded


def run_analyze_acc(input_dir: str, output_dir: str):
    """Run analyze_acc agent - comprehensive paper analysis."""
    config = load_agent_config("analyze_acc")
    system_prompt = get_system_prompt(config)

    papers = read_papers(input_dir)
    os.makedirs(output_dir, exist_ok=True)

    all_analyses = []
    date_str = datetime.now().strftime("%Y-%m-%d")

    for paper in papers:
        print(f"Analyzing: {paper['filename']}")

        # Read PDF content
        sys.path.insert(0, ".claude/skills/pdf-reader")
        from pdf_reader import read_pdf
        content = read_pdf(paper['path'])

        user_message = f"""
        Analyze this paper:

        Filename: {paper['filename']}

        Content:
        {content[:50000]}  # Limit content length
        """

        analysis = call_claude(system_prompt, user_message, model="claude-sonnet-4-20250514")
        all_analyses.append(f"## {paper['filename']}\n\n{analysis}")

    # Write output
    output_file = f"{output_dir}/{date_str}-acc.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(all_analyses))

    return output_file


def run_summarize_and_publish(input_dir: str):
    """Run summarize_and_publish agent - integrate and publish to Notion."""
    config = load_agent_config("summarize_and_publish")
    system_prompt = get_system_prompt(config)

    # Read all analysis files
    analyses = read_analysis_files(input_dir)

    # Combine analyses
    combined = "\n\n".join([f"### {a['filename']}\n\n{a['content']}" for a in analyses])

    user_message = f"""
    Integrate these analyses and create a summary:

    {combined}
    """

    summary = call_claude(system_prompt, user_message)

    # Publish to Notion
    sys.path.insert(0, ".claude/skills/notion-connector")
    from notion_client import write_page, clear_page

    clear_page()
    write_page(summary)

    print("Published to Notion!")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Run an agent")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--input-dir", help="Input directory")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--date", help="Paper date (YYYY-MM-DD)")
    parser.add_argument("--publish-notion", action="store_true", help="Publish to Notion")

    args = parser.parse_args()

    # Add skills to path
    sys.path.insert(0, ".")

    if args.agent == "analyze_pri":
        run_analyze_pri(args.output_dir or "papers/", args.date)

    elif args.agent == "analyze_acc":
        run_analyze_acc(args.input_dir or "papers/", args.output_dir or "analysis/")

    elif args.agent == "theory_deri":
        # Similar to analyze_acc but with different prompt
        run_analyze_acc(args.input_dir or "papers/", args.output_dir or "analysis/")

    elif args.agent == "experiment_analyze":
        # Similar to analyze_acc but with different prompt
        run_analyze_acc(args.input_dir or "papers/", args.output_dir or "analysis/")

    elif args.agent == "summarize_and_publish":
        run_summarize_and_publish(args.input_dir or "analysis/")

    else:
        print(f"Unknown agent: {args.agent}")
        sys.exit(1)


if __name__ == "__main__":
    main()