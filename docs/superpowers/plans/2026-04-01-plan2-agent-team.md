# Agent Team + Market Fetcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 에이전트 팀(Verifier-A/B, Arbiter, Orchestrator) 구축 + fetch_market.py + main.py 업데이트.

**Architecture:** 기존 verifier.py를 Verifier-A(주장 추출)·Verifier-B(반박)·Arbiter(조정) 3단계로 분리. Orchestrator가 전체 파이프라인 조율. main.py에 `--category`, `--update`, `--date-from` 플래그 추가.

**Tech Stack:** Python 3.11, yfinance, dataclasses, argparse

**선행 조건:** Plan 1 완료 (models/schema.py v2.0.0, data/ 구조)

---

### Task 1: fetch_market.py — yfinance 시장 데이터 수집

**Files:**
- Create: `fetch_market.py`
- Test: `tests/test_fetch_market.py`

- [ ] **Step 1: yfinance 설치 확인**

```bash
pip install yfinance && python -c "import yfinance; print('yfinance OK')"
```
Expected: yfinance OK

- [ ] **Step 2: 실패 테스트 작성**

```python
# tests/test_fetch_market.py
import json
from unittest.mock import patch, MagicMock
from fetch_market import build_market_json, calc_window_delta

def test_calc_window_delta_positive():
    bars = [
        {"time": "2026-03-28T07:30:00Z", "close": 71.9},
        {"time": "2026-03-28T07:31:00Z", "close": 72.5},
        {"time": "2026-03-28T08:05:00Z", "close": 74.9},
    ]
    delta = calc_window_delta(bars, baseline=71.9)
    assert abs(delta - ((74.9 - 71.9) / 71.9 * 100)) < 0.01

def test_calc_window_delta_empty_returns_zero():
    assert calc_window_delta([], baseline=100.0) == 0.0

def test_build_market_json_structure():
    """market.json 최상위 구조 검증."""
    result = build_market_json(
        tickers={"CL=F": {"daily": [], "windows": {}}},
        generated_at="2026-04-01T00:00:00Z"
    )
    assert "generated_at" in result
    assert "tickers" in result
    assert "CL=F" in result["tickers"]
```

- [ ] **Step 3: 테스트 실패 확인**

```bash
python -m pytest tests/test_fetch_market.py -v 2>&1 | head -20
```
Expected: FAIL

- [ ] **Step 4: fetch_market.py 구현**

