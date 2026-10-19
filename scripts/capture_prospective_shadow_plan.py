#!/usr/bin/env python3
"""Capture and plan one prospective read-only shadow-controller day."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import math
import os
import statistics
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ZONE = ZoneInfo("Europe/Brussels")
QUARTER = timedelta(minutes=15)
FIVE_MINUTES = timedelta(minutes=5)
ALLOWED_INFORMATIONAL_PRICE_FLAGS = {"collapsed_identical_duplicate"}
PRICE_REFERENCE_EUR_PER_KWH = 0.277


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROSPECTIVE = load_module(
    "capture_prospective_builder", ROOT / "scripts" / "build_prospective_shadow_plan.py"
)
FEED = load_module(
    "capture_shadow_plan_feed", ROOT / "scripts" / "build_shadow_plan_feed.py"
)
JOINT = load_module(
    "capture_joint_control_dry_run", ROOT / "scripts" / "joint_control_dry_run.py"
)
INTEGRITY = load_module(
    "capture_joint_artifact_integrity",
    ROOT / "scripts" / "joint_artifact_integrity.py",
)


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


def finite_number(value: Any, field: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{field} must be a finite number")
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{field} must be a finite number") from error
    if not math.isfinite(number) or (nonnegative and number < 0):
        raise ValueError(f"{field} must be a finite non-negative number")
    return number


def target_bounds(target: date) -> tuple[datetime, datetime, list[datetime]]:
    start_local = datetime.combine(target, time.min, tzinfo=ZONE)
    end_local = datetime.combine(target + timedelta(days=1), time.min, tzinfo=ZONE)
    start = start_local.astimezone(timezone.utc)
    end = end_local.astimezone(timezone.utc)
    instants = []
    cursor = start
    while cursor < end:
        instants.append(cursor)
        cursor += QUARTER
    return start, end, instants


def _quarter_history(load_statistics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_start: dict[datetime, float] = {}
    for row in load_statistics:
        if not isinstance(row, dict):
            raise ValueError("load statistic rows must be objects")
        instant = datetime.fromtimestamp(
            finite_number(row.get("start"), "load_statistics.start") / 1000,
            tz=timezone.utc,
        )
        mean_w = finite_number(row.get("mean"), "load_statistics.mean", nonnegative=True)
        if instant in by_start and abs(by_start[instant] - mean_w) > 1e-9:
            raise ValueError("conflicting duplicate load statistics")
        by_start[instant] = mean_w

    quarters = []
    for instant in sorted(by_start):
        if instant.minute % 15 or instant.second or instant.microsecond:
            continue
        starts = [instant + index * FIVE_MINUTES for index in range(3)]
        if all(start in by_start for start in starts):
            quarters.append(
                {
                    "start": instant,
                    "kwh": sum(by_start[start] for start in starts) / 12000.0,
                }
            )
    return quarters


def build_load_forecast(
    target: date,
    load_statistics: list[dict[str, Any]],
    *,
    minimum_samples: int,
) -> dict[datetime, dict[str, Any]]:
    if minimum_samples <= 0:
        raise ValueError("minimum_samples must be positive")
    target_class = "weekend" if target.weekday() >= 5 else "weekday"
    matching: dict[tuple[int, int], list[float]] = defaultdict(list)
    all_days: dict[tuple[int, int], list[float]] = defaultdict(list)
    for row in _quarter_history(load_statistics):
        local = row["start"].astimezone(ZONE)
        if local.date() >= target:
            continue
        key = (local.hour, local.minute)
        day_class = "weekend" if local.weekday() >= 5 else "weekday"
        all_days[key].append(row["kwh"])
        if day_class == target_class:
            matching[key].append(row["kwh"])

    _, _, expected = target_bounds(target)
    output = {}
    for instant in expected:
        local = instant.astimezone(ZONE)
        key = (local.hour, local.minute)
        values = matching[key]
        method = "median_same_day_class"
        if len(values) < minimum_samples:
            values = all_days[key]
            method = "median_all_day_classes_fallback"
        if len(values) < minimum_samples:
            raise ValueError(
                f"insufficient load samples for {local.strftime('%H:%M')}: "
                f"{len(values)} < {minimum_samples}"
            )
        output[instant] = {
            "load_forecast_kwh": statistics.median(values),
            "load_sample_count": len(values),
            "load_forecast_method": method,
        }
    return output


def build_pv_quarters(
    target: date, detailed_forecast: Any
) -> dict[datetime, float]:
    if not isinstance(detailed_forecast, list):
        raise ValueError("PV forecast detailedForecast must be a list")
    start, end, expected = target_bounds(target)
    output: dict[datetime, float] = {}
    for row in detailed_forecast:
        if not isinstance(row, dict):
            raise ValueError("PV forecast rows must be objects")
        instant = parse_instant(row.get("period_start"), "PV forecast period_start")
        if not start <= instant < end:
            continue
        estimate_kw = finite_number(
            row.get("pv_estimate"), "PV forecast pv_estimate", nonnegative=True
        )
        if instant.minute not in {0, 30} or instant.second or instant.microsecond:
            raise ValueError("PV forecast must use aligned 30-minute intervals")
        for offset in (timedelta(0), QUARTER):
            quarter_start = instant + offset
            if quarter_start in output:
                raise ValueError("PV forecast contains duplicate target quarters")
            output[quarter_start] = estimate_kw * 0.25
    if sorted(output) != expected:
        raise ValueError("PV forecast does not exactly cover the complete target day")
    return output


def build_price_quarters(
    target: date, price_feed: dict[str, Any]
) -> dict[datetime, dict[str, Any]]:
    if not isinstance(price_feed, dict):
        raise ValueError("price feed must be an object")
    quality = price_feed.get("quality")
    if not isinstance(quality, dict):
        raise ValueError("price feed quality must be an object")
    if quality.get("stale") is not False:
        raise ValueError("price feed quality stale must be false")
    if quality.get("sequence_complete") is not True:
        raise ValueError("price feed quality sequence_complete must be true")
    rows = price_feed.get("upcoming_intervals")
    if not isinstance(rows, list):
        raise ValueError("price feed upcoming_intervals must be a list")
    start, end, expected = target_bounds(target)
    output = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("price rows must be objects")
        instant = parse_instant(row.get("start_utc"), "price start_utc")
        if not start <= instant < end:
            continue
        if instant in output:
            raise ValueError("price feed contains duplicate target quarters")
        interval_quality = row.get("quality_flags")
        if not isinstance(interval_quality, list) or any(
            not isinstance(flag, str) or not flag for flag in interval_quality
        ):
            raise ValueError("price interval quality_flags must be a list of strings")
        unsupported_quality = sorted(
            set(interval_quality) - ALLOWED_INFORMATIONAL_PRICE_FLAGS
        )
        if unsupported_quality:
            raise ValueError(
                "price interval quality_flags contain rejecting values: "
                + ", ".join(unsupported_quality)
            )
        output[instant] = {
            "market_price_eur_per_mwh": finite_number(
                row.get("market_price_eur_per_mwh"), "market price"
            ),
            "import_rate_eur_per_kwh": finite_number(
                row.get("ecopower_import_eur_per_kwh_incl_vat"), "import rate"
            ),
            "export_rate_eur_per_kwh": finite_number(
                row.get("ecopower_export_eur_per_kwh"), "export rate"
            ),
            "source_quality_flags": list(interval_quality),
        }
    if sorted(output) != expected:
        raise ValueError("price feed does not exactly cover the complete target day")
    return output


def build_home_assistant_price_feed(
    target: date,
    states: dict[str, dict[str, Any]],
    *,
    captured_at: datetime,
) -> dict[str, Any]:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware")
    captured_at = captured_at.astimezone(timezone.utc)
    start, end, expected = target_bounds(target)

    def parse_state(alias: str) -> tuple[dict[datetime, tuple[datetime, float]], set[datetime], datetime]:
        state = states.get(alias)
        if not isinstance(state, dict):
            raise ValueError(f"Home Assistant {alias} state is missing")
        attributes = state.get("attributes")
        if not isinstance(attributes, dict):
            raise ValueError(f"Home Assistant {alias} attributes are missing")
        if attributes.get("unit_of_measurement") not in {"€/kWh", "EUR/kWh"}:
            raise ValueError(f"Home Assistant {alias} must use EUR/kWh")
        rows = attributes.get("data")
        if not isinstance(rows, list):
            raise ValueError(f"Home Assistant {alias} data must be a list")
        observed_at = parse_instant(
            state.get("last_reported") or state.get("last_updated"),
            f"Home Assistant {alias} last_reported",
        )
        parsed: dict[datetime, tuple[datetime, float]] = {}
        duplicates: set[datetime] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"Home Assistant {alias} rows must be objects")
            row_start = parse_instant(row.get("start_time"), f"{alias} start_time")
            row_end = parse_instant(row.get("end_time"), f"{alias} end_time")
            if not start <= row_start < end:
                continue
            if row_end - row_start != QUARTER:
                raise ValueError(f"Home Assistant {alias} intervals must last 15 minutes")
            price = finite_number(row.get("price_per_kwh"), f"{alias} price_per_kwh")
            value = (row_end, price)
            existing = parsed.get(row_start)
            if existing is not None:
                if existing != value:
                    raise ValueError(f"Home Assistant {alias} has conflicting duplicate intervals")
                duplicates.add(row_start)
                continue
            parsed[row_start] = value
        if sorted(parsed) != expected:
            raise ValueError(f"Home Assistant {alias} does not cover the complete target day")
        return parsed, duplicates, observed_at

    market, market_duplicates, market_observed = parse_state("market_price")
    imports, import_duplicates, import_observed = parse_state("import_price")
    exports, export_duplicates, export_observed = parse_state("export_price")
    observations = {
        "market_price": market_observed,
        "import_price": import_observed,
        "export_price": export_observed,
    }
    if any(observed_at > captured_at for observed_at in observations.values()):
        raise ValueError("Home Assistant price observation is after capture")
    duplicate_starts = market_duplicates | import_duplicates | export_duplicates
    intervals = []
    for instant in expected:
        market_end, market_price = market[instant]
        import_end, import_price = imports[instant]
        export_end, export_price = exports[instant]
        if market_end != import_end or market_end != export_end:
            raise ValueError("Home Assistant price entity interval bounds disagree")
        intervals.append(
            {
                "start_utc": instant.isoformat(),
                "end_utc": market_end.isoformat(),
                "start_local": instant.astimezone(ZONE).isoformat(),
                "market_price_eur_per_mwh": round(market_price * 1000, 6),
                "ecopower_import_eur_per_kwh_incl_vat": import_price,
                "ecopower_export_eur_per_kwh": export_price,
                "quality_flags": (
                    ["collapsed_identical_duplicate"]
                    if instant in duplicate_starts
                    else []
                ),
            }
        )
    retrieved_at = min(market_observed, import_observed, export_observed)
    return {
        "schema_version": 1,
        "generated_at": retrieved_at.isoformat(),
        "mode": "READ_ONLY",
        "classification": "INDICATIVE_PRICE_SIGNAL_NOT_INVOICE",
        "physical_writes": False,
        "home_assistant_writes": False,
        "source": {
            "provider": "Home Assistant EPEX Spot Data + Ecopower Dynamic Prices",
            "retrieved_at": retrieved_at.isoformat(),
            "requested_start": start.isoformat(),
            "requested_end": end.isoformat(),
            "timezone": str(ZONE),
            "observed_at": {
                alias: observed_at.isoformat()
                for alias, observed_at in observations.items()
            },
        },
        "tariff_version": "HOME_ASSISTANT_ECOPOWER_DYNAMIC_PRICES",
        "reference": {
            "eur_per_kwh_incl_vat": PRICE_REFERENCE_EUR_PER_KWH,
            "classification": "OWNER_PROVIDED_INDICATIVE_AVERAGE",
            "comparison_limit": "NOT_AN_INVOICE_RECONSTRUCTION_OR_ALL_IN_FORECAST",
        },
        "quality": {
            "status": "COMPLETE",
            "stale": False,
            "missing_quarter_count": 0,
            "duplicate_quarter_count": len(duplicate_starts),
            "sequence_complete": True,
            "requested_window_complete": True,
            "requested_window_missing_quarter_count": 0,
        },
        "upcoming_intervals": intervals,
        "aggregates": {"daily": [], "weekly": [], "monthly": []},
    }


def build_capture_bundle(
    target: date,
    *,
    captured_at: datetime,
    states: dict[str, dict[str, Any]],
    load_statistics: list[dict[str, Any]],
    price_feed: dict[str, Any],
    minimum_load_samples: int,
    pv_forecast_max_age: timedelta = timedelta(hours=18),
    price_feed_max_age: timedelta = timedelta(hours=18),
    month_peak_max_age: timedelta = timedelta(days=31),
) -> dict[str, Any]:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware")
    captured_at = captured_at.astimezone(timezone.utc)
    start, end, expected = target_bounds(target)
    if captured_at >= start:
        raise ValueError("capture must complete before target day")

    soc = states.get("soc")
    peak = states.get("month_peak")
    pv_state = states.get("pv_forecast")
    if not all(isinstance(value, dict) for value in (soc, peak, pv_state)):
        raise ValueError("required Home Assistant states are missing")
    assert soc is not None and peak is not None and pv_state is not None
    soc_percent = finite_number(soc.get("state"), "battery SOC", nonnegative=True)
    if soc_percent > 100:
        raise ValueError("battery SOC must not exceed 100 percent")
    soc_observed = parse_instant(
        soc.get("last_reported") or soc.get("last_updated"),
        "battery SOC last_reported",
    )
    if soc_observed > captured_at:
        raise ValueError("battery SOC observation is after capture")
    month_peak = finite_number(peak.get("state"), "month peak", nonnegative=True)
    peak_observed = parse_instant(
        peak.get("last_reported") or peak.get("last_updated"),
        "month peak last_reported",
    )
    if peak_observed > captured_at:
        raise ValueError("month peak observation is after capture")
    peak_local = peak_observed.astimezone(ZONE)
    capture_local = captured_at.astimezone(ZONE)
    if (peak_local.year, peak_local.month) != (
        capture_local.year,
        capture_local.month,
    ):
        raise ValueError("month peak is not from current month")
    if captured_at - peak_observed > month_peak_max_age:
        raise ValueError("month peak is stale")
    pv_issued = parse_instant(pv_state.get("last_updated"), "PV forecast last_updated")
    if pv_issued > captured_at:
        raise ValueError("PV forecast issue time is after capture")
    if captured_at - pv_issued > pv_forecast_max_age:
        raise ValueError("PV forecast is stale")
    attributes = pv_state.get("attributes")
    if not isinstance(attributes, dict):
        raise ValueError("PV forecast attributes are missing")

    load = build_load_forecast(
        target, load_statistics, minimum_samples=minimum_load_samples
    )
    pv = build_pv_quarters(target, attributes.get("detailedForecast"))
    prices = build_price_quarters(target, price_feed)
    retrieved_at = parse_instant(
        price_feed.get("source", {}).get("retrieved_at"), "price retrieved_at"
    )
    if retrieved_at > captured_at:
        raise ValueError("price retrieval time is after capture")
    if captured_at - retrieved_at > price_feed_max_age:
        raise ValueError("price feed is stale")

    intervals = []
    fallback_count = 0
    for instant in expected:
        load_row = load[instant]
        price_row = prices[instant]
        fallback = load_row["load_forecast_method"].endswith("fallback")
        fallback_count += int(fallback)
        intervals.append(
            {
                "start_utc": instant.isoformat(),
                "start_local": instant.astimezone(ZONE).isoformat(),
                "duration_hours": 0.25,
                "load_forecast_kwh": load_row["load_forecast_kwh"],
                "pv_forecast_kwh": pv[instant],
                "market_price_eur_per_mwh": price_row[
                    "market_price_eur_per_mwh"
                ],
                "import_rate_eur_per_kwh": price_row["import_rate_eur_per_kwh"],
                "export_rate_eur_per_kwh": price_row["export_rate_eur_per_kwh"],
                "quality_flags": [],
                "source_quality_flags": price_row["source_quality_flags"],
                "load_sample_count": load_row["load_sample_count"],
                "load_forecast_method": load_row["load_forecast_method"],
            }
        )

    quality_flags = []
    if fallback_count:
        quality_flags.append("LOAD_FORECAST_USED_ALL_DAY_CLASS_FALLBACK")
    return {
        "schema_version": 1,
        "mode": "READ_ONLY_SHADOW_CAPTURE",
        "captured_at": captured_at.isoformat(),
        "target_date": target.isoformat(),
        "target_start_local": start.astimezone(ZONE).isoformat(),
        "target_end_local": end.astimezone(ZONE).isoformat(),
        "target_start_utc": start.isoformat(),
        "target_end_utc": end.isoformat(),
        "expected_interval_count": len(expected),
        "initial_soc": {
            "percent": soc_percent,
            "source": "MEASURED_HOME_ASSISTANT",
            "observed_at": soc_observed.isoformat(),
            "max_age_minutes": 10,
            "unit": "%",
        },
        "month_peak_to_date_kw": month_peak,
        "sources": {
            "pv_forecast_issued_at": pv_issued.isoformat(),
            "month_peak_observed_at": peak_observed.isoformat(),
            "load_forecast_issued_at": captured_at.isoformat(),
            "prices_issued_at": retrieved_at.isoformat(),
            "ev_mode": "OBSERVATION_ONLY_INCLUDED_IN_TOTAL_LOAD",
            "heat_pump_mode": "OBSERVATION_ONLY_INCLUDED_IN_TOTAL_LOAD",
            "load_forecast_method_version": "median_same_local_quarter_day_class_v1",
            "pv_forecast_native_resolution_minutes": 30,
            "market_provider": price_feed.get("source", {}).get("provider"),
        },
        "quality_flags": quality_flags,
        "intervals": intervals,
    }


def failure_report(
    target: date, *, generated_at: datetime, flag: str
) -> dict[str, Any]:
    start, end, _ = target_bounds(target)
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
        "target_date": target.isoformat(),
        "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
        "target_start_utc": start.isoformat(),
        "target_end_utc": end.isoformat(),
        "quality_flags": [flag],
        "capture_quality": "REJECTED_PROSPECTIVE_DAY",
        "plans": [],
        "intervals": [],
    }


def build_joint_planner_output(report: dict[str, Any]) -> dict[str, Any]:
    """Adapt the selected prospective battery policy to the joint dry-run contract."""
    if not isinstance(report, dict) or report.get("status") != "PLANNED":
        raise ValueError("source prospective plan must be PLANNED")
    selected_policy_id = report.get("selected_policy_id")
    plans = report.get("plans")
    if not isinstance(selected_policy_id, str) or not selected_policy_id:
        raise ValueError("source prospective plan has no selected policy")
    if not isinstance(plans, list):
        raise ValueError("source prospective plans must be a list")
    selected = next(
        (
            plan
            for plan in plans
            if isinstance(plan, dict) and plan.get("id") == selected_policy_id
        ),
        None,
    )
    if not isinstance(selected, dict) or selected.get("status") != "PLANNED":
        raise ValueError("selected prospective policy is unavailable")
    cap_kw = finite_number(
        selected.get("cap_kw"), "selected policy cap", nonnegative=True
    )
    schedule = selected.get("schedule")
    if not isinstance(schedule, list) or not schedule:
        raise ValueError("selected prospective policy schedule is missing")

    valid_from = parse_instant(
        report.get("target_start_utc"), "joint plan target_start_utc"
    )
    valid_until = parse_instant(
        report.get("target_end_utc"), "joint plan target_end_utc"
    )
    if valid_until <= valid_from:
        raise ValueError("joint plan target bounds are invalid")
    expected_starts = []
    expected = valid_from
    while expected < valid_until:
        expected_starts.append(expected)
        expected += timedelta(minutes=15)
    if expected != valid_until:
        raise ValueError("joint plan target bounds are not quarter aligned")

    intervals = []
    for row in schedule:
        if not isinstance(row, dict):
            raise ValueError("selected prospective schedule rows must be objects")
        start = parse_instant(row.get("start_utc"), "joint schedule start_utc")
        duration = finite_number(
            row.get("duration_hours"), "joint schedule duration_hours", nonnegative=True
        )
        if duration <= 0:
            raise ValueError("joint schedule duration_hours must be positive")
        charge_kwh = finite_number(
            row.get("charge_kwh"), "joint schedule charge_kwh", nonnegative=True
        )
        discharge_kwh = finite_number(
            row.get("discharge_kwh"),
            "joint schedule discharge_kwh",
            nonnegative=True,
        )
        base_net_kwh = finite_number(
            row.get("forecast_base_net_kwh"), "joint schedule forecast_base_net_kwh"
        )
        reason = row.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("joint schedule reason is required")
        intervals.append(
            {
                "start_utc": start.isoformat(),
                "end_utc": (start + timedelta(hours=duration)).isoformat(),
                "forecast_base_load_kw": base_net_kwh / duration,
                "battery_power_kw": (charge_kwh - discharge_kwh) / duration,
                "ev_power_kw": 0.0,
                "reason": reason,
            }
        )

    if [parse_instant(row["start_utc"], "joint interval start_utc") for row in intervals] != expected_starts:
        raise ValueError("selected prospective schedule does not cover the target day")
    if any(
        parse_instant(row["end_utc"], "joint interval end_utc")
        - parse_instant(row["start_utc"], "joint interval start_utc")
        != timedelta(minutes=15)
        for row in intervals
    ):
        raise ValueError("selected prospective schedule is not quarter-hourly")

    return {
        "schema_version": 1,
        "plan_id": f"prospective-shadow-{report.get('target_date')}",
        "generated_at": report.get("generated_at"),
        "valid_from_utc": valid_from.isoformat(),
        "valid_until_utc": valid_until.isoformat(),
        "selected_policy_id": selected_policy_id,
        "shared_grid_import_limit_kw": cap_kw,
        "intervals": intervals,
    }


def summarize_joint_capture(
    report: dict[str, Any],
    intents: dict[str, Any],
    review: dict[str, Any],
    proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    decisions = review.get("decisions") if isinstance(review, dict) else None
    decision_rows = decisions if isinstance(decisions, list) else []
    reason_counts: dict[str, int] = defaultdict(int)
    for decision in decision_rows:
        if not isinstance(decision, dict):
            continue
        reasons = decision.get("reasons")
        if isinstance(reasons, list):
            for reason in reasons:
                if isinstance(reason, str):
                    reason_counts[reason] += 1
    proposal_set_sha256 = hashlib.sha256(
        json.dumps(
            proposals,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "mode": "PROSPECTIVE_JOINT_CONTROL_DRY_RUN",
        "classification": "PRIVACY_SAFE_JOINT_CONTROL_EVIDENCE_NO_EXECUTION",
        "status": review.get("status") if isinstance(review, dict) else "REJECTED",
        "target_date": report.get("target_date") if isinstance(report, dict) else None,
        "source_plan_id": intents.get("source_plan_id") if isinstance(intents, dict) else None,
        "selected_policy_id": intents.get("selected_policy_id") if isinstance(intents, dict) else None,
        "valid_from_utc": intents.get("valid_from_utc") if isinstance(intents, dict) else None,
        "valid_until_utc": intents.get("valid_until_utc") if isinstance(intents, dict) else None,
        "intent_status": intents.get("status") if isinstance(intents, dict) else "NO_ACTION",
        "intent_count": len(intents.get("intents", [])) if isinstance(intents, dict) else 0,
        "accepted_decision_count": sum(
            decision.get("decision") == "ACCEPTED_DRY_RUN"
            for decision in decision_rows
            if isinstance(decision, dict)
        ),
        "rejected_decision_count": sum(
            decision.get("decision") != "ACCEPTED_DRY_RUN"
            for decision in decision_rows
            if isinstance(decision, dict)
        ),
        "proposal_count": len(proposals),
        "proposal_set_sha256": proposal_set_sha256,
        "reason_counts": dict(sorted(reason_counts.items())),
        "execution_allowed": False,
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "privacy": {
            "quarter_household_profile_included": False,
            "device_identifiers_included": False,
        },
    }


def build_joint_capture_artifacts(
    report: dict[str, Any],
    *,
    control_inputs: dict[str, Any] | None,
    safety_state: dict[str, Any] | None,
    now: datetime,
) -> dict[str, Any]:
    """Build joint intents, a safety review and non-dispatchable proposals."""
    control_generation = (
        control_inputs.get("snapshot_generation_id")
        if isinstance(control_inputs, dict)
        else None
    )
    safety_generation = (
        safety_state.get("snapshot_generation_id")
        if isinstance(safety_state, dict)
        else None
    )
    if (
        not isinstance(control_generation, str)
        or not control_generation
        or control_generation != safety_generation
    ):
        control_inputs = None
        safety_state = None
    try:
        planner_output = build_joint_planner_output(report)
    except (KeyError, TypeError, ValueError, OverflowError):
        planner_output = {}
    intents = JOINT.build_intent_bundle(
        planner_output,
        control_inputs if isinstance(control_inputs, dict) else {},
        now=now,
    )
    review = JOINT.supervise_intents(
        intents,
        safety_state if isinstance(safety_state, dict) else {},
        now=now,
    )
    proposals = JOINT.build_dry_run_proposals(review)
    return {
        "intents": intents,
        "review": review,
        "proposals": proposals,
        "summary": summarize_joint_capture(report, intents, review, proposals),
    }


def extract_tool_data(result: Any) -> dict[str, Any]:
    dumped = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    structured = dumped.get("structured_content") if isinstance(dumped, dict) else None
    if isinstance(structured, dict) and isinstance(structured.get("data"), dict):
        return structured["data"]
    if isinstance(dumped, dict):
        for item in dumped.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                parsed = json.loads(item["text"])
                if isinstance(parsed, dict):
                    if isinstance(parsed.get("data"), dict):
                        return parsed["data"]
                    return parsed
    raise ValueError("MCP result did not contain structured Home Assistant data")


async def fetch_live_inputs(
    *,
    config: dict[str, Any],
    entity_config: dict[str, Any],
    captured_at: datetime,
    wrapper: str,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    entities = entity_config.get("entities")
    if not isinstance(entities, dict):
        raise ValueError("private entity config must contain entities")
    aliases = ["soc", "month_peak", "pv_forecast"]
    price_aliases = ["market_price", "import_price", "export_price"]
    configured_price_aliases = [alias for alias in price_aliases if alias in entities]
    if configured_price_aliases and len(configured_price_aliases) != len(price_aliases):
        raise ValueError("private entity config must contain all Home Assistant price entities")
    aliases.extend(configured_price_aliases)
    state_ids = [entities[alias] for alias in aliases]
    params = StdioServerParameters(command=wrapper, args=[])
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            state_result = await session.call_tool(
                "ha_get_state",
                {
                    "entity_id": state_ids,
                    "fields": [
                        "entity_id",
                        "state",
                        "attributes",
                        "last_updated",
                        "last_reported",
                    ],
                },
            )
            state_data = extract_tool_data(state_result)
            raw_states = state_data.get("states")
            if not isinstance(raw_states, dict):
                raise ValueError("Home Assistant state response is incomplete")
            states = {alias: raw_states[entities[alias]] for alias in aliases}

            history_days = int(config.get("load_history_days", 14))
            history_start = captured_at - timedelta(days=history_days)
            offset = 0
            statistics: list[dict[str, Any]] = []
            while True:
                history_result = await session.call_tool(
                    "ha_get_history",
                    {
                        "entity_ids": entities["load_power"],
                        "source": "statistics",
                        "start_time": history_start.isoformat(),
                        "end_time": captured_at.isoformat(),
                        "period": "5minute",
                        "statistic_types": ["mean"],
                        "limit": 1000,
                        "offset": offset,
                    },
                )
                history_data = extract_tool_data(history_result)
                entity_rows = history_data.get("entities")
                if not isinstance(entity_rows, list) or len(entity_rows) != 1:
                    raise ValueError("Home Assistant load statistics response is incomplete")
                page = entity_rows[0].get("statistics")
                if not isinstance(page, list):
                    raise ValueError("Home Assistant load statistics rows are missing")
                statistics.extend(page)
                if not history_data.get("has_more"):
                    break
                next_offset = history_data.get("next_offset")
                if not isinstance(next_offset, int) or next_offset <= offset:
                    raise ValueError("Home Assistant statistics pagination did not advance")
                offset = next_offset
    return states, statistics


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


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


def persist_joint_capture_artifacts(
    captures_dir: Path,
    target: date,
    artifacts: dict[str, Any],
    *,
    integrity_key: bytes | None,
) -> dict[str, Path]:
    paths = {
        "intents": captures_dir / f"joint-intents-{target}.json",
        "review": captures_dir / f"joint-review-{target}.json",
        "proposals": captures_dir / f"joint-proposals-{target}.json",
        "summary": captures_dir / f"joint-summary-{target}.json",
    }
    manifest_path = captures_dir / f"joint-manifest-{target}.json"
    if integrity_key is None:
        manifest_path.unlink(missing_ok=True)
    for name, path in paths.items():
        value = artifacts.get(name)
        if name == "proposals":
            if not isinstance(value, list):
                raise ValueError("joint proposals must be a list")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            try:
                temporary.write_text(
                    json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            continue
        if not isinstance(value, dict):
            raise ValueError(f"joint {name} must be an object")
        write_json_atomic(path, value)
    if integrity_key is not None:
        manifest = INTEGRITY.build_manifest(target, artifacts, key=integrity_key)
        write_json_atomic(manifest_path, manifest)
        paths["manifest"] = manifest_path
    return paths


def update_index(path: Path, report: dict[str, Any]) -> None:
    index = load_json(path) if path.exists() else {"schema_version": 1, "captures": []}
    captures = index.get("captures")
    if not isinstance(captures, list):
        raise ValueError("capture index must contain a captures list")
    entry = {
        "target_date": report.get("target_date"),
        "capture_quality": report.get("capture_quality"),
        "plan_status": report.get("status"),
        "plan_generated_at": report.get("generated_at"),
        "target_start_utc": report.get("target_start_utc"),
        "interval_count": report.get("interval_count", 0),
        "quality_flags": report.get("quality_flags", []),
    }
    captures = [row for row in captures if row.get("target_date") != entry["target_date"]]
    captures.append(entry)
    index["captures"] = sorted(captures, key=lambda row: str(row.get("target_date")))
    write_json_atomic(path, index)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-date", type=date.fromisoformat)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/validation/prospective-shadow-capture.json"),
    )
    parser.add_argument(
        "--price-feed",
        type=Path,
        default=Path("data/raw/day-ahead-prices.json"),
    )
    parser.add_argument(
        "--entity-config",
        type=Path,
        default=Path("config/private/prospective-shadow-capture-entities.json"),
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
        "--captures-dir",
        type=Path,
        default=Path("data/raw/shadow-validation-captures"),
    )
    parser.add_argument(
        "--plan-directory", type=Path, default=Path("data/raw")
    )
    parser.add_argument(
        "--joint-control-inputs",
        type=Path,
        default=Path("config/private/prospective-joint-control-inputs.json"),
    )
    parser.add_argument(
        "--joint-safety-state",
        type=Path,
        default=Path("config/private/prospective-joint-safety-state.json"),
    )
    parser.add_argument(
        "--joint-integrity-key",
        type=Path,
        default=Path("config/private/joint-artifact-hmac.key"),
    )
    parser.add_argument(
        "--wrapper",
        default=str(Path.home() / ".hermes/bin/home-assistant-mcp-wrapper"),
    )
    parser.add_argument("--state-step-kwh", type=float, default=0.25)
    args = parser.parse_args()

    capture_started_at = datetime.now(timezone.utc)
    target = args.target_date or (
        capture_started_at.astimezone(ZONE).date() + timedelta(days=1)
    )
    captured_at = capture_started_at
    exit_code = 0
    bundle: dict[str, Any] | None = None
    price_feed: dict[str, Any] | None = None
    try:
        config = load_json(args.config)
        entity_config = load_json(args.entity_config)
        states, statistics_rows = asyncio.run(
            fetch_live_inputs(
                config=config,
                entity_config=entity_config,
                captured_at=capture_started_at,
                wrapper=args.wrapper,
            )
        )
        captured_at = datetime.now(timezone.utc)
        price_errors = []
        if all(alias in states for alias in ("market_price", "import_price", "export_price")):
            try:
                price_feed = build_home_assistant_price_feed(
                    target,
                    states,
                    captured_at=captured_at,
                )
            except Exception as error:
                price_errors.append(f"Home Assistant prices: {type(error).__name__}: {error}")
        if price_feed is None:
            try:
                price_feed = load_json(args.price_feed)
            except Exception as error:
                price_errors.append(f"local price feed: {type(error).__name__}: {error}")
        if price_feed is None:
            raise ValueError("; ".join(price_errors) or "no price source configured")
        bundle = build_capture_bundle(
            target,
            captured_at=captured_at,
            states=states,
            load_statistics=statistics_rows,
            price_feed=price_feed,
            minimum_load_samples=int(config.get("minimum_load_samples", 3)),
            pv_forecast_max_age=timedelta(
                hours=float(config.get("pv_forecast_max_age_hours", 18))
            ),
            price_feed_max_age=timedelta(
                hours=float(config.get("price_feed_max_age_hours", 18))
            ),
            month_peak_max_age=timedelta(
                hours=float(config.get("month_peak_max_age_hours", 744))
            ),
        )
        battery = load_json(args.battery_config)["battery"]
        marginal = load_json(args.marginal_costs)
        report = PROSPECTIVE.build_prospective_plan(
            bundle,
            battery=battery,
            degradation_rate=float(
                marginal["central_degradation_eur_per_discharged_kwh"]
            ),
            state_step_kwh=args.state_step_kwh,
            planning_completed_at=datetime.now(timezone.utc),
        )
    except Exception as error:  # fail closed at the scheduled integration boundary
        flag = f"CAPTURE_PIPELINE_ERROR:{type(error).__name__}:{error}"
        report = failure_report(target, generated_at=datetime.now(timezone.utc), flag=flag)
        exit_code = 2

    args.captures_dir.mkdir(parents=True, exist_ok=True)
    if bundle is not None:
        write_json_atomic(args.captures_dir / f"bundle-{target}.json", bundle)
    write_json_atomic(args.captures_dir / f"plan-{target}.json", report)
    write_json_atomic(
        args.captures_dir / f"summary-{target}.json",
        PROSPECTIVE.privacy_safe_summary(report),
    )
    write_json_atomic(
        args.captures_dir / f"entity-payload-{target}.json",
        FEED.build_plan_entity_payload(report, price_feed=price_feed),
    )
    write_json_atomic(
        args.plan_directory / f"shadow-controller-plan-{target}.json", report
    )
    try:
        joint_control_inputs = (
            load_json(args.joint_control_inputs)
            if args.joint_control_inputs.exists()
            else None
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        joint_control_inputs = None
    try:
        joint_safety_state = (
            load_json(args.joint_safety_state)
            if args.joint_safety_state.exists()
            else None
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        joint_safety_state = None
    try:
        joint_integrity_key = INTEGRITY.load_key(args.joint_integrity_key)
    except (OSError, UnicodeError, ValueError):
        joint_integrity_key = None
        joint_control_inputs = None
        joint_safety_state = None
    joint_artifacts = build_joint_capture_artifacts(
        report,
        control_inputs=joint_control_inputs,
        safety_state=joint_safety_state,
        now=datetime.now(timezone.utc),
    )
    persist_joint_capture_artifacts(
        args.captures_dir,
        target,
        joint_artifacts,
        integrity_key=joint_integrity_key,
    )
    update_index(args.captures_dir / "index.json", report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "capture_quality": report["capture_quality"],
                "target_date": target.isoformat(),
                "generated_at": report["generated_at"],
                "quality_flags": report.get("quality_flags", []),
                "joint_dry_run_status": joint_artifacts["review"]["status"],
                "joint_proposal_count": len(joint_artifacts["proposals"]),
                "execution_allowed": False,
            },
            ensure_ascii=False,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
