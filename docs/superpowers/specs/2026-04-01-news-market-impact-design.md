# News-Market Impact Timeline — 설계 문서

**날짜:** 2026-04-01
**상태:** 승인 대기

---

## 1. 프로젝트 개요

특정 뉴스 이벤트가 금융 시장(유가선물·BTC·나스닥·코스닥 등)에 미치는 영향을 시각화하는 타임라인 뷰어.
DB 없이 로컬 JSON으로 저장하며, 파일을 공유하면 다른 사용자도 동일하게 열람 가능.
모든 연산은 Claude Code 메모리 내에서 처리하고 결과만 파일로 저장한다.

---

## 2. 아키텍처

### 2.1 디렉토리 구조

```
data/
├── registry.json              # 카테고리 목록 + 메타
├── iran-war/
│   ├── config.json            # 지표 정의, 태그 목록
│   ├── news.json              # 뉴스 타임라인 (이벤트 + 기사)
│   └── market.json            # 일봉 OHLCV + 분봉 윈도우
└── {category-slug}/           # 추후 카테고리
    ├── config.json
    ├── news.json
    └── market.json

agents/                        # Claude Code 에이전트 역할 정의
docs/
fetch_market.py                # yfinance 시장 데이터 수집 (Python 유일)
viewer.html                    # 정적 HTML 뷰어
CLAUDE.md                      # 워크플로우 강제 규칙
```

### 2.2 기술 스택

| 역할 | 수단 |
|------|------|
| 뉴스 수집/분석/번역 | Claude Code (메모리 처리) |
| 시장 데이터 수집 | `fetch_market.py` (yfinance) |
| 저장 형식 | JSON (DB 없음) |
| 시각화 | 정적 `viewer.html` |

---

## 3. 데이터 스키마

### 3.1 registry.json

```json
{
  "categories": [
    {
      "slug": "iran-war",
      "name": "이란-이스라엘 전쟁",
      "created_at": "2026-03-01T00:00:00Z",
      "last_updated": "2026-04-01T12:00:00Z"
    }
  ]
}
```

