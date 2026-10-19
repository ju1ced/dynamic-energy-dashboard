#!/usr/bin/env python3
"""Build a read-only Day-Ahead battery shadow plan with shared peak limits."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ZONE = ZoneInfo("Europe/Brussels")
QUARTER = timedelta(minutes=15)


def parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp requires an offset: {value}")
    return parsed.astimezone(timezone.utc)


def grid_cost(net_kwh: float, import_rate: float, export_rate: float) -> float:
    return net_kwh * (import_rate if net_kwh >= 0 else export_rate)


def _nearest_state_index(value: float, step: float, count: int) -> int:
    return min(count - 1, max(0, round(value / step)))


def _normalise_policy(value: float | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        cap = float(value["cap_kw"])
        return {
            "id": str(value.get("id", f"cap_{cap:g}_kw")),
            "title": str(value.get("title", f"Maximaal {cap:g} kW")),
            "cap_kw": cap,
        }
    cap = float(value)
    return {
        "id": f"cap_{cap:g}_kw",
        "title": f"Maximaal {cap:g} kW",
        "cap_kw": cap,
    }


def _critical_quality_flags(rows: list[dict[str, Any]]) -> list[str]:
    flags = []
    for row in rows:
        for flag in row.get("quality_flags", []):
            if flag.startswith(("MISSING_", "STALE_", "INVALID_")):
                flags.append(flag)
        for key in (
            "start_utc",
            "duration_hours",
            "forecast_base_net_kwh",
            "import_rate_eur_per_kwh",
            "export_rate_eur_per_kwh",
        ):
            if row.get(key) is None:
                flags.append(f"MISSING_{key.upper()}")
    return sorted(set(flags))


def _sequence_is_contiguous(rows: list[dict[str, Any]]) -> bool:
    ordered = sorted(rows, key=lambda row: parse_instant(row["start_utc"]))
    return all(
        parse_instant(right["start_utc"]) - parse_instant(left["start_utc"])
        == timedelta(hours=float(left["duration_hours"]))
        for left, right in zip(ordered, ordered[1:])
    )


def _price_band(rate: float, ordered_rates: list[float]) -> str:
    low = ordered_rates[round((len(ordered_rates) - 1) * 0.25)]
    high = ordered_rates[round((len(ordered_rates) - 1) * 0.75)]
    if rate <= low:
        return "LOW_PRICE"
    if rate >= high:
        return "HIGH_PRICE"
    return "MID_PRICE"


def _optimise_policy(
    rows: list[dict[str, Any]],
    *,
    policy: dict[str, Any],
    battery: dict[str, Any],
    initial_soc_kwh: float,
    degradation_rate: float,
    state_step_kwh: float,
) -> dict[str, Any]:
    capacity = float(battery["usable_capacity_kwh"])
    charge_efficiency = float(battery["charge_efficiency"])
    discharge_efficiency = float(battery["discharge_efficiency"])
    max_charge_kw = float(battery["max_charge_power_kw"])
    max_discharge_kw = float(battery["max_discharge_power_kw"])
    peak_cap_kw = float(policy["cap_kw"])
    if capacity <= 0 or state_step_kwh <= 0:
        raise ValueError("Battery capacity and state step must be positive")
    if not 0 < charge_efficiency <= 1 or not 0 < discharge_efficiency <= 1:
        raise ValueError("Battery efficiencies must be in (0, 1]")

    level_count = max(2, round(capacity / state_step_kwh) + 1)
    step = capacity / (level_count - 1)
    initial_index = _nearest_state_index(initial_soc_kwh, step, level_count)
    terminal_index = initial_index
    infinite = float("inf")
    previous_cost = [infinite] * level_count
    previous_cost[initial_index] = 0.0
    backpointers: list[list[int]] = []

    for row in rows:
        duration = float(row["duration_hours"])
        current_cost = [infinite] * level_count
        current_previous = [-1] * level_count
        for before_index, accumulated in enumerate(previous_cost):
            if not math.isfinite(accumulated):
                continue
            before_energy = before_index * step
            minimum_after = max(
                0.0,
                before_energy
                - max_discharge_kw * duration / discharge_efficiency,
            )
            maximum_after = min(
                capacity,
                before_energy + max_charge_kw * duration * charge_efficiency,
            )
            minimum_index = math.ceil(minimum_after / step - 1e-12)
            maximum_index = math.floor(maximum_after / step + 1e-12)
            for after_index in range(minimum_index, maximum_index + 1):
                after_energy = after_index * step
                stored_delta = after_energy - before_energy
                charge = stored_delta / charge_efficiency if stored_delta > 0 else 0.0
                discharge = (
                    -stored_delta * discharge_efficiency if stored_delta < 0 else 0.0
                )
                base_net = float(row["forecast_base_net_kwh"])
                if discharge > max(0.0, base_net) + 1e-9:
                    continue
                net = base_net + charge - discharge
                if net > peak_cap_kw * duration + 1e-9:
                    continue
                interval_cost = grid_cost(
                    net,
                    float(row["import_rate_eur_per_kwh"]),
                    float(row["export_rate_eur_per_kwh"]),
                ) + discharge * degradation_rate
                candidate = accumulated + interval_cost
                if candidate < current_cost[after_index] - 1e-12:
                    current_cost[after_index] = candidate
                    current_previous[after_index] = before_index
                elif abs(candidate - current_cost[after_index]) <= 1e-12:
                    old_before = current_previous[after_index]
                    old_move = (
                        abs(after_index - old_before) if old_before >= 0 else math.inf
                    )
                    new_move = abs(after_index - before_index)
                    if new_move < old_move:
                        current_previous[after_index] = before_index
        if all(index < 0 for index in current_previous):
            return {
                **policy,
                "status": "NOT_FEASIBLE",
                "reason": "NO_FEASIBLE_STATE_TRANSITION",
                "schedule": [],
                "totals": {},
            }
        previous_cost = current_cost
        backpointers.append(current_previous)

    if not math.isfinite(previous_cost[terminal_index]):
        return {
            **policy,
            "status": "NOT_FEASIBLE",
            "reason": "TERMINAL_SOC_UNREACHABLE",
            "schedule": [],
            "totals": {},
        }

    state_path = [terminal_index]
    cursor = terminal_index
    for pointers in reversed(backpointers):
        cursor = pointers[cursor]
        if cursor < 0:
            raise ValueError("Shadow-plan path reconstruction failed")
        state_path.append(cursor)
    state_path.reverse()

    ordered_rates = sorted(float(row["import_rate_eur_per_kwh"]) for row in rows)
    schedule = []
    totals = defaultdict(float)
    baseline_cost = 0.0
    for index, row in enumerate(rows):
        before_energy = state_path[index] * step
        after_energy = state_path[index + 1] * step
        stored_delta = after_energy - before_energy
        charge = stored_delta / charge_efficiency if stored_delta > 0 else 0.0
        discharge = -stored_delta * discharge_efficiency if stored_delta < 0 else 0.0
        base_net = float(row["forecast_base_net_kwh"])
        net = base_net + charge - discharge
        duration = float(row["duration_hours"])
        import_rate = float(row["import_rate_eur_per_kwh"])
        export_rate = float(row["export_rate_eur_per_kwh"])
        band = _price_band(import_rate, ordered_rates)
        if charge > 1e-9:
            action = "STORE_PV_SURPLUS" if base_net < 0 else "CHARGE_FROM_GRID"
            reason = (
                "PV surplus is stored before export"
                if base_net < 0
                else f"{band}; shared-grid headroom remains below {peak_cap_kw:g} kW"
            )
        elif discharge > 1e-9:
            action = "DISCHARGE_TO_LOAD"
            reason = f"{band}; avoid forecast grid import without battery export"
        else:
            action = "HOLD"
            reason = f"{band}; no profitable battery movement after losses and degradation"
        added_grid_import = (
            max(0.0, max(0.0, net) - max(0.0, base_net))
            if charge > 1e-9
            else 0.0
        )
        energy_cost = grid_cost(net, import_rate, export_rate)
        degradation_cost = discharge * degradation_rate
        baseline_cost += grid_cost(base_net, import_rate, export_rate)
        totals["charge_kwh"] += charge
        totals["grid_charge_kwh"] += max(0.0, added_grid_import)
        totals["surplus_charge_kwh"] += max(0.0, charge - added_grid_import)
        totals["discharge_kwh"] += discharge
        totals["grid_import_kwh"] += max(0.0, net)
        totals["grid_export_kwh"] += max(0.0, -net)
        totals["grid_cost_eur"] += energy_cost
        totals["degradation_cost_eur"] += degradation_cost
        schedule.append(
            {
                **row,
                "action": action,
                "reason": reason,
                "charge_kwh": round(charge, 9),
                "discharge_kwh": round(discharge, 9),
                "soc_start_kwh": round(before_energy, 9),
                "soc_end_kwh": round(after_energy, 9),
                "planned_grid_import_kw": round(max(0.0, net) / duration, 9),
                "planned_grid_export_kw": round(max(0.0, -net) / duration, 9),
                "planned_grid_cost_eur": round(energy_cost, 9),
                "degradation_cost_eur": round(degradation_cost, 9),
            }
        )

    total_cost = totals["grid_cost_eur"] + totals["degradation_cost_eur"]
    return {
        **policy,
        "status": "PLANNED",
        "reason": "OPTIMISED_WITH_SHARED_GRID_CAP",
        "initial_soc_kwh": round(state_path[0] * step, 9),
        "terminal_soc_kwh": round(state_path[-1] * step, 9),
        "state_step_kwh": round(step, 9),
        "baseline_forecast_cost_eur": round(baseline_cost, 9),
        "planned_total_cost_eur": round(total_cost, 9),
        "forecast_saving_eur": round(baseline_cost - total_cost, 9),
        "totals": {key: round(value, 9) for key, value in totals.items()},
        "schedule": schedule,
    }


def build_shadow_plan(
    forecast_rows: list[dict[str, Any]],
    *,
    battery: dict[str, Any],
    initial_soc_kwh: float,
    degradation_rate: float,
    peak_caps_kw: Iterable[float | dict[str, Any]],
    expected_interval_count: int,
    state_step_kwh: float = 0.25,
) -> dict[str, Any]:
    ordered = sorted(forecast_rows, key=lambda row: parse_instant(row["start_utc"]))
    base = {
        "schema_version": 1,
        "mode": "READ_ONLY_SHADOW",
        "classification": "PROPOSED_PLAN_NO_CONTROL",
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "initial_soc_kwh": round(float(initial_soc_kwh), 6),
    }
    if len(ordered) != expected_interval_count or not _sequence_is_contiguous(ordered):
        return {
            **base,
            "status": "NO_ACTION",
            "reason": "INCOMPLETE_FORECAST_INTERVALS",
            "quality_flags": ["INCOMPLETE_FORECAST_INTERVALS"],
            "plans": [],
        }
    quality_flags = _critical_quality_flags(ordered)
    if quality_flags:
        return {
            **base,
            "status": "NO_ACTION",
            "reason": "UNUSABLE_OR_STALE_INPUT",
            "quality_flags": quality_flags,
            "plans": [],
        }
    capacity = float(battery["usable_capacity_kwh"])
    if not 0 <= initial_soc_kwh <= capacity:
        return {
            **base,
            "status": "NO_ACTION",
            "reason": "INITIAL_SOC_OUT_OF_RANGE",
            "quality_flags": ["INVALID_INITIAL_SOC"],
            "plans": [],
        }

    policies = [_normalise_policy(value) for value in peak_caps_kw]
    plans = [
        _optimise_policy(
            ordered,
            policy=policy,
            battery=battery,
            initial_soc_kwh=initial_soc_kwh,
            degradation_rate=degradation_rate,
            state_step_kwh=state_step_kwh,
        )
        for policy in policies
    ]
    feasible = [plan for plan in plans if plan["status"] == "PLANNED"]
    selected = min(
        feasible,
        key=lambda plan: (float(plan["planned_total_cost_eur"]), float(plan["cap_kw"])),
        default=None,
    )
    return {
        **base,
        "status": "PLANNED" if selected else "NO_ACTION",
        "reason": "SHADOW_PLAN_READY" if selected else "NO_FEASIBLE_POLICY",
        "target_start_utc": ordered[0]["start_utc"],
        "target_end_utc": (
            parse_instant(ordered[-1]["start_utc"])
            + timedelta(hours=float(ordered[-1]["duration_hours"]))
        ).isoformat(),
        "interval_count": len(ordered),
        "quality_flags": [],
        "selected_policy_id": selected["id"] if selected else None,
        "plans": plans,
    }


def evaluate_shadow_execution(
    planned_rows: list[dict[str, Any]],
    actual_rows: list[dict[str, Any]],
    *,
    battery: dict[str, Any],
    initial_soc_kwh: float,
    degradation_rate: float,
    peak_cap_kw: float,
) -> dict[str, Any]:
    if len(planned_rows) != len(actual_rows):
        raise ValueError("Planned and actual interval counts differ")
    capacity = float(battery["usable_capacity_kwh"])
    charge_efficiency = float(battery["charge_efficiency"])
    discharge_efficiency = float(battery["discharge_efficiency"])
    soc = float(initial_soc_kwh)
    schedule = []
    totals = defaultdict(float)
    baseline_cost = 0.0
    for planned, actual in zip(planned_rows, actual_rows):
        if parse_instant(planned["start_utc"]) != parse_instant(actual["start_utc"]):
            raise ValueError("Planned and actual timestamps differ")
        duration = float(actual["duration_hours"])
        base = float(actual["actual_base_net_kwh"])
        desired_charge = float(planned["charge_kwh"])
        desired_discharge = float(planned["discharge_kwh"])
        charge = min(
            desired_charge,
            float(battery["max_charge_power_kw"]) * duration,
            max(0.0, peak_cap_kw * duration - max(0.0, base)),
            max(0.0, (capacity - soc) / charge_efficiency),
        )
        discharge = min(
            desired_discharge,
            float(battery["max_discharge_power_kw"]) * duration,
            max(0.0, base + charge),
            soc * discharge_efficiency,
        )
        soc_start = soc
        soc = min(
            capacity,
            max(0.0, soc + charge * charge_efficiency - discharge / discharge_efficiency),
        )
        net = base + charge - discharge
        import_rate = float(actual["import_rate_eur_per_kwh"])
        export_rate = float(actual["export_rate_eur_per_kwh"])
        energy_cost = grid_cost(net, import_rate, export_rate)
        degradation_cost = discharge * degradation_rate
        baseline_cost += grid_cost(base, import_rate, export_rate)
        totals["charge_kwh"] += charge
        totals["discharge_kwh"] += discharge
        totals["grid_import_kwh"] += max(0.0, net)
        totals["grid_export_kwh"] += max(0.0, -net)
        totals["grid_cost_eur"] += energy_cost
        totals["degradation_cost_eur"] += degradation_cost
        schedule.append(
            {
                **actual,
                "planned_charge_kwh": desired_charge,
                "planned_discharge_kwh": desired_discharge,
                "executed_charge_kwh": charge,
                "executed_discharge_kwh": discharge,
                "curtailed_charge_kwh": desired_charge - charge,
                "curtailed_discharge_kwh": desired_discharge - discharge,
                "soc_start_kwh": soc_start,
                "soc_end_kwh": soc,
                "grid_import_kwh": max(0.0, net),
                "grid_export_kwh": max(0.0, -net),
                "grid_cost_eur": energy_cost,
                "degradation_cost_eur": degradation_cost,
            }
        )
    total_cost = totals["grid_cost_eur"] + totals["degradation_cost_eur"]
    return {
        "schedule": schedule,
        "totals": {key: round(value, 9) for key, value in totals.items()},
        "baseline_cost_eur": round(baseline_cost, 9),
        "shadow_total_cost_eur": round(total_cost, 9),
        "shadow_saving_eur": round(baseline_cost - total_cost, 9),
        "terminal_soc_kwh": round(soc, 9),
    }


def _load_multiyear_module() -> Any:
    path = ROOT / "scripts" / "analyze_multiyear_energy_battery.py"
    spec = importlib.util.spec_from_file_location("multiyear_shadow_source", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load multi-year analysis helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _target_instants(target: date, zone: ZoneInfo = ZONE) -> list[datetime]:
    start_local = datetime.combine(target, time.min, tzinfo=zone)
    end_local = datetime.combine(target + timedelta(days=1), time.min, tzinfo=zone)
    cursor = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    output = []
    while cursor < end_utc:
        output.append(cursor)
        cursor += QUARTER
    return output


def build_historical_forecast(
    fluvius_rows: list[dict[str, Any]],
    prices: dict[datetime, float],
    *,
    target_date: date,
    tariff: dict[str, Any],
    marginal_costs: dict[str, Any],
    lookback_days: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    module = _load_multiyear_module()
    target_instants = _target_instants(target_date)
    target_set = set(target_instants)
    history_start = target_date - timedelta(days=lookback_days)
    usable = [
        row
        for row in fluvius_rows
        if not row["unavailable"]
        and history_start <= row["start_local"].date() < target_date
    ]
    buckets: dict[tuple[str, bool], list[float]] = defaultdict(list)
    fallback: dict[str, list[float]] = defaultdict(list)
    for row in usable:
        key = row["start_local"].strftime("%H:%M")
        net = float(row["import_kwh"]) - float(row["export_kwh"])
        buckets[(key, row["start_local"].weekday() >= 5)].append(net)
        fallback[key].append(net)

    target_rows = {
        row["start_utc"]: row
        for row in fluvius_rows
        if row["start_utc"] in target_set and not row["unavailable"]
    }
    forecast = []
    actual = []
    is_weekend = target_date.weekday() >= 5
    for instant in target_instants:
        local = instant.astimezone(ZONE)
        key = local.strftime("%H:%M")
        candidates = buckets.get((key, is_weekend), [])
        if len(candidates) < 3:
            candidates = fallback.get(key, [])
        flags = []
        forecast_net = median(candidates) if candidates else None
        if forecast_net is None:
            flags.append("MISSING_BASE_LOAD_FORECAST")
        market_price = prices.get(instant)
        if market_price is None:
            flags.append("MISSING_DAY_AHEAD_PRICE")
            import_rate = export_rate = None
        else:
            import_rate, export_rate = module.dynamic_rates(
                market_price, tariff, marginal_costs
            )
        forecast.append(
            {
                "start_utc": instant.isoformat(),
                "start_local": local.isoformat(),
                "duration_hours": 0.25,
                "forecast_base_net_kwh": forecast_net,
                "market_price_eur_per_mwh": market_price,
                "import_rate_eur_per_kwh": import_rate,
                "export_rate_eur_per_kwh": export_rate,
                "forecast_method": "trailing same-quarter median residual grid profile",
                "forecast_sample_count": len(candidates),
                "quality_flags": flags,
            }
        )
        source = target_rows.get(instant)
        if source is not None and import_rate is not None and export_rate is not None:
            actual.append(
                {
                    "start_utc": instant.isoformat(),
                    "start_local": local.isoformat(),
                    "duration_hours": 0.25,
                    "actual_base_net_kwh": float(source["import_kwh"])
                    - float(source["export_kwh"]),
                    "import_rate_eur_per_kwh": import_rate,
                    "export_rate_eur_per_kwh": export_rate,
                }
            )

    prior_month = [
        row
        for row in usable
        if row["start_local"].year == target_date.year
        and row["start_local"].month == target_date.month
    ]
    month_peak_to_date = max(
        (
            max(0.0, float(row["import_kwh"]) - float(row["export_kwh"]))
            / float(row["duration_hours"])
            for row in prior_month
        ),
        default=0.0,
    )
    return forecast, actual, month_peak_to_date


def privacy_safe_summary(report: dict[str, Any]) -> dict[str, Any]:
    plans = []
    for plan in report.get("plans", []):
        plans.append(
            {
                key: value
                for key, value in plan.items()
                if key not in {"schedule"}
            }
        )
    selected = next(
        (plan for plan in report.get("plans", []) if plan["id"] == report.get("selected_policy_id")),
        None,
    )
    action_counts: dict[str, int] = defaultdict(int)
    if selected:
        for row in selected["schedule"]:
            action_counts[row["action"]] += 1
    return {
        key: value
        for key, value in report.items()
        if key not in {"plans", "actual_evaluations"}
    } | {
        "plans": plans,
        "selected_action_counts": dict(sorted(action_counts.items())),
        "actual_evaluations": report.get("actual_evaluations", {}),
        "privacy": {
            "quarter_household_profile_included": False,
            "device_identifiers_included": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fluvius", type=Path, required=True)
    parser.add_argument("--prices", type=Path, action="append", required=True)
    parser.add_argument("--dynamic-tariff", type=Path, required=True)
    parser.add_argument("--battery-config", type=Path, required=True)
    parser.add_argument("--marginal-costs", type=Path, required=True)
    parser.add_argument("--target-date", type=date.fromisoformat, required=True)
    parser.add_argument("--initial-soc-percent", type=float, default=50.0)
    parser.add_argument("--lookback-days", type=int, default=56)
    parser.add_argument("--state-step-kwh", type=float, default=0.25)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    args = parser.parse_args()

    module = _load_multiyear_module()
    fluvius = module.load_fluvius_intervals(args.fluvius)
    prices = module.load_price_map(args.prices)
    tariff = json.loads(args.dynamic_tariff.read_text(encoding="utf-8"))
    battery_config = json.loads(args.battery_config.read_text(encoding="utf-8"))
    battery = battery_config["battery"]
    marginal_costs = json.loads(args.marginal_costs.read_text(encoding="utf-8"))
    forecast, actual, month_peak = build_historical_forecast(
        fluvius,
        prices,
        target_date=args.target_date,
        tariff=tariff,
        marginal_costs=marginal_costs,
        lookback_days=args.lookback_days,
    )
    initial_soc = (
        float(battery["usable_capacity_kwh"]) * args.initial_soc_percent / 100
    )
    policies: list[dict[str, Any]] = [
        {
            "id": "peak_neutral",
            "title": "Piekneutraal",
            "cap_kw": month_peak,
        },
        {"id": "cap_7_kw", "title": "Absolute grens 7 kW", "cap_kw": 7.0},
        {"id": "cap_8_kw", "title": "Absolute grens 8 kW", "cap_kw": 8.0},
        {"id": "cap_10_kw", "title": "Absolute grens 10 kW", "cap_kw": 10.0},
    ]
    report = build_shadow_plan(
        forecast,
        battery=battery,
        initial_soc_kwh=initial_soc,
        degradation_rate=float(
            marginal_costs["central_degradation_eur_per_discharged_kwh"]
        ),
        peak_caps_kw=policies,
        expected_interval_count=len(_target_instants(args.target_date)),
        state_step_kwh=args.state_step_kwh,
    )
    report.update(
        {
            "target_date": args.target_date.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "forecast_method": "trailing same-quarter median of the residual Fluvius grid profile",
            "forecast_limitations": [
                "The residual Fluvius profile already includes historical installed-battery behavior.",
                "Separate interval PV, house, EV and heat-pump forecasts are not yet available.",
                "The historical validation run uses an assumed initial SOC because a target-time SOC snapshot is unavailable.",
            ],
            "month_peak_to_date_kw": round(month_peak, 6),
            "battery": {
                "usable_capacity_kwh": battery["usable_capacity_kwh"],
                "max_charge_power_kw": battery["max_charge_power_kw"],
                "max_discharge_power_kw": battery["max_discharge_power_kw"],
                "round_trip_efficiency": battery["round_trip_efficiency"],
                "initial_soc_percent": args.initial_soc_percent,
                "initial_soc_source": "ASSUMED_FOR_HISTORICAL_SHADOW_VALIDATION",
            },
        }
    )
    evaluations = {}
    if len(actual) == report.get("interval_count"):
        for plan in report.get("plans", []):
            if plan["status"] != "PLANNED":
                continue
            evaluations[plan["id"]] = {
                key: value
                for key, value in evaluate_shadow_execution(
                    plan["schedule"],
                    actual,
                    battery=battery,
                    initial_soc_kwh=initial_soc,
                    degradation_rate=float(
                        marginal_costs["central_degradation_eur_per_discharged_kwh"]
                    ),
                    peak_cap_kw=float(plan["cap_kw"]),
                ).items()
                if key != "schedule"
            }
    report["actual_evaluations"] = evaluations

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
                "target_date": report["target_date"],
                "selected_policy_id": report.get("selected_policy_id"),
                "output": str(args.output),
                "evidence_output": str(args.evidence_output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
