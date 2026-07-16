"""Fixtures for the offline digest-writer eval.

Each example is a fixed blob of "raw scanner notes", as if already collected
from LinkedIn - no live browser or LinkedIn login involved. That's a
deliberate split: the digest-writer subagent's job (organize notes into a
grounded, structured Digest) is deterministic enough to regression-test in
CI on every commit; the scanner's job (drive a real browser against a live,
bot-hostile site) is not, and is left to manual/occasional runs (see the
README's "Evals" section).
"""

EXAMPLES: list[dict] = [
    {
        "inputs": {
            "raw_notes": (
                "Topic: AI research\n"
                "- Jane Doe (Stanford AI Lab): posted about a new benchmark for "
                "long-context reasoning called 'LongBench-3'. "
                "Link: https://linkedin.com/posts/janedoe_longbench3-activity-1111\n"
                "- Acme AI (company page): announced general availability of "
                "their new coding model, 'AcmeCode 2'. "
                "Link: https://linkedin.com/posts/acmeai_acmecode2-activity-2222\n"
                "- Random User: 'Hiring backend engineers, DM me!' (not "
                "AI-related, skip)\n"
            )
        },
        "reference_outputs": {
            "min_posts": 2,
            "expected_categories": ["research", "product_launch"],
        },
    },
    {
        "inputs": {
            "raw_notes": (
                "Topic: AI product launches\n"
                "No relevant posts found for this topic in the last 7 days.\n"
            )
        },
        "reference_outputs": {"min_posts": 0, "expected_categories": []},
    },
    {
        "inputs": {
            "raw_notes": (
                "Topic: AI industry news\n"
                "- TechCrunch (company page): reported that a major cloud "
                "provider is cutting GPU prices by 20%. "
                "Link: https://linkedin.com/posts/techcrunch_gpu-pricing-activity-3333\n"
                "- TechCrunch (company page, duplicate share of the same post "
                "by another user): same GPU pricing story, no new link given.\n"
                "- Sam Analyst: 'Hot take: everyone is overbuilding data "
                "centers.' (opinion piece, no link)\n"
            )
        },
        "reference_outputs": {
            "min_posts": 1,
            "expected_categories": ["industry_news"],
        },
    },
]
