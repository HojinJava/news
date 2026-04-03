#!/usr/bin/env python3
"""build_timeline.py — Enricher 출력을 news.json으로 변환한다. AI 판단 없음."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


CAUSAL_KEYWORDS = {
    "retaliation", "retaliatory", "in response", "response to",
    "보복", "대응", "반격", "맞대응",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _objectivity_avg(articles: list[dict]) -> int | None:
    rels = [a["source_reliability"] for a in articles if a.get("source_reliability")]
    return round(sum(rels) / len(rels)) if rels else None


def _is_retaliation(event: dict) -> bool:
    text = (event.get("title_ko", "") + " " + event.get("description_ko", "")).lower()
    return any(k in text for k in CAUSAL_KEYWORDS)


def build(enriched_path: Path, output_path: Path, existing_path: Path | None = None) -> None:
    data = json.loads(enriched_path.read_text(encoding="utf-8"))
    events_in: list[dict] = data["events"]

    # 날짜 오름차순 정렬
    events_in.sort(key=lambda e: (e.get("date", ""), e.get("time", "")))

    events_out: list[dict] = []
    for i, e in enumerate(events_in):
        eid = f"evt-{i + 1:03d}"
        arts = e.get("related_articles", [])
        events_out.append({
            "event_id": eid,
            "date": e.get("date", ""),
            "time": e.get("time", "00:00:00Z"),
            "title": e.get("title_ko") or e.get("title_en", ""),
            "summary": e.get("description_ko") or e.get("description_en", ""),
            "importance": e.get("importance", "minor"),
            "objectivity_avg": _objectivity_avg(arts),
            "causally_related_to": [],
            "confirmed_by": e.get("confirmed_by", []),
            "source_urls": e.get("source_urls", {}),
            "market_impact": {},
            "trump_posts": e.get("trump_posts", []),
            "related_articles": arts,
        })

    # 인과관계 태깅: 보복 키워드 → 직전 critical/major 이벤트 연결
    for i, e in enumerate(events_out):
        if _is_retaliation({"title_ko": e["title"], "description_ko": e["summary"]}):
            for j in range(i - 1, max(i - 6, -1), -1):
                if events_out[j]["importance"] in ("critical", "major"):
                    e["causally_related_to"] = [events_out[j]["event_id"]]
                    break

    # 업데이트 모드: 기존 news.json과 머지
    if existing_path and existing_path.exists():
        existing = json.loads(existing_path.read_text(encoding="utf-8"))
        existing_events = existing.get("events", [])
        existing_ids = {
            (e.get("date", ""), e.get("title", ""))
            for e in existing_events
        }
        # 기존 최대 ID 번호 계산 → 신규 이벤트는 그 다음 번호부터 채번
        max_id = 0
        for e in existing_events:
            eid = e.get("event_id", "")
            if eid.startswith("evt-"):
                try:
                    max_id = max(max_id, int(eid[4:]))
                except ValueError:
                    pass
        counter = max_id + 1
        new_events = []
        for e in events_out:
            if (e["date"], e["title"]) not in existing_ids:
                e = dict(e)
                e["event_id"] = f"evt-{counter:03d}"
                counter += 1
                new_events.append(e)
        merged = existing_events + new_events
        merged.sort(key=lambda e: (e.get("date", ""), e.get("time", "")))
        events_out = merged

    total_articles = sum(len(e["related_articles"]) for e in events_out)

    # date_range
    dates = [e["date"] for e in events_out if e.get("date")]
    date_from = min(dates) if dates else ""
    date_to = max(dates) if dates else ""

    # viewer.html 연산 불필요 — 날짜별 이벤트 ID 사전 구성
    by_date: dict[str, list[str]] = {}
    for e in events_out:
        d = e.get("date", "")
        if d:
            by_date.setdefault(d, []).append(e["event_id"])

    result = {
        "version": "2.0.0",
        "topic": data.get("topic", ""),
        "generated_at": _now_iso(),
        "last_updated": _now_iso(),
        "date_range": {"from": date_from, "to": date_to},
        "total_events": len(events_out),
        "total_articles": total_articles,
        "by_date": by_date,
        "events": events_out,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[build_timeline] {len(events_out)}개 이벤트, {total_articles}개 기사 → {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enricher 출력 → news.json 변환")
    parser.add_argument("--category", required=True, help="카테고리 슬러그 (예: iran-war)")
    parser.add_argument("--merge", action="store_true", help="기존 news.json과 머지")
    args = parser.parse_args()

    base = Path("data") / args.category
    enriched = Path("pipeline") / args.category / "03_enriched_events.json"
    output = base / "news.json"
    existing = output if args.merge else None

    build(enriched, output, existing)


if __name__ == "__main__":
    main()
