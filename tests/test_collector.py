"""collector 에이전트 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.collector import (
    collect_articles,
    generate_search_keywords,
    _clean_title,
    _flatten_sources,
    _parse_pub_date,
)
from models.schema import RawArticle


# ── 픽스처 ───────────────────────────────────────────────────────────

SAMPLE_CONFIG = {
    "sources": {
        "tier1_factual": [
            {
                "name": "Reuters",
                "search_keyword": "site:reuters.com",
                "bias": "center",
                "reliability": 95,
            },
            {
                "name": "Associated Press",
                "search_keyword": "site:apnews.com",
                "bias": "center",
                "reliability": 95,
            },
        ],
    },
    "collection": {
        "max_articles_per_source": 3,
        "date_range_days": 30,
        "languages": ["en"],
        "output_language": "ko",
    },
}

SAMPLE_RSS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Google News</title>
  <item>
    <title>Iran strikes Israel targets - Reuters</title>
    <link>https://reuters.com/article/1</link>
    <pubDate>Mon, 30 Mar 2026 10:00:00 GMT</pubDate>
    <description>Summary of the article about Iran strikes.</description>
  </item>
  <item>
    <title>US responds to Iran attack - Reuters</title>
    <link>https://reuters.com/article/2</link>
    <pubDate>Mon, 30 Mar 2026 12:00:00 GMT</pubDate>
    <description>Summary about US response.</description>
  </item>
  <item>
    <title>Escalation in Middle East - Reuters</title>
    <link>https://reuters.com/article/3</link>
    <pubDate>Mon, 30 Mar 2026 14:00:00 GMT</pubDate>
    <description>Escalation summary.</description>
  </item>
  <item>
    <title>Extra article beyond limit - Reuters</title>
    <link>https://reuters.com/article/4</link>
    <pubDate>Mon, 30 Mar 2026 16:00:00 GMT</pubDate>
    <description>Should be excluded by max limit.</description>
  </item>
</channel>
</rss>
"""

SAMPLE_RSS_XML_AP = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Google News</title>
  <item>
    <title>Iran conflict update - AP News</title>
    <link>https://apnews.com/article/1</link>
    <pubDate>Mon, 30 Mar 2026 11:00:00 GMT</pubDate>
    <description>AP coverage of Iran conflict.</description>
  </item>
