# News-Market Impact Timeline — 운영 규칙

## 프로젝트 개요

특정 뉴스 이벤트가 금융 시장(유가선물·BTC·나스닥·코스닥 등)에 미치는 영향을
시각화하는 타임라인 시스템.

- **이벤트 출처**: 권위 있는 사이트 2개에서 사건 목록 추출 (config.json `authoritative_sources`)
- **보강 자료**: 각 사건에 트럼프 X 게시물 + 관련 뉴스 기사 연결
- **시장 데이터**: `fetch_market.py`를 통해 yfinance 조회 (Python 유일)
- **저장 형식**: JSON (DB 없음)
- **시각화**: `viewer.html` (정적 HTML)

---

## 디렉토리 구조

```
data/
├── registry.json
├── iran-war/
│   ├── config.json        # authoritative_sources(+parse_config), markets, enrichment_sources
│   ├── news.json          # 최종 타임라인
│   └── market.json        # 시장 데이터
agents/
├── site_analyzer.md       # 사이트 구조 분석 + 파싱 전략 수립 (Step 0.5)
├── site_fetcher.md        # 권위 사이트 파싱 (parse_config 기반)
├── event_merger.md        # 두 사이트 사건 병합
├── enricher.md            # 관련 기사 + 트럼프 게시물 연결
└── timeline_builder.md    # 최종 news.json 구성
pipeline/
└── {slug}/                # 카테고리별 파이프라인 중간 산출물
    ├── 01_site_events.json    ← Site-Fetcher
    ├── 02_merged_events.json  ← Event-Merger
    └── 03_enriched_events.json ← Enricher
fetch_market.py
viewer.html
```

---

## 핵심 원칙 (위반 금지)

1. **크롤링/업데이트 요청 시 절대 직접 처리 금지** — 반드시 아래 워크플로우대로 에이전트 팀 사용
2. **이벤트 spine은 authoritative_sources에서만** — 임의 뉴스 검색으로 이벤트 생성 금지
3. **관련 기사는 해당 특정 사건에만** — "전쟁 전반" 기사를 억지로 연결 금지
4. **번역은 Claude Code 직접** — 외부 번역 API 호출 금지
5. **시장 데이터는 fetch_market.py 경유** — yfinance 직접 호출 금지
6. **모든 텍스트 콘텐츠는 한국어 번역 필수** — 기사 제목/요약/트럼프 게시물 전부 `_ko` 필드 저장, 원문은 URL 링크로만 제공
7. **viewer.html은 순수 뷰어 — 연산 금지** — 모든 집계·계산은 Python에서 완료 후 JSON에 저장. HTML은 렌더링만.

---

## JSON 데이터 포맷 원칙

viewer.html이 연산 없이 바로 렌더링할 수 있도록, 모든 계산은 Python에서 완료한다.

### news.json 필수 필드
```json
{
  "by_date": { "2026-03-01": ["evt-001", "evt-002"] },  // build_timeline.py 생성
  "events": [
    {
      "event_id": "evt-001",
      "title": "한국어 제목",
      "summary": "한국어 요약",
      "importance": "critical|major|minor",
      "objectivity_avg": 85
    }
  ]
}
```

### market.json 필수 필드
```json
{
  "tickers": {
    "BTC-USD": {
      "daily": [
        { "date": "2026-03-01", "close": 85000, "delta_pct": 1.23 }
      ],
      "windows": {
        "evt-001": {
          "event_time": "2026-03-01T14:30:00Z",
          "bars10": [
            { "open": 84900, "high": 85100, "low": 84800, "close": 85000,
              "time": "2026-03-01T14:00:00Z", "label": "23:00", "isEvent": false },
            { "open": 85000, "high": 85300, "low": 84900, "close": 85200,
              "time": "2026-03-01T14:30:00Z", "label": "23:30", "isEvent": true }
          ],
          "delta_pct": 0.47
        }
      }
    }
  }
}
```

**규칙:**
- `delta_pct` (일봉): 전일 종가 대비 등락률 → `fetch_market.py`가 계산
- `bars10`: 5분봉을 10분봉으로 집계, KST label 포함 → `fetch_market.py`가 계산
- `by_date`: 날짜→이벤트ID 매핑 → `build_timeline.py`가 계산
- viewer.html에 산술/집계 로직 추가 금지

---

## "크롤링 해줘" 요청 시 워크플로우

### Step 0: 카테고리 확인
- 슬러그·이름 확인 (없으면 생성)
- 시작 날짜 입력 받기 (종료일 = 오늘 강제)
- `data/{slug}/config.json` + `data/registry.json` 생성/업데이트

