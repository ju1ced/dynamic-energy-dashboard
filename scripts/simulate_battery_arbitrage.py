#!/usr/bin/env python3
"""Offline battery dispatch backtest on validated Home Assistant hourly energy data."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
HOUR = timedelta(hours=1)


def parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp requires an offset: {value}")
    return parsed.astimezone(timezone.utc)


def reconstruct_base_net(
    *,
    grid_import_kwh: float,
    grid_export_kwh: float,
    battery_charge_kwh: float,
    battery_discharge_kwh: float,
) -> float:
    return (
        grid_import_kwh
        - grid_export_kwh
        - battery_charge_kwh
        + battery_discharge_kwh
    )


def grid_cost(net_kwh: float, import_rate: float, export_rate: float) -> float:
    if net_kwh >= 0:
        return net_kwh * import_rate
    return net_kwh * export_rate


def nearest_state_index(value: float, step: float, state_count: int) -> int:
    return min(state_count - 1, max(0, round(value / step)))


def optimize_segment(
    rows: list[dict[str, Any]],
    *,
    capacity_kwh: float,
    max_charge_kw: float,
    max_discharge_kw: float,
    charge_efficiency: float,
    discharge_efficiency: float,
    degradation_eur_per_discharged_kwh: float,
    state_step_kwh: float,
    initial_soc_kwh: float,
    terminal_soc_kwh: float,
    allow_battery_export: bool = True,
    max_grid_import_kw: float | None = None,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("Cannot optimize an empty segment")
    if capacity_kwh <= 0 or state_step_kwh <= 0:
        raise ValueError("Capacity and state step must be positive")
    if not 0 < charge_efficiency <= 1 or not 0 < discharge_efficiency <= 1:
        raise ValueError("Battery efficiencies must be in (0, 1]")

    level_count = max(2, round(capacity_kwh / state_step_kwh) + 1)
    step = capacity_kwh / (level_count - 1)
    initial_index = nearest_state_index(initial_soc_kwh, step, level_count)
    terminal_index = nearest_state_index(terminal_soc_kwh, step, level_count)
    infinite = float("inf")
    previous_cost = [infinite] * level_count
    previous_cost[initial_index] = 0.0
    backpointers: list[list[int]] = []

    max_stored_charge = max_charge_kw * charge_efficiency
    max_stored_discharge = max_discharge_kw / discharge_efficiency

    for row in rows:
        current_cost = [infinite] * level_count
        current_previous = [-1] * level_count
        for before_index, accumulated in enumerate(previous_cost):
            if not math.isfinite(accumulated):
                continue
            before_energy = before_index * step
            minimum_after = max(0.0, before_energy - max_stored_discharge)
            maximum_after = min(capacity_kwh, before_energy + max_stored_charge)
            minimum_index = math.ceil(minimum_after / step - 1e-12)
            maximum_index = math.floor(maximum_after / step + 1e-12)
            for after_index in range(minimum_index, maximum_index + 1):
                after_energy = after_index * step
                stored_delta = after_energy - before_energy
                charge_kwh = (
                    stored_delta / charge_efficiency if stored_delta > 0 else 0.0
                )
                discharge_kwh = (
                    -stored_delta * discharge_efficiency if stored_delta < 0 else 0.0
                )
                if charge_kwh > max_charge_kw + 1e-9 or discharge_kwh > max_discharge_kw + 1e-9:
                    continue
                if (
                    not allow_battery_export
                    and discharge_kwh > max(0.0, float(row["base_net_kwh"])) + 1e-9
                ):
                    continue
                net = float(row["base_net_kwh"]) + charge_kwh - discharge_kwh
                if max_grid_import_kw is not None and net > max_grid_import_kw + 1e-9:
                    continue
                interval_cost = grid_cost(
                    net,
                    float(row["import_rate"]),
                    float(row["export_rate"]),
                ) + discharge_kwh * degradation_eur_per_discharged_kwh
                candidate = accumulated + interval_cost
                if candidate < current_cost[after_index] - 1e-12:
                    current_cost[after_index] = candidate
                    current_previous[after_index] = before_index
                elif abs(candidate - current_cost[after_index]) <= 1e-12:
                    old_before = current_previous[after_index]
                    old_move = abs(after_index - old_before) if old_before >= 0 else math.inf
                    new_move = abs(after_index - before_index)
                    if new_move < old_move:
                        current_previous[after_index] = before_index
        if all(index < 0 for index in current_previous):
            raise ValueError("No feasible battery state transition")
        previous_cost = current_cost
        backpointers.append(current_previous)

    if not math.isfinite(previous_cost[terminal_index]):
        raise ValueError("Requested terminal SOC is unreachable")

    state_path = [terminal_index]
    cursor = terminal_index
    for pointers in reversed(backpointers):
        cursor = pointers[cursor]
        if cursor < 0:
            raise ValueError("Battery optimization path reconstruction failed")
        state_path.append(cursor)
    state_path.reverse()

    schedule = []
    totals = {
        "charge_kwh": 0.0,
        "discharge_kwh": 0.0,
        "grid_import_kwh": 0.0,
        "grid_export_kwh": 0.0,
        "grid_cost_eur": 0.0,
        "degradation_cost_eur": 0.0,
    }
    baseline_cost = 0.0
    for index, row in enumerate(rows):
        before_energy = state_path[index] * step
        after_energy = state_path[index + 1] * step
        stored_delta = after_energy - before_energy
        charge_kwh = stored_delta / charge_efficiency if stored_delta > 0 else 0.0
        discharge_kwh = -stored_delta * discharge_efficiency if stored_delta < 0 else 0.0
        net = float(row["base_net_kwh"]) + charge_kwh - discharge_kwh
        imported = max(0.0, net)
        exported = max(0.0, -net)
        energy_cost = grid_cost(net, float(row["import_rate"]), float(row["export_rate"]))
        degradation = discharge_kwh * degradation_eur_per_discharged_kwh
        baseline_cost += grid_cost(
            float(row["base_net_kwh"]),
            float(row["import_rate"]),
            float(row["export_rate"]),
        )
        values = {
            "charge_kwh": charge_kwh,
            "discharge_kwh": discharge_kwh,
            "grid_import_kwh": imported,
            "grid_export_kwh": exported,
            "grid_cost_eur": energy_cost,
            "degradation_cost_eur": degradation,
        }
        for key, value in values.items():
            totals[key] += value
        schedule.append(
            {
                **{key: value for key, value in row.items() if key not in {"forecast_base_net_kwh"}},
                "soc_start_kwh": before_energy,
                "soc_end_kwh": after_energy,
                **values,
            }
        )

    total_cost = totals["grid_cost_eur"] + totals["degradation_cost_eur"]
    return {
        "schedule": schedule,
        "totals": {key: round(value, 9) for key, value in totals.items()},
        "baseline_cost_eur": round(baseline_cost, 9),
        "total_cost_eur": round(total_cost, 9),
        "savings_eur": round(baseline_cost - total_cost, 9),
        "state_step_kwh": step,
        "initial_soc_kwh": state_path[0] * step,
        "terminal_soc_kwh": state_path[-1] * step,
    }


def load_price_map(paths: Iterable[Path]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload["intervals"]:
            key = parse_instant(row["start_utc"]).isoformat()
            value = float(row["price_eur_per_mwh"])
            if key in prices and prices[key] != value:
                raise ValueError(f"Conflicting market price at {key}")
            prices[key] = value
    if not prices:
        raise ValueError("No market prices loaded")
    return prices


def hourly_market_prices(quarter_prices: dict[str, float]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for timestamp, price in quarter_prices.items():
        instant = parse_instant(timestamp)
        hour = instant.replace(minute=0, second=0, microsecond=0).isoformat()
        grouped[hour].append(price)
    output = {}
    for hour, values in grouped.items():
        if len(values) != 4:
            continue
        output[hour] = fmean(values)
    return output


def load_hourly_rows(
    ha_path: Path,
    price_paths: list[Path],
    tariff: dict[str, Any],
    marginal_costs: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(ha_path.read_text(encoding="utf-8"))
    series = {
        name: {row["start_utc"]: row for row in values}
        for name, values in payload["series"].items()
    }
    required = [
        "grid_import",
        "grid_export",
        "battery_charge",
        "battery_discharge",
        "pv_generation",
    ]
    quarter_prices = load_price_map(price_paths)
    prices = hourly_market_prices(quarter_prices)
    adders = sum(
        float(value)
        for value in marginal_costs["import_variable_components_excl_vat_eur_per_kwh"].values()
    )
    vat = float(marginal_costs["vat_rate_import"])
    import_formula = tariff["import_energy"]
    export_formula = tariff["export_energy"]
    gsc = float(tariff["green_certificates_eur_per_kwh"])
    wkk = float(tariff["combined_heat_power_eur_per_kwh"])

    rows = []
    missing_by_reason = CounterLike()
    timestamps = sorted(series[required[0]], key=parse_instant)
    for timestamp in timestamps:
        values = {}
        unusable = False
        for name in required:
            row = series[name].get(timestamp)
            if row is None or row.get("energy_kwh") is None:
                missing_by_reason.increment(name)
                unusable = True
                break
            values[name] = float(row["energy_kwh"])
        hour = parse_instant(timestamp).replace(minute=0, second=0, microsecond=0).isoformat()
        if hour not in prices:
            missing_by_reason.increment("market_price")
            unusable = True
        if unusable:
            continue
        market_price = prices[hour]
        supplier_import = (
            float(import_formula["market_multiplier"]) * market_price
            + float(import_formula["offset_eur_per_kwh"])
        )
        import_rate = (supplier_import + gsc + wkk + adders) * (1 + vat)
        export_rate = (
            float(export_formula["market_multiplier"]) * market_price
            + float(export_formula["offset_eur_per_kwh"])
        )
        source_row = series["grid_import"][timestamp]
        rows.append(
            {
                "start_utc": hour,
                "start_local": source_row["start_local"],
                "month": source_row["start_local"][:7],
                "local_date": source_row["start_local"][:10],
                "local_hour": datetime.fromisoformat(source_row["start_local"]).hour,
                "grid_import_kwh": values["grid_import"],
                "grid_export_kwh": values["grid_export"],
                "actual_battery_charge_kwh": values["battery_charge"],
                "actual_battery_discharge_kwh": values["battery_discharge"],
                "pv_generation_kwh": values["pv_generation"],
                "base_net_kwh": reconstruct_base_net(
                    grid_import_kwh=values["grid_import"],
                    grid_export_kwh=values["grid_export"],
                    battery_charge_kwh=values["battery_charge"],
                    battery_discharge_kwh=values["battery_discharge"],
                ),
                "market_price_eur_per_mwh": market_price,
                "import_rate": import_rate,
                "export_rate": export_rate,
            }
        )
    return rows, {
        "source_hour_count": len(timestamps),
        "usable_hour_count": len(rows),
        "excluded_hour_count": len(timestamps) - len(rows),
        "missing_by_reason": missing_by_reason.values,
    }


class CounterLike:
    def __init__(self) -> None:
        self.values: dict[str, int] = defaultdict(int)

    def increment(self, key: str) -> None:
        self.values[key] += 1


def split_contiguous_month_segments(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    if not rows:
        return []
    ordered = sorted(rows, key=lambda row: parse_instant(row["start_utc"]))
    segments: list[list[dict[str, Any]]] = [[ordered[0]]]
    for row in ordered[1:]:
        previous = segments[-1][-1]
        contiguous = parse_instant(row["start_utc"]) - parse_instant(previous["start_utc"]) == HOUR
        if not contiguous or row["month"] != previous["month"]:
            segments.append([row])
        else:
            segments[-1].append(row)
    return segments


def execute_day_ahead_schedule(
    actual_rows: list[dict[str, Any]],
    schedule: list[dict[str, Any]],
    *,
    battery: dict[str, Any],
    starting_soc_kwh: float,
    degradation_rate: float,
    allow_battery_export: bool,
) -> dict[str, Any]:
    if len(actual_rows) != len(schedule):
        raise ValueError("Actual rows and schedule length differ")
    output = []
    soc = starting_soc_kwh
    capacity = float(battery["usable_capacity_kwh"])
    charge_efficiency = float(battery["charge_efficiency"])
    discharge_efficiency = float(battery["discharge_efficiency"])
    max_charge = float(battery["max_charge_power_kw"])
    max_discharge = float(battery["max_discharge_power_kw"])
    for actual, action in zip(actual_rows, schedule):
        desired_charge = float(action["charge_kwh"])
        desired_discharge = float(action["discharge_kwh"])
        charge = min(desired_charge, max_charge, (capacity - soc) / charge_efficiency)
        discharge = min(desired_discharge, max_discharge, soc * discharge_efficiency)
        if not allow_battery_export:
            discharge = min(discharge, max(0.0, float(actual["base_net_kwh"]) + charge))
        soc_start = soc
        soc = min(
            capacity,
            max(0.0, soc + charge * charge_efficiency - discharge / discharge_efficiency),
        )
        net = (
            float(actual["base_net_kwh"])
            + charge
            - discharge
        )
        energy_cost = grid_cost(net, float(actual["import_rate"]), float(actual["export_rate"]))
        output.append(
            {
                **actual,
                "charge_kwh": charge,
                "discharge_kwh": discharge,
                "curtailed_discharge_kwh": desired_discharge - discharge,
                "soc_start_kwh": soc_start,
                "soc_end_kwh": soc,
                "grid_import_kwh": max(0.0, net),
                "grid_export_kwh": max(0.0, -net),
                "grid_cost_eur": energy_cost,
                "degradation_cost_eur": discharge * degradation_rate,
            }
        )
    result = summarize_schedule(output)
    result["terminal_soc_kwh"] = soc
    return result


def summarize_schedule(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [
        "charge_kwh",
        "discharge_kwh",
        "grid_import_kwh",
        "grid_export_kwh",
        "grid_cost_eur",
        "degradation_cost_eur",
    ]
    totals = {key: sum(float(row[key]) for row in rows) for key in keys}
    return {"schedule": rows, "totals": totals}


def actual_baseline(rows: list[dict[str, Any]], degradation_rate: float) -> dict[str, Any]:
    grid_cost_total = sum(
        float(row["grid_import_kwh"]) * float(row["import_rate"])
        - float(row["grid_export_kwh"]) * float(row["export_rate"])
        for row in rows
    )
    discharge = sum(float(row["actual_battery_discharge_kwh"]) for row in rows)
    return {
        "grid_cost_eur": grid_cost_total,
        "degradation_cost_eur": discharge * degradation_rate,
        "discharge_kwh": discharge,
        "charge_kwh": sum(float(row["actual_battery_charge_kwh"]) for row in rows),
        "grid_import_kwh": sum(float(row["grid_import_kwh"]) for row in rows),
        "grid_export_kwh": sum(float(row["grid_export_kwh"]) for row in rows),
    }


def capacity_peak_delta_cost(
    baseline_rows: list[dict[str, Any]],
    simulated_rows: list[dict[str, Any]],
    annual_rate_excl_vat: float,
    vat_rate: float,
) -> tuple[float, list[dict[str, Any]]]:
    baseline_by_month: dict[str, list[float]] = defaultdict(list)
    simulated_by_month: dict[str, list[float]] = defaultdict(list)
    for row in baseline_rows:
        baseline_by_month[row["month"]].append(float(row["grid_import_kwh"]))
    for row in simulated_rows:
        simulated_by_month[row["month"]].append(float(row["grid_import_kwh"]))
    details = []
    total = 0.0
    for month in sorted(set(baseline_by_month) & set(simulated_by_month)):
        baseline_peak = max(baseline_by_month[month], default=0.0)
        simulated_peak = max(simulated_by_month[month], default=0.0)
        delta_cost = (simulated_peak - baseline_peak) * annual_rate_excl_vat / 12 * (1 + vat_rate)
        total += delta_cost
        details.append(
            {
                "month": month,
                "baseline_hourly_peak_kw": baseline_peak,
                "simulated_hourly_peak_kw": simulated_peak,
                "delta_cost_eur": delta_cost,
            }
        )
    return total, details


def run_perfect_foresight(
    rows: list[dict[str, Any]],
    battery: dict[str, Any],
    degradation_rate: float,
    marginal_costs: dict[str, Any],
    state_step_kwh: float,
    *,
    allow_battery_export: bool,
) -> dict[str, Any]:
    segments_by_month: dict[str, list[list[dict[str, Any]]]] = defaultdict(list)
    for segment in split_contiguous_month_segments(rows):
        segments_by_month[segment[0]["month"]].append(segment)

    schedule = []
    selected_peak_caps = []
    midpoint = float(battery["usable_capacity_kwh"]) / 2
    monthly_capacity_rate = (
        float(marginal_costs["capacity_tariff_eur_per_kw_year_excl_vat"])
        / 12
        * (1 + float(marginal_costs["vat_rate_import"]))
    )
    allowances = [
        float(value)
        for value in marginal_costs["perfect_foresight_peak_allowance_candidates_kw"]
    ]
    for month in sorted(segments_by_month):
        month_segments = segments_by_month[month]
        month_rows = [row for segment in month_segments for row in segment]
        baseline_peak = max(float(row["grid_import_kwh"]) for row in month_rows)
        best: dict[str, Any] | None = None
        for allowance in allowances:
            peak_cap = baseline_peak + allowance
            candidate_schedule = []
            try:
                for segment in month_segments:
                    result = optimize_segment(
                        segment,
                        capacity_kwh=float(battery["usable_capacity_kwh"]),
                        max_charge_kw=float(battery["max_charge_power_kw"]),
                        max_discharge_kw=float(battery["max_discharge_power_kw"]),
                        charge_efficiency=float(battery["charge_efficiency"]),
                        discharge_efficiency=float(battery["discharge_efficiency"]),
                        degradation_eur_per_discharged_kwh=degradation_rate,
                        state_step_kwh=state_step_kwh,
                        initial_soc_kwh=midpoint,
                        terminal_soc_kwh=midpoint,
                        allow_battery_export=allow_battery_export,
                        max_grid_import_kw=peak_cap,
                    )
                    candidate_schedule.extend(result["schedule"])
            except ValueError:
                continue
            candidate_totals = summarize_schedule(candidate_schedule)["totals"]
            simulated_peak = max(
                float(row["grid_import_kwh"]) for row in candidate_schedule
            )
            peak_cost = (simulated_peak - baseline_peak) * monthly_capacity_rate
            objective = (
                float(candidate_totals["grid_cost_eur"])
                + float(candidate_totals["degradation_cost_eur"])
                + peak_cost
            )
            candidate = {
                "schedule": candidate_schedule,
                "peak_cap_kw": peak_cap,
                "simulated_peak_kw": simulated_peak,
                "peak_delta_cost_eur": peak_cost,
                "objective_eur": objective,
            }
            if best is None or objective < float(best["objective_eur"]) - 1e-9:
                best = candidate
        if best is None:
            raise ValueError(f"No feasible perfect-foresight peak candidate for {month}")
        schedule.extend(best["schedule"])
        selected_peak_caps.append(
            {
                "month": month,
                "baseline_hourly_peak_kw": baseline_peak,
                "selected_peak_cap_kw": best["peak_cap_kw"],
                "simulated_hourly_peak_kw": best["simulated_peak_kw"],
                "peak_delta_cost_eur": best["peak_delta_cost_eur"],
            }
        )
    summarized = summarize_schedule(schedule)
    summarized["segment_count"] = len(split_contiguous_month_segments(rows))
    summarized["selected_peak_caps"] = selected_peak_caps
    return summarized


def run_day_ahead(
    rows: list[dict[str, Any]],
    battery: dict[str, Any],
    degradation_rate: float,
    marginal_costs: dict[str, Any],
    state_step_kwh: float,
) -> dict[str, Any]:
    _ = state_step_kwh
    ordered = sorted(rows, key=lambda row: parse_instant(row["start_utc"]))
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    monthly_baseline_peak: dict[str, float] = defaultdict(float)
    for row in ordered:
        by_day[row["local_date"]].append(row)
        monthly_baseline_peak[row["month"]] = max(
            monthly_baseline_peak[row["month"]], float(row["grid_import_kwh"])
        )
    applied = []
    skipped_days = []
    capacity = float(battery["usable_capacity_kwh"])
    midpoint = capacity / 2
    charge_efficiency = float(battery["charge_efficiency"])
    discharge_efficiency = float(battery["discharge_efficiency"])
    round_trip_efficiency = float(battery["round_trip_efficiency"])
    max_charge = float(battery["max_charge_power_kw"])
    max_discharge = float(battery["max_discharge_power_kw"])
    peak_allowance = float(marginal_costs["day_ahead_peak_allowance_kw"])
    current_soc: float | None = None
    previous_surplus_days: list[float] = []
    last_processed: datetime | None = None
    last_import_rate: float | None = None
    inventory_adjustment = 0.0

    def close_segment() -> None:
        nonlocal current_soc, inventory_adjustment
        if current_soc is None or last_import_rate is None:
            return
        if current_soc < midpoint:
            inventory_adjustment += (
                (midpoint - current_soc) / charge_efficiency * last_import_rate
            )
        else:
            inventory_adjustment -= (
                (current_soc - midpoint) * discharge_efficiency * last_import_rate
            )

    for day in sorted(by_day):
        actual_day = sorted(by_day[day], key=lambda row: parse_instant(row["start_utc"]))
        continuous = all(
            parse_instant(right["start_utc"]) - parse_instant(left["start_utc"]) == HOUR
            for left, right in zip(actual_day, actual_day[1:])
        )
        starts_after_gap = (
            last_processed is not None
            and parse_instant(actual_day[0]["start_utc"]) - last_processed != HOUR
        )
        if starts_after_gap:
            close_segment()
            current_soc = None
        if not continuous:
            skipped_days.append(day)
            close_segment()
            current_soc = None
            last_processed = parse_instant(actual_day[-1]["start_utc"])
            continue
        if current_soc is None:
            current_soc = midpoint
        sorted_rates = sorted(float(row["import_rate"]) for row in actual_day)
        low_rate = sorted_rates[round((len(sorted_rates) - 1) * 0.25)]
        high_rate = sorted_rates[round((len(sorted_rates) - 1) * 0.75)]
        forecast_surplus = (
            fmean(previous_surplus_days[-7:])
            if len(previous_surplus_days) >= 3
            else capacity * 0.30 / charge_efficiency
        )
        reserve_for_pv = min(capacity * 0.70, forecast_surplus * charge_efficiency)
        grid_charge_target_soc = capacity - reserve_for_pv
        daily_surplus = 0.0

        for index, row in enumerate(actual_day):
            base_net = float(row["base_net_kwh"])
            import_rate = float(row["import_rate"])
            export_rate = float(row["export_rate"])
            charge = 0.0
            discharge = 0.0
            soc_start = current_soc
            if base_net < 0:
                daily_surplus += -base_net
                charge = min(
                    -base_net,
                    max_charge,
                    (capacity - current_soc) / charge_efficiency,
                )
            elif import_rate >= high_rate:
                discharge = min(
                    base_net,
                    max_discharge,
                    current_soc * discharge_efficiency,
                )
            else:
                future_high = max(
                    float(item["import_rate"]) for item in actual_day[index:]
                )
                profitable_grid_charge = (
                    future_high * round_trip_efficiency
                    - import_rate
                    - degradation_rate * round_trip_efficiency
                    > 0
                )
                if (
                    import_rate <= low_rate
                    and profitable_grid_charge
                    and current_soc < grid_charge_target_soc
                ):
                    peak_cap = monthly_baseline_peak[row["month"]] + peak_allowance
                    charge = min(
                        max_charge,
                        max(0.0, peak_cap - base_net),
                        (grid_charge_target_soc - current_soc) / charge_efficiency,
                    )

            current_soc = min(
                capacity,
                max(
                    0.0,
                    current_soc
                    + charge * charge_efficiency
                    - discharge / discharge_efficiency,
                ),
            )
            net = base_net + charge - discharge
            applied.append(
                {
                    **row,
                    "charge_kwh": charge,
                    "discharge_kwh": discharge,
                    "soc_start_kwh": soc_start,
                    "soc_end_kwh": current_soc,
                    "grid_import_kwh": max(0.0, net),
                    "grid_export_kwh": max(0.0, -net),
                    "grid_cost_eur": grid_cost(net, import_rate, export_rate),
                    "degradation_cost_eur": discharge * degradation_rate,
                }
            )
            last_import_rate = import_rate
            last_processed = parse_instant(row["start_utc"])
        previous_surplus_days.append(daily_surplus)

    close_segment()
    summarized = summarize_schedule(applied)
    summarized["skipped_days"] = skipped_days
    summarized["simulated_day_count"] = len(by_day) - len(skipped_days)
    summarized["inventory_adjustment_eur"] = inventory_adjustment
    return summarized


def evaluate_strategy(
    strategy: dict[str, Any],
    source_rows: list[dict[str, Any]],
    degradation_rate: float,
    marginal_costs: dict[str, Any],
    battery: dict[str, Any],
) -> dict[str, Any]:
    schedule = strategy["schedule"]
    timestamps = {row["start_utc"] for row in schedule}
    comparable = [row for row in source_rows if row["start_utc"] in timestamps]
    baseline = actual_baseline(comparable, degradation_rate)
    peak_delta, peak_details = capacity_peak_delta_cost(
        comparable,
        schedule,
        float(marginal_costs["capacity_tariff_eur_per_kw_year_excl_vat"]),
        float(marginal_costs["vat_rate_import"]),
    )
    simulated_total = (
        float(strategy["totals"]["grid_cost_eur"])
        + float(strategy["totals"]["degradation_cost_eur"])
        + peak_delta
        + float(strategy.get("inventory_adjustment_eur", 0.0))
    )
    baseline_total = baseline["grid_cost_eur"] + baseline["degradation_cost_eur"]
    battery_discharge_to_export = sum(
        max(
            0.0,
            float(row["discharge_kwh"])
            - max(
                0.0,
                float(row["base_net_kwh"]) + float(row["charge_kwh"]),
            ),
        )
        for row in schedule
    )
    charge_efficiency = float(battery["charge_efficiency"])
    discharge_efficiency = float(battery["discharge_efficiency"])
    conversion_loss = (
        float(strategy["totals"]["charge_kwh"]) * (1 - charge_efficiency)
        + float(strategy["totals"]["discharge_kwh"])
        * (1 / discharge_efficiency - 1)
    )
    return {
        "hour_count": len(schedule),
        "baseline": {key: round(value, 9) for key, value in baseline.items()},
        "simulated": {key: round(value, 9) for key, value in strategy["totals"].items()},
        "capacity_peak_delta_eur": round(peak_delta, 9),
        "terminal_inventory_adjustment_eur": round(
            float(strategy.get("inventory_adjustment_eur", 0.0)), 9
        ),
        "capacity_peak_months": peak_details,
        "baseline_total_eur": round(baseline_total, 9),
        "simulated_total_eur": round(simulated_total, 9),
        "net_incremental_saving_eur": round(baseline_total - simulated_total, 9),
        "battery_discharge_to_export_kwh": round(battery_discharge_to_export, 9),
        "conversion_loss_kwh": round(conversion_loss, 9),
        "equivalent_full_cycles": round(
            float(strategy["totals"]["discharge_kwh"])
            / float(battery["usable_capacity_kwh"])
            if float(battery["usable_capacity_kwh"])
            else 0.0,
            9,
        ),
        "schedule": schedule,
        **{key: value for key, value in strategy.items() if key not in {"schedule", "totals"}},
    }


def result_without_schedule(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "schedule"}


def run_scenario(
    rows: list[dict[str, Any]],
    battery: dict[str, Any],
    degradation_rate: float,
    marginal_costs: dict[str, Any],
    state_step_kwh: float,
) -> dict[str, Any]:
    perfect_export_allowed = run_perfect_foresight(
        rows,
        battery,
        degradation_rate,
        marginal_costs,
        state_step_kwh,
        allow_battery_export=True,
    )
    perfect_self_consumption = run_perfect_foresight(
        rows,
        battery,
        degradation_rate,
        marginal_costs,
        state_step_kwh,
        allow_battery_export=False,
    )
    day_ahead = run_day_ahead(
        rows, battery, degradation_rate, marginal_costs, state_step_kwh
    )
    return {
        "degradation_eur_per_discharged_kwh": degradation_rate,
        "perfect_foresight_export_allowed": evaluate_strategy(
            perfect_export_allowed,
            rows,
            degradation_rate,
            marginal_costs,
            battery,
        ),
        "perfect_foresight_self_consumption": evaluate_strategy(
            perfect_self_consumption,
            rows,
            degradation_rate,
            marginal_costs,
            battery,
        ),
        "day_ahead": evaluate_strategy(
            day_ahead,
            rows,
            degradation_rate,
            marginal_costs,
            battery,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-hourly", type=Path, required=True)
    parser.add_argument("--prices", type=Path, action="append", required=True)
    parser.add_argument("--dynamic-tariff", type=Path, required=True)
    parser.add_argument("--battery-config", type=Path, required=True)
    parser.add_argument("--marginal-costs", type=Path, required=True)
    parser.add_argument("--state-step-kwh", type=float, default=0.25)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    tariff = json.loads(args.dynamic_tariff.read_text(encoding="utf-8"))
    battery_config = json.loads(args.battery_config.read_text(encoding="utf-8"))
    battery = battery_config["battery"]
    marginal_costs = json.loads(args.marginal_costs.read_text(encoding="utf-8"))
    rows, quality = load_hourly_rows(args.ha_hourly, args.prices, tariff, marginal_costs)

    sensitivity = []
    for degradation in marginal_costs["degradation_sensitivity_eur_per_discharged_kwh"]:
        scenario = run_scenario(
            rows,
            battery,
            float(degradation),
            marginal_costs,
            args.state_step_kwh,
        )
        sensitivity.append(
            {
                "degradation_eur_per_discharged_kwh": float(degradation),
                "perfect_foresight_export_allowed": result_without_schedule(
                    scenario["perfect_foresight_export_allowed"]
                ),
                "perfect_foresight_self_consumption": result_without_schedule(
                    scenario["perfect_foresight_self_consumption"]
                ),
                "day_ahead": result_without_schedule(scenario["day_ahead"]),
            }
        )

    central_degradation = float(
        marginal_costs["central_degradation_eur_per_discharged_kwh"]
    )
    base_central = run_scenario(
        rows, battery, central_degradation, marginal_costs, args.state_step_kwh
    )
    extra_capacity = []
    for additional in marginal_costs["additional_capacity_kwh"]:
        candidate = dict(battery)
        candidate["usable_capacity_kwh"] = float(battery["usable_capacity_kwh"]) + float(
            additional
        )
        scenario = run_scenario(
            rows,
            candidate,
            central_degradation,
            marginal_costs,
            args.state_step_kwh,
        )
        observed_days = (
            parse_instant(rows[-1]["start_utc"]) + HOUR - parse_instant(rows[0]["start_utc"])
        ).total_seconds() / 86400
        annual_factor = 365 / observed_days
        perfect_marginal = (
            scenario["perfect_foresight_export_allowed"]["net_incremental_saving_eur"]
            - base_central["perfect_foresight_export_allowed"][
                "net_incremental_saving_eur"
            ]
        )
        perfect_self_consumption_marginal = (
            scenario["perfect_foresight_self_consumption"][
                "net_incremental_saving_eur"
            ]
            - base_central["perfect_foresight_self_consumption"][
                "net_incremental_saving_eur"
            ]
        )
        day_ahead_marginal = (
            scenario["day_ahead"]["net_incremental_saving_eur"]
            - base_central["day_ahead"]["net_incremental_saving_eur"]
        )
        perfect_annualized = perfect_marginal * annual_factor
        perfect_self_consumption_annualized = (
            perfect_self_consumption_marginal * annual_factor
        )
        day_ahead_annualized = day_ahead_marginal * annual_factor
        realistic_case_supported = (
            float(base_central["day_ahead"]["net_incremental_saving_eur"]) > 0
            and float(scenario["day_ahead"]["net_incremental_saving_eur"])
            > float(base_central["day_ahead"]["net_incremental_saving_eur"])
        )
        extra_capacity.append(
            {
                "additional_usable_capacity_kwh": float(additional),
                "total_usable_capacity_kwh": candidate["usable_capacity_kwh"],
                "power_limit_kw": candidate["max_charge_power_kw"],
                "perfect_foresight_marginal_saving_observed_period_eur": round(
                    perfect_marginal, 9
                ),
                "perfect_foresight_marginal_saving_annualized_eur": round(
                    perfect_annualized, 9
                ),
                "perfect_foresight_upper_bound_installed_cost_10y_eur": round(
                    max(0.0, perfect_annualized * 10), 2
                ),
                "perfect_foresight_upper_bound_installed_cost_15y_eur": round(
                    max(0.0, perfect_annualized * 15), 2
                ),
                "perfect_self_consumption_marginal_saving_observed_period_eur": round(
                    perfect_self_consumption_marginal, 9
                ),
                "perfect_self_consumption_marginal_saving_annualized_eur": round(
                    perfect_self_consumption_annualized, 9
                ),
                "perfect_self_consumption_upper_bound_installed_cost_10y_eur": round(
                    max(0.0, perfect_self_consumption_annualized * 10), 2
                ),
                "perfect_self_consumption_upper_bound_installed_cost_15y_eur": round(
                    max(0.0, perfect_self_consumption_annualized * 15), 2
                ),
                "day_ahead_marginal_saving_observed_period_eur": round(
                    day_ahead_marginal, 9
                ),
                "day_ahead_marginal_saving_annualized_eur": round(
                    day_ahead_annualized, 9
                ),
                "day_ahead_existing_capacity_net_saving_eur": round(
                    float(base_central["day_ahead"]["net_incremental_saving_eur"]), 9
                ),
                "day_ahead_candidate_total_net_saving_eur": round(
                    float(scenario["day_ahead"]["net_incremental_saving_eur"]), 9
                ),
                "realistic_investment_case_supported": realistic_case_supported,
                "simple_break_even_installed_cost_10y_eur": round(
                    max(0.0, day_ahead_annualized * 10)
                    if realistic_case_supported
                    else 0.0,
                    2,
                ),
                "simple_break_even_installed_cost_15y_eur": round(
                    max(0.0, day_ahead_annualized * 15)
                    if realistic_case_supported
                    else 0.0,
                    2,
                ),
            }
        )

    report = {
        "schema_version": 2,
        "scenario": "offline_battery_arbitrage_hourly",
        "period_start_utc": rows[0]["start_utc"],
        "period_end_utc": (parse_instant(rows[-1]["start_utc"]) + HOUR).isoformat(),
        "model": {
            "read_only": True,
            "physical_writes": False,
            "resolution_minutes": 60,
            "base_net_reconstruction": "grid_import - grid_export - actual_battery_charge + actual_battery_discharge",
            "perfect_foresight_horizon": "contiguous calendar-month segments with monthly peak-cap candidates",
            "perfect_foresight_variants": [
                "battery export allowed",
                "self-consumption only; battery discharge may not create grid export",
            ],
            "day_ahead_strategy": "day-ahead price quartiles plus a trailing seven-day PV-surplus reserve and real-time self-consumption",
            "day_ahead_terminal_soc": "SOC carries across contiguous hours; segment-end inventory is valued at the final import rate",
            "day_ahead_battery_export": "disabled",
            "capacity_peak": marginal_costs["capacity_tariff_method"],
            "additional_capacity_power_assumption": marginal_costs[
                "additional_capacity_power_assumption"
            ],
            "state_step_requested_kwh": args.state_step_kwh,
        },
        "battery": battery,
        "quality": quality,
        "degradation_sensitivity": sensitivity,
        "central_degradation": {
            "rate_eur_per_discharged_kwh": central_degradation,
            "perfect_foresight_export_allowed": result_without_schedule(
                base_central["perfect_foresight_export_allowed"]
            ),
            "perfect_foresight_self_consumption": result_without_schedule(
                base_central["perfect_foresight_self_consumption"]
            ),
            "day_ahead": result_without_schedule(base_central["day_ahead"]),
        },
        "additional_capacity": extra_capacity,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "degradation_sensitivity"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
