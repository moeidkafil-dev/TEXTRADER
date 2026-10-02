from fastapi.testclient import TestClient

from trader.web.server import create_app


def test_web_contract_and_manual_analysis():
    client = TestClient(create_app("BTC/USDT"))
    assert client.get("/api/health").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    r = client.post("/api/analyze/manual", json={
        "symbol": "BTC/USDT", "open": 100, "high": 103, "low": 99,
        "close": 102, "volume": 1200, "equity": 100000,
        "cash": 100000, "positions": {}, "news": [], "sentiment": 0,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["source"] == "manual"
    assert body["final"]["decision"] in {"BUY", "SELL", "WAIT", "RE-EVALUATE"}
    if body["order"]:
        assert body["order"]["size"] > 0
    assert len(body["risk"]["rules"]) == 11
