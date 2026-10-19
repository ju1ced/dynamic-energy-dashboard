import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PROSPECTIVE = load_module(
    "prospective_for_settlement_test",
    ROOT / "scripts" / "build_prospective_shadow_plan.py",
)
SETTLEMENT_PATH = ROOT / "scripts" / "settle_prospective_shadow_plan.py"

BATTERY = {
    "usable_capacity_kwh": 1.0,
    "max_charge_power_kw": 1.0,
    "max_discharge_power_kw": 1.0,
    "charge_efficiency": 1.0,
    "discharge_efficiency": 1.0,
    "round_trip_efficiency": 1.0,
}


def forecast_bundle():
    start = datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc)
    captured = datetime(2026, 1, 1, 22, 55, tzinfo=timezone.utc)
    intervals = []
    for index in range(96):
        base = 0.25 if 24 <= index < 72 else 0.05
        rate = 0.10 if index < 24 else 0.40
        instant = start + PROSPECTIVE.QUARTER * index
        intervals.append(
            {
                "start_utc": instant.isoformat(),
                "duration_hours": 0.25,
                "load_forecast_kwh": base,
                "pv_forecast_kwh": 0.0,
                "market_price_eur_per_mwh": rate * 1000,
                "import_rate_eur_per_kwh": rate,
                "export_rate_eur_per_kwh": 0.0,
                "quality_flags": [],
            }
        )
    return {
        "schema_version": 1,
        "mode": "READ_ONLY_SHADOW_CAPTURE",
        "captured_at": captured.isoformat(),
        "target_date": "2026-01-02",
        "initial_soc": {
            "percent": 50.0,
            "observed_at": captured.isoformat(),
            "max_age_minutes": 5,
            "source": "MEASURED_HOME_ASSISTANT",
        },
        "sources": {
            "pv_forecast_issued_at": captured.isoformat(),
            "load_forecast_issued_at": captured.isoformat(),
            "prices_issued_at": captured.isoformat(),
            "ev_mode": "OBSERVATION_ONLY_INCLUDED_IN_TOTAL_LOAD",
            "heat_pump_mode": "OBSERVATION_ONLY_INCLUDED_IN_TOTAL_LOAD",
        },
        "month_peak_to_date_kw": 4.0,
        "intervals": intervals,
    }


def actual_bundle(plan):
    rows = []
    for row in plan["intervals"]:
        base = row["forecast_base_net_kwh"]
        rows.append(
            {
                "start_utc": row["start_utc"],
                "duration_hours": row["duration_hours"],
                "grid_import_kwh": max(0.0, base),
                "grid_export_kwh": max(0.0, -base),
                "battery_charge_kwh": 0.0,
                "battery_discharge_kwh": 0.0,
                "load_actual_kwh": row["load_forecast_kwh"],
                "pv_actual_kwh": row["pv_forecast_kwh"],
                "quality_flags": [],
            }
        )
    return {
        "schema_version": 1,
        "mode": "READ_ONLY_SHADOW_SETTLEMENT",
        "target_date": plan["target_date"],
        "settled_at": "2026-01-03T00:30:00+00:00",
        "intervals": rows,
    }


class ProspectiveSettlementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module("settle_prospective_shadow_plan", SETTLEMENT_PATH)

    def make_plan(self):
        return PROSPECTIVE.build_prospective_plan(
            forecast_bundle(),
            battery=BATTERY,
            degradation_rate=0.0,
            state_step_kwh=0.05,
            planning_completed_at=datetime(2026, 1, 1, 22, 59, tzinfo=timezone.utc),
        )

    def test_complete_actual_day_settles_every_policy(self):
        plan = self.make_plan()
        result = self.module.settle_plan(
            plan,
            actual_bundle(plan),
            battery=BATTERY,
            degradation_rate=0.0,
        )

        self.assertEqual(result["status"], "SETTLED")
        self.assertEqual(result["quality"], "ACCEPTED_PROSPECTIVE_DAY")
        self.assertEqual(len(result["plans"]), 4)
        self.assertTrue(all("executed_cost_eur" in row for row in result["plans"]))
        self.assertAlmostEqual(result["forecast_error"]["load_mae_kwh"], 0.0)
        self.assertAlmostEqual(result["forecast_error"]["pv_mae_kwh"], 0.0)

    def test_incomplete_actual_day_is_rejected(self):
        plan = self.make_plan()
        actual = actual_bundle(plan)
        actual["intervals"].pop()

        result = self.module.settle_plan(
            plan,
            actual,
            battery=BATTERY,
            degradation_rate=0.0,
        )

        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("INCOMPLETE_ACTUAL_INTERVALS", result["quality_flags"])
        self.assertEqual(result["plans"], [])

    def test_plan_generated_after_target_start_is_rejected(self):
        plan = self.make_plan()
        plan["generated_at"] = plan["target_start_utc"]

        result = self.module.settle_plan(
            plan,
            actual_bundle(plan),
            battery=BATTERY,
            degradation_rate=0.0,
        )

        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("SOURCE_PLAN_NOT_PROSPECTIVE", result["quality_flags"])
        self.assertEqual(result["plans"], [])

    def test_privacy_summary_excludes_actual_interval_profile(self):
        plan = self.make_plan()
        result = self.module.settle_plan(
            plan,
            actual_bundle(plan),
            battery=BATTERY,
            degradation_rate=0.0,
        )
        summary = self.module.privacy_safe_summary(result)

        self.assertNotIn("actual_intervals", summary)
        self.assertTrue(all("schedule" not in row for row in summary["plans"]))
        self.assertFalse(summary["privacy"]["quarter_household_profile_included"])


if __name__ == "__main__":
    unittest.main()