### 3.2 config.json (카테고리별)

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
  "tags": ["미국", "이란", "이스라엘", "후티", "핵", "미사일"]
}
```

### 3.3 news.json (이벤트 + 기사)

```json
{
  "version": "2.0.0",
  "topic": "이란 이스라엘 미국 전쟁",
  "generated_at": "2026-04-01T15:00:00Z",
  "date_range": { "from": "2026-03-01", "to": "2026-04-01" },
  "total_events": 12,
  "total_articles": 100,
  "events": [
    {
      "event_id": "evt-001",
      "date": "2026-03-28",
      "time": "08:00:00Z",
      "title": "미국-이스라엘 연합, 이란 이스파한 핵시설 공습",
      "summary": "미국과 이스라엘이 이란 이스파한 우라늄 농축 시설에 공습 감행.",
      "importance": "critical",
      "objectivity_avg": 78,
      "causally_related_to": ["evt-002"],
      "market_impact": {
        "W": { "delta_pct": 4.2, "window_start": "07:30:00Z", "window_end": "08:05:00Z" },
        "C": { "delta_pct": -2.1, "window_start": "07:30:00Z", "window_end": "08:05:00Z" },
        "N": { "delta_pct": -1.8, "window_start": "07:30:00Z", "window_end": "08:05:00Z" },
        "K": { "delta_pct": -0.9, "window_start": "07:30:00Z", "window_end": "08:05:00Z" }
      },
      "articles": [
        {
          "id": "art-001",
          "title": "US-Israeli strikes hit Iran nuclear facilities",
          "title_ko": "미국-이스라엘, 이란 핵시설 공습",
          "source": "Reuters",
          "url": "https://reuters.com/...",
          "published_date": "2026-03-28T08:00:00Z",
          "summary_ko": "...",
          "view_count": 125000,
          "verification_status": "verified",
          "corroboration_count": 5,
          "corroborating_sources": ["AP", "BBC", "Al Jazeera"],
          "credibility_note": "복수 주요 매체 교차 확인",
          "source_bias": "center",
          "objectivity_score": 92,
          "bias_analysis_note": "사실 중심, 양측 입장 균형"
        }
      ]
    }
  ]
}
```

### 3.4 market.json

```json
{
  "generated_at": "2026-04-01T15:00:00Z",
  "tickers": {
    "CL=F": {
      "daily": [
        { "date": "2026-03-27", "open": 71.2, "high": 72.5, "low": 70.8, "close": 71.9, "volume": 420000 },
        { "date": "2026-03-28", "open": 71.9, "high": 76.3, "low": 71.5, "close": 75.8, "volume": 890000 }
      ],
      "windows": {
        "evt-001": {
          "bars": [
            { "time": "2026-03-28T07:30:00Z", "open": 71.9, "high": 72.1, "low": 71.8, "close": 72.0 },
            { "time": "2026-03-28T07:31:00Z", "open": 72.0, "high": 73.5, "low": 72.0, "close": 73.4 }
          ],
          "baseline_close": 71.9,
          "delta_pct": 4.2
        }
      }
    }
  }
}
```

---

## 4. 에이전트 팀

각 에이전트는 **입력/출력 타입 고정**, **타 에이전트 결과 수정 불가 (읽기 전용)**, **역할 외 작업 금지**.

| 에이전트 | 입력 | 출력 | 금지 사항 |
|----------|------|------|-----------|
| **Orchestrator** | 사용자 명령 | 태스크 분배 | 직접 수집/분석 금지 |
| **Collector** | topic, date_range | RawArticle[] | 판단·번역·분석 금지 |
| **Verifier-A** | RawArticle[] | ClaimsReport (주장 목록 + 초기 검토) | 최종 판정 금지 |
| **Verifier-B** | ClaimsReport | ChallengeReport (반박·상충 정보) | A 결과 수정 금지, 독립 컨텍스트 유지 |
| **Arbiter** | ClaimsReport + ChallengeReport | VerifiedArticle[] (신뢰도 점수 확정) | 새 수집 금지 |
| **Bias-Analyst** | VerifiedArticle[] | AnalyzedArticle[] | 검증 결과 수정 금지 |
| **Timeline-Builder** | AnalyzedArticle[] | news.json | 분석 재수행 금지 |
| **Market-Fetcher** | config.json + event times | market.json | fetch_market.py 호출만 |

---

## 5. CLI 워크플로우

### 5.1 새 카테고리 크롤링

```
사용자: "이란 전쟁 크롤링 해줘"
  → Orchestrator: 카테고리 슬러그·이름 확인
  → 시작 날짜 선택 (입력 받음, 종료는 오늘 강제)
  → config.json + registry.json 생성
  → 에이전트 팀 순차 실행
  → news.json 저장
  → fetch_market.py 실행 → market.json 저장
```

### 5.2 업데이트

```
사용자: "이란 전쟁 업데이트 해줘"
  → Orchestrator: news.json의 last_updated 확인
  → 해당 시각 이후 기사만 수집
  → 에이전트 팀 실행 (증분)
  → news.json 머지 저장
  → market.json 업데이트
```

---

## 6. viewer.html 변경 사항

- **왼쪽 상단**: `registry.json` 읽어 카테고리 스위처 렌더링 (카테고리별 지표 동적 변경)
- **카드 레이아웃**:
  ```
  [시간] [출처라벨1] [출처라벨2]
  헤드라인
  본문 요약
  [W +4.2%] [C -2.1%] [N -1.8%] [K -0.9%]
  ```
- **일별 헤더**: 해당 날의 시장 일봉 요약 표시
- **상세보기**:
  - 출처 목록: [제목][본문요약][조회수][출처 링크]
  - 전날 종가 + 당일 분봉 차트 (lightweight-charts 또는 순수 SVG)
- **지표 범례**: 왼쪽 상단 타이틀 옆에 W/C/N/K 설명 고정

---

## 7. CLAUDE.md 강제 규칙 (추가 예정)

- 크롤링/업데이트 요청 시 **반드시 에이전트 팀 구성 후 진행** (직접 처리 금지)
- 각 에이전트는 **역할 정의서(AGENTS.md) 준수**
- 번역은 **Claude Code 직접 수행** (외부 API 호출 금지)
- 시장 데이터는 **fetch_market.py 경유** (yfinance 직접 호출 금지)

---

## 8. 미결 사항

- 차트 라이브러리: lightweight-charts vs 순수 SVG (viewer.html 구현 시 결정)
- 코스닥 시간대: KST ↔ UTC 변환 로직 fetch_market.py에서 처리
- 분봉 데이터 보존 기간: yfinance 1분봉은 최근 30일 제한 → 수집 후 즉시 저장
