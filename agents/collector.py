"""뉴스 수집 에이전트 — Google News RSS를 이용해 주제별 뉴스를 수집한다."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup

from models.schema import RawArticle, _new_id, _now_iso

try:
    from deep_translator import GoogleTranslator
    _translator = GoogleTranslator(source='en', target='ko')
except ImportError:
    _translator = None

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS_URL = (
    "https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"
)

_TOPIC_KEYWORD_MAP: dict[str, list[str]] = {
    "이란": ["Iran"],
    "이스라엘": ["Israel"],
    "미국": ["US", "United States"],
    "전쟁": ["war", "conflict"],
    "분쟁": ["conflict", "dispute"],
    "핵": ["nuclear"],
    "미사일": ["missile"],
    "공습": ["airstrike"],
    "우크라이나": ["Ukraine"],
    "러시아": ["Russia"],
    "중국": ["China"],
    "대만": ["Taiwan"],
    "북한": ["North Korea"],
}

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


# ── 공개 API ─────────────────────────────────────────────────────────


def collect_articles(topic: str, config: dict) -> list[RawArticle]:
    """주제를 받아 config의 소스 목록에서 뉴스를 수집한다.

    Args:
        topic: 검색 주제 (예: "이란 이스라엘 미국 전쟁")
        config: config.yaml을 파싱한 dict

    Returns:
        중복 제거된 RawArticle 리스트
    """
    keywords = generate_search_keywords(topic)
    sources = _flatten_sources(config)
    max_per_source = config.get("collection", {}).get("max_articles_per_source", 10)

    seen_urls: set[str] = set()
    articles: list[RawArticle] = []

    for source in sources:
        source_count = 0
        source_type = source.get("source_type", "news")
        search_site = source.get("search_site", "")

        for keyword in keywords:
            if source_count >= max_per_source:
                break

            # 소셜 소스: search_site + from:user + keyword 조합
            if search_site:
                query = f"{keyword} {source['search_keyword']} {search_site}".strip()
            else:
                query = f"{keyword} {source['search_keyword']}".strip()

            fetched = _fetch_rss(query, source["name"])

            for raw in fetched:
                if source_count >= max_per_source:
                    break
                if raw["url"] in seen_urls:
                    continue
                seen_urls.add(raw["url"])

                article = RawArticle(
                    id=_new_id("art"),
                    title=raw["title"],
                    title_ko=raw["title"],  # 번역은 수집 후 일괄 처리
                    source=source["name"],
                    url=raw["url"],
                    published_date=raw["published_date"],
                    summary=raw["summary"],
                    summary_ko=raw["summary"],  # 번역은 수집 후 일괄 처리
                    search_keyword=query,
                    source_type=source_type,
                    collected_at=_now_iso(),
                )
                articles.append(article)
                source_count += 1

            time.sleep(1)

    # 번역
    logger.info("번역 중: %d건", len(articles))
    for art in articles:
        art.title_ko = _translate(art.title)
        art.summary_ko = _translate(art.summary) if art.summary else ""

    logger.info("수집 완료: %d건", len(articles))
    return articles


# ── 키워드 생성 ──────────────────────────────────────────────────────


def generate_search_keywords(topic: str) -> list[str]:
    """한국어 주제 문자열에서 영어 검색 키워드 리스트를 생성한다."""
    tokens = topic.split()
    english_parts: list[str] = []

    for token in tokens:
        if token in _TOPIC_KEYWORD_MAP:
            english_parts.append(_TOPIC_KEYWORD_MAP[token][0])
        elif re.match(r"[a-zA-Z]", token):
            english_parts.append(token)

    if not english_parts:
        english_parts = [topic]

    base = " ".join(english_parts)
    keywords = [base]

    # 추가 변형 키워드 생성
    for token in tokens:
        if token in _TOPIC_KEYWORD_MAP and len(_TOPIC_KEYWORD_MAP[token]) > 1:
            for alt in _TOPIC_KEYWORD_MAP[token][1:]:
                variant = base.replace(_TOPIC_KEYWORD_MAP[token][0], alt)
                if variant != base and variant not in keywords:
                    keywords.append(variant)

    return keywords


# ── 내부 함수 ────────────────────────────────────────────────────────


def _flatten_sources(config: dict) -> list[dict]:
    """config의 sources를 단일 리스트로 평탄화한다."""
    sources: list[dict] = []
    for tier_sources in config.get("sources", {}).values():
        if isinstance(tier_sources, list):
            sources.extend(tier_sources)
    return sources


def _fetch_rss(query: str, source_name: str) -> list[dict]:
    """Google News RSS에서 기사를 가져온다."""
    url = GOOGLE_NEWS_RSS_URL.format(query=quote(query))

    try:
        resp = requests.get(url, timeout=15, headers=REQUEST_HEADERS)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception:
        logger.warning("RSS 요청 실패: source=%s query=%s", source_name, query)
        return []

    results: list[dict] = []
    for entry in feed.entries:
        link = entry.get("link", "")
        if not link:
            continue

        raw_title = entry.get("title", "")
        title = _clean_title(raw_title)
        summary = ""
        if hasattr(entry, "summary") and entry.summary:
            soup = BeautifulSoup(entry.summary, "html.parser")
            summary = soup.get_text(separator=" ", strip=True)

        results.append(
            {
                "title": title,
                "url": link,
                "published_date": _parse_pub_date(entry),
                "summary": summary,
            }
        )

    return results


def _translate(text: str) -> str:
    """영어 텍스트를 한국어로 번역한다. 실패 시 원문 반환."""
    if not text or not text.strip():
        return text
    if _translator is None:
        return text
    try:
        result = _translator.translate(text[:4000])
        return result if result else text
    except Exception:
        logger.debug("번역 실패: %s", text[:50])
        return text


def _clean_title(title: str) -> str:
    """Google News 제목에서 " - Source" 접미사를 제거한다."""
    return re.sub(r"\s-\s[^-]+$", "", title).strip()


def _parse_pub_date(entry) -> str:
    """RSS 엔트리에서 발행일을 ISO 8601 문자열로 파싱한다."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    if hasattr(entry, "published") and entry.published:
        return entry.published
    return datetime.now(timezone.utc).isoformat()
