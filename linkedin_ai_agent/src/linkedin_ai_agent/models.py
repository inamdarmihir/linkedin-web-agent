"""Structured schemas shared across the agent, evals, and rendering layer.

The orchestrator's final output is validated against `Digest` via deepagents'
`response_format` parameter (a thin wrapper around LangChain's `create_agent`
structured-output support: https://docs.langchain.com/oss/python/langchain/structured-output).
That means the agent returns typed, validated data - not a markdown string we
hope is well-formed - and turning that data into markdown becomes a pure,
deterministic function (`Digest.to_markdown`) we can unit test without an LLM
in the loop at all. See tests/test_models.py.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["research", "product_launch", "industry_news", "commentary"]

CATEGORY_HEADINGS: dict[Category, str] = {
    "research": "Research",
    "product_launch": "Product Launches",
    "industry_news": "Industry News",
    "commentary": "Commentary & Opinion",
}


class LinkedInPost(BaseModel):
    """A single LinkedIn post surfaced by the linkedin-scanner subagent."""

    author: str = Field(description="Post author or company page name")
    title: str = Field(description="Short title or hook for the post")
    summary: str = Field(description="One-line summary of the post content")
    url: str | None = Field(default=None, description="Post URL, if visible in the browser")
    category: Category
    posted_at: str | None = Field(
        default=None, description="Approximate recency, e.g. '2 days ago'"
    )


class Digest(BaseModel):
    """The orchestrator's final structured output (response_format=Digest)."""

    top_takeaway: str = Field(
        description="2-3 sentence summary of the most important theme across all posts"
    )
    posts: list[LinkedInPost] = Field(default_factory=list)

    def by_category(self, category: Category) -> list[LinkedInPost]:
        return [p for p in self.posts if p.category == category]

    def to_markdown(self) -> str:
        """Deterministic, testable rendering - no LLM call involved."""
        lines = ["# LinkedIn AI Digest", "", "## Top takeaway", self.top_takeaway, ""]
        for category, heading in CATEGORY_HEADINGS.items():
            items = self.by_category(category)
            if not items:
                continue
            lines.append(f"## {heading}")
            for post in items:
                link = f" ([source]({post.url}))" if post.url else ""
                when = f" - {post.posted_at}" if post.posted_at else ""
                lines.append(f"- **{post.title}** ({post.author}){when}: {post.summary}{link}")
            lines.append("")
        if not self.posts:
            lines.append("_No relevant posts found this run._")
        return "\n".join(lines).strip() + "\n"