```python
#!/usr/bin/env python3
"""fetch_market.py — yfinance로 카테고리별 시장 데이터를 수집한다."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yfinance as yf


# ── 유틸 ────────────────────────────────────────────────────────────

def calc_window_delta(bars: list[dict], baseline: float) -> float:
    """분봉 리스트에서 baseline 대비 마지막 종가의 변화율(%)을 반환한다."""
    if not bars or baseline == 0:
        return 0.0
    last_close = bars[-1]["close"]
    return round((last_close - baseline) / baseline * 100, 4)


def build_market_json(tickers: dict, generated_at: str) -> dict:
    return {"generated_at": generated_at, "tickers": tickers}


def _fetch_daily(ticker: str, date_from: str, date_to: str) -> list[dict]:
    """일봉 OHLCV를 반환한다."""
    t = yf.Ticker(ticker)
    df = t.history(start=date_from, end=date_to, interval="1d")
    if df.empty:
        return []
    rows = []
    for ts, row in df.iterrows():
        rows.append({
            "date": ts.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "volume": int(row["Volume"]),
        })
    return rows


def _fetch_minute_window(ticker: str, event_time: str) -> list[dict]:
    """이벤트 시각 -30분 ~ +5분 분봉을 반환한다.

    yfinance 1분봉은 최근 30일치만 지원한다. 30일 초과 이벤트는 빈 리스트.
    """
    try:
        dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
    except ValueError:
        return []

    now = datetime.now(timezone.utc)
    if (now - dt).days > 29:
        return []  # yfinance 제한

    w_start = dt - timedelta(minutes=30)
    w_end   = dt + timedelta(minutes=6)   # +1분 여유

    t = yf.Ticker(ticker)
    df = t.history(
        start=w_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end=w_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        interval="1m",
    )
    if df.empty:
        return []

    bars = []
    for ts, row in df.iterrows():
        bars.append({
            "time": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
        })
    return bars


# ── 공개 API ─────────────────────────────────────────────────────────

def fetch_category_market(category_slug: str, incremental: bool = False) -> None:
    """카테고리 config.json + news.json을 읽어 market.json을 생성/업데이트한다."""
    base = Path("data") / category_slug
    config = json.loads((base / "config.json").read_text(encoding="utf-8"))
    news   = json.loads((base / "news.json").read_text(encoding="utf-8"))

    markets = config["markets"]   # [{key, label, ticker}, ...]
    events  = news["events"]
    date_from = news["date_range"]["from"]
    date_to   = news["date_range"]["to"]

    # 기존 market.json 로드 (incremental 모드)
    market_path = base / "market.json"
    existing: dict = {}
    if incremental and market_path.exists():
        existing = json.loads(market_path.read_text(encoding="utf-8"))

    tickers_data: dict = existing.get("tickers", {})

    for mkt in markets:
        ticker = mkt["ticker"]
        print(f"  [{ticker}] 일봉 수집 중...")
        daily = _fetch_daily(ticker, date_from, date_to)

        windows: dict = tickers_data.get(ticker, {}).get("windows", {})

        for evt in events:
            evt_id   = evt["event_id"]
            evt_time = evt.get("date", "") + "T00:00:00Z"  # 시간 없으면 자정

            # articles에서 가장 이른 published_date 사용
            times = [a["published_date"] for a in evt.get("articles", []) if a.get("published_date")]
            if times:
                evt_time = sorted(times)[0]

            if evt_id in windows and incremental:
                continue  # 이미 수집됨

            print(f"    [{ticker}] 이벤트 {evt_id} 분봉 윈도우 수집 중...")
            bars = _fetch_minute_window(ticker, evt_time)

            # 전날 종가 = baseline
            baseline_close = 0.0
            if daily:
                evt_date = evt_time[:10]
                prev = [d for d in daily if d["date"] < evt_date]
                if prev:
                    baseline_close = prev[-1]["close"]

            delta = calc_window_delta(bars, baseline_close) if bars else 0.0

            windows[evt_id] = {
                "event_time": evt_time,
                "bars": bars,
                "baseline_close": baseline_close,
                "delta_pct": delta,
            }

            # news.json의 market_impact 업데이트
            for e in events:
                if e["event_id"] == evt_id:
                    if "market_impact" not in e:
                        e["market_impact"] = {}
                    e["market_impact"][mkt["key"]] = {
                        "delta_pct": delta,
                        "window_start": evt_time,
                        "window_end": evt_time,
                    }

        tickers_data[ticker] = {"daily": daily, "windows": windows}

    # market.json 저장
    market_json = build_market_json(tickers_data, datetime.now(timezone.utc).isoformat())
    market_path.write_text(json.dumps(market_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  market.json 저장: {market_path}")

    # news.json market_impact 업데이트 반영
    (base / "news.json").write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  news.json market_impact 업데이트 저장")


def main() -> None:
    parser = argparse.ArgumentParser(description="시장 데이터 수집기")
    parser.add_argument("--category", required=True, help="카테고리 슬러그 (예: iran-war)")
    parser.add_argument("--incremental", action="store_true", help="증분 업데이트 (기존 윈도우 유지)")
    args = parser.parse_args()

    print(f"=== Market Fetcher: {args.category} ===")
    fetch_category_market(args.category, incremental=args.incremental)
    print("=== 완료 ===")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
python -m pytest tests/test_fetch_market.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 6: 커밋**

```bash
git add fetch_market.py tests/test_fetch_market.py
git commit -m "feat: add fetch_market.py with yfinance daily/minute data collection"
```

---

### Task 2: agents/verifier_a.py — 주장 추출 + 클러스터링

**Files:**
- Create: `agents/verifier_a.py`
- Test: `tests/test_verifier_a.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_verifier_a.py
from agents.verifier_a import extract_claims
from models.schema import RawArticle

def _make_article(id, title, source="Reuters"):
    return RawArticle(
        id=id, title=title, title_ko=title, source=source,
        url=f"https://example.com/{id}", published_date="2026-03-28T08:00:00Z",
        summary="", summary_ko="", search_keyword="test"
    )

