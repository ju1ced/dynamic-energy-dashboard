import importlib.util
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "capture_prospective_shadow_plan",
    ROOT / "scripts" / "capture_prospective_shadow_plan.py",
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def target_day() -> date:
    return date(2026, 10, 7)


def five_minute_history(days: int = 8):
    start = datetime(2026, 9, 29, 22, 0, tzinfo=timezone.utc)
    rows = []
    for index in range(days * 24 * 12):
        instant = start + timedelta(minutes=5 * index)
        rows.append({"start": instant.timestamp() * 1000, "mean": 1200.0})
    return rows


def pv_rows():
    rows = []
    local = datetime.fromisoformat("2026-10-07T00:00:00+02:00")
    for index in range(48):
        rows.append(
            {
                "period_start": (local + timedelta(minutes=30 * index)).isoformat(),
                "pv_estimate": 2.0 if 16 <= index < 36 else 0.0,
            }
        )
    return rows


def price_feed():
    start = datetime(2026, 10, 6, 22, 0, tzinfo=timezone.utc)
    rows = []
    for index in range(96):
        instant = start + timedelta(minutes=15 * index)
        rows.append(
            {
                "start_utc": instant.isoformat(),
                "market_price_eur_per_mwh": 100.0 + index,
                "ecopower_import_eur_per_kwh_incl_vat": 0.2 + index / 10000,
                "ecopower_export_eur_per_kwh": 0.08 + index / 10000,
                "quality_flags": [],
            }
        )
    return {
        "source": {"provider": "ENTSO-E", "retrieved_at": "2026-10-06T12:00:00+00:00"},
        "quality": {"stale": False, "sequence_complete": True},
        "upcoming_intervals": rows,
    }


def ha_price_state(price: float, *, duplicate: bool = True):
    start = datetime(2026, 10, 7, 0, 0, tzinfo=MODULE.ZONE)
    rows = []
    for index in range(96):
        instant = start + timedelta(minutes=15 * index)
        row = {
            "start_time": instant.isoformat(),
            "end_time": (instant + timedelta(minutes=15)).isoformat(),
            "price_per_kwh": price + index / 10000,
        }
        rows.append(row)
        if duplicate:
            rows.append(dict(row))
    return {
        "attributes": {"data": rows, "unit_of_measurement": "€/kWh"},
        "last_reported": "2026-10-06T21:40:00+00:00",
    }


def prospective_report():
    start = datetime(2026, 10, 6, 22, 0, tzinfo=timezone.utc)
    schedule = []
    for index in range(96):
        base_net = 0.5 if index == 0 else 1.0
        charge = 0.25 if index == 0 else 0.0
        discharge = 0.25 if index == 1 else 0.0
        schedule.append(
            {
                "start_utc": (start + timedelta(minutes=15 * index)).isoformat(),
                "duration_hours": 0.25,
                "forecast_base_net_kwh": base_net,
                "charge_kwh": charge,
                "discharge_kwh": discharge,
                "reason": "prospective battery schedule",
            }
        )
    return {
        "schema_version": 1,
        "status": "PLANNED",
        "target_date": "2026-10-07",
        "generated_at": "2026-10-06T21:45:00+00:00",
        "target_start_utc": start.isoformat(),
        "target_end_utc": (start + timedelta(days=1)).isoformat(),
        "selected_policy_id": "cap_7_kw",
        "plans": [
            {
                "id": "cap_7_kw",
                "status": "PLANNED",
                "cap_kw": 7.0,
                "schedule": schedule,
            }
        ],
    }


def dst_prospective_report(target: date):
    start, end, expected = MODULE.target_bounds(target)
    report = prospective_report()
    report["target_date"] = target.isoformat()
    report["target_start_utc"] = start.isoformat()
    report["target_end_utc"] = end.isoformat()
    report["generated_at"] = (start - timedelta(minutes=15)).isoformat()
    report["plans"][0]["schedule"] = [
        {
            "start_utc": instant.isoformat(),
            "duration_hours": 0.25,
            "forecast_base_net_kwh": 0.25,
            "charge_kwh": 0.0,
            "discharge_kwh": 0.0,
            "reason": "DST-complete prospective schedule",
        }
        for instant in expected
    ]
    return report