### Step 0.5: Site-Analyzer 서브에이전트 (신규 카테고리 or parse_config 없을 때)
```
역할: agents/site_analyzer.md
입력: config.json의 authoritative_sources
출력: config.json의 parse_config 업데이트 + 사용자 확인
```
**parse_config가 이미 있으면 생략 가능.** 없으면 반드시 실행.
- 각 사이트의 페이지 구조 파악 (정적/동적, 서브페이지 패턴, 추출 가능 필드)
- 결과를 사용자에게 보고하고 확인받은 후 config.json에 저장
- **사용자 확인 전까지 Step 1 진행 금지**

### Step 1: Site-Fetcher (Python)
```bash
python fetch_sites.py --category {slug} --date-from {date_from} --date-to {date_to}
```
- `parse_config` CSS 셀렉터 기반으로 HTML 파싱 (BeautifulSoup)
- 날짜 추출 실패 시 `needs_ai_date: true` 마킹 → Event-Merger가 AI로 처리
- 번역 없음 (EN 필드만 저장) → Event-Merger가 번역
- 출력: `pipeline/{slug}/01_site_events.json`

**에이전트 불필요 — Python 직접 실행.**
AI 개입은 Event-Merger 단계에서만 (날짜 보정 + 번역 + 중요도 분류).

### Step 2: Event-Merger 서브에이전트
```
역할: agents/event_merger.md
입력: pipeline/{slug}/01_site_events.json
출력: pipeline/{slug}/02_merged_events.json
```
두 사이트 사건 병합, 중복 제거, importance 분류.
`confirmed_by: ["wikipedia", "iranwarlive"]` — 두 사이트 모두 보도 시 높은 신뢰도.

### Step 3: Enricher 서브에이전트
```
역할: agents/enricher.md
입력: pipeline/{slug}/02_merged_events.json + config.json의 enrichment_sources
출력: pipeline/{slug}/03_enriched_events.json
```
각 사건별로:
- 트럼프 X 게시물 검색 (site:x.com realDonaldTrump + 사건 키워드 + 날짜)
- 관련 뉴스 기사 검색 (Reuters, AP, BBC 등)
- **관련성 검증**: 사건 날짜 ±3일 + 사건 고유 키워드 일치 필수

### Step 4: Timeline 빌드 (Python, AI 불필요)
```bash
# 신규
python build_timeline.py --category {slug}

# 업데이트 (기존 news.json에 머지)
python build_timeline.py --category {slug} --merge
```
AI 판단이 없는 순수 구조 변환 (ID 부여, 필드 매핑, 평균 계산, 인과 키워드 태깅).
서브에이전트 사용 금지 — 토큰 낭비.

### Step 5: 시장 데이터 수집
```bash
python fetch_market.py --category {slug}
```

### Step 6: registry.json 갱신 (필수)
크롤링/업데이트 완료 후 반드시 `data/registry.json`의 해당 카테고리 `last_updated`를 현재 시각으로 갱신:
```python
import json, datetime
reg = json.load(open('data/registry.json'))
for c in reg['categories']:
    if c['slug'] == '{slug}':
        c['last_updated'] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
json.dump(reg, open('data/registry.json','w'), ensure_ascii=False, indent=2)
```

---

## "업데이트 해줘" 요청 시 워크플로우

1. `data/{slug}/news.json`의 `last_updated` 읽기 → 이것이 date_from
   - 반드시 news.json에서 읽을 것 (이전 크롤링의 실제 종료 시각)
   - **전체 재파싱 금지** — date_from ~ 오늘 범위만 수집
2. Step 1~3 실행 (date_from ~ date_to)
   ```bash
   python fetch_sites.py --category {slug} --date-from {date_from} --date-to {date_to}
   ```
3. `python build_timeline.py --category {slug} --merge`
4. `python fetch_market.py --category {slug} --incremental`
5. registry.json의 last_updated 현재 시각으로 갱신 (Step 6)

---

## 새 카테고리 추가 시

`data/{slug}/config.json`의 `authoritative_sources`에
해당 주제의 권위 있는 타임라인/이벤트 목록 사이트 2개 이상 지정.
viewer.html 코드 수정 불필요 (동적 로딩).

---

## 데이터 흐름

```
authoritative_sources (Wikipedia + IranWarLive)
    ↓ Site-Fetcher
pipeline/{slug}/01_site_events.json
    ↓ Event-Merger
pipeline/{slug}/02_merged_events.json
    ↓ Enricher (트럼프 X + 관련 뉴스)
pipeline/{slug}/03_enriched_events.json
    ↓ Timeline-Builder (build_timeline.py)
data/{slug}/news.json  ←  최종
    ↓ fetch_market.py
data/{slug}/market.json
```
