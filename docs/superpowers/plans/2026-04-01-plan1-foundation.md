# Foundation — Schema, Data Migration, Enforcement Rules

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 새 JSON 스키마(v2.0.0) 정의, 기존 데이터 마이그레이션, 에이전트 강제 규칙 문서화.

**Architecture:** `data/{category}/` 폴더 구조로 카테고리별 분리. `models/schema.py`에 MarketImpact 필드 추가. `utils/migrate.py`로 기존 `output/result.json`을 `data/iran-war/news.json`으로 변환.

**Tech Stack:** Python 3.11, dataclasses, json, pathlib

---

### Task 1: models/schema.py — MarketImpact + market_impact 필드 추가

**Files:**
- Modify: `models/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_schema.py 에 추가 (파일 없으면 새로 생성)
import pytest
from models.schema import MarketImpact, TimelineEvent, AnalyzedArticle

def test_market_impact_creation():
    mi = MarketImpact(key="W", delta_pct=4.2, window_start="2026-03-28T07:30:00Z", window_end="2026-03-28T08:05:00Z")
    assert mi.key == "W"
    assert mi.delta_pct == 4.2

def test_timeline_event_has_market_impact():
    evt = TimelineEvent(event_id="evt-001", date="2026-03-28", title="테스트", summary="요약")
    assert isinstance(evt.market_impact, dict)

def test_timeline_result_version_v2():
    from models.schema import TimelineResult
    r = TimelineResult()
    assert r.version == "2.0.0"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /mnt/d/develope/workspace/news && python -m pytest tests/test_schema.py -v 2>&1 | head -30
```
Expected: FAIL (MarketImpact not defined)

- [ ] **Step 3: models/schema.py 업데이트**

`models/schema.py` 전체를 아래 내용으로 교체:

```python
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
    # v2: 시장 영향 데이터 (key → MarketImpact)
    market_impact: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_schema.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: 커밋**

```bash
git add models/schema.py tests/test_schema.py
git commit -m "feat: add MarketImpact dataclass and market_impact field to TimelineEvent (schema v2.0.0)"
```

---

### Task 2: data/ 폴더 구조 + registry.json + iran-war/config.json 생성

**Files:**
- Create: `data/registry.json`
- Create: `data/iran-war/config.json`

- [ ] **Step 1: 디렉토리 생성**

```bash
mkdir -p /mnt/d/develope/workspace/news/data/iran-war
```

- [ ] **Step 2: data/registry.json 생성**

```json
{
  "categories": [
    {
      "slug": "iran-war",
      "name": "이란-이스라엘 전쟁",
      "created_at": "2026-04-01T00:00:00Z",
      "last_updated": "2026-04-01T00:00:00Z"
    }
  ]
}
```
파일 경로: `data/registry.json`

- [ ] **Step 3: data/iran-war/config.json 생성**

```json
{
  "name": "이란-이스라엘 전쟁",
  "topic": "이란 이스라엘 미국 전쟁",
  "markets": [
    { "key": "W", "label": "유가선물(WTI)", "ticker": "CL=F" },
    { "key": "C", "label": "BTC",           "ticker": "BTC-USD" },
    { "key": "N", "label": "나스닥",         "ticker": "^IXIC" },
    { "key": "K", "label": "코스닥",         "ticker": "^KQ11" }
  ],
  "tags": ["미국", "이란", "이스라엘", "후티", "핵", "미사일", "공습", "드론"]
}
```
파일 경로: `data/iran-war/config.json`

- [ ] **Step 4: 검증**

```bash
python -c "
import json
r = json.load(open('data/registry.json'))
c = json.load(open('data/iran-war/config.json'))
assert len(r['categories']) == 1
assert len(c['markets']) == 4
print('OK')
"
```
Expected: OK

- [ ] **Step 5: 커밋**

```bash
git add data/registry.json data/iran-war/config.json
git commit -m "feat: add data/ category structure with iran-war registry and config"
```

---

### Task 3: utils/migrate.py — output/result.json → data/iran-war/news.json

**Files:**
- Create: `utils/migrate.py`
- Test: `tests/test_migrate.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_migrate.py
import json, tempfile, os
from pathlib import Path
from utils.migrate import migrate_result_to_news

