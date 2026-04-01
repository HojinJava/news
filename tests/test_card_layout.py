#!/usr/bin/env python3
"""Card layout height validation script.

Parses CSS constraints directly from viewer.html and simulates browser text
layout to check whether card content (title + summary) is visible.
"""

import json
import math
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NEWS_JSON = PROJECT_ROOT / "data" / "iran-war" / "news.json"
VIEWER_HTML = PROJECT_ROOT / "viewer.html"


# ── CSS parsing ──────────────────────────────────────────────────────────

def parse_css_block(html: str, selector: str) -> str | None:
    """Extract the CSS block body for a given selector (non-media-query context)."""
    # Match selector outside @media blocks (simple heuristic: top-level)
    pattern = re.escape(selector) + r'\s*\{([^}]+)\}'
    m = re.search(pattern, html)
    return m.group(1) if m else None


def parse_css_prop(block: str, prop: str) -> str | None:
    """Extract a CSS property value from a block."""
    if not block:
        return None
    m = re.search(r'(?<![a-zA-Z])' + re.escape(prop) + r'\s*:\s*([^;]+)', block)
    return m.group(1).strip() if m else None


def parse_media_blocks(html: str) -> list[tuple[str, str]]:
    """Return list of (media query, block content) tuples."""
    results = []
    for m in re.finditer(r'@media\s*\(([^)]+)\)\s*\{', html):
        query = m.group(1)
        start = m.end()
        depth = 1
        i = start
        while i < len(html) and depth > 0:
            if html[i] == '{':
                depth += 1
            elif html[i] == '}':
                depth -= 1
            i += 1
        results.append((query, html[start:i - 1]))
    return results


def check_css_constraints(html_path: str | Path) -> dict:
    """Parse viewer.html CSS and return layout constraints."""
    html = open(html_path, encoding='utf-8').read()

    constraints = {}

    # evt-head
    block = parse_css_block(html, '.evt-head')
    if block:
        constraints['evt-head-height'] = parse_css_prop(block, 'height')
        constraints['evt-head-min-height'] = parse_css_prop(block, 'min-height')
        constraints['evt-head-overflow'] = parse_css_prop(block, 'overflow')
        constraints['evt-head-padding'] = parse_css_prop(block, 'padding')
        constraints['evt-head-gap'] = parse_css_prop(block, 'gap')

    # evt-card
    block = parse_css_block(html, '.evt-card')
    if block:
        constraints['evt-card-overflow'] = parse_css_prop(block, 'overflow')

    # evt-title
    block = parse_css_block(html, '.evt-title')
    if block:
        constraints['evt-title-font-size'] = parse_css_prop(block, 'font-size')
        constraints['evt-title-line-height'] = parse_css_prop(block, 'line-height')

    # evt-summary
    block = parse_css_block(html, '.evt-summary')
    if block:
        constraints['evt-summary-font-size'] = parse_css_prop(block, 'font-size')
        constraints['evt-summary-line-height'] = parse_css_prop(block, 'line-height')
        constraints['evt-summary-line-clamp'] = parse_css_prop(block, '-webkit-line-clamp')

    # day-col
    block = parse_css_block(html, '.day-col')
    if block:
        constraints['day-col-width'] = parse_css_prop(block, 'width')

    # media query overrides
    media_overrides = {}
    for query, content in parse_media_blocks(html):
        overrides = {}
        for sel in ['.evt-head', '.evt-summary', '.evt-card', '.day-col']:
            sel_pat = re.escape(sel) + r'\s*\{([^}]+)\}'
            m = re.search(sel_pat, content)
            if m:
                overrides[sel] = m.group(1).strip()
        if overrides:
            media_overrides[query] = overrides
    constraints['media_overrides'] = media_overrides

    return constraints


def get_layout_constants(constraints: dict) -> dict:
    """Derive numeric layout constants from parsed CSS."""
    def px(val, default):
        if val and val.endswith('px'):
            return float(val[:-2])
        return default

    def num(val, default):
        if val:
            try:
                return float(val)
            except ValueError:
                return default
        return default

    card_w = px(constraints.get('day-col-width'), 320)
    padding = constraints.get('evt-head-padding', '12px 14px 8px')
    # parse padding shorthand
    parts = padding.replace('px', '').split() if padding else []
    if len(parts) >= 3:
        pad_top, pad_h, pad_bottom = float(parts[0]), float(parts[1]), float(parts[2])
    else:
        pad_top, pad_h, pad_bottom = 12, 14, 8

    return {
        'card_width': card_w,
        'padding_h': pad_h,
        'inner_width': card_w - pad_h * 2,
        'padding_top': pad_top,
        'padding_bottom': pad_bottom,
        'gap': num(constraints.get('evt-head-gap'), 4),
        'meta_height': 28,  # badge row, not in CSS as explicit height
        'title_font': px(constraints.get('evt-title-font-size'), 16),
        'title_lh': num(constraints.get('evt-title-line-height'), 1.4),
        'summary_font': px(constraints.get('evt-summary-font-size'), 13),
        'summary_lh': num(constraints.get('evt-summary-line-height'), 1.5),
        'summary_clamp': int(num(constraints.get('evt-summary-line-clamp'), 3)),
    }


# ── Layout simulation ───────────────────────────────────────────────────

