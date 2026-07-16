"""
Vercel Python entrypoint.

This project is a CLI agent (see `src/linkedin_ai_agent/main.py`) that drives
a real browser session to scan LinkedIn and is not meant to run as a
serverless function - long-lived browser automation and interactive
LinkedIn login don't fit the serverless request/response model. This file
exists solely so Vercel's Python builder has a discoverable entrypoint
(`api/index.py`) and the build succeeds; it serves a small informational
response pointing back to the README for actual usage.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler

INFO = {
    "name": "linkedin-ai-agent",
    "description": (
        "A deepagents orchestrator that scans LinkedIn for AI news via "
        "Browser Use and produces a structured, evaluated digest."
    ),
    "usage": "Run locally as a CLI: python -m linkedin_ai_agent.main",
    "docs": "See README.md for setup and usage instructions.",
}

# Env vars the CLI needs at runtime. Never echoed back - only whether each is
# set, so this endpoint is safe to hit without leaking secrets, and doubles
# as a quick "did I configure Vercel's env vars correctly" check.
REQUIRED_ENV_VARS = ("OPENAI_API_KEY", "LINKEDIN_EMAIL", "LINKEDIN_PASSWORD")
OPTIONAL_ENV_VARS = ("LANGSMITH_API_KEY", "ORCHESTRATOR_MODEL", "BROWSER_SCAN_MODEL")


def _env_status() -> dict[str, bool]:
    return {name: bool(os.environ.get(name)) for name in (*REQUIRED_ENV_VARS, *OPTIONAL_ENV_VARS)}


# Vercel's Python runtime requires the exported class to be named exactly
# `handler` (lowercase) - this is a platform convention, not a style choice.
class handler(BaseHTTPRequestHandler):  # noqa: N801
    def do_GET(self) -> None:
        env_status = _env_status()
        missing_required = [name for name in REQUIRED_ENV_VARS if not env_status[name]]
        payload = {
            **INFO,
            "env": env_status,
            "env_ok": not missing_required,
            **({"env_missing": missing_required} if missing_required else {}),
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
