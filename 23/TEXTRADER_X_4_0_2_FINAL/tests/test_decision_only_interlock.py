from pathlib import Path


def test_decision_only_interlock_is_at_final_execution_boundary():
    source = Path("trader/engine/orchestrator.py").read_text()
    marker = 'if os.getenv("TEXTRADER_DECISION_ONLY", "0").lower() in {"1", "true", "yes", "on"}:'
    assert marker in source
    block = source[source.index(marker):source.index("# Update portfolio state for a fill")]
    assert '"blocked_decision_only"' in block
    assert "self.final_tools.buy_system(order)" in block
    assert "self.final_tools.sell_system(order)" in block
    assert block.index(marker) < block.index("self.final_tools.buy_system(order)")
    assert block.index(marker) < block.index("self.final_tools.sell_system(order)")
