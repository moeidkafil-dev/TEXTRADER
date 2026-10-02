from trader.core.config import RiskConfig, TraderConfig
from trader.core.schemas import Action, FinalDecision
from trader.engine.orchestrator import Orchestrator


def test_reevaluate_branch_completes_without_state_corruption(tmp_path):
    tc = TraderConfig(db_path=str(tmp_path / "reeval.db"), enable_user_veto=False,
                      max_reevaluate_cycles=3)
    orch = Orchestrator(RiskConfig(), tc, db_path=tc.db_path)

    calls = {"n": 0}
    def always_reevaluate(ctx, initial, failure):
        calls["n"] += 1
        return FinalDecision(cycle_id=ctx.cycle_id, decision=Action.RE_EVALUATE.value,
                             overrode_initial=False, reason="regression")
    orch.agent3.run = always_reevaluate

    result = orch.run_cycle(cycle_id="reeval-regression")
    assert result.errors == []
    assert result.final_state == "IDLE"
    assert orch.state == "IDLE"
    assert result.reeval_count <= tc.max_reevaluate_cycles
    assert calls["n"] == tc.max_reevaluate_cycles
