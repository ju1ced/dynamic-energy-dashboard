#!/usr/bin/env python3
"""Parse a DSMR Reader energy-contract page export into a safe monthly ledger."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

MONTHS = {
    "jan": 1,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "aug": 8,
    "sept": 9,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
HEADER_RE = re.compile(r"^(.+?)\s+(\d+)\s+days stored$")
DATE_RE = re.compile(r"([A-Za-z]+)\.?\s+(\d{1,2}),\s+(\d{4})")


def parse_number(value: str) -> float:
    return float(value.replace(",", "").strip())


def parse_english_date(value: str) -> date:
    match = DATE_RE.search(value)
    if not match:
        raise ValueError(f"Could not parse date: {value!r}")
    month_name, day_value, year_value = match.groups()
    month = MONTHS.get(month_name.lower())
    if month is None:
        raise ValueError(f"Unsupported month name: {month_name!r}")
    return date(int(year_value), month, int(day_value))


def next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def month_starts(start: date, end_exclusive: date) -> list[date]:
    cursor = date(start.year, start.month, 1)
    result = []
    while cursor < end_exclusive:
        result.append(cursor)
        cursor = next_month(cursor)
    return result


def field_value(lines: list[str], prefix: str) -> str:
    for line in lines:
        if line.startswith(prefix):
            parts = line.split("\t")
            if len(parts) < 2:
                raise ValueError(f"Missing value after {prefix!r}")
            return parts[-1].strip()
    raise ValueError(f"Missing DSMR export field: {prefix!r}")


def optional_field_value(lines: list[str], prefix: str, default: str) -> str:
    try:
        return field_value(lines, prefix)
    except ValueError:
        return default


def parse_block(lines: list[str]) -> dict[str, Any]:
    header = HEADER_RE.match(lines[0])
    if not header:
        raise ValueError(f"Invalid contract header: {lines[0]!r}")
    provider, stored_days_text = header.groups()
    stored_days = int(stored_days_text)

    period_line = next((line for line in lines[1:] if "←→" in line), None)
    if period_line is None:
        raise ValueError(f"Missing period for contract {provider!r}")
    period_parts = period_line.split("←→")
    period_start = parse_english_date(period_parts[0])
    period_end = parse_english_date(period_parts[1])

    electricity_line = next(
        (line for line in lines if line.startswith("Electricity (total) kWh\t")), None
    )
    if electricity_line is None:
        raise ValueError(f"Missing electricity totals for contract {provider!r}")
    electricity_parts = electricity_line.split("\t")
    consumed_kwh = parse_number(electricity_parts[1])
    returned_kwh = parse_number(electricity_parts[2] or "0")
    displayed_variable_cost_eur = parse_number(electricity_parts[3])

    import_tariff_1 = parse_number(field_value(lines, "Dagtarief tariff 1"))
    import_tariff_2 = parse_number(field_value(lines, "Nachttarief tariff 2"))
    export_tariff_1 = parse_number(
        optional_field_value(lines, "dagtarief teruglevering tariff 1", "0")
    )
    export_tariff_2 = parse_number(
        optional_field_value(lines, "nachttarief teruglevering tariff 2", "0")
    )
    fixed_daily = parse_number(optional_field_value(lines, "Fixed daily costs", "0"))
    fixed_total = parse_number(optional_field_value(lines, "Fixed costs", "0"))
    total_cost = parse_number(field_value(lines, "Total costs"))

    if import_tariff_1 != import_tariff_2 or export_tariff_1 != export_tariff_2:
        calculated_variable = None
        variable_difference = None
    else:
        calculated_variable = round(
            consumed_kwh * import_tariff_1 - returned_kwh * export_tariff_1, 2
        )
        variable_difference = round(calculated_variable - displayed_variable_cost_eur, 2)

    calendar_days = (period_end - period_start).days + 1
    displayed_total_recalculated = round(displayed_variable_cost_eur + fixed_total, 2)
    total_difference = round(displayed_total_recalculated - total_cost, 2)

    return {
        "provider": provider.strip(),
        "stored_days": stored_days,
        "calendar_period_days": calendar_days,
        "stored_day_count_mismatch": stored_days != calendar_days,
        "period_start": period_start.isoformat(),
        "period_end_inclusive": period_end.isoformat(),
        "import_tariff_1_eur_per_kwh": import_tariff_1,
        "import_tariff_2_eur_per_kwh": import_tariff_2,
        "export_tariff_1_eur_per_kwh": export_tariff_1,
        "export_tariff_2_eur_per_kwh": export_tariff_2,
        "fixed_daily_cost_eur": fixed_daily,
        "displayed_variable_cost_eur": displayed_variable_cost_eur,
        "calculated_variable_cost_eur": calculated_variable,
        "variable_cost_reconciliation_difference_eur": variable_difference,
        "displayed_fixed_cost_eur": fixed_total,
        "displayed_total_cost_eur": total_cost,
        "total_cost_reconciliation_difference_eur": total_difference,
    }


def parse_contract_export_text(
    text: str, canonical_start: str, canonical_end_exclusive: str
) -> dict[str, Any]:
    lines = [line.strip() for line in text.replace("\r", "").splitlines() if line.strip()]
    header_indices = [index for index, line in enumerate(lines) if HEADER_RE.match(line)]
    contracts = []
    for position, start_index in enumerate(header_indices):
        end_index = (
            header_indices[position + 1] if position + 1 < len(header_indices) else len(lines)
        )
        contracts.append(parse_block(lines[start_index:end_index]))

    start = date.fromisoformat(canonical_start)
    end_exclusive = date.fromisoformat(canonical_end_exclusive)
    months_by_key: dict[str, dict[str, Any]] = {}
    overlaps: list[str] = []
    used_contract_starts: set[str] = set()
    for contract in contracts:
        period_start = date.fromisoformat(contract["period_start"])
        period_end = date.fromisoformat(contract["period_end_inclusive"])
        if contract["stored_days"] <= 31:
            coverage_end = next_month(period_start)
        else:
            coverage_end = period_end + timedelta(days=1)
        coverage_start = max(start, period_start)
        coverage_end = min(end_exclusive, coverage_end)
        if coverage_start >= coverage_end:
            continue
        used_contract_starts.add(contract["period_start"])
        for month_start in month_starts(coverage_start, coverage_end):
            key = month_start.strftime("%Y-%m")
            if key in months_by_key:
                overlaps.append(key)
                continue
            months_by_key[key] = {
                "month": key,
                "provider": contract["provider"],
                "source_period_start": contract["period_start"],
                "source_period_end_inclusive": contract["period_end_inclusive"],
                "import_eur_per_kwh": contract["import_tariff_1_eur_per_kwh"],
                "export_eur_per_kwh": contract["export_tariff_1_eur_per_kwh"],
                "fixed_daily_cost_eur": contract["fixed_daily_cost_eur"],
                "rate_semantics": "DSMR_DISPLAYED_ALL_IN_RATE_RECONCILED",
            }

    expected_months = [value.strftime("%Y-%m") for value in month_starts(start, end_exclusive)]
    missing_months = [key for key in expected_months if key not in months_by_key]
    variable_failures = [
        contract["period_start"]
        for contract in contracts
        if contract["period_start"] in used_contract_starts
        and contract["variable_cost_reconciliation_difference_eur"] is not None
        and abs(contract["variable_cost_reconciliation_difference_eur"]) > 0.1000001
    ]
    total_failures = [
        contract["period_start"]
        for contract in contracts
        if contract["period_start"] in used_contract_starts
        and abs(contract["total_cost_reconciliation_difference_eur"]) > 0.0100001
    ]

    return {
        "schema_version": 1,
        "canonical_period": {
            "start": canonical_start,
            "end_exclusive": canonical_end_exclusive,
        },
        "contracts": contracts,
        "months": [months_by_key[key] for key in sorted(months_by_key)],
        "quality": {
            "contract_block_count": len(contracts),
            "expected_month_count": len(expected_months),
            "month_count": len(months_by_key),
            "missing_month_count": len(missing_months),
            "missing_months": missing_months,
            "overlap_month_count": len(overlaps),
            "overlap_months": overlaps,
            "variable_cost_reconciliation_failure_count": len(variable_failures),
            "variable_cost_reconciliation_failures": variable_failures,
            "variable_cost_reconciliation_tolerance_eur": 0.1,
            "total_cost_reconciliation_failure_count": len(total_failures),
            "total_cost_reconciliation_failures": total_failures,
            "stored_day_count_mismatch_count": sum(
                contract["stored_day_count_mismatch"] for contract in contracts
            ),
        },
        "limitations": {
            "independent_invoice_validation": False,
            "fixed_cost_component_decomposition_available": False,
            "grid_capacity_tax_levy_components_separated": False,
            "interpretation": (
                "The export proves DSMR internal all-in rate and displayed-cost consistency; "
                "it does not independently validate invoices or decompose fixed/common charges."
            ),
        },
        "safety": {
            "read_only": True,
            "physical_writes_allowed": False,
            "contract_change_allowed": False,
        },
    }


def parse_contract_export(
    path: Path, canonical_start: str, canonical_end_exclusive: str
) -> dict[str, Any]:
    return parse_contract_export_text(
        path.read_text(encoding="utf-8"), canonical_start, canonical_end_exclusive
    )


def privacy_safe_report(report: dict[str, Any]) -> dict[str, Any]:
    safe_contracts = []
    for contract in report["contracts"]:
        safe_contracts.append(
            {
                key: value
                for key, value in contract.items()
                if key
                not in {
                    "displayed_variable_cost_eur",
                    "calculated_variable_cost_eur",
                    "displayed_fixed_cost_eur",
                    "displayed_total_cost_eur",
                }
            }
        )
    return {**report, "contracts": safe_contracts}


def build_historical_tariff_ledger(
    report: dict[str, Any], ha_import_values: dict[str, float]
) -> dict[str, Any]:
    months = []
    for source in report["months"]:
        month_start = date.fromisoformat(f"{source['month']}-01")
        month_end = next_month(month_start)
        ha_value = ha_import_values.get(source["month"])
        difference = (
            None
            if ha_value is None
            else round(ha_value - source["import_eur_per_kwh"], 6)
        )
        source_label = (
            "DSMR_EXPORT_HA_MATCH"
            if difference == 0.0
            else "DSMR_EXPORT_OWNER_PROVIDED"
        )
        verification_status = (
            "DSMR_EXPORT_HA_RECONCILED"
            if difference == 0.0
            else "DSMR_EXPORT_COST_RECONCILED"
        )
        months.append(
            {
                "month": source["month"],
                "period_start": month_start.isoformat(),
                "period_end_exclusive": month_end.isoformat(),
                "provider": source["provider"],
                "dsmr_contract_start": source["source_period_start"],
                "dsmr_contract_end": source["source_period_end_inclusive"],
                "dsmr_import_eur_per_kwh": source["import_eur_per_kwh"],
                "dsmr_export_eur_per_kwh": source["export_eur_per_kwh"],
                "dsmr_fixed_daily_cost_eur": source["fixed_daily_cost_eur"],
                "ha_import_eur_per_kwh": ha_value,
                "selected_import_eur_per_kwh": source["import_eur_per_kwh"],
                "selected_import_source": source_label,
                "selected_export_eur_per_kwh": source["export_eur_per_kwh"],
                "selected_export_source": "DSMR_EXPORT_OWNER_PROVIDED",
                "ha_dsmr_difference_eur_per_kwh": difference,
                "calculation_scope": "RECONCILED_ALL_IN_RATE_SENSITIVITY",
                "verification_status": verification_status,
            }
        )

    disagreements = [
        row["month"]
        for row in months
        if row["ha_dsmr_difference_eur_per_kwh"] not in (None, 0.0)
    ]
    return {
        "schema_version": 2,
        "classification": "READ_ONLY_HISTORICAL_TARIFF_LEDGER",
        "period_start": report["canonical_period"]["start"],
        "period_end_exclusive": report["canonical_period"]["end_exclusive"],
        "source_evidence": (
            "docs/evidence/dsmr-contract-price-ledger-2023-10_2026-09.json"
        ),
        "months": months,
        "quality": {
            "month_count": len(months),
            "ha_crosscheck_month_count": sum(
                row["ha_import_eur_per_kwh"] is not None for row in months
            ),
            "ha_dsmr_disagreement_count": len(disagreements),
            "ha_dsmr_disagreement_months": disagreements,
        },
        "limitations": {
            "all_in_rate_semantics_requires_confirmation": False,
            "vat_inclusion_requires_confirmation": True,
            "fixed_cost_component_decomposition_available": False,
            "not_component_complete_billing": True,
        },
        "safety": {
            "home_assistant_writes": False,
            "contract_change": False,
            "physical_writes_allowed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("docs/information/energy_contracts_export_dsmr.txt"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "docs/evidence/dsmr-contract-price-ledger-2023-10_2026-09.json"
        ),
    )
    parser.add_argument(
        "--ledger-output",
        type=Path,
        default=Path("config/tariffs/historical-electricity-2023-10_2026-09.json"),
    )
    parser.add_argument(
        "--ha-import-prices",
        type=Path,
        default=Path("config/tariffs/ecopower-monthly-2026-ha.json"),
    )
    parser.add_argument("--start", default="2023-10-01")
    parser.add_argument("--end-exclusive", default="2026-10-01")
    args = parser.parse_args()

    report = parse_contract_export(args.input, args.start, args.end_exclusive)
    if report["quality"]["missing_month_count"] or report["quality"]["overlap_month_count"]:
        raise SystemExit(f"Invalid contract-month coverage: {report['quality']}")
    if report["quality"]["variable_cost_reconciliation_failure_count"]:
        raise SystemExit(f"Variable cost reconciliation failed: {report['quality']}")
    if report["quality"]["total_cost_reconciliation_failure_count"]:
        raise SystemExit(f"Total cost reconciliation failed: {report['quality']}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(privacy_safe_report(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ha_values: dict[str, float] = {}
    if args.ha_import_prices.exists():
        ha_config = json.loads(args.ha_import_prices.read_text(encoding="utf-8"))
        ha_values = {
            key: float(value)
            for key, value in ha_config.get("values", {}).items()
            if args.start[:7] <= key < args.end_exclusive[:7]
        }
    ledger = build_historical_tariff_ledger(report, ha_values)
    args.ledger_output.parent.mkdir(parents=True, exist_ok=True)
    args.ledger_output.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {args.output} and {args.ledger_output} "
        f"with {len(report['months'])} monthly prices"
    )


if __name__ == "__main__":
    main()
