#!/usr/bin/env python3
"""Build a prospective read-only shadow plan from a frozen daily input bundle."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ZONE = ZoneInfo("Europe/Brussels")
QUARTER = timedelta(minutes=15)


def _load_planner_module() -> Any:
    path = ROOT / "scripts" / "build_shadow_controller_plan.py"
    spec = importlib.util.spec_from_file_location("prospective_shadow_planner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load shadow planner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLANNER = _load_planner_module()


def parse_instant(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an offset-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an offset-aware timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be an offset-aware timestamp")
    return parsed.astimezone(timezone.utc)


def target_instants(target: date) -> list[datetime]:
    start_local = datetime.combine(target, time.min, tzinfo=ZONE)
    end_local = datetime.combine(target + timedelta(days=1), time.min, tzinfo=ZONE)
    cursor = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    output = []
    while cursor < end_utc:
        output.append(cursor)
        cursor += QUARTER
    return output


def reconstruct_actual_base_net_kwh(
    *,
    grid_import_kwh: float,
    grid_export_kwh: float,
    battery_charge_kwh: float,
    battery_discharge_kwh: float,
) -> float:
    """Remove observed battery dispatch before applying a shadow schedule."""
    return (
        float(grid_import_kwh)
        - float(grid_export_kwh)
        - float(battery_charge_kwh)
        + float(battery_discharge_kwh)
    )


def _finite_nonnegative(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite non-negative number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be a finite non-negative number")
    return number


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def _no_action(
    bundle: Any,
    flags: list[str],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    target_date = bundle.get("target_date") if isinstance(bundle, dict) else None
    generated_at = generated_at or datetime.now(timezone.utc)
    try:
        instants = target_instants(date.fromisoformat(str(target_date)))
        target_start = instants[0]
        target_end = instants[-1] + QUARTER
    except (TypeError, ValueError):
        target_start = generated_at
        target_end = generated_at + QUARTER
    return {
        "schema_version": 1,
        "mode": "READ_ONLY_SHADOW",
        "classification": "PROPOSED_PLAN_NO_CONTROL",
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "status": "NO_ACTION",
        "reason": "INVALID_OR_STALE_PROSPECTIVE_CAPTURE",
        "target_date": target_date,
        "generated_at": generated_at.isoformat(),
        "target_start_utc": target_start.isoformat(),
        "target_end_utc": target_end.isoformat(),
        "quality_flags": sorted(set(flags)),
        "capture_quality": "REJECTED_PROSPECTIVE_DAY",
        "plans": [],
        "intervals": [],
    }


def build_prospective_plan(
    bundle: dict[str, Any],
    *,
    battery: dict[str, Any],
    degradation_rate: float,
    state_step_kwh: float = 0.25,
    planning_completed_at: datetime | None = None,
) -> dict[str, Any]:
    flags: list[str] = []
    if not isinstance(bundle, dict) or bundle.get("mode") != "READ_ONLY_SHADOW_CAPTURE":
        return _no_action(bundle, ["INVALID_CAPTURE_BUNDLE"])
    try:
        captured_at = parse_instant(bundle.get("captured_at"), "captured_at")
        target = date.fromisoformat(str(bundle.get("target_date")))
        expected = target_instants(target)
        start_utc = expected[0]
        if captured_at >= start_utc:
            flags.append("CAPTURE_NOT_BEFORE_TARGET_DAY")

        soc = bundle.get("initial_soc")
        if not isinstance(soc, dict):
            flags.append("MISSING_INITIAL_SOC")
            soc = {}
        soc_percent = _finite_nonnegative(soc.get("percent"), "initial_soc.percent")
        if soc_percent > 100:
            flags.append("INVALID_INITIAL_SOC")
        observed_at = parse_instant(soc.get("observed_at"), "initial_soc.observed_at")
        max_age = _finite_nonnegative(
            soc.get("max_age_minutes"), "initial_soc.max_age_minutes"
        )
        if observed_at > captured_at:
            flags.append("INITIAL_SOC_OBSERVED_AFTER_CAPTURE")
        elif captured_at - observed_at > timedelta(minutes=max_age):
            flags.append("STALE_INITIAL_SOC")
        if soc.get("source") != "MEASURED_HOME_ASSISTANT":
            flags.append("INITIAL_SOC_NOT_MEASURED")

        sources = bundle.get("sources")
        if not isinstance(sources, dict):
            flags.append("MISSING_SOURCE_METADATA")
            sources = {}
        for key, flag in (
            ("pv_forecast_issued_at", "PV_FORECAST_ISSUED_AFTER_CAPTURE"),
            ("load_forecast_issued_at", "LOAD_FORECAST_ISSUED_AFTER_CAPTURE"),
            ("prices_issued_at", "PRICES_ISSUED_AFTER_CAPTURE"),
        ):
            issued = parse_instant(sources.get(key), f"sources.{key}")
            if issued > captured_at:
                flags.append(flag)
        for key in ("ev_mode", "heat_pump_mode"):
            if sources.get(key) != "OBSERVATION_ONLY_INCLUDED_IN_TOTAL_LOAD":
                flags.append(f"INVALID_{key.upper()}")

        month_peak = _finite_nonnegative(
            bundle.get("month_peak_to_date_kw"), "month_peak_to_date_kw"
        )
        intervals = bundle.get("intervals")
        if not isinstance(intervals, list):
            flags.append("MISSING_INTERVALS")
            intervals = []
        if len(intervals) != len(expected):
            flags.append("INCOMPLETE_FORECAST_INTERVALS")

        forecast_rows = []
        for index, row in enumerate(intervals):
            if not isinstance(row, dict):
                flags.append("INVALID_INTERVAL_STRUCTURE")
                continue
            start = parse_instant(row.get("start_utc"), "interval.start_utc")
            if index >= len(expected) or start != expected[index]:
                flags.append("NONCONTIGUOUS_OR_SHIFTED_INTERVALS")
            duration = _finite_nonnegative(row.get("duration_hours"), "duration_hours")
            if abs(duration - 0.25) > 1e-12:
                flags.append("INVALID_INTERVAL_DURATION")
            load = _finite_nonnegative(
                row.get("load_forecast_kwh"), "load_forecast_kwh"
            )
            pv = _finite_nonnegative(row.get("pv_forecast_kwh"), "pv_forecast_kwh")
            market = _finite_number(
                row.get("market_price_eur_per_mwh"), "market_price_eur_per_mwh"
            )
            import_rate = _finite_number(
                row.get("import_rate_eur_per_kwh"), "import_rate_eur_per_kwh"
            )
            export_rate = _finite_number(
                row.get("export_rate_eur_per_kwh"), "export_rate_eur_per_kwh"
            )
            row_flags = row.get("quality_flags", [])
            if not isinstance(row_flags, list):
                flags.append("INVALID_INTERVAL_QUALITY_FLAGS")
                row_flags = []
            if row_flags:
                flags.extend(str(flag) for flag in row_flags)
            forecast_rows.append(
                {
                    "start_utc": start.isoformat(),
                    "start_local": start.astimezone(ZONE).isoformat(),
                    "duration_hours": duration,
                    "forecast_base_net_kwh": load - pv,
                    "load_forecast_kwh": load,
                    "pv_forecast_kwh": pv,
                    "market_price_eur_per_mwh": market,
                    "import_rate_eur_per_kwh": import_rate,
                    "export_rate_eur_per_kwh": export_rate,
                    "quality_flags": [],
                }
            )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        flags.append(f"INVALID_CAPTURE_VALUE:{error}")
        return _no_action(bundle, flags)

    if flags:
        return _no_action(bundle, flags)

    capacity = _finite_nonnegative(
        battery.get("usable_capacity_kwh"), "battery.usable_capacity_kwh"
    )
    initial_soc_kwh = capacity * soc_percent / 100
    policies = [
        {
            "id": "peak_neutral",
            "title": "Piekneutraal",
            "cap_kw": month_peak,
        },
        {"id": "cap_7_kw", "title": "Absolute grens 7 kW", "cap_kw": 7.0},
        {"id": "cap_8_kw", "title": "Absolute grens 8 kW", "cap_kw": 8.0},
        {"id": "cap_10_kw", "title": "Absolute grens 10 kW", "cap_kw": 10.0},
    ]
    report = PLANNER.build_shadow_plan(
        forecast_rows,
        battery=battery,
        initial_soc_kwh=initial_soc_kwh,
        degradation_rate=degradation_rate,
        peak_caps_kw=policies,
        expected_interval_count=len(expected),
        state_step_kwh=state_step_kwh,
    )
    completed_at = planning_completed_at or datetime.now(timezone.utc)
    if completed_at.tzinfo is None or completed_at.utcoffset() is None:
        return _no_action(bundle, ["INVALID_PLANNING_COMPLETION_TIME"])
    completed_at = completed_at.astimezone(timezone.utc)
    if completed_at >= start_utc:
        return _no_action(
            bundle,
            ["PLAN_GENERATED_AFTER_TARGET_START"],
            generated_at=completed_at,
        )
    report.update(
        {
            "target_date": target.isoformat(),
            "generated_at": completed_at.isoformat(),
            "captured_at": captured_at.isoformat(),
            "capture_quality": "ACCEPTED_PROSPECTIVE_DAY",
            "capture_sources": sources,
            "month_peak_to_date_kw": month_peak,
            "intervals": forecast_rows,
            "battery": {
                "usable_capacity_kwh": capacity,
                "max_charge_power_kw": battery["max_charge_power_kw"],
                "max_discharge_power_kw": battery["max_discharge_power_kw"],
                "round_trip_efficiency": battery.get("round_trip_efficiency"),
                "initial_soc_percent": soc_percent,
                "initial_soc_source": "MEASURED_HOME_ASSISTANT",
                "initial_soc_observed_at": observed_at.isoformat(),
            },
            "forecast_method": (
                "versioned quarter-hour total-load forecast minus native-resolution "
                "PV forecast; EV and heat pump remain observation-only within total load"
            ),
        }
    )
    return report


def privacy_safe_summary(report: dict[str, Any]) -> dict[str, Any]:
    plans = [
        {key: value for key, value in plan.items() if key != "schedule"}
        for plan in report.get("plans", [])
    ]
    return {
        key: value
        for key, value in report.items()
        if key not in {"plans", "intervals"}
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument(
        "--battery-config",
        type=Path,
        default=Path("config/battery/battery-parameters.json"),
    )
    parser.add_argument(
        "--marginal-costs",
        type=Path,
        default=Path("config/tariffs/battery-arbitrage-marginal-costs.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    parser.add_argument("--state-step-kwh", type=float, default=0.25)
    args = parser.parse_args()

    battery = load_json(args.battery_config)["battery"]
    marginal = load_json(args.marginal_costs)
    report = build_prospective_plan(
        load_json(args.bundle),
        battery=battery,
        degradation_rate=float(
            marginal["central_degradation_eur_per_discharged_kwh"]
        ),
        state_step_kwh=args.state_step_kwh,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    args.evidence_output.write_text(
        json.dumps(privacy_safe_summary(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "target_date": report.get("target_date"),
                "capture_quality": report["capture_quality"],
                "selected_policy_id": report.get("selected_policy_id"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