</channel>
</rss>
"""


def _mock_response(xml_text: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.text = xml_text
    resp.raise_for_status = MagicMock()
    return resp


# ── generate_search_keywords ─────────────────────────────────────────


class TestGenerateSearchKeywords:
    def test_korean_topic(self):
        keywords = generate_search_keywords("이란 이스라엘 미국 전쟁")
        assert len(keywords) >= 1
        assert "Iran Israel US war" in keywords

    def test_english_passthrough(self):
        keywords = generate_search_keywords("Iran Israel war")
        assert "Iran Israel war" in keywords

    def test_variant_keywords(self):
        keywords = generate_search_keywords("이란 이스라엘 미국 전쟁")
        # Should contain a variant with "United States" instead of "US"
        assert any("United States" in kw for kw in keywords)

    def test_unknown_topic_uses_raw(self):
        keywords = generate_search_keywords("알수없는주제")
        assert len(keywords) >= 1


# ── _clean_title ─────────────────────────────────────────────────────


class TestCleanTitle:
    def test_removes_source_suffix(self):
        assert _clean_title("Breaking news - Reuters") == "Breaking news"

    def test_no_suffix(self):
        assert _clean_title("Simple title") == "Simple title"

    def test_multiple_dashes(self):
        assert _clean_title("US-Iran war update - BBC News") == "US-Iran war update"


# ── _flatten_sources ─────────────────────────────────────────────────


class TestFlattenSources:
    def test_flattens_tiers(self):
        sources = _flatten_sources(SAMPLE_CONFIG)
        assert len(sources) == 2
        assert sources[0]["name"] == "Reuters"

    def test_empty_config(self):
        assert _flatten_sources({}) == []
        assert _flatten_sources({"sources": {}}) == []


# ── _parse_pub_date ──────────────────────────────────────────────────


class TestParsePubDate:
    def test_with_published_parsed(self):
        entry = MagicMock()
        entry.published_parsed = (2026, 3, 30, 10, 0, 0, 0, 89, 0)
        result = _parse_pub_date(entry)
        assert "2026-03-30" in result

    def test_with_published_string(self):
        entry = MagicMock()
        entry.published_parsed = None
        entry.published = "Mon, 30 Mar 2026 10:00:00 GMT"
        result = _parse_pub_date(entry)
        assert result == "Mon, 30 Mar 2026 10:00:00 GMT"

    def test_fallback_to_now(self):
        entry = MagicMock()
        entry.published_parsed = None
        entry.published = None
        result = _parse_pub_date(entry)
        assert "T" in result  # ISO format


# ── collect_articles ─────────────────────────────────────────────────


class TestCollectArticles:
    @patch("agents.collector.time.sleep")
    @patch("agents.collector.requests.get")
    def test_basic_collection(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(SAMPLE_RSS_XML)

        articles = collect_articles("이란 이스라엘 미국 전쟁", SAMPLE_CONFIG)

        assert all(isinstance(a, RawArticle) for a in articles)
        assert len(articles) > 0
        mock_sleep.assert_called()

    @patch("agents.collector.time.sleep")
    @patch("agents.collector.requests.get")
    def test_max_articles_per_source(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(SAMPLE_RSS_XML)

        articles = collect_articles("이란 이스라엘 미국 전쟁", SAMPLE_CONFIG)

        # Count articles per source name
        from collections import Counter
        source_counts = Counter(a.source for a in articles)
        for count in source_counts.values():
            assert count <= SAMPLE_CONFIG["collection"]["max_articles_per_source"]

    @patch("agents.collector.time.sleep")
    @patch("agents.collector.requests.get")
    def test_deduplication(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(SAMPLE_RSS_XML)

        articles = collect_articles("이란 이스라엘 미국 전쟁", SAMPLE_CONFIG)

        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    @patch("agents.collector.time.sleep")
    @patch("agents.collector.requests.get")
    def test_korean_translation_placeholder(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(SAMPLE_RSS_XML)

        articles = collect_articles("이란 이스라엘 미국 전쟁", SAMPLE_CONFIG)

        for article in articles:
            assert article.title_ko.startswith("[번역 필요] ")
            assert article.summary_ko.startswith("[번역 필요] ")

    @patch("agents.collector.time.sleep")
    @patch("agents.collector.requests.get")
    def test_article_fields(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(SAMPLE_RSS_XML)

        articles = collect_articles("이란 이스라엘 미국 전쟁", SAMPLE_CONFIG)

        if articles:
            a = articles[0]
            assert a.id.startswith("art-")
            assert a.title
            assert a.url.startswith("http")
            assert a.source in ("Reuters", "Associated Press")
            assert a.search_keyword
            assert a.collected_at

    @patch("agents.collector.time.sleep")
    @patch("agents.collector.requests.get")
    def test_handles_request_failure(self, mock_get, mock_sleep):
        mock_get.side_effect = Exception("Network error")

        articles = collect_articles("이란 이스라엘 미국 전쟁", SAMPLE_CONFIG)

        assert articles == []

    @patch("agents.collector.time.sleep")
    @patch("agents.collector.requests.get")
    def test_multiple_sources(self, mock_get, mock_sleep):
        def side_effect(url, **kwargs):
            if "apnews" in url:
                return _mock_response(SAMPLE_RSS_XML_AP)
            return _mock_response(SAMPLE_RSS_XML)

        mock_get.side_effect = side_effect

        articles = collect_articles("이란 이스라엘 미국 전쟁", SAMPLE_CONFIG)
        sources = {a.source for a in articles}
        # Should have articles from both sources (if RSS returns matching content)
        assert len(articles) > 0

    @patch("agents.collector.time.sleep")
    @patch("agents.collector.requests.get")
    def test_title_cleaned(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(SAMPLE_RSS_XML)

        articles = collect_articles("이란 이스라엘 미국 전쟁", SAMPLE_CONFIG)

        for a in articles:
            assert not a.title.endswith("- Reuters")
