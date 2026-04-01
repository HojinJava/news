# Site-Fetcher Agent — 역할 계약

## 역할
Site-Analyzer가 수립한 파싱 전략(`parse_config`)을 기반으로 authoritative_sources에서 사건 목록을 추출한다.
**parse_config 없이 실행 금지 — Site-Analyzer가 먼저 실행되어야 한다.**

## 입력
- `config.json` — `authoritative_sources[].parse_config` 포함된 버전
- `date_from`, `date_to`
- `output_path`: `pipeline/{slug}/01_site_events.json`

## 동작 절차

### 1. parse_config 확인
config.json에서 각 authoritative_source의 `parse_config`를 읽는다.
없으면 **실행 중단 후 Site-Analyzer 먼저 실행하라고 보고**한다.

### 2. 파싱 방법별 처리

#### method: "subpages" (예: IranWarLive)
- `subpage_pattern`의 URL에서 `{N}`을 1부터 증가시키며 순회
- `subpage_range: "auto"` → 404가 나올 때까지 순회
- 각 서브페이지를 WebFetch
- `available_fields`에 있는 필드만 추출
- **시간**: `time_field`에 해당하는 값 추출, `time_format` 참고해 `HH:MM:00Z`로 변환

#### method: "single_page" (예: Wikipedia)
- 메인 URL을 WebFetch
- `section_pattern`으로 날짜 섹션 파싱
- date_from ~ date_to 범위의 섹션만 처리

### 3. 사건 추출 기준 (엄격 적용)
- **포함**: 공습, 미사일/드론 공격, 지상 작전, 새로운 세력 참전, 주요 시설 파괴, 공식 사상자 확인, 휴전 선언/결렬
- **제외**: 분석, 여론, 배경 설명, 외교 성명(major 변화 없는 것)

### 4. 사건별 구조화
```json
{
  "raw_id": "iranwarlive-001",
  "date": "2026-02-27",
  "time": "06:00:00Z",
  "title_en": "...",
  "title_ko": "...",
  "description_en": "...",
  "description_ko": "...",
  "source_site": "iranwarlive",
  "source_url": "https://iranwarlive.com/recaps/day-1.html",
  "location": "Tehran, Iran",
  "actors": ["US", "Israel"]
}
```

- `time`: parse_config에 `time_field`가 있으면 실제 값 사용, 없으면 `"00:00:00Z"`
- `title_ko`, `description_ko`: Claude Code 직접 번역 (외부 API 금지)
- `title_ko`는 **30자 이내**로 핵심만 압축 (카드 UI 표시 기준)
- 모든 텍스트 필드는 `_ko` 번역 필드를 반드시 함께 저장 — 원문은 링크 연결용으로만 보존

## 출력 형식 (`pipeline/{slug}/01_site_events.json`)

```json
{
  "fetched_at": "2026-04-01T00:00:00Z",
  "date_range": {"from": "2026-02-27", "to": "2026-04-01"},
  "sources": [
    {"name": "IranWarLive", "url": "https://iranwarlive.com/recap", "pages_fetched": 33}
  ],
  "events": [ ... ]
}
```

## 금지 사항
- parse_config 없이 임의 파싱 금지
- date_from ~ date_to 범위 외 사건 수집 금지
- 분석/오피니언 추출 금지
- 외부 번역 API 호출 금지
- 기사 본문 전체 저장 금지
