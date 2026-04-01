"""Bias Analyst 에이전트 테스트."""

import pytest

from models.schema import VerifiedArticle, AnalyzedArticle
from agents.bias_analyst import (
    analyze_bias,
    _count_emotional_words,
    _compute_content_bias_score,
    _compute_objectivity,
    _build_source_lookup,
    _generate_framing_comparison,
)


# ── Fixtures ────────────────────────────────────────────────────────────

SAMPLE_CONFIG = {
    "sources": {
        "tier1_factual": [
            {"name": "Reuters", "bias": "center", "reliability": 95},
            {"name": "BBC News", "bias": "center-left", "reliability": 90},
        ],
        "tier2_analysis": [
            {"name": "Al Jazeera", "bias": "center-left", "reliability": 80},
        ],
    }
}


def _make_verified(
    source: str = "Reuters",
    title: str = "US strikes hit targets",
    summary: str = "The US military conducted strikes.",
    cluster_id: str = "c1",
    corroboration_count: int = 3,
    verification_status: str = "verified",
) -> VerifiedArticle:
    return VerifiedArticle(
        id="art-001",
        title=title,
        title_ko="제목",
        source=source,
        url="https://example.com/article",
        published_date="2026-03-28T08:00:00Z",
        summary=summary,
        summary_ko="요약",
        search_keyword="test",
        event_cluster_id=cluster_id,
        verification_status=verification_status,
        corroboration_count=corroboration_count,
        corroborating_sources=["AP", "BBC"],
        credibility_note="검증 완료",
    )


# ── Unit Tests ──────────────────────────────────────────────────────────


class TestCountEmotionalWords:
    def test_no_emotional_words(self):
        assert _count_emotional_words("The president met with officials.") == 0

    def test_single_emotional_word(self):
        assert _count_emotional_words("A devastating attack occurred.") == 1

    def test_multiple_emotional_words(self):
        text = "A brutal and savage massacre occurred."
        count = _count_emotional_words(text)
        assert count == 3  # brutal, savage, massacre

    def test_case_insensitive(self):
        assert _count_emotional_words("TERRORIST regime BRUTAL") == 3

    def test_pro_western_bias_words(self):
        text = "The regime's terrorist extremist forces"
        count = _count_emotional_words(text)
        assert count == 3

    def test_pro_middle_eastern_bias_words(self):
        text = "The imperialist zionist occupier crusader forces"
        count = _count_emotional_words(text)
        assert count == 4


class TestComputeContentBiasScore:
    def test_neutral_article(self):
        article = _make_verified(
            title="Officials met for talks",
            summary="The two sides discussed terms.",
        )
        score = _compute_content_bias_score(article)
        assert score == 100

    def test_biased_article(self):
        article = _make_verified(
            title="Brutal terrorist regime launches savage attack",
            summary="Devastating massacre by extremist forces",
        )
        score = _compute_content_bias_score(article)
        assert score < 50

    def test_score_clamped_to_zero(self):
        article = _make_verified(
            title="brutal savage barbaric ruthless heinous terrorist regime radical extremist rogue tyrant",
            summary="devastating shocking horrifying terrifying outrageous",
        )
        score = _compute_content_bias_score(article)
        assert score == 0


class TestComputeObjectivity:
    def test_high_objectivity(self):
        # reliability=95, corroboration=5 (score=100), content=100
        score = _compute_objectivity(95, 5, 100)
        # 95*0.4 + 100*0.3 + 100*0.3 = 38 + 30 + 30 = 98
        assert score == 98

    def test_low_objectivity(self):
        # reliability=50, corroboration=0 (score=0), content=0
        score = _compute_objectivity(50, 0, 0)
        # 50*0.4 + 0 + 0 = 20
        assert score == 20

    def test_corroboration_capped_at_100(self):
        # corroboration=10 → score = min(200, 100) = 100
        score = _compute_objectivity(80, 10, 80)
        # 80*0.4 + 100*0.3 + 80*0.3 = 32 + 30 + 24 = 86
        assert score == 86