def test_migrate_adds_version_and_last_updated(tmp_path):
    src = tmp_path / "result.json"
    src.write_text(json.dumps({
        "version": "1.0.0",
        "topic": "테스트",
        "generated_at": "2026-03-01T00:00:00Z",
        "date_range": {"from": "2026-03-01", "to": "2026-03-31"},
        "total_events": 1,
        "total_articles": 1,
        "events": [{
            "event_id": "evt-001",
            "date": "2026-03-28",
            "title": "테스트 이벤트",
            "summary": "요약",
            "importance": "major",
            "objectivity_avg": 75,
            "causally_related_to": [],
            "articles": []
        }]
    }, ensure_ascii=False))

    dst = tmp_path / "news.json"
    migrate_result_to_news(str(src), str(dst))

    result = json.loads(dst.read_text())
    assert result["version"] == "2.0.0"
    assert "last_updated" in result
    assert result["events"][0]["market_impact"] == {}

def test_migrate_preserves_articles(tmp_path):
    src = tmp_path / "result.json"
    src.write_text(json.dumps({
        "version": "1.0.0", "topic": "t", "generated_at": "2026-01-01T00:00:00Z",
        "date_range": {"from": "2026-01-01", "to": "2026-01-31"},
        "total_events": 1, "total_articles": 1,
        "events": [{
            "event_id": "e1", "date": "2026-01-01", "title": "T", "summary": "S",
            "importance": "minor", "objectivity_avg": 50,
            "causally_related_to": [], "articles": [{
                "id": "art-001", "title": "Article", "title_ko": "기사",
                "source": "Reuters", "url": "https://example.com",
                "published_date": "2026-01-01T00:00:00Z", "summary": "sum",
                "summary_ko": "요약", "search_keyword": "kw",
                "source_type": "news", "view_count": -1,
                "collected_at": "2026-01-01T00:00:00Z",
                "event_cluster_id": "e1", "verification_status": "verified",
                "corroboration_count": 2, "corroborating_sources": ["AP"],
                "credibility_note": "ok", "source_bias": "center",
                "source_reliability": 90, "content_bias_score": 80,
                "objectivity_score": 85, "bias_analysis_note": "n",
                "framing_comparison": "f"
            }]
        }]
    }, ensure_ascii=False))
    dst = tmp_path / "news.json"
    migrate_result_to_news(str(src), str(dst))
    result = json.loads(dst.read_text())
    assert result["total_articles"] == 1
    assert result["events"][0]["articles"][0]["id"] == "art-001"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_migrate.py -v 2>&1 | head -20
```
Expected: FAIL (migrate_result_to_news not defined)

- [ ] **Step 3: utils/migrate.py 구현**

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_migrate.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 5: 실제 마이그레이션 실행**

```bash
python -c "from utils.migrate import migrate_result_to_news; migrate_result_to_news('output/result.json', 'data/iran-war/news.json')"
```
Expected: "마이그레이션 완료: output/result.json → data/iran-war/news.json"

- [ ] **Step 6: 마이그레이션 결과 검증**

```bash
python -c "
import json
d = json.load(open('data/iran-war/news.json'))
print('version:', d['version'])
print('events:', d['total_events'])
print('articles:', d['total_articles'])
print('market_impact sample:', d['events'][0].get('market_impact'))
"
```
Expected: version 2.0.0, market_impact {}

- [ ] **Step 7: 커밋**

```bash
git add utils/migrate.py tests/test_migrate.py data/iran-war/news.json
git commit -m "feat: add migration util and migrate result.json to data/iran-war/news.json (v2.0.0)"
```

---

### Task 4: AGENTS.md 생성 — 각 에이전트 역할 계약서

**Files:**
- Create: `AGENTS.md`

- [ ] **Step 1: AGENTS.md 작성**

```markdown
# 에이전트 역할 계약서

> 이 문서는 CLAUDE.md의 강제 규칙과 함께 적용됩니다.
> 각 에이전트는 아래 계약을 위반하면 안 됩니다.

## Orchestrator (`agents/orchestrator.py`)
- **입력**: 사용자 명령 (category_slug, topic, date_from, mode)
- **출력**: 파이프라인 실행 결과 요약
- **역할**: 에이전트 팀 순서 조정, 중간 결과 전달
- **금지**: 직접 수집/번역/분석/판정 금지

## Collector (`agents/collector.py`)
- **입력**: topic, date_range, config
- **출력**: `list[RawArticle]`
- **역할**: RSS/웹 수집만. 판단 없음.
- **금지**: 번역·분석·검증·판정 금지

