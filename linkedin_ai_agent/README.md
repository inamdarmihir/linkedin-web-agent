# LinkedIn AI Digest Agent

A [`deepagents`](https://github.com/langchain-ai/deepagents) orchestrator that
scans LinkedIn for AI news via [Browser Use](https://docs.browser-use.com),
and returns a validated, structured digest.

```
                          ┌─────────────────────┐
   topics ───────────────▶│  orchestrator agent  │──▶ Digest (Pydantic,
                          │  (gpt-5.6-terra)     │    response_format)
                          └──────────┬───────────┘         │
                     task tool fan-out (parallel)           ▼
              ┌───────────────┴───────────────┐    digest.to_markdown()
              ▼                                ▼            │
   ┌────────────────────┐          ┌────────────────────┐   ▼
   │  linkedin-scanner   │          │   digest-writer     │  *.md file
   │  (1 per topic)      │          │  (organizes notes    │
   │  tool: browse_      │─notes───▶│   into categories)   │
   │  linkedin (Browser  │          └────────────────────┘
   │  Use, live session) │
   └────────────────────┘
```

## Setup

```bash
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env   # fill in OPENAI_API_KEY, LINKEDIN_EMAIL, LINKEDIN_PASSWORD
```

## Run

```bash
python -m linkedin_ai_agent.main
python -m linkedin_ai_agent.main --topics "LLM research" "AI agents" "AI funding" --output today.md
python -m linkedin_ai_agent.main --headed   # watch the browser window instead of headless
```

Output is a single markdown file (default `linkedin_ai_digest_<date>.md`).

## Engineering notes

A few choices worth calling out, each tied to something concrete rather than
generic best-practice box-checking:

**Structured output, not markdown-shaped hope.** The orchestrator's final
answer is validated against a `Digest` Pydantic schema via `response_format`
(LangChain's [structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
support). Markdown rendering (`Digest.to_markdown`) is then a pure function
with no LLM in the loop, which is what makes it unit-testable
(`tests/test_models.py`) without mocking an API.

**Evals as regression tests, not a one-time report card.** `evals/` contains
an offline eval suite for the digest-writer subagent - fixed "raw notes" ->
does the output parse, is every URL grounded in the source notes, does it hit
minimum coverage, and (optionally) an LLM-as-judge quality score. This
follows the framing in LangChain's
["Improving Agents is a Data Mining Problem"](https://www.langchain.com/blog/improving-agents-is-a-data-mining-problem):
evals are training data for the harness, and a concrete failure mode (a
fabricated source link) becomes a checkable signal, not just a vibe. It's
split from the live browser pipeline deliberately - see "Evals" below.

**Observability.** Set `LANGSMITH_API_KEY` and every model call, tool call,
and subagent fanout in a run lands in LangSmith as one inspectable trace -
which subagent handled which topic, what the scanner actually read on
LinkedIn, token/cost per step, retries. This is the same "you can't debug
what you can't see" argument LangChain makes in
["Your coding agents are a black box"](https://www.langchain.com/blog/your-coding-agents-are-a-black-box-heres-how-to-crack-them-open),
applied to a research agent instead of a coding agent.

**Model-task fit over one-size-fits-all.** The scanner subagent makes many
cheap, high-volume tool calls (browsing loop steps); the orchestrator and
digest-writer make a handful of higher-value reasoning calls. `BROWSER_SCAN_MODEL`
lets you route the scanner to a cheaper tier independently of the
orchestrator's model, in the spirit of LangChain's cost-governance post
["Your coding agent bill doubled"](https://www.langchain.com/blog/fix-your-coding-agent-bill) -
don't pay frontier-reasoning prices for a tool-calling loop.

**Credential handling.** Login uses browser-use's `sensitive_data`
mechanism: the LLM only ever sees placeholder names (`li_email` /
`li_password`); the real values are substituted directly into the DOM and
never appear in a prompt, a trace, or a log line. If LinkedIn throws a
CAPTCHA or 2FA prompt, the agent is instructed to stop and report it rather
than guess - see `browser_tool.login_to_linkedin`.

**Resilience.** `browse_linkedin` retries once with exponential backoff on
transient failures (slow loads, crashed frames) via `tenacity` - browser
automation fails in different ways than API calls do, and a single flaky step
shouldn't sink an entire scan.

## Evals

```bash
python -m evals.run_eval            # deterministic evaluators (schema, grounding, coverage)
python -m evals.run_eval --judge    # + LLM-as-judge quality score
```

This evaluates the **digest-writer subagent in isolation** against fixed
"raw notes" fixtures - no live browser, no LinkedIn login, no orchestrator.
That split is intentional:

- The digest-writer's job (turn notes into a grounded, structured `Digest`)
  is deterministic enough to regression-test on every change to
  `DIGEST_PROMPT` or the `Digest` schema, so it's cheap and safe to run in CI.
- The scanner's job (drive a real browser against a live, bot-detecting site)
  isn't something you want firing on every commit - see the ToS note below.
  Exercise it manually, or wire the (disabled-by-default) `eval` job in
  `.github/workflows/ci.yml` into a scheduled run if you want periodic
  end-to-end coverage.

## A note on LinkedIn's Terms of Service

Automated scraping/browsing of LinkedIn with a bot is against their Terms of
Service, and they actively rate-limit and flag accounts that do this. This
script authenticates as *you* and browses conservatively (a handful of
searches per run), but running it frequently or at volume risks a CAPTCHA
challenge or a temporary/permanent restriction on the account. Treat it as a
personal research aid you run occasionally, not something to put on an
aggressive schedule.

## Project layout

```
src/linkedin_ai_agent/
  models.py        Digest / LinkedInPost Pydantic schemas + markdown rendering
  grounding.py      shared fabricated-link check (runtime guardrail + eval)
  browser_tool.py   persistent Browser session, LinkedIn login, retrying tool
  agents.py         deepagents orchestrator + subagent prompts, model routing
  main.py           CLI entry point, tracing setup
evals/
  dataset.py        offline "raw notes" fixtures
  evaluators.py      schema / grounding / coverage / LLM-judge evaluators
  run_eval.py        LangSmith eval harness entry point
tests/               offline unit tests (no network, no API keys)
.github/workflows/   CI: lint + unit tests on every push/PR
```
