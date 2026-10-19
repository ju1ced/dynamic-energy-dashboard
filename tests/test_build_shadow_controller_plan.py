import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_shadow_controller_plan",
    ROOT / "scripts" / "build_shadow_controller_plan.py",
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def rows(values):
    start = datetime(2026, 1, 2, tzinfo=timezone.utc)
    output = []
    for index, (base_net_kwh, import_rate) in enumerate(values):
        instant = start + timedelta(minutes=15 * index)
        output.append(
            {
                "start_utc": instant.isoformat(),
                "start_local": instant.isoformat(),
                "duration_hours": 0.25,
                "forecast_base_net_kwh": base_net_kwh,
                "market_price_eur_per_mwh": import_rate * 1000,
                "import_rate_eur_per_kwh": import_rate,
                "export_rate_eur_per_kwh": 0.0,
                "quality_flags": [],
            }
        )
    return output


BATTERY = {
    "usable_capacity_kwh": 1.0,
    "max_charge_power_kw": 1.0,
    "max_discharge_power_kw": 1.0,
    "charge_efficiency": 1.0,
    "discharge_efficiency": 1.0,
}


class ShadowControllerPlanTests(unittest.TestCase):
    def test_missing_interval_returns_no_action(self):
        incomplete = rows([(0.25, 0.10), (0.25, 0.50)])
        result = MODULE.build_shadow_plan(
            incomplete,
            battery=BATTERY,
            initial_soc_kwh=0.5,
            degradation_rate=0.0,
            peak_caps_kw=[1.0],
            expected_interval_count=4,
        )

        self.assertEqual(result["status"], "NO_ACTION")
        self.assertEqual(result["reason"], "INCOMPLETE_FORECAST_INTERVALS")
        self.assertFalse(result["physical_writes"])
        self.assertEqual(result["plans"], [])

    def test_price_spread_creates_charge_then_discharge(self):
        forecast = rows(
            [
                (0.0, 0.10),
                (0.0, 0.10),
                (0.25, 0.50),
                (0.25, 0.50),
            ]
        )
        result = MODULE.build_shadow_plan(
            forecast,
            battery=BATTERY,
            initial_soc_kwh=0.0,
            degradation_rate=0.0,
            peak_caps_kw=[1.0],
            expected_interval_count=4,
        )

        plan = result["plans"][0]
        self.assertEqual(result["status"], "PLANNED")
        self.assertGreater(plan["totals"]["grid_charge_kwh"], 0.0)
        self.assertGreater(plan["totals"]["discharge_kwh"], 0.0)
        self.assertAlmostEqual(
            plan["totals"]["charge_kwh"],
            plan["totals"]["grid_charge_kwh"]
            + plan["totals"]["surplus_charge_kwh"],
        )
        self.assertTrue(any(row["action"] == "CHARGE_FROM_GRID" for row in plan["schedule"]))
        self.assertTrue(any(row["action"] == "DISCHARGE_TO_LOAD" for row in plan["schedule"]))

    def test_shared_grid_cap_includes_base_load_and_battery_charge(self):
        forecast = rows(
            [
                (0.20, 0.10),
                (0.20, 0.10),
                (0.25, 0.50),
                (0.25, 0.50),
            ]
        )
        result = MODULE.build_shadow_plan(
            forecast,
            battery=BATTERY,
            initial_soc_kwh=0.0,
            degradation_rate=0.0,
            peak_caps_kw=[1.0],
            expected_interval_count=4,
            state_step_kwh=0.05,
        )

        schedule = result["plans"][0]["schedule"]
        self.assertLessEqual(max(row["planned_grid_import_kw"] for row in schedule), 1.0)
        charged = next(row for row in schedule if row["charge_kwh"] > 0)
        self.assertAlmostEqual(
            charged["planned_grid_import_kw"],
            (charged["forecast_base_net_kwh"] + charged["charge_kwh"]) / 0.25,
        )

    def test_actual_shadow_execution_clips_discharge_to_load(self):
        planned = [
            {
                "start_utc": "2026-01-02T00:00:00+00:00",
                "duration_hours": 0.25,
                "charge_kwh": 0.0,
                "discharge_kwh": 0.25,
            }
        ]
        actual = [
            {
                "start_utc": "2026-01-02T00:00:00+00:00",
                "duration_hours": 0.25,
                "actual_base_net_kwh": 0.10,
                "import_rate_eur_per_kwh": 0.50,
                "export_rate_eur_per_kwh": 0.0,
            }
        ]
        result = MODULE.evaluate_shadow_execution(
            planned,
            actual,
            battery=BATTERY,
            initial_soc_kwh=0.5,
            degradation_rate=0.0,
            peak_cap_kw=1.0,
        )

        self.assertAlmostEqual(result["schedule"][0]["executed_discharge_kwh"], 0.10)
        self.assertAlmostEqual(result["schedule"][0]["grid_export_kwh"], 0.0)
        self.assertAlmostEqual(result["terminal_soc_kwh"], 0.4)

    def test_plan_is_read_only_and_explains_every_interval(self):
        forecast = rows([(0.0, 0.10), (0.0, 0.10), (0.25, 0.50), (0.25, 0.50)])
        result = MODULE.build_shadow_plan(
            forecast,
            battery=BATTERY,
            initial_soc_kwh=0.0,
            degradation_rate=0.0,
            peak_caps_kw=[1.0],
            expected_interval_count=4,
        )

        self.assertEqual(result["mode"], "READ_ONLY_SHADOW")
        self.assertFalse(result["physical_writes"])
        self.assertTrue(
            all(row["reason"] for plan in result["plans"] for row in plan["schedule"])
        )


if __name__ == "__main__":
    unittest.main()
