"""
deepagents orchestration: a main agent that delegates to two subagents and
returns a validated `Digest` (see models.py) via `response_format`.

  - linkedin-scanner: has the browse_linkedin tool, does the actual browsing
    and note-taking on LinkedIn (one call per topic/hashtag, isolated context
    so raw browsing noise never bloats the main thread).
  - digest-writer: pure-reasoning subagent that organizes the combined raw
    notes from every scan into the categories the Digest schema expects.

The main agent's job is to fan out scan requests, hand the combined notes to
the digest writer, and return a Digest as its structured final output.
"""

from __future__ import annotations

import os

from deepagents import create_deep_agent

from linkedin_ai_agent.models import Digest

ORCHESTRATOR_PROMPT = (
    "You are the orchestrator for an 'AI news from LinkedIn' digest workflow.\n\n"
    "Given a list of topics:\n"
    "1. Call the linkedin-scanner subagent once per topic (you may launch "
    "several calls in the same turn to run them in parallel). Ask each call "
    "to search that specific topic/hashtag and return structured notes "
    "(author, title, one-line summary, URL if visible, category, and "
    "approximate date).\n"
    "2. Once you have notes back from every topic, pass the FULL combined set "
    "of notes to the digest-writer subagent and ask it to organize them.\n"
    "3. Your final answer must conform to the Digest schema: a short "
    "top_takeaway plus the full list of posts. NEVER invent a URL, author, or "
    "post that wasn't present in a subagent's notes - if a field is unknown, "
    "omit it rather than guessing."
)

SCANNER_PROMPT = (
    "You are a LinkedIn research scout. You have one tool, browse_linkedin, "
    "which drives a real, already-authenticated browser session on "
    "linkedin.com. Use LinkedIn's search bar and hashtag pages (e.g. #AI, "
    "#MachineLearning, #LLM, #GenerativeAI) plus the home feed to find posts "
    "from roughly the last 7 days about AI/ML research, product launches, or "
    "notable industry news. Skip ads, job postings, and generic engagement-"
    "bait posts.\n\n"
    "For every relevant post capture: author, a one-line summary of the "
    "content, the post URL if visible, and an approximate date/recency. "
    "Return a compact structured list (not prose paragraphs). If a search "
    "turns up nothing relevant, say so plainly rather than padding the list."
)

DIGEST_PROMPT = (
    "You turn raw LinkedIn research notes into an organized set of posts, "
    "each tagged with a category: research, product_launch, industry_news, "
    "or commentary. Deduplicate near-identical posts. Write a 2-3 sentence "
    "top-level takeaway about the most important theme across all notes. "
    "Never invent links, authors, or facts that are not present in the notes "
    "you were given - grounding matters more than completeness."
)


def build_agent(browser_tool, model: str | None = None):
    """Assemble the deepagents orchestrator with its two subagents.

    Model routing: the scanner subagent runs many cheap, high-volume browsing
    steps, while the orchestrator/digest-writer make a small number of
    higher-value reasoning calls. LangChain's own cost-governance guidance
    (https://www.langchain.com/blog/fix-your-coding-agent-bill) is to match
    model tier to task value rather than defaulting to one model everywhere -
    so the scanner's model is independently configurable via
    `BROWSER_SCAN_MODEL`, falling back to the orchestrator's model if unset.
    """
    model = model or os.environ.get("ORCHESTRATOR_MODEL", "gpt-5.6-terra")
    scan_model = os.environ.get("BROWSER_SCAN_MODEL", model)

    scanner_subagent = {
        "name": "linkedin-scanner",
        "description": (
            "Uses a live browser session to search and read LinkedIn for "
            "AI-related posts, research, and updates. Delegate to this agent "
            "for any task that requires fresh information gathered from "
            "LinkedIn itself."
        ),
        "system_prompt": SCANNER_PROMPT,
        "tools": [browser_tool],
        "model": f"openai:{scan_model}",
    }

    digest_subagent = {
        "name": "digest-writer",
        "description": (
            "Turns raw scanned LinkedIn notes into an organized, deduplicated "
            "set of categorized posts. Delegate to this agent once all "
            "scanning is done."
        ),
        "system_prompt": DIGEST_PROMPT,
        "tools": [],
    }

    return create_deep_agent(
        model=f"openai:{model}",
        subagents=[scanner_subagent, digest_subagent],
        system_prompt=ORCHESTRATOR_PROMPT,
        response_format=Digest,
    )
