import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_pv_forecast_quality", ROOT / "scripts" / "analyze_pv_forecast_quality.py"
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PvForecastQualityTests(unittest.TestCase):
    def test_versions_are_preserved_and_horizons_use_only_available_issues(self):
        source = {
            "timezone": "Europe/Brussels",
            "forecast_versions": [
                {"forecast_kind": "tomorrow", "issue_time": "2026-09-24T12:00:00+02:00", "target_date": "2026-09-25", "predicted_kwh": 10.0},
                {"forecast_kind": "tomorrow", "issue_time": "2026-09-24T17:00:00+02:00", "target_date": "2026-09-25", "predicted_kwh": 12.0},
                {"forecast_kind": "today", "issue_time": "2026-09-25T00:00:00+02:00", "target_date": "2026-09-25", "predicted_kwh": 11.0},
                {"forecast_kind": "today", "issue_time": "2026-09-25T07:30:00+02:00", "target_date": "2026-09-25", "predicted_kwh": 9.0},
                {"forecast_kind": "today", "issue_time": "2026-09-25T10:00:00+02:00", "target_date": "2026-09-25", "predicted_kwh": 8.0},
            ],
            "actual_daily": [{"target_date": "2026-09-25", "actual_kwh": 10.0}],
        }

        report = MODULE.analyze_forecast_quality(source)
        day = report["days"][0]

        self.assertEqual(day["forecast_version_count"], 5)
        self.assertTrue(day["overwritten_forecasts_preserved"])
        self.assertEqual(day["horizons"]["day_ahead"]["predicted_kwh"], 12.0)
        self.assertEqual(day["horizons"]["same_day_midnight"]["predicted_kwh"], 11.0)
        self.assertEqual(day["horizons"]["same_day_morning"]["predicted_kwh"], 9.0)
        self.assertEqual(day["horizons"]["day_ahead"]["error_kwh"], 2.0)

    def test_missing_forecast_is_visible_and_not_filled(self):
        source = {
            "timezone": "Europe/Brussels",
            "forecast_versions": [
                {"forecast_kind": "today", "issue_time": "2026-09-24T00:00:00+02:00", "target_date": "2026-09-24", "predicted_kwh": 8.0}
            ],
            "actual_daily": [{"target_date": "2026-09-24", "actual_kwh": 7.0}],
        }

        report = MODULE.analyze_forecast_quality(source)

        self.assertEqual(report["days"][0]["horizons"]["day_ahead"]["status"], "MISSING")
        self.assertEqual(report["summary_by_horizon"]["day_ahead"]["evaluated_day_count"], 0)
        self.assertEqual(report["summary_by_horizon"]["day_ahead"]["missing_day_count"], 1)

    def test_load_and_ev_forecasts_remain_separate_unimplemented_streams(self):
        source = {
            "timezone": "Europe/Brussels",
            "forecast_versions": [],
            "actual_daily": [],
        }

        report = MODULE.analyze_forecast_quality(source)

        self.assertEqual(report["extensions"]["load_forecast"]["status"], "NOT_IMPLEMENTED_SEPARATE_STREAM")
        self.assertEqual(report["extensions"]["ev_energy_forecast"]["status"], "NOT_IMPLEMENTED_SEPARATE_STREAM")
        self.assertFalse(report["extensions"]["load_forecast"]["inferred_from_pv"])
        self.assertFalse(report["extensions"]["ev_energy_forecast"]["inferred_from_pv"])


if __name__ == "__main__":
    unittest.main()
