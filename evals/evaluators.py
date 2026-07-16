"""Evaluators for the digest-writer subagent, run offline against the
fixtures in dataset.py. Two kinds, matching how the LangChain team frames
evals - as regression tests / hill-climbing signal, not just a report card
(https://www.langchain.com/blog/improving-agents-is-a-data-mining-problem):

  - Deterministic checks (schema validity, grounding, minimum coverage) -
    cheap, exact, catch regressions immediately, safe to run in CI.
  - An LLM-as-judge check for the softer "is this actually a good digest"
    quality dimension - useful signal, but noisier and not run in CI.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from langsmith.schemas import Example, Run

from linkedin_ai_agent.grounding import fabricated_urls
from linkedin_ai_agent.models import Digest


def _digest_from_run(run: Run) -> Digest | None:
    output = (run.outputs or {}).get("digest")
    if not output:
        return None
    return Digest.model_validate(output)


def schema_validity(run: Run, example: Example) -> dict:
    """Does the target function's output actually parse as a Digest?"""
    try:
        ok = _digest_from_run(run) is not None
    except Exception:
        ok = False
    return {"key": "schema_validity", "score": 1.0 if ok else 0.0}


def no_fabricated_links(run: Run, example: Example) -> dict:
    """Every URL in the digest must appear verbatim in the source notes."""
    digest = _digest_from_run(run)
    if digest is None:
        return {"key": "no_fabricated_links", "score": 0.0, "comment": "no valid output"}
    bad = fabricated_urls(digest, example.inputs["raw_notes"])
    return {
        "key": "no_fabricated_links",
        "score": 0.0 if bad else 1.0,
        "comment": f"fabricated: {bad}" if bad else "ok",
    }


def meets_minimum_coverage(run: Run, example: Example) -> dict:
    """Did the digest capture at least as many posts as expected?"""
    digest = _digest_from_run(run)
    if digest is None:
        return {"key": "meets_minimum_coverage", "score": 0.0}
    min_posts = example.outputs.get("min_posts", 0) if example.outputs else 0
    ok = len(digest.posts) >= min_posts
    return {"key": "meets_minimum_coverage", "score": 1.0 if ok else 0.0}


_JUDGE_PROMPT = (
    "You are grading a LinkedIn AI digest for quality. Score 1-5 on whether "
    "it is well-organized, non-repetitive, and contains only claims grounded "
    "in the source notes below. Respond with only a single integer 1-5.\n\n"
    "SOURCE NOTES:\n{notes}\n\nDIGEST:\n{digest}"
)


def llm_judge_quality(run: Run, example: Example) -> dict:
    """Soft quality signal via LLM-as-judge. Not run in CI (costs tokens,
    non-deterministic) - intended for manual/periodic eval runs."""
    digest = _digest_from_run(run)
    if digest is None:
        return {"key": "llm_judge_quality", "score": 0.0}
    judge = ChatOpenAI(model="gpt-5.6-terra", temperature=0)
    prompt = _JUDGE_PROMPT.format(notes=example.inputs["raw_notes"], digest=digest.to_markdown())
    response = judge.invoke(prompt)
    digits = "".join(c for c in str(response.content) if c.isdigit())
    score = int(digits[0]) if digits else 0
    return {"key": "llm_judge_quality", "score": score / 5}


DETERMINISTIC_EVALUATORS = [schema_validity, no_fabricated_links, meets_minimum_coverage]
ALL_EVALUATORS = [*DETERMINISTIC_EVALUATORS, llm_judge_quality]
