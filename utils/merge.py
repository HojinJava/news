"""JSON 머지 유틸리티 — 두 TimelineResult를 합친다."""

from __future__ import annotations

import json
from pathlib import Path

from models.schema import TimelineResult, TimelineEvent, AnalyzedArticle, _now_iso


def merge_timelines(base: TimelineResult, other: TimelineResult) -> TimelineResult:
    """두 TimelineResult를 머지한다. version이 다르면 ValueError."""
    if base.version != other.version:
        raise ValueError(
            f"버전 불일치: base={base.version}, other={other.version}. "
            f"같은 버전만 머지할 수 있습니다."
        )

    # event_id -> TimelineEvent 매핑 (base 기준)
    event_map: dict[str, TimelineEvent] = {}
    for ev in base.events:
        event_map[ev.event_id] = ev

    # other 이벤트 머지
    for ev in other.events:
        if ev.event_id in event_map:
            _merge_event(event_map[ev.event_id], ev)
        else:
            event_map[ev.event_id] = ev

    # 날짜 기준 재정렬
    events = sorted(event_map.values(), key=lambda e: e.date)

    # 총계 재계산
    total_articles = sum(len(e.articles) for e in events)
    all_dates = [e.date for e in events if e.date]
    date_range = {"from": min(all_dates), "to": max(all_dates)} if all_dates else {"from": "", "to": ""}

    return TimelineResult(
        version=base.version,
        topic=base.topic,
        generated_at=_now_iso(),
        date_range=date_range,
        total_events=len(events),
        total_articles=total_articles,
        events=events,
    )


def _merge_event(base_ev: TimelineEvent, other_ev: TimelineEvent) -> None:
    """같은 event_id의 두 이벤트를 머지한다 (base_ev를 in-place 수정)."""
    # articles 머지: URL 기준 중복 제거
    existing_urls = {a.url for a in base_ev.articles}
    for art in other_ev.articles:
        if art.url not in existing_urls:
            base_ev.articles.append(art)
            existing_urls.add(art.url)

    # objectivity_avg 재계산
    scores = [a.objectivity_score for a in base_ev.articles]
    base_ev.objectivity_avg = round(sum(scores) / len(scores)) if scores else 0

    # 더 긴 summary 유지
    if len(other_ev.summary) > len(base_ev.summary):
        base_ev.summary = other_ev.summary


def save_timeline(result: TimelineResult, path: str | Path) -> None:
    """TimelineResult를 JSON 파일로 저장한다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.to_json(), encoding="utf-8")


def load_timeline(path: str | Path) -> TimelineResult:
    """JSON 파일에서 TimelineResult를 로드한다."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    return TimelineResult.from_dict(data)
