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


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps(INFO).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
