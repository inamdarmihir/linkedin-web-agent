from linkedin_ai_agent.models import Digest, LinkedInPost


def test_to_markdown_includes_only_nonempty_sections():
    digest = Digest(
        top_takeaway="AI research is moving fast.",
        posts=[
            LinkedInPost(
                author="Jane", title="LongBench-3", summary="new benchmark", category="research"
            ),
        ],
    )
    md = digest.to_markdown()
    assert "## Research" in md
    assert "## Product Launches" not in md
    assert "LongBench-3" in md


def test_url_renders_as_markdown_link():
    digest = Digest(
        top_takeaway="x",
        posts=[
            LinkedInPost(
                author="A",
                title="T",
                summary="S",
                category="commentary",
                url="https://example.com/p",
            )
        ],
    )
    assert "[source](https://example.com/p)" in digest.to_markdown()


def test_empty_digest_still_renders_without_error():
    digest = Digest(top_takeaway="Quiet week, nothing notable.", posts=[])
    md = digest.to_markdown()
    assert "Quiet week" in md
    assert "No relevant posts found" in md


def test_by_category_filters_correctly():
    digest = Digest(
        top_takeaway="x",
        posts=[
            LinkedInPost(author="A", title="T1", summary="S1", category="research"),
            LinkedInPost(author="B", title="T2", summary="S2", category="commentary"),
        ],
    )
    assert len(digest.by_category("research")) == 1
    assert digest.by_category("research")[0].title == "T1"
