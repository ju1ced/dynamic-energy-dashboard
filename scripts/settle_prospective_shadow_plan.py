#!/usr/bin/env python3
"""Settle a frozen prospective shadow plan against next-day measurements."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _load_planner() -> Any:
    path = ROOT / "scripts" / "build_shadow_controller_plan.py"
    spec = importlib.util.spec_from_file_location("settlement_shadow_planner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load shadow planner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLANNER = _load_planner()


def _finite_nonnegative(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite non-negative number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be a finite non-negative number")
    return number


def _rejected(plan: Any, flags: list[str]) -> dict[str, Any]:
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
        "target_date": plan.get("target_date") if isinstance(plan, dict) else None,
        "quality_flags": sorted(set(flags)),
        "plans": [],
        "actual_intervals": [],
    }


def settle_plan(
    plan: dict[str, Any],
    actual: dict[str, Any],
    *,
    battery: dict[str, Any],
    degradation_rate: float,
) -> dict[str, Any]:
    flags: list[str] = []
    if not isinstance(plan, dict) or plan.get("status") != "PLANNED":
        return _rejected(plan, ["SOURCE_PLAN_NOT_PLANNED"])
    if plan.get("capture_quality") != "ACCEPTED_PROSPECTIVE_DAY":
        flags.append("SOURCE_CAPTURE_NOT_ACCEPTED")
    try:
        generated_at = PLANNER.parse_instant(plan["generated_at"])
        target_start = PLANNER.parse_instant(plan["target_start_utc"])
        if generated_at >= target_start:
            flags.append("SOURCE_PLAN_NOT_PROSPECTIVE")
    except (KeyError, TypeError, ValueError, OverflowError):
        flags.append("INVALID_SOURCE_PLAN_TIMESTAMPS")
    if not isinstance(actual, dict) or actual.get("mode") != "READ_ONLY_SHADOW_SETTLEMENT":
        return _rejected(plan, ["INVALID_ACTUAL_BUNDLE"])
    if actual.get("target_date") != plan.get("target_date"):
        flags.append("TARGET_DATE_MISMATCH")

    forecast_rows = plan.get("intervals")
    actual_rows = actual.get("intervals")
    if not isinstance(forecast_rows, list) or not isinstance(actual_rows, list):
        return _rejected(plan, flags + ["INVALID_INTERVAL_COLLECTION"])
    if len(actual_rows) != len(forecast_rows):
        flags.append("INCOMPLETE_ACTUAL_INTERVALS")

    normalized = []
    load_errors = []
    pv_errors = []
    net_errors = []
    try:
        for index, (forecast, measured) in enumerate(zip(forecast_rows, actual_rows)):
            if not isinstance(forecast, dict) or not isinstance(measured, dict):
                flags.append("INVALID_ACTUAL_INTERVAL_STRUCTURE")
                continue
            forecast_start = PLANNER.parse_instant(forecast["start_utc"])
            actual_start = PLANNER.parse_instant(measured["start_utc"])
            if forecast_start != actual_start:
                flags.append("ACTUAL_TIMESTAMP_MISMATCH")
            duration = _finite_nonnegative(measured.get("duration_hours"), "duration_hours")
            if abs(duration - float(forecast["duration_hours"])) > 1e-12:
                flags.append("ACTUAL_DURATION_MISMATCH")
            import_kwh = _finite_nonnegative(
                measured.get("grid_import_kwh"), "grid_import_kwh"
            )
            export_kwh = _finite_nonnegative(
                measured.get("grid_export_kwh"), "grid_export_kwh"
            )
            charge_kwh = _finite_nonnegative(
                measured.get("battery_charge_kwh"), "battery_charge_kwh"
            )
            discharge_kwh = _finite_nonnegative(
                measured.get("battery_discharge_kwh"), "battery_discharge_kwh"
            )
            load_actual = _finite_nonnegative(
                measured.get("load_actual_kwh"), "load_actual_kwh"
            )
            pv_actual = _finite_nonnegative(measured.get("pv_actual_kwh"), "pv_actual_kwh")
            row_flags = measured.get("quality_flags", [])
            if not isinstance(row_flags, list):
                flags.append("INVALID_ACTUAL_QUALITY_FLAGS")
                row_flags = []
            if row_flags:
                flags.extend(str(flag) for flag in row_flags)
            actual_base = import_kwh - export_kwh - charge_kwh + discharge_kwh
            normalized.append(
                {
                    "start_utc": actual_start.isoformat(),
                    "duration_hours": duration,
                    "actual_base_net_kwh": actual_base,
                    "import_rate_eur_per_kwh": forecast["import_rate_eur_per_kwh"],
                    "export_rate_eur_per_kwh": forecast["export_rate_eur_per_kwh"],
                    "actual_load_kwh": load_actual,
                    "actual_pv_kwh": pv_actual,
                }
            )
            forecast_load = float(forecast["load_forecast_kwh"])
            forecast_pv = float(forecast["pv_forecast_kwh"])
            load_errors.append(abs(load_actual - forecast_load))
            pv_errors.append(abs(pv_actual - forecast_pv))
            net_errors.append(
                abs(actual_base - float(forecast["forecast_base_net_kwh"]))
            )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        flags.append(f"INVALID_ACTUAL_VALUE:{error}")

    if flags:
        return _rejected(plan, flags)

    settled_plans = []
    for policy in plan.get("plans", []):
        if not isinstance(policy, dict):
            return _rejected(plan, ["INVALID_PLAN_POLICY"])
        if policy.get("status") != "PLANNED":
            settled_plans.append(
                {
                    "id": policy.get("id"),
                    "title": policy.get("title"),
                    "cap_kw": policy.get("cap_kw"),
                    "status": "NOT_FEASIBLE",
                    "reason": policy.get("reason"),
                }
            )
            continue
        execution = PLANNER.evaluate_shadow_execution(
            policy["schedule"],
            normalized,
            battery=battery,
            initial_soc_kwh=float(plan["initial_soc_kwh"]),
            degradation_rate=degradation_rate,
            peak_cap_kw=float(policy["cap_kw"]),
        )
        settled_plans.append(
            {
                "id": policy["id"],
                "title": policy["title"],
                "cap_kw": policy["cap_kw"],
                "status": "SETTLED",
                "forecast_cost_eur": policy["planned_total_cost_eur"],
                "forecast_saving_eur": policy["forecast_saving_eur"],
                "executed_cost_eur": execution["shadow_total_cost_eur"],
                "executed_saving_eur": execution["shadow_saving_eur"],
                "baseline_actual_cost_eur": execution["baseline_cost_eur"],
                "terminal_soc_kwh": execution["terminal_soc_kwh"],
                "totals": execution["totals"],
                "schedule": execution["schedule"],
            }
        )

    return {
        "schema_version": 1,
        "mode": "READ_ONLY_SHADOW_SETTLEMENT",
        "classification": "AFTER_THE_FACT_EXECUTION_SCORE_NO_CONTROL",
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "status": "SETTLED",
        "quality": "ACCEPTED_PROSPECTIVE_DAY",
        "target_date": plan["target_date"],
        "settled_at": actual.get("settled_at") or datetime.now(timezone.utc).isoformat(),
        "selected_policy_id": plan.get("selected_policy_id"),
        "quality_flags": [],
        "forecast_error": {
            "load_mae_kwh": sum(load_errors) / len(load_errors),
            "pv_mae_kwh": sum(pv_errors) / len(pv_errors),
            "base_net_mae_kwh": sum(net_errors) / len(net_errors),
        },
        "plans": settled_plans,
        "actual_intervals": normalized,
    }


def privacy_safe_summary(report: dict[str, Any]) -> dict[str, Any]:
    plans = [
        {key: value for key, value in row.items() if key != "schedule"}
        for row in report.get("plans", [])
    ]
    return {
        key: value
        for key, value in report.items()
        if key not in {"plans", "actual_intervals"}
    } | {
        "plans": plans,
        "privacy": {
            "quarter_household_profile_included": False,
            "device_identifiers_included": False,
        },
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--actual", type=Path, required=True)
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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    args = parser.parse_args()

    battery = load_json(args.battery_config)["battery"]
    marginal = load_json(args.marginal_costs)
    report = settle_plan(
        load_json(args.plan),
        load_json(args.actual),
        battery=battery,
        degradation_rate=float(
            marginal["central_degradation_eur_per_discharged_kwh"]
        ),
    )
    write_json(args.output, report)
    write_json(args.evidence_output, privacy_safe_summary(report))
    print(
        json.dumps(
            {
                "status": report["status"],
                "quality": report["quality"],
                "target_date": report.get("target_date"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
