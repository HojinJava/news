#!/usr/bin/env python3
"""fetch_market.py — yfinance로 카테고리별 시장 데이터를 수집한다."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yfinance as yf


def calc_window_delta(bars: list[dict], baseline: float) -> float:
    """분봉 리스트에서 baseline 대비 마지막 종가의 변화율(%)을 반환한다."""
    if not bars or baseline == 0:
        return 0.0
    last_close = bars[-1]["close"]
    return round((last_close - baseline) / baseline * 100, 4)


def build_market_json(tickers: dict, generated_at: str) -> dict:
    return {"generated_at": generated_at, "tickers": tickers}


def _fetch_daily(ticker: str, date_from: str, date_to: str) -> list[dict]:
    """일봉 OHLCV를 반환한다."""
    t = yf.Ticker(ticker)
    df = t.history(start=date_from, end=date_to, interval="1d")
    if df.empty:
        return []
    rows = []
    for ts, row in df.iterrows():
        rows.append({
            "date": ts.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "volume": int(row["Volume"]),
        })
    return rows


def _fetch_minute_window(ticker: str, event_time: str) -> list[dict]:
    """이벤트 시각 -30분 ~ +5분 분봉을 반환한다.

    yfinance 1분봉은 최근 30일치만 지원한다. 30일 초과 이벤트는 빈 리스트.
    """
    try:
        dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
    except ValueError:
        return []

    now = datetime.now(timezone.utc)
    if (now - dt).days > 29:
        return []

    w_start = dt - timedelta(minutes=30)
    w_end   = dt + timedelta(minutes=6)

    t = yf.Ticker(ticker)
    df = t.history(
        start=w_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end=w_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        interval="1m",
    )
    if df.empty:
        return []

    bars = []
    for ts, row in df.iterrows():
        bars.append({
            "time": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
        })
    return bars


def fetch_category_market(category_slug: str, incremental: bool = False) -> None:
    """카테고리 config.json + news.json을 읽어 market.json을 생성/업데이트한다."""
    base = Path("data") / category_slug
    config = json.loads((base / "config.json").read_text(encoding="utf-8"))
    news   = json.loads((base / "news.json").read_text(encoding="utf-8"))

    markets   = config["markets"]
    events    = news["events"]
    date_from = news["date_range"]["from"]
    date_to   = news["date_range"]["to"]

    market_path = base / "market.json"
    existing: dict = {}
    if incremental and market_path.exists():
        existing = json.loads(market_path.read_text(encoding="utf-8"))

    tickers_data: dict = existing.get("tickers", {})

    for mkt in markets:
        ticker = mkt["ticker"]
        print(f"  [{ticker}] 일봉 수집 중...")
        daily = _fetch_daily(ticker, date_from, date_to)

        windows: dict = tickers_data.get(ticker, {}).get("windows", {})

        for evt in events:
            evt_id   = evt["event_id"]
            times = [a["published_date"] for a in evt.get("articles", []) if a.get("published_date")]
            evt_time = sorted(times)[0] if times else evt.get("date", "") + "T00:00:00Z"

            if evt_id in windows and incremental:
                continue

            print(f"    [{ticker}] 이벤트 {evt_id} 분봉 수집 중...")
            bars = _fetch_minute_window(ticker, evt_time)

            baseline_close = 0.0
            if daily:
                evt_date = evt_time[:10]
                prev = [d for d in daily if d["date"] < evt_date]
                if prev:
                    baseline_close = prev[-1]["close"]

            delta = calc_window_delta(bars, baseline_close) if bars else 0.0

            windows[evt_id] = {
                "event_time": evt_time,
                "bars": bars,
                "baseline_close": baseline_close,
                "delta_pct": delta,
            }

            for e in events:
                if e["event_id"] == evt_id:
                    if "market_impact" not in e:
                        e["market_impact"] = {}
                    e["market_impact"][mkt["key"]] = {
                        "delta_pct": delta,
                        "window_start": evt_time,
                        "window_end": evt_time,
                    }

        tickers_data[ticker] = {"daily": daily, "windows": windows}

    market_json = build_market_json(tickers_data, datetime.now(timezone.utc).isoformat())
    market_path.write_text(json.dumps(market_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  market.json 저장: {market_path}")

    (base / "news.json").write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  news.json market_impact 업데이트 저장")


def main() -> None:
    parser = argparse.ArgumentParser(description="시장 데이터 수집기")
    parser.add_argument("--category", required=True, help="카테고리 슬러그 (예: iran-war)")
    parser.add_argument("--incremental", action="store_true", help="증분 업데이트")
    args = parser.parse_args()

    print(f"=== Market Fetcher: {args.category} ===")
    fetch_category_market(args.category, incremental=args.incremental)
    print("=== 완료 ===")


if __name__ == "__main__":
    main()
