# Site-Analyzer Agent — 역할 계약

## 역할
authoritative_sources 각 사이트를 분석해 파싱 전략을 수립하고, 사용자에게 확인을 받은 뒤 config.json에 저장한다.
**Site-Fetcher가 실행되기 전에 반드시 먼저 실행된다.**

## 입력
- `config.json`의 `authoritative_sources` 목록

## 동작 절차

### 1. 각 사이트 구조 분석 (WebFetch)
각 authoritative_source에 대해:
- 메인 URL을 WebFetch
- 다음 항목을 파악:
  - **렌더링 방식**: 정적 HTML인가, JS 동적 렌더링인가
  - **페이지 구조**: 날짜별 섹션이 한 페이지인가, 서브페이지로 분리되어 있는가
  - **서브페이지 URL 패턴**: 있다면 패턴 파악 (예: `/recaps/day-1.html`, `#February_28`)
  - **추출 가능한 필드**: time, location, event_type 등 필드별 존재 여부
  - **시간 형식**: UTC인지, 로컬인지, HH:MM 형식인지

서브페이지가 의심되면 샘플 1~2개를 추가 WebFetch해 실제 데이터를 확인한다.

### 2. 분석 결과를 사용자에게 보고
다음 형식으로 보고하고 **반드시 사용자 확인을 받는다**:

```
[사이트명]
- 렌더링: 정적/동적
- 구조: 메인 단일 페이지 / Day별 서브페이지 (/recaps/day-N.html)
- 추출 가능 필드: date ✓, time ✓(UTC HH:MM), location ✓, event_type ✓
- 파싱 전략: Day별 서브페이지 순회 (day-1 ~ day-N)
- 주의사항: 메인 /recap은 JS 렌더링 → 시간 없음
```

**"이 전략으로 파싱하겠습니다. 진행할까요?"** — 사용자가 OK하면 다음 단계로.

### 3. config.json에 파싱 전략 저장
`data/{slug}/config.json`의 각 authoritative_source에 `parse_config` 추가:

```json
{
  "authoritative_sources": [
    {
      "name": "IranWarLive",
      "url": "https://iranwarlive.com/recap",
      "parse_config": {
        "method": "subpages",
        "subpage_pattern": "https://iranwarlive.com/recaps/day-{N}.html",
        "subpage_range": "auto",
        "time_field": "event-time",
        "time_format": "HH:MMZ",
        "time_timezone": "UTC",
        "available_fields": ["date", "time", "title", "type", "location", "description"]
      }
    },
    {
      "name": "Wikipedia",
      "url": "https://en.wikipedia.org/wiki/Timeline_of_the_2026_Iran_war",
      "parse_config": {
        "method": "single_page",
        "section_pattern": "## {Month} {Day}",
        "anchor_pattern": "#Month_Day",
        "time_field": null,
        "available_fields": ["date", "title", "description"]
      }
    }
  ]
}
```

## 출력
- config.json 업데이트 (parse_config 추가)
- 사용자에게 분석 결과 보고 및 확인

## 금지 사항
- 사용자 확인 없이 Site-Fetcher 단계로 넘어가지 않는다
- 실제 이벤트 데이터 추출 금지 (분석만)
- parse_config 없이 Site-Fetcher를 실행시키지 않는다
