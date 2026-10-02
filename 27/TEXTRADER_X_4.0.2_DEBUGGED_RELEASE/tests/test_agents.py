"""Agent tests — REQ-AG-01..06."""
import pytest

from trader.core.schemas import (
    Context, ContextSection, InitialDecision, FailureReport, FailurePath,
    FinalDecision, Action, FailureCategory, Severity,
)
from trader.services.agent1 import Agent1
from trader.services.agent2 import Agent2
from trader.services.agent3 import Agent3


def _ctx(cycle_id="c", bundles_data=None):
    sections = [
        ContextSection(name="market_data", source="test", version="1",
                       data={"bundles": bundles_data or []}, empty=False),
        ContextSection(name="memory", source="test", version="1",
                       data={}, empty=True),
        ContextSection(name="previous_decisions", source="test", version="1",
                       data={"decisions": []}, empty=False),
        ContextSection(name="market_state", source="test", version="1",
                       data={}, empty=True),
        ContextSection(name="user_config", source="test", version="1",
                       data={"risk_appetite": "moderate"}, empty=False),
    ]
    return Context(cycle_id=cycle_id, sections=tuple(sections))


def _ohlcv_bundle(inst="XIR/USDT", o=100, h=101, l=99, c=100.5):
    return {
        "source": "mock://ohlcv",
        "timestamp": "2026-09-22T00:00:00+00:00",
        "quality": "ok",
        "bundle_id": "b1",
        "hash": "h1",
        "payload": {"instrument": inst, "ohlcv": {"open": o, "high": h, "low": l, "close": c, "volume": 1000}},
    }


def _news_bundle(sentiment=0):
    return {
        "source": "mock://news",
        "timestamp": "2026-09-22T00:00:00+00:00",
        "quality": "ok",
        "bundle_id": "bn",
        "hash": "hn",
        "payload": {"headlines": ["x"], "sentiment": sentiment},
    }


def _book_bundle(bids=None, asks=None):
    return {
        "source": "mock://orderbook",
        "timestamp": "2026-09-22T00:00:00+00:00",
        "quality": "ok",
        "bundle_id": "bb",
        "hash": "hb",
        "payload": {"instrument": "XIR/USDT",
                     "order_book": {"bids": bids or [[99, 100]], "asks": asks or [[101, 100]]}},
    }


def test_agent1_produces_initial_decision(orchestrator):
    """REQ-AG-02 — InitialDecision conformant to schema."""
    ctx = _ctx("c1", bundles_data=[_ohlcv_bundle(), _book_bundle(), _news_bundle()])
    initial = orchestrator.agent1.run(ctx)
    assert initial.action in Action.values()
    assert initial.instrument == "XIR/USDT"
    assert initial.rationale


def test_agent2_covers_all_9_categories(orchestrator):
    """REQ-AG-03 / TST-SYS-08 — FailureReport must cover all 9 categories."""
    ctx = _ctx("c2", bundles_data=[_ohlcv_bundle(), _book_bundle(), _news_bundle()])
    initial = orchestrator.agent1.run(ctx)
    report = orchestrator.agent2.run(ctx, initial)
    covered = {p.category for p in report.paths}
    # A valid order book is explicitly analyzed by Agent2 as F9=low.
    # The category must still be present because Agent2's contract requires
    # all nine categories to be represented.
    expected = {c.value for c in FailureCategory.all()}
    assert covered == expected


def test_agent2_blocking_when_missing_data(orchestrator):
    """TST-SYS-10 / F3 — missing data ⇒ blocking severity."""
    from trader.services.data_reader import UnreachableSource
    from trader.services.data_reader import DataReader
    dr = DataReader([UnreachableSource()])
    bundles = dr.read("c3")
    ctx = orchestrator.context_maker.make("c3", bundles)
    initial = orchestrator.agent1.run(ctx)
    report = orchestrator.agent2.run(ctx, initial)
    f3 = next(p for p in report.paths if p.category == "missing_data")
    assert f3.severity == Severity.BLOCKING.value


