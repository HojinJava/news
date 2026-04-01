"""tests/test_arbiter.py — Tests for Arbiter (A/B reconciliation)."""
from agents.arbiter import arbitrate
from models.schema import RawArticle, VerifiedArticle


def _make_article(id, title, source="Reuters"):
    return RawArticle(
        id=id, title=title, title_ko=title, source=source,
        url=f"https://example.com/{id}", published_date="2026-03-28T08:00:00Z",
        summary="", summary_ko="", search_keyword="test"
    )


def test_arbitrate_returns_verified_articles():
    """arbitrate() returns list of VerifiedArticle."""
    arts = [_make_article("a1", "US strikes Iran", "Reuters")]
    claims = {
        "clusters": [{"cluster_id": "c1", "article_ids": ["a1"], "sources": ["Reuters"], "representative_title": "US strikes Iran"}],
        "claims": {"a1": {"cluster_id": "c1", "is_sensational": False, "initial_status": "unverified", "note": "단독"}}
    }
    challenges = {"challenges": {"a1": {"challenge_note": "단독 출처", "confidence": 30, "flags": ["단독 출처"]}}}
    result = arbitrate(arts, claims, challenges)
    assert len(result) == 1
    assert isinstance(result[0], VerifiedArticle)
    assert result[0].verification_status in ("verified", "unverified", "flagged")


def test_arbitrate_verified_when_high_confidence():
    """High confidence (>= 70) → "verified"."""
    arts = [_make_article("a1", "US strikes Iran", "Reuters"), _make_article("a2", "US strikes Iran nuclear", "AP")]
    claims = {
        "clusters": [{"cluster_id": "c1", "article_ids": ["a1","a2"], "sources": ["Reuters","AP"], "representative_title": "US strikes Iran"}],
        "claims": {
            "a1": {"cluster_id": "c1", "is_sensational": False, "initial_status": "likely_verified", "note": "2개 매체"},
            "a2": {"cluster_id": "c1", "is_sensational": False, "initial_status": "likely_verified", "note": "2개 매체"},
        }
    }
    challenges = {
        "challenges": {
            "a1": {"challenge_note": "반박 없음", "confidence": 80, "flags": []},
            "a2": {"challenge_note": "반박 없음", "confidence": 80, "flags": []},
        }
    }
    result = arbitrate(arts, claims, challenges)
    assert all(r.verification_status == "verified" for r in result)


def test_arbitrate_flagged_when_low_confidence():
    """Low confidence (< 40) → "flagged"."""
    arts = [_make_article("a1", "Breaking: Iran nuclear bomb claim")]
    claims = {
        "clusters": [{"cluster_id": "c1", "article_ids": ["a1"], "sources": ["RT"], "representative_title": "Breaking: Iran nuclear bomb claim"}],
        "claims": {"a1": {"cluster_id": "c1", "is_sensational": True, "initial_status": "suspicious", "note": "선정적 + 단독"}}
    }
    challenges = {
        "challenges": {"a1": {"challenge_note": "편향 위험 + 선정적", "confidence": 35, "flags": ["편향 위험", "선정적 표현"]}}
    }
    result = arbitrate(arts, claims, challenges)
    assert result[0].verification_status == "flagged"


def test_arbitrate_flagged_when_multiple_flags():
    """Multiple flags (>= 2) → "flagged" regardless of confidence."""
    arts = [_make_article("a1", "Breaking exclusive: Iran secret weapons")]
    claims = {
        "clusters": [{"cluster_id": "c1", "article_ids": ["a1"], "sources": ["RT"], "representative_title": "Breaking exclusive: Iran secret weapons"}],
        "claims": {"a1": {"cluster_id": "c1", "is_sensational": True, "initial_status": "suspicious", "note": "선정적"}}
    }
    challenges = {
        "challenges": {"a1": {"challenge_note": "문제 다수", "confidence": 50, "flags": ["편향 위험", "선정적 표현", "단독 출처"]}}
    }
    result = arbitrate(arts, claims, challenges)
    assert result[0].verification_status == "flagged"


def test_arbitrate_unverified_default():
    """Mid-range confidence without flags → "unverified"."""
    arts = [_make_article("a1", "Iran responds to strikes")]
    claims = {
        "clusters": [{"cluster_id": "c1", "article_ids": ["a1"], "sources": ["Reuters"], "representative_title": "Iran responds to strikes"}],
        "claims": {"a1": {"cluster_id": "c1", "is_sensational": False, "initial_status": "unverified", "note": "단독"}}
    }
    challenges = {
        "challenges": {"a1": {"challenge_note": "단독 출처", "confidence": 45, "flags": []}}
    }
    result = arbitrate(arts, claims, challenges)
    assert result[0].verification_status == "unverified"


def test_arbitrate_populates_corroborating_sources():
    """Corroborating sources = cluster sources minus the article's own source."""
    arts = [
        _make_article("a1", "US strikes Iran", "Reuters"),
        _make_article("a2", "US strikes Iran", "AP"),
    ]
    claims = {
        "clusters": [{"cluster_id": "c1", "article_ids": ["a1", "a2"], "sources": ["Reuters", "AP"], "representative_title": "US strikes Iran"}],
        "claims": {
            "a1": {"cluster_id": "c1", "is_sensational": False, "initial_status": "likely_verified", "note": "2개 매체"},
            "a2": {"cluster_id": "c1", "is_sensational": False, "initial_status": "likely_verified", "note": "2개 매체"},
        }
    }
    challenges = {
        "challenges": {
            "a1": {"challenge_note": "반박 없음", "confidence": 75, "flags": []},
            "a2": {"challenge_note": "반박 없음", "confidence": 75, "flags": []},
        }
    }
    result = arbitrate(arts, claims, challenges)
    # a1 (Reuters) should have AP as corroborating
    a1_result = [r for r in result if r.id == "a1"][0]
    assert "AP" in a1_result.corroborating_sources
    assert "Reuters" not in a1_result.corroborating_sources
