#!/usr/bin/env python3
"""Build and supervise actuator-neutral battery/EV intents in dry-run only.

This module deliberately has no network, Home Assistant, MQTT, SMA, or Smappee
client. It can only validate data and serialize non-dispatchable proposals.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import secrets
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
CLASSIFICATION = "DRY_RUN_CONTROL_INTENTS_NO_EXECUTION"
DEFAULT_FRESHNESS_LIMIT_SECONDS = 300
DEFAULT_PLAN_FRESHNESS_LIMIT_SECONDS = 18 * 60 * 60
EXPECTED_CONTROLLERS = {"BATTERY": "SMA", "EV_CHARGER": "SMAPPEE"}
_INTEGRITY_KEY = secrets.token_bytes(32)


def _integrity_digest(payload: dict[str, Any], field: str) -> str:
    canonical = {key: value for key, value in payload.items() if key != field}
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hmac.new(_INTEGRITY_KEY, encoded, hashlib.sha256).hexdigest()


def _with_integrity(payload: dict[str, Any], field: str) -> dict[str, Any]:
    payload[field] = _integrity_digest(payload, field)
    return payload


def _parse_instant(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp is required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp requires an offset")
    return parsed.astimezone(timezone.utc)


def _normalise_now(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("now requires a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _finite_number(value: Any, *, minimum: float | None = None) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("number must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"number must be at least {minimum}")
    return number


def _no_action_bundle(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "classification": CLASSIFICATION,
        "mode": "DRY_RUN",
        "status": "NO_ACTION",
        "reason": reason,
        "execution_allowed": False,
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "intents": [],
    }


def _validate_plan_intervals(plan: dict[str, Any]) -> list[dict[str, Any]]:
    raw = plan.get("intervals")
    if not isinstance(raw, list) or not raw:
        raise ValueError("plan intervals are required")
    intervals = []
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("plan interval must be an object")
        start = _parse_instant(row.get("start_utc"))
        end = _parse_instant(row.get("end_utc"))
        if end <= start:
            raise ValueError("plan interval end must be after start")
        base = _finite_number(row.get("forecast_base_load_kw"))
        battery = _finite_number(row.get("battery_power_kw"))
        ev = _finite_number(row.get("ev_power_kw"), minimum=0.0)
        reason = row.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("plan interval reason is required")
        intervals.append(
            {
                **row,
                "_start": start,
                "_end": end,
                "_base": base,
                "_battery": battery,
                "_ev": ev,
            }
        )
    intervals.sort(key=lambda row: row["_start"])
    for left, right in zip(intervals, intervals[1:]):
        if right["_start"] != left["_end"]:
            raise ValueError("plan intervals must be contiguous and unique")
    return intervals


def _action_for_battery(power_kw: float) -> str:
    if power_kw > 0:
        return "CHARGE"
    if power_kw < 0:
        return "DISCHARGE"
    return "HOLD"


def _battery_limits(inputs: dict[str, Any]) -> dict[str, float]:
    limits = {
        "minimum_soc_percent": _finite_number(inputs.get("minimum_soc_percent"), minimum=0.0),
        "maximum_soc_percent": _finite_number(inputs.get("maximum_soc_percent"), minimum=0.0),
        "usable_capacity_kwh": _finite_number(inputs.get("usable_capacity_kwh"), minimum=0.001),
        "max_charge_power_kw": _finite_number(inputs.get("max_charge_power_kw"), minimum=0.0),
        "max_discharge_power_kw": _finite_number(inputs.get("max_discharge_power_kw"), minimum=0.0),
    }
    if limits["maximum_soc_percent"] > 100:
        raise ValueError("battery SOC limit exceeds 100 percent")
    return limits


def _ev_limits(inputs: dict[str, Any]) -> dict[str, Any]:
    limits = {
        "target_soc_percent": _finite_number(inputs.get("target_soc_percent"), minimum=0.0),
        "usable_capacity_kwh": _finite_number(inputs.get("usable_capacity_kwh"), minimum=0.001),
        "max_charge_power_kw": _finite_number(inputs.get("max_charge_power_kw"), minimum=0.0),
        "departure_utc": _parse_instant(inputs.get("departure_utc")).isoformat(),
    }
    if limits["target_soc_percent"] > 100:
        raise ValueError("EV SOC target exceeds 100 percent")
    return limits


def _intent(
    *,
    source_plan_id: str,
    generated_at: str,
    valid_until: datetime,
    interval: dict[str, Any],
    target: str,
    requested_action: str,
    requested_power_kw: float,
    requested_grid_effect_kw: float,
    reason: str,
    observed_controller: str | None,
    input_observed_at: str | None,
    limits: dict[str, Any],
    shared_limit_kw: float,
) -> dict[str, Any]:
    start = interval["_start"]
    end = interval["_end"]
    return {
        "intent_id": f"{source_plan_id}:{target}:{start.isoformat()}",
        "schema_version": SCHEMA_VERSION,
        "target": target,
        "target_interval": {
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
        },
        "source_plan_id": source_plan_id,
        "source_plan_generated_at": generated_at,
        "valid_from_utc": start.isoformat(),
        "valid_until_utc": min(end, valid_until).isoformat(),
        "requested_action": requested_action,
        "requested_power_kw": round(requested_power_kw, 9),
        "requested_grid_effect_kw": round(requested_grid_effect_kw, 9),
        "reason": reason,
        "ownership": {
            "expected_controller": EXPECTED_CONTROLLERS[target],
            "observed_controller": observed_controller,
        },
        "limits": {
            **limits,
            "shared_grid_import_limit_kw": shared_limit_kw,
        },
        "interval_context": {
            "forecast_base_load_kw": round(interval["_base"], 9),
        },
        "input_observed_at": input_observed_at,
        "execution_allowed": False,
        "physical_writes": False,
    }


def build_intent_bundle(
    planner_output: dict[str, Any],
    control_inputs: dict[str, Any],
    *,
    now: datetime,
    freshness_limit_seconds: int = DEFAULT_FRESHNESS_LIMIT_SECONDS,
    plan_freshness_limit_seconds: int = DEFAULT_PLAN_FRESHNESS_LIMIT_SECONDS,
) -> dict[str, Any]:
    """Translate a joint quarter plan into actuator-neutral dry-run intents."""
    try:
        now_utc = _normalise_now(now)
    except ValueError:
        return _no_action_bundle("INVALID_NOW")
    if not isinstance(planner_output, dict) or not isinstance(control_inputs, dict):
        return _no_action_bundle("INVALID_INPUT_CONTRACT")
    try:
        intervals = _validate_plan_intervals(planner_output)
    except (KeyError, TypeError, ValueError, OverflowError):
        return _no_action_bundle("INVALID_PLAN_INTERVALS")
    try:
        if planner_output.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported planner schema")
        source_plan_id = str(planner_output["plan_id"]).strip()
        if not source_plan_id:
            raise ValueError("plan id is required")
        selected_policy_id = str(planner_output["selected_policy_id"]).strip()
        if not selected_policy_id:
            raise ValueError("selected policy id is required")
        generated_at = _parse_instant(planner_output["generated_at"])
        valid_from = _parse_instant(planner_output["valid_from_utc"])
        valid_until = _parse_instant(planner_output["valid_until_utc"])
        if valid_until <= valid_from or generated_at > now_utc:
            raise ValueError("invalid plan validity")
        shared_limit = _finite_number(
            planner_output["shared_grid_import_limit_kw"], minimum=0.0
        )
        if (
            intervals[0]["_start"] != valid_from
            or intervals[-1]["_end"] != valid_until
        ):
            raise ValueError("intervals must cover complete plan validity")
        freshness_limit = int(freshness_limit_seconds)
        plan_freshness_limit = int(plan_freshness_limit_seconds)
        if freshness_limit <= 0 or plan_freshness_limit <= 0:
            raise ValueError("freshness limits must be positive")
        common_observed_at = _parse_instant(control_inputs["observed_at"]).isoformat()
        battery_inputs = control_inputs["battery"]
        if not isinstance(battery_inputs, dict):
            raise ValueError("battery input is required")
        battery_limits = _battery_limits(battery_inputs)
        if battery_limits["minimum_soc_percent"] >= battery_limits["maximum_soc_percent"]:
            raise ValueError("invalid battery SOC range")
        battery_observed_at = _parse_instant(battery_inputs["observed_at"]).isoformat()
        battery_owner = battery_inputs.get("controller_owner")
        ev_inputs = control_inputs.get("ev")
        if ev_inputs is not None and not isinstance(ev_inputs, dict):
            raise ValueError("EV input must be an object")
        if ev_inputs is not None:
            ev_limits = _ev_limits(ev_inputs)
            ev_observed_at = _parse_instant(ev_inputs["observed_at"]).isoformat()
            ev_owner = ev_inputs.get("controller_owner")
        else:
            ev_limits = {
                "target_soc_percent": None,
                "usable_capacity_kwh": None,
                "max_charge_power_kw": 0.0,
                "departure_utc": None,
            }
            ev_observed_at = None
            ev_owner = None
    except (KeyError, TypeError, ValueError, OverflowError):
        return _no_action_bundle("INVALID_PLAN_OR_INPUT_CONTRACT")

    intents = []
    for interval in intervals:
        battery_power = interval["_battery"]
        battery_action = _action_for_battery(battery_power)
        intents.append(
            _intent(
                source_plan_id=source_plan_id,
                generated_at=generated_at.isoformat(),
                valid_until=valid_until,
                interval=interval,
                target="BATTERY",
                requested_action=battery_action,
                requested_power_kw=abs(battery_power),
                requested_grid_effect_kw=battery_power,
                reason=str(interval["reason"]),
                observed_controller=str(battery_owner) if battery_owner is not None else None,
                input_observed_at=battery_observed_at,
                limits=battery_limits,
                shared_limit_kw=shared_limit,
            )
        )
        missing_ev = ev_inputs is None
        ev_power = 0.0 if missing_ev else interval["_ev"]
        ev_reason = "MISSING_EV_REQUIREMENT" if missing_ev else str(interval["reason"])
        intents.append(
            _intent(
                source_plan_id=source_plan_id,
                generated_at=generated_at.isoformat(),
                valid_until=valid_until,
                interval=interval,
                target="EV_CHARGER",
                requested_action="NO_ACTION" if missing_ev else ("CHARGE" if ev_power > 0 else "HOLD"),
                requested_power_kw=ev_power,
                requested_grid_effect_kw=ev_power,
                reason=ev_reason,
                observed_controller=str(ev_owner) if ev_owner is not None else None,
                input_observed_at=ev_observed_at,
                limits=ev_limits,
                shared_limit_kw=shared_limit,
            )
        )

    bundle = {
        "schema_version": SCHEMA_VERSION,
        "classification": CLASSIFICATION,
        "mode": "DRY_RUN",
        "status": "READY_FOR_SAFETY_REVIEW",
        "reason": "ACTUATOR_NEUTRAL_INTENTS_BUILT",
        "created_at": now_utc.isoformat(),
        "observed_at": common_observed_at,
        "valid_from_utc": valid_from.isoformat(),
        "valid_until_utc": valid_until.isoformat(),
        "source_plan_id": source_plan_id,
        "selected_policy_id": selected_policy_id,
        "shared_grid_import_limit_kw": shared_limit,
        "freshness_limit_seconds": freshness_limit,
        "plan_freshness_limit_seconds": plan_freshness_limit,
        "expected_intervals": [
            {
                "start_utc": interval["_start"].isoformat(),
                "end_utc": interval["_end"].isoformat(),
            }
            for interval in intervals
        ],
        "execution_allowed": False,
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "intents": intents,
    }
    return _with_integrity(bundle, "bundle_integrity_hmac_sha256")


def _freshness_reasons(value: Any, now: datetime, limit_seconds: int) -> list[str]:
    try:
        observed = _parse_instant(value)
    except (TypeError, ValueError):
        return ["MISSING_OR_INVALID_OBSERVATION_TIMESTAMP"]
    age = (now - observed).total_seconds()
    if age < 0:
        return ["FUTURE_DATED_INPUT"]
    if age > limit_seconds:
        return ["STALE_INPUT"]
    return []


def _common_bundle_reasons(bundle: dict[str, Any], state: dict[str, Any], now: datetime) -> list[str]:
    reasons = []
    try:
        supplied_integrity = bundle.get("bundle_integrity_hmac_sha256")
        expected_integrity = _integrity_digest(bundle, "bundle_integrity_hmac_sha256")
        if not isinstance(supplied_integrity, str) or not hmac.compare_digest(
            supplied_integrity, expected_integrity
        ):
            reasons.append("INTENT_BUNDLE_INTEGRITY_INVALID")
    except (TypeError, ValueError):
        reasons.append("INTENT_BUNDLE_INTEGRITY_INVALID")
    if bundle.get("schema_version") != SCHEMA_VERSION:
        reasons.append("SCHEMA_VERSION_INVALID")
    if (
        bundle.get("classification") != CLASSIFICATION
        or bundle.get("mode") != "DRY_RUN"
        or bundle.get("execution_allowed") is not False
        or bundle.get("physical_writes") is not False
        or bundle.get("home_assistant_writes") is not False
        or bundle.get("sma_writes") is not False
        or bundle.get("smappee_writes") is not False
    ):
        reasons.append("WRITE_BOUNDARY_INVALID")
    if bundle.get("status") != "READY_FOR_SAFETY_REVIEW":
        reasons.append("INTENT_BUNDLE_NOT_READY")
    try:
        valid_until = _parse_instant(bundle.get("valid_until_utc"))
        if now >= valid_until:
            reasons.append("PLAN_EXPIRED")
    except (TypeError, ValueError):
        reasons.append("PLAN_VALIDITY_INVALID")
    try:
        raw_limit = bundle.get("freshness_limit_seconds")
        if raw_limit is None:
            raise ValueError
        limit_seconds = int(raw_limit)
        if limit_seconds <= 0:
            raise ValueError
    except (TypeError, ValueError):
        limit_seconds = DEFAULT_FRESHNESS_LIMIT_SECONDS
        reasons.append("FRESHNESS_LIMIT_INVALID")
    reasons.extend(_freshness_reasons(bundle.get("observed_at"), now, limit_seconds))
    reasons.extend(_freshness_reasons(state.get("observed_at"), now, limit_seconds))
    try:
        raw_plan_limit = bundle.get("plan_freshness_limit_seconds")
        if raw_plan_limit is None:
            raise ValueError
        plan_limit_seconds = int(raw_plan_limit)
        if plan_limit_seconds <= 0:
            raise ValueError
    except (TypeError, ValueError):
        plan_limit_seconds = DEFAULT_PLAN_FRESHNESS_LIMIT_SECONDS
        reasons.append("PLAN_FRESHNESS_LIMIT_INVALID")
    raw_intents = bundle.get("intents")
    if not isinstance(raw_intents, list):
        raw_intents = []
        reasons.append("INTENTS_INVALID")
    source_timestamps = {
        intent.get("source_plan_generated_at")
        for intent in raw_intents
        if isinstance(intent, dict)
    }
    if len(source_timestamps) != 1:
        reasons.append("SOURCE_PLAN_TIMESTAMP_CONFLICT")
    else:
        reasons.extend(
            _freshness_reasons(next(iter(source_timestamps)), now, plan_limit_seconds)
        )
    interval_targets: dict[tuple[Any, Any], list[Any]] = defaultdict(list)
    for intent in raw_intents:
        if not isinstance(intent, dict):
            continue
        interval = intent.get("target_interval")
        if not isinstance(interval, dict):
            continue
        interval_targets[(interval.get("start_utc"), interval.get("end_utc"))].append(
            intent.get("target")
        )
    expected_targets = set(EXPECTED_CONTROLLERS)
    raw_expected_intervals = bundle.get("expected_intervals")
    expected_intervals = set()
    if isinstance(raw_expected_intervals, list):
        for interval in raw_expected_intervals:
            if isinstance(interval, dict):
                expected_intervals.add((interval.get("start_utc"), interval.get("end_utc")))
    if (
        not expected_intervals
        or set(interval_targets) != expected_intervals
        or any(
        len(targets) != len(expected_targets) or set(targets) != expected_targets
        for targets in interval_targets.values()
        )
    ):
        reasons.append("TARGET_INTERVAL_COVERAGE_INVALID")
    return sorted(set(reasons))


def _finalize_review(payload: dict[str, Any]) -> dict[str, Any]:
    return _with_integrity(payload, "review_integrity_hmac_sha256")


def _action_contract_reasons(intent: dict[str, Any]) -> list[str]:
    try:
        target = str(intent["target"])
        action = str(intent["requested_action"])
        power = _finite_number(intent["requested_power_kw"], minimum=0.0)
        effect = _finite_number(intent["requested_grid_effect_kw"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return ["ACTION_CONTRACT_INVALID"]
    allowed = {
        "BATTERY": {"CHARGE", "DISCHARGE", "HOLD", "NO_ACTION"},
        "EV_CHARGER": {"CHARGE", "HOLD", "NO_ACTION"},
    }
    if action not in allowed.get(target, set()):
        return ["ACTION_CONTRACT_INVALID"]
    valid = False
    if action in {"HOLD", "NO_ACTION"}:
        valid = abs(power) <= 1e-9 and abs(effect) <= 1e-9
    elif action == "CHARGE":
        valid = power > 0 and abs(effect - power) <= 1e-9
    elif action == "DISCHARGE":
        valid = target == "BATTERY" and power > 0 and abs(effect + power) <= 1e-9
    return [] if valid else ["ACTION_CONTRACT_INVALID"]


def _device_reasons(intent: dict[str, Any], state: dict[str, Any], now: datetime, limit: int) -> list[str]:
    reasons = []
    target = intent.get("target")
    state_key = "battery" if target == "BATTERY" else "ev"
    device = state.get(state_key)
    if not isinstance(device, dict):
        return ["DEVICE_STATE_MISSING"]
    reasons.extend(_freshness_reasons(intent.get("input_observed_at"), now, limit))
    ownership = intent.get("ownership") if isinstance(intent.get("ownership"), dict) else {}
    expected = EXPECTED_CONTROLLERS.get(str(target))
    missing_ev_requirement = (
        target == "EV_CHARGER"
        and intent.get("requested_action") == "NO_ACTION"
        and intent.get("reason") == "MISSING_EV_REQUIREMENT"
    )
    if (
        expected is None
        or ownership.get("expected_controller") != expected
        or (
            ownership.get("observed_controller") != expected
            and not missing_ev_requirement
        )
        or device.get("controller_owner") != expected
    ):
        reasons.append("CONTROLLER_OWNERSHIP_CONFLICT")
    if device.get("device_available") is not True:
        reasons.append("DEVICE_UNAVAILABLE")
    safety_fields = (
        "manual_override_active",
        "local_fallback_active",
        "acknowledgement_timed_out",
    )
    if any(field not in device or not isinstance(device.get(field), bool) for field in safety_fields):
        reasons.append("SAFETY_STATE_INCOMPLETE")
    if device.get("manual_override_active") is True:
        reasons.append("MANUAL_OVERRIDE_ACTIVE")
    if device.get("local_fallback_active") is True:
        reasons.append("LOCAL_FALLBACK_ACTIVE")
    if device.get("acknowledgement_timed_out") is True:
        reasons.append("ACKNOWLEDGEMENT_TIMEOUT")

    try:
        action = str(intent["requested_action"])
        power = _finite_number(intent["requested_power_kw"], minimum=0.0)
        limits = intent["limits"]
        if not isinstance(limits, dict):
            raise ValueError
        if target == "BATTERY":
            if action == "CHARGE" and power > _finite_number(limits["max_charge_power_kw"], minimum=0.0):
                reasons.append("POWER_LIMIT_EXCEEDED")
            if action == "DISCHARGE" and power > _finite_number(limits["max_discharge_power_kw"], minimum=0.0):
                reasons.append("POWER_LIMIT_EXCEEDED")
            soc = _finite_number(device.get("soc_percent"), minimum=0.0)
            capacity = _finite_number(limits["usable_capacity_kwh"], minimum=0.001)
            interval = intent["target_interval"]
            duration_hours = (
                _parse_instant(interval["end_utc"])
                - _parse_instant(interval["start_utc"])
            ).total_seconds() / 3600
            if soc > 100:
                raise ValueError("battery SOC exceeds 100 percent")
            maximum_soc = _finite_number(limits["maximum_soc_percent"], minimum=0.0)
            minimum_soc = _finite_number(limits["minimum_soc_percent"], minimum=0.0)
            projected_soc = soc
            if action == "CHARGE":
                projected_soc += power * duration_hours / capacity * 100
            elif action == "DISCHARGE":
                projected_soc -= power * duration_hours / capacity * 100
            if action == "CHARGE" and soc >= maximum_soc:
                reasons.append("BATTERY_SOC_LIMIT")
            if action == "DISCHARGE" and soc <= minimum_soc:
                reasons.append("BATTERY_SOC_LIMIT")
            if projected_soc > maximum_soc + 1e-9 or projected_soc < minimum_soc - 1e-9:
                reasons.append("BATTERY_PROJECTED_SOC_LIMIT")
        elif target == "EV_CHARGER":
            if action == "CHARGE" and power > _finite_number(limits["max_charge_power_kw"], minimum=0.0):
                reasons.append("POWER_LIMIT_EXCEEDED")
            if device.get("connected") is not True:
                reasons.append("EV_NOT_CONNECTED")
            ev_soc = _finite_number(device.get("soc_percent"), minimum=0.0)
            target_soc = limits.get("target_soc_percent")
            capacity = _finite_number(limits["usable_capacity_kwh"], minimum=0.001)
            interval = intent["target_interval"]
            interval_start = _parse_instant(interval["start_utc"])
            interval_end = _parse_instant(interval["end_utc"])
            duration_hours = (interval_end - interval_start).total_seconds() / 3600
            if ev_soc > 100:
                raise ValueError("EV SOC exceeds 100 percent")
            if (
                action == "CHARGE"
                and target_soc is not None
                and ev_soc >= _finite_number(target_soc, minimum=0.0)
            ):
                reasons.append("EV_SOC_TARGET_REACHED")
            if (
                action == "CHARGE"
                and target_soc is not None
                and ev_soc + power * duration_hours / capacity * 100
                > _finite_number(target_soc, minimum=0.0) + 1e-9
            ):
                reasons.append("EV_PROJECTED_SOC_TARGET_EXCEEDED")
            departure = limits.get("departure_utc")
            if (
                action == "CHARGE"
                and departure is not None
                and _parse_instant(departure) < interval_end
            ):
                reasons.append("EV_DEPARTURE_BEFORE_INTERVAL_END")
        else:
            reasons.append("TARGET_INVALID")
    except (KeyError, TypeError, ValueError, OverflowError):
        reasons.append("INTENT_LIMITS_INVALID")
    return sorted(set(reasons))


def supervise_intents(
    bundle: dict[str, Any] | None,
    safety_state: dict[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Apply fail-closed safety checks to each dry-run intent."""
    try:
        now_utc = _normalise_now(now)
    except ValueError:
        now_utc = datetime.now(timezone.utc)
        return _finalize_review({
            "schema_version": SCHEMA_VERSION,
            "classification": "SAFETY_REVIEW_DRY_RUN_NO_EXECUTION",
            "source_plan_id": None,
            "reviewed_at": now_utc.isoformat(),
            "status": "REJECTED",
            "reasons": ["INVALID_NOW"],
            "execution_allowed": False,
            "physical_writes": False,
            "home_assistant_writes": False,
            "sma_writes": False,
            "smappee_writes": False,
            "decisions": [],
        })
    if not isinstance(bundle, dict):
        return _finalize_review({
            "schema_version": SCHEMA_VERSION,
            "classification": "SAFETY_REVIEW_DRY_RUN_NO_EXECUTION",
            "source_plan_id": None,
            "reviewed_at": now_utc.isoformat(),
            "status": "REJECTED",
            "reasons": ["INTENT_BUNDLE_INVALID"],
            "execution_allowed": False,
            "physical_writes": False,
            "home_assistant_writes": False,
            "sma_writes": False,
            "smappee_writes": False,
            "decisions": [],
        })
    state = safety_state if isinstance(safety_state, dict) else {}
    common_reasons = _common_bundle_reasons(bundle, state, now_utc)
    try:
        freshness_limit = int(bundle.get("freshness_limit_seconds"))
    except (TypeError, ValueError):
        freshness_limit = DEFAULT_FRESHNESS_LIMIT_SECONDS
    intents = bundle.get("intents") if isinstance(bundle.get("intents"), list) else []

    keys = []
    for intent in intents:
        if isinstance(intent, dict):
            interval = intent.get("target_interval")
            start = interval.get("start_utc") if isinstance(interval, dict) else None
            keys.append((intent.get("target"), start))
    duplicate_keys = {key for key, count in Counter(keys).items() if count > 1}

    interval_totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {"base": 0.0, "effect": 0.0, "limit": math.inf}
    )
    malformed_interval_starts: set[str] = set()
    malformed_intent_ids: set[str] = set()
    shared_limit_conflicts: set[str] = set()
    try:
        bundle_shared_limit = _finite_number(
            bundle["shared_grid_import_limit_kw"], minimum=0.0
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        bundle_shared_limit = math.nan
        common_reasons.append("SHARED_GRID_LIMIT_INVALID")
    for intent in intents:
        if not isinstance(intent, dict):
            continue
        intent_id = str(intent.get("intent_id"))
        interval = intent.get("target_interval")
        start = interval.get("start_utc") if isinstance(interval, dict) else None
        try:
            start = str(intent["target_interval"]["start_utc"])
            context = intent["interval_context"]
            limits = intent["limits"]
            base = _finite_number(context["forecast_base_load_kw"])
            effect = _finite_number(intent["requested_grid_effect_kw"])
            shared_limit = _finite_number(limits["shared_grid_import_limit_kw"], minimum=0.0)
            if not math.isfinite(bundle_shared_limit) or abs(shared_limit - bundle_shared_limit) > 1e-9:
                shared_limit_conflicts.add(intent_id)
            entry = interval_totals[start]
            if entry["limit"] == math.inf:
                entry["base"] = base
                entry["limit"] = bundle_shared_limit
            elif abs(entry["base"] - base) > 1e-9 or abs(entry["limit"] - shared_limit) > 1e-9:
                malformed_interval_starts.add(start)
            entry["effect"] += effect
        except (KeyError, TypeError, ValueError, OverflowError):
            malformed_intent_ids.add(intent_id)
            if start is not None:
                malformed_interval_starts.add(str(start))
    cap_violations = {
        start
        for start, values in interval_totals.items()
        if max(0.0, values["base"] + values["effect"]) > values["limit"] + 1e-9
    }

    cumulative_soc_reasons: dict[str, str] = {}
    for target, state_key in (("BATTERY", "battery"), ("EV_CHARGER", "ev")):
        device = state.get(state_key)
        if not isinstance(device, dict):
            continue
        try:
            projected_soc = _finite_number(device.get("soc_percent"), minimum=0.0)
            if projected_soc > 100:
                raise ValueError("SOC exceeds 100 percent")
            target_intents = sorted(
                (
                    intent
                    for intent in (intents if isinstance(intents, list) else [])
                    if isinstance(intent, dict) and intent.get("target") == target
                ),
                key=lambda intent: _parse_instant(intent["target_interval"]["start_utc"]),
            )
            for intent in target_intents:
                interval = intent["target_interval"]
                duration_hours = (
                    _parse_instant(interval["end_utc"])
                    - _parse_instant(interval["start_utc"])
                ).total_seconds() / 3600
                action = intent["requested_action"]
                power = _finite_number(intent["requested_power_kw"], minimum=0.0)
                limits = intent["limits"]
                capacity = _finite_number(
                    limits["usable_capacity_kwh"], minimum=0.001
                )
                if action == "CHARGE":
                    projected_soc += power * duration_hours / capacity * 100
                elif action == "DISCHARGE":
                    projected_soc -= power * duration_hours / capacity * 100
                intent_id = str(intent.get("intent_id"))
                if target == "BATTERY":
                    minimum_soc = _finite_number(
                        limits["minimum_soc_percent"], minimum=0.0
                    )
                    maximum_soc = _finite_number(
                        limits["maximum_soc_percent"], minimum=0.0
                    )
                    if (
                        projected_soc < minimum_soc - 1e-9
                        or projected_soc > maximum_soc + 1e-9
                    ):
                        cumulative_soc_reasons[intent_id] = (
                            "BATTERY_CUMULATIVE_SOC_LIMIT"
                        )
                else:
                    target_soc = _finite_number(
                        limits["target_soc_percent"], minimum=0.0
                    )
                    if projected_soc > target_soc + 1e-9:
                        cumulative_soc_reasons[intent_id] = (
                            "EV_CUMULATIVE_SOC_TARGET_EXCEEDED"
                        )
        except (KeyError, TypeError, ValueError, OverflowError):
            continue

    decisions = []
    for intent in intents:
        if not isinstance(intent, dict):
            decisions.append(
                {
                    "intent_id": None,
                    "target": None,
                    "decision": "REJECTED",
                    "reasons": ["INTENT_INVALID"],
                    "dry_run_action": "NO_ACTION",
                    "execution_action": "NO_ACTION",
                    "execution_allowed": False,
                }
            )
            continue
        reasons = list(common_reasons)
        interval = intent.get("target_interval")
        start = interval.get("start_utc") if isinstance(interval, dict) else None
        if (intent.get("target"), start) in duplicate_keys:
            reasons.append("DUPLICATE_TARGET_INTERVAL")
        if start in cap_violations:
            reasons.append("SHARED_GRID_IMPORT_LIMIT_EXCEEDED")
        if start in malformed_interval_starts:
            reasons.append("INTERVAL_CONTEXT_CONFLICT")
        if str(intent.get("intent_id")) in malformed_intent_ids:
            reasons.append("INTERVAL_CONTEXT_CONFLICT")
        if str(intent.get("intent_id")) in shared_limit_conflicts:
            reasons.append("SHARED_GRID_LIMIT_CONFLICT")
        cumulative_reason = cumulative_soc_reasons.get(str(intent.get("intent_id")))
        if cumulative_reason is not None:
            reasons.append(cumulative_reason)
        if intent.get("execution_allowed") is not False or intent.get("physical_writes") is not False:
            reasons.append("WRITE_BOUNDARY_INVALID")
        if intent.get("schema_version") != SCHEMA_VERSION:
            reasons.append("SCHEMA_VERSION_INVALID")
        if intent.get("source_plan_id") != bundle.get("source_plan_id"):
            reasons.append("SOURCE_PLAN_CONFLICT")
        try:
            interval_start = _parse_instant(intent["target_interval"]["start_utc"])
            interval_end = _parse_instant(intent["target_interval"]["end_utc"])
            intent_valid_from = _parse_instant(intent.get("valid_from_utc"))
            intent_valid_until = _parse_instant(intent.get("valid_until_utc"))
            bundle_valid_until = _parse_instant(bundle.get("valid_until_utc"))
            if (
                interval_end <= interval_start
                or intent_valid_from != interval_start
                or intent_valid_until != min(interval_end, bundle_valid_until)
            ):
                reasons.append("INTENT_VALIDITY_INVALID")
            if now_utc >= intent_valid_until:
                reasons.append("INTENT_EXPIRED")
            expected_id = (
                f"{bundle.get('source_plan_id')}:{intent.get('target')}:{interval_start.isoformat()}"
            )
            if intent.get("intent_id") != expected_id:
                reasons.append("INTENT_ID_INVALID")
        except (TypeError, ValueError):
            reasons.append("INTENT_VALIDITY_INVALID")
        reasons.extend(_action_contract_reasons(intent))
        reasons.extend(_device_reasons(intent, state, now_utc, freshness_limit))
        reasons = sorted(set(reasons))
        accepted = not reasons
        decisions.append(
            {
                "intent_id": intent.get("intent_id"),
                "target": intent.get("target"),
                "target_interval": intent.get("target_interval"),
                "decision": "ACCEPTED_DRY_RUN" if accepted else "REJECTED",
                "reasons": reasons,
                "dry_run_action": intent.get("requested_action") if accepted else "NO_ACTION",
                "requested_power_kw": intent.get("requested_power_kw") if accepted else 0.0,
                "execution_action": "NO_ACTION",
                "execution_allowed": False,
            }
        )

    all_accepted = bool(decisions) and all(
        decision["decision"] == "ACCEPTED_DRY_RUN" for decision in decisions
    )
    return _finalize_review({
        "schema_version": SCHEMA_VERSION,
        "classification": "SAFETY_REVIEW_DRY_RUN_NO_EXECUTION",
        "source_plan_id": bundle.get("source_plan_id"),
        "reviewed_at": now_utc.isoformat(),
        "status": "ACCEPTED_DRY_RUN" if all_accepted else "REJECTED",
        "reasons": sorted(set(common_reasons)),
        "execution_allowed": False,
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "decisions": decisions,
    })


def build_dry_run_proposals(supervised: dict[str, Any]) -> list[dict[str, Any]]:
    """Serialize reviewed intents without any dispatch or transport capability."""
    proposals = []
    decisions = supervised.get("decisions") if isinstance(supervised, dict) else None
    if not isinstance(supervised, dict):
        review_integrity_valid = False
    else:
        try:
            supplied_integrity = supervised.get("review_integrity_hmac_sha256")
            expected_integrity = _integrity_digest(supervised, "review_integrity_hmac_sha256")
            review_integrity_valid = isinstance(supplied_integrity, str) and hmac.compare_digest(
                supplied_integrity, expected_integrity
            )
        except (TypeError, ValueError):
            review_integrity_valid = False
    review_valid = isinstance(supervised, dict) and (
        review_integrity_valid
        and supervised.get("schema_version") == SCHEMA_VERSION
        and supervised.get("classification") == "SAFETY_REVIEW_DRY_RUN_NO_EXECUTION"
        and supervised.get("status") == "ACCEPTED_DRY_RUN"
        and supervised.get("reasons") == []
        and supervised.get("execution_allowed") is False
        and supervised.get("physical_writes") is False
        and supervised.get("home_assistant_writes") is False
        and supervised.get("sma_writes") is False
        and supervised.get("smappee_writes") is False
    )
    for decision in decisions if isinstance(decisions, list) else []:
        if not isinstance(decision, dict):
            continue
        target = decision.get("target")
        if target not in EXPECTED_CONTROLLERS:
            continue
        raw_reasons = decision.get("reasons")
        if isinstance(raw_reasons, list) and all(
            isinstance(reason, str) for reason in raw_reasons
        ):
            reasons_valid = True
            decision_reasons = raw_reasons.copy()
        else:
            reasons_valid = False
            decision_reasons = []
        try:
            proposed_power = _finite_number(decision.get("requested_power_kw"), minimum=0.0)
        except (TypeError, ValueError, OverflowError):
            proposed_power = 0.0
            reasons_valid = False
        action = decision.get("dry_run_action")
        action_valid = (
            action in {"CHARGE", "DISCHARGE", "HOLD", "NO_ACTION"}
            and ((action in {"HOLD", "NO_ACTION"}) == (proposed_power == 0.0))
            and not (target == "EV_CHARGER" and action == "DISCHARGE")
        )
        decision_valid = (
            review_valid
            and decision.get("decision") == "ACCEPTED_DRY_RUN"
            and decision.get("execution_action") == "NO_ACTION"
            and decision.get("execution_allowed") is False
            and reasons_valid
            and action_valid
        )
        accepted = decision_valid
        if not decision_valid:
            decision_reasons.append("SAFETY_REVIEW_INVALID")
        proposals.append(
            {
                "schema_version": SCHEMA_VERSION,
                "classification": "NON_DISPATCHABLE_COMMAND_PROPOSAL",
                "adapter": "SMA_DRY_RUN" if target == "BATTERY" else "SMAPPEE_DRY_RUN",
                "target": target,
                "intent_id": decision.get("intent_id"),
                "target_interval": decision.get("target_interval"),
                "proposed_action": decision.get("dry_run_action") if accepted else "NO_ACTION",
                "proposed_power_kw": proposed_power if accepted else 0.0,
                "safety_decision": decision.get("decision"),
                "safety_reasons": sorted(set(decision_reasons)),
                "transport": "NONE",
                "dispatch_supported": False,
                "execution_action": "NO_ACTION",
                "execution_allowed": False,
                "physical_writes": False,
                "home_assistant_writes": False,
                "sma_writes": False,
                "smappee_writes": False,
            }
        )
    return proposals


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--safety-state", type=Path, required=True)
    parser.add_argument("--now", type=_parse_instant, required=True)
    parser.add_argument("--intent-output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--proposals-output", type=Path, required=True)
    args = parser.parse_args()

    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        inputs = json.loads(args.inputs.read_text(encoding="utf-8"))
        state = json.loads(args.safety_state.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        bundle = _no_action_bundle("INPUT_FILE_INVALID")
        review = _finalize_review(
            {
                "schema_version": SCHEMA_VERSION,
                "classification": "SAFETY_REVIEW_DRY_RUN_NO_EXECUTION",
                "source_plan_id": None,
                "reviewed_at": args.now.isoformat(),
                "status": "REJECTED",
                "reasons": ["INPUT_FILE_INVALID"],
                "execution_allowed": False,
                "physical_writes": False,
                "home_assistant_writes": False,
                "sma_writes": False,
                "smappee_writes": False,
                "decisions": [],
            }
        )
        _write_json(args.intent_output, bundle)
        _write_json(args.review_output, review)
        _write_json(args.proposals_output, [])
        print(
            json.dumps(
                {"error": type(error).__name__, "status": "REJECTED"},
                sort_keys=True,
            )
        )
        return 2
    bundle = build_intent_bundle(plan, inputs, now=args.now)
    review = supervise_intents(bundle, state, now=args.now)
    proposals = build_dry_run_proposals(review)
    _write_json(args.intent_output, bundle)
    _write_json(args.review_output, review)
    _write_json(args.proposals_output, proposals)
    print(
        json.dumps(
            {
                "bundle_status": bundle["status"],
                "review_status": review["status"],
                "intent_count": len(bundle.get("intents", [])),
                "proposal_count": len(proposals),
                "execution_allowed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