def test_agent3_blocking_failure_yields_wait(orchestrator):
    """TST-SYS-01 — Agent1=BUY, Agent2 blocking, Agent3=WAIT; override recorded."""
    ctx = _ctx("c4", bundles_data=[_ohlcv_bundle(), _book_bundle(),
                                      _news_bundle(sentiment=-1)])
    initial = InitialDecision(cycle_id="c4", action="BUY", instrument="XIR/USDT",
                              rationale="momentum", assumptions=("a",), evidence=("e",))
    # build a blocking failure report manually
    paths = []
    for c in FailureCategory.all():
        paths.append(FailurePath(category=c.value, description="x",
                                  severity=(Severity.BLOCKING.value
                                            if c == FailureCategory.F3_MISSING_DATA
                                            else Severity.LOW.value)))
    report = FailureReport(cycle_id="c4", paths=tuple(paths))
    final = orchestrator.agent3.run(ctx, initial, report)
    assert final.decision == Action.WAIT.value
    assert final.overrode_initial is True
    assert "F3" in final.reason or "missing_data" in final.reason


def test_agent3_overrides_buy_to_wait_on_contradictory_evidence(orchestrator):
    """Override BUY→WAIT when F6 high, no blocking (chapter 06)."""
    ctx = _ctx("c5", bundles_data=[_ohlcv_bundle(), _book_bundle(), _news_bundle()])
    initial = InitialDecision(cycle_id="c5", action="BUY", instrument="XIR/USDT",
                              rationale="x", assumptions=("a",))
    paths = []
    for c in FailureCategory.all():
        sev = (Severity.HIGH.value
               if c == FailureCategory.F6_CONTRADICTORY_EVIDENCE
               else Severity.LOW.value)
        paths.append(FailurePath(category=c.value, description="x", severity=sev))
    report = FailureReport(cycle_id="c5", paths=tuple(paths))
    final = orchestrator.agent3.run(ctx, initial, report)
    assert final.decision == Action.WAIT.value
    assert final.overrode_initial is True


def test_agent3_accepts_buy_when_no_blocking(orchestrator):
    """No blocking + no F6 high ⇒ accept initial BUY."""
    ctx = _ctx("c6", bundles_data=[_ohlcv_bundle(c=101), _book_bundle(), _news_bundle(0)])
    initial = InitialDecision(cycle_id="c6", action="BUY", instrument="XIR/USDT",
                              rationale="x", assumptions=("a",))
    paths = tuple(FailurePath(category=c.value, description="x", severity="low")
                   for c in FailureCategory.all())
    report = FailureReport(cycle_id="c6", paths=paths)
    final = orchestrator.agent3.run(ctx, initial, report)
    assert final.decision == Action.BUY.value
    assert final.overrode_initial is False


def test_agent3_reevaluate_on_execution_impossibility(orchestrator):
    """F9 blocking ⇒ RE-EVALUATE (chapter 06)."""
    ctx = _ctx("c7", bundles_data=[_ohlcv_bundle(), _book_bundle(), _news_bundle()])
    initial = InitialDecision(cycle_id="c7", action="BUY", instrument="XIR/USDT",
                              rationale="x", assumptions=("a",))
    paths = []
    for c in FailureCategory.all():
        sev = (Severity.BLOCKING.value
               if c == FailureCategory.F9_EXECUTION_IMPOSSIBILITY
               else Severity.LOW.value)
        paths.append(FailurePath(category=c.value, description="x", severity=sev))
    report = FailureReport(cycle_id="c7", paths=tuple(paths))
    final = orchestrator.agent3.run(ctx, initial, report)
    assert final.decision == Action.RE_EVALUATE.value


def test_agent_invalid_output_to_wait(orchestrator):
    """TST-SYS-08 — invalid agent output ⇒ WAIT (I5)."""
    # Build a context with no market data ⇒ agent1 fallback path
    ctx = _ctx("c8", bundles_data=[])
    initial = orchestrator.agent1.run(ctx)
    assert initial.action == Action.WAIT.value
