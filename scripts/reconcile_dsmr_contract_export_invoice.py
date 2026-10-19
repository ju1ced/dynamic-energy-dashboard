#!/usr/bin/env python3
"""Reconcile DSMR displayed contract costs with a privacy-safe invoice baseline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_dsmr_contract_export import parse_contract_export


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_reconciliation(
    dsmr_report: dict[str, Any], invoice: dict[str, Any]
) -> dict[str, Any]:
    used_contract_starts = {
        row["source_period_start"] for row in dsmr_report["months"]
    }
    contracts = [
        row
        for row in dsmr_report["contracts"]
        if row["period_start"] in used_contract_starts
    ]
    dsmr_variable = round(
        sum(float(row["displayed_variable_cost_eur"]) for row in contracts), 2
    )
    dsmr_fixed = round(
        sum(float(row["displayed_fixed_cost_eur"]) for row in contracts), 2
    )
    dsmr_total = round(sum(float(row["displayed_total_cost_eur"]) for row in contracts), 2)
    stored_days = sum(int(row["stored_days"]) for row in contracts)

    components = invoice["components_eur_excl_vat"]
    vat_rate = float(invoice["vat_rate_import"])
    fixed_vat_base = float(components["data_management"]) + float(
        components["capacity_tariff"]
    )
    energy_fund = float(components["energy_fund"])
    invoice_fixed_incl = round(fixed_vat_base * (1.0 + vat_rate) + energy_fund, 6)
    invoice_total = float(invoice["totals"]["incl_vat_eur"])
    invoice_variable_incl = round(invoice_total - invoice_fixed_incl, 6)

    variable_difference = round(dsmr_variable - invoice_variable_incl, 6)
    fixed_difference = round(dsmr_fixed - invoice_fixed_incl, 6)
    total_difference = round(dsmr_total - invoice_total, 6)
    total_difference_percent = round(total_difference / invoice_total * 100.0, 6)
    variable_difference_percent = round(
        variable_difference / invoice_variable_incl * 100.0, 6
    )
    fixed_difference_percent = round(fixed_difference / invoice_fixed_incl * 100.0, 6)

    start = date.fromisoformat(invoice["period_start"])
    end = date.fromisoformat(invoice["period_end_exclusive"])
    calendar_days = (end - start).days

    if (
        abs(total_difference_percent) < 1.0
        and abs(variable_difference) > 50.0
        and abs(fixed_difference) > 50.0
        and variable_difference * fixed_difference < 0.0
    ):
        assessment = "TOTAL_CLOSE_COMPONENT_MISMATCH"
    else:
        assessment = "REVIEW_REQUIRED"

    return {
        "schema_version": 1,
        "classification": "READ_ONLY_DSMR_INVOICE_RECONCILIATION",
        "period": {
            "start": invoice["period_start"],
            "end_exclusive": invoice["period_end_exclusive"],
            "calendar_day_count": calendar_days,
        },
        "dsmr": {
            "contract_block_count": len(contracts),
            "stored_day_count": stored_days,
            "stored_day_gap_vs_calendar": stored_days - calendar_days,
            "variable_eur_incl_vat": dsmr_variable,
            "fixed_eur_incl_vat": dsmr_fixed,
            "total_eur_incl_vat": dsmr_total,
            "source_semantics": "DSMR_DISPLAYED_ALL_IN_RATE_AND_FIXED_DAILY_COST",
        },
        "invoice": {
            "variable_eur_incl_vat": invoice_variable_incl,
            "fixed_eur_incl_vat": invoice_fixed_incl,
            "total_eur_incl_vat": invoice_total,
            "fixed_components": {
                "data_management_eur_excl_vat": float(components["data_management"]),
                "capacity_tariff_eur_excl_vat": float(components["capacity_tariff"]),
                "energy_fund_eur_vat_exempt": energy_fund,
            },
        },
        "difference_dsmr_minus_invoice": {
            "variable_eur": variable_difference,
            "variable_percent": variable_difference_percent,
            "fixed_eur": fixed_difference,
            "fixed_percent": fixed_difference_percent,
            "total_eur": total_difference,
            "total_percent": total_difference_percent,
        },
        "assessment": assessment,
        "independent_component_validation": False,
        "interpretation": (
            "The DSMR total is close to the invoice total only because a lower variable "
            "amount and a higher fixed amount partly offset. Total proximity therefore "
            "does not validate DSMR component allocation or fixed daily cost accuracy."
        ),
        "sources": [
            "docs/evidence/dsmr-contract-price-ledger-2023-10_2026-09.json",
            "docs/evidence/ecopower-invoice-baseline-2025-06-01_2026-05-31.json",
        ],
        "safety": {
            "read_only": True,
            "contract_change_allowed": False,
            "physical_writes_allowed": False,
            "production_automation_allowed": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    difference = report["difference_dsmr_minus_invoice"]
    dsmr = report["dsmr"]
    invoice = report["invoice"]
    return f"""# DSMR-contractexport versus Ecopower-factuur

