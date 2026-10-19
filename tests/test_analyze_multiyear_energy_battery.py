import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_multiyear_energy_battery",
    ROOT / "scripts" / "analyze_multiyear_energy_battery.py",
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class MultiYearEnergyBatteryTests(unittest.TestCase):
    def test_dynamic_rate_components_keep_supplier_grid_tax_and_vat_separate(self):
        components = MODULE.dynamic_rate_components(
            100.0,
            {
                "import_energy": {
                    "market_multiplier": 0.00102,
                    "offset_eur_per_kwh": 0.004,
                },
                "export_energy": {
                    "market_multiplier": 0.00098,
                    "offset_eur_per_kwh": -0.015,
                },
                "green_certificates_eur_per_kwh": 0.011,
                "combined_heat_power_eur_per_kwh": 0.00392,
            },
            {
                "import_variable_components_excl_vat_eur_per_kwh": {
                    "grid": 0.1,
                    "excise": 0.05,
                },
                "vat_rate_import": 0.06,
            },
        )

        self.assertAlmostEqual(components["supplier_import_energy_excl_vat"], 0.106)
        self.assertAlmostEqual(components["green_certificates_excl_vat"], 0.011)
        self.assertAlmostEqual(components["combined_heat_power_excl_vat"], 0.00392)
        self.assertAlmostEqual(components["grid_and_tax_excl_vat"], 0.15)
        self.assertAlmostEqual(components["import_vat"], 0.0162552)
        self.assertAlmostEqual(components["import_total_incl_vat"], 0.2871752)
        self.assertAlmostEqual(components["export_total"], 0.083)

    def test_financial_sensitivity_uses_monthly_historical_rates_and_excludes_unavailable(self):
        rows = [
            {
                "start_local": MODULE.datetime(2025, 10, 1, tzinfo=MODULE.ZONE),
                "import_kwh": 2.0,
                "export_kwh": 1.0,
                "import_rate": 0.20,
                "export_rate": 0.05,
                "unavailable": False,
            },
            {
                "start_local": MODULE.datetime(2025, 11, 1, tzinfo=MODULE.ZONE),
                "import_kwh": 3.0,
                "export_kwh": 0.5,
                "import_rate": 0.30,
                "export_rate": 0.04,
                "unavailable": False,
            },
            {
                "start_local": MODULE.datetime(2025, 11, 1, 0, 15, tzinfo=MODULE.ZONE),
                "import_kwh": None,
                "export_kwh": None,
                "import_rate": 0.30,
                "export_rate": 0.04,
                "unavailable": True,
            },
        ]
        tariffs = {
            "2025-10": {
                "selected_import_eur_per_kwh": 0.40,
                "selected_export_eur_per_kwh": 0.10,
                "dsmr_fixed_daily_cost_eur": 1.0,
                "selected_import_source": "DSMR",
                "provider": "EcoPower",
            },
            "2025-11": {
                "selected_import_eur_per_kwh": 0.50,
                "selected_export_eur_per_kwh": 0.20,
                "dsmr_fixed_daily_cost_eur": 2.0,
                "selected_import_source": "HA_OWNER_CONFIRMED",
                "provider": "EcoPower",
            },
        }

        result = MODULE.summarize_financial_sensitivity(
            rows, tariffs, dynamic_subscription_eur_per_month_incl_vat=5.3
        )

        self.assertEqual(result["calculation_scope"], "RECONCILED_ALL_IN_RATE_SENSITIVITY")
        self.assertEqual(result["usable_interval_count"], 2)
        self.assertEqual(result["unavailable_interval_count"], 1)
        self.assertAlmostEqual(result["historical_import_charge_eur"], 2.3)
        self.assertAlmostEqual(result["historical_export_credit_eur"], 0.2)
        self.assertAlmostEqual(result["historical_net_variable_cost_eur"], 2.1)
        self.assertAlmostEqual(result["dynamic_import_charge_eur"], 1.3)
        self.assertAlmostEqual(result["dynamic_export_credit_eur"], 0.07)
        self.assertAlmostEqual(result["dynamic_net_variable_cost_eur"], 1.23)
        self.assertAlmostEqual(result["historical_fixed_cost_eur"], 91.0)
        self.assertAlmostEqual(result["dynamic_subscription_eur"], 10.6)
        self.assertAlmostEqual(result["historical_total_cost_eur"], 93.1)
        self.assertAlmostEqual(result["dynamic_total_cost_eur"], 102.83)
        self.assertAlmostEqual(result["dynamic_minus_historical_variable_eur"], -0.87)
        self.assertAlmostEqual(result["dynamic_minus_historical_eur"], 9.73)
        self.assertEqual(result["selected_import_sources"], ["DSMR", "HA_OWNER_CONFIRMED"])

    def test_three_year_financial_summary_uses_fixed_adjusted_totals(self):
        rows = [
            {
                "historical_net_variable_cost_eur": 100.0,
                "dynamic_net_variable_cost_eur": 80.0,
                "historical_fixed_cost_eur": 30.0,
                "dynamic_subscription_eur": 6.0,
                "historical_total_cost_eur": 130.0,
                "dynamic_total_cost_eur": 116.0,
                "limitations": ["limited"],
            },
            {
                "historical_net_variable_cost_eur": 120.0,
                "dynamic_net_variable_cost_eur": 110.0,
                "historical_fixed_cost_eur": 40.0,
                "dynamic_subscription_eur": 6.0,
                "historical_total_cost_eur": 160.0,
                "dynamic_total_cost_eur": 156.0,
                "limitations": ["limited"],
            },
        ]

        result = MODULE.summarize_three_year_financial_sensitivity(rows)

        self.assertEqual(result["historical_total_cost_eur"], 290.0)
        self.assertEqual(result["dynamic_total_cost_eur"], 272.0)
        self.assertEqual(result["dynamic_minus_historical_eur"], -18.0)
        self.assertEqual(result["average_dynamic_saving_eur_per_year"], 9.0)

    def test_sunny_energy_parser_reads_decimal_commas_and_missing_values(self):
        content = (
            "sep=;\n"
            "Periode;Totale opwekking [kWh];Totaalverbruik [kWh];Direct verbruik [kWh];"
            "Teruglevering [kWh];Netafname [kWh];Lading batterijsysteem [kWh];"
            "Ontlading batterijsysteem [kWh]\n"
            "1-1-2025;1,25;4,00;1,00;0,25;3,00;0,50;0,40\n"
            "2-1-2025;2,00;5,00;1,50;0,50;3,50;-;0,00\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "energy.csv"
            path.write_text(content, encoding="utf-8")
            rows = MODULE.load_sunny_energy_files([path])

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["date"].isoformat(), "2025-01-01")
        self.assertAlmostEqual(rows[0]["battery_charge_kwh"], 0.5)
        self.assertIsNone(rows[1]["battery_charge_kwh"])

    def test_sunny_power_parser_preserves_duplicate_autumn_local_times(self):
        content = (
            "sep=;\n"
            "Periode;Totale opwekking [kW];Totaalverbruik [kW];Direct verbruik [kW];"
            "Teruglevering [kW];Netafname [kW];Lading batterijsysteem [kW];"
            "Ontlading batterijsysteem [kW];Laadtoestand van de batterij [%]\n"
            "26-10-2025 02:00:00;0;1;0;0;1;0;0;10\n"
            "26-10-2025 02:00:00;0;1;0;0;1;0;0;10\n"
            "26-10-2025 02:05:00;0;1;0;0;1;0;0;10\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "power.csv"
            path.write_text(content, encoding="utf-8")
            rows, quality = MODULE.load_sunny_power_files([path])

        self.assertEqual(len(rows), 3)
        self.assertEqual(quality["duplicate_local_timestamp_count"], 1)
        self.assertEqual(rows[0]["timestamp_local"], rows[1]["timestamp_local"])

    def test_grid_charging_uses_low_price_before_high_price_import(self):
        rows = [
            {
                "base_net_kwh": 1.0,
                "import_rate": 0.10,
                "export_rate": 0.0,
                "duration_hours": 0.25,
            },
            {
                "base_net_kwh": 1.0,
                "import_rate": 0.60,
                "export_rate": 0.0,
                "duration_hours": 0.25,
            },
        ]
        result = MODULE.optimize_residual_segment(
            rows,
            capacity_kwh=1.0,
            max_charge_kw=4.0,
            max_discharge_kw=4.0,
            charge_efficiency=1.0,
            discharge_efficiency=1.0,
            degradation_eur_per_discharged_kwh=0.0,
            state_step_kwh=0.5,
            initial_soc_kwh=0.0,
            terminal_soc_kwh=0.0,
            allow_grid_charge=True,
            allow_battery_export=False,
        )

        self.assertAlmostEqual(result["schedule"][0]["charge_kwh"], 1.0)
        self.assertAlmostEqual(result["schedule"][1]["discharge_kwh"], 1.0)
        self.assertAlmostEqual(result["savings_eur"], 0.5)

    def test_pv_only_mode_cannot_charge_from_positive_base_net(self):
        rows = [
            {
                "base_net_kwh": 1.0,
                "import_rate": 0.10,
                "export_rate": 0.0,
                "duration_hours": 0.25,
            },
            {
                "base_net_kwh": 1.0,
                "import_rate": 0.60,
                "export_rate": 0.0,
                "duration_hours": 0.25,
            },
        ]
        result = MODULE.optimize_residual_segment(
            rows,
            capacity_kwh=1.0,
            max_charge_kw=4.0,
            max_discharge_kw=4.0,
            charge_efficiency=1.0,
            discharge_efficiency=1.0,
            degradation_eur_per_discharged_kwh=0.0,
            state_step_kwh=0.5,
            initial_soc_kwh=0.0,
            terminal_soc_kwh=0.0,
            allow_grid_charge=False,
            allow_battery_export=False,
        )

        self.assertAlmostEqual(result["totals"]["charge_kwh"], 0.0)
        self.assertAlmostEqual(result["totals"]["discharge_kwh"], 0.0)

    def test_grid_charging_option_falls_back_to_pv_only_when_peak_cost_is_worse(self):
        pv_only = {"net_saving_eur": 30.0, "allow_grid_charge": False}
        grid_candidate = {"net_saving_eur": 20.0, "allow_grid_charge": True}

        selected = MODULE.select_best_grid_charging_option(pv_only, grid_candidate)

        self.assertEqual(selected["net_saving_eur"], 30.0)
        self.assertEqual(selected["selected_source"], "pv_surplus_only_fallback")
        self.assertEqual(selected["incremental_value_of_grid_charging_eur"], 0.0)

    def test_sunny_dispatch_estimates_grid_supplied_battery_charge(self):
        summary = MODULE.summarize_sunny_power_dispatch(
            [
                {
                    "timestamp_local": MODULE.datetime(2025, 12, 1, 1, 0),
                    "duration_hours": 0.25,
                    "battery_charge_kw": 1.0,
                    "battery_discharge_kw": 0.0,
                    "pv_generation_kw": 0.0,
                    "total_consumption_kw": 0.0,
                    "grid_import_kw": 1.0,
                }
            ]
        )

        self.assertAlmostEqual(summary["total"]["battery_charge_kwh"], 0.25)
        self.assertAlmostEqual(
            summary["total"]["estimated_grid_charge_kwh"], 0.25
        )

    def test_peak_exposure_reports_quarters_power_and_energy_above_cap(self):
        summary = MODULE.summarize_peak_exposure(
            [
                {"base_net_kwh": 1.5, "duration_hours": 0.25},
                {"base_net_kwh": 2.0, "duration_hours": 0.25},
                {"base_net_kwh": -0.5, "duration_hours": 0.25},
            ],
            cap_kw=7.0,
        )

        self.assertEqual(summary["quarter_count_above_cap"], 1)
        self.assertAlmostEqual(summary["observed_peak_kw"], 8.0)
        self.assertAlmostEqual(summary["maximum_excess_kw"], 1.0)
        self.assertAlmostEqual(summary["excess_energy_kwh"], 0.25)

    def test_absolute_peak_cap_is_recorded_and_respected(self):
        start = MODULE.datetime(2025, 1, 1, tzinfo=MODULE.timezone.utc)
        rows = [
            {
                "start_utc": start,
                "start_local": start.astimezone(MODULE.ZONE),
                "base_net_kwh": 0.75,
                "import_rate": 0.10,
                "export_rate": 0.0,
                "duration_hours": 0.25,
            },
            {
                "start_utc": start + MODULE.QUARTER,
                "start_local": (start + MODULE.QUARTER).astimezone(MODULE.ZONE),
                "base_net_kwh": 1.25,
                "import_rate": 0.60,
                "export_rate": 0.0,
                "duration_hours": 0.25,
            },
        ]
        result = MODULE.simulate_residual_year(
            rows,
            capacity_kwh=1.0,
            battery={
                "max_charge_power_kw": 4.0,
                "max_discharge_power_kw": 4.0,
                "charge_efficiency": 1.0,
                "discharge_efficiency": 1.0,
            },
            marginal_costs={
                "day_ahead_peak_allowance_kw": 1.0,
                "central_degradation_eur_per_discharged_kwh": 0.0,
                "capacity_tariff_eur_per_kw_year_excl_vat": 0.0,
                "vat_rate_import": 0.0,
            },
            allow_grid_charge=True,
            state_step_kwh=0.5,
            absolute_peak_kw=5.0,
        )

        self.assertEqual(result["peak_policy"], "absolute_5_kw")
        self.assertLessEqual(
            max(row["simulated_peak_kw"] for row in result["monthly_peaks"]),
            5.0,
        )

    def test_scenario_recommendation_separates_options_from_data_gaps(self):
        self.assertEqual(
            MODULE.classify_scenario_option(
                average_net_value_eur=36.0,
                feasible_year_count=3,
                requires_new_hardware=False,
                data_complete=True,
            ),
            "OPTION",
        )
        self.assertEqual(
            MODULE.classify_scenario_option(
                average_net_value_eur=None,
                feasible_year_count=0,
                requires_new_hardware=False,
                data_complete=False,
            ),
            "DATA_GATED",
        )

    def test_privacy_safe_summary_keeps_annual_results_without_interval_rows(self):
        raw_path = (
            ROOT
            / "data"
            / "raw"
            / "multiyear-energy-battery-comparison-2023-10-01_2026-10-01.json"
        )
        if not raw_path.exists():
            self.skipTest("multi-year raw analysis has not been generated")
        raw = MODULE.json.loads(raw_path.read_text(encoding="utf-8"))

        summary = MODULE.build_privacy_safe_summary(raw)

        self.assertEqual(summary["status"], "VERIFIED_WITH_LIMITATIONS")
        self.assertFalse(summary["physical_writes"])
        self.assertEqual(len(summary["years"]), 3)
        self.assertEqual(summary["quality"]["interval_count"], 105216)
        self.assertNotIn("schedule", MODULE.json.dumps(summary))
        self.assertEqual(
            [row["cap_kw"] for row in summary["scenario_overview"]["peak_caps"]],
            [7.0, 8.0, 10.0],
        )
        self.assertTrue(
            any(
                row["id"] == "peak_neutral_winter_grid_charging"
                for row in summary["scenario_overview"]["computed"]
            )
        )
        self.assertTrue(
            all("financial_sensitivity" in year for year in summary["years"])
        )
        contract_option = next(
            row
            for row in summary["scenario_overview"]["computed"]
            if row["id"] == "dynamic_contract_unchanged_behavior"
        )
        self.assertIsNotNone(contract_option["value_eur_per_year"])
        self.assertEqual(
            summary["three_year_financial_sensitivity"]["calculation_scope"],
            "RECONCILED_ALL_IN_RATE_SENSITIVITY",
        )
        self.assertEqual(
            summary["three_year_financial_sensitivity"]["verification_status"],
            "RATE_RECONCILED_FIXED_COMPONENTS_HELD_CONSTANT",
        )


if __name__ == "__main__":
    unittest.main()
