#!/usr/bin/env python3
"""Analyze a Fluvius quarter-hour CSV without emitting identifiers."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DATE_TIME_FORMAT = "%d-%m-%Y %H:%M:%S"
INTERVAL = timedelta(minutes=15)


def parse_local(date_value: str, time_value: str) -> datetime:
    return datetime.strptime(f"{date_value} {time_value}", DATE_TIME_FORMAT)


def parse_volume(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def classify_flow(register: str) -> str:
    lowered = register.casefold()
    if lowered.startswith("afname"):
        return "import"
    if lowered.startswith("injectie"):
        return "export"
    return "unknown"


def rounded_mapping(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 3) for key, value in sorted(values.items())}


def utc_start_candidates(
    local_start: datetime, local_end: datetime, zone: ZoneInfo
) -> list[datetime]:
    candidates = set()
    for fold in (0, 1):
        utc_start = local_start.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        roundtrip_start = utc_start.astimezone(zone).replace(tzinfo=None)
        roundtrip_end = (utc_start + INTERVAL).astimezone(zone).replace(tzinfo=None)
        if roundtrip_start == local_start and roundtrip_end == local_end:
            candidates.add(utc_start)
    return sorted(candidates)


def analyze_csv(path: str | Path, timezone_name: str = "Europe/Brussels") -> dict[str, Any]:
    source = Path(path)
    zone = ZoneInfo(timezone_name)

    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))

    issues: list[str] = []
    if not rows:
        raise ValueError("CSV contains no data rows")
    if len(rows) % 2:
        issues.append("odd_row_count")

    intervals: list[dict[str, Any]] = []
    for index in range(0, len(rows) - 1, 2):
        pair = rows[index : index + 2]
        starts = {
            parse_local(item["Van (datum)"], item["Van (tijdstip)"])
            for item in pair
        }
        ends = {
            parse_local(item["Tot (datum)"], item["Tot (tijdstip)"])
            for item in pair
        }
        flows = [classify_flow(item["Register"]) for item in pair]
        if len(starts) != 1 or len(ends) != 1:
            issues.append(f"row_pair_{index + 2}_has_mismatched_bounds")
        intervals.append(
            {
                "start": min(starts),
                "end": min(ends),
                "rows": pair,
                "flows": flows,
            }
        )

    used_utc_starts: set[datetime] = set()
    for position, interval in enumerate(intervals):
        available = [
            candidate
            for candidate in utc_start_candidates(interval["start"], interval["end"], zone)
            if candidate not in used_utc_starts
        ]
        if not available:
            issues.append(f"interval_{position}_has_no_unique_utc_mapping")
            interval["utc_start"] = None
            continue
        interval["utc_start"] = available[0]
        used_utc_starts.add(available[0])

    mapped_intervals = [item for item in intervals if item["utc_start"] is not None]
    mapped_intervals.sort(key=lambda item: item["utc_start"])
    if not mapped_intervals:
        raise ValueError("CSV contains no intervals with a valid UTC mapping")

    first_utc = mapped_intervals[0]["utc_start"]
    sequence_complete = True
    clock_transition_count = 0
    totals: dict[str, float] = defaultdict(float)
    monthly: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    register_rows: Counter[str] = Counter()
    validation_rows: Counter[str] = Counter()
    validation_intervals: Counter[str] = Counter()
    estimated_intervals = 0
    read_intervals = 0
    unavailable_intervals = 0
    missing_volume_rows = 0
    complete_flow_intervals = 0

    for position, interval in enumerate(mapped_intervals):
        expected_start_utc = first_utc + position * INTERVAL
        expected_end_utc = expected_start_utc + INTERVAL
        expected_start_local = expected_start_utc.astimezone(zone).replace(tzinfo=None)
        expected_end_local = expected_end_utc.astimezone(zone).replace(tzinfo=None)

        if (
            interval["utc_start"] != expected_start_utc
            or interval["start"] != expected_start_local
            or interval["end"] != expected_end_local
        ):
            sequence_complete = False
        if interval["end"] - interval["start"] != INTERVAL:
            clock_transition_count += 1

        if Counter(interval["flows"]) == Counter({"import": 1, "export": 1}):
            complete_flow_intervals += 1
        else:
            issues.append(f"interval_{position}_does_not_have_one_import_and_one_export_row")

        statuses = set()
        interval_has_missing_volume = False
        month = expected_start_local.strftime("%Y-%m")
        for item, flow in zip(interval["rows"], interval["flows"]):
            status = item["Validatiestatus"].strip() or "UNKNOWN"
            statuses.add(status)
            validation_rows[status] += 1
            register_rows[item["Register"].strip() or "UNKNOWN"] += 1
            if flow in {"import", "export"}:
                raw_volume = item["Volume"].strip()
                if not raw_volume:
                    missing_volume_rows += 1
                    interval_has_missing_volume = True
                    continue
                volume = parse_volume(raw_volume)
                totals[flow] += volume
                monthly[month][flow] += volume

        interval_status = "+".join(sorted(statuses))
        validation_intervals[interval_status] += 1
        if interval_has_missing_volume:
            unavailable_intervals += 1
            issues.append(f"interval_{position}_has_missing_volume")
        elif any(status.casefold() == "geschat" for status in statuses):
            estimated_intervals += 1
        elif statuses and all(status.casefold() == "uitgelezen" for status in statuses):
            read_intervals += 1
        else:
            unavailable_intervals += 1

    if not sequence_complete:
        issues.append("local_timestamps_do_not_form_a_complete_utc_quarter_sequence")

    period_end_utc = first_utc + len(mapped_intervals) * INTERVAL
    period_end_local = period_end_utc.astimezone(zone)
    interval_count = len(mapped_intervals)
    usable_interval_count = read_intervals + estimated_intervals

    return {
        "schema_version": 1,
        "timezone": timezone_name,
        "period_start_local": first_utc.astimezone(zone).isoformat(),
        "period_end_local": period_end_local.isoformat(),
        "period_start_utc": first_utc.isoformat(),
        "period_end_utc": period_end_utc.isoformat(),
        "row_count": len(rows),
        "interval_count": interval_count,
        "sequence_complete": sequence_complete,
        "all_intervals_have_import_and_export": complete_flow_intervals == interval_count,
        "clock_transition_interval_count": clock_transition_count,
        "read_interval_count": read_intervals,
        "estimated_interval_count": estimated_intervals,
        "unavailable_interval_count": unavailable_intervals,
        "usable_interval_count": usable_interval_count,
        "missing_volume_row_count": missing_volume_rows,
        "read_interval_percentage": round(read_intervals / interval_count * 100, 6),
        "estimated_interval_percentage": round(estimated_intervals / interval_count * 100, 6),
        "unavailable_interval_percentage": round(unavailable_intervals / interval_count * 100, 6),
        "totals_kwh": rounded_mapping(totals),
        "monthly_totals_kwh": {
            month: rounded_mapping(values) for month, values in sorted(monthly.items())
        },
        "register_row_counts": dict(sorted(register_rows.items())),
        "validation_status_row_counts": dict(sorted(validation_rows.items())),
        "validation_status_interval_counts": dict(sorted(validation_intervals.items())),
        "identifiers_consistent": {
            "ean": len({row["EAN-code"] for row in rows}) == 1,
            "meter": len({row["Meter"] for row in rows}) == 1,
        },
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--timezone", default="Europe/Brussels")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = analyze_csv(args.csv_path, args.timezone)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if not report["issues"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
