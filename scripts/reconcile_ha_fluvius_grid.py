#!/usr/bin/env python3
"""Reconcile privacy-safe Home Assistant grid totals with Fluvius intervals."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

QUARTER = timedelta(minutes=15)
HOUR = timedelta(hours=1)
DATE_TIME_FORMAT = "%d-%m-%Y %H:%M:%S"


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp lacks timezone: {value}")
    return parsed.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def hour_floor(value: datetime) -> datetime:
    return value.replace(minute=0, second=0, microsecond=0)


def parse_volume(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def classify_flow(register: str) -> str:
    lowered = register.casefold()
    if lowered.startswith("afname"):
        return "import"
    if lowered.startswith("injectie"):
        return "export"
    return "unknown"


def utc_start_candidates(
    local_start: datetime, local_end: datetime, zone: ZoneInfo
) -> list[datetime]:
    candidates = set()
    for fold in (0, 1):
        utc_start = local_start.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if (
            utc_start.astimezone(zone).replace(tzinfo=None) == local_start
            and (utc_start + QUARTER).astimezone(zone).replace(tzinfo=None) == local_end
        ):
            candidates.add(utc_start)
    return sorted(candidates)


def load_fluvius_intervals(
    path: str | Path, timezone_name: str = "Europe/Brussels"
) -> list[dict[str, Any]]:
    zone = ZoneInfo(timezone_name)
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    if not rows or len(rows) % 2:
        raise ValueError("Fluvius CSV must contain paired import/export rows")

    intervals = []
    used_utc_starts: set[datetime] = set()
    for index in range(0, len(rows), 2):
        pair = rows[index : index + 2]
        starts = {
            datetime.strptime(
                f'{row["Van (datum)"]} {row["Van (tijdstip)"]}', DATE_TIME_FORMAT
            )
            for row in pair
        }
        ends = {
            datetime.strptime(
                f'{row["Tot (datum)"]} {row["Tot (tijdstip)"]}', DATE_TIME_FORMAT
            )
            for row in pair
        }
        if len(starts) != 1 or len(ends) != 1:
            raise ValueError(f"Fluvius row pair {index // 2} has mismatched bounds")
        candidates = [
            candidate
            for candidate in utc_start_candidates(min(starts), min(ends), zone)
            if candidate not in used_utc_starts
        ]
        if not candidates:
            raise ValueError(f"Fluvius row pair {index // 2} has no UTC mapping")
        start_utc = candidates[0]
        used_utc_starts.add(start_utc)
        values: dict[str, float | None] = {"import": None, "export": None}
        statuses = set()
        for row in pair:
            flow = classify_flow(row["Register"])
            if flow not in values:
                raise ValueError(f"Unknown Fluvius register in row pair {index // 2}")
            values[flow] = parse_volume(row["Volume"])
            statuses.add(row["Validatiestatus"].strip() or "UNKNOWN")
        if values["import"] is None or values["export"] is None:
            raise ValueError(f"Fluvius row pair {index // 2} lacks a grid flow")
        intervals.append(
            {
                "start_utc": iso_utc(start_utc),
                "import_kwh": values["import"],
                "export_kwh": values["export"],
                "estimated": any(
                    status.casefold() != "uitgelezen" for status in statuses
                ),
            }
        )
    return intervals


def comparison_summary(
    rows: list[dict[str, Any]], flow: str
) -> dict[str, float | None]:
    ha_total = round(sum(row[f"ha_{flow}_kwh"] for row in rows), 6)
    fluvius_total = round(sum(row[f"fluvius_{flow}_kwh"] for row in rows), 6)
    difference = round(ha_total - fluvius_total, 6)
    difference_percentage = (
        round(difference / fluvius_total * 100, 6) if fluvius_total else None
    )
    return {
        "ha_total_kwh": ha_total,
        "fluvius_total_kwh": fluvius_total,
        "difference_kwh": difference,
        "difference_percentage_of_fluvius": difference_percentage,
    }


def reconcile_grid_data(
    ha_export: dict[str, Any], fluvius_intervals: list[dict[str, Any]]
) -> dict[str, Any]:
    ha_import = {
        parse_utc(row["start_utc"]): row.get("energy_kwh")
        for row in ha_export["series"]["grid_import"]
    }
    ha_exported = {
        parse_utc(row["start_utc"]): row.get("energy_kwh")
        for row in ha_export["series"]["grid_export"]
    }

    quarters_by_hour: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for row in fluvius_intervals:
        quarters_by_hour[hour_floor(parse_utc(row["start_utc"]))].append(row)

    fluvius_hours: dict[datetime, dict[str, Any]] = {}
    for hour, rows in quarters_by_hour.items():
        starts = {parse_utc(row["start_utc"]) for row in rows}
        expected = {hour + index * QUARTER for index in range(4)}
        if starts != expected:
            continue
        fluvius_hours[hour] = {
            "import_kwh": sum(float(row["import_kwh"]) for row in rows),
            "export_kwh": sum(float(row["export_kwh"]) for row in rows),
            "estimated": any(bool(row["estimated"]) for row in rows),
        }

    ha_hours = set(ha_import) & set(ha_exported)
    if not ha_hours or not fluvius_hours:
        raise ValueError("No HA or Fluvius grid hours available")
    overlap_start = max(min(ha_hours), min(fluvius_hours))
    overlap_end = min(max(ha_hours) + HOUR, max(fluvius_hours) + HOUR)
    if overlap_end <= overlap_start:
        raise ValueError("HA and Fluvius datasets do not overlap")

    expected_hours = []
    current = overlap_start
    while current < overlap_end:
        expected_hours.append(current)
        current += HOUR

    comparable = []
    ha_unusable = 0
    fluvius_incomplete = 0
    estimated_hours = 0
    for hour in expected_hours:
        fluvius = fluvius_hours.get(hour)
        if fluvius is None:
            fluvius_incomplete += 1
            continue
        if ha_import.get(hour) is None or ha_exported.get(hour) is None:
            ha_unusable += 1
            continue
        row = {
            "start_utc": iso_utc(hour),
            "ha_import_kwh": float(ha_import[hour]),
            "ha_export_kwh": float(ha_exported[hour]),
            "fluvius_import_kwh": float(fluvius["import_kwh"]),
            "fluvius_export_kwh": float(fluvius["export_kwh"]),
            "estimated": bool(fluvius["estimated"]),
        }
        comparable.append(row)
        if row["estimated"]:
            estimated_hours += 1

    read_only = [row for row in comparable if not row["estimated"]]
    return {
        "schema_version": 1,
        "source_resolutions": {"home_assistant": "PT1H", "fluvius": "PT15M"},
        "overlap": {
            "start_utc": iso_utc(overlap_start),
            "end_utc": iso_utc(overlap_end),
            "expected_hour_count": len(expected_hours),
            "comparable_hour_count": len(comparable),
            "read_fluvius_hour_count": len(read_only),
            "estimated_fluvius_hour_count": estimated_hours,
            "ha_unusable_hour_count": ha_unusable,
            "fluvius_incomplete_hour_count": fluvius_incomplete,
        },
        "all_comparable": {
            flow: comparison_summary(comparable, flow)
            for flow in ("import", "export")
        },
        "read_only": {
            flow: comparison_summary(read_only, flow) for flow in ("import", "export")
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-export", required=True, type=Path)
    parser.add_argument("--fluvius-csv", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timezone", default="Europe/Brussels")
    args = parser.parse_args()

    ha_export = json.loads(args.ha_export.read_text(encoding="utf-8"))
    fluvius = load_fluvius_intervals(args.fluvius_csv, args.timezone)
    report = reconcile_grid_data(ha_export, fluvius)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
