"""FastAPI backend for the Next.js UI (`web/`).

Exposes the same `run_pipeline` workflow as the CLI, over HTTP + Server-Sent
Events so a browser can kick off a real run, watch live progress (subagent
dispatch via deepagents' `task` tool, `browse_linkedin` calls, grounding
warnings), and read the final structured digest.

This process is long-running and stateful (in-memory job store, a real
browser session per run) - run it on a persistent host (locally, a VM, a
container), never as a Vercel serverless function. See README "Web UI".

Run it directly:
    python -m linkedin_ai_agent.server
or with uvicorn's reloader:
    uvicorn linkedin_ai_agent.server:app --reload

Every run is a real LinkedIn login + LLM-driven browse, so
OPENAI_API_KEY/LINKEDIN_EMAIL/LINKEDIN_PASSWORD must be set (see
.env.example) - there is no demo/mock mode.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from linkedin_ai_agent.models import Digest
from linkedin_ai_agent.pipeline import run_pipeline

REQUIRED_ENV_VARS = ("OPENAI_API_KEY", "LINKEDIN_EMAIL", "LINKEDIN_PASSWORD")
OPTIONAL_ENV_VARS = ("LANGSMITH_API_KEY",)

ProgressEventType = Literal["status", "tool_start", "tool_end", "done", "error"]
JobStatus = Literal["queued", "running", "done", "error"]


class CreateRunRequest(BaseModel):
    topics: list[str] = Field(min_length=1)
    project: str = "linkedin-ai-digest"

    @field_validator("topics")
    @classmethod
    def _clean_topics(cls, value: list[str]) -> list[str]:
        cleaned = [t.strip() for t in value if t.strip()]
        if not cleaned:
            raise ValueError("at least one non-empty topic is required")
        return cleaned


class ProgressEventOut(BaseModel):
    id: int
    ts: str
    type: ProgressEventType
    label: str = ""
    detail: str = ""
    result: Digest | None = None


@dataclass
class Job:
    id: str
    topics: list[str]
    project: str
    status: JobStatus = "queued"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    events: list[ProgressEventOut] = field(default_factory=list)
    result: Digest | None = None
    error: str | None = None
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    _next_id: int = field(default=0, init=False, repr=False)

    def emit(
        self,
        kind: ProgressEventType,
        label: str = "",
        detail: str = "",
        result: Digest | None = None,
    ) -> ProgressEventOut:
        pe = ProgressEventOut(
            id=self._next_id,
            ts=datetime.now(UTC).isoformat(),
            type=kind,
            label=label,
            detail=detail,
            result=result,
        )
        self._next_id += 1
        self.events.append(pe)
        # No `await` between a caller's decision to emit and this fan-out, so
        # a concurrently-subscribing SSE stream can never see a duplicate or
        # miss this event - see _event_stream.
        for q in self.subscribers:
            q.put_nowait(pe)
        return pe


JOBS: dict[str, Job] = {}


async def _run_job(job: Job) -> None:
    job.status = "running"
    try:
        async for event in run_pipeline(job.topics, project=job.project, headless=True):
            if event.kind == "done":
                job.status = "done"
                job.result = event.digest
                job.emit("done", result=event.digest)
                return
            if event.kind == "error":
                job.status = "error"
                job.error = event.label
                job.emit("error", label=event.label, detail=event.detail)
                return
            job.emit(event.kind, label=event.label, detail=event.detail)
        job.status = "error"
        job.error = "Pipeline ended without a result."
        job.emit("error", label=job.error)
    except Exception as exc:  # noqa: BLE001 - report any unexpected failure to the UI
        job.status = "error"
        job.error = str(exc)
        job.emit("error", label="Unexpected error", detail=str(exc))
    finally:
        for q in job.subscribers:
            q.put_nowait(None)  # wake any open SSE streams so they can close


def _env_status() -> dict[str, bool]:
    return {name: bool(os.environ.get(name)) for name in (*REQUIRED_ENV_VARS, *OPTIONAL_ENV_VARS)}


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(title="linkedin-ai-agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    env = _env_status()
    missing = [name for name in REQUIRED_ENV_VARS if not env[name]]
    return {"ok": True, "env": env, "env_ok": not missing}


@app.post("/api/runs", status_code=201)
async def create_run(req: CreateRunRequest) -> dict:
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise HTTPException(
            status_code=503,
            detail=f"Missing required environment variable(s): {', '.join(missing)}",
        )
    job = Job(id=str(uuid.uuid4()), topics=req.topics, project=req.project)
    JOBS[job.id] = job
    asyncio.create_task(_run_job(job))
    return {"id": job.id, "status": job.status, "topics": job.topics, "created_at": job.created_at}


def _get_job(job_id: str) -> Job:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return job


@app.get("/api/runs/{job_id}")
def get_run(job_id: str) -> dict:
    job = _get_job(job_id)
    return {
        "id": job.id,
        "status": job.status,
        "topics": job.topics,
        "created_at": job.created_at,
        "events": [e.model_dump() for e in job.events],
        "result": job.result.model_dump() if job.result else None,
        "error": job.error,
    }


def _sse_line(event: ProgressEventOut) -> str:
    return f"data: {event.model_dump_json()}\n\n"


async def _event_stream(job: Job) -> AsyncIterator[str]:
    q: asyncio.Queue = asyncio.Queue()
    job.subscribers.append(q)
    snapshot = list(job.events)  # no `await` above - atomic w.r.t. Job.emit, see there
    already_done = job.status in ("done", "error")
    try:
        for pe in snapshot:
            yield _sse_line(pe)
        if already_done:
            return
        while True:
            item = await q.get()
            if item is None:
                break
            yield _sse_line(item)
    finally:
        if q in job.subscribers:
            job.subscribers.remove(q)


@app.get("/api/runs/{job_id}/events")
async def stream_run(job_id: str) -> StreamingResponse:
    job = _get_job(job_id)
    return StreamingResponse(
        _event_stream(job),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/runs/{job_id}/markdown")
def get_markdown(job_id: str) -> PlainTextResponse:
    job = _get_job(job_id)
    if job.status != "done" or job.result is None:
        raise HTTPException(status_code=409, detail=f"Run is {job.status}, not done yet")
    return PlainTextResponse(job.result.to_markdown(), media_type="text/markdown")


def main() -> None:
    import uvicorn

    uvicorn.run(
        "linkedin_ai_agent.server:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=os.environ.get("RELOAD", "").strip().lower() in ("1", "true", "yes"),
    )


if __name__ == "__main__":
    main()
