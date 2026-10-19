#!/usr/bin/env python3
"""Build a read-only day course for battery and EV charging from a shadow plan.

The battery schedule is taken unchanged from the selected shadow-controller
policy. EV charging is allocated on top of it under the shared grid import
limit, a price ceiling and a departure time. Nothing here talks to a device,
Home Assistant, SMA or Smappee.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Brussels")
SCHEMA_VERSION = 1
CLASSIFICATION = "PROPOSED_COURSE_NO_CONTROL"
READ_ONLY_FLAGS = (
    "physical_writes",
    "home_assistant_writes",
    "sma_writes",
    "smappee_writes",
)
EPSILON = 1e-9

DEFAULT_PARAMETERS: dict[str, Any] = {
    "max_grid_import_kw": 7.0,
    "price_ceiling_eur_per_kwh": 0.2,
    "ev_enabled": True,
    "ev_start_soc_percent": 20.0,
    "ev_target_soc_percent": 80.0,
    "ev_capacity_kwh": 60.0,
    "ev_max_charge_kw": 7.4,
    "ev_departure_time": "07:30",
    "active_days": [0, 1, 2, 3, 4, 5, 6],
}

_BOUNDS = {
    "max_grid_import_kw": (0.5, 25.0),
    "price_ceiling_eur_per_kwh": (0.0, 2.0),
    "ev_start_soc_percent": (0.0, 100.0),
    "ev_target_soc_percent": (0.0, 100.0),
    "ev_capacity_kwh": (1.0, 200.0),
    "ev_max_charge_kw": (1.0, 22.0),
}

ASSUMPTIONS = (
    "De auto hangt aan de lader vanaf het begin van de dag tot de vertrektijd.",
    "De batterijsturing is ongewijzigd het gekozen shadow-plan; de EV wordt erbovenop gepland.",
    "Geen minimaal laadvermogen, faseomschakeling of laadverlies in de auto gemodelleerd.",
    "Prijzen zijn de indicatieve Ecopower-importtarieven uit het shadow-plan, geen factuur.",
)


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} is not a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def parse_parameters(query: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    """Validate query-string parameters; return (parameters, error codes)."""
    params = dict(DEFAULT_PARAMETERS)
    errors: list[str] = []
    for name, (low, high) in _BOUNDS.items():
        if name not in query:
            continue
        try:
            number = _finite(query[name], name)
        except (TypeError, ValueError):
            errors.append(f"{name.upper()}_INVALID")
            continue
        if not low <= number <= high:
            errors.append(f"{name.upper()}_OUT_OF_RANGE")
            continue
        params[name] = number
    if "ev_enabled" in query:
        if query["ev_enabled"] not in {"true", "false"}:
            errors.append("EV_ENABLED_INVALID")
        else:
            params["ev_enabled"] = query["ev_enabled"] == "true"
    if "ev_departure_time" in query:
        try:
            params["ev_departure_time"] = _parse_clock(query["ev_departure_time"])
        except ValueError:
            errors.append("EV_DEPARTURE_TIME_INVALID")
    if "active_days" in query:
        try:
            days = sorted({int(day) for day in query["active_days"].split(",") if day != ""})
            if not days or any(day < 0 or day > 6 for day in days):
                raise ValueError
            params["active_days"] = days
        except ValueError:
            errors.append("ACTIVE_DAYS_INVALID")
    return params, errors


def _parse_clock(value: str) -> str:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise ValueError("clock must be HH:MM")
    hour, minute = int(value[:2]), int(value[3:])
    return time(hour, minute).strftime("%H:%M")


def _aware(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{name} requires an offset")
    return parsed.astimezone(timezone.utc)


def load_latest_report(directory: Path) -> dict[str, Any]:
    """Return the shadow plan report with the latest target_end_utc."""
    candidates = []
    for path in directory.glob("shadow-controller-plan-*.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("shadow plan must be an object")
        candidates.append((_aware(report.get("target_end_utc"), "target_end_utc"), path.name, report))
    if not candidates:
        raise ValueError("no shadow plan available")
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def _selected_schedule(report: dict[str, Any]) -> list[dict[str, Any]]:
    if report.get("mode") != "READ_ONLY_SHADOW" or any(
        report.get(flag) is not False for flag in READ_ONLY_FLAGS
    ):
        raise ValueError("shadow plan is not read-only")
    selected = next(
        (
            plan
            for plan in report.get("plans", [])
            if plan.get("id") == report.get("selected_policy_id")
        ),
        None,
    )
    if selected is None or selected.get("status") != "PLANNED":
        raise ValueError("selected planned policy is missing")
    schedule = selected.get("schedule")
    if not isinstance(schedule, list) or not schedule or len(schedule) != report.get("interval_count"):
        raise ValueError("selected schedule is incomplete")
    cursor = _aware(report.get("target_start_utc"), "target_start_utc")
    for row in schedule:
        if not isinstance(row, dict) or _aware(row.get("start_utc"), "start_utc") != cursor:
            raise ValueError("schedule intervals must be contiguous")
        cursor += timedelta(hours=_finite(row.get("duration_hours"), "duration_hours"))
    if cursor != _aware(report.get("target_end_utc"), "target_end_utc"):
        raise ValueError("schedule does not cover the target window")
    return schedule


def _cost(net_kwh: float, import_rate: float, export_rate: float) -> float:
    return net_kwh * (import_rate if net_kwh >= 0 else export_rate)


def _allocate_ev(rows: list[dict[str, Any]], needed_kwh: float, params: dict[str, Any],
                 ceiling: float) -> tuple[list[float], dict[str, int], float]:
    """Greedy cheapest-first EV allocation; returns kWh per row, blocked counts, highest price used."""
    allocation = [0.0] * len(rows)
    blocked = {"CEILING": 0, "LIMIT": 0}
    order = sorted(
        (i for i, row in enumerate(rows) if row["ev_window"]),
        key=lambda i: (rows[i]["marginal_rate"], rows[i]["start_utc"]),
    )
    remaining = needed_kwh
    highest = 0.0
    for i in order:
        row = rows[i]
        if row["marginal_rate"] > ceiling + EPSILON:
            blocked["CEILING"] += 1
            continue
        headroom_kw = params["max_grid_import_kw"] - row["base_grid_net_kw"]
        power_kw = min(params["ev_max_charge_kw"], max(0.0, headroom_kw))
        if power_kw <= EPSILON:
            blocked["LIMIT"] += 1
            continue
        if remaining <= EPSILON:
            continue
        energy = min(remaining, power_kw * row["duration_hours"])
        allocation[i] = energy
        remaining -= energy
        highest = max(highest, row["marginal_rate"])
    return allocation, blocked, highest


def build_day_course(report: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    schedule = _selected_schedule(report)
    target_date = str(report.get("target_date"))
    weekday_sun0 = (datetime.fromisoformat(target_date).weekday() + 1) % 7
    departure = time.fromisoformat(params["ev_departure_time"])
    warnings: list[str] = []
    ev_active = bool(params["ev_enabled"])
    if ev_active and weekday_sun0 not in params["active_days"]:
        ev_active = False
        warnings.append("AUTOMATION_NOT_ACTIVE_ON_TARGET_DAY")
    needed_kwh = max(
        0.0,
        (params["ev_target_soc_percent"] - params["ev_start_soc_percent"]) / 100.0 * params["ev_capacity_kwh"],
    )
    if ev_active and needed_kwh <= EPSILON:
        warnings.append("EV_TARGET_ALREADY_REACHED")

    rows: list[dict[str, Any]] = []
    for item in schedule:
        duration = _finite(item["duration_hours"], "duration_hours")
        start_local = datetime.fromisoformat(item["start_local"])
        grid_import = _finite(item["planned_grid_import_kw"], "planned_grid_import_kw")
        grid_export = _finite(item.get("planned_grid_export_kw", 0.0), "planned_grid_export_kw")
        net_kw = grid_import - grid_export
        import_rate = _finite(item["import_rate_eur_per_kwh"], "import_rate_eur_per_kwh")
        export_rate = _finite(item["export_rate_eur_per_kwh"], "export_rate_eur_per_kwh")
        charge = _finite(item.get("charge_kwh", 0.0), "charge_kwh")
        discharge = _finite(item.get("discharge_kwh", 0.0), "discharge_kwh")
        rows.append({
            "start_utc": item["start_utc"],
            "start_local": item["start_local"],
            "duration_hours": duration,
            "import_rate": import_rate,
            "export_rate": export_rate,
            "house_net_kw": _finite(item["forecast_base_net_kwh"], "forecast_base_net_kwh") / duration,
            "battery_kw": (charge - discharge) / duration,
            "battery_action": str(item.get("action", "HOLD")),
            "battery_reason": str(item.get("reason", "")),
            "base_grid_net_kw": net_kw,
            "marginal_rate": export_rate if net_kw < 0 else import_rate,
            "ev_window": ev_active and start_local.timetz().replace(tzinfo=None) < departure,
        })

    allocation, blocked, _ = (
        _allocate_ev(rows, needed_kwh, params, params["price_ceiling_eur_per_kwh"])
        if ev_active
        else ([0.0] * len(rows), {"CEILING": 0, "LIMIT": 0}, 0.0)
    )
    delivered = sum(allocation)
    unmet = max(0.0, needed_kwh - delivered) if ev_active else 0.0

    required_ceiling: float | None = None
    if ev_active and unmet > 0.001:
        free_alloc, _, highest = _allocate_ev(rows, needed_kwh, params, float("inf"))
        if needed_kwh - sum(free_alloc) <= 0.001:
            required_ceiling = round(highest, 4)
            warnings.append("PRICE_CEILING_BLOCKS_TARGET")
        else:
            warnings.append("LIMIT_OR_WINDOW_BLOCKS_TARGET")

    naive = [0.0] * len(rows)
    if ev_active:
        remaining = needed_kwh
        for i, row in enumerate(rows):
            if remaining <= EPSILON or not row["ev_window"]:
                continue
            naive[i] = min(remaining, params["ev_max_charge_kw"] * row["duration_hours"])
            remaining -= naive[i]

    intervals = []
    totals = {"baseline": 0.0, "battery": 0.0, "plan": 0.0, "ev": 0.0, "ev_naive": 0.0}
    peak = peak_naive = 0.0
    over_limit = over_limit_naive = 0
    for row, ev_kwh, naive_kwh in zip(rows, allocation, naive):
        d = row["duration_hours"]
        ev_kw = ev_kwh / d
        net_after = row["base_grid_net_kw"] + ev_kw
        net_naive = row["base_grid_net_kw"] + naive_kwh / d
        base_cost = _cost(row["house_net_kw"] * d, row["import_rate"], row["export_rate"])
        battery_cost = _cost(row["base_grid_net_kw"] * d, row["import_rate"], row["export_rate"])
        plan_cost = _cost(net_after * d, row["import_rate"], row["export_rate"])
        naive_cost = _cost(net_naive * d, row["import_rate"], row["export_rate"])
        totals["baseline"] += base_cost
        totals["battery"] += battery_cost
        totals["plan"] += plan_cost
        totals["ev"] += plan_cost - battery_cost
        totals["ev_naive"] += naive_cost - battery_cost
        imp, imp_naive = max(0.0, net_after), max(0.0, net_naive)
        peak, peak_naive = max(peak, imp), max(peak_naive, imp_naive)
        limit = params["max_grid_import_kw"]
        over_limit += imp > limit + 1e-6
        over_limit_naive += imp_naive > limit + 1e-6
        if ev_kw > EPSILON:
            ev_reason = (
                "PV-overschot zelf verbruiken" if row["base_grid_net_kw"] < 0
                else "Goedkoopste beschikbare kwartier onder prijsplafond"
            )
        elif not ev_active:
            ev_reason = "EV niet ingepland"
        elif not row["ev_window"]:
            ev_reason = "Na vertrektijd"
        elif row["marginal_rate"] > params["price_ceiling_eur_per_kwh"] + EPSILON:
            ev_reason = "Prijs boven plafond"
        elif params["max_grid_import_kw"] - row["base_grid_net_kw"] <= EPSILON:
            ev_reason = "Gezamenlijke importlimiet bereikt"
        else:
            ev_reason = "Doel al gehaald met goedkopere kwartieren"
        intervals.append({
            "start_utc": row["start_utc"],
            "start_local": row["start_local"],
            "duration_hours": d,
            "import_rate_eur_per_kwh": row["import_rate"],
            "export_rate_eur_per_kwh": row["export_rate"],
            "house_net_kw": round(row["house_net_kw"], 4),
            "battery_kw": round(row["battery_kw"], 4),
            "battery_action": row["battery_action"],
            "battery_reason": row["battery_reason"],
            "ev_kw": round(ev_kw, 4),
            "ev_reason": ev_reason,
            "grid_net_kw": round(net_after, 4),
            "over_limit": imp > limit + 1e-6,
        })

    soc_end = params["ev_start_soc_percent"] + delivered / params["ev_capacity_kwh"] * 100.0
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "READ_ONLY_DRY_RUN_DAY_COURSE",
        "classification": CLASSIFICATION,
        **{flag: False for flag in READ_ONLY_FLAGS},
        "execution_allowed": False,
        "status": "READY",
        "plan": {
            "target_date": target_date,
            "generated_at": report.get("generated_at"),
            "selected_policy_id": report.get("selected_policy_id"),
            "interval_count": len(intervals),
        },
        "parameters": params,
        "assumptions": list(ASSUMPTIONS),
        "warnings": warnings,
        "summary": {
            "ev_needed_kwh": round(needed_kwh, 3) if ev_active else 0.0,
            "ev_planned_kwh": round(delivered, 3),
            "ev_unmet_kwh": round(unmet, 3),
            "ev_target_reached": ev_active and unmet <= 0.001,
            "ev_end_soc_percent": round(min(100.0, soc_end), 1),
            "ev_blocked_intervals": blocked,
            "required_price_ceiling_eur_per_kwh": required_ceiling,
            "cost_no_control_eur": round(totals["baseline"], 4),
            "cost_battery_only_eur": round(totals["battery"], 4),
            "cost_with_ev_eur": round(totals["plan"], 4),
            "ev_cost_eur": round(totals["ev"], 4),
            "ev_cost_unmanaged_eur": round(totals["ev_naive"], 4),
            "ev_saving_vs_unmanaged_eur": round(totals["ev_naive"] - totals["ev"], 4),
            "peak_grid_import_kw": round(peak, 3),
            "peak_grid_import_unmanaged_kw": round(peak_naive, 3),
            "over_limit_intervals": over_limit,
            "over_limit_intervals_unmanaged": over_limit_naive,
        },
        "intervals": intervals,
    }
