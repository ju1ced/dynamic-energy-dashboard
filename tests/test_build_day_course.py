import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_day_course", ROOT / "scripts" / "build_day_course.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def report(prices=None, base_net_kw=0.5, target_date="2026-10-20"):
    """A 96-quarter local day (2026-10-20 is a Tuesday, UTC+2)."""
    start = datetime(2026, 10, 19, 22, 0, tzinfo=timezone.utc)
    schedule = []
    for i in range(96):
        begin = start + timedelta(minutes=15 * i)
        local = begin.astimezone(MODULE.ZONE)
        price = (prices or {}).get(i, 0.3)
        schedule.append({
            "start_utc": begin.isoformat(),
            "start_local": local.isoformat(),
            "duration_hours": 0.25,
            "forecast_base_net_kwh": base_net_kw * 0.25,
            "import_rate_eur_per_kwh": price,
            "export_rate_eur_per_kwh": 0.05,
            "action": "HOLD",
            "reason": "test",
            "charge_kwh": 0.0,
            "discharge_kwh": 0.0,
            "planned_grid_import_kw": max(base_net_kw, 0.0),
            "planned_grid_export_kw": max(-base_net_kw, 0.0),
        })
    return {
        "mode": "READ_ONLY_SHADOW",
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "target_date": target_date,
        "target_start_utc": start.isoformat(),
        "target_end_utc": (start + timedelta(hours=24)).isoformat(),
        "interval_count": 96,
        "selected_policy_id": "p",
        "generated_at": start.isoformat(),
        "plans": [{"id": "p", "status": "PLANNED", "schedule": schedule}],
    }


def params(**overrides):
    result = dict(MODULE.DEFAULT_PARAMETERS)
    result.update(overrides)
    return result


class ParseParametersTests(unittest.TestCase):
    def test_defaults_and_valid_values(self):
        parsed, errors = MODULE.parse_parameters(
            {"max_grid_import_kw": "5", "ev_departure_time": "06:15", "active_days": "1,2"}
        )
        self.assertEqual(errors, [])
        self.assertEqual(parsed["max_grid_import_kw"], 5.0)
        self.assertEqual(parsed["ev_departure_time"], "06:15")
        self.assertEqual(parsed["active_days"], [1, 2])

    def test_rejects_invalid_values(self):
        _, errors = MODULE.parse_parameters({
            "max_grid_import_kw": "nan",
            "price_ceiling_eur_per_kwh": "-1",
            "ev_departure_time": "7:30",
            "ev_enabled": "yes",
            "active_days": "9",
            "ev_capacity_kwh": "abc",
        })
        self.assertEqual(
            sorted(errors),
            sorted([
                "MAX_GRID_IMPORT_KW_INVALID",
                "PRICE_CEILING_EUR_PER_KWH_OUT_OF_RANGE",
                "EV_DEPARTURE_TIME_INVALID",
                "EV_ENABLED_INVALID",
                "ACTIVE_DAYS_INVALID",
                "EV_CAPACITY_KWH_INVALID",
            ]),
        )


class DayCourseTests(unittest.TestCase):
    def test_charges_cheapest_quarters_before_departure(self):
        cheap = {i: 0.1 for i in range(8, 16)}  # 02:00-04:00 local
        course = MODULE.build_day_course(
            report(cheap), params(price_ceiling_eur_per_kwh=0.5, ev_start_soc_percent=70.0)
        )
        charging = [i for i, row in enumerate(course["intervals"]) if row["ev_kw"] > 0]
        self.assertEqual(charging, [8, 9, 10, 11])  # 6 kWh at 7.4 kW needs four quarters
        self.assertTrue(course["summary"]["ev_target_reached"])
        self.assertAlmostEqual(course["summary"]["ev_planned_kwh"], 6.0, places=3)

    def test_never_charges_after_departure(self):
        course = MODULE.build_day_course(
            report({i: 0.01 for i in range(40, 60)}),  # 10:00-15:00, after 07:30
            params(price_ceiling_eur_per_kwh=0.5),
        )
        self.assertTrue(all(row["ev_kw"] == 0 for row in course["intervals"][30:]))

    def test_ceiling_blocks_and_reports_required_ceiling(self):
        course = MODULE.build_day_course(report(), params(price_ceiling_eur_per_kwh=0.2))
        summary = course["summary"]
        self.assertFalse(summary["ev_target_reached"])
        self.assertEqual(summary["ev_planned_kwh"], 0.0)
        self.assertEqual(summary["required_price_ceiling_eur_per_kwh"], 0.3)
        self.assertIn("PRICE_CEILING_BLOCKS_TARGET", course["warnings"])

    def test_shared_import_limit_is_respected(self):
        course = MODULE.build_day_course(
            report(base_net_kw=1.0),
            params(price_ceiling_eur_per_kwh=0.5, max_grid_import_kw=4.0, ev_max_charge_kw=11.0),
        )
        self.assertLessEqual(max(row["grid_net_kw"] for row in course["intervals"]), 4.0 + 1e-6)
        self.assertEqual(course["summary"]["over_limit_intervals"], 0)
        self.assertGreater(course["summary"]["over_limit_intervals_unmanaged"], 0)

    def test_inactive_weekday_skips_ev(self):
        course = MODULE.build_day_course(
            report(), params(price_ceiling_eur_per_kwh=0.5, active_days=[0, 6])
        )
        self.assertIn("AUTOMATION_NOT_ACTIVE_ON_TARGET_DAY", course["warnings"])
        self.assertEqual(course["summary"]["ev_planned_kwh"], 0.0)

    def test_pv_surplus_is_used_first(self):
        surplus = report(base_net_kw=-2.0)
        course = MODULE.build_day_course(
            surplus, params(price_ceiling_eur_per_kwh=0.5, ev_start_soc_percent=75.0)
        )
        first = next(row for row in course["intervals"] if row["ev_kw"] > 0)
        self.assertEqual(first["ev_reason"], "PV-overschot zelf verbruiken")

    def test_output_stays_read_only(self):
        course = MODULE.build_day_course(report(), params())
        for flag in MODULE.READ_ONLY_FLAGS + ("execution_allowed",):
            self.assertIs(course[flag], False)

    def test_rejects_non_read_only_report(self):
        broken = report()
        broken["sma_writes"] = True
        with self.assertRaises(ValueError):
            MODULE.build_day_course(broken, params())


if __name__ == "__main__":
    unittest.main()
