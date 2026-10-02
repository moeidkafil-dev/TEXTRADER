from xir_trader.core.memory_types import MemoryType, ORDERED_MEMORY_TYPES
from xir_trader.services.db_manager import DBManager
from xir_trader.services.observability import Observability
from xir_trader.services.memory_manager import MemoryManager


def test_28_memory_types_preserved():
    assert len(ORDERED_MEMORY_TYPES) == 28


def test_memory_manager_cycle_removes_duplicates(tmp_path):
    db = DBManager(str(tmp_path / "m.db"))
    obs = Observability(db, "test")
    mm = MemoryManager(db, obs, sleep_interval_seconds=0)

    mm.remember(MemoryType.EXPERIENCE, {"x": 1}, agent_id="a1")
    mm.remember(MemoryType.EXPERIENCE, {"x": 1}, agent_id="a1")  # exact duplicate
    mm.remember(MemoryType.EXPERIENCE, {"x": 2}, agent_id="a1")

    report = mm.run_cycle(trace_id="t1")
    assert report.junks_found >= 1
    remaining = mm.recall(MemoryType.EXPERIENCE, limit=100)
    assert len(remaining) == 2  # one duplicate removed
    db.close()


def test_memory_manager_due_respects_interval(tmp_path):
    db = DBManager(str(tmp_path / "m2.db"))
    obs = Observability(db, "test")
    mm = MemoryManager(db, obs, sleep_interval_seconds=7200)
    assert mm.due() is True  # never run yet
    mm.run_cycle(trace_id="t1")
    assert mm.due() is False  # just ran
    db.close()
