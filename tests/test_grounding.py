from linkedin_ai_agent.grounding import fabricated_urls
from linkedin_ai_agent.models import Digest, LinkedInPost


def test_flags_url_not_present_in_notes():
    notes = "Jane posted about X. Link: https://linkedin.com/posts/real-1"
    digest = Digest(
        top_takeaway="x",
        posts=[
            LinkedInPost(
                author="Jane",
                title="T",
                summary="S",
                category="research",
                url="https://linkedin.com/posts/real-1",
            ),
            LinkedInPost(
                author="Bob",
                title="T2",
                summary="S2",
                category="research",
                url="https://linkedin.com/posts/fake-2",
            ),
        ],
    )
    assert fabricated_urls(digest, notes) == ["https://linkedin.com/posts/fake-2"]


def test_no_urls_means_nothing_flagged():
    digest = Digest(
        top_takeaway="x",
        posts=[LinkedInPost(author="A", title="T", summary="S", category="commentary")],
    )
    assert fabricated_urls(digest, "irrelevant notes") == []


def test_all_urls_grounded_returns_empty_list():
    notes = "post one: https://a.com/1\npost two: https://a.com/2"
    digest = Digest(
        top_takeaway="x",
        posts=[
            LinkedInPost(author="A", title="T1", summary="S1", category="research", url="https://a.com/1"),
            LinkedInPost(author="B", title="T2", summary="S2", category="research", url="https://a.com/2"),
        ],
    )
    assert fabricated_urls(digest, notes) == []
