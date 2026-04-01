"""tests for agents/timeline_builder.py"""

import pytest

from models.schema import AnalyzedArticle, TimelineResult
from agents.timeline_builder import build_timeline, _extract_keywords


def _make_article(**overrides) -> AnalyzedArticle:
    defaults = dict(
        id="art-001",
        title="US strikes Iran",
        title_ko="미국, 이란 공습",
        source="Reuters",
        url="https://reuters.com/1",
        published_date="2026-03-28T08:00:00Z",
        summary="US launched strikes on Iran",
        summary_ko="미국이 이란에 공습을 감행",
        search_keyword="Iran war",
        event_cluster_id="evt-001",
        verification_status="verified",
        corroboration_count=3,
        corroborating_sources=["Reuters", "AP", "BBC"],
        credibility_note="신뢰",
        source_bias="center",
        source_reliability=95,
        content_bias_score=80,
        objectivity_score=85,
        bias_analysis_note="사실 중심",
        framing_comparison="",
    )
    defaults.update(overrides)
    return AnalyzedArticle(**defaults)


class TestBuildTimeline:
    def test_empty_input(self):
        result = build_timeline([], "test topic")
        assert isinstance(result, TimelineResult)
        assert result.topic == "test topic"
        assert result.total_events == 0
        assert result.events == []

    def test_single_article(self):
        art = _make_article()
        result = build_timeline([art], "이란 전쟁")

        assert result.version == "1.0.0"
        assert result.topic == "이란 전쟁"
        assert result.total_events == 1
        assert result.total_articles == 1
        assert len(result.events) == 1

        ev = result.events[0]
        assert ev.event_id == "evt-001"
        assert ev.date == "2026-03-28T08:00:00Z"
        assert ev.title == "미국, 이란 공습"
        assert ev.summary.startswith("종합:")
        assert ev.importance == "major"  # corroboration_count=3
        assert ev.objectivity_avg == 85

    def test_grouping_by_cluster(self):
        a1 = _make_article(id="a1", url="https://r.com/1", event_cluster_id="evt-001")
        a2 = _make_article(id="a2", url="https://r.com/2", event_cluster_id="evt-001", source="AP")
        a3 = _make_article(id="a3", url="https://r.com/3", event_cluster_id="evt-002",
                           title_ko="이란 보복", published_date="2026-03-30T00:00:00Z")

        result = build_timeline([a1, a2, a3], "test")
        assert result.total_events == 2
        assert result.total_articles == 3

        ids = [e.event_id for e in result.events]
        assert "evt-001" in ids
        assert "evt-002" in ids

    def test_importance_critical(self):
        art = _make_article(corroboration_count=5)
        result = build_timeline([art], "test")
        assert result.events[0].importance == "critical"

    def test_importance_minor(self):
        art = _make_article(corroboration_count=1)
        result = build_timeline([art], "test")
        assert result.events[0].importance == "minor"

    def test_date_sorting(self):
        a1 = _make_article(id="a1", url="u1", event_cluster_id="evt-002",
                           published_date="2026-03-30T00:00:00Z")
        a2 = _make_article(id="a2", url="u2", event_cluster_id="evt-001",
                           published_date="2026-03-28T00:00:00Z")

        result = build_timeline([a1, a2], "test")
        assert result.events[0].event_id == "evt-001"
        assert result.events[1].event_id == "evt-002"

    def test_date_range(self):
        a1 = _make_article(id="a1", url="u1", event_cluster_id="e1",
                           published_date="2026-03-01T00:00:00Z")
        a2 = _make_article(id="a2", url="u2", event_cluster_id="e2",
                           published_date="2026-03-31T00:00:00Z")

        result = build_timeline([a1, a2], "test")
        assert result.date_range["from"] == "2026-03-01T00:00:00Z"
        assert result.date_range["to"] == "2026-03-31T00:00:00Z"

    def test_causal_relation_within_3_days(self):
        a1 = _make_article(id="a1", url="u1", event_cluster_id="evt-001",
                           title_ko="이란 미사일 공격", summary_ko="이란이 미사일 공격",
                           published_date="2026-03-28T00:00:00Z")
        a2 = _make_article(id="a2", url="u2", event_cluster_id="evt-002",
                           title_ko="이란 보복 미사일", summary_ko="이란 미사일 보복 공격",
                           published_date="2026-03-29T00:00:00Z")

        result = build_timeline([a1, a2], "test")
        ev1 = next(e for e in result.events if e.event_id == "evt-001")
        assert "evt-002" in ev1.causally_related_to

    def test_no_causal_relation_beyond_3_days(self):
        a1 = _make_article(id="a1", url="u1", event_cluster_id="evt-001",
                           title_ko="attack strike", summary_ko="attack in city",
                           published_date="2026-03-01T00:00:00Z")
        a2 = _make_article(id="a2", url="u2", event_cluster_id="evt-002",
                           title_ko="attack strike", summary_ko="attack in city",
                           published_date="2026-03-20T00:00:00Z")

        result = build_timeline([a1, a2], "test")
        ev1 = next(e for e in result.events if e.event_id == "evt-001")
        assert "evt-002" not in ev1.causally_related_to

    def test_best_title_by_objectivity(self):
        a1 = _make_article(id="a1", url="u1", event_cluster_id="evt-001",
                           title_ko="낮은 객관도 제목", objectivity_score=30)
        a2 = _make_article(id="a2", url="u2", event_cluster_id="evt-001",
                           title_ko="높은 객관도 제목", objectivity_score=95)

        result = build_timeline([a1, a2], "test")
        assert result.events[0].title == "높은 객관도 제목"


class TestExtractKeywords:
    def test_basic(self):
        kw = _extract_keywords("Iran missile attack")
        assert "iran" in kw
        assert "missile" in kw
        assert "attack" in kw

    def test_stopwords_removed(self):
        kw = _extract_keywords("the and for with")
        assert len(kw) == 0

    def test_korean(self):
        kw = _extract_keywords("이란 미사일 공격")
        assert "이란" in kw
        assert "미사일" in kw
