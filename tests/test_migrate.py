import json
from pathlib import Path
from utils.migrate import migrate_result_to_news

def test_migrate_adds_version_and_last_updated(tmp_path):
    src = tmp_path / "result.json"
    src.write_text(json.dumps({
        "version": "1.0.0",
        "topic": "테스트",
        "generated_at": "2026-03-01T00:00:00Z",
        "date_range": {"from": "2026-03-01", "to": "2026-03-31"},
        "total_events": 1,
        "total_articles": 1,
        "events": [{
            "event_id": "evt-001",
            "date": "2026-03-28",
            "title": "테스트 이벤트",
            "summary": "요약",
            "importance": "major",
            "objectivity_avg": 75,
            "causally_related_to": [],
            "articles": []
        }]
    }, ensure_ascii=False))

    dst = tmp_path / "news.json"
    migrate_result_to_news(str(src), str(dst))

    result = json.loads(dst.read_text())
    assert result["version"] == "2.0.0"
    assert "last_updated" in result
    assert result["events"][0]["market_impact"] == {}

def test_migrate_preserves_articles(tmp_path):
    src = tmp_path / "result.json"
    src.write_text(json.dumps({
        "version": "1.0.0", "topic": "t", "generated_at": "2026-01-01T00:00:00Z",
        "date_range": {"from": "2026-01-01", "to": "2026-01-31"},
        "total_events": 1, "total_articles": 1,
        "events": [{
            "event_id": "e1", "date": "2026-01-01", "title": "T", "summary": "S",
            "importance": "minor", "objectivity_avg": 50,
            "causally_related_to": [], "articles": [{
                "id": "art-001", "title": "Article", "title_ko": "기사",
                "source": "Reuters", "url": "https://example.com",
                "published_date": "2026-01-01T00:00:00Z", "summary": "sum",
                "summary_ko": "요약", "search_keyword": "kw",
                "source_type": "news", "view_count": -1,
                "collected_at": "2026-01-01T00:00:00Z",
                "event_cluster_id": "e1", "verification_status": "verified",
                "corroboration_count": 2, "corroborating_sources": ["AP"],
                "credibility_note": "ok", "source_bias": "center",
                "source_reliability": 90, "content_bias_score": 80,
                "objectivity_score": 85, "bias_analysis_note": "n",
                "framing_comparison": "f"
            }]
        }]
    }, ensure_ascii=False))
    dst = tmp_path / "news.json"
    migrate_result_to_news(str(src), str(dst))
    result = json.loads(dst.read_text())
    assert result["total_articles"] == 1
    assert result["events"][0]["articles"][0]["id"] == "art-001"