def estimate_lines(text: str, font_size: float, container_width: float) -> int:
    """Estimate number of lines text will take."""
    if not text:
        return 0
    avg_char_w = font_size * 0.7  # mix of Korean/ASCII
    chars_per_line = container_width / avg_char_w
    effective_chars = len(text) * 1.15  # word-wrap overhead
    return max(1, math.ceil(effective_chars / chars_per_line))


def test_card_visibility(evt: dict, head_height, lc: dict) -> dict:
    """Returns dict with visibility analysis."""
    title = evt.get("title", "")
    summary = evt.get("summary", "")

    title_lines = estimate_lines(title, lc['title_font'], lc['inner_width'])
    title_px = title_lines * lc['title_font'] * lc['title_lh']

    summary_lines = estimate_lines(summary, lc['summary_font'], lc['inner_width'])
    summary_px = summary_lines * lc['summary_font'] * lc['summary_lh']

    total_needed = (lc['padding_top'] + lc['padding_bottom']
                    + lc['meta_height'] + lc['gap'] + title_px + lc['gap'] + summary_px)

    if head_height is None:  # auto height
        available_for_summary = summary_px  # always shows
    else:
        used = (lc['padding_top'] + lc['padding_bottom']
                + lc['meta_height'] + lc['gap'] + title_px + lc['gap'])
        available_for_summary = head_height - used

    one_summary_line = lc['summary_font'] * lc['summary_lh']

    return {
        "event_id": evt["event_id"],
        "title_len": len(title),
        "summary_len": len(summary),
        "title_lines": title_lines,
        "title_h": round(title_px, 1),
        "summary_lines": summary_lines,
        "summary_h": round(summary_px, 1),
        "total_needed": round(total_needed, 1),
        "available_for_summary": round(available_for_summary, 1),
        "summary_visible": available_for_summary >= one_summary_line,
        "summary_fully_visible": available_for_summary >= summary_px,
    }


# ── Test assertions ──────────────────────────────────────────────────────

def test_no_fixed_height(constraints: dict) -> bool:
    """Assert evt-head has no fixed height constraint."""
    h = constraints.get('evt-head-height')
    assert h is None or h == 'auto', f"❌ evt-head has fixed height: {h}"
    print(f"✅ evt-head: no fixed height (height={h}, min-height={constraints.get('evt-head-min-height')})")
    return True


def test_no_card_overflow_hidden(constraints: dict) -> bool:
    """Check evt-card overflow allows content to show."""
    ov = constraints.get('evt-card-overflow')
    # 'hidden' is OK for evt-card (clips border-radius), the key is evt-head
    head_ov = constraints.get('evt-head-overflow')
    assert head_ov is None or head_ov in ('visible', 'unset'), \
        f"❌ evt-head has overflow: {head_ov}"
    print(f"✅ evt-head overflow: {head_ov} (card overflow: {ov})")
    return True


def test_summary_line_clamp(constraints: dict) -> bool:
    """Check summary line-clamp is reasonable (2-5 lines)."""
    clamp = constraints.get('evt-summary-line-clamp')
    if clamp:
        n = int(clamp)
        assert 2 <= n <= 5, f"❌ summary line-clamp out of range: {n}"
        print(f"✅ summary line-clamp: {n}")
    else:
        print(f"✅ summary: no line-clamp")
    return True


# ── Scenario runner ──────────────────────────────────────────────────────

def run_scenario(events: list, head_height, label: str, lc: dict):
    """Run visibility test for a scenario and print report."""
    results = [test_card_visibility(evt, head_height, lc) for evt in events]
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

    nv_mark = "✅" if len(not_visible) == 0 else "❌"
    print(f"요약 안보임: {len(not_visible)}개 {nv_mark}")

    pa_mark = "✅" if len(partial) == 0 else "⚠️"
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


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    if not VIEWER_HTML.exists():
        print(f"ERROR: {VIEWER_HTML} not found", file=sys.stderr)
        sys.exit(1)

    # Parse CSS constraints from viewer.html
    print("── CSS Constraint Check ──")
    constraints = check_css_constraints(VIEWER_HTML)

    print(f"\nParsed CSS values:")
    for k, v in sorted(constraints.items()):
        if k == 'media_overrides':
            continue
        print(f"  {k}: {v}")

    if constraints.get('media_overrides'):
        print(f"\nMedia query overrides:")
        for query, overrides in constraints['media_overrides'].items():
            print(f"  @media ({query}):")
            for sel, body in overrides.items():
                print(f"    {sel}: {body}")

    # Run CSS assertions
    print(f"\n── CSS Assertions ──")
    test_no_fixed_height(constraints)
    test_no_card_overflow_hidden(constraints)
    test_summary_line_clamp(constraints)

    # Derive layout constants from CSS
    lc = get_layout_constants(constraints)
    print(f"\n── Derived Layout Constants ──")
    for k, v in sorted(lc.items()):
        print(f"  {k}: {v}")

    # Load events and run scenarios
    if not NEWS_JSON.exists():
        print(f"\nWARNING: {NEWS_JSON} not found, skipping visibility scenarios", file=sys.stderr)
        return

    with open(NEWS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("events", [])
    print(f"\n로드된 이벤트 수: {len(events)}")

    # Scenario 1: auto height (current)
    run_scenario(events, head_height=None, label="head_height=None (auto)", lc=lc)

    # Scenario 2: old fixed 160px
    run_scenario(events, head_height=160, label="head_height=160px (old)", lc=lc)

    # Scenario 3: previous attempt 190px
    run_scenario(events, head_height=190, label="head_height=190px (previous)", lc=lc)


if __name__ == "__main__":
    main()