## Verifier-A (`agents/verifier_a.py`)
- **입력**: `list[RawArticle]`
- **출력**: `ClaimsReport` (주장 목록 + 클러스터 + 초기 검토)
- **역할**: 핵심 주장 추출, 클러스터링, 초기 신뢰도 평가
- **금지**: 최종 판정 금지. Verifier-B 결과 참조 금지.

## Verifier-B (`agents/verifier_b.py`)
- **입력**: `ClaimsReport` (Verifier-A 출력)
- **출력**: `ChallengeReport` (반박·상충 정보 목록)
- **역할**: A의 주장에 독립적으로 반박 시도, 상충 정보 탐색
- **금지**: A 결과 수정 금지. 독립 컨텍스트 유지 (A와 동일 판단 금지).

## Arbiter (`agents/arbiter.py`)
- **입력**: `ClaimsReport` + `ChallengeReport`
- **출력**: `list[VerifiedArticle]` (신뢰도 점수 확정)
- **역할**: A·B 불일치 조정, 최종 검증 상태 및 신뢰도 점수 결정
- **금지**: 새 수집·번역 금지.

## Bias-Analyst (`agents/bias_analyst.py`)
- **입력**: `list[VerifiedArticle]`
- **출력**: `list[AnalyzedArticle]`
- **역할**: 매체 편향도 조회, 기사 내용 편향 분석, 객관도 점수 산출
- **금지**: 검증 결과 수정 금지.

## Timeline-Builder (`agents/timeline_builder.py`)
- **입력**: `list[AnalyzedArticle]`, category_slug
- **출력**: `data/{category_slug}/news.json` 저장
- **역할**: 타임라인 구조화, 인과관계 태깅, 종합 요약 작성
- **금지**: 분석·검증 재수행 금지.

## Market-Fetcher (`fetch_market.py`)
- **입력**: category_slug (config.json + news.json 읽음)
- **출력**: `data/{category_slug}/market.json` 저장
- **역할**: yfinance로 일봉·분봉 수집, 이벤트별 윈도우 계산
- **금지**: 뉴스 데이터 수정 금지. yfinance 외 시장 데이터 소스 금지.
```

- [ ] **Step 2: 파일 저장 및 커밋**

```bash
git add AGENTS.md
git commit -m "docs: add AGENTS.md with per-agent role contracts"
```

---

### Task 5: CLAUDE.md 업데이트 — 에이전트 팀 강제 규칙

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: CLAUDE.md 하단에 아래 섹션 추가**

```markdown
---

## 에이전트 팀 강제 규칙

### 핵심 원칙 (위반 금지)
- **크롤링/업데이트 요청 시 절대 직접 처리 금지** — 반드시 에이전트 팀을 통해 처리한다.
- **번역은 Claude Code 직접 수행** — 외부 번역 API(deep_translator, Google Translate 등) 호출 금지.
- **시장 데이터는 fetch_market.py 경유** — yfinance 직접 호출 금지.
- **각 에이전트는 AGENTS.md의 역할 계약 준수** — 역할 외 작업 금지.

### "크롤링 해줘" 요청 시 워크플로우
1. 카테고리 슬러그/이름 확인 (없으면 생성)
2. 시작 날짜 입력 받기 (종료일은 오늘로 강제)
3. `data/{slug}/config.json` + `data/registry.json` 생성/업데이트
4. 에이전트 팀 순차 실행: Collector → Verifier-A → Verifier-B → Arbiter → Bias-Analyst → Timeline-Builder
5. `python fetch_market.py --category {slug}` 실행

### "업데이트 해줘" 요청 시 워크플로우
1. `data/{slug}/news.json`의 `last_updated` 읽기
2. 해당 시각 이후 기사만 수집 (date_from = last_updated)
3. 에이전트 팀 순차 실행 (증분)
4. news.json 머지 저장 (기존 이벤트 유지, 새 이벤트 추가)
5. `python fetch_market.py --category {slug} --incremental` 실행

### 새 카테고리 추가 시
- `data/{slug}/config.json`에 해당 카테고리에서 사용할 지표(markets) 정의
- `data/registry.json`의 categories 배열에 항목 추가
- viewer.html 코드 수정 불필요 (동적 로딩)
```

- [ ] **Step 2: 커밋**

```bash
git add CLAUDE.md
git commit -m "docs: add agent team enforcement rules to CLAUDE.md"
```