class TestBuildSourceLookup:
    def test_lookup_known_source(self):
        lookup = _build_source_lookup(SAMPLE_CONFIG)
        assert lookup["Reuters"]["bias"] == "center"
        assert lookup["Reuters"]["reliability"] == 95

    def test_lookup_all_sources(self):
        lookup = _build_source_lookup(SAMPLE_CONFIG)
        assert len(lookup) == 3
        assert "Al Jazeera" in lookup

    def test_empty_config(self):
        lookup = _build_source_lookup({})
        assert lookup == {}


class TestFramingComparison:
    def test_single_article(self):
        article = _make_verified()
        result = _generate_framing_comparison([(article, "center", 90)])
        assert "부족" in result

    def test_multiple_articles(self):
        a1 = _make_verified(source="Reuters")
        a2 = _make_verified(source="Al Jazeera")
        result = _generate_framing_comparison([
            (a1, "center", 90),
            (a2, "center-left", 70),
        ])
        assert "Reuters" in result
        assert "Al Jazeera" in result
        assert "중도" in result


# ── Integration Tests ───────────────────────────────────────────────────


class TestAnalyzeBias:
    def test_basic_analysis(self):
        articles = [_make_verified()]
        results = analyze_bias(articles, SAMPLE_CONFIG)
        assert len(results) == 1
        assert isinstance(results[0], AnalyzedArticle)

    def test_source_info_from_config(self):
        articles = [_make_verified(source="Reuters")]
        results = analyze_bias(articles, SAMPLE_CONFIG)
        assert results[0].source_bias == "center"
        assert results[0].source_reliability == 95

    def test_unknown_source_defaults(self):
        articles = [_make_verified(source="Unknown Daily")]
        results = analyze_bias(articles, SAMPLE_CONFIG)
        assert results[0].source_bias == "center"
        assert results[0].source_reliability == 50

    def test_objectivity_score_formula(self):
        article = _make_verified(
            source="Reuters",  # reliability=95
            title="Officials met for talks",
            summary="The two sides discussed terms.",
            corroboration_count=5,  # corroboration_score = 100
        )
        results = analyze_bias([article], SAMPLE_CONFIG)
        r = results[0]
        # content_bias_score = 100 (no emotional words)
        # objectivity = 95*0.4 + 100*0.3 + 100*0.3 = 98
        assert r.objectivity_score == 98

    def test_framing_comparison_same_cluster(self):
        a1 = _make_verified(source="Reuters", cluster_id="c1")
        a1.id = "art-001"
        a2 = _make_verified(source="Al Jazeera", cluster_id="c1")
        a2.id = "art-002"
        results = analyze_bias([a1, a2], SAMPLE_CONFIG)
        # Both should have the same framing comparison
        assert "Reuters" in results[0].framing_comparison
        assert "Al Jazeera" in results[0].framing_comparison
        assert results[0].framing_comparison == results[1].framing_comparison

    def test_different_clusters_separate_framing(self):
        a1 = _make_verified(source="Reuters", cluster_id="c1")
        a2 = _make_verified(source="BBC News", cluster_id="c2")
        results = analyze_bias([a1, a2], SAMPLE_CONFIG)
        # Each is alone in its cluster
        assert "부족" in results[0].framing_comparison
        assert "부족" in results[1].framing_comparison

    def test_bias_note_in_korean(self):
        articles = [_make_verified()]
        results = analyze_bias(articles, SAMPLE_CONFIG)
        note = results[0].bias_analysis_note
        assert "매체 성향" in note
        assert "객관도 점수" in note

    def test_preserves_verified_fields(self):
        article = _make_verified(verification_status="flagged")
        results = analyze_bias([article], SAMPLE_CONFIG)
        assert results[0].verification_status == "flagged"
        assert results[0].corroborating_sources == ["AP", "BBC"]
        assert results[0].url == "https://example.com/article"

    def test_empty_input(self):
        results = analyze_bias([], SAMPLE_CONFIG)
        assert results == []

    def test_multiple_articles_various_sources(self):
        articles = [
            _make_verified(source="Reuters"),
            _make_verified(source="BBC News"),
            _make_verified(source="Al Jazeera"),
        ]
        results = analyze_bias(articles, SAMPLE_CONFIG)
        assert len(results) == 3
        biases = {r.source_bias for r in results}
        assert "center" in biases
        assert "center-left" in biases
