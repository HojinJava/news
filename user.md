# 크롤링 방식 안내

이 프로젝트는 Claude Code(AI)가 여러 에이전트를 순서대로 실행해 뉴스 이벤트를 수집·가공합니다.
사람이 직접 코드를 실행할 필요 없이, Claude Code에 아래처럼 말하면 됩니다.

---

## 시작하는 법

### 처음 수집할 때
```
크롤링 해줘
```

### 이미 수집된 데이터를 최신화할 때
```
업데이트 해줘
```

---

## 파이프라인 구조

Claude Code가 내부적으로 아래 단계를 순서대로 실행합니다.

```
[0]   카테고리 확인         → 슬러그·날짜 범위 설정
[0.5] Site-Analyzer       → 대상 사이트 구조 분석, 파싱 전략 수립 (사용자 확인 후 진행)
[1]   Site-Fetcher        → 권위 사이트 2곳에서 이벤트 목록 수집
[2]   Event-Merger        → 두 사이트 이벤트 병합·중복 제거·중요도 분류
[3]   Enricher            → 각 이벤트에 관련 기사·트럼프 X 게시물 연결
[4]   build_timeline.py   → 최종 news.json 구성 (AI 없음, 순수 Python)
[5]   fetch_market.py     → 이벤트 전후 시장 데이터 수집 (yfinance)
```

---

## 각 단계 설명

### [0] 카테고리 확인
어떤 주제를 수집할지 슬러그(예: `iran-war`)와 시작 날짜를 확인합니다.
`data/{slug}/config.json`과 `data/registry.json`이 없으면 생성합니다.

### [0.5] Site-Analyzer
수집 대상 사이트의 페이지 구조를 분석합니다.
- 정적/동적 페이지 여부
- 이벤트 목록 위치, 날짜·시간 추출 방법
- 서브페이지 순회 필요 여부

분석 결과를 사용자에게 보고하고, **확인을 받은 후** 다음 단계로 진행합니다.
`config.json`에 `parse_config`가 이미 있으면 이 단계는 생략됩니다.

### [1] Site-Fetcher
`parse_config`에 정의된 전략대로 사이트를 파싱합니다.
서브페이지를 순회하며 이벤트 제목·날짜·시간·출처 URL을 추출합니다.
→ `pipeline/{slug}/01_site_events.json`

### [2] Event-Merger
두 사이트에서 수집한 이벤트를 하나로 병합합니다.
- 동일 사건 중복 제거
- 중요도(CRITICAL / MAJOR / MINOR) 분류
- 두 사이트 모두 보도 시 `confirmed_by` 표시

→ `pipeline/{slug}/02_merged_events.json`

### [3] Enricher
각 이벤트에 보강 자료를 연결합니다.
- 트럼프 X(트위터) 게시물 검색 (사건 키워드 + 날짜 기준)
- Reuters·AP·BBC 등 관련 기사 검색 (최대 10개 후보 → 상위 3개 선별)
- **모든 텍스트는 한국어 번역본만 저장**, 원문은 URL 링크로 제공

→ `pipeline/{slug}/03_enriched_events.json`

### [4] build_timeline.py
Enricher 출력을 `news.json` 포맷으로 변환합니다.
AI 없이 Python만 실행합니다.
- 이벤트 ID 부여
- 날짜별 인덱스(`by_date`) 생성
- 인과관계 키워드 태깅
- 업데이트 모드(`--merge`)로 실행 시 기존 데이터와 병합

→ `data/{slug}/news.json`

### [5] fetch_market.py
각 이벤트 시각 기준 ±30분 시장 데이터를 수집합니다.
- 5분봉 → 10분봉 집계까지 Python에서 완료 (viewer.html은 연산 없이 렌더링만)
- 일봉 등락률(`delta_pct`) 사전 계산
- 60일 이상 지난 이벤트는 분봉 데이터 없음 (yfinance 제한)

→ `data/{slug}/market.json`

---

## 결과 파일

| 파일 | 내용 |
|------|------|
| `data/{slug}/news.json` | 이벤트 타임라인 (제목·요약·기사·트럼프 게시물) |
| `data/{slug}/market.json` | 시장 데이터 (10분봉·일봉·등락률) |
| `data/registry.json` | 카테고리 목록 + 마지막 업데이트 시각 |

`viewer.html`을 열면 이 JSON을 읽어 타임라인을 표시합니다.

---

## 이벤트 출처 원칙

- **이벤트 목록은 권위 사이트 2곳에서만** 추출합니다 (`config.json`의 `authoritative_sources`)
- 임의 뉴스 검색으로 이벤트를 만들지 않습니다
- 관련 기사는 해당 특정 사건에만 연결합니다 (전쟁 전반 기사 금지)
