#!/usr/bin/env python3
"""Build a privacy-safe three-year energy and residual-battery comparison."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ZONE = ZoneInfo("Europe/Brussels")
QUARTER = timedelta(minutes=15)
SUNNY_ENERGY_COLUMNS = {
    "Totale opwekking [kWh]": "pv_generation_kwh",
    "Totaalverbruik [kWh]": "total_consumption_kwh",
    "Direct verbruik [kWh]": "direct_consumption_kwh",
    "Teruglevering [kWh]": "grid_export_kwh",
    "Netafname [kWh]": "grid_import_kwh",
    "Lading batterijsysteem [kWh]": "battery_charge_kwh",
    "Ontlading batterijsysteem [kWh]": "battery_discharge_kwh",
}
SUNNY_POWER_COLUMNS = {
    "Totale opwekking [kW]": "pv_generation_kw",
    "Totaalverbruik [kW]": "total_consumption_kw",
    "Direct verbruik [kW]": "direct_consumption_kw",
    "Teruglevering [kW]": "grid_export_kw",
    "Netafname [kW]": "grid_import_kw",
    "Lading batterijsysteem [kW]": "battery_charge_kw",
    "Ontlading batterijsysteem [kW]": "battery_discharge_kw",
    "Laadtoestand van de batterij [%]": "battery_soc_percent",
}


def parse_number(value: str) -> float | None:
    stripped = value.strip()
    if stripped in {"", "-", "—"}:
        return None
    return float(stripped.replace(".", "").replace(",", "."))


def csv_rows_after_separator(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        first = handle.readline()
        if not first.casefold().startswith("sep="):
            handle.seek(0)
        return list(csv.DictReader(handle, delimiter=";"))


def load_sunny_energy_files(paths: Iterable[Path]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[date] = set()
    for path in sorted(paths):
        for source in csv_rows_after_separator(path):
            day = datetime.strptime(source["Periode"], "%d-%m-%Y").date()
            if day in seen:
                raise ValueError(f"Duplicate Sunny Portal energy date: {day}")
            seen.add(day)
            output.append(
                {
                    "date": day,
                    **{
                        target: parse_number(source[source_name])
                        for source_name, target in SUNNY_ENERGY_COLUMNS.items()
                    },
                }
            )
    return sorted(output, key=lambda row: row["date"])


def load_sunny_power_files(
    paths: Iterable[Path],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output: list[dict[str, Any]] = []
    per_file: list[dict[str, Any]] = []
    all_local_timestamps: list[datetime] = []
    for path in sorted(paths):
        file_rows: list[dict[str, Any]] = []
        for source in csv_rows_after_separator(path):
            timestamp = datetime.strptime(source["Periode"], "%d-%m-%Y %H:%M:%S")
            file_rows.append(
                {
                    "timestamp_local": timestamp,
                    **{
                        target: parse_number(source[source_name])
                        for source_name, target in SUNNY_POWER_COLUMNS.items()
                    },
                }
            )
        if not file_rows:
            continue
        timestamps = [row["timestamp_local"] for row in file_rows]
        differences = [
            int((right - left).total_seconds() / 60)
            for left, right in zip(timestamps, timestamps[1:])
        ]
        positive = [difference for difference in differences if difference > 0]
        cadence = Counter(positive).most_common(1)[0][0] if positive else None
        for index, row in enumerate(file_rows):
            candidate = differences[index] if index < len(differences) else cadence
            duration_minutes = candidate if candidate in {5, 15} else cadence
            row["duration_hours"] = duration_minutes / 60 if duration_minutes else None
        per_file.append(
            {
                "period": timestamps[0].strftime("%Y-%m"),
                "start_local": timestamps[0].isoformat(),
                "end_local": timestamps[-1].isoformat(),
                "row_count": len(file_rows),
                "dominant_cadence_minutes": cadence,
                "cadence_counts": {
                    str(key): value for key, value in sorted(Counter(differences).items())
                },
                "duplicate_local_timestamp_count": len(timestamps) - len(set(timestamps)),
                "missing_value_counts": {
                    field: sum(row[field] is None for row in file_rows)
                    for field in SUNNY_POWER_COLUMNS.values()
                },
            }
        )
        output.extend(file_rows)
        all_local_timestamps.extend(timestamps)
    return output, {
        "file_count": len(per_file),
        "row_count": len(output),
        "period_start_local": min(all_local_timestamps).isoformat()
        if all_local_timestamps
        else None,
        "period_end_local": max(all_local_timestamps).isoformat()
        if all_local_timestamps
        else None,
        "duplicate_local_timestamp_count": len(all_local_timestamps)
        - len(set(all_local_timestamps)),
        "files": per_file,
    }


def summarize_sunny_power_dispatch(rows: list[dict[str, Any]]) -> dict[str, Any]:
    monthly: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    skipped = 0
    for row in rows:
        required = (
            "duration_hours",
            "battery_charge_kw",
            "battery_discharge_kw",
            "pv_generation_kw",
            "total_consumption_kw",
            "grid_import_kw",
        )
        if any(row.get(field) is None for field in required):
            skipped += 1
            continue
        duration = float(row["duration_hours"])
        charge = float(row["battery_charge_kw"])
        discharge = float(row["battery_discharge_kw"])
        pv_generation = float(row["pv_generation_kw"])
        consumption = float(row["total_consumption_kw"])
        grid_import = float(row["grid_import_kw"])
        pv_surplus = max(0.0, pv_generation - consumption)
        estimated_grid_charge = min(
            grid_import, max(0.0, charge - pv_surplus)
        )
        month = row["timestamp_local"].strftime("%Y-%m")
        values = monthly[month]
        values["battery_charge_kwh"] += charge * duration
        values["battery_discharge_kwh"] += discharge * duration
        values["estimated_grid_charge_kwh"] += estimated_grid_charge * duration
    total = {
        key: sum(values[key] for values in monthly.values())
        for key in (
            "battery_charge_kwh",
            "battery_discharge_kwh",
            "estimated_grid_charge_kwh",
        )
    }
    return {
        "method": "INFERRED: grid-supplied battery charge is limited by simultaneous grid import after available PV surplus",
        "skipped_row_count": skipped,
        "total": {key: round(value, 6) for key, value in total.items()},
        "monthly": [
            {
                "month": month,
                **{key: round(value, 6) for key, value in values.items()},
            }
            for month, values in sorted(monthly.items())
        ],
    }


def local_interval_utc_candidates(
    local_start: datetime, local_end: datetime
) -> list[datetime]:
    candidates: set[datetime] = set()
    for fold in (0, 1):
        utc_start = local_start.replace(tzinfo=ZONE, fold=fold).astimezone(timezone.utc)
        if (
            utc_start.astimezone(ZONE).replace(tzinfo=None) == local_start
            and (utc_start + QUARTER).astimezone(ZONE).replace(tzinfo=None)
            == local_end
        ):
            candidates.add(utc_start)
    return sorted(candidates)


def load_fluvius_intervals(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    if len(rows) % 2:
        raise ValueError("Fluvius CSV has an odd row count")

    intervals: list[dict[str, Any]] = []
    used_utc: set[datetime] = set()
    for offset in range(0, len(rows), 2):
        pair = rows[offset : offset + 2]
        local_start = datetime.strptime(
            f"{pair[0]['Van (datum)']} {pair[0]['Van (tijdstip)']}",
            "%d-%m-%Y %H:%M:%S",
        )
        local_end = datetime.strptime(
            f"{pair[0]['Tot (datum)']} {pair[0]['Tot (tijdstip)']}",
            "%d-%m-%Y %H:%M:%S",
        )
        candidates = [
            candidate
            for candidate in local_interval_utc_candidates(local_start, local_end)
            if candidate not in used_utc
        ]
        if not candidates:
            raise ValueError(f"No unique UTC mapping for Fluvius interval {local_start}")
        utc_start = candidates[0]
        used_utc.add(utc_start)
        values: dict[str, float | None] = {"import_kwh": 0.0, "export_kwh": 0.0}
        estimated = False
        unavailable = False
        flows: set[str] = set()
        for item in pair:
            register = item["Register"].casefold()
            if register.startswith("afname"):
                field = "import_kwh"
                flows.add("import")
            elif register.startswith("injectie"):
                field = "export_kwh"
                flows.add("export")
            else:
                continue
            volume = parse_number(item["Volume"])
            if volume is None:
                values[field] = None
                unavailable = True
            else:
                values[field] = volume
            estimated = estimated or item["Validatiestatus"].casefold() == "geschat"
        if flows != {"import", "export"}:
            raise ValueError(f"Incomplete Fluvius flow pair at {local_start}")
        aware_local = utc_start.astimezone(ZONE)
        intervals.append(
            {
                "start_utc": utc_start,
                "start_local": aware_local,
                "import_kwh": values["import_kwh"],
                "export_kwh": values["export_kwh"],
                "estimated": estimated,
                "unavailable": unavailable,
                "duration_hours": 0.25,
            }
        )
    return sorted(intervals, key=lambda row: row["start_utc"])


def load_price_map(paths: Iterable[Path]) -> dict[datetime, float]:
    output: dict[datetime, float] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload["intervals"]:
            instant = datetime.fromisoformat(row["start_utc"]).astimezone(timezone.utc)
            price = float(row["price_eur_per_mwh"])
            if instant in output and output[instant] != price:
                raise ValueError(f"Conflicting price at {instant.isoformat()}")
            output[instant] = price
    return output


def dynamic_rate_components(
    market_price_eur_per_mwh: float,
    tariff: dict[str, Any],
    marginal_costs: dict[str, Any],
) -> dict[str, float]:
    import_formula = tariff["import_energy"]
    export_formula = tariff["export_energy"]
    supplier_import = (
        float(import_formula["market_multiplier"]) * market_price_eur_per_mwh
        + float(import_formula["offset_eur_per_kwh"])
    )
    green_certificates = float(tariff["green_certificates_eur_per_kwh"])
    combined_heat_power = float(tariff["combined_heat_power_eur_per_kwh"])
    grid_and_tax = sum(
        float(value)
        for value in marginal_costs[
            "import_variable_components_excl_vat_eur_per_kwh"
        ].values()
    )
    import_excl_vat = (
        supplier_import + green_certificates + combined_heat_power + grid_and_tax
    )
    import_vat = import_excl_vat * float(marginal_costs["vat_rate_import"])
    export_total = (
        float(export_formula["market_multiplier"]) * market_price_eur_per_mwh
        + float(export_formula["offset_eur_per_kwh"])
    )
    return {
        "supplier_import_energy_excl_vat": supplier_import,
        "green_certificates_excl_vat": green_certificates,
        "combined_heat_power_excl_vat": combined_heat_power,
        "grid_and_tax_excl_vat": grid_and_tax,
        "import_vat": import_vat,
        "import_total_incl_vat": import_excl_vat + import_vat,
        "export_total": export_total,
    }


def dynamic_rates(
    market_price_eur_per_mwh: float,
    tariff: dict[str, Any],
    marginal_costs: dict[str, Any],
) -> tuple[float, float]:
    components = dynamic_rate_components(
        market_price_eur_per_mwh, tariff, marginal_costs
    )
    return components["import_total_incl_vat"], components["export_total"]


def grid_cost(net_kwh: float, import_rate: float, export_rate: float) -> float:
    return net_kwh * (import_rate if net_kwh >= 0 else export_rate)


def nearest_state_index(value: float, step: float, count: int) -> int:
    return min(count - 1, max(0, round(value / step)))


def optimize_residual_segment(
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
    allow_grid_charge: bool,
    allow_battery_export: bool,
    max_grid_import_kw: float | None = None,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("Cannot optimize an empty segment")
    state_count = max(2, round(capacity_kwh / state_step_kwh) + 1)
    step = capacity_kwh / (state_count - 1)
    initial_index = nearest_state_index(initial_soc_kwh, step, state_count)
    terminal_index = nearest_state_index(terminal_soc_kwh, step, state_count)
    previous = [math.inf] * state_count
    previous[initial_index] = 0.0
    pointers: list[list[int]] = []

    for row in rows:
        duration = float(row.get("duration_hours", 1.0))
        maximum_stored_charge = max_charge_kw * duration * charge_efficiency
        maximum_stored_discharge = max_discharge_kw * duration / discharge_efficiency
        current = [math.inf] * state_count
        current_pointer = [-1] * state_count
        for before_index, accumulated in enumerate(previous):
            if not math.isfinite(accumulated):
                continue
            before = before_index * step
            minimum_after = max(0.0, before - maximum_stored_discharge)
            maximum_after = min(capacity_kwh, before + maximum_stored_charge)
            low = math.ceil(minimum_after / step - 1e-12)
            high = math.floor(maximum_after / step + 1e-12)
            for after_index in range(low, high + 1):
                after = after_index * step
                stored_delta = after - before
                charge = stored_delta / charge_efficiency if stored_delta > 0 else 0.0
                discharge = (
                    -stored_delta * discharge_efficiency if stored_delta < 0 else 0.0
                )
                base_net = float(row["base_net_kwh"])
                if not allow_grid_charge and charge > max(0.0, -base_net) + 1e-9:
                    continue
                if (
                    not allow_battery_export
                    and discharge > max(0.0, base_net + charge) + 1e-9
                ):
                    continue
                net = base_net + charge - discharge
                if (
                    max_grid_import_kw is not None
                    and net / duration > max_grid_import_kw + 1e-9
                ):
                    continue
                candidate = (
                    accumulated
                    + grid_cost(net, float(row["import_rate"]), float(row["export_rate"]))
                    + discharge * degradation_eur_per_discharged_kwh
                )
                if candidate < current[after_index] - 1e-12:
                    current[after_index] = candidate
                    current_pointer[after_index] = before_index
                elif abs(candidate - current[after_index]) <= 1e-12:
                    old = current_pointer[after_index]
                    if old < 0 or abs(after_index - before_index) < abs(after_index - old):
                        current_pointer[after_index] = before_index
        if all(index < 0 for index in current_pointer):
            raise ValueError("No feasible residual-battery transition")
        previous = current
        pointers.append(current_pointer)

    if not math.isfinite(previous[terminal_index]):
        raise ValueError("Residual-battery terminal SOC is unreachable")
    state_path = [terminal_index]
    cursor = terminal_index
    for interval_pointers in reversed(pointers):
        cursor = interval_pointers[cursor]
        if cursor < 0:
            raise ValueError("Residual-battery path reconstruction failed")
        state_path.append(cursor)
    state_path.reverse()

    schedule: list[dict[str, Any]] = []
    totals: dict[str, float] = defaultdict(float)
    baseline_cost = 0.0
    for index, row in enumerate(rows):
        before = state_path[index] * step
        after = state_path[index + 1] * step
        stored_delta = after - before
        charge = stored_delta / charge_efficiency if stored_delta > 0 else 0.0
        discharge = -stored_delta * discharge_efficiency if stored_delta < 0 else 0.0
        base_net = float(row["base_net_kwh"])
        net = base_net + charge - discharge
        imported = max(0.0, net)
        exported = max(0.0, -net)
        pv_surplus = max(0.0, -base_net)
        values = {
            "charge_kwh": charge,
            "discharge_kwh": discharge,
            "grid_charge_kwh": max(0.0, charge - pv_surplus),
            "surplus_charge_kwh": min(charge, pv_surplus),
            "grid_import_kwh": imported,
            "grid_export_kwh": exported,
            "grid_cost_eur": grid_cost(
                net, float(row["import_rate"]), float(row["export_rate"])
            ),
            "degradation_cost_eur": discharge
            * degradation_eur_per_discharged_kwh,
        }
        baseline_cost += grid_cost(
            base_net, float(row["import_rate"]), float(row["export_rate"])
        )
        for key, value in values.items():
            totals[key] += value
        schedule.append({**row, **values, "soc_start_kwh": before, "soc_end_kwh": after})
    total_cost = totals["grid_cost_eur"] + totals["degradation_cost_eur"]
    return {
        "schedule": schedule,
        "totals": dict(totals),
        "baseline_cost_eur": baseline_cost,
        "total_cost_eur": total_cost,
        "savings_eur": baseline_cost - total_cost,
        "state_step_kwh": step,
    }


def analysis_year(local_timestamp: datetime) -> str:
    start_year = (
        local_timestamp.year if local_timestamp.month >= 10 else local_timestamp.year - 1
    )
    return f"{start_year}-{start_year + 1}"


def year_bounds(label: str) -> tuple[datetime, datetime]:
    start_year = int(label.split("-")[0])
    return (
        datetime(start_year, 10, 1, tzinfo=ZONE),
        datetime(start_year + 1, 10, 1, tzinfo=ZONE),
    )


def split_contiguous_month_segments(
    rows: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    if not rows:
        return []
    ordered = sorted(rows, key=lambda row: row["start_utc"])
    segments = [[ordered[0]]]
    for row in ordered[1:]:
        previous = segments[-1][-1]
        contiguous = row["start_utc"] - previous["start_utc"] == QUARTER
        same_month = row["start_local"].strftime("%Y-%m") == previous[
            "start_local"
        ].strftime("%Y-%m")
        if contiguous and same_month:
            segments[-1].append(row)
        else:
            segments.append([row])
    return segments


def summarize_peak_exposure(
    rows: list[dict[str, Any]], cap_kw: float
) -> dict[str, Any]:
    powers = [
        max(0.0, float(row["base_net_kwh"]))
        / float(row.get("duration_hours", 0.25))
        for row in rows
    ]
    excess = [max(0.0, power - cap_kw) for power in powers]
    return {
        "cap_kw": cap_kw,
        "observed_peak_kw": round(max(powers, default=0.0), 6),
        "quarter_count_above_cap": sum(value > 1e-9 for value in excess),
        "maximum_excess_kw": round(max(excess, default=0.0), 6),
        "excess_energy_kwh": round(
            sum(
                value * float(row.get("duration_hours", 0.25))
                for value, row in zip(excess, rows)
            ),
            6,
        ),
    }


def classify_scenario_option(
    *,
    average_net_value_eur: float | None,
    feasible_year_count: int,
    requires_new_hardware: bool,
    data_complete: bool,
) -> str:
    if not data_complete:
        return "DATA_GATED"
    if feasible_year_count == 0:
        return "NOT_FEASIBLE"
    if requires_new_hardware:
        return "INVESTMENT_CASE_REQUIRED"
    if average_net_value_eur is not None and average_net_value_eur > 0:
        return "OPTION"
    return "LOW_VALUE"


def simulate_residual_year(
    rows: list[dict[str, Any]],
    *,
    capacity_kwh: float,
    battery: dict[str, Any],
    marginal_costs: dict[str, Any],
    allow_grid_charge: bool,
    state_step_kwh: float,
    absolute_peak_kw: float | None = None,
    allow_battery_export: bool = False,
    peak_allowance_kw: float | None = None,
) -> dict[str, Any]:
    midpoint = capacity_kwh / 2
    schedule: list[dict[str, Any]] = []
    segment_count = 0
    for segment in split_contiguous_month_segments(rows):
        month_rows = [
            row
            for row in rows
            if row["start_local"].strftime("%Y-%m")
            == segment[0]["start_local"].strftime("%Y-%m")
        ]
        baseline_peak_kw = max(
            max(0.0, float(row["base_net_kwh"]))
            / float(row["duration_hours"])
            for row in month_rows
        )
        peak_cap_kw = (
            absolute_peak_kw
            if absolute_peak_kw is not None
            else baseline_peak_kw
            + (
                float(peak_allowance_kw)
                if peak_allowance_kw is not None
                else float(marginal_costs["day_ahead_peak_allowance_kw"])
            )
        )
        result = optimize_residual_segment(
            segment,
            capacity_kwh=capacity_kwh,
            max_charge_kw=float(battery["max_charge_power_kw"]),
            max_discharge_kw=float(battery["max_discharge_power_kw"]),
            charge_efficiency=float(battery["charge_efficiency"]),
            discharge_efficiency=float(battery["discharge_efficiency"]),
            degradation_eur_per_discharged_kwh=float(
                marginal_costs["central_degradation_eur_per_discharged_kwh"]
            ),
            state_step_kwh=state_step_kwh,
            initial_soc_kwh=midpoint,
            terminal_soc_kwh=midpoint,
            allow_grid_charge=allow_grid_charge,
            allow_battery_export=allow_battery_export,
            max_grid_import_kw=peak_cap_kw,
        )
        schedule.extend(result["schedule"])
        segment_count += 1

    totals: dict[str, float] = defaultdict(float)
    for row in schedule:
        for key in (
            "charge_kwh",
            "discharge_kwh",
            "grid_charge_kwh",
            "surplus_charge_kwh",
            "grid_import_kwh",
            "grid_export_kwh",
            "grid_cost_eur",
            "degradation_cost_eur",
        ):
            totals[key] += float(row[key])
    source_by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    simulated_by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source_by_month[row["start_local"].strftime("%Y-%m")].append(row)
    for row in schedule:
        simulated_by_month[row["start_local"].strftime("%Y-%m")].append(row)
    peak_details = []
    peak_delta_cost = 0.0
    monthly_rate = (
        float(marginal_costs["capacity_tariff_eur_per_kw_year_excl_vat"])
        / 12
        * (1 + float(marginal_costs["vat_rate_import"]))
    )
    monthly_financials = []
    for month in sorted(source_by_month):
        source_rows = source_by_month[month]
        simulated_rows = simulated_by_month[month]
        baseline_peak = max(
            max(0.0, float(row["base_net_kwh"]))
            / float(row["duration_hours"])
            for row in source_rows
        )
        simulated_peak = max(
            float(row["grid_import_kwh"]) / float(row["duration_hours"])
            for row in simulated_rows
        )
        delta = (simulated_peak - baseline_peak) * monthly_rate
        peak_delta_cost += delta
        baseline_month_cost = sum(
            grid_cost(
                float(row["base_net_kwh"]),
                float(row["import_rate"]),
                float(row["export_rate"]),
            )
            for row in source_rows
        )
        simulated_grid_cost = sum(float(row["grid_cost_eur"]) for row in simulated_rows)
        degradation_cost = sum(
            float(row["degradation_cost_eur"]) for row in simulated_rows
        )
        monthly_financials.append(
            {
                "month": month,
                "net_saving_eur": baseline_month_cost
                - simulated_grid_cost
                - degradation_cost
                - delta,
                "grid_charge_kwh": sum(
                    float(row["grid_charge_kwh"]) for row in simulated_rows
                ),
                "surplus_charge_kwh": sum(
                    float(row["surplus_charge_kwh"]) for row in simulated_rows
                ),
                "discharge_kwh": sum(
                    float(row["discharge_kwh"]) for row in simulated_rows
                ),
                "conversion_loss_kwh": sum(
                    float(row["charge_kwh"])
                    * (1 - float(battery["charge_efficiency"]))
                    + float(row["discharge_kwh"])
                    * (1 / float(battery["discharge_efficiency"]) - 1)
                    for row in simulated_rows
                ),
            }
        )
        peak_details.append(
            {
                "month": month,
                "baseline_peak_kw": baseline_peak,
                "simulated_peak_kw": simulated_peak,
                "delta_cost_eur": delta,
            }
        )
    baseline_cost = sum(
        grid_cost(
            float(row["base_net_kwh"]),
            float(row["import_rate"]),
            float(row["export_rate"]),
        )
        for row in rows
    )
    simulated_cost = (
        totals["grid_cost_eur"]
        + totals["degradation_cost_eur"]
        + peak_delta_cost
    )
    efficiency_loss = totals["charge_kwh"] * (
        1 - float(battery["charge_efficiency"])
    ) + totals["discharge_kwh"] * (
        1 / float(battery["discharge_efficiency"]) - 1
    )
    seasonal = {}
    for name, months in (
        ("winter", {10, 11, 12, 1, 2, 3}),
        ("summer", {4, 5, 6, 7, 8, 9}),
    ):
        selected_months = [
            row for row in monthly_financials if int(row["month"][5:7]) in months
        ]
        seasonal[name] = {
            key: round(sum(float(row[key]) for row in selected_months), 6)
            for key in (
                "net_saving_eur",
                "grid_charge_kwh",
                "surplus_charge_kwh",
                "discharge_kwh",
                "conversion_loss_kwh",
            )
        }
    return {
        "allow_grid_charge": allow_grid_charge,
        "allow_battery_export": allow_battery_export,
        "peak_policy": (
            f"absolute_{absolute_peak_kw:g}_kw"
            if absolute_peak_kw is not None
            else (
                "observed_monthly_peak"
                if peak_allowance_kw == 0
                else "observed_monthly_peak_plus_allowance"
            )
        ),
        "segment_count": segment_count,
        "baseline_cost_eur": round(baseline_cost, 6),
        "simulated_cost_eur": round(simulated_cost, 6),
        "net_saving_eur": round(baseline_cost - simulated_cost, 6),
        "capacity_peak_delta_eur": round(peak_delta_cost, 6),
        "charge_kwh": round(totals["charge_kwh"], 6),
        "grid_charge_kwh": round(totals["grid_charge_kwh"], 6),
        "surplus_charge_kwh": round(totals["surplus_charge_kwh"], 6),
        "discharge_kwh": round(totals["discharge_kwh"], 6),
        "conversion_loss_kwh": round(efficiency_loss, 6),
        "equivalent_full_cycles": round(totals["discharge_kwh"] / capacity_kwh, 6),
        "grid_import_kwh": round(totals["grid_import_kwh"], 6),
        "grid_export_kwh": round(totals["grid_export_kwh"], 6),
        "monthly_peaks": peak_details,
        "seasonal": seasonal,
    }


def safe_simulate_residual_year(*args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return {"feasible": True, **simulate_residual_year(*args, **kwargs)}
    except ValueError as error:
        return {
            "feasible": False,
            "reason": str(error),
            "allow_grid_charge": kwargs.get("allow_grid_charge"),
            "allow_battery_export": kwargs.get("allow_battery_export", False),
            "peak_policy": (
                f"absolute_{kwargs['absolute_peak_kw']:g}_kw"
                if kwargs.get("absolute_peak_kw") is not None
                else "observed_monthly_peak"
            ),
        }


def select_best_grid_charging_option(
    pv_only: dict[str, Any], grid_candidate: dict[str, Any]
) -> dict[str, Any]:
    candidate_increment = float(grid_candidate["net_saving_eur"]) - float(
        pv_only["net_saving_eur"]
    )
    if candidate_increment > 1e-9:
        return {
            **grid_candidate,
            "selected_source": "price_aware_grid_charging_candidate",
            "incremental_value_of_grid_charging_eur": round(candidate_increment, 6),
        }
    return {
        **pv_only,
        "selected_source": "pv_surplus_only_fallback",
        "grid_charging_candidate_net_saving_eur": grid_candidate[
            "net_saving_eur"
        ],
        "incremental_value_of_grid_charging_eur": 0.0,
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def summarize_energy_year(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if not row["unavailable"]]
    imports = [float(row["import_kwh"]) for row in usable]
    exports = [float(row["export_kwh"]) for row in usable]
    prices = [float(row["market_price_eur_per_mwh"]) for row in usable]
    import_total = sum(imports)
    export_total = sum(exports)
    winter = [row for row in usable if row["start_local"].month in {10, 11, 12, 1, 2, 3}]
    summer = [row for row in usable if row not in winter]
    baseline_cost = sum(
        grid_cost(
            float(row["base_net_kwh"]),
            float(row["import_rate"]),
            float(row["export_rate"]),
        )
        for row in usable
    )
    return {
        "interval_count": len(rows),
        "usable_interval_count": len(usable),
        "estimated_interval_count": sum(
            row["estimated"] and not row["unavailable"] for row in rows
        ),
        "unavailable_interval_count": sum(row["unavailable"] for row in rows),
        "import_kwh": round(import_total, 3),
        "export_kwh": round(export_total, 3),
        "net_import_kwh": round(import_total - export_total, 3),
        "observed_peak_import_kw": round(max(imports) / 0.25, 3),
        "average_market_price_eur_per_mwh": round(fmean(prices), 6),
        "p10_market_price_eur_per_mwh": round(percentile(prices, 0.10), 3),
        "p90_market_price_eur_per_mwh": round(percentile(prices, 0.90), 3),
        "import_weighted_market_price_eur_per_mwh": round(
            sum(price * volume for price, volume in zip(prices, imports)) / import_total,
            6,
        ),
        "export_weighted_market_price_eur_per_mwh": round(
            sum(price * volume for price, volume in zip(prices, exports)) / export_total,
            6,
        ),
        "negative_market_interval_count": sum(price < 0 for price in prices),
        "import_during_negative_market_kwh": round(
            sum(volume for price, volume in zip(prices, imports) if price < 0), 3
        ),
        "export_during_negative_market_kwh": round(
            sum(volume for price, volume in zip(prices, exports) if price < 0), 3
        ),
        "retrospective_dynamic_energy_cost_eur": round(baseline_cost, 6),
        "winter_import_kwh": round(sum(float(row["import_kwh"]) for row in winter), 3),
        "winter_export_kwh": round(sum(float(row["export_kwh"]) for row in winter), 3),
        "summer_import_kwh": round(sum(float(row["import_kwh"]) for row in summer), 3),
        "summer_export_kwh": round(sum(float(row["export_kwh"]) for row in summer), 3),
    }


def summarize_financial_sensitivity(
    rows: list[dict[str, Any]],
    historical_tariffs: dict[str, dict[str, Any]],
    dynamic_subscription_eur_per_month_incl_vat: float = 0.0,
) -> dict[str, Any]:
    usable = [row for row in rows if not row["unavailable"]]
    historical_import = 0.0
    historical_export = 0.0
    dynamic_import = 0.0
    dynamic_export = 0.0
    sources: set[str] = set()
    providers: set[str] = set()
    represented_months = sorted({row["start_local"].strftime("%Y-%m") for row in rows})
    for row in usable:
        month = row["start_local"].strftime("%Y-%m")
        if month not in historical_tariffs:
            raise ValueError(f"Missing historical tariff for {month}")
        historical = historical_tariffs[month]
        imported = float(row["import_kwh"])
        exported = float(row["export_kwh"])
        historical_import += imported * float(
            historical["selected_import_eur_per_kwh"]
        )
        historical_export += exported * float(
            historical["selected_export_eur_per_kwh"]
        )
        dynamic_import += imported * float(row["import_rate"])
        dynamic_export += exported * float(row["export_rate"])
        sources.add(str(historical["selected_import_source"]))
        if historical.get("provider"):
            providers.add(str(historical["provider"]))

    historical_fixed = 0.0
    for month in represented_months:
        if month not in historical_tariffs:
            raise ValueError(f"Missing historical tariff for {month}")
        tariff = historical_tariffs[month]
        month_start = date.fromisoformat(f"{month}-01")
        if month_start.month == 12:
            month_end = date(month_start.year + 1, 1, 1)
        else:
            month_end = date(month_start.year, month_start.month + 1, 1)
        days = (month_end - month_start).days
        historical_fixed += days * float(tariff["dsmr_fixed_daily_cost_eur"])

    dynamic_subscription = (
        len(represented_months) * dynamic_subscription_eur_per_month_incl_vat
    )
    historical_net = historical_import - historical_export
    dynamic_net = dynamic_import - dynamic_export
    historical_total = historical_net + historical_fixed
    dynamic_total = dynamic_net + historical_fixed + dynamic_subscription
    return {
        "calculation_scope": "RECONCILED_ALL_IN_RATE_SENSITIVITY",
        "verification_status": "RATE_RECONCILED_FIXED_COMPONENTS_HELD_CONSTANT",
        "usable_interval_count": len(usable),
        "unavailable_interval_count": sum(row["unavailable"] for row in rows),
        "represented_month_count": len(represented_months),
        "historical_import_charge_eur": round(historical_import, 6),
        "historical_export_credit_eur": round(historical_export, 6),
        "historical_net_variable_cost_eur": round(historical_net, 6),
        "historical_fixed_cost_eur": round(historical_fixed, 6),
        "historical_total_cost_eur": round(historical_total, 6),
        "dynamic_import_charge_eur": round(dynamic_import, 6),
        "dynamic_export_credit_eur": round(dynamic_export, 6),
        "dynamic_net_variable_cost_eur": round(dynamic_net, 6),
        "dynamic_subscription_eur": round(dynamic_subscription, 6),
        "dynamic_fixed_cost_carried_forward_eur": round(historical_fixed, 6),
        "dynamic_total_cost_eur": round(dynamic_total, 6),
        "dynamic_minus_historical_variable_eur": round(
            dynamic_net - historical_net, 6
        ),
        "dynamic_minus_historical_eur": round(dynamic_total - historical_total, 6),
        "selected_import_sources": sorted(sources),
        "providers": sorted(providers),
        "limitations": [
            "DSMR exported all-in rates are internally reconciled but not independently invoice-validated.",
            "Historical fixed costs are carried unchanged into the dynamic scenario because supplier, grid, capacity, tax and levy components are not decomposed.",
            "The dynamic supplier subscription is added separately including configured import VAT.",
            "Unavailable quarter energy is excluded from variable charges; fixed monthly costs remain included.",
            "The August 2026 dynamic tariff formula and current marginal components are applied retrospectively.",
        ],
    }


def summarize_three_year_financial_sensitivity(
    financial_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    historical_variable = sum(
        row["historical_net_variable_cost_eur"] for row in financial_rows
    )
    dynamic_variable = sum(
        row["dynamic_net_variable_cost_eur"] for row in financial_rows
    )
    historical_fixed = sum(
        row["historical_fixed_cost_eur"] for row in financial_rows
    )
    dynamic_subscription = sum(
        row["dynamic_subscription_eur"] for row in financial_rows
    )
    historical_total = sum(row["historical_total_cost_eur"] for row in financial_rows)
    dynamic_total = sum(row["dynamic_total_cost_eur"] for row in financial_rows)
    return {
        "calculation_scope": "RECONCILED_ALL_IN_RATE_SENSITIVITY",
        "verification_status": "RATE_RECONCILED_FIXED_COMPONENTS_HELD_CONSTANT",
        "historical_net_variable_cost_eur": round(historical_variable, 6),
        "dynamic_net_variable_cost_eur": round(dynamic_variable, 6),
        "historical_fixed_cost_eur": round(historical_fixed, 6),
        "dynamic_fixed_cost_carried_forward_eur": round(historical_fixed, 6),
        "dynamic_subscription_eur": round(dynamic_subscription, 6),
        "historical_total_cost_eur": round(historical_total, 6),
        "dynamic_total_cost_eur": round(dynamic_total, 6),
        "dynamic_minus_historical_variable_eur": round(
            dynamic_variable - historical_variable, 6
        ),
        "dynamic_minus_historical_eur": round(dynamic_total - historical_total, 6),
        "average_dynamic_saving_eur_per_year": round(
            (historical_total - dynamic_total) / len(financial_rows), 6
        ),
        "limitations": financial_rows[0]["limitations"],
    }


def observed_battery_by_year(
    sunny_rows: list[dict[str, Any]],
    ha_path: Path,
    labels: list[str],
    usable_capacity_kwh: float,
) -> dict[str, Any]:
    ha_payload = json.loads(ha_path.read_text(encoding="utf-8"))
    charge_by_time = {
        row["start_utc"]: row for row in ha_payload["series"]["battery_charge"]
    }
    discharge_by_time = {
        row["start_utc"]: row for row in ha_payload["series"]["battery_discharge"]
    }
    ha_rows = []
    for timestamp in sorted(set(charge_by_time) & set(discharge_by_time)):
        charge = charge_by_time[timestamp].get("energy_kwh")
        discharge = discharge_by_time[timestamp].get("energy_kwh")
        if charge is None or discharge is None:
            continue
        local = datetime.fromisoformat(charge_by_time[timestamp]["start_local"])
        ha_rows.append(
            {
                "start_local": local,
                "battery_charge_kwh": float(charge),
                "battery_discharge_kwh": float(discharge),
            }
        )

    output = {}
    for label in labels:
        start, end = year_bounds(label)
        sunny_selected = [
            row
            for row in sunny_rows
            if start.date() <= row["date"] < end.date()
            and row["battery_charge_kwh"] is not None
            and row["battery_discharge_kwh"] is not None
        ]
        ha_selected = [
            row for row in ha_rows if start <= row["start_local"] < end
        ]
        charge = sum(float(row["battery_charge_kwh"]) for row in sunny_selected) + sum(
            float(row["battery_charge_kwh"]) for row in ha_selected
        )
        discharge = sum(
            float(row["battery_discharge_kwh"]) for row in sunny_selected
        ) + sum(float(row["battery_discharge_kwh"]) for row in ha_selected)
        output[label] = {
            "sunny_daily_day_count": len(sunny_selected),
            "ha_hour_count": len(ha_selected),
            "coverage_classification": (
                "COMPLETE_DAILY_SUNNY"
                if len(sunny_selected) in {365, 366} and not ha_selected
                else "PARTIAL_MIXED_SUNNY_HA"
            ),
            "charge_kwh": round(charge, 3),
            "discharge_kwh": round(discharge, 3),
            "discharge_charge_ratio": round(discharge / charge, 6)
            if charge
            else None,
            "equivalent_full_cycles": round(discharge / usable_capacity_kwh, 3),
            "sources": [
                source
                for source, present in (
                    ("Sunny Portal daily energy", bool(sunny_selected)),
                    ("Home Assistant hourly statistics", bool(ha_selected)),
                )
                if present
            ],
        }
    return output


def build_report(
    *,
    fluvius_path: Path,
    price_paths: list[Path],
    sunny_energy_paths: list[Path],
    sunny_power_paths: list[Path],
    ha_path: Path,
    tariff_path: Path,
    historical_tariffs_path: Path,
    battery_path: Path,
    marginal_costs_path: Path,
    state_step_kwh: float,
) -> dict[str, Any]:
    fluvius = load_fluvius_intervals(fluvius_path)
    price_map = load_price_map(price_paths)
    tariff = json.loads(tariff_path.read_text(encoding="utf-8"))
    historical_tariff_ledger = json.loads(
        historical_tariffs_path.read_text(encoding="utf-8")
    )
    historical_tariffs = {
        row["month"]: row for row in historical_tariff_ledger["months"]
    }
    battery_config = json.loads(battery_path.read_text(encoding="utf-8"))
    battery = battery_config["battery"]
    marginal_costs = json.loads(marginal_costs_path.read_text(encoding="utf-8"))
    sunny_energy = load_sunny_energy_files(sunny_energy_paths)
    sunny_power, sunny_power_quality = load_sunny_power_files(sunny_power_paths)
    sunny_dispatch = summarize_sunny_power_dispatch(sunny_power)

    canonical_start = datetime(2023, 10, 1, tzinfo=ZONE)
    canonical_end = datetime(2026, 10, 1, tzinfo=ZONE)
    selected = [
        row
        for row in fluvius
        if canonical_start <= row["start_local"] < canonical_end
    ]
    if len(selected) != 105216:
        raise ValueError(f"Expected 105216 Fluvius intervals, found {len(selected)}")
    joined: list[dict[str, Any]] = []
    for row in selected:
        if row["start_utc"] not in price_map:
            raise ValueError(f"Missing market price at {row['start_utc'].isoformat()}")
        market_price = price_map[row["start_utc"]]
        import_rate, export_rate = dynamic_rates(market_price, tariff, marginal_costs)
        usable = not row["unavailable"]
        joined.append(
            {
                **row,
                "market_price_eur_per_mwh": market_price,
                "import_rate": import_rate,
                "export_rate": export_rate,
                "base_net_kwh": (
                    float(row["import_kwh"]) - float(row["export_kwh"])
                    if usable
                    else None
                ),
            }
        )

    labels = ["2023-2024", "2024-2025", "2025-2026"]
    observed_battery = observed_battery_by_year(
        sunny_energy,
        ha_path,
        labels,
        float(battery["usable_capacity_kwh"]),
    )
    years = []
    additional_capacities = [
        float(value) for value in marginal_costs["additional_capacity_kwh"]
    ]
    for label in labels:
        year_rows_all = [row for row in joined if analysis_year(row["start_local"]) == label]
        usable_rows = [row for row in year_rows_all if not row["unavailable"]]
        scenarios = []
        for capacity in additional_capacities:
            pv_only = simulate_residual_year(
                usable_rows,
                capacity_kwh=capacity,
                battery=battery,
                marginal_costs=marginal_costs,
                allow_grid_charge=False,
                state_step_kwh=state_step_kwh,
            )
            price_aware = simulate_residual_year(
                usable_rows,
                capacity_kwh=capacity,
                battery=battery,
                marginal_costs=marginal_costs,
                allow_grid_charge=True,
                state_step_kwh=state_step_kwh,
            )
            selected_price_aware = select_best_grid_charging_option(
                pv_only, price_aware
            )
            scenarios.append(
                {
                    "additional_usable_capacity_kwh": capacity,
                    "power_limit_kw": float(battery["max_charge_power_kw"]),
                    "pv_surplus_only": pv_only,
                    "price_aware_grid_charging_candidate": price_aware,
                    "best_with_grid_charging_option": selected_price_aware,
                    "incremental_value_of_grid_charging_eur": selected_price_aware[
                        "incremental_value_of_grid_charging_eur"
                    ],
                }
            )

        decision_capacity = float(battery["usable_capacity_kwh"])
        peak_neutral_pv = safe_simulate_residual_year(
            usable_rows,
            capacity_kwh=decision_capacity,
            battery=battery,
            marginal_costs=marginal_costs,
            allow_grid_charge=False,
            state_step_kwh=state_step_kwh,
            peak_allowance_kw=0.0,
        )
        peak_neutral_grid = safe_simulate_residual_year(
            usable_rows,
            capacity_kwh=decision_capacity,
            battery=battery,
            marginal_costs=marginal_costs,
            allow_grid_charge=True,
            state_step_kwh=state_step_kwh,
            peak_allowance_kw=0.0,
        )
        peak_neutral_export = safe_simulate_residual_year(
            usable_rows,
            capacity_kwh=decision_capacity,
            battery=battery,
            marginal_costs=marginal_costs,
            allow_grid_charge=True,
            allow_battery_export=True,
            state_step_kwh=state_step_kwh,
            peak_allowance_kw=0.0,
        )
        absolute_peak_scenarios = []
        for cap_kw in (7.0, 8.0, 10.0):
            cap_pv = safe_simulate_residual_year(
                usable_rows,
                capacity_kwh=decision_capacity,
                battery=battery,
                marginal_costs=marginal_costs,
                allow_grid_charge=False,
                state_step_kwh=state_step_kwh,
                absolute_peak_kw=cap_kw,
            )
            cap_grid = safe_simulate_residual_year(
                usable_rows,
                capacity_kwh=decision_capacity,
                battery=battery,
                marginal_costs=marginal_costs,
                allow_grid_charge=True,
                state_step_kwh=state_step_kwh,
                absolute_peak_kw=cap_kw,
            )
            absolute_peak_scenarios.append(
                {
                    "cap_kw": cap_kw,
                    "baseline_exposure": summarize_peak_exposure(
                        usable_rows, cap_kw
                    ),
                    "pv_surplus_only": cap_pv,
                    "price_aware_grid_charging": cap_grid,
                    "incremental_grid_charging_value_eur": (
                        round(
                            float(cap_grid["net_saving_eur"])
                            - float(cap_pv["net_saving_eur"]),
                            6,
                        )
                        if cap_pv["feasible"] and cap_grid["feasible"]
                        else None
                    ),
                }
            )
        years.append(
            {
                "analysis_year": label,
                "period_start_local": year_bounds(label)[0].isoformat(),
                "period_end_local": year_bounds(label)[1].isoformat(),
                "energy_and_price": summarize_energy_year(year_rows_all),
                "financial_sensitivity": summarize_financial_sensitivity(
                    year_rows_all,
                    historical_tariffs,
                    dynamic_subscription_eur_per_month_incl_vat=(
                        float(tariff["subscription_eur_per_month"])
                        * (1.0 + float(tariff["vat_rate_import"]))
                    ),
                ),
                "observed_battery": observed_battery[label],
                "residual_grid_additional_battery": scenarios,
                "decision_scenarios": {
                    "interpretation": "virtual 14.24 kWh dispatch on the residual grid profile; not an exact redispatch of the installed battery",
                    "peak_neutral": {
                        "pv_surplus_only": peak_neutral_pv,
                        "price_aware_grid_charging": peak_neutral_grid,
                        "price_aware_with_battery_export": peak_neutral_export,
                        "incremental_grid_charging_value_eur": (
                            round(
                                float(peak_neutral_grid["net_saving_eur"])
                                - float(peak_neutral_pv["net_saving_eur"]),
                                6,
                            )
                            if peak_neutral_pv["feasible"]
                            and peak_neutral_grid["feasible"]
                            else None
                        ),
                        "incremental_export_value_eur": (
                            round(
                                float(peak_neutral_export["net_saving_eur"])
                                - float(peak_neutral_grid["net_saving_eur"]),
                                6,
                            )
                            if peak_neutral_grid["feasible"]
                            and peak_neutral_export["feasible"]
                            else None
                        ),
                    },
                    "absolute_peak_caps": absolute_peak_scenarios,
                },
            }
        )

    return {
        "schema_version": 1,
        "classification": "READ_ONLY_MULTI_YEAR_COMPARISON",
        "period_start_local": canonical_start.isoformat(),
        "period_end_local": canonical_end.isoformat(),
        "model": {
            "energy_source": "Fluvius quarter-hour import/export",
            "price_source": "ENTSO-E Belgian Day-Ahead",
            "observed_battery_sources": [
                "Sunny Portal daily energy 2023-2025",
                "Sunny Portal intraday power 2025-05-29 through 2025-12-31",
                "Home Assistant hourly battery statistics 2026-01-22 through 2026-09-30",
            ],
            "retrospective_tariff_version": tariff["version"],
            "historical_tariff_ledger": historical_tariff_ledger[
                "classification"
            ],
            "historical_tariff_calculation_scope": "RECONCILED_ALL_IN_RATE_SENSITIVITY",
            "residual_battery_interpretation": "additional virtual battery applied after historically observed battery behavior",
            "residual_battery_export": False,
            "grid_charging_comparison": [
                "PV surplus only",
                "price-aware grid charging with perfect foresight and a baseline monthly peak plus 1 kW cap",
            ],
            "physical_writes": False,
            "contract_change": False,
            "state_step_kwh": state_step_kwh,
        },
        "battery_parameters": battery,
        "sunny_portal_quality": {
            "daily_energy": {
                "row_count": len(sunny_energy),
                "period_start": sunny_energy[0]["date"].isoformat(),
                "period_end": sunny_energy[-1]["date"].isoformat(),
                "missing_day_count": (
                    sunny_energy[-1]["date"] - sunny_energy[0]["date"]
                ).days
                + 1
                - len(sunny_energy),
            },
            "intraday_power": sunny_power_quality,
            "observed_dispatch": sunny_dispatch,
        },
        "years": years,
        "limitations": [
            "Fluvius residual net flow already includes the historical operation of the existing battery; residual scenarios therefore represent additional storage, not a clean replacement of the existing battery.",
            "Sunny Portal provides complete daily battery energy for 2023-2025, but interval battery power only from 2025-05-29 through 2025-12-31.",
            "The 2025-2026 observed battery year is partial because detailed battery data is unavailable for 2026-01-01 through 2026-01-21.",
            "The August 2026 Ecopower dynamic formula is applied retrospectively as a controlled constant-tariff sensitivity across all three years.",
            "The three-year historical comparison uses configured DSMR rates, with owner-confirmed Home Assistant import rates taking precedence for January through September 2026; component scope and VAT inclusion remain unverified.",
            "Residual-battery scenarios use perfect price and residual-load foresight and are upper bounds, not deployable production forecasts.",
            "The six unavailable Fluvius quarters remain excluded from optimization and visible in quality counts.",
        ],
    }


def build_privacy_safe_summary(report: dict[str, Any]) -> dict[str, Any]:
    years = []
    for source_year in report["years"]:
        scenarios = []
        for source_scenario in source_year["residual_grid_additional_battery"]:
            pv_only = source_scenario["pv_surplus_only"]
            best = source_scenario["best_with_grid_charging_option"]
            scenarios.append(
                {
                    "additional_usable_capacity_kwh": source_scenario[
                        "additional_usable_capacity_kwh"
                    ],
                    "power_limit_kw": source_scenario["power_limit_kw"],
                    "pv_surplus_only_net_saving_eur": pv_only["net_saving_eur"],
                    "best_with_grid_charging_net_saving_eur": best[
                        "net_saving_eur"
                    ],
                    "incremental_value_of_grid_charging_eur": source_scenario[
                        "incremental_value_of_grid_charging_eur"
                    ],
                    "selected_source": best["selected_source"],
                    "grid_charge_kwh": best["grid_charge_kwh"],
                    "conversion_loss_kwh": best["conversion_loss_kwh"],
                    "equivalent_full_cycles": best["equivalent_full_cycles"],
                    "capacity_peak_delta_eur": best["capacity_peak_delta_eur"],
                    "battery_export_allowed": False,
                }
            )
        years.append(
            {
                "analysis_year": source_year["analysis_year"],
                "period_start_local": source_year["period_start_local"],
                "period_end_local": source_year["period_end_local"],
                "energy_and_price": source_year["energy_and_price"],
                "financial_sensitivity": source_year["financial_sensitivity"],
                "observed_battery": source_year["observed_battery"],
                "additional_battery": scenarios,
                "decision_scenarios": source_year["decision_scenarios"],
            }
        )

    energy_rows = [year["energy_and_price"] for year in years]
    first = energy_rows[0]
    last = energy_rows[-1]
    capacities = sorted(
        {
            row["additional_usable_capacity_kwh"]
            for year in years
            for row in year["additional_battery"]
        }
    )
    three_year_capacity = []
    for capacity in capacities:
        matching = [
            next(
                row
                for row in year["additional_battery"]
                if row["additional_usable_capacity_kwh"] == capacity
            )
            for year in years
        ]
        three_year_capacity.append(
            {
                "additional_usable_capacity_kwh": capacity,
                "average_pv_surplus_only_net_saving_eur_per_year": round(
                    fmean(
                        row["pv_surplus_only_net_saving_eur"] for row in matching
                    ),
                    6,
                ),
                "average_best_with_grid_charging_net_saving_eur_per_year": round(
                    fmean(
                        row["best_with_grid_charging_net_saving_eur"]
                        for row in matching
                    ),
                    6,
                ),
                "average_incremental_grid_charging_value_eur_per_year": round(
                    fmean(
                        row["incremental_value_of_grid_charging_eur"]
                        for row in matching
                    ),
                    6,
                ),
            }
        )

    decision_years = [year["decision_scenarios"] for year in years]
    peak_neutral = [year["peak_neutral"] for year in decision_years]
    peak_neutral_incremental = [
        float(year["incremental_grid_charging_value_eur"])
        for year in peak_neutral
        if year["incremental_grid_charging_value_eur"] is not None
    ]
    peak_neutral_winter_incremental = [
        float(year["price_aware_grid_charging"]["seasonal"]["winter"]["net_saving_eur"])
        - float(year["pv_surplus_only"]["seasonal"]["winter"]["net_saving_eur"])
        for year in peak_neutral
        if year["price_aware_grid_charging"]["feasible"]
        and year["pv_surplus_only"]["feasible"]
    ]
    peak_neutral_export_incremental = [
        float(year["incremental_export_value_eur"])
        for year in peak_neutral
        if year["incremental_export_value_eur"] is not None
    ]
    peak_cap_overview = []
    for cap_kw in (7.0, 8.0, 10.0):
        matching = [
            next(row for row in year["absolute_peak_caps"] if row["cap_kw"] == cap_kw)
            for year in decision_years
        ]
        feasible = [
            row
            for row in matching
            if row["price_aware_grid_charging"]["feasible"]
            or row["pv_surplus_only"]["feasible"]
        ]
        values = [
            max(
                [
                    float(option["net_saving_eur"])
                    for option in (
                        row["price_aware_grid_charging"],
                        row["pv_surplus_only"],
                    )
                    if option["feasible"]
                ]
            )
            for row in feasible
        ]
        incremental = [
            max(0.0, float(row["incremental_grid_charging_value_eur"]))
            for row in matching
            if row["incremental_grid_charging_value_eur"] is not None
        ]
        peak_cap_overview.append(
            {
                "cap_kw": cap_kw,
                "status": classify_scenario_option(
                    average_net_value_eur=fmean(values) if values else None,
                    feasible_year_count=len(feasible),
                    requires_new_hardware=False,
                    data_complete=True,
                ),
                "feasible_year_count": len(feasible),
                "average_net_saving_eur_per_year": round(fmean(values), 6)
                if values
                else None,
                "average_incremental_grid_charging_value_eur_per_year": round(
                    fmean(incremental), 6
                )
                if incremental
                else None,
                "grid_charging_selected_year_count": sum(
                    float(row["incremental_grid_charging_value_eur"] or 0.0) > 0
                    for row in matching
                ),
                "baseline_quarter_count_above_cap": sum(
                    row["baseline_exposure"]["quarter_count_above_cap"]
                    for row in matching
                ),
                "maximum_historical_excess_kw": max(
                    row["baseline_exposure"]["maximum_excess_kw"]
                    for row in matching
                ),
                "interpretation": "shared quarter-hour grid-import ceiling covering house, heat pump, EV and battery charging; individual loads are not separately reconstructed",
            }
        )

    financial_rows = [year["financial_sensitivity"] for year in years]
    three_year_financial_sensitivity = summarize_three_year_financial_sensitivity(
        financial_rows
    )

    scenario_overview = {
        "computed": [
            {
                "id": "dynamic_contract_unchanged_behavior",
                "title": "Dynamisch contract zonder sturing",
                "status": "OPTION",
                "value_eur_per_year": three_year_financial_sensitivity[
                    "average_dynamic_saving_eur_per_year"
                ],
                "why": "DSMR-exported monthly all-in rates are compared with the same retrospective dynamic formula for all three local years; unchanged fixed costs are carried forward and the dynamic subscription is added.",
                "limitation": "The export reconciles configured prices to DSMR displayed costs, but fixed supplier, grid, capacity, tax and levy components are not decomposed or independently invoice-validated.",
            },
            {
                "id": "peak_neutral_winter_grid_charging",
                "title": "Winterse netlading zonder hogere maandpiek",
                "status": classify_scenario_option(
                    average_net_value_eur=fmean(peak_neutral_incremental),
                    feasible_year_count=len(peak_neutral_incremental),
                    requires_new_hardware=False,
                    data_complete=True,
                ),
                "value_eur_per_year": round(fmean(peak_neutral_incremental), 6),
                "winter_value_eur_per_year": round(
                    fmean(peak_neutral_winter_incremental), 6
                ),
                "why": "Uses cheap Day-Ahead quarters to fill otherwise idle storage while keeping every simulated month at or below its observed peak.",
                "limitation": "Perfect foresight on a residual profile; this is not an exact redispatch of the installed battery.",
            },
            {
                "id": "battery_export",
                "title": "Prijsarbitrage met batterij-export",
                "status": "REQUIRES_TESTING",
                "value_eur_per_year": round(
                    fmean(peak_neutral_export_incremental), 6
                ),
                "why": "Can capture rare high-price intervals after household demand is covered.",
                "limitation": "Requires controller, warranty, metering, supplier and regulatory validation; no physical export control has been tested.",
            },
            {
                "id": "additional_battery_capacity",
                "title": "Extra batterijcapaciteit",
                "status": "INVESTMENT_CASE_REQUIRED",
                "value_eur_per_year": three_year_capacity[-1][
                    "average_best_with_grid_charging_net_saving_eur_per_year"
                ],
                "why": "Adds PV capture and some price arbitrage on the residual profile.",
                "limitation": "The perfect-foresight annual value remains too small to support hardware purchase without installed cost and lifetime inputs.",
            },
        ],
        "peak_caps": peak_cap_overview,
        "data_gated": [
            {
                "id": "coordinated_ev_charging",
                "title": "EV-laden op goedkope uren binnen een gezamenlijke piek",
                "status": "DATA_GATED",
                "required_data": "EV availability, departure time, target energy and complete interval power",
            },
            {
                "id": "heat_pump_preheating",
                "title": "Warmtepomp voorverwarmen op goedkope uren",
                "status": "DATA_GATED",
                "required_data": "heat-pump interval power, indoor/outdoor temperature, COP and comfort constraints",
            },
            {
                "id": "coordinated_home_energy_manager",
                "title": "Gezamenlijke planning batterij, EV, warmtepomp en huis",
                "status": "DATA_GATED",
                "required_data": "battery SOC and flows plus disaggregated EV, heat-pump and base-load intervals",
            },
        ],
    }

    quality = {
        "interval_count": sum(row["interval_count"] for row in energy_rows),
        "usable_interval_count": sum(
            row["usable_interval_count"] for row in energy_rows
        ),
        "estimated_interval_count": sum(
            row["estimated_interval_count"] for row in energy_rows
        ),
        "unavailable_interval_count": sum(
            row["unavailable_interval_count"] for row in energy_rows
        ),
        "sunny_daily_row_count": report["sunny_portal_quality"]["daily_energy"][
            "row_count"
        ],
        "sunny_missing_day_count": report["sunny_portal_quality"][
            "daily_energy"
        ]["missing_day_count"],
        "sunny_intraday_duplicate_local_timestamp_count": report[
            "sunny_portal_quality"
        ]["intraday_power"]["duplicate_local_timestamp_count"],
    }
    total_import = sum(row["import_kwh"] for row in energy_rows)
    total_export = sum(row["export_kwh"] for row in energy_rows)
    total_dynamic = sum(
        row["retrospective_dynamic_energy_cost_eur"] for row in energy_rows
    )
    return {
        "schema_version": 1,
        "status": "VERIFIED_WITH_LIMITATIONS",
        "classification": report["classification"],
        "period_start_local": report["period_start_local"],
        "period_end_local": report["period_end_local"],
        "physical_writes": False,
        "contract_change": False,
        "quality": quality,
        "three_year_totals": {
            "import_kwh": round(total_import, 3),
            "export_kwh": round(total_export, 3),
            "net_import_kwh": round(total_import - total_export, 3),
            "negative_market_interval_count": sum(
                row["negative_market_interval_count"] for row in energy_rows
            ),
            "retrospective_dynamic_energy_cost_eur": round(total_dynamic, 6),
        },
        "trend": {
            "first_to_last_import_change_percent": round(
                (last["import_kwh"] / first["import_kwh"] - 1) * 100, 6
            ),
            "first_to_last_export_change_percent": round(
                (last["export_kwh"] / first["export_kwh"] - 1) * 100, 6
            ),
            "first_to_last_import_weighted_market_price_change_percent": round(
                (
                    last["import_weighted_market_price_eur_per_mwh"]
                    / first["import_weighted_market_price_eur_per_mwh"]
                    - 1
                )
                * 100,
                6,
            ),
        },
        "sunny_intraday_observed_dispatch": report["sunny_portal_quality"][
            "observed_dispatch"
        ],
        "years": years,
        "three_year_financial_sensitivity": three_year_financial_sensitivity,
        "additional_capacity_three_year_average": three_year_capacity,
        "scenario_overview": scenario_overview,
        "model": report["model"],
        "limitations": report["limitations"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fluvius", type=Path, required=True)
    parser.add_argument("--prices", type=Path, action="append", required=True)
    parser.add_argument("--sunny-energy", type=Path, action="append", required=True)
    parser.add_argument("--sunny-power", type=Path, action="append", default=[])
    parser.add_argument("--ha-hourly", type=Path, required=True)
    parser.add_argument("--dynamic-tariff", type=Path, required=True)
    parser.add_argument("--historical-tariffs", type=Path, required=True)
    parser.add_argument("--battery-config", type=Path, required=True)
    parser.add_argument("--marginal-costs", type=Path, required=True)
    parser.add_argument("--state-step-kwh", type=float, default=0.5)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path)
    args = parser.parse_args()

    report = build_report(
        fluvius_path=args.fluvius,
        price_paths=args.prices,
        sunny_energy_paths=args.sunny_energy,
        sunny_power_paths=args.sunny_power,
        ha_path=args.ha_hourly,
        tariff_path=args.dynamic_tariff,
        historical_tariffs_path=args.historical_tariffs,
        battery_path=args.battery_config,
        marginal_costs_path=args.marginal_costs,
        state_step_kwh=args.state_step_kwh,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if args.evidence_output:
        args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_output.write_text(
            json.dumps(build_privacy_safe_summary(report), indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "years": [
                    {
                        "analysis_year": year["analysis_year"],
                        "import_kwh": year["energy_and_price"]["import_kwh"],
                        "observed_battery": year["observed_battery"],
                        "additional_battery": [
                            {
                                "capacity_kwh": row["additional_usable_capacity_kwh"],
                                "pv_only_saving_eur": row["pv_surplus_only"][
                                    "net_saving_eur"
                                ],
                                "price_aware_saving_eur": row[
                                    "best_with_grid_charging_option"
                                ]["net_saving_eur"],
                            }
                            for row in year["residual_grid_additional_battery"]
                        ],
                    }
                    for year in report["years"]
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
