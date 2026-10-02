import math

import pytest

from xir_trader.core.config import AppConfig, RiskConfig
from xir_trader.core.schemas import InitialDecision, SchemaError


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, True])
def test_risk_thresholds_reject_nonfinite_or_boolean_values(value):
    with pytest.raises(ValueError):
        RiskConfig(max_position_size=value)


@pytest.mark.parametrize("value", [0, -1, math.nan, math.inf, True])
def test_order_size_configuration_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        AppConfig(default_order_size=value)


def test_invalid_veto_policy_and_live_mode_fail_closed():
    with pytest.raises(ValueError):
        AppConfig(on_silence="unknown")
    config = AppConfig(mode="live", live_confirmed=True)
    with pytest.raises(RuntimeError, match="disabled"):
        config.validate_for_mode()


def test_agent_confidence_rejects_boolean_and_out_of_range_values():
    for value in (True, -0.1, 1.1, math.nan, math.inf):
        decision = InitialDecision("cycle", "WAIT", "EURUSD", "reason", confidence=value)
        with pytest.raises(SchemaError):
            decision.validate()
