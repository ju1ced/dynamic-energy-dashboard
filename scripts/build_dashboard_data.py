#!/usr/bin/env python3
"""Build privacy-safe, read-only dashboard data from validated project evidence."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "web-dashboard" / "data" / "dashboard-data.json"
SHADOW_EVIDENCE = ROOT / "docs" / "evidence" / "shadow-bill-scenario-a-2025-06-01_2026-06-01.json"
SHADOW_RAW = ROOT / "data" / "raw" / "shadow-bill-scenario-a-2025-06-01_2026-06-01.json"
PRICE_EVIDENCE = ROOT / "docs" / "evidence" / "entsoe-day-ahead-summary-2025-06-01_2026-06-01.json"
PRICE_RAW = ROOT / "data" / "raw" / "entsoe-day-ahead-quarter-prices-2025-06-01_2026-06-01.json"
HA_SMOKE = ROOT / "docs" / "evidence" / "ha-energy-export-smoke-2026-09-27_2026-09-29.json"
HA_RECONCILIATION = ROOT / "docs" / "evidence" / "ha-energy-export-and-grid-reconciliation-2026-01-22_2026-09-30.json"
BATTERY_EVIDENCE = ROOT / "docs" / "evidence" / "battery-arbitrage-simulation-summary-2026-01-22_2026-09-30.json"
MULTIYEAR_EVIDENCE = ROOT / "docs" / "evidence" / "multiyear-energy-battery-summary-2023-10-01_2026-10-01.json"
DECISION_LOG_EVIDENCE = ROOT / "docs" / "evidence" / "energy-decision-log-2026-10-01.json"
FORECAST_QUALITY_EVIDENCE = ROOT / "docs" / "evidence" / "pv-forecast-quality-2026-09-24_2026-09-30.json"
SHADOW_CONTROLLER_EVIDENCE = ROOT / "docs" / "evidence" / "shadow-controller-plan-2026-09-30.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def round_value(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def monthly_price_summary(price_data: dict[str, Any]) -> list[dict[str, Any]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for interval in price_data.get("intervals", []):
        buckets[interval["start_local"][:7]].append(float(interval["price_eur_per_mwh"]))

    return [
        {
            "month": month,
            "average_eur_per_mwh": round_value(sum(values) / len(values), 2),
            "minimum_eur_per_mwh": round_value(min(values), 2),
            "maximum_eur_per_mwh": round_value(max(values), 2),
            "negative_interval_count": sum(value < 0 for value in values),
        }
        for month, values in sorted(buckets.items())
    ]


def build_payload(root: Path = ROOT) -> dict[str, Any]:
    shadow = load_json(root / SHADOW_EVIDENCE.relative_to(ROOT))
    price = load_json(root / PRICE_EVIDENCE.relative_to(ROOT))
    ha_smoke = load_json(root / HA_SMOKE.relative_to(ROOT))
    ha_reconciliation = load_json(root / HA_RECONCILIATION.relative_to(ROOT))
    battery = load_json(root / BATTERY_EVIDENCE.relative_to(ROOT))
    multi_year = load_json(root / MULTIYEAR_EVIDENCE.relative_to(ROOT))
    decision_log = load_json(root / DECISION_LOG_EVIDENCE.relative_to(ROOT))
    forecast_quality = load_json(root / FORECAST_QUALITY_EVIDENCE.relative_to(ROOT))
    shadow_controller_plan = load_json(
        root / SHADOW_CONTROLLER_EVIDENCE.relative_to(ROOT)
    )

    raw_shadow_path = root / SHADOW_RAW.relative_to(ROOT)
    raw_price_path = root / PRICE_RAW.relative_to(ROOT)
    raw_shadow = load_json(raw_shadow_path) if raw_shadow_path.exists() else None
    raw_price = load_json(raw_price_path) if raw_price_path.exists() else None

    monthly = []
    daily = []
    if raw_shadow:
        monthly = [
            {
                "month": row["month"],
                "import_kwh": round_value(row["import_kwh"]),
                "export_kwh": round_value(row["export_kwh"]),
                "historical_supplier_eur_excl_vat": round_value(row["baseline_supplier_eur_excl_vat"], 2),
                "dynamic_supplier_eur_excl_vat": round_value(row["supplier_net_eur_excl_vat"], 2),
                "difference_eur_excl_vat": round_value(row["supplier_difference_eur_excl_vat"], 2),
                "cumulative_difference_eur_excl_vat": round_value(row["cumulative_supplier_difference_eur_excl_vat"], 2),
                "estimated_interval_count": row["estimated_interval_count"],
            }
            for row in raw_shadow["monthly"]
        ]
        daily = [
            {
                "date": row["date"],
                "import_kwh": round_value(row["import_kwh"]),
                "export_kwh": round_value(row["export_kwh"]),
                "difference_eur_excl_vat": round_value(row["supplier_difference_eur_excl_vat"], 3),
                "cumulative_difference_eur_excl_vat": round_value(row["cumulative_supplier_difference_eur_excl_vat"], 3),
                "estimated_interval_count": row["estimated_interval_count"],
            }
            for row in raw_shadow["daily"]
        ]
    else:
        cumulative = 0.0
        for month, difference in shadow["monthly_supplier_difference_eur_excl_vat"].items():
            cumulative += difference
            monthly.append(
                {
                    "month": month,
                    "difference_eur_excl_vat": round_value(difference, 2),
                    "cumulative_difference_eur_excl_vat": round_value(cumulative, 2),
                }
            )

    ha_series = {
        key: {"total_kwh": round_value(value["total_kwh"]), "quality_issue_count": sum(
            int(value.get(field, 0))
            for field in (
                "missing_5minute_count",
                "duplicate_5minute_count",
                "counter_decrease_count",
                "reported_change_mismatch_count",
            )
        )}
        for key, value in ha_smoke["series"].items()
    }

    comparison = shadow["invoice_comparison"]
    difference_incl = float(comparison["difference_eur_incl_vat"])
    baseline_incl = float(comparison["baseline_total_eur_incl_vat"])

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "classification": shadow["classification"],
        "period": {
            "start_local": shadow["period_start_local"],
            "end_local": shadow["period_end_local"],
        },
        "summary": {
            "historical_total_eur_incl_vat": round_value(baseline_incl, 2),
            "dynamic_total_eur_incl_vat": round_value(comparison["dynamic_total_eur_incl_vat"], 2),
            "difference_eur_incl_vat": round_value(difference_incl, 2),
            "difference_percentage": round_value((difference_incl / baseline_incl) * 100, 2),
            "historical_supplier_eur_excl_vat": round_value(shadow["historical_supplier_baseline"]["supplier_net_eur_excl_vat"], 2),
            "dynamic_supplier_eur_excl_vat": round_value(shadow["dynamic_supplier"]["supplier_net_eur_excl_vat"], 2),
            "import_kwh": round_value(shadow["energy"]["import_kwh"]),
            "export_kwh": round_value(shadow["energy"]["export_kwh"]),
        },
        "monthly": monthly,
        "daily": daily,
        "prices": {
            "minimum_eur_per_mwh": price["minimum_price_eur_per_mwh"],
            "maximum_eur_per_mwh": price["maximum_price_eur_per_mwh"],
            "negative_interval_count": price["negative_price_quarter_count"],
            "native_quarter_count": price["quarter_counts_by_source_resolution_minutes"]["15"],
            "expanded_hour_count": price["quarter_counts_by_source_resolution_minutes"]["60"],
            "variable_block_count": price["variable_sized_block_quarter_count"],
            "monthly": monthly_price_summary(raw_price) if raw_price else [],
        },
        "quality": {
            "energy_interval_count": shadow["quality"]["energy_interval_count"],
            "price_interval_count": shadow["quality"]["price_coverage_interval_count"],
            "estimated_interval_count": shadow["quality"]["estimated_interval_count"],
            "missing_price_interval_count": shadow["quality"]["missing_price_interval_count"],
            "sequence_complete": shadow["quality"]["sequence_complete"],
            "grid_reconciliation_import_difference_percentage": ha_reconciliation["grid_reconciliation"]["all_comparable"]["import"]["difference_percentage_of_fluvius"],
            "grid_reconciliation_export_difference_percentage": ha_reconciliation["grid_reconciliation"]["all_comparable"]["export"]["difference_percentage_of_fluvius"],
        },
        "recent_energy": {
            "period_start_utc": ha_smoke["period_start_utc"],
            "period_end_utc": ha_smoke["period_end_utc"],
            "series": ha_series,
        },
        "battery_simulation": {
            "status": battery["status"],
            "period_start_utc": battery["period_start_utc"],
            "period_end_utc": battery["period_end_utc"],
            "quality": battery["quality"],
            "battery": battery["battery"],
            "central_degradation_eur_per_discharged_kwh": battery[
                "central_degradation_eur_per_discharged_kwh"
            ],
            "central_results": battery["central_results"],
            "degradation_sensitivity": battery["degradation_sensitivity"],
            "additional_capacity": battery["additional_capacity"],
            "limitations": battery["limitations"],
            "physical_writes": battery["conclusion"]["physical_writes"],
        },
        "multi_year_comparison": multi_year,
        "data_retention": {
            "first_usable_quarter_utc": ha_reconciliation["five_minute_export"]["first_usable_quarter_utc"],
            "last_usable_quarter_utc": ha_reconciliation["five_minute_export"]["last_usable_quarter_utc"],
            "finding": ha_reconciliation["five_minute_export"]["retention_finding"],
        },
        "price_exposure": shadow["price_exposure"],
        "estimated_interval_sensitivity_eur_excl_vat": round_value(
            shadow["estimated_interval_sensitivity"]["difference_eur_excl_vat"], 2
        ),
        "decision_log": decision_log,
        "forecast_quality": forecast_quality,
        "shadow_controller_plan": shadow_controller_plan,
        "method": {
            "scenario": shadow["scenario"],
            "tariff_version": shadow["tariff_version"],
            "retrospective": True,
            "unchanged_behavior": True,
            "read_only": True,
            "raw_identifiers_included": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build_payload()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({len(payload['monthly'])} months, {len(payload['daily'])} days)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
