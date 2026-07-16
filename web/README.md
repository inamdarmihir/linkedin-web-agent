# LinkedIn AI Digest — Web UI

A single-page Next.js (App Router, TypeScript, Tailwind CSS) frontend for the
LinkedIn AI Digest FastAPI backend. It lets you kick off a scan for AI-related
LinkedIn posts on a set of topics, watch live progress over Server-Sent
Events, and view/download the resulting categorized digest.

This app is a **frontend only** — it does not run or embed the backend.

## Prerequisites

- Node.js 18.18+ (Node 20+ recommended)
- The FastAPI backend running separately (see below)

## Install

```bash
npm install
```

## Configure

Copy the example env file and adjust if your backend isn't on the default
port:

```bash
cp .env.example .env.local
```

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

If unset, the app falls back to `http://localhost:8000` at build/runtime.

## Run the backend

From the repository root (not this `web/` directory), in a separate
terminal, with `OPENAI_API_KEY`, `LINKEDIN_EMAIL`, and `LINKEDIN_PASSWORD`
set (see the root `.env.example`):

```bash
uvicorn linkedin_ai_agent.server:app --reload
```

Every run drives a real LinkedIn login and a real LLM - there is no demo
mode. The UI reads the backend's `/api/health` endpoint on load and shows a
warning if required environment variables are missing on the backend.

## Run the dev server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Build

```bash
npm run build
npm run start
```
