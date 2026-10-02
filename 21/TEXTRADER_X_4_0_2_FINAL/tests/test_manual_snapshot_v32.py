from fastapi.testclient import TestClient

from trader.web.server import create_app


BASE = {
    "schema_version": "1.0",
    "snapshot_id": "manual-test-001",
    "symbol": "BTC/USDT",
    "exchange": "manual",
    "timestamp": "2026-09-26T20:00:00Z",
    "timeframe": "5m",
    "open": 109300,
    "high": 109600,
    "low": 109200,
    "close": 109500,
    "volume": 125.4,
    "order_book": {"bids": [[109490, 2.4], [109480, 5.1]], "asks": [[109500, 1.8], [109510, 4.2]]},
    "trades": {"buy_volume": 72.8, "sell_volume": 52.6, "trade_count": 184},
    "derivatives": {"funding_rate": 0.0001, "open_interest": 125000000},
    "volatility": {"atr": 420, "realized_1h": 0.018},
    "technical": {"rsi_14": 57.4, "vwap": 109210},
    "sentiment": 0,
    "news": [{"title": "neutral test", "source": "manual"}],
    "macro": {"risk_mode": "neutral"},
    "onchain": {"whale_activity": None},
    "equity": 100000,
    "cash": 100000,
    "positions": {},
    "risk_limits": {"max_position_pct": 0.05},
    "execution": {"order_type": "limit", "fee_rate": 0.0004},
    "data_quality": {"source": "manual", "completeness": 1.0},
    "agent_context": {"notes": "integration test"},
}


def test_advanced_manual_snapshot_is_accepted_and_audited():
    client = TestClient(create_app("BTC/USDT"))
    response = client.post("/api/analyze/manual", json=BASE)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["meta"]["source"] == "manual"
    assert body["meta"]["symbol"] == "BTC/USDT"
    assert body["final"]["decision"] in {"BUY", "SELL", "WAIT", "RE-EVALUATE"}
    market = body["context"]["sections"] if "context" in body else []
    assert body["errors"] == []
    assert len(body["risk"]["rules"]) == 11


def test_invalid_ohlc_is_rejected_cleanly():
    client = TestClient(create_app("BTC/USDT"))
    payload = dict(BASE, high=100000, low=109200)
    response = client.post("/api/analyze/manual", json=payload)
    assert response.status_code == 422
    assert "high must be" in response.text


def test_crossed_orderbook_is_rejected_cleanly():
    client = TestClient(create_app("BTC/USDT"))
    payload = dict(BASE, order_book={"bids": [[109600, 1]], "asks": [[109500, 1]]})
    response = client.post("/api/analyze/manual", json=payload)
    assert response.status_code == 422
    assert "best bid" in response.text


def test_unknown_fields_are_rejected_instead_of_silently_ignored():
    client = TestClient(create_app("BTC/USDT"))
    payload = dict(BASE, typo_field=123)
    response = client.post("/api/analyze/manual", json=payload)
    assert response.status_code == 422
    assert "extra_forbidden" in response.text


def test_openapi_exposes_professional_manual_contract():
    client = TestClient(create_app("BTC/USDT"))
    spec = client.get("/openapi.json").json()
    schema = spec["components"]["schemas"]["ManualDataRequest"]
    props = schema["properties"]
    for field in ("order_book", "trades", "derivatives", "volatility", "technical", "macro", "onchain", "risk_limits", "execution", "data_quality", "agent_context"):
        assert field in props
