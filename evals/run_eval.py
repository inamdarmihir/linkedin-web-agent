"""Run the offline digest-writer eval suite against LangSmith.

    python -m evals.run_eval            # deterministic evaluators only
    python -m evals.run_eval --judge    # also run the LLM-as-judge evaluator

Requires LANGSMITH_API_KEY and OPENAI_API_KEY. Creates (or reuses) a dataset
called 'linkedin-digest-writer' and runs a scored experiment against it -
results show up in the LangSmith UI as a comparable experiment across runs,
the workflow described in
https://www.langchain.com/blog/improving-agents-is-a-data-mining-problem.

This only exercises the digest-writer subagent's prompt + schema in
isolation (no browser, no LinkedIn login, no orchestrator) so it's fast,
cheap, and safe to run in CI on every change to DIGEST_PROMPT or Digest.
"""

from __future__ import annotations

import argparse

from langchain.agents import create_agent
from langsmith import Client, evaluate

from evals.dataset import EXAMPLES
from evals.evaluators import ALL_EVALUATORS, DETERMINISTIC_EVALUATORS
from linkedin_ai_agent.agents import DIGEST_PROMPT
from linkedin_ai_agent.models import Digest

DATASET_NAME = "linkedin-digest-writer"


def _ensure_dataset(client: Client):
    try:
        return client.read_dataset(dataset_name=DATASET_NAME)
    except Exception:
        dataset = client.create_dataset(
            DATASET_NAME,
            description="Offline regression set for the digest-writer subagent.",
        )
        for example in EXAMPLES:
            client.create_example(
                inputs=example["inputs"],
                outputs=example["reference_outputs"],
                dataset_id=dataset.id,
            )
        return dataset


def target(inputs: dict) -> dict:
    """Run the digest-writer's prompt + schema in isolation."""
    writer = create_agent(
        model="openai:gpt-5.6-terra", system_prompt=DIGEST_PROMPT, response_format=Digest
    )
    result = writer.invoke({"messages": [{"role": "user", "content": inputs["raw_notes"]}]})
    return {"digest": result["structured_response"].model_dump()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judge", action="store_true", help="Include the LLM-as-judge evaluator.")
    args = parser.parse_args()

    client = Client()
    _ensure_dataset(client)
    evaluators = ALL_EVALUATORS if args.judge else DETERMINISTIC_EVALUATORS

    evaluate(
        target,
        data=DATASET_NAME,
        evaluators=evaluators,
        client=client,
        experiment_prefix="digest-writer",
        description="Offline regression eval for the digest-writer subagent.",
    )


if __name__ == "__main__":
    main()
