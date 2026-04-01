# War News Agent Team

## Quick Context
- **프로젝트**: 전쟁/분쟁 뉴스를 수집 → 검증 → 편향 분석 → 타임라인 정리하는 에이전트 팀
- **언어**: Python 3.11+
- **출력**: `output/result.json` (Flutter 앱 연동용)
- **실행**: `python main.py --topic "이란 이스라엘 미국 전쟁"`
- **테스트**: `python -m pytest tests/`

---

## 프로젝트 개요

사용자가 주제(예: "이란 이스라엘 미국 전쟁")를 입력하면, 해외 뉴스를 수집하고 교차 검증하고 편향도를 분석하고 타임라인으로 정리하여 JSON 파일로 출력한다.

이 JSON은 Flutter 앱(별도 프로젝트)에서 타임라인 UI로 시각화된다. JSON 파일을 다른 사용자와 공유하면 뉴스를 머지(동기화)할 수 있다.

향후 전쟁 외 어떤 주제든 입력 가능하도록 확장성 있게 설계한다.

---

## Independent Modules

| Module | Directory | Owner | 설명 |
|--------|-----------|-------|------|
| Schema & Config | `models/`, `config.yaml` | 공유 (수정 전 조율 필요) | 공통 데이터 모델, 소스 설정 |
| Collector | `agents/collector.py` | collector 팀원 | 뉴스 수집 |
| Verifier | `agents/verifier.py` | verifier 팀원 | 교차 검증 |
| Bias Analyst | `agents/bias_analyst.py` | bias-analyst 팀원 | 편향 분석 |
| Timeline Builder | `agents/timeline_builder.py` | timeline 팀원 | 타임라인 정리 |
| Orchestrator | `main.py` | 리드 | 파이프라인 실행, CLI |
| Merge | `utils/merge.py` | 리드 | JSON 머지 유틸 |

**공유 파일 (수정 전 반드시 조율):**
- `models/schema.py` — 모든 에이전트가 참조하는 데이터 모델
- `config.yaml` — 소스 목록, 설정값
- `requirements.txt`

---

## 디렉토리 구조

```
war-news-agents/
├── CLAUDE.md
├── main.py                # 파이프라인 오케스트레이터 + CLI
├── config.yaml            # 주제, 소스, 설정
├── agents/
│   ├── __init__.py
│   ├── collector.py       # 수집 에이전트
│   ├── verifier.py        # 검증 에이전트
│   ├── bias_analyst.py    # 편향 분석 에이전트
│   └── timeline_builder.py # 타임라인 정리 에이전트
├── models/
│   ├── __init__.py
│   └── schema.py          # 공통 데이터 모델 (dataclass)
├── utils/
│   ├── __init__.py
│   └── merge.py           # JSON 머지 유틸리티
├── output/
│   └── (result.json 생성됨)
├── debug/                 # --debug 모드 중간 결과
├── tests/
│   ├── test_collector.py
│   ├── test_verifier.py
│   ├── test_bias_analyst.py
│   ├── test_timeline_builder.py
│   └── test_merge.py
└── requirements.txt
```

---

## 에이전트 팀 구성 프롬프트

리드에게 아래와 같이 요청하면 된다:

```
이 프로젝트의 에이전트 팀을 구성해줘.

팀원 4명:
1. collector — agents/collector.py 담당. 웹 검색으로 뉴스를 수집하고 구조화.
2. verifier — agents/verifier.py 담당. collector 결과를 교차 검증.
3. bias-analyst — agents/bias_analyst.py 담당. 편향 분석 및 객관도 점수 산출.
4. timeline — agents/timeline_builder.py 및 utils/merge.py 담당. 타임라인 구조화 + 머지 기능.

공유 파일인 models/schema.py는 리드가 먼저 작성한 뒤 팀원들에게 공유.
main.py (오케스트레이터)도 리드가 직접 작성.
각 팀원은 자기 모듈의 tests도 함께 작성.
```

---

## 각 팀원별 상세 요구사항

### Collector (수집 에이전트)
**파일**: `agents/collector.py`, `tests/test_collector.py`

**역할**: 주제를 받아 config.yaml의 소스 목록에서 뉴스를 검색하고 구조화

