from fetch_market import build_market_json, calc_window_delta

def test_calc_window_delta_positive():
    bars = [
        {"time": "2026-03-28T07:30:00Z", "close": 71.9},
        {"time": "2026-03-28T07:31:00Z", "close": 72.5},
        {"time": "2026-03-28T08:05:00Z", "close": 74.9},
    ]
    delta = calc_window_delta(bars, baseline=71.9)
    assert abs(delta - ((74.9 - 71.9) / 71.9 * 100)) < 0.01

def test_calc_window_delta_empty_returns_zero():
    assert calc_window_delta([], baseline=100.0) == 0.0

def test_build_market_json_structure():
    result = build_market_json(
        tickers={"CL=F": {"daily": [], "windows": {}}},
        generated_at="2026-04-01T00:00:00Z"
    )
    assert "generated_at" in result
    assert "tickers" in result
    assert "CL=F" in result["tickers"]
