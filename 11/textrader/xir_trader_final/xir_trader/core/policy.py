"""Deterministic safety policy shared by agents and the runtime.

Model recommendations are untrusted. The policy only consumes parsed data and
validated report structures, and its result always takes precedence.
"""
from __future__ import annotations

import math
import re


def critical_data_failures(context_sections: dict, expected_instrument: str | None = None) -> list[str]:
    section = context_sections.get("data", {})
    rows = section.get("value", []) if isinstance(section, dict) else []
    if not isinstance(rows, list):
        return ["data section is not a list"]
    critical = [row for row in rows if isinstance(row, dict) and row.get("critical") is True]
    if not critical:
        return ["no data adapter declared critical market facts"]
    failures = []
    valid = False
    for row in critical:
        if row.get("quality") != "VALID":
            failures.append(f"critical source {row.get('source', '<unknown>')} quality={row.get('quality', 'UNKNOWN')}")
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            failures.append(f"critical source {row.get('source', '<unknown>')} payload is malformed")
            continue
        if expected_instrument and payload.get("instrument", expected_instrument) != expected_instrument:
            failures.append(f"critical source {row.get('source', '<unknown>')} instrument does not match request")
            continue
        numbers = [payload.get(k) for k in ("open", "high", "low", "close", "volume")]
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in numbers):
            failures.append(f"critical source {row.get('source', '<unknown>')} has missing/non-finite OHLCV")
            continue
        open_, high, low, close, volume = (float(payload[key]) for key in
                                           ("open", "high", "low", "close", "volume"))
        if min(open_, high, low, close) <= 0 or volume < 0 or high < max(open_, close) or low > min(open_, close) or low > high:
            failures.append(f"critical source {row.get('source', '<unknown>')} has contradictory OHLCV")
            continue
        valid = True
    if not valid and not failures:
        failures.append("no valid critical market facts")
    return failures


def agent1_evidence_failures(decision, context_sections: dict) -> list[str]:
    if decision.action not in ("BUY", "SELL"):
        return []
    section = context_sections.get("data", {})
    rows = section.get("value", []) if isinstance(section, dict) else []
    market = next((row.get("payload") for row in rows if isinstance(row, dict)
                   and row.get("critical") and row.get("quality") == "VALID"), None)
    if not isinstance(market, dict):
        return ["trade proposal has no valid critical evidence source"]
    cited = {}
    for item in decision.evidence:
        for key, value in re.findall(r"\b(open|high|low|close|volume)\s*[=:]\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", item, re.IGNORECASE):
            try:
                cited[key.lower()] = float(value)
            except ValueError:
                pass
    missing = [key for key in ("open", "close") if key not in cited]
    mismatched = [key for key, value in cited.items()
                  if not isinstance(market.get(key), (int, float)) or isinstance(market.get(key), bool) or not math.isclose(value, float(market[key]), rel_tol=1e-9, abs_tol=1e-9)]
    failures = []
    if missing:
        failures.append(f"trade evidence omits observed fields: {','.join(missing)}")
    if mismatched:
        failures.append(f"trade evidence contradicts market fields: {','.join(sorted(mismatched))}")
    return failures


def final_decision_evidence_failures(decision, context_sections: dict) -> list[str]:
    """A final BUY/SELL must cite current, observed critical market facts."""
    if decision.decision not in ("BUY", "SELL"):
        return []
    section = context_sections.get("data", {})
    rows = section.get("value", []) if isinstance(section, dict) else []
    market = next((row.get("payload") for row in rows if isinstance(row, dict)
                   and row.get("critical") and row.get("quality") == "VALID"), None)
    if not isinstance(market, dict):
        return ["final trade has no valid critical evidence source"]
    requested = context_sections.get("user_config", {}).get("value", {}).get("instrument")
    if requested and market.get("instrument", requested) != requested:
        return ["final trade critical evidence is for a different instrument"]
    cited = {}
    for item in decision.supporting_evidence:
        for key, value in re.findall(r"\b(open|high|low|close|volume)\s*[=:]\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", item, re.IGNORECASE):
            cited[key.lower()] = float(value)
    missing = [key for key in ("open", "close") if key not in cited]
    mismatched = [key for key, value in cited.items()
                  if not isinstance(market.get(key), (int, float)) or isinstance(market.get(key), bool) or not math.isclose(value, float(market[key]), rel_tol=1e-9, abs_tol=1e-9)]
    failures = []
    if missing:
        failures.append(f"final trade evidence omits observed fields: {','.join(missing)}")
    if mismatched:
        failures.append(f"final trade evidence contradicts market fields: {','.join(sorted(mismatched))}")
    return failures


def blocking_failure_reasons(failure_report, context_sections: dict) -> list[str]:
    user_config = context_sections.get("user_config", {})
    configured = user_config.get("value", {}) if isinstance(user_config, dict) else {}
    expected_instrument = configured.get("instrument") if isinstance(configured, dict) else None
    reasons = critical_data_failures(context_sections, expected_instrument)
    try:
        for path in failure_report.paths:
            value = path.get("blocking", False) if isinstance(path, dict) else path.blocking
            severity = path.get("severity") if isinstance(path, dict) else path.severity
            category = path.get("category", "unknown") if isinstance(path, dict) else path.category
            if value or severity == "blocking":
                reasons.append(f"Agent 2 blocking finding: {category}")
    except Exception:
        reasons.append("Agent 2 report cannot be deterministically inspected")
    return list(dict.fromkeys(reasons))
