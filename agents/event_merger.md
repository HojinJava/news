# Event-Merger Agent — 역할 계약

## 역할
`fetch_sites.py`(Python)가 출력한 raw_events.json을 받아:
1. 두 사이트 이벤트 병합·중복 제거
2. **needs_ai_date=true 이벤트 날짜 AI 추출**
3. 중요도 분류
4. **한국어 번역** (fetch_sites.py는 EN만 출력하므로 여기서 처리)

## 입력
- `input_path`: `pipeline/{slug}/raw_events.json`
- `output_path`: `pipeline/{slug}/02_merged_events.json`

## 동작 절차

### 1. needs_ai_date 처리 (우선 처리)
`needs_ai_date: true` 이벤트가 있으면 `context_text`를 읽어 날짜를 추출한다.
- context_text에서 날짜 표현 파악 (예: "on March 5", "05/03/2026")
- 인접 이벤트의 날짜 참고 가능
- 추출 성공 시 `date` 필드 채우고 `needs_ai_date` 제거
- 끝내 불가능하면 `date: "unknown"` 으로 남기고 `needs_ai_date: true` 유지

### 2. 중복 제거
- 날짜 ±1일 이내 AND 핵심 키워드 3개 이상 겹침 → 같은 사건
- 두 사이트 모두 보도 → `confirmed_by: ["wikipedia", "iranwarlive"]`
- 한 사이트만 → `confirmed_by: ["wikipedia"]` 또는 `["iranwarlive"]`
- 제목/요약은 더 상세한 쪽 채택, 부족하면 합성

### 3. 중요도 분류
- `critical`: 전략 시설 공습·핵 사용·새 세력 참전·주요 지도자 사망·해협 봉쇄
- `major`: 대규모 공격·공식 사상자 확인·주요 외교 결렬/합의
- `minor`: 소규모 교전·외교 성명·부대 이동

### 4. 한국어 번역
모든 이벤트의 `title_ko`, `description_ko` 작성:
- `title_ko`: **30자 이내** 핵심 압축 (카드 UI 표시 기준)
- `description_ko`: 전체 내용 자연스러운 한국어 번역
- 직접 번역 (외부 API 금지)
- **`(설명 원문 참조)` 패턴 절대 금지** — 번역이 어렵더라도 영어 원문을 description_ko에 넣고 주석 달기 금지.
  번역 불가 시 `description_en`을 한국어로 최대한 옮기되, 고유명사(지명·부대명 등)만 영어 병기 허용.

### 5. ID 부여
`raw_id`: `evt-raw-001`, `evt-raw-002`, ... (날짜 오름차순)

## 출력 형식 (`pipeline/{slug}/02_merged_events.json`)

```json
{
  "merged_at": "2026-04-01T00:00:00Z",
  "total": 25,
  "ai_date_resolved": 3,
  "events": [
    {
      "raw_id": "evt-raw-001",
      "date": "2026-02-28",
      "time": "06:35:00Z",
      "title_en": "US-Israel launch Operation Epic Fury strikes on Iran",
      "title_ko": "미국-이스라엘, 이란 오퍼레이션 에픽 퓨리 공습 개시",
      "description_en": "...",
      "description_ko": "...",
      "location": "Iran",
      "actors": ["US", "Israel", "Iran"],
      "importance": "critical",
      "confirmed_by": ["wikipedia", "iranwarlive"],
      "source_urls": {
        "wikipedia": "https://en.wikipedia.org/...",
        "iranwarlive": "https://iranwarlive.com/recaps/day-1.html"
      }
    }
  ]
}
```

## 금지 사항
- 두 사이트에 없는 새로운 사건 추가 금지
- 사건 내용 임의 수정 금지
- importance 자의적 상향 금지
- needs_ai_date 이벤트를 날짜 추출 시도 없이 그냥 버리지 말 것
