#!/usr/bin/env python3
"""Reconstruct historical fixed electricity costs from official tariff cards."""

from __future__ import annotations

import argparse
import calendar
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def extract_monthly_peaks(summary: dict[str, Any]) -> dict[str, float]:
    peaks: dict[str, float] = {}
    for year in summary.get("years", []):
        rows = year["decision_scenarios"]["peak_neutral"]["pv_surplus_only"][
            "monthly_peaks"
        ]
        for row in rows:
            month = str(row["month"])
            peak = float(row["baseline_peak_kw"])
            if month in peaks and peaks[month] != peak:
                raise ValueError(f"conflicting monthly peak for {month}")
            peaks[month] = peak
    return peaks


def _month_days(month: str) -> tuple[int, int]:
    year, month_number = (int(part) for part in month.split("-"))
    return calendar.monthrange(year, month_number)[1], 366 if calendar.isleap(year) else 365


def _period_for_month(month: str, periods: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [
        period
        for period in periods
        if str(period["start_month"]) <= month
        < str(period["end_month_exclusive"])
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one rate period for {month}")
    return matches[0]


def build_fixed_cost_reconciliation(
    historical_months: list[dict[str, Any]],
    measured_monthly_peaks: dict[str, float],
    config: dict[str, Any],
) -> dict[str, Any]:
    periods = config.get("periods")
    overrides = config.get("monthly_peak_overrides_kw", {})
    if not isinstance(periods, list) or not isinstance(overrides, dict):
        raise ValueError("invalid fixed-cost configuration")

    rows: list[dict[str, Any]] = []
    for source in historical_months:
        month = str(source["month"])
        period = _period_for_month(month, periods)
        if month in overrides:
            peak_kw = float(overrides[month])
            peak_source = "OWNER_CONFIRMED_OVERRIDE"
        elif month in measured_monthly_peaks:
            peak_kw = float(measured_monthly_peaks[month])
            peak_source = "MODELED_INTERVAL_MAX_NOT_OFFICIAL_BILLING_PEAK"
        else:
            raise ValueError(f"monthly peak is missing for {month}")
        if peak_kw < 0:
            raise ValueError(f"monthly peak must be non-negative for {month}")

        days, days_in_year = _month_days(month)
        data_management = (
            float(period["data_management_eur_per_year_incl_vat"])
            * days
            / days_in_year
        )
        capacity = (
            float(period["capacity_eur_per_kw_year_incl_vat"])
            * max(2.5, peak_kw)
            / 12
        )
        supplier = (
            float(period["supplier_fixed_eur_per_year_incl_vat"])
            * days
            / days_in_year
        )
        energy_fund = float(period["energy_fund_eur_per_month"])
        reconstructed = data_management + capacity + supplier + energy_fund
        dsmr_fixed = float(source["dsmr_fixed_daily_cost_eur"]) * days
        rows.append(
            {
                "month": month,
                "provider": source["provider"],
                "calendar_days": days,
                "monthly_peak_kw": peak_kw,
                "monthly_peak_source": peak_source,
                "data_management_eur_incl_vat": data_management,
                "capacity_eur_incl_vat": capacity,
                "supplier_fixed_eur_incl_vat": supplier,
                "energy_fund_eur": energy_fund,
                "reconstructed_fixed_eur_incl_vat": reconstructed,
                "dsmr_fixed_eur_incl_vat": dsmr_fixed,
                "difference_dsmr_minus_reconstructed_eur": dsmr_fixed
                - reconstructed,
                "tariff_source": period["source"],
                "supplier_fixed_evidence_status": period.get(
                    "supplier_fixed_evidence_status", "UNSPECIFIED"
                ),
                "energy_fund_evidence_status": period.get(
                    "energy_fund_evidence_status", "UNSPECIFIED"
                ),
            }
        )

    by_year: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {
            "month_count": 0,
            "reconstructed_fixed_eur_incl_vat": 0.0,
            "dsmr_fixed_eur_incl_vat": 0.0,
        }
    )
    for row in rows:
        year, month_number = (int(part) for part in row["month"].split("-"))
        start_year = year if month_number >= 10 else year - 1
        label = f"{start_year}-{start_year + 1}"
        summary = by_year[label]
        summary["month_count"] = int(summary["month_count"]) + 1
        summary["reconstructed_fixed_eur_incl_vat"] = float(
            summary["reconstructed_fixed_eur_incl_vat"]
        ) + float(row["reconstructed_fixed_eur_incl_vat"])
        summary["dsmr_fixed_eur_incl_vat"] = float(
            summary["dsmr_fixed_eur_incl_vat"]
        ) + float(row["dsmr_fixed_eur_incl_vat"])

    years = []
    for label, values in sorted(by_year.items()):
        reconstructed = float(values["reconstructed_fixed_eur_incl_vat"])
        dsmr = float(values["dsmr_fixed_eur_incl_vat"])
        years.append(
            {
                "analysis_year": label,
                "month_count": int(values["month_count"]),
                "reconstructed_fixed_eur_incl_vat": round(reconstructed, 6),
                "dsmr_fixed_eur_incl_vat": round(dsmr, 6),
                "difference_dsmr_minus_reconstructed_eur": round(
                    dsmr - reconstructed, 6
                ),
            }
        )

    return {
        "schema_version": 1,
        "classification": "READ_ONLY_HISTORICAL_FIXED_COST_RECONCILIATION",
        "status": "MODELLED_WITH_UNVERIFIED_COMPONENTS",
        "generated_on": date.today().isoformat(),
        "months": rows,
        "years": years,
        "interpretation": (
            "Tariff-card components form a read-only model compared with DSMR daily "
            "configuration estimates. Differences are unresolved model residuals, not "
            "invoice residuals or savings."
        ),
        "evidence_limitations": [
            "Most monthly peaks are interval-derived maxima, not official Fluvius billing peaks.",
            "The TotalEnergies fixed supplier fee is not yet proven applicable to the 2023-07 contract start.",
            "The zero Energy Fund assumption still requires domiciliation or invoice evidence.",
            "April 2024 at 5.031 kW is owner-confirmed and lacks archived direct source evidence.",
            "No settlement invoice currently proves the reconstructed fixed-component totals.",
        ],
        "safety": {
            "read_only": True,
            "contract_change_allowed": False,
            "physical_writes_allowed": False,
            "production_automation_allowed": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Historische vaste-kostenreconciliatie 2023-10 tot 2025-09",
        "",
        f"Status: `{report['status']}`",
        "",
        "Modus: uitsluitend offline en read-only",
        "",
        "## Resultaat",
        "",
        "| Lokaal jaar | Maanden | Tariefkaartcomponenten incl. btw | DSMR-vaste kost | DSMR minus reconstructie |",
        "|---|---:|---:|---:|---:|",
    ]
    for year in report["years"]:
        lines.append(
            f"| {year['analysis_year']} | `{year['month_count']}` | "
            f"`€{year['reconstructed_fixed_eur_incl_vat']:.2f}` | "
            f"`€{year['dsmr_fixed_eur_incl_vat']:.2f}` | "
            f"`€{year['difference_dsmr_minus_reconstructed_eur']:.2f}` |"
        )
    lines.extend(
        [
            "",
            "De reconstructie modelleert per maand de vaste leverancierskost,",
            "databeheerkost, het capaciteitstarief en het Energiefonds op basis van",
            "tariefkaarten en nog niet volledig bewezen contract-/factuuraannames.",
            "De maandpiek van april 2024 is door de eigenaar gemeld als `5,031 kW`;",
            "direct gearchiveerd Fluvius-bewijs ontbreekt nog.",
            "",
            "DSMR-verschillen blijven zichtbaar als onopgeloste modelresiduen en worden",
            "niet als factuurverschil of contractbesparing geïnterpreteerd.",
            "",
            "## Open evidencebeperkingen",
            "",
            *[f"- {item}" for item in report["evidence_limitations"]],
            "",
            "## Bronnen",
            "",
            "- officiële TotalEnergies eMobility-tariefkaart december 2023;",
            "- officiële Ecopower-tariefkaarten januari 2024 en januari 2025;",
            "- Fluvius-kwartiermetingen voor de overige maandpieken;",
            "- eigenaarbevestiging van de officiële aprilpiek op 2026-10-05;",
            "- DSMR-contractexport voor de vergelijking met de ingestelde dagkosten.",
            "",
            "## Veiligheidsgrens",
            "",
            "Geen contractwijziging, Home Assistant-write of apparaatsturing is uitgevoerd.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--historical-ledger",
        type=Path,
        default=Path("config/tariffs/historical-electricity-2023-10_2026-09.json"),
    )
    parser.add_argument(
        "--multiyear-summary",
        type=Path,
        default=Path(
            "docs/evidence/multiyear-energy-battery-summary-2023-10-01_2026-10-01.json"
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "config/tariffs/historical-fixed-components-2023-10_2025-09.json"
        ),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path(
            "docs/evidence/historical-fixed-cost-reconciliation-2023-10_2025-09.json"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path(
            "docs/evidence/HISTORICAL_FIXED_COST_RECONCILIATION_2023-10_TO_2025-09.md"
        ),
    )
    args = parser.parse_args()

    historical = load_json(args.historical_ledger)["months"]
    config = load_json(args.config)
    start = str(config["scope_start_month"])
    end = str(config["scope_end_month_exclusive"])
    selected = [row for row in historical if start <= str(row["month"]) < end]
    peaks = extract_monthly_peaks(load_json(args.multiyear_summary))
    report = build_fixed_cost_reconciliation(selected, peaks, config)

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "years": report["years"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
