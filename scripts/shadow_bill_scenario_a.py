#!/usr/bin/env python3
"""Calculate Ecopower Scenario A on unchanged Fluvius quarter-hour flows."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

INTERVAL = timedelta(minutes=15)
DATE_TIME_FORMAT = "%d-%m-%Y %H:%M:%S"
CONTRACT_DEPENDENT_COMPONENTS = {
    "energy",
    "green_certificates",
    "combined_heat_power_certificates",
    "injection_credit",
}


def parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a UTC offset: {value}")
    return parsed.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_volume(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def classify_flow(register: str) -> str:
    lowered = register.casefold()
    if lowered.startswith("afname"):
        return "import"
    if lowered.startswith("injectie"):
        return "export"
    raise ValueError(f"Unsupported Fluvius register: {register}")


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


def load_fluvius_intervals(
    path: str | Path, timezone_name: str = "Europe/Brussels"
) -> list[dict[str, Any]]:
    source = Path(path)
    zone = ZoneInfo(timezone_name)
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    if not rows or len(rows) % 2:
        raise ValueError("Fluvius CSV must contain complete import/export row pairs")

    used_utc_starts: set[datetime] = set()
    intervals = []
    for index in range(0, len(rows), 2):
        pair = rows[index : index + 2]
        starts = {
            datetime.strptime(
                f"{item['Van (datum)']} {item['Van (tijdstip)']}",
                DATE_TIME_FORMAT,
            )
            for item in pair
        }
        ends = {
            datetime.strptime(
                f"{item['Tot (datum)']} {item['Tot (tijdstip)']}",
                DATE_TIME_FORMAT,
            )
            for item in pair
        }
        if len(starts) != 1 or len(ends) != 1:
            raise ValueError(f"Fluvius row pair {index + 2} has mismatched bounds")
        local_start = starts.pop()
        local_end = ends.pop()
        available = [
            candidate
            for candidate in utc_start_candidates(local_start, local_end, zone)
            if candidate not in used_utc_starts
        ]
        if not available:
            raise ValueError(f"No unique UTC mapping for Fluvius row pair {index + 2}")
        utc_start = available[0]
        used_utc_starts.add(utc_start)

        values: dict[str, float] = {}
        statuses = set()
        for item in pair:
            flow = classify_flow(item["Register"])
            if flow in values:
                raise ValueError(f"Duplicate {flow} row in Fluvius row pair {index + 2}")
            values[flow] = parse_volume(item["Volume"])
            statuses.add(item["Validatiestatus"].strip() or "UNKNOWN")
        if set(values) != {"import", "export"}:
            raise ValueError(f"Fluvius row pair {index + 2} lacks import or export")

        intervals.append(
            {
                "start_utc": iso_utc(utc_start),
                "start_local": utc_start.astimezone(zone).isoformat(),
                "import_kwh": values["import"],
                "export_kwh": values["export"],
                "validation_status": "+".join(sorted(statuses)),
                "estimated": any(
                    status.casefold() != "uitgelezen" for status in statuses
                ),
            }
        )

    intervals.sort(key=lambda row: parse_instant(row["start_utc"]))
    for previous, current in zip(intervals, intervals[1:]):
        if parse_instant(current["start_utc"]) - parse_instant(previous["start_utc"]) != INTERVAL:
            raise ValueError("Fluvius intervals do not form a continuous UTC sequence")
    return intervals


def load_market_prices(path: str | Path) -> dict[str, float]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    prices: dict[str, float] = {}
    for item in data.get("intervals", []):
        key = iso_utc(parse_instant(item["start_utc"]))
        if key in prices:
            raise ValueError(f"Duplicate market price: {key}")
        prices[key] = float(item["price_eur_per_mwh"])
    if not prices:
        raise ValueError("Market price dataset contains no intervals")
    return prices


def expected_month_quarters(local_value: datetime, timezone_name: str) -> int:
    zone = ZoneInfo(timezone_name)
    start = datetime(local_value.year, local_value.month, 1, tzinfo=zone)
    if local_value.month == 12:
        end = datetime(local_value.year + 1, 1, 1, tzinfo=zone)
    else:
        end = datetime(local_value.year, local_value.month + 1, 1, tzinfo=zone)
    return int((end.astimezone(timezone.utc) - start.astimezone(timezone.utc)) / INTERVAL)


def _new_aggregate(label_name: str, label: str) -> dict[str, Any]:
    return {
        label_name: label,
        "interval_count": 0,
        "estimated_interval_count": 0,
        "import_kwh": 0.0,
        "export_kwh": 0.0,
        "import_energy_eur_excl_vat": 0.0,
        "export_value_eur_excl_vat": 0.0,
        "green_certificates_eur_excl_vat": 0.0,
        "combined_heat_power_eur_excl_vat": 0.0,
        "subscription_eur_excl_vat": 0.0,
        "supplier_net_eur_excl_vat": 0.0,
        "import_vat_base_eur": 0.0,
    }


def _add_to_aggregate(target: dict[str, Any], row: dict[str, Any]) -> None:
    target["interval_count"] += 1
    target["estimated_interval_count"] += int(row["estimated"])
    for key in (
        "import_kwh",
        "export_kwh",
        "import_energy_eur_excl_vat",
        "export_value_eur_excl_vat",
        "green_certificates_eur_excl_vat",
        "combined_heat_power_eur_excl_vat",
        "subscription_eur_excl_vat",
        "supplier_net_eur_excl_vat",
        "import_vat_base_eur",
    ):
        target[key] += row[key]


def _round_aggregate(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: round(item, 9) if isinstance(item, float) else item
        for key, item in value.items()
    }


def calculate_shadow_bill(
    intervals: list[dict[str, Any]],
    prices: dict[str, float],
    tariff: dict[str, Any],
) -> dict[str, Any]:
    if not intervals:
        raise ValueError("No energy intervals supplied")
    timezone_name = tariff.get("timezone", "Europe/Brussels")
    import_formula = tariff["import_energy"]
    export_formula = tariff["export_energy"]
    gsc_rate = float(tariff["green_certificates_eur_per_kwh"])
    wkk_rate = float(tariff["combined_heat_power_eur_per_kwh"])
    monthly_subscription = float(tariff["subscription_eur_per_month"])

    normalized_prices = {
        iso_utc(parse_instant(key)): float(value) for key, value in prices.items()
    }
    output_rows = []
    daily: dict[str, dict[str, Any]] = {}
    monthly: dict[str, dict[str, Any]] = {}
    totals = _new_aggregate("period", "all")

    for source in intervals:
        start_utc = iso_utc(parse_instant(source["start_utc"]))
        if start_utc not in normalized_prices:
            raise ValueError(f"Missing market price for energy interval: {start_utc}")
        local = datetime.fromisoformat(source["start_local"])
        if local.tzinfo is None:
            raise ValueError(f"Local timestamp has no offset: {source['start_local']}")
        price = normalized_prices[start_utc]
        import_kwh = float(source["import_kwh"])
        export_kwh = float(source["export_kwh"])
        import_rate = (
            float(import_formula["market_multiplier"]) * price
            + float(import_formula["offset_eur_per_kwh"])
        )
        export_rate = (
            float(export_formula["market_multiplier"]) * price
            + float(export_formula["offset_eur_per_kwh"])
        )
        subscription = monthly_subscription / expected_month_quarters(
            local, timezone_name
        )
        import_energy = import_kwh * import_rate
        export_value = export_kwh * export_rate
        gsc = import_kwh * gsc_rate
        wkk = import_kwh * wkk_rate
        supplier_net = import_energy + gsc + wkk + subscription - export_value
        import_vat_base = import_energy + gsc + wkk + subscription
        row = {
            "start_utc": start_utc,
            "start_local": local.isoformat(),
            "import_kwh": import_kwh,
            "export_kwh": export_kwh,
            "estimated": bool(source.get("estimated", False)),
            "market_price_eur_per_mwh": price,
            "import_rate_eur_per_kwh": import_rate,
            "export_rate_eur_per_kwh": export_rate,
            "import_energy_eur_excl_vat": import_energy,
            "export_value_eur_excl_vat": export_value,
            "green_certificates_eur_excl_vat": gsc,
            "combined_heat_power_eur_excl_vat": wkk,
            "subscription_eur_excl_vat": subscription,
            "supplier_net_eur_excl_vat": supplier_net,
            "import_vat_base_eur": import_vat_base,
        }
        output_rows.append(row)

        day = local.date().isoformat()
        month = local.strftime("%Y-%m")
        daily.setdefault(day, _new_aggregate("date", day))
        monthly.setdefault(month, _new_aggregate("month", month))
        _add_to_aggregate(daily[day], row)
        _add_to_aggregate(monthly[month], row)
        _add_to_aggregate(totals, row)

    totals.pop("period")
    total_import = totals["import_kwh"]
    total_export = totals["export_kwh"]
    totals["weighted_import_energy_rate_eur_per_kwh"] = (
        totals["import_energy_eur_excl_vat"] / total_import if total_import else None
    )
    totals["weighted_export_rate_eur_per_kwh"] = (
        totals["export_value_eur_excl_vat"] / total_export if total_export else None
    )

    return {
        "schema_version": 1,
        "scenario": "A_dynamic_contract_unchanged_behavior",
        "tariff_version": tariff["version"],
        "timezone": timezone_name,
        "period_start_utc": output_rows[0]["start_utc"],
        "period_end_utc": iso_utc(parse_instant(output_rows[-1]["start_utc"]) + INTERVAL),
        "intervals": output_rows,
        "daily": [_round_aggregate(daily[key]) for key in sorted(daily)],
        "monthly": [_round_aggregate(monthly[key]) for key in sorted(monthly)],
        "totals": _round_aggregate(totals),
        "quality": {
            "energy_interval_count": len(output_rows),
            "price_coverage_interval_count": len(output_rows),
            "estimated_interval_count": sum(row["estimated"] for row in output_rows),
            "missing_price_interval_count": 0,
            "sequence_complete": True,
        },
    }


def compare_with_invoice(
    dynamic: dict[str, Any], invoice: dict[str, Any]
) -> dict[str, Any]:
    components = invoice["components_eur_excl_vat"]
    unchanged = sum(
        float(value)
        for key, value in components.items()
        if key not in CONTRACT_DEPENDENT_COMPONENTS
    )
    dynamic_supplier = float(dynamic["totals"]["supplier_net_eur_excl_vat"])
    import_vat_base = float(dynamic["totals"]["import_vat_base_eur"])
    vat_rate = float(invoice["vat_rate_import"])
    dynamic_excl = unchanged + dynamic_supplier
    dynamic_vat = (unchanged + import_vat_base) * vat_rate
    dynamic_incl = dynamic_excl + dynamic_vat
    baseline = invoice["totals"]
    return {
        "method": "replace_contract_dependent_supplier_components",
        "unchanged_components_eur_excl_vat": round(unchanged, 9),
        "baseline_total_eur_excl_vat": float(baseline["excl_vat_eur"]),
        "baseline_vat_eur": float(baseline["vat_eur"]),
        "baseline_total_eur_incl_vat": float(baseline["incl_vat_eur"]),
        "dynamic_total_eur_excl_vat": round(dynamic_excl, 9),
        "dynamic_vat_eur": round(dynamic_vat, 9),
        "dynamic_total_eur_incl_vat": round(dynamic_incl, 9),
        "difference_eur_excl_vat": round(dynamic_excl - float(baseline["excl_vat_eur"]), 9),
        "difference_eur_incl_vat": round(dynamic_incl - float(baseline["incl_vat_eur"]), 9),
    }


def add_historical_baseline(
    dynamic: dict[str, Any], invoice: dict[str, Any]
) -> None:
    """Allocate validated invoice supplier components over actual intervals."""
    rows = dynamic["intervals"]
    components = invoice["components_eur_excl_vat"]
    monthly_amounts = {
        item["month"]: float(item["amount_eur_excl_vat"])
        for item in invoice["monthly_energy"]
    }
    monthly_import: dict[str, float] = defaultdict(float)
    total_import = 0.0
    total_export = 0.0
    for row in rows:
        month = row["start_local"][:7]
        monthly_import[month] += float(row["import_kwh"])
        total_import += float(row["import_kwh"])
        total_export += float(row["export_kwh"])
    missing_months = sorted(set(monthly_import) - set(monthly_amounts))
    if missing_months:
        raise ValueError(
            "Invoice baseline lacks monthly energy amounts for: "
            + ", ".join(missing_months)
        )

    gsc_total = float(components["green_certificates"])
    wkk_total = float(components["combined_heat_power_certificates"])
    injection_total = float(components["injection_credit"])
    day_values: dict[str, dict[str, float]] = defaultdict(
        lambda: {"baseline": 0.0, "difference": 0.0}
    )
    month_values: dict[str, dict[str, float]] = defaultdict(
        lambda: {"baseline": 0.0, "difference": 0.0}
    )
    baseline_total = 0.0

    for row in rows:
        month = row["start_local"][:7]
        day = row["start_local"][:10]
        import_kwh = float(row["import_kwh"])
        export_kwh = float(row["export_kwh"])
        energy = (
            monthly_amounts[month] * import_kwh / monthly_import[month]
            if monthly_import[month]
            else 0.0
        )
        gsc = gsc_total * import_kwh / total_import if total_import else 0.0
        wkk = wkk_total * import_kwh / total_import if total_import else 0.0
        injection = (
            injection_total * export_kwh / total_export if total_export else 0.0
        )
        baseline_supplier = energy + gsc + wkk + injection
        difference = float(row["supplier_net_eur_excl_vat"]) - baseline_supplier
        row["baseline_supplier_eur_excl_vat"] = round(baseline_supplier, 9)
        row["supplier_difference_eur_excl_vat"] = round(difference, 9)
        baseline_total += baseline_supplier
        day_values[day]["baseline"] += baseline_supplier
        day_values[day]["difference"] += difference
        month_values[month]["baseline"] += baseline_supplier
        month_values[month]["difference"] += difference

    cumulative = 0.0
    for item in dynamic["daily"]:
        values = day_values[item["date"]]
        cumulative += values["difference"]
        item["baseline_supplier_eur_excl_vat"] = round(values["baseline"], 9)
        item["supplier_difference_eur_excl_vat"] = round(values["difference"], 9)
        item["cumulative_supplier_difference_eur_excl_vat"] = round(
            cumulative, 9
        )

    cumulative = 0.0
    for item in dynamic["monthly"]:
        values = month_values[item["month"]]
        cumulative += values["difference"]
        item["baseline_supplier_eur_excl_vat"] = round(values["baseline"], 9)
        item["supplier_difference_eur_excl_vat"] = round(values["difference"], 9)
        item["cumulative_supplier_difference_eur_excl_vat"] = round(
            cumulative, 9
        )

    dynamic_total = float(dynamic["totals"]["supplier_net_eur_excl_vat"])
    dynamic["totals"]["baseline_supplier_eur_excl_vat"] = round(
        baseline_total, 9
    )
    dynamic["totals"]["supplier_difference_eur_excl_vat"] = round(
        dynamic_total - baseline_total, 9
    )
    dynamic["baseline"] = {
        "method": "invoice_components_allocated_pro_rata_to_actual_intervals",
        "energy_eur_excl_vat": round(sum(monthly_amounts.values()), 9),
        "green_certificates_eur_excl_vat": round(gsc_total, 9),
        "combined_heat_power_eur_excl_vat": round(wkk_total, 9),
        "injection_credit_eur_excl_vat": round(injection_total, 9),
        "supplier_net_eur_excl_vat": round(baseline_total, 9),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fluvius-csv", required=True, type=Path)
    parser.add_argument("--prices", required=True, type=Path)
    parser.add_argument("--tariff", required=True, type=Path)
    parser.add_argument("--invoice-baseline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    tariff = json.loads(args.tariff.read_text(encoding="utf-8"))
    invoice = json.loads(args.invoice_baseline.read_text(encoding="utf-8"))
    intervals = load_fluvius_intervals(args.fluvius_csv, tariff.get("timezone", "Europe/Brussels"))
    prices = load_market_prices(args.prices)
    report = calculate_shadow_bill(intervals, prices, tariff)
    add_historical_baseline(report, invoice)
    report["comparison"] = compare_with_invoice(report, invoice)
    report["model"] = {
        "retrospective_tariff_application": True,
        "unchanged_physical_behavior": True,
        "unchanged_grid_and_tax_components_from_invoice": True,
        "estimated_fluvius_intervals_retained": True,
        "silent_price_fill": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