def joint_inputs():
    observed = "2026-10-06T21:44:00+00:00"
    return {
        "snapshot_generation_id": "snapshot-generation-1",
        "observed_at": observed,
        "battery": {
            "soc_percent": 50.0,
            "minimum_soc_percent": 10.0,
            "maximum_soc_percent": 95.0,
            "usable_capacity_kwh": 10.0,
            "max_charge_power_kw": 3.0,
            "max_discharge_power_kw": 3.0,
            "controller_owner": "SMA",
            "observed_at": observed,
        },
        "ev": {
            "connected": True,
            "soc_percent": 40.0,
            "target_soc_percent": 80.0,
            "usable_capacity_kwh": 60.0,
            "departure_utc": "2026-10-07T08:00:00+00:00",
            "max_charge_power_kw": 7.4,
            "controller_owner": "SMAPPEE",
            "observed_at": observed,
        },
    }


def joint_safety_state():
    observed = "2026-10-06T21:44:00+00:00"
    return {
        "snapshot_generation_id": "snapshot-generation-1",
        "observed_at": observed,
        "battery": {
            "device_available": True,
            "controller_owner": "SMA",
            "manual_override_active": False,
            "local_fallback_active": False,
            "acknowledgement_timed_out": False,
            "soc_percent": 50.0,
        },
        "ev": {
            "device_available": True,
            "controller_owner": "SMAPPEE",
            "manual_override_active": False,
            "local_fallback_active": False,
            "acknowledgement_timed_out": False,
            "connected": True,
            "soc_percent": 0.0,
        },
    }


