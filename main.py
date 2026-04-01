#!/usr/bin/env python3
"""War News Agent — 파이프라인 오케스트레이터 + CLI."""

import argparse
import json
import sys
from pathlib import Path

import yaml

from agents.collector import collect_articles
from agents.verifier import verify_articles
from agents.bias_analyst import analyze_bias
from agents.timeline_builder import build_timeline
from utils.merge import merge_timelines, load_timeline, save_timeline


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_debug(data, name: str, debug_dir: Path):
    debug_dir.mkdir(parents=True, exist_ok=True)
    out = debug_dir / f"{name}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            [item.to_dict() if hasattr(item, "to_dict") else item for item in data],
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"  [debug] {out}")


def run_pipeline(topic: str, config: dict, debug: bool = False):
    debug_dir = Path("debug")

    # Step 1: 수집
    print("\n[1/4] 뉴스 수집 중...")
    raw_articles = collect_articles(topic, config)
    print(f"  → {len(raw_articles)}건 수집 완료")
    if debug:
        save_debug(raw_articles, "01_collected", debug_dir)

    if not raw_articles:
        print("수집된 기사가 없습니다. 종료합니다.")
        return None

    # Step 2: 검증
    print("\n[2/4] 교차 검증 중...")
    verified_articles = verify_articles(raw_articles, config)
    verified_count = sum(1 for a in verified_articles if a.verification_status == "verified")
    flagged_count = sum(1 for a in verified_articles if a.verification_status == "flagged")
    print(f"  → {len(verified_articles)}건 검증 완료 (verified: {verified_count}, flagged: {flagged_count})")
    if debug:
        save_debug(verified_articles, "02_verified", debug_dir)

    # Step 3: 편향 분석
    print("\n[3/4] 편향 분석 중...")
    analyzed_articles = analyze_bias(verified_articles, config)
    avg_obj = (
        sum(a.objectivity_score for a in analyzed_articles) // len(analyzed_articles)
        if analyzed_articles
        else 0
    )
    print(f"  → {len(analyzed_articles)}건 분석 완료 (평균 객관도: {avg_obj})")
    if debug:
        save_debug(analyzed_articles, "03_analyzed", debug_dir)

    # Step 4: 타임라인 구축
    print("\n[4/4] 타임라인 구축 중...")
    timeline = build_timeline(analyzed_articles, topic)
    print(f"  → {timeline.total_events}개 사건, {timeline.total_articles}건 기사")
    if debug:
        debug_dir.mkdir(parents=True, exist_ok=True)
        with open(debug_dir / "04_timeline.json", "w", encoding="utf-8") as f:
            f.write(timeline.to_json())
        print(f"  [debug] {debug_dir / '04_timeline.json'}")

    return timeline


def main():
    parser = argparse.ArgumentParser(
        description="War News Agent — 전쟁/분쟁 뉴스 수집·검증·분석·타임라인 파이프라인",
    )
    parser.add_argument(
        "--topic",
        type=str,
        help="분석할 주제 (예: '이란 이스라엘 미국 전쟁')",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="디버그 모드 — debug/ 폴더에 중간 결과 저장",
    )
    parser.add_argument(
        "--merge",
        type=str,
        metavar="FILE",
        help="기존 JSON 파일과 머지",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="설정 파일 경로 (기본: config.yaml)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="출력 파일 경로 (기본: config의 pipeline.output_path)",
    )

    args = parser.parse_args()

    if not args.topic and not args.merge:
        parser.error("--topic 또는 --merge 중 하나는 필요합니다.")

    config = load_config(args.config)
    output_path = args.output or config.get("pipeline", {}).get("output_path", "output/result.json")
    debug = args.debug or config.get("pipeline", {}).get("debug_mode", False)

    timeline = None

    # 파이프라인 실행
    if args.topic:
        print(f"=== War News Agent ===")
        print(f"주제: {args.topic}")
        print(f"출력: {output_path}")
        timeline = run_pipeline(args.topic, config, debug=debug)

    # 머지
    if args.merge:
        other = load_timeline(args.merge)
        if timeline is None:
            if not Path(output_path).exists():
                print(f"오류: {output_path} 파일이 없습니다. --topic과 함께 사용하세요.")
                sys.exit(1)
            timeline = load_timeline(output_path)
        print(f"\n머지 중: {args.merge}")
        timeline = merge_timelines(timeline, other)
        print(f"  → 머지 완료: {timeline.total_events}개 사건, {timeline.total_articles}건 기사")

    # 저장
    if timeline:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        save_timeline(timeline, str(out))
        print(f"\n=== 완료 ===")
        print(f"결과 저장: {out}")
        print(f"총 {timeline.total_events}개 사건 / {timeline.total_articles}건 기사")
    else:
        print("결과가 없습니다.")
        sys.exit(1)


if __name__ == "__main__":
    main()
