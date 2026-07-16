"""
Browser-Use integration layer.

Responsibilities:
  1. Own a single, persistent `Browser` session so the LinkedIn login (cookies)
     survives across every subsequent browsing task in the run.
  2. Log in to LinkedIn once, using browser-use's `sensitive_data` mechanism so
     the raw email/password are substituted at the DOM level and never appear
     in the text sent to the LLM (see
     docs.browser-use.com/examples/templates/sensitive-data).
  3. Expose a single `browse_linkedin(task: str)` tool function that deepagents
     subagents can call to run an arbitrary natural-language browsing task
     against that same session, wrapped with a short exponential-backoff
     retry - browser automation is inherently flaky (slow loads, transient DOM
     changes), so one bad step shouldn't fail the whole scan.

Login is intentionally conservative: if LinkedIn throws a CAPTCHA, OTP/2FA
challenge, or any other verification step, the agent is instructed to stop
and report it rather than try to guess or bypass it. Handle those manually
(or pre-authenticate the profile) if they come up.
"""

from __future__ import annotations

import os

from browser_use import Agent, Browser, ChatOpenAI
from browser_use.agent.views import AgentHistoryList
from tenacity import retry, stop_after_attempt, wait_exponential

LINKEDIN_ALLOWED_DOMAINS = ["*.linkedin.com"]


def build_browser(headless: bool = True) -> Browser:
    """Create the single Browser session shared by login + every scan task."""
    return Browser(
        headless=headless,
        keep_alive=True,
        allowed_domains=LINKEDIN_ALLOWED_DOMAINS,
    )


def _extract_result(history: AgentHistoryList, *, fallback: str) -> str:
    """Text report from a finished agent run - `final_result()` can return
    `None` (e.g. the agent never reached a `done` action), so this never
    silently returns the literal string "None" to a caller.
    """
    return history.final_result() or fallback


async def login_to_linkedin(browser: Browser, model: str) -> tuple[bool, str]:
    """Log in to LinkedIn using credentials from the environment.

    Credentials are passed via `sensitive_data`, so the LLM only ever sees the
    placeholder names ('li_email' / 'li_password'), never the real values -
    those are substituted directly into the DOM.

    Returns `(success, report)`. `success` is the agent's own judgement (the
    `success` flag on its final `done` action) rather than a keyword search
    over the report text - the report can legitimately *mention* "CAPTCHA" or
    "2FA" while explicitly saying neither appeared, which plain substring
    matching can't tell apart from an actual challenge.
    """
    try:
        email = os.environ["LINKEDIN_EMAIL"]
        password = os.environ["LINKEDIN_PASSWORD"]
    except KeyError as exc:
        raise RuntimeError(
            f"{exc.args[0]} is not set. Copy .env.example to .env and fill in "
            "LINKEDIN_EMAIL / LINKEDIN_PASSWORD before running."
        ) from exc

    sensitive_data = {
        "https://*.linkedin.com": {"li_email": email, "li_password": password}
    }

    task = (
        "Go to https://www.linkedin.com/login. Enter li_email into the email "
        "field and li_password into the password field, then click the sign in "
        "button. If LinkedIn shows a CAPTCHA, a 2FA/one-time-code prompt, or any "
        "other identity verification step, DO NOT attempt to solve or bypass it "
        "- immediately stop, mark the task as not successful, and report exactly "
        "what challenge appeared so a human can complete it. Otherwise, confirm "
        "you have reached the LinkedIn feed, mark the task as successful, and "
        "report success."
    )

    agent = Agent(
        task=task,
        llm=ChatOpenAI(model=model),
        browser=browser,
        sensitive_data=sensitive_data,
        allowed_domains=LINKEDIN_ALLOWED_DOMAINS,
        use_vision=False,  # avoid the LLM seeing credentials in screenshots
    )
    history = await agent.run()
    report = _extract_result(history, fallback="Login agent finished without a final report.")
    return bool(history.is_successful()), report


def make_browser_tool(browser: Browser, model: str):
    """Return a `browse_linkedin` tool function bound to the shared session."""

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=2, min=2, max=10),
    )
    async def _run_browser_task(task: str) -> str:
        agent = Agent(
            task=task,
            llm=ChatOpenAI(model=model),
            browser=browser,
            allowed_domains=LINKEDIN_ALLOWED_DOMAINS,
        )
        history = await agent.run()
        return _extract_result(history, fallback="No result reported for this task.")

    async def browse_linkedin(task: str) -> str:
        """Run a browser agent against the already-authenticated LinkedIn
        session to complete a research task and return a text report.

        Use this for anything that requires visiting linkedin.com: searching
        hashtags, reading the feed, opening a post, or extracting post details.
        Pass a specific, detailed instruction, including exactly what
        information (author, summary, URL, date) should come back. Retries
        once with backoff on transient failures (timeouts, crashed frames);
        it does not retry on login/verification stops.
        """
        return await _run_browser_task(task)

    return browse_linkedin
