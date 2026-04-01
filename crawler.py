#!/usr/bin/env python3
"""Google News RSS 기반 뉴스 크롤러 - 이란 vs 이스라엘+미국 관련 뉴스 수집"""

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = DATA_DIR / "news.json"

SEARCH_KEYWORDS = [
    "Iran Israel war",
    "Iran Israel conflict",
    "Iran US military",
    "Israel Iran strike",
    "Iran nuclear Israel",
    "이란 이스라엘",
    "Iran Israel US war 2026",
    "Iran retaliation Israel",
    "Middle East conflict Iran",
]

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"


def generate_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def extract_keywords_from_title(title: str) -> list[str]:
    keyword_map = {
        "iran": "iran",
        "israel": "israel",
        "us ": "us",
        "u.s.": "us",
        "united states": "us",
        "america": "us",
        "military": "military",
        "nuclear": "nuclear",
        "strike": "strike",
        "war": "war",
        "missile": "missile",
        "attack": "attack",
        "conflict": "conflict",
        "irgc": "irgc",
        "hezbollah": "hezbollah",
        "hamas": "hamas",
        "gaza": "gaza",
        "middle east": "middle_east",
        "sanction": "sanctions",
        "drone": "drone",
    }
    lower = title.lower()
    found = []
    for pattern, kw in keyword_map.items():
        if pattern in lower and kw not in found:
            found.append(kw)
    return found if found else ["middle_east"]


def parse_pub_date(entry) -> str:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    if hasattr(entry, "published") and entry.published:
        return entry.published
    return datetime.now(timezone.utc).isoformat()


def extract_source(entry) -> str:
    if hasattr(entry, "source") and hasattr(entry.source, "title"):
        return entry.source.title
    # Google News RSS 제목에서 " - Source" 패턴 추출
    title = entry.get("title", "")
    match = re.search(r"\s-\s([^-]+)$", title)
    if match:
        return match.group(1).strip()
    return "Unknown"


def clean_title(title: str) -> str:
    # Google News는 제목 끝에 " - Source" 를 붙임 → 제거
    cleaned = re.sub(r"\s-\s[^-]+$", "", title)
    return cleaned.strip()


def fetch_rss_articles(keyword: str) -> list[dict]:
    url = GOOGLE_NEWS_RSS_URL.format(query=quote(keyword))
    articles = []

    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as e:
        print(f"  [ERROR] RSS fetch failed for '{keyword}': {e}")
        return []

    for entry in feed.entries:
        raw_title = entry.get("title", "")
        link = entry.get("link", "")
        if not link:
            continue

        source = extract_source(entry)
        title = clean_title(raw_title)
        summary = ""
        if hasattr(entry, "summary"):
            soup = BeautifulSoup(entry.summary, "html.parser")
            summary = soup.get_text(separator=" ", strip=True)

        article = {
            "id": generate_id(link),
            "title": title,
            "summary": summary,
            "date": parse_pub_date(entry),
            "source": source,
            "url": link,
            "keywords": extract_keywords_from_title(raw_title),
        }
        articles.append(article)

    return articles


def load_existing() -> dict:
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"lastUpdated": "", "articles": []}


def save_data(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def crawl():
    print("=== 뉴스 크롤러 시작 ===")
    print(f"검색 키워드 {len(SEARCH_KEYWORDS)}개")

    existing = load_existing()
    existing_urls = {a["url"] for a in existing["articles"]}
    existing_ids = {a["id"] for a in existing["articles"]}
    new_articles = []

    for i, keyword in enumerate(SEARCH_KEYWORDS, 1):
        print(f"\n[{i}/{len(SEARCH_KEYWORDS)}] '{keyword}' 검색 중...")
        articles = fetch_rss_articles(keyword)
        print(f"  → {len(articles)}건 발견")

        added = 0
        for article in articles:
            if article["url"] in existing_urls or article["id"] in existing_ids:
                continue
            existing_urls.add(article["url"])
            existing_ids.add(article["id"])
            new_articles.append(article)
            added += 1

        print(f"  → {added}건 신규 추가")

        # Rate limiting
        if i < len(SEARCH_KEYWORDS):
            time.sleep(1)

    all_articles = existing["articles"] + new_articles

    # 날짜 기준 최신순 정렬
    all_articles.sort(key=lambda a: a.get("date", ""), reverse=True)

    data = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "articles": all_articles,
    }

    save_data(data)

    print(f"\n=== 크롤링 완료 ===")
    print(f"신규 수집: {len(new_articles)}건")
    print(f"총 기사 수: {len(all_articles)}건")
    print(f"저장 위치: {OUTPUT_FILE}")


if __name__ == "__main__":
    crawl()