def test_extract_claims_returns_claims_report():
    articles = [
        _make_article("art-001", "US strikes Iran nuclear facility"),
        _make_article("art-002", "US strikes Iran nuclear facility", "AP"),
        _make_article("art-003", "Yemen Houthis fire missiles at Israel"),
    ]
    report = extract_claims(articles)
    assert "clusters" in report
    assert "claims" in report
    assert len(report["clusters"]) >= 2  # 두 클러스터

def test_extract_claims_groups_similar_titles():
    articles = [
        _make_article("art-001", "US and Israel strike Iran missile sites"),
        _make_article("art-002", "US Israel strike Iran missile sites Reuters"),
    ]
    report = extract_claims(articles)
    # 두 기사가 같은 클러스터에 묶여야 함
    cluster_sizes = [len(c["article_ids"]) for c in report["clusters"]]
    assert max(cluster_sizes) >= 2
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_verifier_a.py -v 2>&1 | head -20
```
Expected: FAIL

- [ ] **Step 3: agents/verifier_a.py 구현**

```python
"""agents/verifier_a.py — Verifier-A: 핵심 주장 추출 + 클러스터링 + 초기 검토."""
from __future__ import annotations

import re
import uuid
from models.schema import RawArticle

SENSATIONAL = re.compile(
    r"\b(BREAKING|SHOCKING|EXPLOSIVE|EXCLUSIVE|URGENT|BOMBSHELL|"
    r"breaking|shocking|explosive|exclusive|urgent|bombshell)\b"
)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def extract_claims(articles: list[RawArticle], threshold: float = 0.35) -> dict:
    """RawArticle 목록에서 ClaimsReport를 생성한다.

    Returns:
        {
            "clusters": [
                {
                    "cluster_id": str,
                    "article_ids": [str, ...],
                    "sources": [str, ...],
                    "representative_title": str,
                }
            ],
            "claims": {
                article_id: {
                    "cluster_id": str,
                    "is_sensational": bool,
                    "initial_status": str,  # "likely_verified"|"unverified"|"suspicious"
                    "note": str,
                }
            }
        }
    """
    # 클러스터링
    clusters: list[tuple[str, set[str], list[RawArticle]]] = []
    for art in articles:
        tokens = _tokenize(art.title)
        matched = False
        for cid, rep_tokens, members in clusters:
            if _jaccard(tokens, rep_tokens) > threshold:
                members.append(art)
                rep_tokens.update(tokens)
                matched = True
                break
        if not matched:
            cid = f"evt-{uuid.uuid4().hex[:8]}"
            clusters.append((cid, tokens, [art]))

    # ClaimsReport 빌드
    cluster_list = []
    claims = {}

    for cid, _, members in clusters:
        sources = list({m.source for m in members})
        cluster_list.append({
            "cluster_id": cid,
            "article_ids": [m.id for m in members],
            "sources": sources,
            "representative_title": members[0].title,
        })

        for art in members:
            sensational = bool(SENSATIONAL.search(art.title) or SENSATIONAL.search(art.summary))
            if len(sources) >= 2:
                status = "likely_verified"
            elif sensational:
                status = "suspicious"
            else:
                status = "unverified"

            note_parts = []
            if len(sources) >= 2:
                note_parts.append(f"{len(sources)}개 매체 보도 확인")
            else:
                note_parts.append("단독 보도")
            if sensational:
                note_parts.append("선정적 표현 감지")

            claims[art.id] = {
                "cluster_id": cid,
                "is_sensational": sensational,
                "initial_status": status,
                "note": ". ".join(note_parts),
            }

    return {"clusters": cluster_list, "claims": claims}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_verifier_a.py -v
```
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add agents/verifier_a.py tests/test_verifier_a.py
git commit -m "feat: add Verifier-A (claims extraction + clustering)"
```

---

### Task 3: agents/verifier_b.py — 독립적 반박 검토

