#!/usr/bin/env python3
"""Evaluate versioned daily PV forecasts against realized PV energy."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from statistics import fmean
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    ROOT
    / "docs"
    / "evidence"
    / "solcast-pv-forecast-snapshots-2026-09-24_2026-09-30.json"
)
DEFAULT_OUTPUT = (
    ROOT / "docs" / "evidence" / "pv-forecast-quality-2026-09-24_2026-09-30.json"
)


def parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Issue time must include a UTC offset: {value}")
    return parsed


def _missing() -> dict[str, Any]:
    return {
        "status": "MISSING",
        "issue_time": None,
        "predicted_kwh": None,
        "actual_kwh": None,
        "error_kwh": None,
        "absolute_error_kwh": None,
        "absolute_percentage_error": None,
        "horizon_hours_to_target_end": None,
    }


def _evaluate(
    version: dict[str, Any] | None,
    *,
    actual_kwh: float,
    target_end: datetime,
) -> dict[str, Any]:
    if version is None:
        return _missing()
    issue = parse_instant(version["issue_time"])
    predicted = float(version["predicted_kwh"])
    error = predicted - actual_kwh
    return {
        "status": "EVALUATED",
        "issue_time": issue.isoformat(),
        "predicted_kwh": round(predicted, 6),
        "actual_kwh": round(actual_kwh, 6),
        "error_kwh": round(error, 6),
        "absolute_error_kwh": round(abs(error), 6),
        "absolute_percentage_error": round(abs(error) / actual_kwh * 100, 6)
        if actual_kwh > 0
        else None,
        "horizon_hours_to_target_end": round(
            (target_end - issue).total_seconds() / 3600, 6
        ),
    }


def _select_horizons(
    versions: list[dict[str, Any]], target_date: date, zone: ZoneInfo
) -> dict[str, dict[str, Any] | None]:
    target_start = datetime.combine(target_date, time.min, tzinfo=zone)
    previous_day = target_date - timedelta(days=1)
    day_ahead = [
        row
        for row in versions
        if row["forecast_kind"] == "tomorrow"
        and parse_instant(row["issue_time"]).astimezone(zone).date() == previous_day
        and parse_instant(row["issue_time"]) < target_start
    ]
    same_day = [
        row
        for row in versions
        if row["forecast_kind"] == "today"
        and parse_instant(row["issue_time"]).astimezone(zone).date() == target_date
    ]
    midnight = [
        row
        for row in same_day
        if parse_instant(row["issue_time"]).astimezone(zone)
        <= target_start + timedelta(minutes=10)
    ]
    morning_cutoff = target_start + timedelta(hours=8)
    morning = [
        row for row in same_day if parse_instant(row["issue_time"]) <= morning_cutoff
    ]
    return {
        "day_ahead": max(day_ahead, key=lambda row: parse_instant(row["issue_time"]), default=None),
        "same_day_midnight": max(midnight, key=lambda row: parse_instant(row["issue_time"]), default=None),
        "same_day_morning": max(morning, key=lambda row: parse_instant(row["issue_time"]), default=None),
    }


def analyze_forecast_quality(source: dict[str, Any]) -> dict[str, Any]:
    zone = ZoneInfo(source.get("timezone", "Europe/Brussels"))
    versions_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source.get("forecast_versions", []):
        parse_instant(row["issue_time"])
        if row["forecast_kind"] not in {"today", "tomorrow"}:
            raise ValueError(f"Unsupported forecast kind: {row['forecast_kind']}")
        versions_by_target[row["target_date"]].append(row)

    days = []
    for actual in sorted(source.get("actual_daily", []), key=lambda row: row["target_date"]):
        target_text = actual["target_date"]
        target = date.fromisoformat(target_text)
        target_end = datetime.combine(target + timedelta(days=1), time.min, tzinfo=zone)
        versions = sorted(
            versions_by_target.get(target_text, []),
            key=lambda row: parse_instant(row["issue_time"]),
        )
        selected = _select_horizons(versions, target, zone)
        actual_kwh = float(actual["actual_kwh"])
        predicted_values = [float(row["predicted_kwh"]) for row in versions]
        days.append(
            {
                "target_date": target_text,
                "target_start_local": datetime.combine(
                    target, time.min, tzinfo=zone
                ).isoformat(),
                "target_end_local": target_end.isoformat(),
                "actual_kwh": round(actual_kwh, 6),
                "actual_method": actual.get("method"),
                "forecast_version_count": len(versions),
                "revision_count": max(0, len(versions) - 1),
                "overwritten_forecasts_preserved": len(versions) > 1,
                "forecast_range_kwh": round(
                    max(predicted_values) - min(predicted_values), 6
                )
                if predicted_values
                else None,
                "versions": [
                    {
                        "forecast_kind": row["forecast_kind"],
                        "issue_time": parse_instant(row["issue_time"]).isoformat(),
                        "predicted_kwh": round(float(row["predicted_kwh"]), 6),
                    }
                    for row in versions
                ],
                "horizons": {
                    name: _evaluate(value, actual_kwh=actual_kwh, target_end=target_end)
                    for name, value in selected.items()
                },
            }
        )

    summary_by_horizon = {}
    for horizon in ("day_ahead", "same_day_midnight", "same_day_morning"):
        evaluated = [
            row["horizons"][horizon]
            for row in days
            if row["horizons"][horizon]["status"] == "EVALUATED"
        ]
        errors = [float(row["error_kwh"]) for row in evaluated]
        absolute = [float(row["absolute_error_kwh"]) for row in evaluated]
        percentages = [
            float(row["absolute_percentage_error"])
            for row in evaluated
            if row["absolute_percentage_error"] is not None
        ]
        summary_by_horizon[horizon] = {
            "evaluated_day_count": len(evaluated),
            "missing_day_count": len(days) - len(evaluated),
            "mean_error_kwh": round(fmean(errors), 6) if errors else None,
            "mean_absolute_error_kwh": round(fmean(absolute), 6) if absolute else None,
            "root_mean_square_error_kwh": round(
                math.sqrt(fmean(error * error for error in errors)), 6
            )
            if errors
            else None,
            "mean_absolute_percentage_error": round(fmean(percentages), 6)
            if percentages
            else None,
        }

    return {
        "schema_version": 1,
        "status": "VERIFIED_WITH_LIMITATIONS",
        "classification": "READ_ONLY_PV_FORECAST_QUALITY",
        "mode": "READ_ONLY",
        "timezone": str(zone),
        "period_start": days[0]["target_date"] if days else None,
        "period_end_inclusive": days[-1]["target_date"] if days else None,
        "quality": {
            "target_day_count": len(days),
            "forecast_version_count": sum(
                row["forecast_version_count"] for row in days
            ),
            "days_with_revisions": sum(
                row["overwritten_forecasts_preserved"] for row in days
            ),
            "day_ahead_missing_day_count": summary_by_horizon["day_ahead"][
                "missing_day_count"
            ],
            "source_retention_note": source.get("source_retention_note"),
        },
        "summary_by_horizon": summary_by_horizon,
        "days": days,
        "extensions": {
            "load_forecast": {
                "status": "NOT_IMPLEMENTED_SEPARATE_STREAM",
                "inferred_from_pv": False,
            },
            "ev_energy_forecast": {
                "status": "NOT_IMPLEMENTED_SEPARATE_STREAM",
                "inferred_from_pv": False,
            },
        },
        "limitations": [
            "The recorder raw-state window covers only seven completed target days, not the full Solcast long-term-statistics period.",
            "Daily forecast sensors are evaluated as whole-day energy; interval PV forecast series are not yet exported.",
            "The first target day lacks a preserved previous-day forecast because it predates the retained raw-state window.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    report = analyze_forecast_quality(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "target_days": report["quality"]["target_day_count"],
                "forecast_versions": report["quality"]["forecast_version_count"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
