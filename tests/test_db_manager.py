"""DB Manager tests — REQ-DB-01 (12-step pipeline)."""
import pytest

from trader.memory.db_manager import DBManager


def test_db_manager_12_steps(orchestrator):
    """REQ-DB-01 — every DB op must run all 12 steps and log them."""
    from trader.core.util import now_ts
    dbm = orchestrator.db_manager
    result = dbm.execute("insert_cycle", cycle_id="dbtest1", started_at=now_ts(),
                         status="test")
    expected = [
        "receiver", "compile", "reader", "analyser", "executer",
        "db_analyser", "db_situation_analyser", "db_log_maker", "result_maker",
        "log_maker", "result_sender", "log_sender",
    ]
    assert result["steps"] == expected


def test_db_manager_unknown_op(orchestrator):
    dbm = orchestrator.db_manager
    with pytest.raises(KeyError):
        dbm.execute("nonexistent_op")
