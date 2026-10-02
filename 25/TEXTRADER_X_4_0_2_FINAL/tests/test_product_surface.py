from trader.market.binance import BinanceMarketClient
from trader.cli import build_parser


def test_professional_cli_has_core_commands():
    p = build_parser()
    assert p.parse_args(["doctor"]).command == "doctor"
    assert p.parse_args(["market", "BTC/USDT"]).command == "market"
    assert p.parse_args(["analyze", "BTC/USDT"]).command == "analyze"
    assert p.parse_args(["paper", "BTC/USDT", "--cycles", "2"]).command == "paper"
    assert p.parse_args(["backtest", "--bars", "10"]).command == "backtest"
    assert p.parse_args(["kill-switch", "on"]).command == "kill-switch"
    assert p.parse_args(["web"]).command == "web"


def test_binance_symbol_normalization():
    assert BinanceMarketClient.symbol("BTC/USDT") == "BTCUSDT"
    assert BinanceMarketClient.symbol("eth-usdt") == "ETHUSDT"


def test_paper_parser_does_not_require_mode_attribute():
    p = build_parser()
    args = p.parse_args(["paper", "BTC/USDT", "--source", "mock", "--cycles", "1"])
    # The command must be buildable even though paper has no --mode option.
    assert args.command == "paper"
    assert args.cycles == 1


def test_snapshot_discards_open_candle():
    from trader.market.binance import BinanceMarketClient

    class Fake(BinanceMarketClient):
        def __init__(self):
            pass

        def ticker(self, symbol):
            return {"lastPrice": "100", "bidPrice": "99", "askPrice": "101",
                    "priceChangePercent": "1", "volume": "10"}

        def depth(self, symbol, limit=20):
            return {"bids": [["99", "1"]], "asks": [["101", "1"]]}

        def klines(self, symbol, interval="1m", limit=200):
            now = int(__import__("time").time() * 1000)
            return [
                [now - 120000, "99", "101", "98", "100", "10", now - 60001, "0", 1, "0", "0", "0"],
                [now - 30000, "100", "102", "99", "101", "12", now + 30000, "0", 1, "0", "0", "0"],
            ]

    snap = Fake().snapshot("BTC/USDT", "1m", 100)
    assert len(snap["klines"]) == 1
    assert snap["klines"][0][4] == "100"



def test_binance_base_url_uses_environment(monkeypatch):
    monkeypatch.setenv("BINANCE_BASE_URL", "https://data-api.binance.vision/")
    client = BinanceMarketClient()
    assert client.base_url == "https://data-api.binance.vision"
    explicit = BinanceMarketClient("https://example.test/")
    assert explicit.base_url == "https://example.test"


def test_binance_public_source_network_failure_is_missing_not_exception():
    from trader.market.binance import BinancePublicSource

    class FailingClient:
        def snapshot(self, symbol, interval, limit):
            raise TimeoutError("upstream unavailable")

    bundles = BinancePublicSource(["BTC/USDT"], client=FailingClient()).fetch("cycle")
    assert len(bundles) == 2
    assert {b.source for b in bundles} == {
        "binance://rest/market", "binance://rest/orderbook"
    }
    assert all(b.quality == "missing" for b in bundles)
    assert all(b.payload["instrument"] == "BTC/USDT" for b in bundles)
    assert all("TimeoutError" in b.payload["error"] for b in bundles)


def test_binance_public_source_empty_closed_klines_is_missing():
    from trader.market.binance import BinancePublicSource

    class EmptyBarsClient:
        def snapshot(self, symbol, interval, limit):
            return {
                "ticker": {
                    "lastPrice": "100", "bidPrice": "99", "askPrice": "101",
                    "priceChangePercent": "1", "volume": "10",
                },
                "depth": {"bids": [["99", "1"]], "asks": [["101", "1"]]},
                "klines": [],
            }

    bundles = BinancePublicSource(["BTC/USDT"], client=EmptyBarsClient()).fetch("cycle")
    assert len(bundles) == 2
    assert all(b.quality == "missing" for b in bundles)
    assert all("ohlcv" not in b.payload for b in bundles)
