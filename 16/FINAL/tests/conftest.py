"""Shared pytest fixtures."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Make `trader` importable without install
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "trader_test.db")


@pytest.fixture
def orchestrator(tmp_db):
    from trader.core.config import RiskConfig, TraderConfig
    from trader.engine.orchestrator import Orchestrator
    rc = RiskConfig()
    tc = TraderConfig()
    tc.db_path = tmp_db
    tc.enable_user_veto = False  # silence ⇒ execute
    tc.enable_email = False
    tc.enable_telegram = False
    orch = Orchestrator(rc, tc, db_path=tmp_db)
    return orch


@pytest.fixture
def orchestrator_with_veto(tmp_db):
    """Same as `orchestrator` but user_veto_hook is injectable per-test."""
    from trader.core.config import RiskConfig, TraderConfig
    from trader.core.schemas import VetoResponse
    from trader.engine.orchestrator import Orchestrator
    rc = RiskConfig()
    tc = TraderConfig()
    tc.db_path = tmp_db
    tc.enable_user_veto = True
    tc.enable_email = False
    tc.enable_telegram = False
    # default hook: silence
    hook_holder = {"fn": lambda o: VetoResponse.SILENCE.value}
    def hook(order):
        return hook_holder["fn"](order)
    orch = Orchestrator(rc, tc, db_path=tmp_db, user_veto_hook=hook)
    orch._test_hook_holder = hook_holder  # type: ignore[attr-defined]
    return orch