class CaptureProspectiveShadowPlanTests(unittest.TestCase):
    def test_joint_capture_builds_non_dispatchable_battery_and_ev_artifacts(self):
        artifacts = MODULE.build_joint_capture_artifacts(
            prospective_report(),
            control_inputs=joint_inputs(),
            safety_state=joint_safety_state(),
            now=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
        )

        self.assertEqual(artifacts["intents"]["status"], "READY_FOR_SAFETY_REVIEW")
        self.assertEqual(artifacts["review"]["status"], "ACCEPTED_DRY_RUN")
        self.assertEqual(len(artifacts["proposals"]), 192)
        self.assertEqual(
            {row["target"] for row in artifacts["proposals"]},
            {"BATTERY", "EV_CHARGER"},
        )
        self.assertTrue(
            all(row["execution_action"] == "NO_ACTION" for row in artifacts["proposals"])
        )
        self.assertTrue(
            all(row["transport"] == "NONE" for row in artifacts["proposals"])
        )
        self.assertFalse(artifacts["summary"]["execution_allowed"])
        self.assertNotIn("decisions", artifacts["summary"])
        self.assertNotIn("intents", artifacts["summary"])

    def test_joint_capture_without_private_control_snapshot_fails_closed(self):
        artifacts = MODULE.build_joint_capture_artifacts(
            prospective_report(),
            control_inputs=None,
            safety_state=None,
            now=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
        )

        self.assertEqual(artifacts["intents"]["status"], "NO_ACTION")
        self.assertEqual(artifacts["review"]["status"], "REJECTED")
        self.assertEqual(artifacts["proposals"], [])
        self.assertEqual(artifacts["summary"]["status"], "REJECTED")
        self.assertFalse(artifacts["summary"]["physical_writes"])

    def test_joint_capture_rejects_mixed_snapshot_generations(self):
        control = joint_inputs()
        safety = joint_safety_state()
        safety["snapshot_generation_id"] = "snapshot-generation-2"

        artifacts = MODULE.build_joint_capture_artifacts(
            prospective_report(),
            control_inputs=control,
            safety_state=safety,
            now=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
        )

        self.assertEqual(artifacts["intents"]["status"], "NO_ACTION")
        self.assertEqual(artifacts["review"]["status"], "REJECTED")
        self.assertEqual(artifacts["proposals"], [])

    def test_joint_capture_rejects_truncated_target_day_schedule(self):
        report = prospective_report()
        report["plans"][0]["schedule"] = report["plans"][0]["schedule"][1:-1]

        artifacts = MODULE.build_joint_capture_artifacts(
            report,
            control_inputs=joint_inputs(),
            safety_state=joint_safety_state(),
            now=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
        )

        self.assertEqual(artifacts["intents"]["status"], "NO_ACTION")
        self.assertEqual(artifacts["proposals"], [])

    def test_joint_capture_persists_detailed_and_privacy_safe_artifacts(self):
        artifacts = MODULE.build_joint_capture_artifacts(
            prospective_report(),
            control_inputs=joint_inputs(),
            safety_state=joint_safety_state(),
            now=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
        )

        with tempfile.TemporaryDirectory() as directory:
            integrity_key = bytes(range(32))
            paths = MODULE.persist_joint_capture_artifacts(
                Path(directory),
                target_day(),
                artifacts,
                integrity_key=integrity_key,
            )

            self.assertEqual(
                set(paths),
                {"intents", "review", "proposals", "summary", "manifest"},
            )
            summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
            self.assertEqual(summary["classification"], "PRIVACY_SAFE_JOINT_CONTROL_EVIDENCE_NO_EXECUTION")
            self.assertEqual(summary["target_date"], "2026-10-07")
            self.assertEqual(summary["source_plan_id"], "prospective-shadow-2026-10-07")
            self.assertNotIn("intents", summary)
            self.assertNotIn("decisions", summary)
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            MODULE.INTEGRITY.verify_manifest(
                manifest,
                target_day(),
                artifacts,
                key=integrity_key,
            )

    def test_joint_planner_adapter_accepts_complete_dst_target_days(self):
        for target, expected_count in (
            (date(2026, 3, 29), 92),
            (date(2026, 10, 25), 100),
        ):
            with self.subTest(target=target):
                planner = MODULE.build_joint_planner_output(
                    dst_prospective_report(target)
                )

                self.assertEqual(len(planner["intervals"]), expected_count)
                self.assertEqual(
                    planner["valid_from_utc"],
                    MODULE.target_bounds(target)[0].isoformat(),
                )
                self.assertEqual(
                    planner["valid_until_utc"],
                    MODULE.target_bounds(target)[1].isoformat(),
                )

    def test_home_assistant_price_feed_collapses_identical_integration_rows(self):
        result = MODULE.build_home_assistant_price_feed(
            target_day(),
            {
                "market_price": ha_price_state(0.1),
                "import_price": ha_price_state(0.2),
                "export_price": ha_price_state(0.08),
            },
            captured_at=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
        )

        self.assertEqual(len(result["upcoming_intervals"]), 96)
        self.assertEqual(result["quality"]["duplicate_quarter_count"], 96)
        self.assertEqual(
            result["upcoming_intervals"][0]["quality_flags"],
            ["collapsed_identical_duplicate"],
        )
        self.assertEqual(
            result["upcoming_intervals"][0]["market_price_eur_per_mwh"],
            100.0,
        )
        payload = MODULE.FEED.build_plan_entity_payload(
            MODULE.failure_report(
                target_day(),
                generated_at=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
                flag="TEST_NO_ACTION",
            ),
            price_feed=result,
            now=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
        )
        self.assertEqual(len(payload["prices"]), 96)
        self.assertEqual(payload["price_reference_eur_per_kwh"], 0.277)

    def test_home_assistant_price_feed_rejects_conflicting_duplicates(self):
        market = ha_price_state(0.1)
        market["attributes"]["data"][1]["price_per_kwh"] = 0.99

        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            MODULE.build_home_assistant_price_feed(
                target_day(),
                {
                    "market_price": market,
                    "import_price": ha_price_state(0.2),
                    "export_price": ha_price_state(0.08),
                },
                captured_at=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
            )

    def test_home_assistant_price_feed_rejects_any_future_observation(self):
        import_state = ha_price_state(0.2)
        import_state["last_reported"] = "2026-10-06T21:46:00+00:00"

        with self.assertRaisesRegex(ValueError, "observation is after capture"):
            MODULE.build_home_assistant_price_feed(
                target_day(),
                {
                    "market_price": ha_price_state(0.1),
                    "import_price": import_state,
                    "export_price": ha_price_state(0.08),
                },
                captured_at=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
            )

    def test_build_bundle_combines_measured_and_versioned_inputs(self):
        captured = datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc)
        states = {
            "soc": {
                "state": "40",
                "last_updated": "2026-10-06T23:44:00+02:00",
            },
            "month_peak": {
                "state": "5.386",
                "last_reported": "2026-10-06T23:43:00+02:00",
            },
            "pv_forecast": {
                "last_updated": "2026-10-06T12:25:59+02:00",
                "attributes": {"detailedForecast": pv_rows()},
            },
        }

        result = MODULE.build_capture_bundle(
            target_day(),
            captured_at=captured,
            states=states,
            load_statistics=five_minute_history(),
            price_feed=price_feed(),
            minimum_load_samples=3,
        )

        self.assertEqual(result["target_date"], "2026-10-07")
        self.assertEqual(len(result["intervals"]), 96)
        self.assertEqual(result["initial_soc"]["percent"], 40.0)
        self.assertEqual(result["month_peak_to_date_kw"], 5.386)
        self.assertAlmostEqual(result["intervals"][0]["load_forecast_kwh"], 0.3)
        self.assertAlmostEqual(result["intervals"][32]["pv_forecast_kwh"], 0.5)
        self.assertEqual(result["quality_flags"], [])

    def test_missing_target_price_quarter_is_rejected(self):
        prices = price_feed()
        prices["upcoming_intervals"].pop()

        with self.assertRaisesRegex(ValueError, "complete target day"):
            MODULE.build_capture_bundle(
                target_day(),
                captured_at=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
                states={
                    "soc": {
                        "state": "40",
                        "last_updated": "2026-10-06T23:44:00+02:00",
                    },
                    "month_peak": {
                        "state": "5.386",
                        "last_reported": "2026-10-06T23:43:00+02:00",
                    },
                    "pv_forecast": {
                        "last_updated": "2026-10-06T12:25:59+02:00",
                        "attributes": {"detailedForecast": pv_rows()},
                    },
                },
                load_statistics=five_minute_history(),
                price_feed=prices,
                minimum_load_samples=3,
            )

    def test_shifted_pv_forecast_is_rejected(self):
        shifted = pv_rows()
        shifted[0]["period_start"] = "2026-10-07T00:30:00+02:00"

        with self.assertRaisesRegex(ValueError, "PV forecast"):
            MODULE.build_pv_quarters(target_day(), shifted)

    def test_stale_pv_forecast_is_rejected(self):
        captured = datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc)
        states = {
            "soc": {
                "state": "40",
                "last_updated": "2026-10-06T23:44:00+02:00",
            },
            "month_peak": {
                "state": "5.386",
                "last_reported": "2026-10-06T23:43:00+02:00",
            },
            "pv_forecast": {
                "last_updated": "2026-09-01T12:25:59+02:00",
                "attributes": {"detailedForecast": pv_rows()},
            },
        }

        with self.assertRaisesRegex(ValueError, "PV forecast is stale"):
            MODULE.build_capture_bundle(
                target_day(),
                captured_at=captured,
                states=states,
                load_statistics=five_minute_history(),
                price_feed=price_feed(),
                minimum_load_samples=3,
                pv_forecast_max_age=timedelta(hours=18),
            )

    def test_missing_or_malformed_price_quality_is_rejected(self):
        prices = price_feed()
        prices["quality"] = {"stale": "false", "sequence_complete": True}

        with self.assertRaisesRegex(ValueError, "price feed quality"):
            MODULE.build_price_quarters(target_day(), prices)

    def test_critical_or_malformed_interval_price_quality_is_rejected(self):
        for flags in (["SOURCE_CORRECTION_PENDING"], "SOURCE_CORRECTION_PENDING"):
            with self.subTest(flags=flags):
                prices = price_feed()
                prices["upcoming_intervals"][0]["quality_flags"] = flags

                with self.assertRaisesRegex(ValueError, "price interval quality"):
                    MODULE.build_price_quarters(target_day(), prices)

    def test_known_informational_interval_price_quality_is_preserved(self):
        prices = price_feed()
        prices["upcoming_intervals"][0]["quality_flags"] = [
            "collapsed_identical_duplicate"
        ]

        result = MODULE.build_price_quarters(target_day(), prices)

        first = min(result)
        self.assertEqual(
            result[first]["source_quality_flags"],
            ["collapsed_identical_duplicate"],
        )

    def test_stale_month_peak_observation_is_rejected(self):
        captured = datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc)
        states = {
            "soc": {
                "state": "40",
                "last_updated": "2026-10-06T23:44:00+02:00",
            },
            "month_peak": {
                "state": "5.386",
                "last_reported": "2026-10-06T10:00:00+02:00",
            },
            "pv_forecast": {
                "last_updated": "2026-10-06T12:25:59+02:00",
                "attributes": {"detailedForecast": pv_rows()},
            },
        }

        with self.assertRaisesRegex(ValueError, "month peak is stale"):
            MODULE.build_capture_bundle(
                target_day(),
                captured_at=captured,
                states=states,
                load_statistics=five_minute_history(),
                price_feed=price_feed(),
                minimum_load_samples=3,
                month_peak_max_age=timedelta(hours=1),
            )

    def test_month_peak_from_previous_local_month_is_rejected(self):
        captured = datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc)
        states = {
            "soc": {
                "state": "40",
                "last_updated": "2026-10-06T23:44:00+02:00",
            },
            "month_peak": {
                "state": "5.386",
                "last_reported": "2026-09-30T23:43:00+02:00",
            },
            "pv_forecast": {
                "last_updated": "2026-10-06T12:25:59+02:00",
                "attributes": {"detailedForecast": pv_rows()},
            },
        }

        with self.assertRaisesRegex(ValueError, "month peak is not from current month"):
            MODULE.build_capture_bundle(
                target_day(),
                captured_at=captured,
                states=states,
                load_statistics=five_minute_history(),
                price_feed=price_feed(),
                minimum_load_samples=3,
                month_peak_max_age=timedelta(days=31),
            )

    def test_older_monotone_peak_from_current_local_month_is_accepted(self):
        captured = datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc)
        states = {
            "soc": {
                "state": "40",
                "last_updated": "2026-10-06T23:44:00+02:00",
            },
            "month_peak": {
                "state": "5.386",
                "last_reported": "2026-10-01T00:05:00+02:00",
            },
            "pv_forecast": {
                "last_updated": "2026-10-06T12:25:59+02:00",
                "attributes": {"detailedForecast": pv_rows()},
            },
        }

        result = MODULE.build_capture_bundle(
            target_day(),
            captured_at=captured,
            states=states,
            load_statistics=five_minute_history(),
            price_feed=price_feed(),
            minimum_load_samples=3,
            month_peak_max_age=timedelta(days=31),
        )

        self.assertEqual(result["month_peak_to_date_kw"], 5.386)

    def test_future_month_peak_observation_is_rejected(self):
        states = {
            "soc": {
                "state": "40",
                "last_updated": "2026-10-06T23:44:00+02:00",
            },
            "month_peak": {
                "state": "5.386",
                "last_reported": "2026-10-06T21:46:00+00:00",
            },
            "pv_forecast": {
                "last_updated": "2026-10-06T12:25:59+02:00",
                "attributes": {"detailedForecast": pv_rows()},
            },
        }

        with self.assertRaisesRegex(ValueError, "month peak observation is after capture"):
            MODULE.build_capture_bundle(
                target_day(),
                captured_at=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
                states=states,
                load_statistics=five_minute_history(),
                price_feed=price_feed(),
                minimum_load_samples=3,
            )

    def test_stale_or_future_price_retrieval_is_rejected(self):
        captured = datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc)
        states = {
            "soc": {
                "state": "40",
                "last_reported": "2026-10-06T23:44:00+02:00",
            },
            "month_peak": {
                "state": "5.386",
                "last_reported": "2026-10-06T23:43:00+02:00",
            },
            "pv_forecast": {
                "last_updated": "2026-10-06T12:25:59+02:00",
                "attributes": {"detailedForecast": pv_rows()},
            },
        }
        for retrieved_at, message in (
            ("2026-10-05T00:00:00+00:00", "price feed is stale"),
            ("2026-10-06T21:46:00+00:00", "price retrieval time is after capture"),
        ):
            with self.subTest(retrieved_at=retrieved_at):
                prices = price_feed()
                prices["source"]["retrieved_at"] = retrieved_at
                with self.assertRaisesRegex(ValueError, message):
                    MODULE.build_capture_bundle(
                        target_day(),
                        captured_at=captured,
                        states=states,
                        load_statistics=five_minute_history(),
                        price_feed=prices,
                        minimum_load_samples=3,
                        price_feed_max_age=timedelta(hours=18),
                    )

    def test_soc_observation_after_capture_completion_is_rejected(self):
        states = {
            "soc": {
                "state": "40",
                "last_reported": "2026-10-06T21:46:00+00:00",
            },
            "month_peak": {
                "state": "5.386",
                "last_reported": "2026-10-06T21:44:00+00:00",
            },
            "pv_forecast": {
                "last_updated": "2026-10-06T12:25:59+02:00",
                "attributes": {"detailedForecast": pv_rows()},
            },
        }

        with self.assertRaisesRegex(ValueError, "SOC observation is after capture"):
            MODULE.build_capture_bundle(
                target_day(),
                captured_at=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
                states=states,
                load_statistics=five_minute_history(),
                price_feed=price_feed(),
                minimum_load_samples=3,
            )

    def test_load_forecast_requires_real_samples_for_every_quarter(self):
        with self.assertRaisesRegex(ValueError, "insufficient load samples"):
            MODULE.build_load_forecast(
                target_day(),
                five_minute_history(days=1),
                minimum_samples=3,
            )

    def test_failure_report_is_read_only_no_action(self):
        result = MODULE.failure_report(
            target_day(),
            generated_at=datetime(2026, 10, 6, 21, 45, tzinfo=timezone.utc),
            flag="MISSING_COMPLETE_TARGET_PRICES",
        )

        self.assertEqual(result["status"], "NO_ACTION")
        self.assertEqual(result["plans"], [])
        self.assertFalse(result["physical_writes"])
        self.assertFalse(result["home_assistant_writes"])
        self.assertIn("MISSING_COMPLETE_TARGET_PRICES", result["quality_flags"])


if __name__ == "__main__":
    unittest.main()
