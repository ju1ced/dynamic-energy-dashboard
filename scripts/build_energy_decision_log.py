#!/usr/bin/env python3
"""Build a privacy-safe, read-only Energy Decision Log from validated evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "docs" / "evidence" / "energy-decision-log-2026-10-01.json"
)
RECORDED_AT = "2026-10-01T12:00:00+02:00"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def base_entry(
    *,
    entry_id: str,
    entry_kind: str,
    scenario_id: str,
    title: str,
    evidence_refs: list[str],
    reason: str,
    action_type: str,
    action_summary: str,
    confidence_level: str,
    confidence_score: float,
    confidence_basis: str,
    outcome_status: str,
    outcome_summary: str,
    metrics: dict[str, Any],
    reproduction_script: str,
    reproduction_arguments: list[str],
) -> dict[str, Any]:
    return {
        "id": entry_id,
        "recorded_at": RECORDED_AT,
        "entry_kind": entry_kind,
        "scenario_id": scenario_id,
        "title": title,
        "inputs": {
            "evidence_refs": evidence_refs,
            "data_classification": "PRIVACY_SAFE_DERIVED_EVIDENCE",
        },
        "constraints": {
            "read_only": True,
            "physical_writes_allowed": False,
            "contract_change_allowed": False,
            "production_automation_allowed": False,
        },
        "reason": reason,
        "proposed_action": {
            "type": action_type,
            "summary": action_summary,
            "production_command": None,
            "setpoint": None,
        },
        "confidence": {
            "level": confidence_level,
            "score": confidence_score,
            "basis": confidence_basis,
        },
        "outcome": {
            "status": outcome_status,
            "summary": outcome_summary,
            "metrics": metrics,
        },
        "reproduction": {
            "script": reproduction_script,
            "arguments": reproduction_arguments,
        },
    }


def build_decision_log(root: Path = ROOT) -> dict[str, Any]:
    shadow = load_json(
        root
        / "docs"
        / "evidence"
        / "shadow-bill-scenario-a-2025-06-01_2026-06-01.json"
    )
    multi_year = load_json(
        root
        / "docs"
        / "evidence"
        / "multiyear-energy-battery-summary-2023-10-01_2026-10-01.json"
    )
    battery = load_json(
        root
        / "docs"
        / "evidence"
        / "battery-arbitrage-simulation-summary-2026-01-22_2026-09-30.json"
    )
    forecast_quality = load_json(
        root
        / "docs"
        / "evidence"
        / "pv-forecast-quality-2026-09-24_2026-09-30.json"
    )
    dsmr_invoice = load_json(
        root
        / "docs"
        / "evidence"
        / "dsmr-contract-invoice-reconciliation-2025-06_2026-05.json"
    )

    invoice_comparison = shadow["invoice_comparison"]
    scenario_overview = multi_year["scenario_overview"]
    computed = {row["id"]: row for row in scenario_overview["computed"]}
    peak_caps = {float(row["cap_kw"]): row for row in scenario_overview["peak_caps"]}
    financial = multi_year["three_year_financial_sensitivity"]

    entries = [
        base_entry(
            entry_id="EDL-2026-10-01-001",
            entry_kind="MEASUREMENT_CONCLUSION",
            scenario_id="shadow_bill_scenario_a",
            title="Scenario A is retrospectief goedkoper",
            evidence_refs=[
                "docs/evidence/SHADOW_BILL_SCENARIO_A_2025-06_TO_2026-05.md",
                "docs/evidence/shadow-bill-scenario-a-2025-06-01_2026-06-01.json",
            ],
            reason="Dezelfde 35.040 Fluvius-kwartieren zijn met de gevalideerde dynamische formule tegen de gereconcilieerde jaarfactuur vergeleken.",
            action_type="RECONCILE_BEFORE_CONTRACT_DECISION",
            action_summary="Behoud de uitkomst als backtest en rond de historische componentreconciliatie af voordat een contractadvies wordt gegeven.",
            confidence_level="HIGH",
            confidence_score=0.95,
            confidence_basis="Volledig factuurjaar, volledige prijsdekking en gereconcilieerde import- en exportvolumes.",
            outcome_status="VERIFIED",
            outcome_summary="Dynamisch is in de gevalideerde jaarbacktest lager, zonder gedragswijziging.",
            metrics={
                "difference_eur_incl_vat": invoice_comparison[
                    "difference_eur_incl_vat"
                ],
                "energy_interval_count": shadow["quality"]["energy_interval_count"],
                "missing_price_interval_count": shadow["quality"][
                    "missing_price_interval_count"
                ],
            },
            reproduction_script="scripts/shadow_bill_scenario_a.py",
            reproduction_arguments=["--help"],
        ),
        base_entry(
            entry_id="EDL-2026-10-01-002",
            entry_kind="MEASUREMENT_CONCLUSION",
            scenario_id="three_year_energy_trend",
            title="Netafhankelijkheid is over drie jaar gestegen",
            evidence_refs=[
                "docs/evidence/MULTIYEAR_ENERGY_BATTERY_COMPARISON_2023-10_TO_2026-09.md",
                "docs/evidence/multiyear-energy-battery-summary-2023-10-01_2026-10-01.json",
            ],
            reason="De drie volledige lokale Fluvius-jaren tonen meer afname, minder injectie en een hogere afnamegewogen marktprijs.",
            action_type="PRIORITIZE_SOFTWARE_SCENARIOS",
            action_summary="Prioriteer contract- en softwarematige optimalisatie boven extra hardware.",
            confidence_level="HIGH",
            confidence_score=0.94,
            confidence_basis="105.216 kwartieren zijn gekoppeld; zes onbeschikbare kwartieren blijven expliciet zichtbaar.",
            outcome_status="VERIFIED",
            outcome_summary="Het laatste jaar is sterker afhankelijk van netafname dan het eerste jaar.",
            metrics={
                "import_change_percent": multi_year["trend"][
                    "first_to_last_import_change_percent"
                ],
                "export_change_percent": multi_year["trend"][
                    "first_to_last_export_change_percent"
                ],
                "unavailable_interval_count": multi_year["quality"][
                    "unavailable_interval_count"
                ],
            },
            reproduction_script="scripts/analyze_multiyear_energy_battery.py",
            reproduction_arguments=["--help"],
        ),
        base_entry(
            entry_id="EDL-2026-10-01-003",
            entry_kind="SIMULATION_DECISION",
            scenario_id="peak_neutral_winter_grid_charging",
            title="Winterse piekneutrale netlading eerst shadow-testen",
            evidence_refs=[
                "docs/evidence/SCENARIO_OPTIONS_OVERVIEW_2023-10_TO_2026-09.md",
                "docs/evidence/multiyear-energy-battery-summary-2023-10-01_2026-10-01.json",
            ],
            reason="De perfecte piekneutrale bovengrens is positief, terwijl extra hardware niet nodig is.",
            action_type="BUILD_OFFLINE_SHADOW_CONTROLLER",
            action_summary="Bouw een offline Day-Ahead-shadowplanning met forecastfouten en zonder apparaatwrites.",
            confidence_level="MEDIUM",
            confidence_score=0.64,
            confidence_basis="Drie volledige jaren zijn doorgerekend, maar de optimizer gebruikt perfecte kennis van prijs en residueel profiel.",
            outcome_status="PROPOSED",
            outcome_summary="Kandidaat voor de volgende read-only simulatie-iteratie.",
            metrics={
                "average_value_eur_per_year": computed[
                    "peak_neutral_winter_grid_charging"
                ]["value_eur_per_year"],
                "winter_value_eur_per_year": computed[
                    "peak_neutral_winter_grid_charging"
                ]["winter_value_eur_per_year"],
            },
            reproduction_script="scripts/analyze_multiyear_energy_battery.py",
            reproduction_arguments=["--help"],
        ),
        base_entry(
            entry_id="EDL-2026-10-01-004",
            entry_kind="SIMULATION_DECISION",
            scenario_id="shared_grid_peak_cap_7kw",
            title="7 kW alleen als expliciete gezamenlijke guardrail testen",
            evidence_refs=[
                "docs/evidence/SCENARIO_OPTIONS_OVERVIEW_2023-10_TO_2026-09.md"
            ],
            reason="De 7 kW-grens is de enige onderzochte limiet waarbij prijsbewuste netlading in een jaar nodig was voor peak shaving.",
            action_type="OFFLINE_GUARDRAIL_TEST",
            action_summary="Test 7 kW naast 8 en 10 kW met expliciete headroom voor huis, warmtepomp, EV en batterijladen.",
            confidence_level="MEDIUM",
            confidence_score=0.70,
            confidence_basis="De gezamenlijke Fluvius-kwartierpiek is volledig beschikbaar, maar individuele lasten zijn niet gedesaggregeerd.",
            outcome_status="PROPOSED",
            outcome_summary="Geen productielimiet; uitsluitend een offline guardrail-scenario.",
            metrics={
                "historical_quarters_above_cap": peak_caps[7.0][
                    "baseline_quarter_count_above_cap"
                ],
                "maximum_historical_excess_kw": peak_caps[7.0][
                    "maximum_historical_excess_kw"
                ],
                "average_model_value_eur_per_year": peak_caps[7.0][
                    "average_net_saving_eur_per_year"
                ],
            },
            reproduction_script="scripts/analyze_multiyear_energy_battery.py",
            reproduction_arguments=["--help"],
        ),
        base_entry(
            entry_id="EDL-2026-10-01-005",
            entry_kind="SIMULATION_DECISION",
            scenario_id="additional_battery_capacity",
            title="Extra batterijcapaciteit uitstellen",
            evidence_refs=[
                "docs/evidence/MULTIYEAR_ENERGY_BATTERY_COMPARISON_2023-10_TO_2026-09.md",
                "docs/evidence/BATTERY_ARBITRAGE_SIMULATION_2026-01_TO_2026-09.md",
            ],
            reason="De perfecte bovengrens is te klein en de realistische Day-Ahead-test was negatief.",
            action_type="DEFER_INVESTMENT",
            action_summary="Geen extra batterij adviseren zonder installatiekost, levensduur en positieve realistische forecastsimulatie.",
            confidence_level="MEDIUM",
            confidence_score=0.83,
            confidence_basis="Zowel overlap- als driejaarsanalyses wijzen in dezelfde richting, maar hardwarekosten zijn nog niet ingevoerd.",
            outcome_status="DEFERRED",
            outcome_summary="Geen investeringscase ondersteund.",
            metrics={
                "perfect_upper_bound_eur_per_year": computed[
                    "additional_battery_capacity"
                ]["value_eur_per_year"],
                "realistic_overlap_value_eur": battery["central_results"][
                    "day_ahead_realistic"
                ]["net_incremental_saving_eur"],
            },
            reproduction_script="scripts/simulate_battery_arbitrage.py",
            reproduction_arguments=["--help"],
        ),
        base_entry(
            entry_id="EDL-2026-10-01-006",
            entry_kind="MEASUREMENT_CONCLUSION",
            scenario_id="solcast_daily_forecast_quality",
            title="Day-Ahead PV-forecast overschat de korte evaluatieperiode",
            evidence_refs=[
                "docs/evidence/PV_FORECAST_QUALITY_2026-09-24_TO_2026-09-30.md",
                "docs/evidence/pv-forecast-quality-2026-09-24_2026-09-30.json",
            ],
            reason="Zes bewaarde Day-Ahead-dagforecasts zijn tegen afgeleide werkelijke PV-dagenergie beoordeeld, met alle revisies en één retentiegat zichtbaar.",
            action_type="CALIBRATE_BEFORE_SHADOW_CONTROL",
            action_summary="Gebruik Solcast nog niet rechtstreeks voor batterijplanning; bouw eerst een langere issue-time-reeks en kalibreer de positieve bias.",
            confidence_level="MEDIUM",
            confidence_score=0.68,
            confidence_basis="De issue times en realisaties zijn reproduceerbaar, maar het evaluatievenster bevat slechts zeven doeldagen.",
            outcome_status="VERIFIED_WITH_LIMITATIONS",
            outcome_summary="De korte Day-Ahead-reeks heeft een positieve gemiddelde fout; ochtendupdates verbeterden de fout in dit venster niet.",
            metrics={
                "target_day_count": forecast_quality["quality"]["target_day_count"],
                "forecast_version_count": forecast_quality["quality"]["forecast_version_count"],
                "day_ahead_mean_error_kwh": forecast_quality["summary_by_horizon"]["day_ahead"]["mean_error_kwh"],
                "day_ahead_mean_absolute_error_kwh": forecast_quality["summary_by_horizon"]["day_ahead"]["mean_absolute_error_kwh"],
                "day_ahead_mape_percent": forecast_quality["summary_by_horizon"]["day_ahead"]["mean_absolute_percentage_error"],
            },
            reproduction_script="scripts/analyze_pv_forecast_quality.py",
            reproduction_arguments=[],
        ),
        base_entry(
            entry_id="EDL-2026-10-01-007",
            entry_kind="MEASUREMENT_CONCLUSION",
            scenario_id="dynamic_contract_component_reconciliation",
            title="DSMR-totaal maskeert afwijkende vaste en variabele componenten",
            evidence_refs=[
                "docs/evidence/MULTIYEAR_FINANCIAL_SENSITIVITY_2023-10_TO_2026-09.md",
                "docs/evidence/DSMR_CONTRACT_INVOICE_RECONCILIATION_2025-06_TO_2026-05.md",
                "docs/evidence/dsmr-contract-invoice-reconciliation-2025-06_2026-05.json",
                "config/tariffs/historical-electricity-2023-10_2026-09.json",
            ],
            reason="In het gevalideerde factuurjaar ligt het DSMR-totaal dicht bij de factuur, maar een te lage variabele kost en een te hoge vaste kost compenseren elkaar gedeeltelijk.",
            action_type="COMPLETE_TARIFF_RECONCILIATION",
            action_summary="Gebruik de DSMR-totalen niet als componentbewijs; splits de vaste dagkosten per jaar uit en toets ze tegen facturen en tariefkaarten.",
            confidence_level="HIGH",
            confidence_score=0.91,
            confidence_basis="Dezelfde twaalf maanden zijn rechtstreeks vergeleken met een gevalideerde privacy-safe factuurbaseline.",
            outcome_status="VERIFIED_WITH_LIMITATIONS",
            outcome_summary="De driejarige sensitivity blijft bruikbaar, maar de DSMR-componentverdeling is niet factuurgevalideerd en ondersteunt nog geen contractadvies.",
            metrics={
                "reconciled_average_saving_eur_per_year": financial[
                    "average_dynamic_saving_eur_per_year"
                ],
                "verification_status": financial["verification_status"],
                "dsmr_invoice_assessment": dsmr_invoice["assessment"],
                "dsmr_invoice_total_difference_eur": dsmr_invoice[
                    "difference_dsmr_minus_invoice"
                ]["total_eur"],
                "dsmr_invoice_variable_difference_eur": dsmr_invoice[
                    "difference_dsmr_minus_invoice"
                ]["variable_eur"],
                "dsmr_invoice_fixed_difference_eur": dsmr_invoice[
                    "difference_dsmr_minus_invoice"
                ]["fixed_eur"],
            },
            reproduction_script="scripts/reconcile_dsmr_contract_export_invoice.py",
            reproduction_arguments=[],
        ),
    ]

    return {
        "schema_version": 1,
        "classification": "ENERGY_DECISION_LOG",
        "mode": "READ_ONLY",
        "generated_at": RECORDED_AT,
        "entry_count": len(entries),
        "entries": entries,
    }


def write_decision_log(root: Path, output: Path) -> dict[str, Any]:
    payload = build_decision_log(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = write_decision_log(ROOT, args.output)
    print(f"wrote {args.output} ({payload['entry_count']} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
