"""
CLI: scan LinkedIn for AI news via a browser agent, write a markdown digest.

Usage:
    python -m linkedin_ai_agent.main
    python -m linkedin_ai_agent.main --topics "LLM research" "AI agents" --output today.md
    python -m linkedin_ai_agent.main --headed   # watch the browser instead of running headless

For a UI instead of the CLI (topic input, live progress, a rendered report),
see the `web/` Next.js app backed by `linkedin_ai_agent.server` - see README.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import os

from dotenv import load_dotenv

from linkedin_ai_agent.pipeline import PipelineEvent, run_pipeline


async def run(topics: list[str], output_path: str, headless: bool, project: str) -> None:
    digest = None
    async for event in run_pipeline(topics, project=project, headless=headless):
        _print_event(event)
        if event.kind == "error":
            return
        if event.kind == "done":
            digest = event.digest

    if digest is None:
        print("ERROR: run finished without producing a digest.")
        return

    with open(output_path, "w") as f:
        f.write(digest.to_markdown())
    print(f"\nDigest written to {output_path} ({len(digest.posts)} posts)")


def _print_event(event: PipelineEvent) -> None:
    if event.kind == "status":
        print(event.label)
    elif event.kind == "tool_start":
        suffix = f": {event.detail}" if event.detail else ""
        print(f"-> {event.label}{suffix}")
    elif event.kind == "tool_end":
        suffix = f": {event.detail}" if event.detail else ""
        print(f"<- {event.label}{suffix}")
    elif event.kind == "error":
        suffix = f" ({event.detail})" if event.detail else ""
        print(f"ERROR: {event.label}{suffix}")


def main() -> None:
    load_dotenv()  # so BROWSER_USE_HEADLESS from .env is visible to the default below
    parser = argparse.ArgumentParser(
        description="Scan LinkedIn for AI news via a browser agent and write a markdown digest."
    )
    parser.add_argument(
        "--topics",
        nargs="+",
        default=["AI research", "large language models", "AI product launches"],
        help="Topics/hashtags to search on LinkedIn.",
    )
    parser.add_argument(
        "--output",
        default=f"linkedin_ai_digest_{datetime.date.today()}.md",
        help="Path to write the markdown digest to.",
    )
    default_headed = os.environ.get("BROWSER_USE_HEADLESS", "true").strip().lower() == "false"
    parser.add_argument(
        "--headed",
        action="store_true",
        default=default_headed,
        help=(
            "Show the browser window instead of running headless. Defaults to "
            "the inverse of the BROWSER_USE_HEADLESS env var (true unless set "
            "to 'false')."
        ),
    )
    parser.add_argument(
        "--project",
        default="linkedin-ai-digest",
        help="LangSmith project name to trace this run under.",
    )
    args = parser.parse_args()
    asyncio.run(run(args.topics, args.output, headless=not args.headed, project=args.project))


if __name__ == "__main__":
    main()