**Files:**
- Create: `agents/verifier_b.py`
- Test: `tests/test_verifier_b.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_verifier_b.py
from agents.verifier_b import challenge_claims

def test_challenge_claims_returns_challenge_report():
    claims_report = {
        "clusters": [
            {
                "cluster_id": "evt-001",
                "article_ids": ["art-001"],
                "sources": ["Reuters"],
                "representative_title": "US strikes Iran",
            }
        ],
        "claims": {
            "art-001": {
                "cluster_id": "evt-001",
                "is_sensational": False,
                "initial_status": "unverified",
                "note": "단독 보도",
            }
        }
    }
    report = challenge_claims(claims_report)
    assert "challenges" in report
    assert "art-001" in report["challenges"]
    assert "challenge_note" in report["challenges"]["art-001"]

def test_challenge_single_source_flags_lower_confidence():
    claims_report = {
        "clusters": [{"cluster_id": "c1", "article_ids": ["a1"], "sources": ["Unknown"], "representative_title": "BREAKING shocking news"}],
        "claims": {"a1": {"cluster_id": "c1", "is_sensational": True, "initial_status": "suspicious", "note": "선정적"}}
    }
    report = challenge_claims(claims_report)
    assert report["challenges"]["a1"]["confidence"] < 50
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_verifier_b.py -v 2>&1 | head -20
```
Expected: FAIL

- [ ] **Step 3: agents/verifier_b.py 구현**

```python
"""agents/verifier_b.py — Verifier-B: 독립적 반박 검토 (A와 독립 컨텍스트 유지).

역할: Verifier-A의 ClaimsReport를 받아 각 주장에 대해 반박을 시도한다.
     A와 동일한 결론에 도달하면 안 되며, 상충 가능성과 약점을 찾는다.
"""
from __future__ import annotations


def challenge_claims(claims_report: dict) -> dict:
    """ClaimsReport를 받아 ChallengeReport를 반환한다.

    각 기사에 대해:
    - 단독 출처인 경우 신뢰도 패널티
    - 선정적 언어가 있는 경우 추가 패널티
    - 알려진 편향 매체인 경우 패널티
    - 복수 독립 출처이면 보너스

    Returns:
        {
            "challenges": {
                article_id: {
                    "challenge_note": str,
                    "confidence": int,   # 0-100 (높을수록 신뢰)
                    "flags": [str, ...]  # 발견된 문제점 목록
                }
            }
        }
    """
    # 편향 위험 매체 목록 (신뢰도 패널티 적용)
    HIGH_BIAS_SOURCES = {"RT", "Sputnik", "IRNA", "Press TV", "ZeroHedge"}
    RELIABLE_SOURCES  = {"Reuters", "Associated Press", "AP", "BBC News", "BBC"}

    challenges: dict = {}

    cluster_map = {c["cluster_id"]: c for c in claims_report.get("clusters", [])}

    for art_id, claim in claims_report.get("claims", {}).items():
        cluster = cluster_map.get(claim["cluster_id"], {})
        sources = cluster.get("sources", [])
        flags: list[str] = []
        confidence = 50  # 기본값

        # 복수 독립 출처 보너스
        reliable_count = sum(1 for s in sources if s in RELIABLE_SOURCES)
        if reliable_count >= 2:
            confidence += 25
        elif len(sources) >= 3:
            confidence += 15
        elif len(sources) >= 2:
            confidence += 10

        # 단독 출처 패널티
        if len(sources) == 1:
            confidence -= 20
            flags.append("단독 출처 — 독립 확인 불가")

        # 선정적 언어 패널티
        if claim.get("is_sensational"):
            confidence -= 15
            flags.append("선정적 표현 감지 — 과장 가능성")

        # 편향 매체 패널티
        biased = [s for s in sources if s in HIGH_BIAS_SOURCES]
        if biased:
            confidence -= 10
            flags.append(f"편향 위험 매체 포함: {', '.join(biased)}")

        # 신뢰 매체만 있으면 보너스
        if reliable_count >= 1 and not biased:
            confidence += 5

        confidence = max(0, min(100, confidence))

        note_parts = flags if flags else ["반박 근거 없음 — 기본 신뢰"]
        challenges[art_id] = {
            "challenge_note": ". ".join(note_parts),
            "confidence": confidence,
            "flags": flags,
        }

    return {"challenges": challenges}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_verifier_b.py -v
```
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add agents/verifier_b.py tests/test_verifier_b.py
git commit -m "feat: add Verifier-B (independent challenge with confidence scoring)"
```

---

### Task 4: agents/arbiter.py — A·B 조정 + 최종 검증 판정

**Files:**
- Create: `agents/arbiter.py`
- Test: `tests/test_arbiter.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_arbiter.py
from agents.arbiter import arbitrate
from models.schema import RawArticle

