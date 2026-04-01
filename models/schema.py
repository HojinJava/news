"""공통 데이터 모델 — 모든 에이전트가 참조하는 스키마."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "art") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ── MarketImpact ─────────────────────────────────────────────────────

@dataclass
class MarketImpact:
    key: str              # "W" | "C" | "N" | "K"
    delta_pct: float      # 변화율 (%)
    window_start: str     # ISO 8601 — 뉴스 시각 -30분
    window_end: str       # ISO 8601 — 뉴스 시각 +5분

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── RawArticle (Collector 출력) ──────────────────────────────────────

@dataclass
class RawArticle:
    id: str
    title: str
    title_ko: str
    source: str
    url: str
    published_date: str
    summary: str
    summary_ko: str
    search_keyword: str
    source_type: str = "news"
    view_count: int = -1
    collected_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RawArticle:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── VerifiedArticle (Verifier 출력) ──────────────────────────────────

@dataclass
class VerifiedArticle(RawArticle):
    event_cluster_id: str = ""
    verification_status: str = "unverified"
    corroboration_count: int = 0
    corroborating_sources: list[str] = field(default_factory=list)
    credibility_note: str = ""

    @classmethod
    def from_raw(cls, raw: RawArticle, **kwargs: Any) -> VerifiedArticle:
        return cls(**{**raw.to_dict(), **kwargs})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerifiedArticle:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── AnalyzedArticle (Bias Analyst 출력) ──────────────────────────────

@dataclass
class AnalyzedArticle(VerifiedArticle):
    source_bias: str = "center"
    source_reliability: int = 50
    content_bias_score: int = 50
    objectivity_score: int = 50
    bias_analysis_note: str = ""
    framing_comparison: str = ""

    @classmethod
    def from_verified(cls, v: VerifiedArticle, **kwargs: Any) -> AnalyzedArticle:
        return cls(**{**v.to_dict(), **kwargs})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalyzedArticle:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── TimelineEvent ────────────────────────────────────────────────────

@dataclass
class TimelineEvent:
    event_id: str
    date: str
    title: str
    summary: str
    importance: str = "minor"
    objectivity_avg: int = 0
    causally_related_to: list[str] = field(default_factory=list)
    articles: list[AnalyzedArticle] = field(default_factory=list)
    market_impact: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineEvent:
        data = dict(data)
        articles_data = data.pop("articles", [])
        articles = [AnalyzedArticle.from_dict(a) for a in articles_data]
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**filtered, articles=articles)


# ── TimelineResult (최종 출력) ───────────────────────────────────────

@dataclass
class TimelineResult:
    version: str = "2.0.0"
    topic: str = ""
    generated_at: str = field(default_factory=_now_iso)
    date_range: dict[str, str] = field(default_factory=lambda: {"from": "", "to": ""})
    total_events: int = 0
    total_articles: int = 0
    events: list[TimelineEvent] = field(default_factory=list)
    last_updated: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineResult:
        data = dict(data)
        events_data = data.pop("events", [])
        events = [TimelineEvent.from_dict(e) for e in events_data]
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**filtered, events=events)

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
