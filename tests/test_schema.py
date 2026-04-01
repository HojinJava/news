import pytest
from models.schema import MarketImpact, TimelineEvent, AnalyzedArticle

def test_market_impact_creation():
    mi = MarketImpact(key="W", delta_pct=4.2, window_start="2026-03-28T07:30:00Z", window_end="2026-03-28T08:05:00Z")
    assert mi.key == "W"
    assert mi.delta_pct == 4.2

def test_timeline_event_has_market_impact():
    evt = TimelineEvent(event_id="evt-001", date="2026-03-28", title="테스트", summary="요약")
    assert isinstance(evt.market_impact, dict)

def test_timeline_result_version_v2():
    from models.schema import TimelineResult
    r = TimelineResult()
    assert r.version == "2.0.0"
