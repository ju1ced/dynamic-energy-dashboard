#!/usr/bin/env python3
"""Export privacy-safe interval energy changes from HA statistics."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

FIVE_MINUTES = timedelta(minutes=5)
QUARTER_HOUR = timedelta(minutes=15)
ONE_HOUR = timedelta(hours=1)
SOURCE_PERIODS = {"5minute": FIVE_MINUTES, "hour": ONE_HOUR}


def parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a UTC offset: {value}")
    return parsed.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def interval_floor(value: datetime, interval: timedelta) -> datetime:
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    elapsed = value - epoch
    return epoch + (elapsed // interval) * interval


def extract_tool_data(result: Any) -> dict[str, Any]:
    dumped = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    structured = dumped.get("structured_content") if isinstance(dumped, dict) else None
    if isinstance(structured, dict) and isinstance(structured.get("data"), dict):
        return structured["data"]
    if isinstance(dumped, dict):
        for item in dumped.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                parsed = json.loads(item["text"])
                if isinstance(parsed, dict) and isinstance(parsed.get("data"), dict):
                    return parsed["data"]
    raise ValueError("MCP result did not contain structured Home Assistant data")


def build_export(
    responses: list[dict[str, Any]],
    *,
    entity_map: dict[str, dict[str, Any]],
    start: str,
    end: str,
    retrieved_at: str,
    local_timezone: str = "Europe/Brussels",
    source_period: str = "5minute",
) -> dict[str, Any]:
    start_utc = parse_instant(start)
    end_utc = parse_instant(end)
    retrieved = parse_instant(retrieved_at)
    if end_utc <= start_utc:
        raise ValueError("End must be after start")
    if source_period not in SOURCE_PERIODS:
        raise ValueError(f"Unsupported source period: {source_period}")
    source_interval = SOURCE_PERIODS[source_period]
    target_interval = QUARTER_HOUR if source_period == "5minute" else ONE_HOUR
    if interval_floor(start_utc, target_interval) != start_utc or interval_floor(
        end_utc, target_interval
    ) != end_utc:
        raise ValueError("Start and end must align to target interval boundaries")

    zone = ZoneInfo(local_timezone)
    alias_by_entity = {
        settings["entity_id"]: alias for alias, settings in entity_map.items()
    }
    rows_by_alias: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for response in responses:
        if not response.get("success"):
            raise ValueError("Home Assistant statistics response was not successful")
        for entity in response.get("entities", []):
            entity_id = entity.get("entity_id")
            alias = alias_by_entity.get(entity_id)
            if alias is None:
                continue
            scale = float(entity_map[alias].get("scale_to_kwh", 1.0))
            for statistic in entity.get("statistics", []):
                instant = datetime.fromtimestamp(
                    float(statistic["start"]) / 1000, tz=timezone.utc
                )
                if not start_utc - source_interval <= instant < end_utc:
                    continue
                state = statistic.get("state")
                change = statistic.get("change")
                rows_by_alias[alias].append(
                    {
                        "start": instant,
                        "state_kwh": None if state is None else float(state) * scale,
                        "change_kwh": None if change is None else float(change) * scale,
                    }
                )

    expected_source_starts = []
    cursor = start_utc
    while cursor < end_utc:
        expected_source_starts.append(cursor)
        cursor += source_interval

    series: dict[str, list[dict[str, Any]]] = {}
    quality: dict[str, dict[str, Any]] = {}

    for alias in sorted(entity_map):
        source_rows = sorted(rows_by_alias.get(alias, []), key=lambda row: row["start"])
        rows_by_start: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
        for row in source_rows:
            rows_by_start[row["start"]].append(row)
        duplicates = sorted(
            instant
            for instant, rows in rows_by_start.items()
            if start_utc <= instant < end_utc
            and len(rows) > 1
            and any(
                (row["state_kwh"], row["change_kwh"])
                != (rows[0]["state_kwh"], rows[0]["change_kwh"])
                for row in rows[1:]
            )
        )
        unique_rows = {instant: rows[0] for instant, rows in rows_by_start.items()}

        missing = [
            instant
            for instant in expected_source_starts
            if instant not in unique_rows
        ]
        decreases: list[datetime] = []
        previous_state = None
        for row in sorted(unique_rows.values(), key=lambda item: item["start"]):
            state = row["state_kwh"]
            if (
                row["start"] >= start_utc
                and state is not None
                and previous_state is not None
                and state < previous_state
            ):
                decreases.append(row["start"])
            if state is not None:
                previous_state = state

        derived_changes: dict[datetime, float | None] = {}
        reported_change_mismatches: list[datetime] = []
        transient_spikes: list[datetime] = []
        counter_recoveries: list[datetime] = []
        for instant in expected_source_starts:
            preceding = unique_rows.get(instant - 2 * source_interval)
            previous = unique_rows.get(instant - source_interval)
            row = unique_rows.get(instant)
            following = unique_rows.get(instant + source_interval)
            if not previous or not row or not following:
                continue
            previous_state = previous["state_kwh"]
            state = row["state_kwh"]
            following_state = following["state_kwh"]
            if (
                previous_state is not None
                and state is not None
                and following_state is not None
                and state > previous_state
                and following_state < state
                and following_state >= previous_state - 1e-9
            ):
                transient_spikes.append(instant)
            if preceding and previous and row:
                preceding_state = preceding["state_kwh"]
                previous_state = previous["state_kwh"]
                state = row["state_kwh"]
                if (
                    preceding_state is not None
                    and previous_state is not None
                    and state is not None
                    and previous_state < preceding_state
                    and state >= preceding_state
                ):
                    counter_recoveries.append(instant)

        for instant in expected_source_starts:
            row = unique_rows.get(instant)
            previous = unique_rows.get(instant - source_interval)
            if instant in transient_spikes or instant in counter_recoveries:
                derived_changes[instant] = None
            elif (
                row is not None
                and previous is not None
                and row["state_kwh"] is not None
                and previous["state_kwh"] is not None
            ):
                delta = row["state_kwh"] - previous["state_kwh"]
                if delta < -1e-9:
                    derived_changes[instant] = None
                else:
                    derived_changes[instant] = max(delta, 0.0)
                    reported = row["change_kwh"]
                    tolerance = max(1e-6, abs(delta) * 1e-6)
                    if reported is not None and abs(reported - delta) > tolerance:
                        reported_change_mismatches.append(instant)
            elif row is not None and instant == start_utc:
                derived_changes[instant] = row["change_kwh"]
            elif row is not None:
                derived_changes[instant] = None
            else:
                derived_changes[instant] = None

        decrease_intervals = {
            interval_floor(value, target_interval) for value in decreases
        }
        duplicate_intervals = {
            interval_floor(value, target_interval) for value in duplicates
        }
        mismatch_intervals = {
            interval_floor(value, target_interval)
            for value in reported_change_mismatches
        }
        spike_intervals = {
            interval_floor(value, target_interval) for value in transient_spikes
        }
        recovery_intervals = {
            interval_floor(value, target_interval) for value in counter_recoveries
        }
        alias_series = []
        interval_start = start_utc
        source_bucket_count = int(target_interval / source_interval)
        missing_bucket_flag = (
            "missing_5minute_bucket"
            if source_period == "5minute"
            else "missing_hour_bucket"
        )
        duplicate_bucket_flag = (
            "duplicate_5minute_bucket"
            if source_period == "5minute"
            else "duplicate_hour_bucket"
        )
        while interval_start < end_utc:
            bucket_starts = [
                interval_start + offset * source_interval
                for offset in range(source_bucket_count)
            ]
            bucket_rows = [unique_rows.get(value) for value in bucket_starts]
            flags = []
            if any(row is None for row in bucket_rows):
                flags.append(missing_bucket_flag)
            if interval_start in duplicate_intervals:
                flags.append(duplicate_bucket_flag)
            if interval_start in decrease_intervals:
                flags.append("counter_decrease")
            if interval_start in mismatch_intervals:
                flags.append("reported_change_mismatch")
            if interval_start in spike_intervals:
                flags.append("transient_counter_spike")
            if interval_start in recovery_intervals:
                flags.append("counter_recovery_after_drop")
            if missing_bucket_flag not in flags and any(
                row is not None and derived_changes[start] is None
                for start, row in zip(bucket_starts, bucket_rows)
            ):
                flags.append("missing_change_value")

            if flags and (
                missing_bucket_flag in flags
                or duplicate_bucket_flag in flags
                or "missing_change_value" in flags
            ):
                energy_kwh = None
            else:
                energy_kwh = round(
                    sum(
                        value
                        for start in bucket_starts
                        if (value := derived_changes[start]) is not None
                    ),
                    9,
                )
            alias_series.append(
                {
                    "start_utc": iso_utc(interval_start),
                    "end_utc": iso_utc(interval_start + target_interval),
                    "start_local": interval_start.astimezone(zone).isoformat(),
                    "end_local": (interval_start + target_interval)
                    .astimezone(zone)
                    .isoformat(),
                    "energy_kwh": energy_kwh,
                    "quality_flags": flags,
                }
            )
            interval_start += target_interval

        incomplete_quarters = sum(bool(row["quality_flags"]) for row in alias_series)
        alias_quality = {
            "source_period": source_period,
            "expected_source_count": len(expected_source_starts),
            "available_source_count": sum(
                start_utc <= row["start"] < end_utc for row in source_rows
            ),
            "unique_available_source_count": sum(
                start_utc <= instant < end_utc for instant in unique_rows
            ),
            "missing_source_count": len(missing),
            "missing_source_starts_utc": [iso_utc(value) for value in missing],
            "duplicate_source_count": len(duplicates),
            "duplicate_source_starts_utc": [iso_utc(value) for value in duplicates],
            "counter_decrease_count": len(decreases),
            "counter_decrease_starts_utc": [iso_utc(value) for value in decreases],
            "reported_change_mismatch_count": len(reported_change_mismatches),
            "reported_change_mismatch_starts_utc": [
                iso_utc(value) for value in reported_change_mismatches
            ],
            "transient_counter_spike_count": len(transient_spikes),
            "transient_counter_spike_starts_utc": [
                iso_utc(value) for value in transient_spikes
            ],
            "counter_recovery_after_drop_count": len(counter_recoveries),
            "counter_recovery_after_drop_starts_utc": [
                iso_utc(value) for value in counter_recoveries
            ],
            "interval_count": len(alias_series),
            "incomplete_interval_count": incomplete_quarters,
            "complete": not missing
            and not duplicates
            and not decreases
            and not reported_change_mismatches
            and not transient_spikes
            and not counter_recoveries,
        }
        if source_period == "5minute":
            alias_quality.update(
                {
                    "expected_5minute_count": len(expected_source_starts),
                    "available_5minute_count": alias_quality["available_source_count"],
                    "unique_available_5minute_count": alias_quality[
                        "unique_available_source_count"
                    ],
                    "missing_5minute_count": len(missing),
                    "missing_5minute_starts_utc": alias_quality[
                        "missing_source_starts_utc"
                    ],
                    "duplicate_5minute_count": len(duplicates),
                    "duplicate_5minute_starts_utc": alias_quality[
                        "duplicate_source_starts_utc"
                    ],
                    "quarter_count": len(alias_series),
                    "incomplete_quarter_count": incomplete_quarters,
                }
            )
        quality[alias] = alias_quality
        series[alias] = alias_series

    return {
        "schema_version": 1,
        "source": {
            "provider": "Home Assistant long-term statistics",
            "access_method": "read-only ha_get_history via MCP",
            "source_period": source_period,
            "source_resolution_minutes": int(source_interval.total_seconds() // 60),
            "retrieved_at": iso_utc(retrieved),
        },
        "timezone": local_timezone,
        "period_start_utc": iso_utc(start_utc),
        "period_end_utc": iso_utc(end_utc),
        "target_resolution_minutes": int(target_interval.total_seconds() // 60),
        "aliases": sorted(entity_map),
        "series": series,
        "quality": quality,
    }


def load_entity_map(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entities = data.get("entities", data)
    if not isinstance(entities, dict) or not entities:
        raise ValueError("Entity map must contain a non-empty object")
    for alias, settings in entities.items():
        if not isinstance(settings, dict) or not settings.get("entity_id"):
            raise ValueError(f"Entity map entry has no entity_id: {alias}")
    return entities


def chunk_ranges(start: datetime, end: datetime, chunk_days: int):
    cursor = start
    step = timedelta(days=chunk_days)
    while cursor < end:
        chunk_end = min(cursor + step, end)
        yield cursor, chunk_end
        cursor = chunk_end


async def query_statistics(
    *,
    wrapper: str,
    entity_map: dict[str, dict[str, Any]],
    start: datetime,
    end: datetime,
    chunk_days: int,
    source_period: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=wrapper, args=[])
    responses = []
    raw_results = []
    source_interval = SOURCE_PERIODS[source_period]
    entity_ids = [settings["entity_id"] for settings in entity_map.values()]
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            for chunk_start, chunk_end in chunk_ranges(start, end, chunk_days):
                result = await session.call_tool(
                    "ha_get_history",
                    {
                        "entity_ids": entity_ids,
                        "source": "statistics",
                        "start_time": iso_utc(chunk_start - source_interval),
                        "end_time": iso_utc(chunk_end),
                        "period": source_period,
                        "statistic_types": ["state", "change"],
                        "limit": 1000,
                    },
                )
                raw_results.append(result.model_dump(mode="json"))
                responses.append(extract_tool_data(result))
    return responses, raw_results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity-map", required=True, type=Path)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--raw-output", type=Path)
    parser.add_argument(
        "--wrapper",
        default=str(Path.home() / ".hermes/bin/home-assistant-mcp-wrapper"),
    )
    parser.add_argument("--chunk-days", type=int, default=3)
    parser.add_argument(
        "--source-period",
        choices=sorted(SOURCE_PERIODS),
        default="5minute",
    )
    parser.add_argument("--timezone", default="Europe/Brussels")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    entity_map = load_entity_map(args.entity_map)
    start = parse_instant(args.start)
    end = parse_instant(args.end)
    retrieved = datetime.now(timezone.utc)
    responses, raw_results = asyncio.run(
        query_statistics(
            wrapper=args.wrapper,
            entity_map=entity_map,
            start=start,
            end=end,
            chunk_days=args.chunk_days,
            source_period=args.source_period,
        )
    )
    report = build_export(
        responses,
        entity_map=entity_map,
        start=iso_utc(start),
        end=iso_utc(end),
        retrieved_at=iso_utc(retrieved),
        local_timezone=args.timezone,
        source_period=args.source_period,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.raw_output:
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)
        args.raw_output.write_text(
            json.dumps(raw_results, indent=2) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
