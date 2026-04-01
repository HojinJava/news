# 에이전트 역할 계약서

> 이 문서는 CLAUDE.md의 강제 규칙과 함께 적용됩니다.
> 각 에이전트는 아래 계약을 위반하면 안 됩니다.

## Orchestrator (`agents/orchestrator.py`)
- **입력**: 사용자 명령 (category_slug, topic, date_from, mode)
- **출력**: 파이프라인 실행 결과 요약
- **역할**: 에이전트 팀 순서 조정, 중간 결과 전달
- **금지**: 직접 수집/번역/분석/판정 금지

## Collector (`agents/collector.py`)
- **입력**: topic, date_range, config
- **출력**: `list[RawArticle]`
- **역할**: RSS/웹 수집만. 판단 없음.
- **금지**: 번역·분석·검증·판정 금지

## Verifier-A (`agents/verifier_a.py`)
- **입력**: `list[RawArticle]`
- **출력**: `ClaimsReport` (주장 목록 + 클러스터 + 초기 검토)
- **역할**: 핵심 주장 추출, 클러스터링, 초기 신뢰도 평가
- **금지**: 최종 판정 금지. Verifier-B 결과 참조 금지.

## Verifier-B (`agents/verifier_b.py`)
- **입력**: `ClaimsReport` (Verifier-A 출력)
- **출력**: `ChallengeReport` (반박·상충 정보 목록)
- **역할**: A의 주장에 독립적으로 반박 시도, 상충 정보 탐색
- **금지**: A 결과 수정 금지. 독립 컨텍스트 유지 (A와 동일 판단 금지).

## Arbiter (`agents/arbiter.py`)
- **입력**: `ClaimsReport` + `ChallengeReport`
- **출력**: `list[VerifiedArticle]` (신뢰도 점수 확정)
- **역할**: A·B 불일치 조정, 최종 검증 상태 및 신뢰도 점수 결정
- **금지**: 새 수집·번역 금지.

## Bias-Analyst (`agents/bias_analyst.py`)
- **입력**: `list[VerifiedArticle]`
- **출력**: `list[AnalyzedArticle]`
- **역할**: 매체 편향도 조회, 기사 내용 편향 분석, 객관도 점수 산출
- **금지**: 검증 결과 수정 금지.

## Timeline-Builder (`agents/timeline_builder.py`)
- **입력**: `list[AnalyzedArticle]`, category_slug
- **출력**: `data/{category_slug}/news.json` 저장
- **역할**: 타임라인 구조화, 인과관계 태깅, 종합 요약 작성
- **금지**: 분석·검증 재수행 금지.

## Market-Fetcher (`fetch_market.py`)
- **입력**: category_slug (config.json + news.json 읽음)
- **출력**: `data/{category_slug}/market.json` 저장
- **역할**: yfinance로 일봉·분봉 수집, 이벤트별 윈도우 계산
- **금지**: 뉴스 데이터 수정 금지. yfinance 외 시장 데이터 소스 금지.
