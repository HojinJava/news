"""Verifier 에이전트 테스트."""

import re
import pytest

from models.schema import RawArticle, VerifiedArticle
from agents.verifier import (
    verify_articles,
    _tokenize,
    _jaccard,
    _cluster_articles,
    _has_sensational_language,
)


# ── helpers ─────────────────────────────────────────────────────────────

def _make_raw(
    title: str = "Test headline",
    source: str = "Reuters",
    url: str = "https://example.com/1",
    **kwargs,
) -> RawArticle:
    defaults = dict(
        id="art-0001",
        title=title,
        title_ko="테스트 제목",
        source=source,
        url=url,
        published_date="2026-03-28T08:00:00Z",
        summary="A test summary.",
        summary_ko="테스트 요약.",
        search_keyword="test",
        collected_at="2026-03-28T10:00:00Z",
    )
    defaults.update(kwargs)
    return RawArticle(**defaults)


# ── _tokenize / _jaccard ───────────────────────────────────────────────

class TestTokenize:
    def test_basic(self):
        assert _tokenize("US strikes Iran") == {"us", "strikes", "iran"}

    def test_punctuation_removed(self):
        assert _tokenize("U.S. strikes: Iran!") == {"u", "s", "strikes", "iran"}

    def test_empty(self):
        assert _tokenize("") == set()


class TestJaccard:
    def test_identical(self):
        s = {"a", "b", "c"}
        assert _jaccard(s, s) == 1.0

    def test_disjoint(self):
        assert _jaccard({"a"}, {"b"}) == 0.0

    def test_partial_overlap(self):
        assert _jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)

    def test_empty_sets(self):
        assert _jaccard(set(), {"a"}) == 0.0
        assert _jaccard(set(), set()) == 0.0


# ── clustering ──────────────────────────────────────────────────────────

class TestClustering:
    def test_similar_titles_cluster_together(self):
        a1 = _make_raw(title="US and Israel strike Iran nuclear facility", id="art-01")
        a2 = _make_raw(title="Israel and US strike Iran nuclear site", source="AP", id="art-02")
        clusters = _cluster_articles([a1, a2])
        assert len(clusters) == 1

    def test_different_titles_separate_clusters(self):
        a1 = _make_raw(title="US strikes Iran nuclear facility", id="art-01")
        a2 = _make_raw(title="Olympics opening ceremony in Paris", id="art-02")
        clusters = _cluster_articles([a1, a2])
        assert len(clusters) == 2

    def test_cluster_ids_format(self):
        a1 = _make_raw(id="art-01")
        clusters = _cluster_articles([a1])
        for cid in clusters:
            assert re.match(r"^evt-[0-9a-f]{8}$", cid)


# ── sensational language ────────────────────────────────────────────────

class TestSensational:
    def test_detects_breaking(self):
        art = _make_raw(title="BREAKING: Iran fires missiles")
        assert _has_sensational_language(art) is True

    def test_detects_in_summary(self):
        art = _make_raw(summary="EXCLUSIVE report on the conflict")
        assert _has_sensational_language(art) is True

    def test_normal_headline(self):
        art = _make_raw(title="Iran fires missiles at Israel")
        assert _has_sensational_language(art) is False


# ── verify_articles (통합) ──────────────────────────────────────────────

class TestVerifyArticles:
    def test_empty_input(self):
        assert verify_articles([], {}) == []

    def test_single_article_unverified(self):
        art = _make_raw()
        result = verify_articles([art])
        assert len(result) == 1
        assert result[0].verification_status == "unverified"
        assert result[0].corroboration_count == 1

    def test_two_sources_verified(self):
        a1 = _make_raw(
            title="US strikes Iran nuclear facility",
            source="Reuters",
            id="art-01",
            url="https://reuters.com/1",
        )
        a2 = _make_raw(
            title="US strikes Iran nuclear site",
            source="AP",
            id="art-02",
            url="https://ap.com/1",
        )
        result = verify_articles([a1, a2])
        assert len(result) == 2
        for v in result:
            assert v.verification_status == "verified"
            assert v.corroboration_count == 2

    def test_same_source_not_verified(self):
        a1 = _make_raw(
            title="US strikes Iran nuclear facility",
            source="Reuters",
            id="art-01",
            url="https://reuters.com/1",
        )
        a2 = _make_raw(
            title="US strikes Iran nuclear site",
            source="Reuters",
            id="art-02",
            url="https://reuters.com/2",
        )
        result = verify_articles([a1, a2])
        # Same source → only 1 distinct source → unverified
        for v in result:
            assert v.verification_status == "unverified"
            assert v.corroboration_count == 1

    def test_sensational_unverified_becomes_flagged(self):
        art = _make_raw(
            title="BREAKING: Shocking attack on Iran",
            source="UnknownBlog",
            id="art-01",
        )
        result = verify_articles([art])
        assert result[0].verification_status == "flagged"

    def test_sensational_but_verified_stays_verified(self):
        a1 = _make_raw(
            title="BREAKING: US strikes Iran nuclear facility",
            source="Reuters",
            id="art-01",
            url="https://reuters.com/1",
        )
        a2 = _make_raw(
            title="US strikes Iran nuclear facility",
            source="AP",
            id="art-02",
            url="https://ap.com/1",
        )
        result = verify_articles([a1, a2])
        # Both should be verified (2 distinct sources), even with sensational language
        for v in result:
            assert v.verification_status == "verified"

    def test_credibility_note_is_korean(self):
        art = _make_raw()
        result = verify_articles([art])
        # Should contain Korean characters
        assert re.search(r"[\uac00-\ud7a3]", result[0].credibility_note)

    def test_returns_verified_article_instances(self):
        art = _make_raw()
        result = verify_articles([art])
        assert isinstance(result[0], VerifiedArticle)

    def test_preserves_raw_fields(self):
        art = _make_raw(title="Original title", source="BBC")
        result = verify_articles([art])
        assert result[0].title == "Original title"
        assert result[0].source == "BBC"

    def test_corroborating_sources_excludes_self(self):
        a1 = _make_raw(
            title="US strikes Iran nuclear facility",
            source="Reuters",
            id="art-01",
            url="https://reuters.com/1",
        )
        a2 = _make_raw(
            title="US strikes Iran nuclear site",
            source="AP",
            id="art-02",
            url="https://ap.com/1",
        )
        result = verify_articles([a1, a2])
        reuters_article = [v for v in result if v.source == "Reuters"][0]
        assert "Reuters" not in reuters_article.corroborating_sources
        assert "AP" in reuters_article.corroborating_sources

    def test_event_cluster_id_consistent_within_cluster(self):
        a1 = _make_raw(
            title="US strikes Iran nuclear facility",
            source="Reuters",
            id="art-01",
            url="https://reuters.com/1",
        )
        a2 = _make_raw(
            title="US strikes Iran nuclear site",
            source="AP",
            id="art-02",
            url="https://ap.com/1",
        )
        result = verify_articles([a1, a2])
        assert result[0].event_cluster_id == result[1].event_cluster_id

    def test_multiple_clusters(self):
        a1 = _make_raw(title="US strikes Iran", source="Reuters", id="art-01", url="https://r.com/1")
        a2 = _make_raw(title="US strikes Iran facility", source="AP", id="art-02", url="https://a.com/1")
        a3 = _make_raw(title="Olympics ceremony in Paris begins", source="BBC", id="art-03", url="https://b.com/1")
        result = verify_articles([a1, a2, a3])
        cluster_ids = {v.event_cluster_id for v in result}
        assert len(cluster_ids) == 2
