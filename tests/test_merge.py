"""tests for utils/merge.py"""

import json
import pytest
from pathlib import Path

from models.schema import AnalyzedArticle, TimelineEvent, TimelineResult
from utils.merge import merge_timelines, save_timeline, load_timeline


def _make_article(**overrides) -> AnalyzedArticle:
    defaults = dict(
        id="art-001",
        title="US strikes Iran",
        title_ko="미국, 이란 공습",
        source="Reuters",
        url="https://reuters.com/1",
        published_date="2026-03-28T08:00:00Z",
        summary="US launched strikes",
        summary_ko="미국이 공습 감행",
        search_keyword="Iran war",
        event_cluster_id="evt-001",
        verification_status="verified",
        corroboration_count=3,
        corroborating_sources=["Reuters", "AP"],
        credibility_note="",
        source_bias="center",
        source_reliability=90,
        content_bias_score=80,
        objectivity_score=85,
        bias_analysis_note="",
        framing_comparison="",
    )
    defaults.update(overrides)
    return AnalyzedArticle(**defaults)


def _make_event(event_id: str, date: str, articles: list[AnalyzedArticle],
                summary: str = "요약") -> TimelineEvent:
    scores = [a.objectivity_score for a in articles]
    avg = round(sum(scores) / len(scores)) if scores else 0
    return TimelineEvent(
        event_id=event_id,
        date=date,
        title="이벤트",
        summary=summary,
        importance="major",
        objectivity_avg=avg,
        articles=articles,
    )


def _make_timeline(events: list[TimelineEvent], version: str = "1.0.0") -> TimelineResult:
    all_dates = [e.date for e in events if e.date]
    total_articles = sum(len(e.articles) for e in events)
    return TimelineResult(
        version=version,
        topic="test",
        date_range={"from": min(all_dates), "to": max(all_dates)} if all_dates else {"from": "", "to": ""},
        total_events=len(events),
        total_articles=total_articles,
        events=events,
    )


class TestMergeTimelines:
    def test_version_mismatch_raises(self):
        t1 = _make_timeline([], version="1.0.0")
        t2 = _make_timeline([], version="2.0.0")
        with pytest.raises(ValueError, match="버전 불일치"):
            merge_timelines(t1, t2)

    def test_merge_new_event(self):
        a1 = _make_article(id="a1", url="u1")
        a2 = _make_article(id="a2", url="u2", event_cluster_id="evt-002",
                           published_date="2026-03-30T00:00:00Z")

        t1 = _make_timeline([_make_event("evt-001", "2026-03-28T00:00:00Z", [a1])])
        t2 = _make_timeline([_make_event("evt-002", "2026-03-30T00:00:00Z", [a2])])

        merged = merge_timelines(t1, t2)
        assert merged.total_events == 2
        assert merged.total_articles == 2
        ids = [e.event_id for e in merged.events]
        assert "evt-001" in ids
        assert "evt-002" in ids

    def test_merge_same_event_dedup_articles(self):
        a1 = _make_article(id="a1", url="https://same.com/1")
        a2 = _make_article(id="a2", url="https://same.com/1")  # same URL
        a3 = _make_article(id="a3", url="https://different.com/2", objectivity_score=70)

        t1 = _make_timeline([_make_event("evt-001", "2026-03-28T00:00:00Z", [a1])])
        t2 = _make_timeline([_make_event("evt-001", "2026-03-28T00:00:00Z", [a2, a3])])

        merged = merge_timelines(t1, t2)
        assert merged.total_events == 1
        ev = merged.events[0]
        assert len(ev.articles) == 2  # deduped by URL
        urls = {a.url for a in ev.articles}
        assert "https://same.com/1" in urls
        assert "https://different.com/2" in urls

    def test_merge_keeps_longer_summary(self):
        a1 = _make_article(id="a1", url="u1")
        short_summary = "짧은 요약"
        long_summary = "이것은 훨씬 더 긴 요약으로 더 많은 정보를 담고 있습니다"

        t1 = _make_timeline([_make_event("evt-001", "2026-03-28T00:00:00Z", [a1], summary=short_summary)])
        t2 = _make_timeline([_make_event("evt-001", "2026-03-28T00:00:00Z", [a1], summary=long_summary)])

        merged = merge_timelines(t1, t2)
        assert merged.events[0].summary == long_summary

    def test_merge_recalculates_objectivity(self):
        a1 = _make_article(id="a1", url="u1", objectivity_score=80)
        a2 = _make_article(id="a2", url="u2", objectivity_score=60)

        t1 = _make_timeline([_make_event("evt-001", "2026-03-28T00:00:00Z", [a1])])
        t2 = _make_timeline([_make_event("evt-001", "2026-03-28T00:00:00Z", [a2])])

        merged = merge_timelines(t1, t2)
        assert merged.events[0].objectivity_avg == 70  # (80+60)/2

    def test_merge_sorts_by_date(self):
        a1 = _make_article(id="a1", url="u1")
        a2 = _make_article(id="a2", url="u2")

        ev_late = _make_event("evt-002", "2026-04-01T00:00:00Z", [a2])
        ev_early = _make_event("evt-001", "2026-03-01T00:00:00Z", [a1])

        t1 = _make_timeline([ev_late])
        t2 = _make_timeline([ev_early])

        merged = merge_timelines(t1, t2)
        assert merged.events[0].event_id == "evt-001"
        assert merged.events[1].event_id == "evt-002"

    def test_merge_empty_with_nonempty(self):
        a1 = _make_article(id="a1", url="u1")
        t1 = _make_timeline([])
        t2 = _make_timeline([_make_event("evt-001", "2026-03-28T00:00:00Z", [a1])])

        merged = merge_timelines(t1, t2)
        assert merged.total_events == 1


class TestSaveLoadTimeline:
    def test_save_and_load(self, tmp_path: Path):
        a1 = _make_article()
        ev = _make_event("evt-001", "2026-03-28T00:00:00Z", [a1])
        original = _make_timeline([ev])

        filepath = tmp_path / "result.json"
        save_timeline(original, filepath)

        assert filepath.exists()
        loaded = load_timeline(filepath)

        assert loaded.version == original.version
        assert loaded.topic == original.topic
        assert loaded.total_events == 1
        assert loaded.total_articles == 1
        assert loaded.events[0].event_id == "evt-001"
        assert len(loaded.events[0].articles) == 1
        assert loaded.events[0].articles[0].url == "https://reuters.com/1"

    def test_save_creates_directories(self, tmp_path: Path):
        result = _make_timeline([])
        filepath = tmp_path / "nested" / "dir" / "result.json"
        save_timeline(result, filepath)
        assert filepath.exists()

    def test_load_roundtrip_preserves_data(self, tmp_path: Path):
        a1 = _make_article(id="a1", url="u1", objectivity_score=90)
        a2 = _make_article(id="a2", url="u2", objectivity_score=70,
                           event_cluster_id="evt-002",
                           published_date="2026-03-30T00:00:00Z")
        ev1 = _make_event("evt-001", "2026-03-28T00:00:00Z", [a1])
        ev2 = _make_event("evt-002", "2026-03-30T00:00:00Z", [a2])
        original = _make_timeline([ev1, ev2])

        filepath = tmp_path / "result.json"
        save_timeline(original, filepath)
        loaded = load_timeline(filepath)

        assert loaded.total_events == 2
        assert loaded.total_articles == 2
        assert loaded.date_range == original.date_range
