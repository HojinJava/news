"""tests/test_verifier_a.py — Tests for Verifier-A."""
from agents.verifier_a import extract_claims
from models.schema import RawArticle


def _make_article(id, title, source="Reuters"):
    return RawArticle(
        id=id, title=title, title_ko=title, source=source,
        url=f"https://example.com/{id}", published_date="2026-03-28T08:00:00Z",
        summary="", summary_ko="", search_keyword="test"
    )


def test_extract_claims_returns_claims_report():
    articles = [
        _make_article("art-001", "US strikes Iran nuclear facility"),
        _make_article("art-002", "US strikes Iran nuclear facility", "AP"),
        _make_article("art-003", "Yemen Houthis fire missiles at Israel"),
    ]
    report = extract_claims(articles)
    assert "clusters" in report
    assert "claims" in report
    assert len(report["clusters"]) >= 2


def test_extract_claims_groups_similar_titles():
    articles = [
        _make_article("art-001", "US and Israel strike Iran missile sites"),
        _make_article("art-002", "US Israel strike Iran missile sites Reuters"),
    ]
    report = extract_claims(articles)
    cluster_sizes = [len(c["article_ids"]) for c in report["clusters"]]
    assert max(cluster_sizes) >= 2
