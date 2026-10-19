import importlib.util
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_prospective_shadow_plan",
    ROOT / "scripts" / "build_prospective_shadow_plan.py",
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

FEED_SPEC = importlib.util.spec_from_file_location(
    "build_shadow_plan_feed_for_prospective_test",
    ROOT / "scripts" / "build_shadow_plan_feed.py",
)
assert FEED_SPEC is not None
FEED_MODULE = importlib.util.module_from_spec(FEED_SPEC)
assert FEED_SPEC.loader is not None
FEED_SPEC.loader.exec_module(FEED_MODULE)

BATTERY = {
    "usable_capacity_kwh": 1.0,
    "max_charge_power_kw": 1.0,
    "max_discharge_power_kw": 1.0,
    "charge_efficiency": 1.0,
    "discharge_efficiency": 1.0,
    "round_trip_efficiency": 1.0,
}


def bundle(values=None):
    values = values or [
        (0.0, 0.10),
        (0.0, 0.10),
        (0.25, 0.50),
        (0.25, 0.50),
    ] + [(0.0, 0.20)] * 92
    captured = datetime(2026, 1, 1, 22, 55, tzinfo=timezone.utc)
    start = datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc)
    intervals = []
    for index, (base_net, rate) in enumerate(values):
        instant = start + timedelta(minutes=15 * index)
        intervals.append(
            {
                "start_utc": instant.isoformat(),
                "start_local": instant.isoformat(),
                "duration_hours": 0.25,
                "load_forecast_kwh": max(0.0, base_net),
                "pv_forecast_kwh": max(0.0, -base_net),
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
        "expected_interval_count": len(intervals),
        "initial_soc": {
            "percent": 0.0,
            "observed_at": (captured - timedelta(minutes=2)).isoformat(),
            "max_age_minutes": 5,
            "source": "MEASURED_HOME_ASSISTANT",
        },
        "sources": {
            "pv_forecast_issued_at": (captured - timedelta(hours=1)).isoformat(),
            "load_forecast_issued_at": captured.isoformat(),
            "prices_issued_at": (captured - timedelta(hours=8)).isoformat(),
            "ev_mode": "OBSERVATION_ONLY_INCLUDED_IN_TOTAL_LOAD",
            "heat_pump_mode": "OBSERVATION_ONLY_INCLUDED_IN_TOTAL_LOAD",
        },
        "month_peak_to_date_kw": 1.0,
        "intervals": intervals,
    }


class ProspectiveShadowPlanTests(unittest.TestCase):
    def test_measured_bundle_builds_read_only_plan(self):
        result = MODULE.build_prospective_plan(
            bundle(),
            battery=BATTERY,
            degradation_rate=0.0,
            state_step_kwh=0.05,
            planning_completed_at=datetime(2026, 1, 1, 22, 59, tzinfo=timezone.utc),
        )

        self.assertEqual(result["status"], "PLANNED")
        self.assertEqual(result["battery"]["initial_soc_source"], "MEASURED_HOME_ASSISTANT")
        self.assertFalse(result["physical_writes"])
        self.assertEqual(result["capture_quality"], "ACCEPTED_PROSPECTIVE_DAY")

    def test_stale_soc_or_hindsight_forecast_fails_closed(self):
        stale = bundle()
        stale["initial_soc"]["observed_at"] = "2026-01-01T22:40:00+00:00"
        stale_result = MODULE.build_prospective_plan(
            stale,
            battery=BATTERY,
            degradation_rate=0.0,
            planning_completed_at=datetime(2026, 1, 1, 22, 59, tzinfo=timezone.utc),
        )
        self.assertEqual(stale_result["status"], "NO_ACTION")
        self.assertIn("STALE_INITIAL_SOC", stale_result["quality_flags"])

        hindsight = bundle()
        hindsight["sources"]["pv_forecast_issued_at"] = "2026-01-01T23:00:00+00:00"
        hindsight_result = MODULE.build_prospective_plan(
            hindsight,
            battery=BATTERY,
            degradation_rate=0.0,
            planning_completed_at=datetime(2026, 1, 1, 22, 59, tzinfo=timezone.utc),
        )
        self.assertEqual(hindsight_result["status"], "NO_ACTION")
        self.assertIn("PV_FORECAST_ISSUED_AFTER_CAPTURE", hindsight_result["quality_flags"])

    def test_plan_completed_after_target_start_is_rejected(self):
        result = MODULE.build_prospective_plan(
            bundle(),
            battery=BATTERY,
            degradation_rate=0.0,
            planning_completed_at=datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result["status"], "NO_ACTION")
        self.assertEqual(result["capture_quality"], "REJECTED_PROSPECTIVE_DAY")
        self.assertIn("PLAN_GENERATED_AFTER_TARGET_START", result["quality_flags"])

    def test_rejected_capture_still_builds_fail_closed_entity_payload(self):
        stale = bundle()
        stale["initial_soc"]["observed_at"] = "2026-01-01T20:00:00+00:00"

        report = MODULE.build_prospective_plan(
            stale,
            battery=BATTERY,
            degradation_rate=0.0,
            state_step_kwh=0.05,
            planning_completed_at=datetime(2026, 1, 1, 22, 59, tzinfo=timezone.utc),
        )
        payload = FEED_MODULE.build_plan_entity_payload(
            report,
            now=datetime(2026, 1, 1, 22, 55, tzinfo=timezone.utc),
        )

        self.assertEqual(payload["state"], "NO_ACTION")
        self.assertEqual(payload["schedule"], [])
        self.assertEqual(payload["reason"], "INVALID_OR_STALE_PROSPECTIVE_CAPTURE")

    def test_target_day_interval_counts_follow_dst(self):
        self.assertEqual(len(MODULE.target_instants(date(2026, 3, 29))), 92)
        self.assertEqual(len(MODULE.target_instants(date(2026, 6, 1))), 96)
        self.assertEqual(len(MODULE.target_instants(date(2026, 10, 25))), 100)

    def test_actual_base_load_removes_observed_battery_behavior(self):
        self.assertAlmostEqual(
            MODULE.reconstruct_actual_base_net_kwh(
                grid_import_kwh=1.0,
                grid_export_kwh=0.2,
                battery_charge_kwh=0.3,
                battery_discharge_kwh=0.4,
            ),
            0.9,
        )

    def test_privacy_summary_excludes_interval_profiles(self):
        result = MODULE.build_prospective_plan(
            bundle(),
            battery=BATTERY,
            degradation_rate=0.0,
            planning_completed_at=datetime(2026, 1, 1, 22, 59, tzinfo=timezone.utc),
        )
        summary = MODULE.privacy_safe_summary(result)

        self.assertNotIn("intervals", summary)
        self.assertTrue(summary["privacy"]["quarter_household_profile_included"] is False)
        self.assertTrue(all("schedule" not in plan for plan in summary["plans"]))


if __name__ == "__main__":
    unittest.main()
