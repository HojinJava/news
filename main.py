#!/usr/bin/env python3
"""News-Market Agent — 파이프라인 오케스트레이터 + CLI."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from agents.orchestrator import run_pipeline_for_category


def _update_registry(slug: str, name: str) -> None:
    reg_path = Path("data/registry.json")
    reg_path.parent.mkdir(parents=True, exist_ok=True)

    if reg_path.exists():
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    else:
        reg = {"categories": []}

    existing_slugs = [c["slug"] for c in reg["categories"]]
    now = datetime.now(timezone.utc).isoformat()
    if slug not in existing_slugs:
        reg["categories"].append({"slug": slug, "name": name, "created_at": now, "last_updated": now})
    else:
        for c in reg["categories"]:
            if c["slug"] == slug:
                c["last_updated"] = now

    reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_last_updated(slug: str) -> str | None:
    news_path = Path("data") / slug / "news.json"
    if not news_path.exists():
        return None
    data = json.loads(news_path.read_text(encoding="utf-8"))
    return data.get("last_updated") or data.get("generated_at")


def main() -> None:
    parser = argparse.ArgumentParser(description="News-Market Agent")
    parser.add_argument("--category", required=True, help="카테고리 슬러그 (예: iran-war)")
    parser.add_argument("--topic",    help="검색 주제 (신규 카테고리 시 필수)")
    parser.add_argument("--date-from", dest="date_from", help="수집 시작 날짜 YYYY-MM-DD")
    parser.add_argument("--update",  action="store_true", help="last_updated 이후 증분 업데이트")
    parser.add_argument("--name",    help="카테고리 표시 이름")
    parser.add_argument("--debug",   action="store_true")
    args = parser.parse_args()

    slug = args.category
    cat_dir = Path("data") / slug

    if args.update:
        last = _get_last_updated(slug)
        if not last:
            print(f"오류: {slug} 카테고리 news.json 없음. --date-from으로 신규 수집하세요.")
            sys.exit(1)
        date_from = last[:10]
        config_path = cat_dir / "config.json"
        if not config_path.exists():
            print(f"오류: {cat_dir}/config.json 없음.")
            sys.exit(1)
        topic = json.loads(config_path.read_text(encoding="utf-8"))["topic"]
        print(f"=== 업데이트 모드: {slug} ({date_from} 이후) ===")
    else:
        if not args.topic:
            parser.error("신규 카테고리는 --topic이 필요합니다.")
        if not args.date_from:
            parser.error("신규 크롤링은 --date-from이 필요합니다.")
        date_from = args.date_from
        topic = args.topic
        name = args.name or slug
        cat_dir.mkdir(parents=True, exist_ok=True)
        _update_registry(slug, name)
        print(f"=== 신규 크롤링: {slug} ({date_from} ~ 오늘) ===")

    run_pipeline_for_category(
        category_slug=slug,
        topic=topic,
        date_from=date_from,
        debug=args.debug,
    )

    _update_registry(slug, args.name or slug)
    print(f"\n=== 완료 ===")
    print(f"다음 단계: python fetch_market.py --category {slug}")


if __name__ == "__main__":
    main()
