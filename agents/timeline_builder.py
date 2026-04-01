"""타임라인 정리 에이전트 — 분석 완료 뉴스를 시간순 타임라인으로 구조화."""

from __future__ import annotations

import re
from collections import defaultdict

from models.schema import AnalyzedArticle, TimelineEvent, TimelineResult, _now_iso


def build_timeline(articles: list[AnalyzedArticle], topic: str) -> TimelineResult:
    """AnalyzedArticle 리스트를 받아 TimelineResult를 생성한다."""
    if not articles:
        return TimelineResult(topic=topic, generated_at=_now_iso())

    # 1. event_cluster_id 기준으로 그룹핑
    clusters: dict[str, list[AnalyzedArticle]] = defaultdict(list)
    for art in articles:
        clusters[art.event_cluster_id].append(art)

    # 2. 클러스터별 TimelineEvent 생성
    events: list[TimelineEvent] = []
    for cluster_id, cluster_articles in clusters.items():
        event = _build_event(cluster_id, cluster_articles)
        events.append(event)

    # 3. 날짜 기준 오름차순 정렬
    events.sort(key=lambda e: e.date)

    # 4. 인과관계 태깅
    _tag_causal_relations(events)

    # 5. date_range 및 총계 계산
    all_dates = [e.date for e in events if e.date]
    date_range = {"from": min(all_dates), "to": max(all_dates)} if all_dates else {"from": "", "to": ""}
    total_articles = sum(len(e.articles) for e in events)

    return TimelineResult(
        version="1.0.0",
        topic=topic,
        generated_at=_now_iso(),
        date_range=date_range,
        total_events=len(events),
        total_articles=total_articles,
        events=events,
    )


def _build_event(cluster_id: str, articles: list[AnalyzedArticle]) -> TimelineEvent:
    """클러스터 내 기사들로 하나의 TimelineEvent를 생성한다."""
    # 가장 이른 발행일
    dates = [a.published_date for a in articles if a.published_date]
    earliest_date = min(dates) if dates else ""

    # 객관도 가장 높은 기사의 title_ko 사용
    best = max(articles, key=lambda a: a.objectivity_score)
    title = best.title_ko or best.title

    # 종합 요약: 각 기사의 핵심 정보를 결합
    summaries = [a.summary_ko or a.summary for a in articles if (a.summary_ko or a.summary)]
    unique_summaries = list(dict.fromkeys(summaries))  # 순서 유지하면서 중복 제거
    summary = "종합: " + " ".join(unique_summaries[:5])

    # 중요도 판정
    max_corroboration = max(a.corroboration_count for a in articles)
    if max_corroboration >= 4:
        importance = "critical"
    elif max_corroboration >= 2:
        importance = "major"
    else:
        importance = "minor"

    # 평균 객관도
    scores = [a.objectivity_score for a in articles]
    objectivity_avg = round(sum(scores) / len(scores)) if scores else 0

    return TimelineEvent(
        event_id=cluster_id,
        date=earliest_date,
        title=title,
        summary=summary,
        importance=importance,
        objectivity_avg=objectivity_avg,
        articles=list(articles),
    )


def _extract_keywords(text: str) -> set[str]:
    """텍스트에서 의미 있는 키워드를 추출한다."""
    words = re.findall(r"[a-zA-Z]{3,}|[\uac00-\ud7af]{2,}", text.lower())
    stopwords = {"the", "and", "for", "with", "from", "that", "this", "are", "was", "been"}
    return {w for w in words if w not in stopwords}


def _tag_causal_relations(events: list[TimelineEvent]) -> None:
    """3일 이내이고 키워드가 겹치는 이벤트 간 인과관계를 태깅한다."""
    for i, ev_a in enumerate(events):
        kw_a = _extract_keywords(ev_a.title + " " + ev_a.summary)
        for j, ev_b in enumerate(events):
            if i == j:
                continue
            if ev_b.event_id in ev_a.causally_related_to:
                continue
            # 날짜 차이 확인 (3일 이내)
            try:
                date_a = ev_a.date[:10]
                date_b = ev_b.date[:10]
                from datetime import datetime as dt
                diff = abs((dt.fromisoformat(date_a) - dt.fromisoformat(date_b)).days)
                if diff > 3:
                    continue
            except (ValueError, IndexError):
                continue

            kw_b = _extract_keywords(ev_b.title + " " + ev_b.summary)
            overlap = kw_a & kw_b
            if len(overlap) >= 2:
                ev_a.causally_related_to.append(ev_b.event_id)
