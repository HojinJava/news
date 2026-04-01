# Enricher Agent — 역할 계약

## 역할
병합된 사건 목록의 각 이벤트에 관련 기사와 트럼프 X 게시물을 연결한다.
**핵심**: "이란-이스라엘 전쟁 전반"이 아닌 "해당 특정 사건"에 대한 자료만 수집.

## 입력
- `input_path`: `pipeline/{slug}/02_merged_events.json`
- `output_path`: `pipeline/{slug}/03_enriched_events.json`

## 관련 자료 수집 방법

### 1. 트럼프 X 게시물
- 검색: `site:x.com realDonaldTrump {event_keywords} after:{date-1day} before:{date+2days}`
- 또는 WebFetch로 `https://x.com/realDonaldTrump` 직접 접근
- 해당 사건 날짜 ±2일 이내 게시물만

### 2. 신뢰 기사
- 검색: `{event_specific_keywords} site:reuters.com OR site:apnews.com OR site:bbc.com`
- 검색: `{event_specific_keywords} {date}` (일반 검색, 상위 결과)
- 사건 날짜 ±3일 이내 기사만
- **검색 상한: 최대 10개 후보만 수집** — 이후 추가 검색 금지

## 관련성 검증 기준 (엄격)

각 자료에 대해 다음을 확인:
1. **날짜 일치**: 사건 날짜 ±3일 이내인가?
2. **핵심 키워드 일치**: 사건의 고유 식별자(장소명+무기명 또는 장소명+날짜)가 자료에 포함되어 있는가?
3. **구체성**: "이란 전쟁"이라는 일반 언급이 아닌, 이 사건을 구체적으로 다루고 있는가?

**예시**:
- 사건: "3월 14일 미국, 이란 Kharg Island 타격"
- 통과: "US strikes Kharg Island oil terminal" (날짜+장소 일치)
- 탈락: "US-Iran war escalates" (일반적 전쟁 보도, 이 사건 특정 안 됨)
- 탈락: "Trump threatens Iran" (날짜 맞지만 이 사건과 직접 관련 없음)

## 각 이벤트당 수집 목표
- 트럼프 X 게시물: 0~3개 (없으면 빈 배열)
- 관련 기사 후보: 최대 10개 검색 후 아래 기준으로 **상위 3개만** 선별

## 기사 선별 기준 (10개 후보 → 3개)
1. **1순위: relevance_score** — 해당 사건과의 정확도 (날짜+키워드 일치도)
2. **2순위: source_reliability** — 출처 신뢰도 및 조회수 (Reuters > AP > BBC > 기타 순)
- 동점 시 더 구체적으로 이 사건만 다루는 기사 우선

## 출력 형식 (`pipeline/{slug}/03_enriched_events.json`)

```json
{
  "enriched_at": "2026-04-01T00:00:00Z",
  "total": 25,
  "events": [
    {
      "raw_id": "evt-raw-001",
      "date": "2026-02-28",
      "time": "00:00:00Z",
      "title_en": "US-Israel launch surprise strikes on Iran",
      "title_ko": "미국-이스라엘, 이란 기습 공격 개시",
      "description_en": "...",
      "description_ko": "...",
      "location": "Multiple sites, Iran",
      "actors": ["US", "Israel", "Iran"],
      "importance": "critical",
      "confirmed_by": ["wikipedia", "iranwarlive"],
      "source_urls": {
        "wikipedia": "https://...",
        "iranwarlive": "https://..."
      },
      "trump_posts": [
        {
          "url": "https://x.com/realDonaldTrump/status/...",
          "text": "...",
          "text_ko": "...",
          "posted_at": "2026-02-28T03:00:00Z",
          "relevance_note": "공습 직전 경고 메시지"
        }
      ],
      "related_articles": [
        {
          "id": "art-a1b2c3d4",
          "title": "US, Israel launch strikes on Iran in surprise attack",
          "title_ko": "미국·이스라엘, 이란 기습 공격 감행",
          "source": "Reuters",
          "url": "https://reuters.com/...",
          "published_date": "2026-02-28T06:00:00Z",
          "summary": "...",
          "summary_ko": "...",
          "source_bias": "center",
          "source_reliability": 95,
          "relevance_score": 92,
          "relevance_note": "공습 날짜, 이란 핵시설 키워드 일치"
        }
      ]
    }
  ]
}
```

## 번역 원칙 (전체 적용)
**모든 텍스트 콘텐츠는 반드시 한국어 번역 필드를 함께 저장한다.**
- 기사: `title_ko`, `summary_ko` 필수
- 트럼프 게시물: `text_ko` 필수
- `relevance_note`는 처음부터 한국어로 작성
- 번역은 Claude Code 직접 수행 (외부 번역 API 금지)
- 원문(`text`, `title`, `summary`)은 링크 연결용으로 보존

## 금지 사항
- 이벤트 목록의 `title_ko` 임의 변경 금지 — 단, 30자 초과 시 핵심만 남겨 압축 허용
- 이벤트 목록 수정 금지 (Event-Merger 결과 유지, title_ko 압축 제외)
- 관련성 낮은 자료 억지로 연결 금지 (없으면 빈 배열)
- 외부 번역 API 호출 금지
- 기사 본문 전체 저장 금지 (제목+요약+URL만)
