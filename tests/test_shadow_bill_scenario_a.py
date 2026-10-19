import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "shadow_bill_scenario_a.py"


def load_module():
    spec = importlib.util.spec_from_file_location("shadow_bill", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load shadow billing module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TARIFF = {
    "version": "TEST_DYNAMIC",
    "timezone": "Europe/Brussels",
    "import_energy": {"market_multiplier": 0.00102, "offset_eur_per_kwh": 0.004},
    "export_energy": {"market_multiplier": 0.00098, "offset_eur_per_kwh": -0.015},
    "green_certificates_eur_per_kwh": 0.011,
    "combined_heat_power_eur_per_kwh": 0.00392,
    "subscription_eur_per_month": 5.0,
    "vat_rate_import": 0.06,
}


class ShadowBillScenarioATests(unittest.TestCase):
    def test_dynamic_formula_and_negative_injection_value_are_preserved(self):
        module = load_module()
        intervals = [
            {
                "start_utc": "2025-05-31T22:00:00+00:00",
                "start_local": "2025-06-01T00:00:00+02:00",
                "import_kwh": 2.0,
                "export_kwh": 1.0,
                "estimated": False,
            }
        ]
        prices = {"2025-05-31T22:00:00+00:00": -100.0}

        report = module.calculate_shadow_bill(intervals, prices, TARIFF)
        item = report["intervals"][0]

        self.assertAlmostEqual(item["import_rate_eur_per_kwh"], -0.098)
        self.assertAlmostEqual(item["export_rate_eur_per_kwh"], -0.113)
        self.assertAlmostEqual(item["import_energy_eur_excl_vat"], -0.196)
        self.assertAlmostEqual(item["export_value_eur_excl_vat"], -0.113)
        self.assertGreater(item["supplier_net_eur_excl_vat"], -0.196)

    def test_missing_price_fails_instead_of_filling(self):
        module = load_module()
        intervals = [
            {
                "start_utc": "2025-05-31T22:00:00+00:00",
                "start_local": "2025-06-01T00:00:00+02:00",
                "import_kwh": 1.0,
                "export_kwh": 0.0,
                "estimated": False,
            }
        ]

        with self.assertRaisesRegex(ValueError, "Missing market price"):
            module.calculate_shadow_bill(intervals, {}, TARIFF)

    def test_estimated_intervals_and_monthly_subscription_are_reported(self):
        module = load_module()
        intervals = [
            {
                "start_utc": "2025-05-31T22:00:00+00:00",
                "start_local": "2025-06-01T00:00:00+02:00",
                "import_kwh": 1.0,
                "export_kwh": 0.0,
                "estimated": True,
            },
            {
                "start_utc": "2025-05-31T22:15:00+00:00",
                "start_local": "2025-06-01T00:15:00+02:00",
                "import_kwh": 0.0,
                "export_kwh": 1.0,
                "estimated": False,
            },
        ]
        prices = {row["start_utc"]: 100.0 for row in intervals}

        report = module.calculate_shadow_bill(intervals, prices, TARIFF)

        self.assertEqual(report["quality"]["estimated_interval_count"], 1)
        self.assertEqual(report["quality"]["price_coverage_interval_count"], 2)
        self.assertGreater(report["totals"]["subscription_eur_excl_vat"], 0)
        self.assertLess(report["totals"]["subscription_eur_excl_vat"], 5.0)
        self.assertEqual(report["monthly"][0]["month"], "2025-06")

    def test_duplicate_autumn_local_time_has_two_distinct_utc_candidates(self):
        module = load_module()
        from datetime import datetime
        from zoneinfo import ZoneInfo

        candidates = module.utc_start_candidates(
            datetime(2025, 10, 26, 2, 0),
            datetime(2025, 10, 26, 2, 15),
            ZoneInfo("Europe/Brussels"),
        )

        self.assertEqual(len(candidates), 2)
        self.assertEqual((candidates[1] - candidates[0]).total_seconds(), 3600)

    def test_invoice_comparison_replaces_only_contract_dependent_components(self):
        module = load_module()
        dynamic = {
            "totals": {
                "supplier_net_eur_excl_vat": 1000.0,
                "import_vat_base_eur": 1100.0,
            }
        }
        invoice = {
            "components_eur_excl_vat": {
                "energy": 1192.08,
                "green_certificates": 100.78,
                "combined_heat_power_certificates": 35.91,
                "injection_credit": -23.21,
                "data_management": 17.65,
                "capacity_tariff": 300.06,
                "grid_withdrawal_tariff": 614.48,
                "energy_contribution": 17.65,
                "special_excise": 434.99,
                "energy_fund": 0.0,
            },
            "totals": {"excl_vat_eur": 2690.39, "vat_eur": 162.82, "incl_vat_eur": 2853.21},
            "vat_rate_import": 0.06,
        }

        comparison = module.compare_with_invoice(dynamic, invoice)

        self.assertAlmostEqual(comparison["unchanged_components_eur_excl_vat"], 1384.83)
        self.assertAlmostEqual(comparison["dynamic_total_eur_excl_vat"], 2384.83)
        self.assertAlmostEqual(comparison["dynamic_vat_eur"], (1384.83 + 1100.0) * 0.06)
        self.assertAlmostEqual(
            comparison["dynamic_total_eur_incl_vat"],
            comparison["dynamic_total_eur_excl_vat"] + comparison["dynamic_vat_eur"],
        )

    def test_daily_monthly_and_cumulative_supplier_differences_are_reproducible(self):
        module = load_module()
        intervals = [
            {
                "start_utc": "2025-05-31T22:00:00+00:00",
                "start_local": "2025-06-01T00:00:00+02:00",
                "import_kwh": 1.0,
                "export_kwh": 0.0,
                "estimated": False,
            },
            {
                "start_utc": "2025-06-01T22:00:00+00:00",
                "start_local": "2025-06-02T00:00:00+02:00",
                "import_kwh": 1.0,
                "export_kwh": 1.0,
                "estimated": False,
            },
        ]
        prices = {row["start_utc"]: 100.0 for row in intervals}
        dynamic = module.calculate_shadow_bill(intervals, prices, TARIFF)
        invoice = {
            "monthly_energy": [
                {"month": "2025-06", "amount_eur_excl_vat": 0.40}
            ],
            "components_eur_excl_vat": {
                "energy": 0.40,
                "green_certificates": 0.02,
                "combined_heat_power_certificates": 0.01,
                "injection_credit": -0.10,
            },
        }

        module.add_historical_baseline(dynamic, invoice)

        self.assertAlmostEqual(dynamic["baseline"]["supplier_net_eur_excl_vat"], 0.33)
        self.assertEqual(len(dynamic["daily"]), 2)
        self.assertIn("supplier_difference_eur_excl_vat", dynamic["daily"][0])
        self.assertAlmostEqual(
            dynamic["daily"][-1]["cumulative_supplier_difference_eur_excl_vat"],
            dynamic["totals"]["supplier_difference_eur_excl_vat"],
        )


if __name__ == "__main__":
    unittest.main()
