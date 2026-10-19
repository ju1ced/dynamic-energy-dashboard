import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reconcile_historical_fixed_costs",
    ROOT / "scripts" / "reconcile_historical_fixed_costs.py",
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class HistoricalFixedCostReconciliationTests(unittest.TestCase):
    def test_monthly_components_are_reconstructed_from_official_rates(self):
        historical_months = [
            {
                "month": "2024-01",
                "provider": "eMobility",
                "dsmr_fixed_daily_cost_eur": 1.0,
            }
        ]
        config = {
            "periods": [
                {
                    "start_month": "2024-01",
                    "end_month_exclusive": "2024-02",
                    "data_management_eur_per_year_incl_vat": 12.0,
                    "capacity_eur_per_kw_year_incl_vat": 120.0,
                    "supplier_fixed_eur_per_year_incl_vat": 60.0,
                    "energy_fund_eur_per_month": 0.0,
                    "source": "official-test-card",
                }
            ],
            "monthly_peak_overrides_kw": {"2024-01": 5.0},
        }

        report = MODULE.build_fixed_cost_reconciliation(
            historical_months, {}, config
        )

        row = report["months"][0]
        self.assertAlmostEqual(row["data_management_eur_incl_vat"], 12.0 * 31 / 366)
        self.assertAlmostEqual(row["capacity_eur_incl_vat"], 50.0)
        self.assertAlmostEqual(row["supplier_fixed_eur_incl_vat"], 60.0 * 31 / 366)
        self.assertAlmostEqual(row["reconstructed_fixed_eur_incl_vat"], 56.0983606557)
        self.assertAlmostEqual(row["dsmr_fixed_eur_incl_vat"], 31.0)
        self.assertEqual(row["monthly_peak_source"], "OWNER_CONFIRMED_OVERRIDE")
        self.assertTrue(report["safety"]["read_only"])
        self.assertFalse(report["safety"]["contract_change_allowed"])
        self.assertEqual(report["status"], "MODELLED_WITH_UNVERIFIED_COMPONENTS")

    def test_missing_peak_or_rate_period_fails_closed(self):
        month = {
            "month": "2024-01",
            "provider": "EcoPower",
            "dsmr_fixed_daily_cost_eur": 1.0,
        }
        config = {
            "periods": [],
            "monthly_peak_overrides_kw": {},
        }

        with self.assertRaisesRegex(ValueError, "rate period"):
            MODULE.build_fixed_cost_reconciliation([month], {}, config)

        config["periods"] = [
            {
                "start_month": "2024-01",
                "end_month_exclusive": "2024-02",
                "data_management_eur_per_year_incl_vat": 12.0,
                "capacity_eur_per_kw_year_incl_vat": 120.0,
                "supplier_fixed_eur_per_year_incl_vat": 0.0,
                "energy_fund_eur_per_month": 0.0,
                "source": "official-test-card",
            }
        ]
        with self.assertRaisesRegex(ValueError, "monthly peak"):
            MODULE.build_fixed_cost_reconciliation([month], {}, config)

    def test_owner_confirmed_april_peak_overrides_measured_series(self):
        config = {
            "periods": [
                {
                    "start_month": "2024-04",
                    "end_month_exclusive": "2024-05",
                    "data_management_eur_per_year_incl_vat": 0.0,
                    "capacity_eur_per_kw_year_incl_vat": 120.0,
                    "supplier_fixed_eur_per_year_incl_vat": 0.0,
                    "energy_fund_eur_per_month": 0.0,
                    "source": "official-test-card",
                }
            ],
            "monthly_peak_overrides_kw": {"2024-04": 5.031},
        }
        historical = [
            {
                "month": "2024-04",
                "provider": "EcoPower",
                "dsmr_fixed_daily_cost_eur": 0.0,
            }
        ]

        report = MODULE.build_fixed_cost_reconciliation(
            historical, {"2024-04": 5.032}, config
        )

        row = report["months"][0]
        self.assertEqual(row["monthly_peak_kw"], 5.031)
        self.assertEqual(row["monthly_peak_source"], "OWNER_CONFIRMED_OVERRIDE")
        self.assertAlmostEqual(row["capacity_eur_incl_vat"], 50.31)

    def test_production_config_uses_fluvius_west_row_and_source_hashes(self):
        config = MODULE.load_json(
            ROOT / "config/tariffs/historical-fixed-components-2023-10_2025-09.json"
        )

        self.assertEqual(config["periods"][0]["capacity_eur_per_kw_year_incl_vat"], 41.0823)
        self.assertEqual(
            config["monthly_peak_override_evidence"]["2024-04"],
            "OWNER_CONFIRMED_2026-10-05_MONTHLY_PEAK_REPORTED_AS_FLUVIUS",
        )
        self.assertTrue(all(source.get("sha256") for source in config["sources"]))
        self.assertEqual(
            config["periods"][0]["supplier_fixed_evidence_status"],
            "UNVERIFIED_CONTRACT_APPLICABILITY",
        )
        self.assertEqual(
            config["periods"][0]["energy_fund_evidence_status"],
            "DOMICILIATION_EVIDENCE_REQUIRED",
        )


if __name__ == "__main__":
    unittest.main()
