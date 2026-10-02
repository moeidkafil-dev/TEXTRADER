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
