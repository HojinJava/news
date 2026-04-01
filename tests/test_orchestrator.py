import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from agents.orchestrator import run_pipeline_for_category

def test_run_pipeline_requires_category_slug():
    import pytest
    with pytest.raises(ValueError, match="category_slug"):
        run_pipeline_for_category(category_slug="", topic="test", date_from="2026-01-01")

def test_run_pipeline_creates_news_json(tmp_path, monkeypatch):
    cat_dir = tmp_path / "data" / "test-cat"
    cat_dir.mkdir(parents=True)
    (cat_dir / "config.json").write_text(json.dumps({
        "name": "테스트", "topic": "test",
        "markets": [{"key": "N", "label": "나스닥", "ticker": "^IXIC"}],
        "tags": []
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    mock_timeline = MagicMock()
    mock_timeline.to_dict.return_value = {
        "version": "2.0.0", "topic": "test",
        "generated_at": "2026-01-01T00:00:00Z",
        "last_updated": "2026-01-01T00:00:00Z",
        "date_range": {"from": "2026-01-01", "to": "2026-01-31"},
        "total_events": 0, "total_articles": 0, "events": []
    }

    with patch("agents.orchestrator.collect_articles", return_value=[]), \
         patch("agents.orchestrator.extract_claims", return_value={"clusters": [], "claims": {}}), \
         patch("agents.orchestrator.challenge_claims", return_value={"challenges": {}}), \
         patch("agents.orchestrator.arbitrate", return_value=[]), \
         patch("agents.orchestrator.analyze_bias", return_value=[]), \
         patch("agents.orchestrator.build_timeline", return_value=mock_timeline):
        run_pipeline_for_category(
            category_slug="test-cat",
            topic="test topic",
            date_from="2026-01-01",
        )

    assert (cat_dir / "news.json").exists()
