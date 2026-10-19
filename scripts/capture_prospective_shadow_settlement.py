#!/usr/bin/env python3
"""Settle one completed prospective shadow day from read-only HA statistics."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
import math
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ZONE = ZoneInfo("Europe/Brussels")


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPORT = load_module(
    "prospective_settlement_export", ROOT / "scripts" / "export_ha_energy_statistics.py"
)
SETTLE = load_module(
    "prospective_settlement", ROOT / "scripts" / "settle_prospective_shadow_plan.py"
)
SUMMARIZE = load_module(
    "prospective_settlement_summary",
    ROOT / "scripts" / "summarize_prospective_shadow_validation.py",
)
INTEGRITY = load_module(
    "prospective_joint_artifact_integrity",
    ROOT / "scripts" / "joint_artifact_integrity.py",
)

REQUIRED_ALIASES = (
    "grid_import",
    "grid_export",
    "pv_generation",
    "battery_charge",
    "battery_discharge",
    "ev_charge",
)


def target_bounds(target: date) -> tuple[datetime, datetime]:
    start = datetime.combine(target, time.min, tzinfo=ZONE).astimezone(timezone.utc)
    end = datetime.combine(
        target + timedelta(days=1), time.min, tzinfo=ZONE
    ).astimezone(timezone.utc)
    return start, end


def finite_nonnegative(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite non-negative number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be a finite non-negative number")
    return number


def build_actual_bundle(
    target: date, exported: dict[str, Any], *, settled_at: str
) -> dict[str, Any]:
    series = exported.get("series")
    if not isinstance(series, dict):
        raise ValueError("exported energy must contain series")
    for alias in REQUIRED_ALIASES:
        if not isinstance(series.get(alias), list):
            raise ValueError(f"exported energy misses {alias}")

    counts = {len(series[alias]) for alias in REQUIRED_ALIASES}
    if len(counts) != 1:
        raise ValueError("exported energy series lengths differ")
    rows = []
    for index in range(next(iter(counts))):
        source = {alias: series[alias][index] for alias in REQUIRED_ALIASES}
        starts = {row.get("start_utc") for row in source.values()}
        if len(starts) != 1:
            raise ValueError("exported energy timestamps differ")
        flags = []
        values = {}
        for alias, row in source.items():
            energy = row.get("energy_kwh")
            if energy is None:
                values[alias] = 0.0
                flags.append(f"{alias}:missing_energy_value")
            else:
                values[alias] = finite_nonnegative(
                    energy, f"{alias}.energy_kwh"
                )
            source_flags = row.get("quality_flags", [])
            if not isinstance(source_flags, list):
                flags.append(f"{alias}:invalid_quality_flags")
            else:
                flags.extend(f"{alias}:{flag}" for flag in source_flags)
        reconstructed_load = (
            values["grid_import"]
            - values["grid_export"]
            + values["pv_generation"]
            + values["battery_discharge"]
            - values["battery_charge"]
        )
        if reconstructed_load < -1e-9:
            flags.append("NEGATIVE_RECONSTRUCTED_LOAD")
        rows.append(
            {
                "start_utc": next(iter(starts)),
                "duration_hours": 0.25,
                "grid_import_kwh": values["grid_import"],
                "grid_export_kwh": values["grid_export"],
                "battery_charge_kwh": values["battery_charge"],
                "battery_discharge_kwh": values["battery_discharge"],
                "load_actual_kwh": max(0.0, reconstructed_load),
                "pv_actual_kwh": values["pv_generation"],
                "ev_charge_kwh": values["ev_charge"],
                "quality_flags": sorted(set(flags)),
            }
        )
    return {
        "schema_version": 1,
        "mode": "READ_ONLY_SHADOW_SETTLEMENT",
        "target_date": target.isoformat(),
        "settled_at": settled_at,
        "intervals": rows,
    }


def classify_primary_stratum(
    target: date,
    *,
    minimum_market_price: float,
    pv_forecast_kwh: float,
    ev_charge_kwh: float,
) -> str:
    if minimum_market_price < 0:
        return "negative_price_day"
    if target.weekday() >= 5:
        return "weekend"
    if ev_charge_kwh >= 5.0:
        return "high_load_ev_day"
    if target.month in {12, 1, 2}:
        return "winter_weekday"
    if target.month in {5, 6, 7, 8} and pv_forecast_kwh >= 20.0:
        return "summer_high_pv_weekday"
    return "ordinary_shoulder_weekday"


def empty_actual_bundle(target: date, settled_at: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": "READ_ONLY_SHADOW_SETTLEMENT",
        "target_date": target.isoformat(),
        "settled_at": settled_at,
        "intervals": [],
    }


def rejected_joint_score(
    target: date, settled_at: str, flags: list[str]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": "READ_ONLY_JOINT_DRY_RUN_SETTLEMENT",
        "classification": "AFTER_THE_FACT_JOINT_DRY_RUN_SCORE_NO_CONTROL",
        "status": "REJECTED",
        "target_date": target.isoformat(),
        "settled_at": settled_at,
        "quality_flags": sorted(set(flags)),
        "target_count": 0,
        "targets": {},
        "interval_scores": [],
        "execution_allowed": False,
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
    }


def _parse_instant(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an offset-aware timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be an offset-aware timestamp")
    return parsed.astimezone(timezone.utc)


def score_joint_dry_run(
    target: date,
    capture_summary: dict[str, Any],
    proposals: list[dict[str, Any]],
    actual: dict[str, Any],
    *,
    settled_at: str,
) -> dict[str, Any]:
    flags: list[str] = []
    required_false = (
        "execution_allowed",
        "physical_writes",
        "home_assistant_writes",
        "sma_writes",
        "smappee_writes",
    )
    if (
        not isinstance(capture_summary, dict)
        or capture_summary.get("mode") != "PROSPECTIVE_JOINT_CONTROL_DRY_RUN"
        or capture_summary.get("classification")
        != "PRIVACY_SAFE_JOINT_CONTROL_EVIDENCE_NO_EXECUTION"
        or capture_summary.get("status") != "ACCEPTED_DRY_RUN"
        or any(capture_summary.get(field) is not False for field in required_false)
    ):
        flags.append("JOINT_CAPTURE_NOT_ACCEPTED_READ_ONLY")
    if not isinstance(proposals, list) or not proposals:
        flags.append("JOINT_PROPOSALS_MISSING")
        proposals = []
    try:
        proposal_set_sha256 = hashlib.sha256(
            json.dumps(
                proposals,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
    except (TypeError, ValueError, OverflowError):
        proposal_set_sha256 = None
    if (
        proposal_set_sha256 is None
        or capture_summary.get("proposal_set_sha256") != proposal_set_sha256
    ):
        flags.append("JOINT_PROPOSAL_DIGEST_MISMATCH")
    if (
        capture_summary.get("target_date") != target.isoformat()
        or not isinstance(capture_summary.get("source_plan_id"), str)
        or not capture_summary.get("source_plan_id")
    ):
        flags.append("JOINT_CAPTURE_IDENTITY_INVALID")
    count_fields = {
        "intent_count": len(proposals),
        "accepted_decision_count": len(proposals),
        "rejected_decision_count": 0,
        "proposal_count": len(proposals),
    }
    if any(
        isinstance(capture_summary.get(field), bool)
        or capture_summary.get(field) != expected
        for field, expected in count_fields.items()
    ):
        flags.append("JOINT_CAPTURE_PROPOSAL_MISMATCH")
    try:
        capture_valid_from = _parse_instant(
            capture_summary.get("valid_from_utc"), "joint capture valid_from_utc"
        )
        capture_valid_until = _parse_instant(
            capture_summary.get("valid_until_utc"), "joint capture valid_until_utc"
        )
        if capture_valid_until <= capture_valid_from:
            raise ValueError("joint capture validity is empty")
    except (TypeError, ValueError, OverflowError):
        capture_valid_from = None
        capture_valid_until = None
        flags.append("JOINT_CAPTURE_VALIDITY_INVALID")
    actual_rows = actual.get("intervals") if isinstance(actual, dict) else None
    if (
        not isinstance(actual, dict)
        or actual.get("mode") != "READ_ONLY_SHADOW_SETTLEMENT"
        or actual.get("target_date") != target.isoformat()
        or not isinstance(actual_rows, list)
    ):
        return rejected_joint_score(target, settled_at, flags + ["JOINT_ACTUAL_BUNDLE_INVALID"])

    actual_by_start = {}
    try:
        for row in actual_rows:
            if not isinstance(row, dict):
                raise ValueError("actual row must be an object")
            start = _parse_instant(row.get("start_utc"), "actual start_utc").isoformat()
            if start in actual_by_start:
                raise ValueError("duplicate actual interval")
            row_flags = row.get("quality_flags")
            if not isinstance(row_flags, list) or row_flags:
                raise ValueError("actual interval quality rejected")
            actual_by_start[start] = row
        expected_start, expected_end = target_bounds(target)
        expected_starts = []
        instant = expected_start
        while instant < expected_end:
            expected_starts.append(instant.isoformat())
            instant += timedelta(minutes=15)
        if instant != expected_end or list(actual_by_start) != expected_starts:
            raise ValueError("actual intervals do not cover complete target day")
        if any(
            abs(finite_nonnegative(row.get("duration_hours"), "actual duration_hours") - 0.25)
            > 1e-9
            for row in actual_by_start.values()
        ):
            raise ValueError("actual intervals are not quarter-hourly")
    except (TypeError, ValueError, OverflowError):
        flags.append("JOINT_ACTUAL_INTERVALS_INVALID")

    interval_scores = []
    seen = set()
    for proposal in proposals:
        if not isinstance(proposal, dict):
            flags.append("JOINT_PROPOSAL_INVALID")
            continue
        if (
            proposal.get("schema_version") != 1
            or proposal.get("classification") != "NON_DISPATCHABLE_COMMAND_PROPOSAL"
            or proposal.get("transport") != "NONE"
            or proposal.get("dispatch_supported") is not False
            or proposal.get("execution_action") != "NO_ACTION"
            or any(proposal.get(field) is not False for field in required_false)
        ):
            flags.append("JOINT_PROPOSAL_WRITE_BOUNDARY_INVALID")
            continue
        try:
            target_name = proposal.get("target")
            if not isinstance(target_name, str):
                raise ValueError("proposal target invalid")
            expected_adapter = {
                "BATTERY": "SMA_DRY_RUN",
                "EV_CHARGER": "SMAPPEE_DRY_RUN",
            }[target_name]
            if proposal.get("adapter") != expected_adapter:
                raise ValueError("adapter mismatch")
            if proposal.get("safety_decision") != "ACCEPTED_DRY_RUN":
                raise ValueError("proposal was not safety accepted")
            if proposal.get("safety_reasons") != []:
                raise ValueError("proposal has safety reasons")
            interval = proposal.get("target_interval")
            if not isinstance(interval, dict):
                raise ValueError("target interval missing")
            start = _parse_instant(interval.get("start_utc"), "proposal start_utc")
            end = _parse_instant(interval.get("end_utc"), "proposal end_utc")
            duration = (end - start).total_seconds() / 3600
            if duration <= 0:
                raise ValueError("proposal interval duration invalid")
            key = (target_name, start.isoformat())
            if key in seen:
                raise ValueError("duplicate target proposal")
            seen.add(key)
            measured = actual_by_start[start.isoformat()]
            measured_duration = finite_nonnegative(
                measured.get("duration_hours"), "actual duration_hours"
            )
            if (
                measured_duration <= 0
                or abs(duration - measured_duration) > 1e-9
                or capture_valid_from is None
                or capture_valid_until is None
                or start < capture_valid_from
                or end > capture_valid_until
            ):
                raise ValueError("proposal interval does not match captured actual interval")
            expected_intent_id = (
                f"{capture_summary.get('source_plan_id')}:{target_name}:{start.isoformat()}"
            )
            if proposal.get("intent_id") != expected_intent_id:
                raise ValueError("proposal identity does not match capture")
            proposed_action = proposal.get("proposed_action")
            proposed_power = finite_nonnegative(
                proposal.get("proposed_power_kw"), "proposed_power_kw"
            )
            if proposed_action not in {"CHARGE", "DISCHARGE", "HOLD", "NO_ACTION"}:
                raise ValueError("proposed action invalid")
            if target_name == "EV_CHARGER" and proposed_action == "DISCHARGE":
                raise ValueError("EV discharge is invalid")
            if (proposed_action in {"HOLD", "NO_ACTION"}) != (proposed_power == 0.0):
                raise ValueError("proposed action and power disagree")

            if target_name == "BATTERY":
                charge = finite_nonnegative(
                    measured.get("battery_charge_kwh"), "battery_charge_kwh"
                )
                discharge = finite_nonnegative(
                    measured.get("battery_discharge_kwh"), "battery_discharge_kwh"
                )
                if charge > 1e-9 and discharge > 1e-9:
                    raise ValueError("simultaneous observed battery charge and discharge")
                actual_action = (
                    "CHARGE" if charge > 1e-9 else "DISCHARGE" if discharge > 1e-9 else "HOLD"
                )
                actual_energy = (
                    charge
                    if proposed_action == "CHARGE"
                    else discharge
                    if proposed_action == "DISCHARGE"
                    else charge + discharge
                )
            else:
                ev_energy = finite_nonnegative(
                    measured.get("ev_charge_kwh"), "ev_charge_kwh"
                )
                actual_action = "CHARGE" if ev_energy > 1e-9 else "HOLD"
                actual_energy = ev_energy
            proposed_energy = proposed_power * duration
            interval_scores.append(
                {
                    "target": target_name,
                    "intent_id": proposal.get("intent_id"),
                    "start_utc": start.isoformat(),
                    "end_utc": end.isoformat(),
                    "proposed_action": proposed_action,
                    "actual_action": actual_action,
                    "proposed_energy_kwh": proposed_energy,
                    "actual_energy_kwh": actual_energy,
                    "absolute_energy_error_kwh": abs(actual_energy - proposed_energy),
                    "action_match": proposed_action == actual_action
                    or (proposed_action == "NO_ACTION" and actual_action == "HOLD"),
                }
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            flags.append("JOINT_PROPOSAL_OR_ACTUAL_VALUE_INVALID")

    expected_coverage = {
        (target_name, start)
        for start in (
            (target_bounds(target)[0] + timedelta(minutes=15 * index)).isoformat()
            for index in range(
                int(
                    (target_bounds(target)[1] - target_bounds(target)[0]).total_seconds()
                    // 900
                )
            )
        )
        for target_name in ("BATTERY", "EV_CHARGER")
    }
    if seen != expected_coverage:
        flags.append("JOINT_TARGET_INTERVAL_COVERAGE_INVALID")
    if flags or len(interval_scores) != len(proposals):
        return rejected_joint_score(target, settled_at, flags or ["JOINT_SCORE_INCOMPLETE"])

    targets = {}
    for target_name in sorted({row["target"] for row in interval_scores}):
        rows = [row for row in interval_scores if row["target"] == target_name]
        targets[target_name] = {
            "interval_count": len(rows),
            "energy_mae_kwh": sum(row["absolute_energy_error_kwh"] for row in rows)
            / len(rows),
            "action_match_count": sum(row["action_match"] for row in rows),
            "action_match_rate": sum(row["action_match"] for row in rows) / len(rows),
            "proposed_energy_kwh": sum(row["proposed_energy_kwh"] for row in rows),
            "actual_energy_kwh": sum(row["actual_energy_kwh"] for row in rows),
        }
    return {
        "schema_version": 1,
        "mode": "READ_ONLY_JOINT_DRY_RUN_SETTLEMENT",
        "classification": "AFTER_THE_FACT_JOINT_DRY_RUN_SCORE_NO_CONTROL",
        "status": "SCORED",
        "target_date": target.isoformat(),
        "settled_at": settled_at,
        "quality_flags": [],
        "target_count": len(targets),
        "targets": targets,
        "interval_scores": interval_scores,
        "execution_allowed": False,
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
    }


def privacy_safe_joint_score(score: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in score.items() if key != "interval_scores"} | {
        "privacy": {
            "quarter_household_profile_included": False,
            "device_identifiers_included": False,
        }
    }


def failure_settlement(target: date, flag: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": "READ_ONLY_SHADOW_SETTLEMENT",
        "classification": "AFTER_THE_FACT_EXECUTION_SCORE_NO_CONTROL",
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "status": "REJECTED",
        "quality": "REJECTED_PROSPECTIVE_DAY",
        "target_date": target.isoformat(),
        "quality_flags": [flag],
        "plans": [],
        "actual_intervals": [],
    }


def failure_cohort_report(target: date, flag: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": "READ_ONLY_SHADOW_VALIDATION_COHORT",
        "classification": "PROSPECTIVE_MULTI_DAY_EVIDENCE_NO_CONTROL",
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "status": "IN_PROGRESS",
        "required_day_count": 12,
        "qualifying_day_count": 0,
        "remaining_day_count": 12,
        "captured_plan_count": 0,
        "settlement_summary_count": 1,
        "qualifying_dates": [],
        "pending_days": [],
        "rejected_days": [
            {"target_date": target.isoformat(), "quality_flags": [flag]}
        ],
        "strata": {},
        "forecast_error_mean": {
            "load_mae_kwh": None,
            "pv_mae_kwh": None,
            "base_net_mae_kwh": None,
        },
        "policy_aggregates": {},
        "privacy": {
            "quarter_household_profile_included": False,
            "device_identifiers_included": False,
        },
    }


def upsert_by_target_date(
    rows: list[dict[str, Any]], current: dict[str, Any]
) -> list[dict[str, Any]]:
    target_date = current.get("target_date")
    return [row for row in rows if row.get("target_date") != target_date] + [current]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_json_list(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{path} must contain a JSON array of objects")
    return value


def load_verified_joint_capture_set(
    captures_dir: Path,
    target: date,
    *,
    integrity_key_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    artifacts: dict[str, Any] = {
        "intents": load_json(captures_dir / f"joint-intents-{target}.json"),
        "review": load_json(captures_dir / f"joint-review-{target}.json"),
        "proposals": load_json_list(
            captures_dir / f"joint-proposals-{target}.json"
        ),
        "summary": load_json(captures_dir / f"joint-summary-{target}.json"),
    }
    manifest = load_json(captures_dir / f"joint-manifest-{target}.json")
    key = INTEGRITY.load_key(integrity_key_path)
    INTEGRITY.verify_manifest(manifest, target, artifacts, key=key)
    return artifacts["summary"], artifacts["proposals"]


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def persist_outputs(
    *,
    target: date,
    settled_at: str,
    captures_dir: Path,
    cohort_output: Path,
    runtime_config_path: Path,
    actual: dict[str, Any],
    settlement: dict[str, Any],
    summary: dict[str, Any],
    cohort: dict[str, Any],
    runtime_config: dict[str, Any] | None,
) -> dict[str, Any]:
    try:
        write_json_atomic(captures_dir / f"actual-{target}.json", actual)
        write_json_atomic(captures_dir / f"settlement-{target}.json", settlement)
        write_json_atomic(
            captures_dir / f"settlement-summary-{target}.json", summary
        )
        write_json_atomic(cohort_output, cohort)
        if runtime_config is not None:
            write_json_atomic(runtime_config_path, runtime_config)
        return {
            "actual": actual,
            "settlement": settlement,
            "summary": summary,
            "cohort": cohort,
            "failed_closed": False,
        }
    except Exception as error:
        flag = f"SETTLEMENT_OUTPUT_ERROR:{type(error).__name__}"
        failed_actual = empty_actual_bundle(target, settled_at)
        failed_settlement = failure_settlement(target, flag)
        failed_summary = SETTLE.privacy_safe_summary(failed_settlement)
        failed_cohort = failure_cohort_report(target, flag)
        fallback_outputs = (
            (captures_dir / f"actual-{target}.json", failed_actual),
            (captures_dir / f"settlement-{target}.json", failed_settlement),
            (
                captures_dir / f"settlement-summary-{target}.json",
                failed_summary,
            ),
            (cohort_output, failed_cohort),
        )
        fallback_errors = []
        for path, value in fallback_outputs:
            try:
                write_json_atomic(path, value)
            except Exception as fallback_error:
                fallback_errors.append(
                    f"{path.name}:{type(fallback_error).__name__}"
                )
        if fallback_errors:
            raise OSError(
                "fail-closed output writes failed: " + ", ".join(fallback_errors)
            ) from error
        return {
            "actual": failed_actual,
            "settlement": failed_settlement,
            "summary": failed_summary,
            "cohort": failed_cohort,
            "failed_closed": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-date", type=date.fromisoformat)
    parser.add_argument(
        "--captures-dir",
        type=Path,
        default=Path("data/raw/shadow-validation-captures"),
    )
    parser.add_argument(
        "--entity-map",
        type=Path,
        default=Path("config/private/ha-energy-entities.json"),
    )
    parser.add_argument(
        "--battery-config",
        type=Path,
        default=Path("config/simulation/battery-scenario-owner-confirmed.json"),
    )
    parser.add_argument(
        "--marginal-costs",
        type=Path,
        default=Path("config/tariffs/battery-arbitrage-marginal-costs.json"),
    )
    parser.add_argument(
        "--cohort-template",
        type=Path,
        default=Path("config/validation/prospective-shadow-cohort.json"),
    )
    parser.add_argument(
        "--cohort-output",
        type=Path,
        default=Path("docs/evidence/prospective-shadow-validation-cohort.json"),
    )
    parser.add_argument(
        "--wrapper",
        default=str(Path.home() / ".hermes/bin/home-assistant-mcp-wrapper"),
    )
    parser.add_argument(
        "--joint-integrity-key",
        type=Path,
        default=Path("config/private/joint-artifact-hmac.key"),
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    target = args.target_date or (now.astimezone(ZONE).date() - timedelta(days=1))
    runtime_config_path = args.captures_dir / "cohort-runtime.json"
    runtime_config_to_write: dict[str, Any] | None = None
    exit_code = 0
    stratum = None
    try:
        plan = load_json(args.captures_dir / f"plan-{target}.json")
        start, end = target_bounds(target)
        if plan.get("status") == "PLANNED":
            entity_map = EXPORT.load_entity_map(args.entity_map)
            missing = sorted(set(REQUIRED_ALIASES) - set(entity_map))
            if missing:
                raise ValueError(
                    f"entity map misses required aliases: {', '.join(missing)}"
                )
            responses, _ = asyncio.run(
                EXPORT.query_statistics(
                    wrapper=args.wrapper,
                    entity_map=entity_map,
                    start=start,
                    end=end,
                    chunk_days=1,
                    source_period="5minute",
                )
            )
            exported = EXPORT.build_export(
                responses,
                entity_map=entity_map,
                start=start.isoformat(),
                end=end.isoformat(),
                retrieved_at=now.isoformat(),
                source_period="5minute",
            )
            actual = build_actual_bundle(
                target, exported, settled_at=now.isoformat()
            )
        else:
            actual = empty_actual_bundle(target, now.isoformat())

        battery = load_json(args.battery_config)["battery"]
        marginal = load_json(args.marginal_costs)
        settlement = SETTLE.settle_plan(
            plan,
            actual,
            battery=battery,
            degradation_rate=float(
                marginal["central_degradation_eur_per_discharged_kwh"]
            ),
        )
        summary = SETTLE.privacy_safe_summary(settlement)

        cohort_config = (
            load_json(runtime_config_path)
            if runtime_config_path.exists()
            else load_json(args.cohort_template)
        )
        assignments = cohort_config.get("assignments")
        if not isinstance(assignments, dict):
            raise ValueError("cohort assignments must be an object")
        candidate_runtime_config = copy.deepcopy(cohort_config)
        candidate_assignments = candidate_runtime_config["assignments"]
        if settlement.get("status") == "SETTLED":
            intervals = plan.get("intervals", [])
            minimum_market_price = min(
                float(row["market_price_eur_per_mwh"]) for row in intervals
            )
            pv_forecast_kwh = sum(
                float(row["pv_forecast_kwh"]) for row in intervals
            )
            ev_charge_kwh = sum(
                float(row.get("ev_charge_kwh", 0.0))
                for row in actual["intervals"]
            )
            stratum = classify_primary_stratum(
                target,
                minimum_market_price=minimum_market_price,
                pv_forecast_kwh=pv_forecast_kwh,
                ev_charge_kwh=ev_charge_kwh,
            )
            candidate_assignments[target.isoformat()] = stratum

        settlements = upsert_by_target_date(
            SUMMARIZE.load_matching(
                args.captures_dir, "settlement-summary-*.json"
            ),
            summary,
        )
        cohort = SUMMARIZE.build_cohort_report(
            SUMMARIZE.load_matching(args.captures_dir, "plan-*.json"),
            settlements,
            candidate_assignments,
            strata=cohort_config.get("strata", SUMMARIZE.DEFAULT_STRATA),
            required_per_stratum=int(cohort_config.get("required_per_stratum", 2)),
        )
        if settlement.get("status") == "SETTLED":
            runtime_config_to_write = candidate_runtime_config
        if settlement.get("status") != "SETTLED":
            exit_code = 2
    except Exception as error:  # fail closed at the scheduled integration boundary
        flag = f"SETTLEMENT_PIPELINE_ERROR:{type(error).__name__}"
        actual = empty_actual_bundle(target, now.isoformat())
        settlement = failure_settlement(target, flag)
        summary = SETTLE.privacy_safe_summary(settlement)
        cohort = failure_cohort_report(target, flag)
        exit_code = 2

    persisted = persist_outputs(
        target=target,
        settled_at=now.isoformat(),
        captures_dir=args.captures_dir,
        cohort_output=args.cohort_output,
        runtime_config_path=runtime_config_path,
        actual=actual,
        settlement=settlement,
        summary=summary,
        cohort=cohort,
        runtime_config=runtime_config_to_write,
    )
    actual = persisted["actual"]
    settlement = persisted["settlement"]
    summary = persisted["summary"]
    cohort = persisted["cohort"]
    if persisted["failed_closed"]:
        stratum = None
        exit_code = 2
    try:
        joint_capture_summary, joint_proposals = load_verified_joint_capture_set(
            args.captures_dir,
            target,
            integrity_key_path=args.joint_integrity_key,
        )
        joint_score = score_joint_dry_run(
            target,
            joint_capture_summary,
            joint_proposals,
            actual,
            settled_at=now.isoformat(),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        joint_score = rejected_joint_score(
            target, now.isoformat(), ["JOINT_SETTLEMENT_INPUT_ERROR"]
        )
    try:
        write_json_atomic(
            args.captures_dir / f"joint-settlement-{target}.json", joint_score
        )
        write_json_atomic(
            args.captures_dir / f"joint-settlement-summary-{target}.json",
            privacy_safe_joint_score(joint_score),
        )
    except Exception as error:
        joint_score = rejected_joint_score(
            target,
            now.isoformat(),
            [f"JOINT_SETTLEMENT_OUTPUT_ERROR:{type(error).__name__}"],
        )
        exit_code = 2
        fallback_errors = []
        for path, value in (
            (args.captures_dir / f"joint-settlement-{target}.json", joint_score),
            (
                args.captures_dir / f"joint-settlement-summary-{target}.json",
                privacy_safe_joint_score(joint_score),
            ),
        ):
            try:
                write_json_atomic(path, value)
            except Exception as fallback_error:
                fallback_errors.append(f"{path.name}:{type(fallback_error).__name__}")
        if fallback_errors:
            raise OSError(
                "joint fail-closed output writes failed: " + ", ".join(fallback_errors)
            ) from error
    print(
        json.dumps(
            {
                "status": settlement["status"],
                "quality": settlement["quality"],
                "target_date": target.isoformat(),
                "primary_stratum": stratum,
                "cohort": f"{cohort['qualifying_day_count']}/{cohort['required_day_count']}",
                "joint_dry_run_score_status": joint_score["status"],
                "execution_allowed": False,
            }
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
