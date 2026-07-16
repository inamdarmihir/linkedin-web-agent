"""Tests for the FastAPI backend's HTTP/job-orchestration layer.

Most of these need no test double at all - request validation, the
missing-credentials guard, and 404 handling are exercised for real. Only
`test_job_lifecycle_and_sse_stream` swaps out `run_pipeline` (a real login +
LLM-driven browser run that takes minutes and needs live credentials) for a
two-event generator defined inline in the test, purely to check the job
store/SSE plumbing around it - not a feature reachable by any real request.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from linkedin_ai_agent.models import Digest, LinkedInPost
from linkedin_ai_agent.pipeline import PipelineEvent
from linkedin_ai_agent.server import JOBS, app

TOPICS = ["AI agents"]


@pytest.fixture(autouse=True)
def _clear_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("OPENAI_API_KEY", "LINKEDIN_EMAIL", "LINKEDIN_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


def test_health_reports_missing_credentials() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "ok": True,
        "env_ok": False,
        "env": {
            "OPENAI_API_KEY": False,
            "LINKEDIN_EMAIL": False,
            "LINKEDIN_PASSWORD": False,
            "LANGSMITH_API_KEY": False,
        },
    }


def test_create_run_rejects_empty_topics() -> None:
    with TestClient(app) as client:
        assert client.post("/api/runs", json={"topics": []}).status_code == 422
        assert client.post("/api/runs", json={"topics": ["   ", ""]}).status_code == 422


def test_create_run_requires_credentials() -> None:
    with TestClient(app) as client:
        resp = client.post("/api/runs", json={"topics": TOPICS})
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert "OPENAI_API_KEY" in detail
    assert "LINKEDIN_EMAIL" in detail
    assert "LINKEDIN_PASSWORD" in detail


def test_unknown_job_returns_404() -> None:
    with TestClient(app) as client:
        assert client.get("/api/runs/does-not-exist").status_code == 404
        assert client.get("/api/runs/does-not-exist/markdown").status_code == 404


def test_job_lifecycle_and_sse_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """Job creation, status transitions, event replay, and the markdown
    export - driven by a trivial in-test stand-in for the real pipeline so
    the test runs in milliseconds instead of minutes against a live browser.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LINKEDIN_EMAIL", "test@example.com")
    monkeypatch.setenv("LINKEDIN_PASSWORD", "test-password")

    async def fake_run_pipeline(topics, *, project, headless):
        yield PipelineEvent(kind="status", label="Logging in to LinkedIn...")
        yield PipelineEvent(kind="tool_start", label="browse_linkedin", detail=topics[0])
        yield PipelineEvent(kind="tool_end", label="browse_linkedin", detail="done")
        digest = Digest(
            top_takeaway=f"Digest for {topics[0]}",
            posts=[
                LinkedInPost(
                    author="Jane",
                    title="T",
                    summary="S",
                    url="https://linkedin.com/posts/1",
                    category="research",
                )
            ],
        )
        yield PipelineEvent(kind="done", digest=digest)

    monkeypatch.setattr("linkedin_ai_agent.server.run_pipeline", fake_run_pipeline)

    with TestClient(app) as client:
        created = client.post("/api/runs", json={"topics": TOPICS})
        assert created.status_code == 201
        job_id = created.json()["id"]
        assert created.json()["status"] == "queued"

        deadline = time.monotonic() + 5
        final = None
        while time.monotonic() < deadline:
            final = client.get(f"/api/runs/{job_id}").json()
            if final["status"] in ("done", "error"):
                break
            time.sleep(0.02)
        assert final is not None and final["status"] == "done", final

        assert final["result"]["top_takeaway"] == f"Digest for {TOPICS[0]}"
        kinds = [e["type"] for e in final["events"]]
        assert kinds == ["status", "tool_start", "tool_end", "done"]

        md = client.get(f"/api/runs/{job_id}/markdown")
        assert md.status_code == 200
        assert "# LinkedIn AI Digest" in md.text

        with client.stream("GET", f"/api/runs/{job_id}/events") as resp:
            assert resp.headers["content-type"].startswith("text/event-stream")
            events = [
                json.loads(line[len("data: ") :])
                for line in resp.iter_lines()
                if line.startswith("data: ")
            ]
        assert events[-1]["type"] == "done"

    JOBS.pop(job_id, None)
