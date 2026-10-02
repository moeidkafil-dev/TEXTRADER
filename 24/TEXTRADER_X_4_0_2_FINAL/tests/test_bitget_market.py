from __future__ import annotations

from datetime import datetime, timezone

from trader.market.bitget import BitgetMarketClient, BitgetPublicSource


def _candle(ts: int, close: float = 100.0):
    return [str(ts), "99", "101", "98", str(close), "12.5", "1250"]


def _snapshot_payload():
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    # Two completed 1m candles; the newest is safely >1 minute old.
    return {
        "ticker": {
            "lastPrice": "100.5", "bid1Price": "100.4", "ask1Price": "100.5",
            "price24hPcnt": "0.0123", "volume24h": "1234"
        },
        "depth": {
            "bids": [[100.4, 2.0], [100.3, 3.0]],
            "asks": [[100.5, 1.5], [100.6, 2.5]],
        },
        "klines": [_candle(now - 180000, 100.0), _candle(now - 120000, 100.2)],
    }


class FakeClient:
    def snapshot(self, symbol, interval, limit):
        assert symbol == "BTC/USDT"
        assert interval == "1m"
        return _snapshot_payload()


def test_bitget_symbol_normalization():
    assert BitgetMarketClient.symbol("btc/usdt") == "BTCUSDT"
    assert BitgetMarketClient.symbol("ETH-USDT") == "ETHUSDT"


def test_bitget_public_source_maps_real_shapes():
    bundles = BitgetPublicSource(["BTC/USDT"], client=FakeClient()).fetch("c1")
    assert [b.quality for b in bundles] == ["ok", "ok"]
    market, book = bundles
    assert market.source == "bitget://rest/market"
    assert market.payload["ohlcv"]["close"] == 100.2
    assert book.payload["order_book"]["bids"][0] == [100.4, 2.0]
    assert book.payload["order_book"]["asks"][0] == [100.5, 1.5]


def test_bitget_source_fails_closed_on_client_error():
    class Broken:
        def snapshot(self, *args, **kwargs):
            raise TimeoutError("network")
    bundles = BitgetPublicSource(["BTC/USDT"], client=Broken()).fetch("c1")
    assert len(bundles) == 2
    assert all(b.quality == "missing" for b in bundles)
    assert all(b.hash == "missing" for b in bundles)


def test_bitget_source_rejects_crossed_book():
    class Crossed:
        def snapshot(self, *args, **kwargs):
            x = _snapshot_payload()
            x["depth"]["bids"][0][0] = 101.0
            return x
    bundles = BitgetPublicSource(["BTC/USDT"], client=Crossed()).fetch("c1")
    assert all(b.quality == "missing" for b in bundles)


def test_cli_decision_only_flag_is_available():
    from trader.cli import build_parser
    a = build_parser().parse_args(["analyze", "BTC/USDT", "--source", "bitget", "--decision-only"])
    p = build_parser().parse_args(["paper", "BTC/USDT", "--source", "bitget", "--decision-only"])
    assert a.decision_only is True
    assert p.decision_only is True
