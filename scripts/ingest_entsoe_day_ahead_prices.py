#!/usr/bin/env python3
"""Fetch and normalize ENTSO-E Belgian Day-Ahead prices to quarter-hours."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

API_URL = "https://web-api.tp.entsoe.eu/api"
BELGIUM_BIDDING_ZONE_EIC = "10YBE----------2"
TARGET_INTERVAL = timedelta(minutes=15)


def parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a UTC offset: {value}")
    return parsed.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def child(element: ET.Element, name: str) -> ET.Element | None:
    return next((item for item in element if local_name(item) == name), None)


def child_text(element: ET.Element, name: str) -> str | None:
    item = child(element, name)
    return item.text.strip() if item is not None and item.text else None


def descendants(element: ET.Element, name: str) -> list[ET.Element]:
    return [item for item in element.iter() if local_name(item) == name]


def parse_resolution(value: str) -> timedelta:
    supported = {"PT15M": timedelta(minutes=15), "PT60M": timedelta(hours=1)}
    if value not in supported:
        raise ValueError(f"Unsupported ENTSO-E price resolution: {value}")
    return supported[value]


def parse_market_document(
    xml_text: str,
    *,
    retrieved_at: str,
    market_area_eic: str = BELGIUM_BIDDING_ZONE_EIC,
    local_timezone: str = "Europe/Brussels",
    requested_start: str | None = None,
    requested_end: str | None = None,
) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    zone = ZoneInfo(local_timezone)
    retrieved = parse_instant(retrieved_at)
    document_mrid = child_text(root, "mRID")
    document_created_text = child_text(root, "createdDateTime")
    document_created = (
        parse_instant(document_created_text) if document_created_text else None
    )
    window_start = parse_instant(requested_start) if requested_start else None
    window_end = parse_instant(requested_end) if requested_end else None
    if window_start and window_end and window_end <= window_start:
        raise ValueError("Requested end must be after requested start")

    intervals: list[dict[str, Any]] = []
    expected_quarter_starts: set[datetime] = set()
    native_resolution_counts: Counter[int] = Counter()

    for series in descendants(root, "TimeSeries"):
        series_mrid = child_text(series, "mRID")
        curve_type = child_text(series, "curveType") or "A01"
        for period in [item for item in series if local_name(item) == "Period"]:
            time_interval = child(period, "timeInterval")
            if time_interval is None:
                raise ValueError("ENTSO-E Period has no timeInterval")
            start_text = child_text(time_interval, "start")
            end_text = child_text(time_interval, "end")
            resolution_text = child_text(period, "resolution")
            if not start_text or not end_text or not resolution_text:
                raise ValueError("ENTSO-E Period is missing start, end, or resolution")

            period_start = parse_instant(start_text)
            period_end = parse_instant(end_text)
            resolution = parse_resolution(resolution_text)
            resolution_minutes = int(resolution.total_seconds() // 60)
            native_resolution_counts[resolution_minutes] += 1

            cursor = period_start
            while cursor < period_end:
                if (window_start is None or cursor >= window_start) and (
                    window_end is None or cursor + TARGET_INTERVAL <= window_end
                ):
                    expected_quarter_starts.add(cursor)
                cursor += TARGET_INTERVAL

            points: list[tuple[int, float]] = []
            for point in [item for item in period if local_name(item) == "Point"]:
                position_text = child_text(point, "position")
                price_text = child_text(point, "price.amount")
                if not position_text or price_text is None:
                    raise ValueError("ENTSO-E Point is missing position or price.amount")
                points.append((int(position_text), float(price_text)))

            points.sort(key=lambda item: item[0])
            for index, (position, price) in enumerate(points):
                native_start = period_start + (position - 1) * resolution
                if native_start < period_start or native_start >= period_end:
                    raise ValueError(f"ENTSO-E Point position outside Period: {position}")

                if resolution < TARGET_INTERVAL or resolution % TARGET_INTERVAL:
                    raise ValueError(
                        f"Resolution cannot be normalized to quarter-hours: {resolution_text}"
                    )
                block_end = native_start + resolution
                flags = []
                if curve_type == "A03":
                    block_end = (
                        period_start + (points[index + 1][0] - 1) * resolution
                        if index + 1 < len(points)
                        else period_end
                    )
                    if block_end - native_start > resolution:
                        flags.append("expanded_variable_sized_block")
                if block_end > period_end or block_end <= native_start:
                    raise ValueError(f"Invalid ENTSO-E price block at position: {position}")

                quarter_start = native_start
                while quarter_start < block_end:
                    quarter_end = quarter_start + TARGET_INTERVAL
                    if (window_start is not None and quarter_start < window_start) or (
                        window_end is not None and quarter_end > window_end
                    ):
                        quarter_start = quarter_end
                        continue
                    quarter_flags = list(flags)
                    if resolution != TARGET_INTERVAL:
                        quarter_flags.append(f"expanded_from_{resolution_minutes}_minutes")
                    intervals.append(
                        {
                            "start_utc": iso_utc(quarter_start),
                            "end_utc": iso_utc(quarter_end),
                            "start_local": quarter_start.astimezone(zone).isoformat(),
                            "end_local": quarter_end.astimezone(zone).isoformat(),
                            "price_eur_per_mwh": price,
                            "source_resolution_minutes": resolution_minutes,
                            "source_document_mrid": document_mrid,
                            "source_timeseries_mrid": series_mrid,
                            "source_position": position,
                            "quality_flags": quarter_flags,
                        }
                    )
                    quarter_start = quarter_end

    intervals.sort(key=lambda row: (row["start_utc"], row["source_timeseries_mrid"] or ""))
    deduplicated_intervals: list[dict[str, Any]] = []
    identical_by_bounds: dict[tuple[str, str], dict[str, Any]] = {}
    collapsed_identical_duplicates = 0
    for row in intervals:
        bounds = (row["start_utc"], row["end_utc"])
        existing = identical_by_bounds.get(bounds)
        if existing is not None and (
            existing["price_eur_per_mwh"] == row["price_eur_per_mwh"]
            and existing["source_resolution_minutes"] == row["source_resolution_minutes"]
            and existing["quality_flags"] == row["quality_flags"]
        ):
            collapsed_identical_duplicates += 1
            if "collapsed_identical_duplicate" not in existing["quality_flags"]:
                existing["quality_flags"].append("collapsed_identical_duplicate")
            continue
        deduplicated_intervals.append(row)
        identical_by_bounds.setdefault(bounds, row)
    intervals = deduplicated_intervals
    available_counts = Counter(parse_instant(row["start_utc"]) for row in intervals)
    missing_starts = sorted(expected_quarter_starts - set(available_counts))
    duplicate_starts = sorted(
        instant for instant, count in available_counts.items() if count > 1
    )

    return {
        "schema_version": 1,
        "source": {
            "provider": "ENTSO-E Transparency Platform Web API",
            "document_type": "A44",
            "process_type": "A01",
            "market_area_eic": market_area_eic,
            "document_mrid": document_mrid,
            "document_created_at": iso_utc(document_created) if document_created else None,
            "market_issue_time": None,
            "retrieved_at": iso_utc(retrieved),
            "response_sha256": hashlib.sha256(xml_text.encode()).hexdigest(),
            "requested_start": iso_utc(window_start) if window_start else None,
            "requested_end": iso_utc(window_end) if window_end else None,
        },
        "timezone": local_timezone,
        "target_resolution_minutes": 15,
        "intervals": intervals,
        "quality": {
            "expected_quarter_count": len(expected_quarter_starts),
            "available_quarter_count": len(intervals),
            "unique_available_quarter_count": len(available_counts),
            "missing_quarter_count": len(missing_starts),
            "missing_quarter_starts_utc": [iso_utc(value) for value in missing_starts],
            "duplicate_quarter_count": len(duplicate_starts),
            "duplicate_quarter_starts_utc": [iso_utc(value) for value in duplicate_starts],
            "collapsed_identical_duplicate_quarter_count": collapsed_identical_duplicates,
            "native_resolution_period_counts": {
                str(minutes): count
                for minutes, count in sorted(native_resolution_counts.items())
            },
            "sequence_complete": not missing_starts and not duplicate_starts,
            "issue_time_available": False,
        },
    }


def fetch_market_document(
    start: datetime,
    end: datetime,
    security_token: str,
    market_area_eic: str = BELGIUM_BIDDING_ZONE_EIC,
) -> str:
    if not security_token:
        raise ValueError("ENTSO-E security token is empty")
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Start and end must include a UTC offset")
    if end <= start:
        raise ValueError("End must be after start")

    params = {
        "securityToken": security_token,
        "documentType": "A44",
        "processType": "A01",
        "in_Domain": market_area_eic,
        "out_Domain": market_area_eic,
        "periodStart": start.astimezone(timezone.utc).strftime("%Y%m%d%H%M"),
        "periodEnd": end.astimezone(timezone.utc).strftime("%Y%m%d%H%M"),
    }
    request = urllib.request.Request(
        f"{API_URL}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": "dynamic-energy-dashboard/phase2-read-only"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(
            f"ENTSO-E API returned HTTP {error.code}: {body}"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-xml", type=Path, help="Parse an existing ENTSO-E XML response")
    source.add_argument("--fetch", action="store_true", help="Fetch from the ENTSO-E Web API")
    parser.add_argument("--start", help="Inclusive ISO timestamp for API fetch")
    parser.add_argument("--end", help="Exclusive ISO timestamp for API fetch")
    parser.add_argument("--token-env", default="ENTSOE_SECURITY_TOKEN")
    parser.add_argument("--area-eic", default=BELGIUM_BIDDING_ZONE_EIC)
    parser.add_argument("--timezone", default="Europe/Brussels")
    parser.add_argument("--retrieved-at", help="ISO retrieval timestamp; defaults to current UTC")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--raw-output", type=Path, help="Optional path for the raw XML response")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    retrieved_at = args.retrieved_at or datetime.now(timezone.utc).isoformat()

    if args.input_xml:
        xml_text = args.input_xml.read_text(encoding="utf-8")
    else:
        if not args.start or not args.end:
            raise SystemExit("--fetch requires --start and --end")
        token = os.environ.get(args.token_env, "")
        if not token:
            raise SystemExit(f"Missing required environment variable: {args.token_env}")
        xml_text = fetch_market_document(
            parse_instant(args.start),
            parse_instant(args.end),
            token,
            args.area_eic,
        )

    if args.raw_output:
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)
        args.raw_output.write_text(xml_text, encoding="utf-8")

    report = parse_market_document(
        xml_text,
        retrieved_at=retrieved_at,
        market_area_eic=args.area_eic,
        local_timezone=args.timezone,
        requested_start=args.start,
        requested_end=args.end,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
