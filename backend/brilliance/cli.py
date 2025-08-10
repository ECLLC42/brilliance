#!/usr/bin/env python3
"""Command-line workflow that exercises the new two-step backend logic locally (no HTTP required).

Usage:
    python cli_workflow.py "crispr gene editing 2025"

It will:
1. Optimize & gather papers via `multi_source_search`.
2. Print counts per source.
3. Run `synthesize_papers_async` on the combined metadata.
4. Print the final AI synthesis.

This lets you validate backend logic quickly before wiring up the React frontend.
"""
from __future__ import annotations

import asyncio
import sys
from textwrap import indent

from brilliance.agents.workflows import multi_source_search, prepare_results_for_synthesis
from dotenv import load_dotenv, find_dotenv
from brilliance.synthesis.synthesis_tool import synthesize_papers_async


def cyan(text: str) -> str:
    return f"\033[36m{text}\033[0m"


def bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


async def run_workflow(user_query: str, max_results: int = 3):
    print(bold("\n🔍 Collecting papers ..."))
    collected = await multi_source_search(user_query, max_results)
    payload = prepare_results_for_synthesis(collected)

    # Summary stats
    summary = payload.get("summary", {})
    print(f"Found {summary.get('total', 0)} papers across {len(summary.get('sources', []))} sources\n")

    for source, block in payload["raw_results"].items():
        if not block or block.startswith("No papers") or block.startswith("Error"):
            print(f"{source.capitalize()}: 0 papers")
        else:
            count = block.count("\nURL: ")  # quick heuristic
            print(f"{source.capitalize()}: {count} papers")

    # Build combined text for synthesis
    combined = ""
    for s, block in payload["raw_results"].items():
        if block and not block.startswith("No papers") and not block.startswith("Error"):
            combined += f"\n=== {s.upper()} Results ===\n{block}\n"

    if not combined.strip():
        print("\n❌ Nothing to synthesize.")
        return

    print(bold("\n🤖 Synthesizing AI summary ..."))
    prompt = f"User Query: {user_query}\n\nPaper Data:\n{combined}"
    summary_text = await synthesize_papers_async(prompt)

    print(cyan("\n===== AI SYNTHESIS ====="))
    print(indent(summary_text, " "))
    print(cyan("===== END =====\n"))


def main():
    # Ensure environment variables from .env are loaded
    load_dotenv(find_dotenv())
    if len(sys.argv) < 2:
        print("Usage: python cli_workflow.py \"research question\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    asyncio.run(run_workflow(query))


if __name__ == "__main__":
    main()
