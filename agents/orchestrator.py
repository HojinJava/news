"""agents/orchestrator.py — 에이전트 팀 파이프라인 조율."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agents.collector import collect_articles
from agents.verifier_a import extract_claims
from agents.verifier_b import challenge_claims
from agents.arbiter import arbitrate
from agents.bias_analyst import analyze_bias
from agents.timeline_builder import build_timeline

logger = logging.getLogger(__name__)


def _load_pipeline_config(category_slug: str) -> dict:
    """카테고리용 config.yaml 또는 루트 config.yaml을 로드한다.

    두 파일 모두 없으면 빈 기본값을 반환한다 (테스트 환경 대응).
    """
    cat_path = Path("data") / category_slug / "config.yaml"
    if cat_path.exists():
        with open(cat_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    root_path = Path("config.yaml")
    if root_path.exists():
        with open(root_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    logger.warning("config.yaml not found; using empty default config")
    return {}


def _save_news_json(category_slug: str, timeline_dict: dict) -> Path:
    out = Path("data") / category_slug / "news.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(timeline_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def run_pipeline_for_category(
    category_slug: str,
    topic: str,
    date_from: str,
    date_to: str | None = None,
    debug: bool = False,
) -> Path:
    """에이전트 팀을 순차 실행하고 data/{slug}/news.json을 저장한다."""
    if not category_slug:
        raise ValueError("category_slug is required")

    if date_to is None:
        date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    pipeline_config = _load_pipeline_config(category_slug)
    pipeline_config.setdefault("collection", {})
    pipeline_config["collection"]["date_from"] = date_from
    pipeline_config["collection"]["date_to"] = date_to

    print(f"\n[1/6] 수집 중... (topic={topic}, {date_from} ~ {date_to})")
    raw_articles = collect_articles(topic, pipeline_config)
    print(f"  → {len(raw_articles)}건 수집")

    if not raw_articles:
        print("  수집 기사 없음. 빈 결과 저장.")
        timeline = build_timeline([], topic)
        timeline_dict = timeline.to_dict()
        timeline_dict["last_updated"] = datetime.now(timezone.utc).isoformat()
        return _save_news_json(category_slug, timeline_dict)

    print(f"\n[2/6] Verifier-A: 주장 추출 중...")
    claims_report = extract_claims(raw_articles)
    print(f"  → 클러스터 {len(claims_report['clusters'])}개")

    print(f"\n[3/6] Verifier-B: 독립 반박 검토 중...")
    challenge_report = challenge_claims(claims_report)
    print(f"  → {len(challenge_report['challenges'])}건 검토")

    print(f"\n[4/6] Arbiter: 최종 검증 판정 중...")
    verified_articles = arbitrate(raw_articles, claims_report, challenge_report)
    verified_count = sum(1 for a in verified_articles if a.verification_status == "verified")
    flagged_count  = sum(1 for a in verified_articles if a.verification_status == "flagged")
    print(f"  → verified: {verified_count}, flagged: {flagged_count}")

    print(f"\n[5/6] 편향 분석 중...")
    analyzed_articles = analyze_bias(verified_articles, pipeline_config)
    avg_obj = sum(a.objectivity_score for a in analyzed_articles) // max(len(analyzed_articles), 1)
    print(f"  → 평균 객관도: {avg_obj}")

    print(f"\n[6/6] 타임라인 구축 중...")
    timeline = build_timeline(analyzed_articles, topic)
    print(f"  → {timeline.total_events}개 사건, {timeline.total_articles}건 기사")

    timeline_dict = timeline.to_dict()
    timeline_dict["last_updated"] = datetime.now(timezone.utc).isoformat()

    out_path = _save_news_json(category_slug, timeline_dict)
    print(f"\n  저장: {out_path}")
    return out_path
