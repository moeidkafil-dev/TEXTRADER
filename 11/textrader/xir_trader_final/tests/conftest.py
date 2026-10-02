import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xir_trader.core.config import AppConfig, RiskConfig
from xir_trader.runtime import Runtime


@pytest.fixture
def tmp_db_path(tmp_path):
    return str(tmp_path / f"test_{uuid.uuid4().hex}.db")


@pytest.fixture
def runtime(tmp_db_path):
    app_config = AppConfig(mode="paper", db_path=tmp_db_path, veto_window_seconds=1)
    risk_config = RiskConfig()
    rt = Runtime(app_config=app_config, risk_config=risk_config)
    yield rt
    rt.db.close()
