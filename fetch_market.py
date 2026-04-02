#!/usr/bin/env python3
"""fetch_market.py — yfinance로 카테고리별 시장 데이터를 수집한다."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yfinance as yf


def _sanitize(obj):
    """NaN/Infinity → None (JSON null). 재귀적으로 처리."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def calc_window_delta(bars: list[dict], baseline: float) -> float:
    """분봉 리스트에서 baseline 대비 마지막 종가의 변화율(%)을 반환한다."""
    if not bars or baseline == 0:
        return 0.0
    last_close = bars[-1]["close"]
    return round((last_close - baseline) / baseline * 100, 4)


def _aggregate_10min(bars: list[dict], event_time_iso: str) -> list[dict]:
    """5분봉 리스트를 이벤트 시각 기준 10분봉으로 집계한다.

    각 bar에 label(KST HH:MM)과 isEvent(이벤트 버킷 여부)를 추가한다.
    viewer.html이 연산 없이 바로 렌더링할 수 있는 포맷으로 반환한다.
    """
    try:
        evt_dt = datetime.fromisoformat(event_time_iso.replace("Z", "+00:00"))
    except ValueError:
        return []

    KST = timezone(timedelta(hours=9))
    buckets: dict[int, dict] = {}
    for b in bars:
        try:
            bar_dt = datetime.fromisoformat(b["time"].replace("Z", "+00:00"))
        except ValueError:
            continue
        diff_min = (bar_dt - evt_dt).total_seconds() / 60
        bucket_key = int(diff_min // 10) * 10  # -30, -20, -10, 0, 10, 20
        if bucket_key not in buckets:
            buckets[bucket_key] = {
                "open": b["open"], "high": b["high"],
                "low": b["low"], "close": b["close"], "time": b["time"],
            }
        else:
            cur = buckets[bucket_key]
            cur["high"] = max(cur["high"], b["high"])
            cur["low"] = min(cur["low"], b["low"])
            cur["close"] = b["close"]

    result = []
    for k in sorted(buckets.keys()):
        v = buckets[k]
        bar_dt = datetime.fromisoformat(v["time"].replace("Z", "+00:00"))
        kst_dt = bar_dt.astimezone(KST)
        result.append({
            "open": v["open"], "high": v["high"], "low": v["low"], "close": v["close"],
            "time": v["time"],
            "label": kst_dt.strftime("%H:%M"),
            "isEvent": k == 0,
        })
    # isEvent bar가 없으면 (거래시간 미겹침 or 시간 미상) 중간 bar 마킹
    if result and not any(r["isEvent"] for r in result):
        result[len(result) // 2]["isEvent"] = True
    return result


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
    # 전일 종가 대비 등락률 사전 계산 (viewer.html 연산 불필요)
    for i, bar in enumerate(rows):
        if i == 0:
            bar["delta_pct"] = 0.0
        else:
            prev = rows[i - 1]["close"]
            bar["delta_pct"] = round((bar["close"] - prev) / prev * 100, 4) if prev else 0.0
    return rows


def _fetch_minute_window(ticker: str, event_time: str) -> list[dict]:
    """이벤트 시각 -30분 ~ +30분 분봉을 반환한다.

    5분봉(interval=5m)은 최근 60일치를 지원한다.
    60일 초과 이벤트는 빈 리스트.
    """
    try:
        dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
    except ValueError:
        return []

    now = datetime.now(timezone.utc)
    if (now - dt).days > 59:
        return []

    w_start = dt - timedelta(minutes=30)
    w_end   = dt + timedelta(minutes=31)

    t = yf.Ticker(ticker)
    df = t.history(
        start=w_start,
        end=w_end,
        interval="5m",
    )
    if df.empty:
        return []

    bars = []
    for ts, row in df.iterrows():
        utc_ts = ts.astimezone(timezone.utc)
        bars.append({
            "time": utc_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
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
            raw_time = evt.get("time", "")
            has_real_time = raw_time and raw_time != "00:00:00Z"
            evt_time = (evt.get("date", "") + "T" + raw_time) if has_real_time else evt.get("date", "") + "T00:00:00Z"

            if evt_id in windows and incremental:
                continue

            print(f"    [{ticker}] 이벤트 {evt_id} 분봉 수집 중...")
            bars = _fetch_minute_window(ticker, evt_time) if has_real_time else []

            baseline_close = 0.0
            if daily:
                evt_date = evt_time[:10]
                prev = [d for d in daily if d["date"] < evt_date]
                if prev:
                    baseline_close = prev[-1]["close"]

            delta = calc_window_delta(bars, baseline_close) if bars else 0.0

            bars10 = _aggregate_10min(bars, evt_time) if bars else []
            windows[evt_id] = {
                "event_time": evt_time,
                "bars": bars,
                "bars10": bars10,
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
    market_path.write_text(json.dumps(_sanitize(market_json), ensure_ascii=False, indent=2), encoding="utf-8")
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
