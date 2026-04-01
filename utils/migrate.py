"""utils/migrate.py — output/result.json → data/{category}/news.json 마이그레이션."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def migrate_result_to_news(src_path: str, dst_path: str) -> None:
    """result.json(v1)을 news.json(v2)으로 변환한다.

    변경 사항:
    - version: "1.0.0" → "2.0.0"
    - last_updated 필드 추가
    - 각 event에 market_impact: {} 추가
    """
    with open(src_path, encoding="utf-8") as f:
        data = json.load(f)

    data["version"] = "2.0.0"
    data["last_updated"] = datetime.now(timezone.utc).isoformat()

    for event in data.get("events", []):
        if "market_impact" not in event:
            event["market_impact"] = {}

    dst = Path(dst_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"마이그레이션 완료: {src_path} → {dst_path}")
    print(f"  이벤트: {len(data.get('events', []))}개")
