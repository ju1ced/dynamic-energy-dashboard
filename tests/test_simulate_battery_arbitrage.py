import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "simulate_battery_arbitrage", ROOT / "scripts" / "simulate_battery_arbitrage.py"
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class BatteryArbitrageTests(unittest.TestCase):
    def test_reconstruct_base_net_removes_observed_battery_behavior(self):
        self.assertAlmostEqual(
            MODULE.reconstruct_base_net(
                grid_import_kwh=3.0,
                grid_export_kwh=0.5,
                battery_charge_kwh=1.0,
                battery_discharge_kwh=2.0,
            ),
            3.5,
        )

    def test_price_spread_causes_cyclic_charge_and_discharge(self):
        rows = [
            {"base_net_kwh": 0.0, "import_rate": 0.10, "export_rate": 0.0},
            {"base_net_kwh": 1.0, "import_rate": 0.50, "export_rate": 0.0},
        ]
        result = MODULE.optimize_segment(
            rows,
            capacity_kwh=1.0,
            max_charge_kw=1.0,
            max_discharge_kw=1.0,
            charge_efficiency=1.0,
            discharge_efficiency=1.0,
            degradation_eur_per_discharged_kwh=0.0,
            state_step_kwh=0.5,
            initial_soc_kwh=0.0,
            terminal_soc_kwh=0.0,
        )
        self.assertAlmostEqual(result["schedule"][0]["charge_kwh"], 1.0)
        self.assertAlmostEqual(result["schedule"][1]["discharge_kwh"], 1.0)
        self.assertAlmostEqual(result["total_cost_eur"], 0.1)
        self.assertAlmostEqual(result["baseline_cost_eur"], 0.5)
        self.assertAlmostEqual(result["savings_eur"], 0.4)

    def test_losses_prevent_cycling_without_a_price_spread(self):
        rows = [
            {"base_net_kwh": 0.0, "import_rate": 0.20, "export_rate": 0.0},
            {"base_net_kwh": 0.0, "import_rate": 0.20, "export_rate": 0.0},
        ]
        result = MODULE.optimize_segment(
            rows,
            capacity_kwh=1.0,
            max_charge_kw=1.0,
            max_discharge_kw=1.0,
            charge_efficiency=0.9,
            discharge_efficiency=0.9,
            degradation_eur_per_discharged_kwh=0.0,
            state_step_kwh=0.5,
            initial_soc_kwh=0.0,
            terminal_soc_kwh=0.0,
        )
        self.assertAlmostEqual(result["totals"]["charge_kwh"], 0.0)
        self.assertAlmostEqual(result["totals"]["discharge_kwh"], 0.0)

    def test_pv_surplus_is_stored_before_export_when_later_import_is_expensive(self):
        rows = [
            {"base_net_kwh": -1.0, "import_rate": 0.20, "export_rate": 0.02},
            {"base_net_kwh": 1.0, "import_rate": 0.40, "export_rate": 0.02},
        ]
        result = MODULE.optimize_segment(
            rows,
            capacity_kwh=1.0,
            max_charge_kw=1.0,
            max_discharge_kw=1.0,
            charge_efficiency=1.0,
            discharge_efficiency=1.0,
            degradation_eur_per_discharged_kwh=0.0,
            state_step_kwh=0.5,
            initial_soc_kwh=0.0,
            terminal_soc_kwh=0.0,
        )
        self.assertAlmostEqual(result["schedule"][0]["charge_kwh"], 1.0)
        self.assertAlmostEqual(result["schedule"][1]["discharge_kwh"], 1.0)
        self.assertAlmostEqual(result["totals"]["grid_import_kwh"], 0.0)
        self.assertAlmostEqual(result["totals"]["grid_export_kwh"], 0.0)

    def test_degradation_can_suppress_small_arbitrage(self):
        rows = [
            {"base_net_kwh": 0.0, "import_rate": 0.10, "export_rate": 0.0},
            {"base_net_kwh": 0.0, "import_rate": 0.15, "export_rate": 0.0},
        ]
        result = MODULE.optimize_segment(
            rows,
            capacity_kwh=1.0,
            max_charge_kw=1.0,
            max_discharge_kw=1.0,
            charge_efficiency=1.0,
            discharge_efficiency=1.0,
            degradation_eur_per_discharged_kwh=0.10,
            state_step_kwh=0.5,
            initial_soc_kwh=0.0,
            terminal_soc_kwh=0.0,
        )
        self.assertAlmostEqual(result["totals"]["discharge_kwh"], 0.0)

    def test_self_consumption_mode_does_not_discharge_into_grid_export(self):
        rows = [
            {"base_net_kwh": 0.0, "import_rate": 0.10, "export_rate": 0.50},
            {"base_net_kwh": 0.0, "import_rate": 0.10, "export_rate": 0.00},
        ]
        result = MODULE.optimize_segment(
            rows,
            capacity_kwh=1.0,
            max_charge_kw=1.0,
            max_discharge_kw=1.0,
            charge_efficiency=1.0,
            discharge_efficiency=1.0,
            degradation_eur_per_discharged_kwh=0.0,
            state_step_kwh=0.5,
            initial_soc_kwh=0.5,
            terminal_soc_kwh=0.5,
            allow_battery_export=False,
        )
        self.assertAlmostEqual(result["totals"]["discharge_kwh"], 0.0)

    def test_grid_import_cap_prevents_peak_increasing_charge(self):
        rows = [
            {"base_net_kwh": 1.0, "import_rate": 0.10, "export_rate": 0.0},
            {"base_net_kwh": 1.0, "import_rate": 0.50, "export_rate": 0.0},
        ]
        result = MODULE.optimize_segment(
            rows,
            capacity_kwh=1.0,
            max_charge_kw=1.0,
            max_discharge_kw=1.0,
            charge_efficiency=1.0,
            discharge_efficiency=1.0,
            degradation_eur_per_discharged_kwh=0.0,
            state_step_kwh=0.5,
            initial_soc_kwh=0.0,
            terminal_soc_kwh=0.0,
            max_grid_import_kw=1.0,
        )
        self.assertAlmostEqual(result["totals"]["charge_kwh"], 0.0)

    def test_day_ahead_execution_clips_discharge_to_actual_self_consumption(self):
        actual_rows = [
            {
                "base_net_kwh": 0.25,
                "import_rate": 0.50,
                "export_rate": 0.10,
            }
        ]
        planned = [{"charge_kwh": 0.0, "discharge_kwh": 1.0}]
        result = MODULE.execute_day_ahead_schedule(
            actual_rows,
            planned,
            battery={
                "usable_capacity_kwh": 2.0,
                "charge_efficiency": 1.0,
                "discharge_efficiency": 1.0,
                "max_charge_power_kw": 1.0,
                "max_discharge_power_kw": 1.0,
            },
            starting_soc_kwh=1.0,
            degradation_rate=0.0,
            allow_battery_export=False,
        )
        self.assertAlmostEqual(result["schedule"][0]["discharge_kwh"], 0.25)
        self.assertAlmostEqual(result["schedule"][0]["grid_export_kwh"], 0.0)
        self.assertAlmostEqual(result["terminal_soc_kwh"], 0.75)

    def test_scenario_reports_export_allowed_and_self_consumption_upper_bounds(self):
        rows = [
            {
                "start_utc": "2026-01-01T00:00:00+00:00",
                "month": "2026-01",
                "local_date": "2026-01-01",
                "local_hour": 1,
                "base_net_kwh": 0.0,
                "grid_import_kwh": 0.0,
                "grid_export_kwh": 0.0,
                "actual_battery_charge_kwh": 0.0,
                "actual_battery_discharge_kwh": 0.0,
                "import_rate": 0.10,
                "export_rate": 0.50,
            },
            {
                "start_utc": "2026-01-01T01:00:00+00:00",
                "month": "2026-01",
                "local_date": "2026-01-01",
                "local_hour": 2,
                "base_net_kwh": 0.0,
                "grid_import_kwh": 0.0,
                "grid_export_kwh": 0.0,
                "actual_battery_charge_kwh": 0.0,
                "actual_battery_discharge_kwh": 0.0,
                "import_rate": 0.10,
                "export_rate": 0.00,
            },
        ]
        battery = {
            "usable_capacity_kwh": 1.0,
            "max_charge_power_kw": 1.0,
            "max_discharge_power_kw": 1.0,
            "charge_efficiency": 1.0,
            "discharge_efficiency": 1.0,
            "round_trip_efficiency": 1.0,
        }
        marginal_costs = {
            "capacity_tariff_eur_per_kw_year_excl_vat": 0.0,
            "vat_rate_import": 0.0,
            "perfect_foresight_peak_allowance_candidates_kw": [1.0],
            "day_ahead_peak_allowance_kw": 1.0,
        }
        result = MODULE.run_scenario(
            rows,
            battery,
            degradation_rate=0.0,
            marginal_costs=marginal_costs,
            state_step_kwh=0.5,
        )
        self.assertIn("perfect_foresight_export_allowed", result)
        self.assertIn("perfect_foresight_self_consumption", result)
        self.assertGreater(
            result["perfect_foresight_export_allowed"][
                "battery_discharge_to_export_kwh"
            ],
            0.0,
        )
        self.assertAlmostEqual(
            result["perfect_foresight_self_consumption"][
                "battery_discharge_to_export_kwh"
            ],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
