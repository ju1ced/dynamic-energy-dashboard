import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_shadow_plan_feed.py"
HA_EXAMPLE = ROOT / "deploy" / "home-assistant" / "shadow-plan-rest-sensor.yaml.example"
ACTIVE_NOW = datetime(2026, 10, 5, 22, 10, tzinfo=timezone.utc)


def load_module():
    spec = importlib.util.spec_from_file_location("build_shadow_plan_feed", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def report():
    return {
        "schema_version": 1,
        "mode": "READ_ONLY_SHADOW",
        "classification": "PROPOSED_PLAN_NO_CONTROL",
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "status": "PLANNED",
        "target_date": "2026-10-06",
        "target_start_utc": "2026-10-05T22:00:00+00:00",
        "target_end_utc": "2026-10-05T22:30:00+00:00",
        "generated_at": "2026-10-05T13:30:00+00:00",
        "interval_count": 2,
        "selected_policy_id": "cap_7_kw",
        "plans": [
            {
                "id": "cap_7_kw",
                "status": "PLANNED",
                "schedule": [
                    {
                        "start_utc": "2026-10-05T22:00:00+00:00",
                        "start_local": "2026-10-06T00:00:00+02:00",
                        "duration_hours": 0.25,
                        "action": "HOLD",
                        "reason": "No profitable movement",
                        "planned_grid_import_kw": 0.4,
                        "forecast_base_net_kwh": 0.1,
                        "market_price_eur_per_mwh": 50.0,
                    },
                    {
                        "start_utc": "2026-10-05T22:15:00+00:00",
                        "start_local": "2026-10-06T00:15:00+02:00",
                        "duration_hours": 0.25,
                        "action": "CHARGE_FROM_GRID",
                        "reason": "Low price and headroom",
                        "planned_grid_import_kw": 2.0,
                        "forecast_base_net_kwh": 0.25,
                        "market_price_eur_per_mwh": 20.0,
                    },
                ],
            }
        ],
    }


def price_feed():
    return {
        "schema_version": 1,
        "mode": "READ_ONLY",
        "classification": "INDICATIVE_PRICE_SIGNAL_NOT_INVOICE",
        "physical_writes": False,
        "home_assistant_writes": False,
        "source": {
            "provider": "ENTSO-E Transparency Platform Web API",
            "retrieved_at": "2026-10-05T13:20:00+00:00",
        },
        "tariff_version": "ECOPOWER_DBS_2026-08-01",
        "reference": {"eur_per_kwh_incl_vat": 0.277},
        "quality": {"stale": False, "sequence_complete": True},
        "upcoming_intervals": [
            {
                "start_utc": "2026-10-05T22:00:00+00:00",
                "end_utc": "2026-10-05T22:15:00+00:00",
                "market_price_eur_per_mwh": 50.0,
                "ecopower_import_eur_per_kwh_incl_vat": 0.071,
                "ecopower_export_eur_per_kwh": 0.034,
            },
            {
                "start_utc": "2026-10-05T22:15:00+00:00",
                "end_utc": "2026-10-05T22:30:00+00:00",
                "market_price_eur_per_mwh": 20.0,
                "ecopower_import_eur_per_kwh_incl_vat": 0.039,
                "ecopower_export_eur_per_kwh": 0.005,
            },
        ],
        "aggregates": {
            "daily": [
                {
                    "period": "2026-10-06",
                    "interval_count": 2,
                    "expected_interval_count": 96,
                    "partial_period": True,
                    "average_eur_per_kwh_incl_vat": 0.055,
                    "difference_vs_reference_eur_per_kwh": -0.222,
                }
            ],
            "weekly": [
                {
                    "period": "2026-W41",
                    "interval_count": 2,
                    "expected_interval_count": 672,
                    "partial_period": True,
                    "average_eur_per_kwh_incl_vat": 0.055,
                    "difference_vs_reference_eur_per_kwh": -0.222,
                }
            ],
            "monthly": [
                {
                    "period": "2026-10",
                    "interval_count": 2,
                    "expected_interval_count": 2976,
                    "partial_period": True,
                    "average_eur_per_kwh_incl_vat": 0.055,
                    "difference_vs_reference_eur_per_kwh": -0.222,
                }
            ],
        },
    }


class ShadowPlanFeedTests(unittest.TestCase):
    def test_cli_includes_the_validated_price_feed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            price_path = root / "prices.json"
            output_path = root / "entity.json"
            plan_path.write_text(json.dumps(report()), encoding="utf-8")
            price_path.write_text(json.dumps(price_feed()), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(plan_path),
                    "--price-feed",
                    str(price_path),
                    "--output",
                    str(output_path),
                    "--now",
                    ACTIVE_NOW.isoformat(),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["prices"]), 2)
            self.assertEqual(payload["price_quality"]["status"], "ACCEPTED")

    def test_price_timeline_is_available_when_plan_has_no_action(self):
        module = load_module()
        unavailable = report()
        unavailable["status"] = "NO_ACTION"
        unavailable["reason"] = "MISSING_MONTH_PEAK"
        unavailable["plans"] = []
        unavailable["selected_policy_id"] = None
        unavailable["interval_count"] = 0

        payload = module.build_plan_entity_payload(
            unavailable,
            price_feed=price_feed(),
            now=ACTIVE_NOW,
        )

        self.assertEqual(payload["state"], "NO_ACTION")
        self.assertEqual(payload["price_source"], "ENTSO-E Transparency Platform Web API")
        self.assertEqual(payload["price_tariff_version"], "ECOPOWER_DBS_2026-08-01")
        self.assertEqual(payload["price_reference_eur_per_kwh"], 0.277)
        self.assertEqual(payload["price_aggregates"]["daily"][0]["period"], "2026-10-06")
        self.assertEqual(
            payload["price_aggregates"]["weekly"][0]["average_eur_per_kwh"],
            0.055,
        )
        self.assertTrue(payload["price_aggregates"]["monthly"][0]["partial_period"])
        self.assertEqual(
            payload["prices"],
            [
                {
                    "start_utc": "2026-10-05T22:00:00+00:00",
                    "duration_hours": 0.25,
                    "market_eur_per_mwh": 50.0,
                    "import_eur_per_kwh": 0.071,
                    "export_eur_per_kwh": 0.034,
                },
                {
                    "start_utc": "2026-10-05T22:15:00+00:00",
                    "duration_hours": 0.25,
                    "market_eur_per_mwh": 20.0,
                    "import_eur_per_kwh": 0.039,
                    "export_eur_per_kwh": 0.005,
                },
            ],
        )

    def test_price_timeline_is_available_when_no_plan_file_exists(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            payload = module.build_latest_plan_entity_payload(
                Path(directory),
                price_feed=price_feed(),
                now=ACTIVE_NOW,
            )

        self.assertEqual(payload["state"], "NO_ACTION")
        self.assertEqual(payload["reason"], "PLAN_UNAVAILABLE")
        self.assertEqual(len(payload["prices"]), 2)

    def test_negative_market_and_export_prices_are_preserved(self):
        module = load_module()
        feed = price_feed()
        feed["upcoming_intervals"][0]["market_price_eur_per_mwh"] = -25.0
        feed["upcoming_intervals"][0]["ecopower_export_eur_per_kwh"] = -0.039

        payload = module.build_plan_entity_payload(
            report(),
            price_feed=feed,
            now=ACTIVE_NOW,
        )

        self.assertEqual(payload["prices"][0]["market_eur_per_mwh"], -25.0)
        self.assertEqual(payload["prices"][0]["export_eur_per_kwh"], -0.039)

    def test_stale_price_feed_is_rejected_without_erasing_valid_plan(self):
        module = load_module()
        feed = price_feed()
        feed["source"]["retrieved_at"] = "2026-10-01T00:00:00+00:00"

        payload = module.build_plan_entity_payload(
            report(), price_feed=feed, now=ACTIVE_NOW
        )

        self.assertEqual(payload["state"], "PLANNED")
        self.assertEqual(len(payload["schedule"]), 2)
        self.assertEqual(payload["prices"], [])
        self.assertEqual(payload["price_quality"]["status"], "REJECTED")
        self.assertIn("STALE", payload["price_quality"]["flags"])

    def test_feed_contains_only_card_contract_fields(self):
        module = load_module()

        payload = module.build_plan_entity_payload(report(), now=ACTIVE_NOW)

        self.assertEqual(payload["state"], "PLANNED")
        self.assertEqual(payload["mode"], "READ_ONLY_SHADOW")
        self.assertFalse(payload["physical_writes"])
        self.assertFalse(payload["home_assistant_writes"])
        self.assertEqual(len(payload["schedule"]), 2)
        self.assertEqual(
            set(payload["schedule"][0]),
            {
                "start_utc",
                "duration_hours",
                "action",
                "reason",
                "planned_grid_import_kw",
            },
        )
        self.assertNotIn("forecast_base_net_kwh", payload["schedule"][0])
        self.assertNotIn("market_price_eur_per_mwh", payload["schedule"][0])

    def test_feed_rejects_any_write_capability(self):
        module = load_module()
        unsafe = report()
        unsafe["home_assistant_writes"] = True

        with self.assertRaisesRegex(ValueError, "write capability"):
            module.build_plan_entity_payload(unsafe)

    def test_feed_rejects_non_object_and_malformed_plan_structures(self):
        module = load_module()
        malformed_values = [
            ([], "object"),
            ({**report(), "plans": {}}, "plans"),
            ({**report(), "plans": ["not-an-object"]}, "plan entry"),
        ]
        for value, message in malformed_values:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    module.build_plan_entity_payload(value)

    def test_feed_rejects_unsupported_top_level_status(self):
        module = load_module()
        unsupported = report()
        unsupported["status"] = "EXECUTE"

        with self.assertRaisesRegex(ValueError, "status"):
            module.build_plan_entity_payload(unsupported)

    def test_feed_rejects_incomplete_selected_schedule(self):
        module = load_module()
        incomplete = report()
        incomplete["plans"][0]["schedule"].pop()

        with self.assertRaisesRegex(ValueError, "interval count"):
            module.build_plan_entity_payload(incomplete, now=ACTIVE_NOW)

    def test_feed_rejects_timezone_naive_plan_bounds(self):
        module = load_module()
        naive = report()
        naive["target_end_utc"] = "2026-10-05T22:30:00"

        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            module.build_plan_entity_payload(naive)

    def test_feed_rejects_timezone_naive_interval_start(self):
        module = load_module()
        naive = report()
        naive["plans"][0]["schedule"][0]["start_utc"] = "2026-10-05T22:00:00"

        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            module.build_plan_entity_payload(naive, now=ACTIVE_NOW)

    def test_feed_rejects_invalid_interval_numbers_and_actions(self):
        module = load_module()
        cases = [
            ("duration_hours", -0.25, "duration_hours"),
            ("planned_grid_import_kw", math.nan, "planned_grid_import_kw"),
            ("action", "TURN_BATTERY_ON", "action"),
        ]
        for field, value, message in cases:
            with self.subTest(field=field):
                invalid = report()
                invalid["plans"][0]["schedule"][0][field] = value
                with self.assertRaisesRegex(ValueError, message):
                    module.build_plan_entity_payload(invalid, now=ACTIVE_NOW)

        overflow = report()
        overflow["plans"][0]["schedule"][0]["duration_hours"] = 1e308
        with self.assertRaisesRegex(ValueError, "duration_hours"):
            module.build_plan_entity_payload(overflow, now=ACTIVE_NOW)

    def test_feed_validates_generated_at_and_no_action_plan_bounds(self):
        module = load_module()
        naive_generated = report()
        naive_generated["generated_at"] = "2026-10-05T13:30:00"
        with self.assertRaisesRegex(ValueError, "generated_at.*timezone-aware"):
            module.build_plan_entity_payload(naive_generated)

        unavailable = report()
        unavailable["status"] = "NO_ACTION"
        unavailable["reason"] = "MISSING_DAY_AHEAD_PRICE"
        unavailable["plans"] = []
        unavailable["selected_policy_id"] = None
        unavailable["interval_count"] = 0
        unavailable["target_start_utc"] = "2026-10-05T22:00:00"
        with self.assertRaisesRegex(ValueError, "target_start_utc.*timezone-aware"):
            module.build_plan_entity_payload(unavailable)

    def test_feed_rejects_noncontiguous_or_out_of_window_schedule(self):
        module = load_module()
        gap = report()
        gap["plans"][0]["schedule"][1]["start_utc"] = "2026-10-05T22:30:00+00:00"

        with self.assertRaisesRegex(ValueError, "contiguous"):
            module.build_plan_entity_payload(gap, now=ACTIVE_NOW)

        wrong_end = report()
        wrong_end["target_end_utc"] = "2026-10-05T22:45:00+00:00"
        with self.assertRaisesRegex(ValueError, "target_end_utc"):
            module.build_plan_entity_payload(wrong_end, now=ACTIVE_NOW)

    def test_latest_plan_is_re_evaluated_at_each_read(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shadow-controller-plan-2026-10-06.json"
            path.write_text(json.dumps(report()), encoding="utf-8")

            active = module.build_latest_plan_entity_payload(
                Path(directory),
                now=datetime(2026, 10, 5, 22, 10, tzinfo=timezone.utc),
            )
            expired = module.build_latest_plan_entity_payload(
                Path(directory),
                now=datetime(2026, 10, 5, 23, tzinfo=timezone.utc),
            )

        self.assertEqual(active["state"], "PLANNED")
        self.assertEqual(len(active["schedule"]), 2)
        self.assertEqual(expired["state"], "NO_ACTION")
        self.assertEqual(expired["reason"], "PLAN_EXPIRED")
        self.assertEqual(expired["schedule"], [])

    def test_no_action_report_exposes_no_schedule(self):
        module = load_module()
        unavailable = report()
        unavailable["status"] = "NO_ACTION"
        unavailable["reason"] = "MISSING_DAY_AHEAD_PRICE"
        unavailable["plans"] = []
        unavailable["selected_policy_id"] = None
        unavailable["interval_count"] = 0

        payload = module.build_plan_entity_payload(unavailable)

        self.assertEqual(payload["state"], "NO_ACTION")
        self.assertEqual(payload["reason"], "MISSING_DAY_AHEAD_PRICE")
        self.assertEqual(payload["schedule"], [])
        self.assertFalse(payload["physical_writes"])

    def test_expired_plan_fails_closed_without_schedule(self):
        module = load_module()

        payload = module.build_plan_entity_payload(
            report(),
            now=datetime(2026, 10, 7, tzinfo=timezone.utc),
        )

        self.assertEqual(payload["state"], "NO_ACTION")
        self.assertEqual(payload["reason"], "PLAN_EXPIRED")
        self.assertEqual(payload["schedule"], [])

    def test_home_assistant_example_is_read_only_and_uses_feed_contract(self):
        source = HA_EXAMPLE.read_text(encoding="utf-8")

        self.assertIn("https://<AUTHENTICATED_DASHBOARD_HOST>", source)
        self.assertNotIn("http://", source)
        self.assertIn("/data/shadow-plan.json", source)
        self.assertIn("value_json.state", source)
        self.assertIn("schedule", source)
        self.assertIn("prices", source)
        self.assertIn("price_reference_eur_per_kwh", source)
        self.assertIn("price_tariff_version", source)
        self.assertIn("price_aggregates", source)
        self.assertIn("generated_at", source)
        self.assertNotIn("service:", source)
        self.assertNotIn("command", source.lower())


if __name__ == "__main__":
    unittest.main()
