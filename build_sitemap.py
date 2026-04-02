#!/usr/bin/env python3
"""build_sitemap.py — news.json에서 sitemap.xml 생성. 크롤링/빌드 후 실행."""
import json
from pathlib import Path
from datetime import datetime, timezone

BASE_URL = "https://hojinjava.github.io/news/"


def build_sitemap() -> None:
    reg = json.loads(Path("data/registry.json").read_text(encoding="utf-8"))

    entries: list[tuple[str, str]] = []

    # 홈
    entries.append((BASE_URL, datetime.now(timezone.utc).strftime("%Y-%m-%d")))

    for cat in reg.get("categories", []):
        slug = cat["slug"]
        last = (cat.get("last_updated") or "")[:10] or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        news_path = Path(f"data/{slug}/news.json")
        if not news_path.exists():
            continue

        # 카테고리 URL
        entries.append((f"{BASE_URL}?cat={slug}", last))

        # 이벤트별 URL
        news = json.loads(news_path.read_text(encoding="utf-8"))
        for evt in news.get("events", []):
            eid = evt.get("event_id")
            date = (evt.get("date") or last)[:10]
            if eid:
                entries.append((f"{BASE_URL}?cat={slug}&evt={eid}", date))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in entries:
        lines.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    lines.append("</urlset>")

    Path("sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"sitemap.xml 생성: {len(entries)}개 URL")


if __name__ == "__main__":
    build_sitemap()
