#!/usr/bin/env python3
"""fetch_sites.py — parse_config 기반으로 authoritative_sources를 Python으로 파싱한다.

parse_config가 없으면 실행 중단 → Site-Analyzer 에이전트를 먼저 실행해야 한다.
날짜 추출 실패 시 needs_ai_date=true 로 마킹 → Event-Merger 에이전트가 AI로 처리.
번역 없음 (EN 필드만) → Event-Merger 에이전트가 번역.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; news-fetcher/1.0)"}
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


# ─── HTTP ───────────────────────────────────────────────────────────────────

def _get(url: str) -> BeautifulSoup:
    resp = requests.get(url, timeout=20, headers=HEADERS)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


# ─── 날짜·시간 파싱 ──────────────────────────────────────────────────────────

def _parse_date(raw: str) -> str | None:
    """텍스트에서 YYYY-MM-DD 추출. 실패 시 None."""
    if not raw:
        return None
    # ISO
    m = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
    if m:
        return m.group(1)
    # "February 28" / "28 February" / "February 28, 2026"
    raw_l = raw.lower()
    for name, num in MONTHS.items():
        if name in raw_l:
            day_m = re.search(r"\b(\d{1,2})\b", raw_l)
            year_m = re.search(r"\b(20\d{2})\b", raw_l)
            if day_m:
                year = int(year_m.group(1)) if year_m else datetime.now().year
                return f"{year}-{num:02d}-{int(day_m.group(1)):02d}"
    return None


def _parse_time(raw: str) -> str:
    """텍스트에서 HH:MM:00Z 추출. 실패 시 00:00:00Z."""
    if not raw:
        return "00:00:00Z"
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", raw)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}:00Z"
    return "00:00:00Z"


# ─── 이벤트 추출 ─────────────────────────────────────────────────────────────

def _build_event(item: BeautifulSoup, source: dict, url: str, page_date: str | None) -> dict | None:
    pc = source["parse_config"]

    # 제목
    title = ""
    if pc.get("title_selector"):
        el = item.select_one(pc["title_selector"])
        title = el.get_text(strip=True) if el else ""
    if not title:
        title = item.get_text(separator=" ", strip=True)[:150]
    if not title:
        return None

    # 설명
    desc = ""
    if pc.get("description_selector"):
        el = item.select_one(pc["description_selector"])
        desc = el.get_text(strip=True) if el else ""

    # 시간
    time_str = "00:00:00Z"
    time_raw = ""
    if pc.get("time_selector"):
        el = item.select_one(pc["time_selector"])
        if el:
            time_raw = el.get_text(strip=True)
            time_str = _parse_time(time_raw)

    # 날짜: 이벤트 요소 내부 → page_date 순으로 시도
    date: str | None = None
    date_raw = ""
    if pc.get("date_selector"):
        el = item.select_one(pc["date_selector"])
        if el:
            date_raw = el.get_text(strip=True)
            date = _parse_date(date_raw)
    if not date:
        date = page_date

    needs_ai_date = date is None

    e: dict = {
        "date":        date or "",
        "time":        time_str,
        "title_en":    title,
        "description_en": desc,
        "source_site": source["name"].lower().replace(" ", ""),
        "source_url":  url,
    }
    # AI 처리 필요 마킹
    if needs_ai_date:
        e["needs_ai_date"] = True
        e["context_text"] = item.get_text(separator=" ", strip=True)[:400]
    # 시간 추출 실패 시 원문 보존 (AI 재파싱용)
    if time_raw and time_str == "00:00:00Z":
        e["time_raw"] = time_raw

    return e


# ─── method: subpages ────────────────────────────────────────────────────────

def _parse_subpages(source: dict, date_from: str, date_to: str) -> list[dict]:
    """Day별 서브페이지를 순회하며 이벤트 추출. 404 또는 범위 초과 시 중단."""
    pc = source["parse_config"]
    pattern = pc["subpage_pattern"]
    events: list[dict] = []
    n = 1

    while True:
        url = pattern.replace("{N}", str(n))
        try:
            soup = _get(url)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                print(f"    day-{n} 없음 → 순회 종료")
            else:
                print(f"    day-{n} 오류: {e}")
            break
        except Exception as e:
            print(f"    day-{n} 오류: {e}")
            break

        # 페이지에서 날짜 추출 (URL 패턴 또는 페이지 내 heading)
        page_date = _extract_date_from_url(url, pc) or _extract_date_from_page(soup, pc)

        # 범위 체크: 날짜가 확정된 경우만 필터링
        if page_date:
            if page_date > date_to:
                print(f"    day-{n} ({page_date}) > date_to → 순회 종료")
                break
            if page_date < date_from:
                print(f"    day-{n} ({page_date}) < date_from → 건너뜀")
                n += 1
                continue

        selector = pc.get("event_selector", "li")
        page_events = []
        for item in soup.select(selector):
            e = _build_event(item, source, url, page_date)
            if e:
                page_events.append(e)

        print(f"    day-{n} ({page_date or '날짜미상'}): {len(page_events)}건")
        events.extend(page_events)
        n += 1

    return events


# ─── method: single_page ────────────────────────────────────────────────────

def _parse_single_page(source: dict, date_from: str, date_to: str) -> list[dict]:
    """단일 페이지에서 날짜 섹션별로 이벤트 추출 (Wikipedia 등)."""
    pc = source["parse_config"]
    url = source["url"]
    soup = _get(url)
    events: list[dict] = []

    heading_sel = pc.get("section_heading_selector", "h2, h3")
    event_sel = pc.get("event_selector", "li")

    for heading in soup.select(heading_sel):
        heading_text = heading.get_text(strip=True)
        date = _parse_date(heading_text)
        if not date:
            continue
        if date < date_from or date > date_to:
            continue

        # heading 다음 형제 노드에서 이벤트 수집
        sibling = heading.next_sibling
        section_items: list[BeautifulSoup] = []
        while sibling:
            tag = getattr(sibling, "name", None)
            if tag in ("h2", "h3"):
                break
            if tag:
                section_items.extend(sibling.select(event_sel))
            sibling = sibling.next_sibling

        page_events = []
        for item in section_items:
            e = _build_event(item, source, url + f"#{heading.get('id','')}", date)
            if e:
                page_events.append(e)

        print(f"    섹션 {date}: {len(page_events)}건")
        events.extend(page_events)

    return events


# ─── 날짜 추출 헬퍼 ──────────────────────────────────────────────────────────

def _extract_date_from_url(url: str, pc: dict) -> str | None:
    pattern = pc.get("url_date_pattern")
    if not pattern:
        return None
    m = re.search(pattern, url)
    return _parse_date(m.group(0)) if m else None


def _extract_date_from_page(soup: BeautifulSoup, pc: dict) -> str | None:
    sel = pc.get("page_date_selector")
    if not sel:
        return None
    el = soup.select_one(sel)
    return _parse_date(el.get_text(strip=True)) if el else None


# ─── 메인 ────────────────────────────────────────────────────────────────────

def fetch_category_sites(slug: str, date_from: str, date_to: str) -> None:
    base = Path("data") / slug
    config = json.loads((base / "config.json").read_text(encoding="utf-8"))

    all_events: list[dict] = []
    sources_meta: list[dict] = []

    for source in config.get("authoritative_sources", []):
        pc = source.get("parse_config")
        if not pc:
            print(f"  [{source['name']}] ⚠ parse_config 없음 → Site-Analyzer 에이전트 먼저 실행 필요")
            continue

        method = pc.get("method")
        print(f"  [{source['name']}] 파싱 시작 (method={method})")

        try:
            if method == "subpages":
                events = _parse_subpages(source, date_from, date_to)
            elif method == "single_page":
                events = _parse_single_page(source, date_from, date_to)
            else:
                print(f"  [{source['name']}] ⚠ 알 수 없는 method: {method}")
                continue
        except Exception as ex:
            print(f"  [{source['name']}] ❌ 파싱 오류: {ex}")
            continue

        ai_needed = sum(1 for e in events if e.get("needs_ai_date"))
        if ai_needed:
            print(f"  [{source['name']}] ⚠ 날짜 추출 실패 {ai_needed}건 → Event-Merger가 AI로 처리")

        print(f"  [{source['name']}] 완료: {len(events)}건")
        all_events.extend(events)
        sources_meta.append({
            "name": source["name"],
            "url": source["url"],
            "events_count": len(events),
            "ai_needed": ai_needed,
        })

    # raw_id 부여
    for i, e in enumerate(all_events):
        e["raw_id"] = f"{e['source_site']}-{i + 1:03d}"

    out_dir = Path("pipeline") / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "01_site_events.json"

    ai_total = sum(1 for e in all_events if e.get("needs_ai_date"))
    result = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date_range": {"from": date_from, "to": date_to},
        "sources": sources_meta,
        "total": len(all_events),
        "ai_date_needed": ai_total,
        "events": all_events,
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  저장 완료: {out_path}")
    print(f"  총 {len(all_events)}건 (날짜 AI 처리 필요: {ai_total}건)")


def main() -> None:
    parser = argparse.ArgumentParser(description="authoritative_sources Python 파싱")
    parser.add_argument("--category", required=True, help="카테고리 슬러그 (예: iran-war)")
    parser.add_argument("--date-from", required=True, help="수집 시작일 YYYY-MM-DD")
    parser.add_argument("--date-to",   required=True, help="수집 종료일 YYYY-MM-DD")
    args = parser.parse_args()

    print(f"=== Site Fetcher (Python): {args.category} ===")
    fetch_category_sites(args.category, args.date_from, args.date_to)
    print("=== 완료 ===")


if __name__ == "__main__":
    main()
