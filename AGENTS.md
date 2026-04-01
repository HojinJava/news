# Agent Team — 역할 계약 요약

각 에이전트는 Claude Code가 `Agent tool`로 소환하는 서브에이전트다.
상세 역할 프롬프트는 `agents/{name}.md` 참조.

---

## 파이프라인

```
Orchestrator (메인 세션)
  → [0.5] Site-Analyzer   → config.json (parse_config) + 사용자 확인
  → [1]   Site-Fetcher    → pipeline/{slug}/01_site_events.json
  → [2]   Event-Merger    → pipeline/{slug}/02_merged_events.json
  → [3]   Enricher        → pipeline/{slug}/03_enriched_events.json
  → [4]   build_timeline.py → data/{slug}/news.json
  → [5]   fetch_market.py   → data/{slug}/market.json
```

---

## 에이전트 일람

| 에이전트 | 역할 | 입력 | 출력 | 핵심 금지 |
|----------|------|------|------|-----------|
| **Site-Analyzer** | `agents/site_analyzer.md` | authoritative_sources URL | `config.json` parse_config + 사용자 확인 | 사용자 확인 전 Step 1 진행 금지 |
| **Site-Fetcher** | `agents/site_fetcher.md` | config.json (parse_config 필수) | `pipeline/{slug}/01_site_events.json` | parse_config 없이 실행 금지 |
| **Event-Merger** | `agents/event_merger.md` | `pipeline/{slug}/01_site_events.json` | `pipeline/{slug}/02_merged_events.json` | 두 사이트 외 사건 추가 금지 |
| **Enricher** | `agents/enricher.md` | `pipeline/{slug}/02_merged_events.json` | `pipeline/{slug}/03_enriched_events.json` | 관련성 낮은 자료 연결 금지 |
| **Timeline-Builder** | `build_timeline.py` (Python) | `pipeline/{slug}/03_enriched_events.json` | `data/{slug}/news.json` | AI 불필요 — Python 전용 |
| **Market-Fetcher** | Python 스크립트 | `config.json` + 이벤트 시각 | `data/{slug}/market.json` | fetch_market.py 경유만 |

---

## 핵심 원칙

- **이벤트 spine = authoritative_sources만** (Wikipedia + IranWarLive)
- **관련 기사는 해당 사건 특정** (전쟁 전반 기사 금지)
- **번역은 Claude Code 직접** (외부 API 금지)
- **Python은 fetch_market.py 하나뿐**
- **viewer.html에서 출처 사이트 배지 표시** (사용자가 확인 가능)
