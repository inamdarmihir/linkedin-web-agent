"""Grounding check: verify every URL in a `Digest` actually appeared in the
raw notes it was supposedly built from.

This is a cheap, deterministic proxy for "did the model hallucinate a
source?" - the same instinct behind the trace-mining approach LangChain
describes in "Improving Agents is a Data Mining Problem"
(https://www.langchain.com/blog/improving-agents-is-a-data-mining-problem):
turn a failure mode you care about into a signal you can check automatically,
then use it both as a regression eval (evals/evaluators.py) and as a runtime
guardrail (main.py logs a warning if this fires).

It's intentionally a heuristic (substring match against the visible
transcript), not a proof of non-hallucination - flag it, don't silently trust it.
"""

from __future__ import annotations

from linkedin_ai_agent.models import Digest


def fabricated_urls(digest: Digest, raw_notes: str) -> list[str]:
    """Return every post URL in `digest` that does not appear verbatim in `raw_notes`."""
    return [post.url for post in digest.posts if post.url and post.url not in raw_notes]
