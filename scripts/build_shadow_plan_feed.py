#!/usr/bin/env python3
"""Build a privacy-minimized read-only Home Assistant shadow-plan feed."""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

READ_ONLY_FLAGS = (
    "physical_writes",
    "home_assistant_writes",
    "sma_writes",
    "smappee_writes",
)
INTERVAL_FIELDS = (
    "start_utc",
    "duration_hours",
    "action",
    "reason",
    "planned_grid_import_kw",
)
SUPPORTED_ACTIONS = frozenset(
    {
        "CHARGE_FROM_GRID",
        "STORE_PV_SURPLUS",
        "DISCHARGE_TO_LOAD",
        "HOLD",
        "NO_ACTION",
    }
)
SUPPORTED_STATUSES = frozenset({"PLANNED", "NO_ACTION"})
PRICE_FEED_MAX_AGE = timedelta(hours=36)


def _aware_utc(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be a valid ISO timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _finite_number(value: Any, field: str, *, positive: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a finite number") from error
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    if positive and number <= 0:
        raise ValueError(f"{field} must be positive")
    if not positive and number < 0:
        raise ValueError(f"{field} must be non-negative")
    return number


def _finite_signed_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a finite number") from error
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def _public_price_aggregates(price_feed: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    aggregates = price_feed.get("aggregates")
    if not isinstance(aggregates, dict):
        raise ValueError("price feed aggregates must be an object")
    limits = {"daily": 12, "weekly": 8, "monthly": 6}
    output: dict[str, list[dict[str, Any]]] = {}
    for key, limit in limits.items():
        rows = aggregates.get(key)
        if not isinstance(rows, list):
            raise ValueError(f"price feed aggregates.{key} must be a list")
        public_rows = []
        for row in rows[-limit:]:
            if not isinstance(row, dict) or not isinstance(row.get("period"), str):
                raise ValueError(f"price feed aggregates.{key} contains an invalid row")
            public_rows.append(
                {
                    "period": row["period"],
                    "interval_count": int(row.get("interval_count")),
                    "expected_interval_count": int(row.get("expected_interval_count")),
                    "partial_period": row.get("partial_period") is True,
                    "average_eur_per_kwh": _finite_signed_number(
                        row.get("average_eur_per_kwh_incl_vat"),
                        f"aggregates.{key}.average_eur_per_kwh_incl_vat",
                    ),
                    "difference_vs_reference_eur_per_kwh": _finite_signed_number(
                        row.get("difference_vs_reference_eur_per_kwh"),
                        f"aggregates.{key}.difference_vs_reference_eur_per_kwh",
                    ),
                }
            )
        output[key] = public_rows
    return output


def _validate_report_structure(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise ValueError("shadow plan must be a JSON object")
    plans = report.get("plans")
    if not isinstance(plans, list):
        raise ValueError("plans must be a list")
    if any(not isinstance(plan, dict) for plan in plans):
        raise ValueError("every plan entry must be an object")
    return report


def _validate_read_only(report: dict[str, Any]) -> None:
    if report.get("mode") != "READ_ONLY_SHADOW":
        raise ValueError("shadow plan must use READ_ONLY_SHADOW mode")
    if any(report.get(flag) is not False for flag in READ_ONLY_FLAGS):
        raise ValueError("shadow plan contains or omits a disabled write capability")


def _selected_schedule(report: dict[str, Any]) -> list[dict[str, Any]]:
    selected_policy_id = report.get("selected_policy_id")
    selected = next(
        (
            plan
            for plan in report.get("plans", [])
            if plan.get("id") == selected_policy_id
        ),
        None,
    )
    if selected is None or selected.get("status") != "PLANNED":
        raise ValueError("selected planned policy is missing")
    schedule = selected.get("schedule")
    if not isinstance(schedule, list):
        raise ValueError("selected policy schedule is missing")
    if any(not isinstance(row, dict) for row in schedule):
        raise ValueError("every schedule interval must be an object")
    expected_count = report.get("interval_count")
    if not isinstance(expected_count, int) or len(schedule) != expected_count:
        raise ValueError("selected schedule interval count does not match report")
    return schedule


def _public_interval(row: dict[str, Any]) -> tuple[dict[str, Any], datetime]:
    missing = [field for field in INTERVAL_FIELDS if field not in row]
    if missing:
        raise ValueError(f"schedule interval misses required fields: {', '.join(missing)}")
    start = _aware_utc(row["start_utc"], "start_utc")
    duration = _finite_number(row["duration_hours"], "duration_hours", positive=True)
    planned_grid_import = _finite_number(
        row["planned_grid_import_kw"], "planned_grid_import_kw"
    )
    action = str(row["action"])
    if action not in SUPPORTED_ACTIONS:
        raise ValueError(f"action is not supported: {action}")
    reason = row["reason"]
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be a non-empty string")
    return (
        {
            "start_utc": start.isoformat(),
            "duration_hours": duration,
            "action": action,
            "reason": reason,
            "planned_grid_import_kw": planned_grid_import,
        },
        start,
    )


def _public_schedule(
    report: dict[str, Any],
    target_start: datetime,
    target_end: datetime,
) -> list[dict[str, Any]]:
    output = []
    cursor = target_start
    for row in _selected_schedule(report):
        public, start = _public_interval(row)
        if start != cursor:
            raise ValueError("schedule intervals must be contiguous from target_start_utc")
        try:
            cursor = start + timedelta(hours=public["duration_hours"])
        except OverflowError as error:
            raise ValueError("duration_hours is outside the supported range") from error
        if cursor > target_end:
            raise ValueError("schedule interval falls outside target_end_utc")
        output.append(public)
    if cursor != target_end:
        raise ValueError("schedule final interval does not match target_end_utc")
    return output


def _public_price_timeline(
    price_feed: dict[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    if price_feed is None:
        return {
            "price_source": None,
            "price_tariff_version": None,
            "price_reference_eur_per_kwh": None,
            "prices": [],
            "price_aggregates": {"daily": [], "weekly": [], "monthly": []},
            "price_quality": {"status": "UNAVAILABLE", "flags": ["PRICE_FEED_MISSING"]},
        }
    if not isinstance(price_feed, dict):
        raise ValueError("price feed must be a JSON object")
    if price_feed.get("mode") != "READ_ONLY":
        raise ValueError("price feed must use READ_ONLY mode")
    if price_feed.get("physical_writes") is not False:
        raise ValueError("price feed must disable physical writes")
    if price_feed.get("home_assistant_writes") is not False:
        raise ValueError("price feed must disable Home Assistant writes")
    quality = price_feed.get("quality")
    if not isinstance(quality, dict):
        raise ValueError("price feed quality must be an object")
    if quality.get("stale") is not False or quality.get("sequence_complete") is not True:
        return {
            "price_source": None,
            "price_tariff_version": None,
            "price_reference_eur_per_kwh": None,
            "prices": [],
            "price_aggregates": {"daily": [], "weekly": [], "monthly": []},
            "price_quality": {
                "status": "REJECTED",
                "flags": ["SOURCE_STALE_OR_INCOMPLETE"],
            },
        }
    source = price_feed.get("source")
    reference = price_feed.get("reference")
    rows = price_feed.get("upcoming_intervals")
    if not isinstance(source, dict) or not isinstance(reference, dict):
        raise ValueError("price feed metadata is incomplete")
    retrieved_at = _aware_utc(source.get("retrieved_at"), "source.retrieved_at")
    if retrieved_at > now:
        return {
            "price_source": source.get("provider"),
            "price_tariff_version": price_feed.get("tariff_version"),
            "price_reference_eur_per_kwh": None,
            "prices": [],
            "price_aggregates": {"daily": [], "weekly": [], "monthly": []},
            "price_quality": {"status": "REJECTED", "flags": ["FUTURE_RETRIEVAL"]},
        }
    if now - retrieved_at > PRICE_FEED_MAX_AGE:
        return {
            "price_source": source.get("provider"),
            "price_tariff_version": price_feed.get("tariff_version"),
            "price_reference_eur_per_kwh": None,
            "prices": [],
            "price_aggregates": {"daily": [], "weekly": [], "monthly": []},
            "price_quality": {"status": "REJECTED", "flags": ["STALE"]},
        }
    if not isinstance(rows, list):
        raise ValueError("upcoming_intervals must be a list")
    reference_rate = _finite_number(
        reference.get("eur_per_kwh_incl_vat"),
        "reference.eur_per_kwh_incl_vat",
    )
    output = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("every price interval must be an object")
        start = _aware_utc(row.get("start_utc"), "price.start_utc")
        end = _aware_utc(row.get("end_utc"), "price.end_utc")
        if end <= start:
            raise ValueError("price interval end must be after start")
        if end <= now:
            continue
        output.append(
            {
                "start_utc": start.isoformat(),
                "duration_hours": (end - start).total_seconds() / 3600,
                "market_eur_per_mwh": _finite_signed_number(
                    row.get("market_price_eur_per_mwh"),
                    "price.market_price_eur_per_mwh",
                ),
                "import_eur_per_kwh": _finite_signed_number(
                    row.get("ecopower_import_eur_per_kwh_incl_vat"),
                    "price.ecopower_import_eur_per_kwh_incl_vat",
                ),
                "export_eur_per_kwh": _finite_signed_number(
                    row.get("ecopower_export_eur_per_kwh"),
                    "price.ecopower_export_eur_per_kwh",
                ),
            }
        )
    return {
        "price_source": source.get("provider"),
        "price_tariff_version": price_feed.get("tariff_version"),
        "price_reference_eur_per_kwh": reference_rate,
        "prices": output,
        "price_aggregates": _public_price_aggregates(price_feed),
        "price_quality": {
            "status": "ACCEPTED",
            "flags": [],
            "retrieved_at": retrieved_at.isoformat(),
        },
    }


def unavailable_plan_entity_payload(reason: str) -> dict[str, Any]:
    return {
        "state": "NO_ACTION",
        "mode": "READ_ONLY_SHADOW",
        "classification": "PROPOSED_PLAN_NO_CONTROL",
        "physical_writes": False,
        "home_assistant_writes": False,
        "target_date": None,
        "target_start_utc": None,
        "target_end_utc": None,
        "generated_at": None,
        "selected_policy_id": None,
        "reason": reason,
        "schedule": [],
    }


def build_plan_entity_payload(
    report: dict[str, Any],
    *,
    price_feed: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return the minimal attribute payload consumed by the Lovelace card."""
    report = _validate_report_structure(report)
    _validate_read_only(report)
    status = str(report.get("status") or "NO_ACTION")
    if status not in SUPPORTED_STATUSES:
        raise ValueError(f"status is not supported: {status}")
    reason = report.get("reason")
    _aware_utc(report.get("generated_at"), "generated_at")
    target_start = _aware_utc(report.get("target_start_utc"), "target_start_utc")
    target_end = _aware_utc(report.get("target_end_utc"), "target_end_utc")
    if target_end <= target_start:
        raise ValueError("target_end_utc must be after target_start_utc")
    schedule: list[dict[str, Any]] = []
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    if status == "PLANNED":
        if target_end <= current:
            status = "NO_ACTION"
            reason = "PLAN_EXPIRED"
        else:
            schedule = _public_schedule(report, target_start, target_end)

    return {
        "state": status,
        "mode": "READ_ONLY_SHADOW",
        "classification": "PROPOSED_PLAN_NO_CONTROL",
        "physical_writes": False,
        "home_assistant_writes": False,
        "target_date": report.get("target_date"),
        "target_start_utc": report.get("target_start_utc"),
        "target_end_utc": report.get("target_end_utc"),
        "generated_at": report.get("generated_at"),
        "selected_policy_id": report.get("selected_policy_id"),
        "reason": reason,
        "schedule": schedule,
    } | _public_price_timeline(price_feed, now=current)


def build_latest_plan_entity_payload(
    plan_directory: Path,
    *,
    price_feed: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    candidates = []
    for path in plan_directory.glob("shadow-controller-plan-*.json"):
        report = _validate_report_structure(
            json.loads(path.read_text(encoding="utf-8"))
        )
        target_end = _aware_utc(report.get("target_end_utc"), "target_end_utc")
        candidates.append((target_end, path.name, report))
    if not candidates:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        return unavailable_plan_entity_payload("PLAN_UNAVAILABLE") | _public_price_timeline(
            price_feed,
            now=current.astimezone(timezone.utc),
        )
    _, _, latest = max(candidates, key=lambda item: (item[0], item[1]))
    return build_plan_entity_payload(latest, price_feed=price_feed, now=now)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--price-feed",
        type=Path,
        default=Path("web-dashboard/data/day-ahead-prices.json"),
    )
    parser.add_argument("--now")
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8"))
    price_feed = (
        json.loads(args.price_feed.read_text(encoding="utf-8"))
        if args.price_feed.exists()
        else None
    )
    now = _aware_utc(args.now, "now") if args.now else None
    payload = build_plan_entity_payload(report, price_feed=price_feed, now=now)
    _write_json_atomic(args.output, payload)
    print(
        json.dumps(
            {
                "state": payload["state"],
                "target_date": payload["target_date"],
                "interval_count": len(payload["schedule"]),
                "output": str(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
