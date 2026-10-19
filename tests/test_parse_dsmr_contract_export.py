import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "parse_dsmr_contract_export", ROOT / "scripts" / "parse_dsmr_contract_export.py"
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DsmrContractExportTests(unittest.TestCase):
    def test_parser_reconciles_displayed_costs_and_expands_contract_months(self):
        text = """EcoPower 31 days stored
Aug. 1, 2026 ←→ Aug. 31, 2026\tConsumed\tReturned\tCosts €
Electricity (total) kWh\t354.636\t106.320\t101.00
Fixed costs\t35.34
Total costs\t136.34
Contract prices
Dagtarief tariff 1\t0.297000
Nachttarief tariff 2\t0.297000
dagtarief teruglevering tariff 1\t0.040600
nachttarief teruglevering tariff 2\t0.040600
Fixed daily costs\t1.144000
"""
        report = MODULE.parse_contract_export_text(text, "2026-08-01", "2026-09-01")

        self.assertEqual(len(report["contracts"]), 1)
        self.assertEqual(len(report["months"]), 1)
        contract = report["contracts"][0]
        self.assertLessEqual(abs(contract["variable_cost_reconciliation_difference_eur"]), 0.01)
        self.assertAlmostEqual(contract["total_cost_reconciliation_difference_eur"], 0.0, places=2)
        self.assertEqual(report["months"][0]["month"], "2026-08")
        self.assertEqual(report["months"][0]["import_eur_per_kwh"], 0.297)

    def test_parser_uses_aggregate_contract_for_each_intersecting_month(self):
        text = """eMobility 243 days stored
July 1, 2023 ←→ Feb. 29, 2024\tConsumed\tReturned\tCosts €
Electricity (total) kWh\t6,463.587\t787.046\t2,078.38
Fixed costs\t281.88
Total costs\t2,360.26
Contract prices
Dagtarief tariff 1\t0.327156
Nachttarief tariff 2\t0.327156
dagtarief teruglevering tariff 1\t0.045920
nachttarief teruglevering tariff 2\t0.045920
Fixed daily costs\t1.155300
"""
        report = MODULE.parse_contract_export_text(text, "2023-10-01", "2024-03-01")

        self.assertEqual([row["month"] for row in report["months"]], [
            "2023-10", "2023-11", "2023-12", "2024-01", "2024-02"
        ])
        self.assertTrue(report["contracts"][0]["stored_day_count_mismatch"])

    def test_owner_export_produces_complete_three_year_ledger(self):
        report = MODULE.parse_contract_export(
            ROOT / "docs" / "information" / "energy_contracts_export_dsmr.txt",
            "2023-10-01",
            "2026-10-01",
        )

        self.assertEqual(len(report["months"]), 36)
        self.assertEqual(report["months"][0]["month"], "2023-10")
        self.assertEqual(report["months"][-1]["month"], "2026-09")
        march = next(row for row in report["months"] if row["month"] == "2026-03")
        self.assertEqual(march["import_eur_per_kwh"], 0.277)
        self.assertEqual(report["quality"]["missing_month_count"], 0)
        self.assertEqual(report["quality"]["variable_cost_reconciliation_failure_count"], 0)

        ledger = MODULE.build_historical_tariff_ledger(
            report, {"2026-03": 0.277, "2026-04": 0.2702}
        )
        march_ledger = next(row for row in ledger["months"] if row["month"] == "2026-03")
        self.assertEqual(march_ledger["selected_import_eur_per_kwh"], 0.277)
        self.assertEqual(march_ledger["selected_import_source"], "DSMR_EXPORT_HA_MATCH")
        self.assertEqual(march_ledger["ha_dsmr_difference_eur_per_kwh"], 0.0)
        self.assertFalse(ledger["limitations"]["all_in_rate_semantics_requires_confirmation"])
        self.assertTrue(ledger["limitations"]["not_component_complete_billing"])


if __name__ == "__main__":
    unittest.main()
