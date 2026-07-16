"""
CLI: scan LinkedIn for AI news via a browser agent, write a markdown digest.

Usage:
    python -m linkedin_ai_agent.main
    python -m linkedin_ai_agent.main --topics "LLM research" "AI agents" --output today.md
    python -m linkedin_ai_agent.main --headed   # watch the browser instead of running headless
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import os

from dotenv import load_dotenv

from linkedin_ai_agent.agents import build_agent
from linkedin_ai_agent.browser_tool import build_browser, login_to_linkedin, make_browser_tool
from linkedin_ai_agent.grounding import fabricated_urls
from linkedin_ai_agent.models import Digest

VERIFICATION_KEYWORDS = ("captcha", "2fa", "one-time", "verification")


def _configure_tracing(project: str) -> None:
    """Turn on LangSmith tracing if an API key is present.

    Every model call, tool call, and subagent fanout in this run then lands
    in LangSmith as one traced session you can inspect end to end - see
    https://www.langchain.com/blog/your-coding-agents-are-a-black-box-heres-how-to-crack-them-open
    for what that view actually looks like. Tracing is opt-in: with no
    LANGSMITH_API_KEY the run just proceeds untraced.
    """
    if os.environ.get("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", project)
        print(f"LangSmith tracing enabled (project: {os.environ['LANGSMITH_PROJECT']})")
    else:
        print("LANGSMITH_API_KEY not set - running untraced. See README to enable tracing.")


async def run(topics: list[str], output_path: str, headless: bool, project: str) -> None:
    load_dotenv()
    _configure_tracing(project)

    model = os.environ.get("ORCHESTRATOR_MODEL", "gpt-5.6-terra")
    scan_model = os.environ.get("BROWSER_SCAN_MODEL", model)

    browser = build_browser(headless=headless)

    print("Logging in to LinkedIn...")
    login_report = await login_to_linkedin(browser, model)
    print(f"Login step finished: {login_report}\n")
    if any(keyword in login_report.lower() for keyword in VERIFICATION_KEYWORDS):
        print(
            "LinkedIn appears to have thrown a verification challenge. Complete "
            "it manually (rerun with --headed to see the browser), then re-run."
        )
        await browser.close()
        return

    tool = make_browser_tool(browser, scan_model)
    agent = build_agent(tool, model)

    prompt = (
        "Scan LinkedIn for recent AI posts, research, and updates on these "
        f"topics: {', '.join(topics)}. Produce the final digest."
    )

    print("Running the agent (this can take a few minutes)...")
    result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    await browser.close()

    digest: Digest = result["structured_response"]

    # Best-effort grounding check against the visible transcript. This is a
    # heuristic, not a proof - flag it, don't silently trust the digest.
    raw_notes = "\n".join(
        m.content for m in result["messages"] if isinstance(getattr(m, "content", None), str)
    )
    bad_links = fabricated_urls(digest, raw_notes)
    if bad_links:
        print(
            f"WARNING: {len(bad_links)} URL(s) in the digest were not found in "
            f"the scanned notes and may be fabricated: {bad_links}"
        )

    with open(output_path, "w") as f:
        f.write(digest.to_markdown())
    print(f"\nDigest written to {output_path} ({len(digest.posts)} posts)")


def main() -> None:
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
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window instead of running headless.",
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
