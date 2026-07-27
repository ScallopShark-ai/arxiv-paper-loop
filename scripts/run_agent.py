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


def run_analyze_pri(output_dir: str, start_date: str = None, end_date: str = None):
    """Run analyze_pri agent - search and download papers."""
    sys.path.insert(0, ".claude/skills/arxiv-connect/scripts")
    from arxiv_client import ArxivClient

    config = load_agent_config("analyze_pri")
    system_prompt = get_system_prompt(config)

    # Use provided date range or default to yesterday
    if start_date is None or end_date is None:
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        start_date = yesterday
        end_date = yesterday

    print(f"Searching papers for date range: {start_date} to {end_date}")

    # Search papers - use keyword search instead of date range (more reliable)
    # arXiv API date range queries often return 500 errors
    client = ArxivClient()

    # Search by keywords relevant to RL, Agent, Human Behavior, Game AI Bot
    keywords = [
        "reinforcement learning",
        "large language model agent",
        "human behavior",
        "game AI",
        "game bot",
        "LLM agent",
        "autonomous agent"
    ]

    print("Searching with keywords instead of date range (more reliable)...")
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
                # Parse paper published date
                pub_date_str = paper.published.split("T")[0]  # Format: 2026-07-15T...
                pub_date = dt.strptime(pub_date_str, "%Y-%m-%d")
                if start_dt <= pub_date <= end_dt:
                    filtered_papers.append(paper)
            except:
                continue

        papers = filtered_papers
        print(f"Filtered to {len(papers)} papers in date range")

    # Handle no papers found
    if not papers:
        print("No papers found for the given criteria")
        os.makedirs(output_dir, exist_ok=True)
        # Create a marker file to indicate no papers (non-hidden for artifact upload)
        with open(f"{output_dir}/no_papers.txt", "w", encoding="utf-8") as f:
            f.write(f"No papers found for date range {start_date} to {end_date}")
        # Update state
        with open("state.md", "a", encoding="utf-8") as f:
            f.write(f"\n## {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(f"- Papers screened: 0\n")
            f.write(f"- Papers downloaded: 0\n")
        return []

    # Filter papers using Claude
    os.makedirs(output_dir, exist_ok=True)
    downloaded = []

    for paper in papers[:30]:  # Limit to 30
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

    # Handle no papers found
    if not papers:
        print("No papers to analyze")
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_file = f"{output_dir}/{date_str}-acc.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# 无相关论文\n\n")
            f.write("昨日没有相关论文。\n")
        return output_file

    all_analyses = []
    date_str = datetime.now().strftime("%Y-%m-%d")

    for paper in papers:
        print(f"Analyzing: {paper['filename']}")

        # Read PDF content
        sys.path.insert(0, ".claude/skills/pdf-reader/scripts")
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

    # Handle no analyses found - generate Chinese report directly
    if not analyses:
        print("No analysis files found")
        date_str = datetime.now().strftime("%Y-%m-%d")
        summary = f"""# 论文日报 - {date_str}

## 每日概览
- 日期：{date_str}
- 分析论文数：0 篇
- 评分分布：Accept (0), Minor Revision (0), Major Revision (0), Reject (0)

## 论文摘要

昨日没有发现符合筛选条件的相关论文。

## 重点推荐

暂无推荐论文。

## 详细分析

由于没有相关论文，暂无详细分析内容。

---

**说明：** 本日报基于arXiv每日更新的论文进行自动分析和筛选。未发现相关论文可能是由于：
1. 该领域当日没有新提交的论文
2. 新提交的论文不符合预设的筛选标准
3. arXiv API 查询出现异常

建议关注后续日期的更新。"""
    else:
        # Combine analyses
        combined = "\n\n".join([f"### {a['filename']}\n\n{a['content']}" for a in analyses])

        user_message = f"""请根据以下分析报告，生成一份中文的论文日报。

{combined}

输出要求：
1. 必须使用中文输出所有内容
2. 按照 agent 配置中的格式输出
3. 包括每日概览、论文摘要、重点推荐等部分"""

        summary = call_claude(system_prompt, user_message)

    # Publish to Notion - create new child page with today's date
    sys.path.insert(0, ".claude/skills/notion-connector/scripts")
    from notion_publisher import create_child_page, write_to_page

    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"Creating new Notion page for: {date_str}")
    page_id = create_child_page(date_str)
    write_to_page(page_id, summary)

    print(f"Published to Notion! Page ID: {page_id}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Run an agent")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--input-dir", help="Input directory")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--publish-notion", action="store_true", help="Publish to Notion")

    args = parser.parse_args()

    # Add skills to path
    sys.path.insert(0, ".")

    if args.agent == "analyze_pri":
        run_analyze_pri(args.output_dir or "papers/", args.start_date, args.end_date)

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