**동작**:
1. 주제 문자열 → 영어 검색 키워드 자동 생성 (다양한 관점 포괄)
2. config.yaml 소스별로 웹 검색 수행
3. 검색 결과에서 뉴스 기사 추출: 제목, 날짜, 출처, 요약, URL
4. 중복 URL 제거
5. 한국어 번역 (제목, 요약)

**입력**: `topic: str`, `config: dict`
**출력**: `list[RawArticle]`

```python
@dataclass
class RawArticle:
    id: str                  # UUID
    title: str               # 기사 제목 (원문 영어)
    title_ko: str            # 기사 제목 (한국어)
    source: str              # 매체명
    url: str                 # 원문 URL
    published_date: str      # ISO 8601
    summary: str             # 요약 (원문 영어)
    summary_ko: str          # 요약 (한국어)
    search_keyword: str      # 이 기사를 찾은 검색어
    collected_at: str        # 수집 시각 ISO 8601
```

---

### Verifier (검증 에이전트)
**파일**: `agents/verifier.py`, `tests/test_verifier.py`

**역할**: 수집된 뉴스를 교차 검증하고 신뢰도 판단

**동작**:
1. `list[RawArticle]` 입력
2. "같은 사건" 기사들을 의미적 유사도 기반으로 클러스터링
3. 각 클러스터:
   - 보도 매체 수 카운트
   - 2개+ 매체 → `verified`, 1개만 → `unverified`
4. 기사별 신뢰도 판단: 출처 인용 여부, 선정적 표현, 사실 오류
5. 심각한 오보 의심 → `flagged`

**출력**: `list[VerifiedArticle]`

```python
@dataclass
class VerifiedArticle(RawArticle):
    event_cluster_id: str       # 같은 사건 클러스터 ID
    verification_status: str    # "verified" | "unverified" | "flagged"
    corroboration_count: int    # 같은 사건 보도 매체 수
    corroborating_sources: list[str]
    credibility_note: str       # 검증 판단 메모 (한국어)
```

---

### Bias Analyst (편향 분석 에이전트)
**파일**: `agents/bias_analyst.py`, `tests/test_bias_analyst.py`

**역할**: 각 뉴스의 편향도 분석 및 객관도 점수 산출

**동작**:
1. `list[VerifiedArticle]` 입력
2. 기사별:
   - config.yaml에서 매체 기본 편향도/신뢰도 조회
   - 기사 내용 자체의 편향 분석 (프레이밍, 감정적 언어, 양측 입장 균형)
   - 객관도 점수(0-100) 산출
3. 같은 클러스터 내 기사 간 프레이밍 비교 (서방 vs 중동 등)

**객관도 점수 산출**:
- 매체 기본 신뢰도: 40%
- 교차 검증 수: 30%
- 기사 내용 편향 분석: 30%

**출력**: `list[AnalyzedArticle]`

```python
@dataclass
class AnalyzedArticle(VerifiedArticle):
    source_bias: str              # "left"|"center-left"|"center"|"center-right"|"right"
    source_reliability: int       # 0-100
    content_bias_score: int       # 0-100 (100=완전 객관)
    objectivity_score: int        # 최종 객관도 0-100
    bias_analysis_note: str       # 편향 분석 설명 (한국어)
    framing_comparison: str       # 타매체 프레이밍 비교 (한국어)
```

---

### Timeline Builder (타임라인 정리 에이전트)
**파일**: `agents/timeline_builder.py`, `utils/merge.py`, `tests/test_timeline_builder.py`, `tests/test_merge.py`

**역할**: 분석 완료 뉴스를 시간순 타임라인으로 구조화

**동작**:
1. `list[AnalyzedArticle]` 입력
2. 사건 클러스터를 시간순 정렬
3. 사건 간 인과관계 태깅 (예: "미사일 공격" → "보복 공습")
4. 각 사건의 종합 요약 작성 (한국어, 중립적)
5. 중요도 판단: `critical` / `major` / `minor`
6. `TimelineResult` JSON 생성

**출력**: `TimelineResult`

```python
@dataclass
class TimelineEvent:
    event_id: str
    date: str                        # ISO 8601
    title: str                       # 한국어
    summary: str                     # 종합 요약 (한국어, 중립)
    importance: str                  # "critical"|"major"|"minor"
    objectivity_avg: int             # 관련 기사 평균 객관도
    causally_related_to: list[str]   # 인과 관련 event_id 리스트
    articles: list[AnalyzedArticle]

@dataclass
class TimelineResult:
    version: str                     # "1.0.0"
    topic: str
    generated_at: str                # ISO 8601
    date_range: dict                 # {"from": "...", "to": "..."}
    total_events: int
    total_articles: int
    events: list[TimelineEvent]
```