Status: `VERIFIED_WITH_LIMITATIONS`

Classificatie: `{report['classification']}`

Periode: `{report['period']['start']}` tot `{report['period']['end_exclusive']}`

## Resultaat

| Kostgroep | DSMR-export | Factuur | DSMR minus factuur |
|---|---:|---:|---:|
| Variabel, incl. btw | `€{dsmr['variable_eur_incl_vat']:.2f}` | `€{invoice['variable_eur_incl_vat']:.2f}` | `€{difference['variable_eur']:.2f}` |
| Vast, incl. btw | `€{dsmr['fixed_eur_incl_vat']:.2f}` | `€{invoice['fixed_eur_incl_vat']:.2f}` | `€{difference['fixed_eur']:.2f}` |
| Totaal, incl. btw | `€{dsmr['total_eur_incl_vat']:.2f}` | `€{invoice['total_eur_incl_vat']:.2f}` | `€{difference['total_eur']:.2f}` |

Het totaal uit DSMR ligt slechts `{abs(difference['total_percent']):.2f}%` van de factuur,
maar dat maskeert twee tegengestelde componentverschillen: DSMR is bij de variabele
kosten `€{abs(difference['variable_eur']):.2f}` lager en bij de vaste kosten
`€{abs(difference['fixed_eur']):.2f}` hoger. De nabijheid van het totaal bewijst dus
niet dat de componenten of de vaste dagkost correct zijn.

DSMR telt `{dsmr['stored_day_count']}` opgeslagen dagen tegenover
`{report['period']['calendar_day_count']}` kalenderdagen. Dit verschil blijft als
kwaliteitsbeperking zichtbaar.

## Gevolg voor de driejarige sensitivity

De huidige conservatieve aanpak blijft correct: houd de historische DSMR-vaste
kosten gelijk in beide scenario's en voeg alleen het dynamische abonnement apart
toe. Behandel de DSMR-vaste dagkost niet als vermijdbare contractbesparing.

Voor definitief contractadvies moeten de vaste DSMR-kosten nog per jaar worden
uitgesplitst en onafhankelijk worden gekoppeld aan databeheer, capaciteitstarief,
Energiefonds en eventuele leverancierskosten.

## Veiligheidsgrens

Uitsluitend read-only analyse. Geen contractwijziging, productieautomatisatie of
apparaatsturing is uitgevoerd.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsmr-export",
        type=Path,
        default=Path("docs/information/energy_contracts_export_dsmr.txt"),
    )
    parser.add_argument(
        "--invoice",
        type=Path,
        default=Path(
            "docs/evidence/ecopower-invoice-baseline-2025-06-01_2026-05-31.json"
        ),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path(
            "docs/evidence/dsmr-contract-invoice-reconciliation-2025-06_2026-05.json"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path(
            "docs/evidence/DSMR_CONTRACT_INVOICE_RECONCILIATION_2025-06_TO_2026-05.md"
        ),
    )
    args = parser.parse_args()

    invoice = load_json(args.invoice)
    dsmr = parse_contract_export(
        args.dsmr_export,
        invoice["period_start"],
        invoice["period_end_exclusive"],
    )
    report = build_reconciliation(dsmr, invoice)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "assessment": report["assessment"],
                "total_difference_eur": report["difference_dsmr_minus_invoice"][
                    "total_eur"
                ],
                "variable_difference_eur": report[
                    "difference_dsmr_minus_invoice"
                ]["variable_eur"],
                "fixed_difference_eur": report["difference_dsmr_minus_invoice"][
                    "fixed_eur"
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
