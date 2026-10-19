import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_dashboard_data", ROOT / "scripts" / "build_dashboard_data.py"
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DashboardDataTests(unittest.TestCase):
    def test_payload_is_read_only_and_reconciled(self):
        payload = MODULE.build_payload(ROOT)

        self.assertEqual(payload["mode"], "READ_ONLY")
        self.assertTrue(payload["method"]["read_only"])
        self.assertFalse(payload["method"]["raw_identifiers_included"])
        self.assertEqual(payload["quality"]["energy_interval_count"], 35040)
        self.assertEqual(payload["quality"]["price_interval_count"], 35040)
        self.assertEqual(payload["quality"]["missing_price_interval_count"], 0)
        self.assertEqual(payload["quality"]["estimated_interval_count"], 99)

    def test_financial_summary_matches_validated_evidence(self):
        payload = MODULE.build_payload(ROOT)

        self.assertEqual(payload["summary"]["historical_total_eur_incl_vat"], 2853.21)
        self.assertEqual(payload["summary"]["dynamic_total_eur_incl_vat"], 2607.12)
        self.assertEqual(payload["summary"]["difference_eur_incl_vat"], -246.09)
        self.assertEqual(len(payload["monthly"]), 12)

    def test_price_months_are_generated_when_raw_dataset_exists(self):
        payload = MODULE.build_payload(ROOT)

        raw_path = ROOT / "data" / "raw" / "entsoe-day-ahead-quarter-prices-2025-06-01_2026-06-01.json"
        if raw_path.exists():
            self.assertEqual(len(payload["prices"]["monthly"]), 12)
            self.assertTrue(all("average_eur_per_mwh" in row for row in payload["prices"]["monthly"]))

    def test_dashboard_loads_current_day_ahead_price_feed(self):
        app_source = (ROOT / "web-dashboard" / "app.js").read_text(
            encoding="utf-8"
        )
        view_source = (ROOT / "web-dashboard" / "day-ahead-view.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('fetch("data/day-ahead-prices.json"', app_source)
        self.assertIn("function priceComparisonChart", app_source)
        self.assertIn("aggregates.daily", app_source)
        self.assertIn("aggregates.weekly", app_source)
        self.assertIn("aggregates.monthly", app_source)
        self.assertIn('import { currentDayAheadView } from "./day-ahead-view.js"', app_source)
        self.assertIn("function currentDayAheadView", view_source)
        self.assertIn("Date.now()", view_source)
        self.assertIn('stale ? "STALE"', view_source)
        self.assertIn("row => Date.parse(row.start_utc) >= nowMs", view_source)
        self.assertIn("currentPrices.coverage.upcoming_interval_count", app_source)
        self.assertIn("const renderNow = Date.now()", app_source)
        self.assertEqual(app_source.count("currentDayAheadView("), 1)
        self.assertIn("renderPrices(state.data, currentPrices)", app_source)
        self.assertIn("renderContext(state.data, currentPrices)", app_source)
        self.assertIn("0,2770", app_source)
        self.assertIn("INDICATIEVE VERGELIJKING", app_source)

    def test_battery_summary_is_read_only_and_includes_realistic_result(self):
        payload = MODULE.build_payload(ROOT)

        battery = payload["battery_simulation"]
        self.assertEqual(battery["status"], "VERIFIED_WITH_LIMITATIONS")
        self.assertFalse(battery["physical_writes"])
        self.assertEqual(battery["quality"]["usable_hour_count"], 5814)
        self.assertLess(
            battery["central_results"]["day_ahead_realistic"][
                "net_incremental_saving_eur"
            ],
            0.0,
        )
        self.assertTrue(
            all(
                not row["realistic_investment_case_supported"]
                for row in battery["additional_capacity"]
            )
        )

    def test_multi_year_comparison_is_read_only_and_complete(self):
        payload = MODULE.build_payload(ROOT)

        comparison = payload["multi_year_comparison"]
        self.assertFalse(comparison["physical_writes"])
        self.assertEqual(comparison["quality"]["interval_count"], 105216)
        self.assertEqual(comparison["quality"]["unavailable_interval_count"], 6)
        self.assertEqual(len(comparison["years"]), 3)
        self.assertAlmostEqual(
            comparison["additional_capacity_three_year_average"][-1][
                "average_best_with_grid_charging_net_saving_eur_per_year"
            ],
            84.209486,
        )
        self.assertTrue(
            all("financial_sensitivity" in year for year in comparison["years"])
        )
        self.assertEqual(
            comparison["three_year_financial_sensitivity"]["verification_status"],
            "RATE_RECONCILED_FIXED_COMPONENTS_HELD_CONSTANT",
        )

    def test_dashboard_exposes_a_multi_year_view(self):
        index_source = (ROOT / "web-dashboard" / "index.html").read_text(
            encoding="utf-8"
        )
        app_source = (ROOT / "web-dashboard" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('data-view="multiyear"', index_source)
        self.assertIn('multiyear: "Meerjarig"', app_source)
        self.assertIn("function renderMultiYear", app_source)

    def test_dashboard_exposes_scenario_overview(self):
        payload = MODULE.build_payload(ROOT)
        index_source = (ROOT / "web-dashboard" / "index.html").read_text(
            encoding="utf-8"
        )
        app_source = (ROOT / "web-dashboard" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("scenario_overview", payload["multi_year_comparison"])
        self.assertIn('data-view="scenarios"', index_source)
        self.assertIn('scenarios: "Scenario\'s"', app_source)
        self.assertIn("function renderScenarios", app_source)

    def test_dashboard_exposes_read_only_shadow_controller_plan(self):
        payload = MODULE.build_payload(ROOT)
        index_source = (ROOT / "web-dashboard" / "index.html").read_text(
            encoding="utf-8"
        )
        app_source = (ROOT / "web-dashboard" / "app.js").read_text(
            encoding="utf-8"
        )

        plan = payload["shadow_controller_plan"]
        self.assertEqual(plan["mode"], "READ_ONLY_SHADOW")
        self.assertFalse(plan["physical_writes"])
        self.assertEqual(plan["interval_count"], 96)
        self.assertIn('data-view="steering"', index_source)
        self.assertIn('steering: "Sturing"', app_source)
        self.assertIn("function renderSteering", app_source)

    def test_dashboard_labels_three_year_financial_result_as_sensitivity(self):
        app_source = (ROOT / "web-dashboard" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("Geconfigureerd historisch", app_source)
        self.assertIn("Dynamische sensitiviteit", app_source)
        self.assertIn("niet component-compleet", app_source)

    def test_dashboard_uses_the_formal_energy_decision_log(self):
        payload = MODULE.build_payload(ROOT)
        app_source = (ROOT / "web-dashboard" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertEqual(payload["decision_log"]["mode"], "READ_ONLY")
        self.assertGreaterEqual(len(payload["decision_log"]["entries"]), 5)
        self.assertNotIn("decisions", payload)
        self.assertNotIn("data.decisions", app_source)
        self.assertIn("data.decision_log.entries", app_source)
        self.assertIn("Werkelijke meting", app_source)
        self.assertIn("Simulatiebesluit", app_source)

    def test_dashboard_exposes_forecast_quality_without_inferred_load_or_ev(self):
        payload = MODULE.build_payload(ROOT)
        app_source = (ROOT / "web-dashboard" / "app.js").read_text(
            encoding="utf-8"
        )

        forecast = payload["forecast_quality"]
        self.assertEqual(forecast["mode"], "READ_ONLY")
        self.assertGreaterEqual(forecast["quality"]["target_day_count"], 7)
        self.assertEqual(
            forecast["extensions"]["load_forecast"]["status"],
            "NOT_IMPLEMENTED_SEPARATE_STREAM",
        )
        self.assertIn("forecast_quality", app_source)
        self.assertIn("Forecastkwaliteit", app_source)


if __name__ == "__main__":
    unittest.main()
