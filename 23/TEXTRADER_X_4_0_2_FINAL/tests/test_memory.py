"""Memory subsystem tests — REQ-MEM-01..06."""
import json

import pytest

from trader.memory.stores import MemoryType, MEMORY_TYPE_NAMES, ALL_MEMORY_TYPES


def test_28_memory_types_preserved():
    """REQ-MEM-01 — All 28 types must exist (owner's signature)."""
    assert len(ALL_MEMORY_TYPES) == 28
    expected_names = {
        "Sensory Memory", "Working Memory", "Short-Term Memory (STM)",
        "Long-Term Memory (LTM)", "Episodic Memory", "Semantic (Knowledge) Memory",
        "Procedural Memory", "Goal Memory", "Task Memory", "Context Memory",
        "Conversation Memory", "Tool Memory", "Environment / World State",
        "User Profile Memory", "Learning Memory", "Experience Memory",
        "Failure Memory", "Success Memory", "Reflection Memory",
        "Planning Memory", "RAG Memory", "Cache Memory", "Shared Memory",
        "Agent Local Memory", "Audit / History Memory", "Temporal Memory",
        "Meta Memory", "memory manager agent",
    }
    assert set(MEMORY_TYPE_NAMES.values()) == expected_names


def test_memory_type_resolution_by_ordinal_and_name():
    assert MemoryType.from_name("4") == MemoryType.LTM
    assert MemoryType.from_name("Long-Term Memory (LTM)") == MemoryType.LTM
    assert MemoryType.from_name("Agent Local Memory") == MemoryType.AGENT_LOCAL
    with pytest.raises(KeyError):
        MemoryType.from_name("nonexistent")


def test_agent_local_memory_isolation(orchestrator):
    """REQ-MEM-02 — per-agent stores must be isolated."""
    mm = orchestrator.memory
    mm.write("24", {"x": 1}, agent_id="agent1")
    mm.write("24", {"y": 2}, agent_id="agent2")
    a1 = mm.read("24", agent_id="agent1")
    a2 = mm.read("24", agent_id="agent2")
    a1_contents = [json.loads(it["content"]) for it in a1]
    a2_contents = [json.loads(it["content"]) for it in a2]
    assert {"x": 1} in a1_contents
    assert {"y": 2} in a2_contents
    assert {"y": 2} not in a1_contents
    assert {"x": 1} not in a2_contents


def test_memory_manager_12_step_pipeline(orchestrator):
    """REQ-MEM-03 — every step should be logged in the result."""
    mm = orchestrator.memory
    result = mm.write("4", {"test": "value"})
    expected_steps = [
        "input_reader", "input_analyser", "input_setter", "memory_analyser",
        "memory_complete_analyser", "find_junks", "tables_cleaner",
        "memory_analyser_2", "sleep_mode(active)", "output_request_analyser",
        "result_maker", "result_log",
    ]
    assert result["steps"] == expected_steps


def test_memory_manager_junk_detection(orchestrator):
    """REQ-MEM-05 — find_junks identifies duplicates; audit exempt."""
    mm = orchestrator.memory
    # write the same content twice
    mm.write("4", {"dup": True})
    mm.write("4", {"dup": True})
    # trigger cleanup
    cleaned = mm.trigger_sleep_cleanup()
    assert cleaned >= 1, f"expected at least 1 junk item, got {cleaned}"


def test_audit_memory_append_only(orchestrator):
    """REQ-MEM-05 / I4 — audit memory cannot be deleted."""
    from trader.memory.stores import MemoryStore
    store = MemoryStore(__import__("trader.storage.repo", fromlist=["repo"]))
    # write an audit memory item directly
    rowid = store.write("25", {"audit": "event"})
    # attempt to delete should raise
    with pytest.raises(ValueError):
        store.remove_junk(rowid)


def test_memory_manager_sleep_mode_2h(orchestrator):
    """REQ-MEM-04 — 2-hour interval default."""
    assert orchestrator.memory.sleep_interval == 7200
