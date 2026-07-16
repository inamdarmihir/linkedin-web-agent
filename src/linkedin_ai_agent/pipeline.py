"""Shared orchestration pipeline: login, run the agent, return a digest.

This is the single source of truth for "run the LinkedIn digest workflow",
used by both the CLI (`main.py`, prints each event to stdout) and the web
backend (`server.py`, translates each event into an SSE message for the
Next.js UI). Keeping the login -> agent -> grounding-check -> digest flow in
one place means the two front ends can never drift out of sync.

`run_pipeline` is an async generator that yields `PipelineEvent`s as the run
progresses (status updates, tool start/end - including subagent dispatch,
which deepagents implements as a `task` tool call) and finishes with exactly
one terminal event: `done` (carries the validated `Digest`) or `error`.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

from dotenv import load_dotenv

from linkedin_ai_agent.agents import build_agent
from linkedin_ai_agent.browser_tool import build_browser, login_to_linkedin, make_browser_tool
from linkedin_ai_agent.grounding import fabricated_urls
from linkedin_ai_agent.models import Digest

VERIFICATION_FOLLOWUP = (
    "Complete it manually (run the CLI with --headed to see the browser), then retry."
)

PipelineEventKind = Literal["status", "tool_start", "tool_end", "done", "error"]

_PREVIEW_LIMIT = 200


@dataclass
class PipelineEvent:
    """One step of progress. `digest` is only set on a `done` event."""

    kind: PipelineEventKind
    label: str = ""
    detail: str = ""
    digest: Digest | None = None


def build_prompt(topics: list[str]) -> str:
    return (
        "Scan LinkedIn for recent AI posts, research, and updates on these "
        f"topics: {', '.join(topics)}. Produce the final digest."
    )


def configure_tracing(project: str) -> str:
    """Turn on LangSmith tracing if an API key is present. Returns a status message.

    Every model call, tool call, and subagent fanout in this run then lands
    in LangSmith as one traced session you can inspect end to end - see
    https://www.langchain.com/blog/your-coding-agents-are-a-black-box-heres-how-to-crack-them-open
    for what that view actually looks like. Tracing is opt-in: with no
    LANGSMITH_API_KEY the run just proceeds untraced.
    """
    if os.environ.get("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", project)
        return f"LangSmith tracing enabled (project: {os.environ['LANGSMITH_PROJECT']})"
    return "LANGSMITH_API_KEY not set - running untraced. See README to enable tracing."


def _preview(value: Any, limit: int = _PREVIEW_LIMIT) -> str:
    """Collapse an arbitrary tool input/output into a short one-line string."""
    if value is None:
        return ""
    content = getattr(value, "content", value)  # unwrap ToolMessage-like objects
    text = json.dumps(content, default=str) if isinstance(content, dict) else str(content)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _translate(event: dict[str, Any]) -> PipelineEvent | None:
    """Map one LangGraph `astream_events` v2 event to a `PipelineEvent`.

    Subagent dispatch (deepagents' `task` tool) and the `browse_linkedin`
    tool both surface as ordinary tool calls, so filtering on
    on_tool_start/on_tool_end covers "which subagent is running" and "what is
    it doing on LinkedIn right now" with no dependency on deepagents' internal
    graph node names.
    """
    kind = event.get("event")
    name = event.get("name", "tool")
    if kind == "on_tool_start":
        return PipelineEvent(
            kind="tool_start", label=name, detail=_preview(event.get("data", {}).get("input"))
        )
    if kind == "on_tool_end":
        return PipelineEvent(
            kind="tool_end", label=name, detail=_preview(event.get("data", {}).get("output"))
        )
    return None


async def _stream_agent(agent: Any, prompt: str) -> AsyncIterator[PipelineEvent]:
    """Drive `agent.astream_events` to completion, yielding translated
    progress and finishing with exactly one `done` (digest attached) or
    `error` event.

    Split out from `run_pipeline` so it can be exercised directly against a
    real (deepagents-built) LangGraph agent in tests, independent of the
    browser/login side of the pipeline.
    """
    root_run_id: str | None = None
    final_output: dict[str, Any] | None = None
    async for event in agent.astream_events(
        {"messages": [{"role": "user", "content": prompt}]}, version="v2"
    ):
        if root_run_id is None:
            root_run_id = event.get("run_id")
        translated = _translate(event)
        if translated is not None:
            yield translated
        if event.get("event") == "on_chain_end" and event.get("run_id") == root_run_id:
            final_output = event.get("data", {}).get("output")

    if not isinstance(final_output, dict) or "structured_response" not in final_output:
        yield PipelineEvent(kind="error", label="The agent did not return a structured digest.")
        return

    digest: Digest = final_output["structured_response"]

    # Best-effort grounding check against the visible transcript. This is a
    # heuristic, not a proof - flag it, don't silently trust the digest.
    raw_notes = "\n".join(
        m.content
        for m in final_output.get("messages", [])
        if isinstance(getattr(m, "content", None), str)
    )
    bad_links = fabricated_urls(digest, raw_notes)
    if bad_links:
        yield PipelineEvent(
            kind="status",
            label=(
                f"Warning: {len(bad_links)} URL(s) in the digest were not found "
                "in the scanned notes and may be fabricated"
            ),
            detail=", ".join(bad_links),
        )

    yield PipelineEvent(kind="done", digest=digest)


async def run_pipeline(
    topics: list[str],
    *,
    project: str = "linkedin-ai-digest",
    headless: bool = True,
) -> AsyncIterator[PipelineEvent]:
    """Log in, run the orchestrator agent, and yield progress as it happens.

    Always ends with a `done` (digest attached) or `error` event - callers
    can treat either as the signal to stop consuming.
    """
    load_dotenv()
    yield PipelineEvent(kind="status", label=configure_tracing(project))

    model = os.environ.get("ORCHESTRATOR_MODEL", "gpt-5.6-terra")
    scan_model = os.environ.get("BROWSER_SCAN_MODEL", model)

    browser = build_browser(headless=headless)

    yield PipelineEvent(kind="status", label="Logging in to LinkedIn...")
    try:
        login_success, login_report = await login_to_linkedin(browser, model)
    except Exception as exc:  # noqa: BLE001 - surface any login failure to the caller
        await browser.kill()
        yield PipelineEvent(kind="error", label="Login failed", detail=str(exc))
        return

    yield PipelineEvent(kind="status", label=f"Login step finished: {login_report}")
    if not login_success:
        await browser.kill()
        yield PipelineEvent(
            kind="error",
            label="LinkedIn login did not complete",
            detail=f"{login_report} {VERIFICATION_FOLLOWUP}",
        )
        return

    tool = make_browser_tool(browser, scan_model)
    agent = build_agent(tool, model)
    prompt = build_prompt(topics)

    yield PipelineEvent(kind="status", label="Running the agent (this can take a few minutes)...")
    try:
        async for event in _stream_agent(agent, prompt):
            yield event
    finally:
        await browser.kill()
