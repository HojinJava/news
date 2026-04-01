#!/usr/bin/env python3
"""Card layout height validation script.

Simulates browser text layout to check whether card content (title + summary)
is visible given CSS layout constraints in viewer.html.

CSS reference (viewer.html):
  .evt-head:    padding 12px 14px 8px, flex-column, gap 4px, min-height 100px, overflow visible
  .evt-meta:    single-row badges ~28px
  .evt-title:   font-size 16px, line-height 1.4
  .evt-summary: font-size 15px, line-height 1.5, -webkit-line-clamp 2 on cards
  Card width:   320px, inner = 320 - 14*2 = 292px
"""

import json
import math
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NEWS_JSON = PROJECT_ROOT / "data" / "iran-war" / "news.json"

# Layout constants
CARD_WIDTH = 320
CARD_PADDING_H = 14
INNER_WIDTH = CARD_WIDTH - CARD_PADDING_H * 2  # 292px
PADDING_TOP = 12
PADDING_BOTTOM = 8
GAP = 4
META_HEIGHT = 28

TITLE_FONT = 16
TITLE_LH = 1.4
TITLE_PX_PER_LINE = TITLE_FONT * TITLE_LH  # 22.4

SUMMARY_FONT = 15
SUMMARY_LH = 1.5
SUMMARY_PX_PER_LINE = SUMMARY_FONT * SUMMARY_LH  # 22.5


def estimate_lines(text: str, font_size: float, container_width: float) -> int:
    """Estimate number of lines text will take."""
    if not text:
        return 0
    avg_char_w = font_size * 0.7  # mix of Korean/ASCII
    chars_per_line = container_width / avg_char_w
    effective_chars = len(text) * 1.15  # word-wrap overhead
    lines = max(1, math.ceil(effective_chars / chars_per_line))
    return lines


def test_card_visibility(evt: dict, head_height, inner_width=INNER_WIDTH) -> dict:
    """Returns dict with visibility analysis."""
    title = evt.get("title", "")
    summary = evt.get("summary", "")

    title_lines = estimate_lines(title, TITLE_FONT, inner_width)
    title_h = title_lines * TITLE_PX_PER_LINE

    summary_lines = estimate_lines(summary, SUMMARY_FONT, inner_width)
    summary_h = summary_lines * SUMMARY_PX_PER_LINE

    total_needed = PADDING_TOP + PADDING_BOTTOM + META_HEIGHT + GAP + title_h + GAP + summary_h

    if head_height is None:  # auto height
        available_for_summary = summary_h  # always shows
    else:
        used_before_summary = PADDING_TOP + PADDING_BOTTOM + META_HEIGHT + GAP + title_h + GAP
        available_for_summary = head_height - used_before_summary

    return {
        "event_id": evt["event_id"],
        "title_len": len(title),
        "summary_len": len(summary),
        "title_lines": title_lines,
        "title_h": round(title_h, 1),
        "summary_lines": summary_lines,
        "summary_h": round(summary_h, 1),
        "total_needed": round(total_needed, 1),
        "available_for_summary": round(available_for_summary, 1),
        "summary_visible": available_for_summary >= SUMMARY_PX_PER_LINE,  # at least 1 line
        "summary_fully_visible": available_for_summary >= summary_h,
    }


def run_scenario(events: list, head_height, label: str):
    """Run visibility test for a scenario and print report."""
    results = [test_card_visibility(evt, head_height) for evt in events]
    total = len(results)

    not_visible = [r for r in results if not r["summary_visible"]]
    partial = [r for r in results if r["summary_visible"] and not r["summary_fully_visible"]]

    totals_needed = [r["total_needed"] for r in results]
    min_h = min(totals_needed)
    max_h = max(totals_needed)
    avg_h = sum(totals_needed) / len(totals_needed)
    sorted_needed = sorted(totals_needed)
    p95_idx = int(len(sorted_needed) * 0.95)
    p95_h = sorted_needed[min(p95_idx, len(sorted_needed) - 1)]

    print(f"\n{'=' * 50}")
    print(f"=== {label} ===")
    print(f"{'=' * 50}")
    print(f"전체: {total}개")

    nv_mark = "\u2705" if len(not_visible) == 0 else "\u274c"
    print(f"요약 안보임: {len(not_visible)}개 {nv_mark}")

    pa_mark = "\u2705" if len(partial) == 0 else "\u26a0\ufe0f"
    print(f"요약 일부만 보임: {len(partial)}개 {pa_mark}")

    if not_visible:
        print(f"\n  요약 안보이는 최악 케이스 (상위 5개):")
        worst = sorted(not_visible, key=lambda r: r["available_for_summary"])[:5]
        for r in worst:
            print(
                f"    {r['event_id']}: available={r['available_for_summary']}px "
                f"(title_lines={r['title_lines']}, summary_len={r['summary_len']})"
            )

    if partial:
        print(f"\n  일부만 보이는 최악 케이스 (상위 5개):")
        worst_partial = sorted(partial, key=lambda r: r["available_for_summary"])[:5]
        for r in worst_partial:
            print(
                f"    {r['event_id']}: available={r['available_for_summary']}px / "
                f"needed={r['summary_h']}px "
                f"(title_lines={r['title_lines']}, summary_len={r['summary_len']})"
            )

    print(f"\n  필요 높이 분포:")
    print(f"    min: {min_h:.0f}px / avg: {avg_h:.0f}px / max: {max_h:.0f}px / p95: {p95_h:.0f}px")


def main():
    if not NEWS_JSON.exists():
        print(f"ERROR: {NEWS_JSON} not found", file=sys.stderr)
        sys.exit(1)

    with open(NEWS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("events", [])
    print(f"로드된 이벤트 수: {len(events)}")

    # Scenario 1: auto height (current fix)
    run_scenario(events, head_height=None, label="head_height=None (auto)")

    # Scenario 2: old fixed 160px
    run_scenario(events, head_height=160, label="head_height=160px (old)")

    # Scenario 3: previous attempt 190px
    run_scenario(events, head_height=190, label="head_height=190px (previous)")


if __name__ == "__main__":
    main()
