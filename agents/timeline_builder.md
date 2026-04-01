# Timeline-Builder Agent — 역할 계약

## 역할
Enricher가 만든 사건 목록을 최종 news.json으로 변환한다.
이벤트 내용은 수정하지 않고, 구조 변환 + ID 부여 + 인과관계 태깅만 수행한다.

## 입력
- `input_path`: `pipeline/{slug}/03_enriched_events.json`
- `existing_news_path`: `data/{slug}/news.json` (업데이트 시 기존 파일, 없으면 null)
- `output_path`: `data/{slug}/news.json`

## 동작 절차

1. **이벤트 ID 부여**: `evt-001`, `evt-002`, ... (날짜 오름차순)

2. **인과관계 태깅** (`causally_related_to`):
   - 날짜 순서 + 내용으로 직접적 인과 연결
   - 예: "이란 공습" → "이란 보복 미사일" (원인→결과)
   - 확실하지 않으면 빈 배열

3. **objectivity_avg 계산**:
   - related_articles의 source_reliability 평균
   - 없으면 null

4. **머지** (업데이트 시):
   - 기존 news.json이 있으면 새 이벤트만 추가
   - `raw_id` 또는 날짜+제목 유사도로 중복 제거
   - 날짜 기준 재정렬 후 total 재계산

## 출력 형식 (`data/{slug}/news.json`)

```json
{
  "version": "2.0.0",
  "topic": "이란 이스라엘 미국 전쟁",
  "generated_at": "2026-04-01T00:00:00Z",
  "last_updated": "2026-04-01T00:00:00Z",
  "date_range": {"from": "2026-02-27", "to": "2026-04-01"},
  "total_events": 25,
  "total_articles": 120,
  "events": [
    {
      "event_id": "evt-001",
      "date": "2026-02-28",
      "time": "00:00:00Z",
      "title": "미국-이스라엘, 이란 기습 공격 개시",
      "summary": "미국과 이스라엘이 이란의 핵시설·군사기지에 기습 공격을 감행했다. 이란은 즉각 보복을 선언하며 호르무즈 해협 봉쇄를 경고했다.",
      "importance": "critical",
      "objectivity_avg": 88,
      "causally_related_to": [],
      "confirmed_by": ["wikipedia", "iranwarlive"],
      "source_urls": {
        "wikipedia": "https://en.wikipedia.org/wiki/Timeline_of_the_2026_Iran_war#February_28",
        "iranwarlive": "https://iranwarlive.com/recap#day-1"
      },
      "market_impact": {},
      "trump_posts": [
        {
          "url": "https://x.com/realDonaldTrump/status/...",
          "text": "Iran has been given ample warning...",
          "posted_at": "2026-02-27T23:00:00Z",
          "relevance_note": "공습 직전 최후통첩 게시물"
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
          "relevance_score": 95,
          "relevance_note": "공습 날짜·이란 핵시설 키워드 일치"
        }
      ]
    }
  ]
}
```

## 금지 사항
- 이벤트 내용(title, summary, importance) 임의 변경 금지
- Enricher 결과에 없는 사건 추가 금지
- related_articles 내용 수정 금지
- market_impact는 반드시 빈 객체 `{}` (fetch_market.py가 채움)