**머지 기능** (`utils/merge.py`):
- 두 `TimelineResult` JSON을 합침
- `event_id` 동일 → 같은 사건, articles를 url 기준 중복 제거 후 합침
- 새로운 event_id → events에 추가
- 머지 후 date 기준 재정렬, total 재계산
- version 다르면 머지 거부

---

## config.yaml

```yaml
sources:
  tier1_factual:
    - name: "Associated Press"
      search_keyword: "site:apnews.com"
      bias: "center"
      reliability: 95
    - name: "Reuters"
      search_keyword: "site:reuters.com"
      bias: "center"
      reliability: 95
    - name: "BBC News"
      search_keyword: "site:bbc.com/news"
      bias: "center-left"
      reliability: 90

  tier2_analysis:
    - name: "Al Jazeera"
      search_keyword: "site:aljazeera.com"
      bias: "center-left"
      reliability: 80
      note: "중동 이슈에서 카타르 자본 영향 가능"
    - name: "The War Zone"
      search_keyword: "site:twz.com"
      bias: "center-right"
      reliability: 85
      note: "군사/무기 전문, 미국 시각 강함"

  tier3_tracker:
    - name: "International Crisis Group"
      search_keyword: "site:crisisgroup.org"
      bias: "center"
      reliability: 90
    - name: "CFR Global Conflict Tracker"
      search_keyword: "site:cfr.org"
      bias: "center"
      reliability: 90

collection:
  max_articles_per_source: 10
  date_range_days: 30
  languages: ["en"]
  output_language: "ko"

pipeline:
  debug_mode: false
  output_path: "output/result.json"
```

---

## CLI 사용법

```bash
# 기본 실행
python main.py --topic "이란 이스라엘 미국 전쟁"

# 디버그 모드 (debug/ 폴더에 중간 결과 저장)
python main.py --topic "이란 이스라엘 미국 전쟁" --debug

# 기존 JSON에 새 결과 머지
python main.py --topic "이란 이스라엘 미국 전쟁" --merge output/friend_result.json

# 프리셋 사용 (config.yaml에 정의)
python main.py --preset war_iran
```

---

## JSON 최종 출력 예시 (Flutter 연동용)

```json
{
  "version": "1.0.0",
  "topic": "이란 이스라엘 미국 전쟁",
  "generated_at": "2026-04-01T15:30:00Z",
  "date_range": {"from": "2026-03-01", "to": "2026-04-01"},
  "total_events": 12,
  "total_articles": 47,
  "events": [
    {
      "event_id": "evt-001",
      "date": "2026-03-28",
      "title": "미국-이스라엘 연합, 이란 이스파한 핵시설 공습",
      "summary": "미국과 이스라엘이 이란 이스파한의 우라늄 농축 시설 등에 공습을 감행. IRGC는 확전을 경고.",
      "importance": "critical",
      "objectivity_avg": 78,
      "causally_related_to": ["evt-002"],
      "articles": [
        {
          "id": "art-001",
          "title": "US-Israeli strikes hit Iran nuclear facilities",
          "title_ko": "미국-이스라엘, 이란 핵시설 공습",
          "source": "Reuters",
          "url": "https://reuters.com/...",
          "published_date": "2026-03-28T08:00:00Z",
          "summary_ko": "...",
          "verification_status": "verified",
          "corroboration_count": 5,
          "source_bias": "center",
          "objectivity_score": 92,
          "bias_analysis_note": "사실 중심 보도, 양측 입장 균형"
        }
      ]
    }
  ]
}
```

---

## 주의사항

- 뉴스 본문 통째로 저장하지 않는다 (저작권). 제목 + 요약 + URL만 저장.
- 한국어 번역 시 원문도 함께 보존.
- 객관도 점수는 참고용이며 절대적 진실이 아님 (UI에서 안내 필요).
- 특정 국가/세력 입장을 대변하지 않도록 중립적으로 작성.
- 각 팀원은 자기 파일만 수정. 공유 파일은 리드가 관리.