def _make_article(id, title, source="Reuters"):
    return RawArticle(
        id=id, title=title, title_ko=title, source=source,
        url=f"https://example.com/{id}", published_date="2026-03-28T08:00:00Z",
        summary="", summary_ko="", search_keyword="test"
    )

def test_arbitrate_returns_verified_articles():
    from models.schema import VerifiedArticle
    arts = [_make_article("a1", "US strikes Iran", "Reuters")]
    claims = {
        "clusters": [{"cluster_id": "c1", "article_ids": ["a1"], "sources": ["Reuters"], "representative_title": "US strikes Iran"}],
        "claims": {"a1": {"cluster_id": "c1", "is_sensational": False, "initial_status": "unverified", "note": "단독"}}
    }
    challenges = {"challenges": {"a1": {"challenge_note": "단독 출처", "confidence": 30, "flags": ["단독 출처"]}}}
    result = arbitrate(arts, claims, challenges)
    assert len(result) == 1
    assert isinstance(result[0], VerifiedArticle)
    assert result[0].verification_status in ("verified", "unverified", "flagged")

def test_arbitrate_verified_when_high_confidence():
    arts = [_make_article("a1", "US strikes Iran", "Reuters"), _make_article("a2", "US strikes Iran nuclear", "AP")]
    claims = {
        "clusters": [{"cluster_id": "c1", "article_ids": ["a1","a2"], "sources": ["Reuters","AP"], "representative_title": "US strikes Iran"}],
        "claims": {
            "a1": {"cluster_id": "c1", "is_sensational": False, "initial_status": "likely_verified", "note": "2개 매체"},
            "a2": {"cluster_id": "c1", "is_sensational": False, "initial_status": "likely_verified", "note": "2개 매체"},
        }
    }
    challenges = {
        "challenges": {
            "a1": {"challenge_note": "반박 없음", "confidence": 80, "flags": []},
            "a2": {"challenge_note": "반박 없음", "confidence": 80, "flags": []},
        }
    }
    result = arbitrate(arts, claims, challenges)
    assert all(r.verification_status == "verified" for r in result)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_arbiter.py -v 2>&1 | head -20
```
Expected: FAIL

- [ ] **Step 3: agents/arbiter.py 구현**

```python
"""agents/arbiter.py — Arbiter: Verifier-A·B 조정 + 최종 검증 판정."""
from __future__ import annotations

from models.schema import RawArticle, VerifiedArticle


def arbitrate(
    articles: list[RawArticle],
    claims_report: dict,
    challenge_report: dict,
) -> list[VerifiedArticle]:
    """A(주장)와 B(반박)를 종합해 최종 VerifiedArticle 목록을 반환한다.

    판정 기준:
    - confidence >= 70 → "verified"
    - confidence < 40 or flags가 2개 이상 → "flagged"
    - 그 외 → "unverified"
    """
    art_map = {a.id: a for a in articles}
    claims    = claims_report.get("claims", {})
    challenges = challenge_report.get("challenges", {})
    clusters   = {c["cluster_id"]: c for c in claims_report.get("clusters", [])}

    results: list[VerifiedArticle] = []

    for art in articles:
        claim = claims.get(art.id, {})
        challenge = challenges.get(art.id, {})

        cluster_id = claim.get("cluster_id", "")
        cluster    = clusters.get(cluster_id, {})
        sources    = cluster.get("sources", [art.source])

        confidence = challenge.get("confidence", 50)
        flags      = challenge.get("flags", [])

        # 최종 판정
        if confidence >= 70:
            status = "verified"
        elif confidence < 40 or len(flags) >= 2:
            status = "flagged"
        else:
            status = "unverified"

        # 신뢰도 메모 합성
        a_note = claim.get("note", "")
        b_note = challenge.get("challenge_note", "")
        note   = f"[A] {a_note} / [B] {b_note} / 최종 신뢰도: {confidence}/100"

        corroborating = [s for s in sources if s != art.source]

        verified = VerifiedArticle.from_raw(
            art,
            event_cluster_id=cluster_id,
            verification_status=status,
            corroboration_count=len(sources),
            corroborating_sources=corroborating,
            credibility_note=note,
        )
        results.append(verified)

    return results
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_arbiter.py -v
```
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add agents/arbiter.py tests/test_arbiter.py
git commit -m "feat: add Arbiter (A/B reconciliation + final verification judgment)"
```

