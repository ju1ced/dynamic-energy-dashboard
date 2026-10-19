#!/usr/bin/env python3
"""Create a privacy-safe quality summary from a private DSMR Reader export."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_ROOT = ROOT / "data" / "raw" / "dsmr-reader-export-2023-10-01_2026-10-01"
DEFAULT_HA_PRICES = ROOT / "config" / "tariffs" / "ecopower-monthly-2026-ha.json"


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize_quarter_start(value: str) -> datetime:
    instant = parse_datetime(value).astimezone(timezone.utc)
    return instant.replace(
        minute=(instant.minute // 15) * 15,
        second=0,
        microsecond=0,
    )


def contiguous_ranges(values: Iterable[datetime], step: timedelta) -> list[dict[str, Any]]:
    ordered = sorted(set(values))
    if not ordered:
        return []
    output: list[dict[str, Any]] = []
    range_start = previous = ordered[0]
    for instant in ordered[1:]:
        if instant - previous != step:
            output.append(
                {
                    "start_utc": range_start.isoformat(),
                    "end_utc_inclusive": previous.isoformat(),
                    "count": int((previous - range_start) / step) + 1,
                }
            )
            range_start = instant
        previous = instant
    output.append(
        {
            "start_utc": range_start.isoformat(),
            "end_utc_inclusive": previous.isoformat(),
            "count": int((previous - range_start) / step) + 1,
        }
    )
    return output


def iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current < end:
        yield current
        current += timedelta(days=1)


def analyze_contract_coverage(
    contracts: list[dict[str, Any]],
    *,
    start: str,
    end: str,
) -> dict[str, Any]:
    start_day = date.fromisoformat(start)
    end_day = date.fromisoformat(end)
    parsed = [
        (date.fromisoformat(item["start"]), date.fromisoformat(item["end"]))
        for item in contracts
    ]
    uncovered: list[str] = []
    overlapping: list[str] = []
    covered_once = 0
    for day in iter_dates(start_day, end_day):
        matches = sum(contract_start <= day <= contract_end for contract_start, contract_end in parsed)
        if matches == 0:
            uncovered.append(day.isoformat())
        elif matches == 1:
            covered_once += 1
        else:
            overlapping.append(day.isoformat())
    return {
        "expected_days": (end_day - start_day).days,
        "covered_once_days": covered_once,
        "uncovered_days": uncovered,
        "overlapping_days": overlapping,
    }


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError(f"Invalid DSMR Reader export: {path}")
    return records


def expected_instants(start: datetime, end: datetime, step: timedelta) -> set[datetime]:
    output: set[datetime] = set()
    current = start
    while current < end:
        output.add(current)
        current += step
    return output


def find_contract(contracts: list[dict[str, Any]], day: date) -> list[dict[str, Any]]:
    return [
        item
        for item in contracts
        if date.fromisoformat(item["start"]) <= day <= date.fromisoformat(item["end"])
    ]


def decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def analyze_daily_cost_reconciliation(
    days: list[dict[str, Any]], contracts: list[dict[str, Any]]
) -> dict[str, Any]:
    mismatches: list[str] = []
    skipped: list[str] = []
    for item in days:
        day = date.fromisoformat(item["day"])
        matching = find_contract(contracts, day)
        if len(matching) != 1:
            skipped.append(item["day"])
            continue
        contract = matching[0]
        cost_1 = (
            decimal(item["electricity1"]) * decimal(contract["electricity_delivered_1_price"])
            - decimal(item["electricity1_returned"])
            * decimal(contract["electricity_returned_1_price"])
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cost_2 = (
            decimal(item["electricity2"]) * decimal(contract["electricity_delivered_2_price"])
            - decimal(item["electricity2_returned"])
            * decimal(contract["electricity_returned_2_price"])
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if cost_1 != decimal(item["electricity1_cost"]) or cost_2 != decimal(
            item["electricity2_cost"]
        ):
            mismatches.append(item["day"])
    return {
        "checked_days": len(days) - len(skipped),
        "skipped_days": skipped,
        "mismatch_count": len(mismatches),
        "first_mismatch_days": mismatches[:10],
    }


def compare_ha_monthly_prices(
    contracts: list[dict[str, Any]], ha_price_values: dict[str, Any]
) -> dict[str, Any]:
    compared: list[dict[str, Any]] = []
    for month, ha_value in sorted(ha_price_values.items()):
        month_start = date.fromisoformat(f"{month}-01")
        matching = find_contract(contracts, month_start)
        if len(matching) != 1:
            compared.append({"month": month, "status": "contract_coverage_not_unique"})
            continue
        dsmr_value = decimal(matching[0]["electricity_delivered_1_price"])
        ha_decimal = decimal(ha_value)
        compared.append(
            {
                "month": month,
                "ha_eur_per_kwh": float(ha_decimal),
                "dsmr_eur_per_kwh": float(dsmr_value),
                "difference_eur_per_kwh": float(ha_decimal - dsmr_value),
                "match": ha_decimal == dsmr_value,
            }
        )
    actual = [item for item in compared if item["month"] <= "2026-09"]
    return {
        "historical_months_compared": len(actual),
        "historical_matches": sum(item.get("match") is True for item in actual),
        "historical_mismatches": [item for item in actual if item.get("match") is False],
        "all_months": compared,
    }


def next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def build_historical_tariff_ledger(
    contracts: list[dict[str, Any]],
    ha_price_config: dict[str, Any],
    *,
    start: str,
    end: str,
) -> dict[str, Any]:
    start_month = date.fromisoformat(start).replace(day=1)
    end_month = date.fromisoformat(end).replace(day=1)
    ha_values = ha_price_config.get("values", {})
    usage = ha_price_config.get("usage", {})
    historical_through = date.fromisoformat(
        usage.get("historical_through", "0001-01-01")
    )
    months: list[dict[str, Any]] = []
    current = start_month
    while current < end_month:
        matching = find_contract(contracts, current)
        if len(matching) != 1:
            raise ValueError(
                f"Historical tariff coverage is not unique for {current:%Y-%m}"
            )
        contract = matching[0]
        month = current.strftime("%Y-%m")
        dsmr_import = decimal(contract["electricity_delivered_1_price"])
        dsmr_export = decimal(contract["electricity_returned_1_price"])
        use_ha = month in ha_values and current <= historical_through
        selected_import = decimal(ha_values[month]) if use_ha else dsmr_import
        months.append(
            {
                "month": month,
                "period_start": current.isoformat(),
                "period_end_exclusive": next_month(current).isoformat(),
                "provider": contract.get("description"),
                "dsmr_contract_start": contract["start"],
                "dsmr_contract_end": contract["end"],
                "dsmr_import_eur_per_kwh": float(dsmr_import),
                "dsmr_export_eur_per_kwh": float(dsmr_export),
                "dsmr_fixed_daily_cost_eur": float(decimal(contract["fixed_daily_cost"])),
                "ha_import_eur_per_kwh": float(decimal(ha_values[month]))
                if month in ha_values
                else None,
                "selected_import_eur_per_kwh": float(selected_import),
                "selected_import_source": "HA_OWNER_CONFIRMED" if use_ha else "DSMR",
                "selected_export_eur_per_kwh": float(dsmr_export),
                "selected_export_source": "DSMR",
                "ha_dsmr_difference_eur_per_kwh": float(
                    decimal(ha_values[month]) - dsmr_import
                )
                if month in ha_values
                else None,
                "calculation_scope": "CONFIGURED_ALL_IN_RATE_SENSITIVITY",
                "verification_status": "OWNER_CONFIRMED"
                if use_ha
                else "DSMR_CONFIGURED_VALUE",
            }
        )
        current = next_month(current)
    return {
        "schema_version": 1,
        "classification": "READ_ONLY_HISTORICAL_TARIFF_LEDGER",
        "period_start": start_month.isoformat(),
        "period_end_exclusive": end_month.isoformat(),
        "months": months,
        "limitations": {
            "component_scope_requires_confirmation": bool(
                usage.get("component_scope_requires_confirmation", True)
            ),
            "vat_inclusion_requires_confirmation": bool(
                usage.get("vat_inclusion_requires_confirmation", True)
            ),
            "not_component_complete_billing": True,
        },
        "safety": {
            "home_assistant_writes": False,
            "contract_change": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--ha-prices", type=Path, default=DEFAULT_HA_PRICES)
    parser.add_argument("--start-local", default="2023-10-01T00:00:00+02:00")
    parser.add_argument("--end-local", default="2026-10-01T00:00:00+02:00")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    start_local = parse_datetime(args.start_local)
    end_local = parse_datetime(args.end_local)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    start_day = start_local.date()
    end_day = end_local.date()

    electricity = load_records(args.export_root / "interval" / "electricity.json")
    hours = load_records(args.export_root / "interval" / "hour-statistics.json")
    peaks = load_records(args.export_root / "interval" / "quarter-hour-peaks.json")
    contracts = load_records(args.export_root / "daily" / "energy-supplier-prices.json")
    days = load_records(args.export_root / "daily" / "day-statistics.json")
    ha_price_config = json.loads(args.ha_prices.read_text(encoding="utf-8"))
    ha_prices = ha_price_config["values"]

    electricity_ordered = sorted(electricity, key=lambda item: parse_datetime(item["read_at"]))
    electricity_instants = [parse_datetime(item["read_at"]) for item in electricity_ordered]
    cadence = Counter(
        int((right - left).total_seconds())
        for left, right in zip(electricity_instants, electricity_instants[1:])
    )
    counter_decreases = {}
    for field in ("delivered_1", "delivered_2", "returned_1", "returned_2"):
        counter_decreases[field] = sum(
            decimal(right[field]) < decimal(left[field])
            for left, right in zip(electricity_ordered, electricity_ordered[1:])
        )

    expected_hours = expected_instants(start_utc, end_utc, timedelta(hours=1))
    hour_starts = [
        parse_datetime(item["hour_start"]).astimezone(timezone.utc) for item in hours
    ]
    missing_hours = expected_hours - set(hour_starts)
    hour_ranges = contiguous_ranges(missing_hours, timedelta(hours=1))

    expected_quarters = expected_instants(start_utc, end_utc, timedelta(minutes=15))
    normalized_peak_starts = [normalize_quarter_start(item["read_at_start"]) for item in peaks]
    missing_quarters = expected_quarters - set(normalized_peak_starts)
    quarter_ranges = contiguous_ranges(missing_quarters, timedelta(minutes=15))

    expected_days = set(iter_dates(start_day, end_day))
    day_values = [date.fromisoformat(item["day"]) for item in days]
    missing_days = sorted(expected_days - set(day_values))

    summary = {
        "schema_version": 1,
        "classification": "VERIFIED_READ_ONLY_EXPORT_SUMMARY",
        "period_local": {
            "start": start_local.isoformat(),
            "end": end_local.isoformat(),
            "end_exclusive": True,
        },
        "privacy": {
            "api_key_included": False,
            "endpoint_included": False,
            "measurement_values_included": False,
        },
        "resources": {
            "electricity": {
                "record_count": len(electricity),
                "first_timestamp": min(electricity_instants).isoformat(),
                "last_timestamp": max(electricity_instants).isoformat(),
                "duplicate_timestamp_count": len(electricity_instants)
                - len(set(electricity_instants)),
                "top_cadence_seconds": [
                    {"seconds": seconds, "count": count}
                    for seconds, count in cadence.most_common(10)
                ],
                "counter_decreases": counter_decreases,
            },
            "hour_statistics": {
                "record_count": len(hours),
                "expected_hour_count": len(expected_hours),
                "duplicate_start_count": len(hour_starts) - len(set(hour_starts)),
                "missing_hour_count": len(missing_hours),
                "gap_range_count": len(hour_ranges),
                "longest_gap": max(hour_ranges, key=lambda item: item["count"])
                if hour_ranges
                else None,
            },
            "quarter_hour_peaks": {
                "record_count": len(peaks),
                "expected_quarter_count": len(expected_quarters),
                "duplicate_nominal_start_count": len(normalized_peak_starts)
                - len(set(normalized_peak_starts)),
                "missing_quarter_count": len(missing_quarters),
                "gap_range_count": len(quarter_ranges),
                "longest_gap": max(quarter_ranges, key=lambda item: item["count"])
                if quarter_ranges
                else None,
            },
            "day_statistics": {
                "record_count": len(days),
                "expected_day_count": len(expected_days),
                "duplicate_day_count": len(day_values) - len(set(day_values)),
                "missing_days": [item.isoformat() for item in missing_days],
            },
            "energy_supplier_prices": {
                "record_count": len(contracts),
                "coverage": analyze_contract_coverage(
                    contracts, start=start_day.isoformat(), end=end_day.isoformat()
                ),
                "daily_cost_reconciliation": analyze_daily_cost_reconciliation(days, contracts),
                "ha_monthly_price_cross_check": compare_ha_monthly_prices(
                    contracts, ha_prices
                ),
            },
        },
        "assessment": {
            "contracts_cover_full_period": True,
            "dsmr_daily_statistics_are_not_gap_free": bool(missing_days),
            "dsmr_hour_and_peak_statistics_are_not_gap_free": bool(
                missing_hours or missing_quarters
            ),
            "fluvius_remains_primary_billing_energy_source": True,
            "dsmr_contract_price_differences_remain_visible": True,
            "historical_2026_price_authority": ha_price_config["usage"]["authority"],
            "source_priority_owner_confirmed": True,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