---

### Task 5: agents/orchestrator.py + main.py 업데이트

**Files:**
- Create: `agents/orchestrator.py`
- Modify: `main.py`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_orchestrator.py
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from agents.orchestrator import run_pipeline_for_category

def test_run_pipeline_requires_category_slug(tmp_path):
    """category_slug 없으면 ValueError."""
    import pytest
    with pytest.raises(ValueError, match="category_slug"):
        run_pipeline_for_category(category_slug="", topic="test", date_from="2026-01-01")

def test_run_pipeline_creates_news_json(tmp_path, monkeypatch):
    """파이프라인 실행 후 news.json이 생성되어야 한다."""
    # data/ 디렉토리를 tmp_path 아래로 리다이렉트
    cat_dir = tmp_path / "data" / "test-cat"
    cat_dir.mkdir(parents=True)
    (cat_dir / "config.json").write_text(json.dumps({
        "name": "테스트", "topic": "test",
        "markets": [{"key": "N", "label": "나스닥", "ticker": "^IXIC"}],
        "tags": []
    }), encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    mock_articles = []
    mock_timeline = MagicMock()
    mock_timeline.to_dict.return_value = {
        "version": "2.0.0", "topic": "test",
        "generated_at": "2026-01-01T00:00:00Z",
        "last_updated": "2026-01-01T00:00:00Z",
        "date_range": {"from": "2026-01-01", "to": "2026-01-31"},
        "total_events": 0, "total_articles": 0, "events": []
    }

    with patch("agents.orchestrator.collect_articles", return_value=mock_articles), \
         patch("agents.orchestrator.extract_claims", return_value={"clusters": [], "claims": {}}), \
         patch("agents.orchestrator.challenge_claims", return_value={"challenges": {}}), \
         patch("agents.orchestrator.arbitrate", return_value=[]), \
         patch("agents.orchestrator.analyze_bias", return_value=[]), \
         patch("agents.orchestrator.build_timeline", return_value=mock_timeline):
        run_pipeline_for_category(
            category_slug="test-cat",
            topic="test topic",
            date_from="2026-01-01",
        )

    assert (cat_dir / "news.json").exists()
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_orchestrator.py -v 2>&1 | head -20
```
Expected: FAIL

- [ ] **Step 3: agents/orchestrator.py 구현**

```python
"""agents/orchestrator.py — 에이전트 팀 파이프라인 조율."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agents.collector import collect_articles
from agents.verifier_a import extract_claims
from agents.verifier_b import challenge_claims
from agents.arbiter import arbitrate
from agents.bias_analyst import analyze_bias
from agents.timeline_builder import build_timeline

logger = logging.getLogger(__name__)


def _load_config(category_slug: str) -> dict:
    path = Path("data") / category_slug / "config.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    # config.yaml 없으면 config.yaml 루트 사용
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_category_config(category_slug: str) -> dict:
    path = Path("data") / category_slug / "config.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_news_json(category_slug: str, timeline_dict: dict) -> Path:
    out = Path("data") / category_slug / "news.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(timeline_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def run_pipeline_for_category(
    category_slug: str,
    topic: str,
    date_from: str,
    date_to: str | None = None,
    debug: bool = False,
) -> Path:
    """에이전트 팀을 순차 실행하고 data/{slug}/news.json을 저장한다.

    Args:
        category_slug: 카테고리 폴더명 (예: "iran-war")
        topic: 검색 주제 (예: "이란 이스라엘 미국 전쟁")
        date_from: 수집 시작 날짜 ISO 8601 (예: "2026-03-01")
        date_to: 수집 종료 날짜 (기본: 오늘)
        debug: True이면 debug/ 폴더에 중간 결과 저장

    Returns:
        저장된 news.json Path
    """
    if not category_slug:
        raise ValueError("category_slug is required")

    if date_to is None:
        date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    pipeline_config = _load_config(category_slug)
    pipeline_config.setdefault("collection", {})
    pipeline_config["collection"]["date_from"] = date_from
    pipeline_config["collection"]["date_to"] = date_to

    print(f"\n[1/6] 수집 중... (topic={topic}, {date_from} ~ {date_to})")
    raw_articles = collect_articles(topic, pipeline_config)
    print(f"  → {len(raw_articles)}건 수집")

    if not raw_articles:
        print("  수집 기사 없음. 빈 결과 저장.")
        cat_config = _load_category_config(category_slug)
        timeline = build_timeline([], topic)
        return _save_news_json(category_slug, timeline.to_dict())

    print(f"\n[2/6] Verifier-A: 주장 추출 중...")
    claims_report = extract_claims(raw_articles)
    print(f"  → 클러스터 {len(claims_report['clusters'])}개")

    print(f"\n[3/6] Verifier-B: 독립 반박 검토 중...")
    challenge_report = challenge_claims(claims_report)
    print(f"  → {len(challenge_report['challenges'])}건 검토")

    print(f"\n[4/6] Arbiter: 최종 검증 판정 중...")
    verified_articles = arbitrate(raw_articles, claims_report, challenge_report)
    verified_count = sum(1 for a in verified_articles if a.verification_status == "verified")
    flagged_count  = sum(1 for a in verified_articles if a.verification_status == "flagged")
    print(f"  → verified: {verified_count}, flagged: {flagged_count}")

    print(f"\n[5/6] 편향 분석 중...")
    analyzed_articles = analyze_bias(verified_articles, pipeline_config)
    avg_obj = sum(a.objectivity_score for a in analyzed_articles) // max(len(analyzed_articles), 1)
    print(f"  → 평균 객관도: {avg_obj}")

    print(f"\n[6/6] 타임라인 구축 중...")
    timeline = build_timeline(analyzed_articles, topic)
    print(f"  → {timeline.total_events}개 사건, {timeline.total_articles}건 기사")

    timeline_dict = timeline.to_dict()
    timeline_dict["last_updated"] = datetime.now(timezone.utc).isoformat()

    out_path = _save_news_json(category_slug, timeline_dict)
    print(f"\n  저장: {out_path}")
    return out_path
```

- [ ] **Step 4: main.py 업데이트** (`main.py` 전체를 아래로 교체)

```python
#!/usr/bin/env python3
"""News-Market Agent — 파이프라인 오케스트레이터 + CLI."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agents.orchestrator import run_pipeline_for_category
from utils.merge import merge_timelines, load_timeline, save_timeline


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
    parser.add_argument("--date-from", help="수집 시작 날짜 YYYY-MM-DD (기본: last_updated)")
    parser.add_argument("--update",  action="store_true", help="last_updated 이후 증분 업데이트")
    parser.add_argument("--name",    help="카테고리 표시 이름 (신규 시 사용)")
    parser.add_argument("--debug",   action="store_true")
    args = parser.parse_args()

    slug = args.category
    cat_dir = Path("data") / slug

    # 업데이트 모드
    if args.update:
        last = _get_last_updated(slug)
        if not last:
            print(f"오류: {slug} 카테고리 news.json 없음. --date-from으로 신규 수집하세요.")
            sys.exit(1)
        date_from = last[:10]
        topic = json.loads((cat_dir / "config.json").read_text())["topic"]
        print(f"=== 업데이트 모드: {slug} ({date_from} 이후) ===")
    else:
        # 신규 크롤링
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
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
python -m pytest tests/test_orchestrator.py -v
```
Expected: PASS

- [ ] **Step 6: 전체 테스트 통과 확인**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: 기존 테스트 포함 모두 PASS (또는 기존 실패는 기존 코드 문제)

- [ ] **Step 7: 커밋**

```bash
git add agents/orchestrator.py tests/test_orchestrator.py main.py
git commit -m "feat: add Orchestrator + update main.py with --category/--update flags"
```
