import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "capture_prospective_shadow_settlement",
    ROOT / "scripts" / "capture_prospective_shadow_settlement.py",
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def exported_energy():
    aliases = [
        "grid_import",
        "grid_export",
        "pv_generation",
        "battery_charge",
        "battery_discharge",
        "ev_charge",
    ]
    series = {}
    for alias in aliases:
        value = {
            "grid_import": 1.0,
            "grid_export": 0.2,
            "pv_generation": 0.8,
            "battery_charge": 0.3,
            "battery_discharge": 0.4,
            "ev_charge": 0.1,
        }[alias]
        series[alias] = [
            {
                "start_utc": "2026-10-06T22:00:00+00:00",
                "energy_kwh": value,
                "quality_flags": [],
            }
        ]
    return {"series": series}


def proposal_digest(proposals):
    encoded = json.dumps(
        proposals,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def accepted_joint_summary():
    proposals = joint_proposals()
    return {
        "schema_version": 1,
        "mode": "PROSPECTIVE_JOINT_CONTROL_DRY_RUN",
        "classification": "PRIVACY_SAFE_JOINT_CONTROL_EVIDENCE_NO_EXECUTION",
        "status": "ACCEPTED_DRY_RUN",
        "target_date": "2026-10-07",
        "source_plan_id": "plan",
        "valid_from_utc": "2026-10-06T22:00:00+00:00",
        "valid_until_utc": "2026-10-06T22:15:00+00:00",
        "intent_count": 2,
        "accepted_decision_count": 2,
        "rejected_decision_count": 0,
        "proposal_count": 2,
        "proposal_set_sha256": proposal_digest(proposals),
        "execution_allowed": False,
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
    }


def joint_proposals():
    interval = {
        "start_utc": "2026-10-06T22:00:00+00:00",
        "end_utc": "2026-10-06T22:15:00+00:00",
    }
    common = {
        "schema_version": 1,
        "classification": "NON_DISPATCHABLE_COMMAND_PROPOSAL",
        "target_interval": interval,
        "safety_decision": "ACCEPTED_DRY_RUN",
        "safety_reasons": [],
        "transport": "NONE",
        "dispatch_supported": False,
        "execution_action": "NO_ACTION",
        "execution_allowed": False,
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
    }
    return [
        {
            **common,
            "adapter": "SMA_DRY_RUN",
            "target": "BATTERY",
            "intent_id": "plan:BATTERY:2026-10-06T22:00:00+00:00",
            "proposed_action": "CHARGE",
            "proposed_power_kw": 1.2,
        },
        {
            **common,
            "adapter": "SMAPPEE_DRY_RUN",
            "target": "EV_CHARGER",
            "intent_id": "plan:EV_CHARGER:2026-10-06T22:00:00+00:00",
            "proposed_action": "CHARGE",
            "proposed_power_kw": 0.4,
        },
    ]


def full_day_actual_and_proposals(target=date(2026, 10, 7)):
    start, end = MODULE.target_bounds(target)
    aliases = (
        "grid_import",
        "grid_export",
        "pv_generation",
        "battery_charge",
        "battery_discharge",
        "ev_charge",
    )
    values = {
        "grid_import": 1.0,
        "grid_export": 0.2,
        "pv_generation": 0.8,
        "battery_charge": 0.3,
        "battery_discharge": 0.0,
        "ev_charge": 0.1,
    }
    series = {alias: [] for alias in aliases}
    proposals = []
    instant = start
    while instant < end:
        interval_end = instant + timedelta(minutes=15)
        for alias in aliases:
            series[alias].append(
                {
                    "start_utc": instant.isoformat(),
                    "energy_kwh": values[alias],
                    "quality_flags": [],
                }
            )
        for target_name, adapter, power in (
            ("BATTERY", "SMA_DRY_RUN", 1.2),
            ("EV_CHARGER", "SMAPPEE_DRY_RUN", 0.4),
        ):
            proposals.append(
                {
                    "schema_version": 1,
                    "classification": "NON_DISPATCHABLE_COMMAND_PROPOSAL",
                    "adapter": adapter,
                    "target": target_name,
                    "intent_id": f"plan:{target_name}:{instant.isoformat()}",
                    "target_interval": {
                        "start_utc": instant.isoformat(),
                        "end_utc": interval_end.isoformat(),
                    },
                    "proposed_action": "CHARGE",
                    "proposed_power_kw": power,
                    "safety_decision": "ACCEPTED_DRY_RUN",
                    "safety_reasons": [],
                    "transport": "NONE",
                    "dispatch_supported": False,
                    "execution_action": "NO_ACTION",
                    "execution_allowed": False,
                    "physical_writes": False,
                    "home_assistant_writes": False,
                    "sma_writes": False,
                    "smappee_writes": False,
                }
            )
        instant = interval_end
    actual = MODULE.build_actual_bundle(
        target,
        {"series": series},
        settled_at=(end + timedelta(hours=1)).isoformat(),
    )
    summary = accepted_joint_summary()
    summary.update(
        {
            "target_date": target.isoformat(),
            "valid_from_utc": start.isoformat(),
            "valid_until_utc": end.isoformat(),
            "intent_count": len(proposals),
            "accepted_decision_count": len(proposals),
            "proposal_count": len(proposals),
            "proposal_set_sha256": proposal_digest(proposals),
        }
    )
    return actual, proposals, summary


class CaptureProspectiveShadowSettlementTests(unittest.TestCase):
    def test_joint_capture_set_manifest_rejects_mixed_or_tampered_artifacts(self):
        target = date(2026, 10, 7)
        artifacts = {
            "intents": {"status": "READY_FOR_SAFETY_REVIEW"},
            "review": {"status": "ACCEPTED_DRY_RUN"},
            "proposals": joint_proposals(),
            "summary": accepted_joint_summary(),
        }
        key = bytes(range(32))
        manifest = MODULE.INTEGRITY.build_manifest(target, artifacts, key=key)

        with tempfile.TemporaryDirectory() as directory:
            captures_dir = Path(directory)
            key_path = captures_dir / "integrity.key"
            key_path.write_bytes(key)
            for name, value in artifacts.items():
                (captures_dir / f"joint-{name}-{target}.json").write_text(
                    json.dumps(value), encoding="utf-8"
                )
            (captures_dir / f"joint-manifest-{target}.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )

            loaded_summary, loaded_proposals = MODULE.load_verified_joint_capture_set(
                captures_dir,
                target,
                integrity_key_path=key_path,
            )
            self.assertEqual(loaded_summary, artifacts["summary"])
            self.assertEqual(loaded_proposals, artifacts["proposals"])

            tampered = joint_proposals()
            tampered[0]["proposed_action"] = "HOLD"
            tampered[0]["proposed_power_kw"] = 0.0
            (captures_dir / f"joint-proposals-{target}.json").write_text(
                json.dumps(tampered), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                MODULE.load_verified_joint_capture_set(
                    captures_dir,
                    target,
                    integrity_key_path=key_path,
                )

    def test_joint_dry_run_score_compares_proposals_with_observed_energy(self):
        actual, proposals, capture_summary = full_day_actual_and_proposals()

        score = MODULE.score_joint_dry_run(
            date(2026, 10, 7),
            capture_summary,
            proposals,
            actual,
            settled_at="2026-10-07T23:00:00+00:00",
        )

        self.assertEqual(score["status"], "SCORED")
        self.assertFalse(score["execution_allowed"])
        self.assertEqual(score["target_count"], 2)
        self.assertAlmostEqual(score["targets"]["BATTERY"]["energy_mae_kwh"], 0.0)
        self.assertAlmostEqual(score["targets"]["EV_CHARGER"]["energy_mae_kwh"], 0.0)
        self.assertTrue(all(row["action_match"] for row in score["interval_scores"]))

        summary = MODULE.privacy_safe_joint_score(score)
        self.assertNotIn("interval_scores", summary)
        self.assertFalse(summary["privacy"]["quarter_household_profile_included"])

    def test_joint_dry_run_score_rejects_durable_proposal_action_tampering(self):
        actual, proposals, capture_summary = full_day_actual_and_proposals()
        proposals[0]["proposed_action"] = "HOLD"
        proposals[0]["proposed_power_kw"] = 0.0

        score = MODULE.score_joint_dry_run(
            date(2026, 10, 7),
            capture_summary,
            proposals,
            actual,
            settled_at="2026-10-07T23:00:00+00:00",
        )

        self.assertEqual(score["status"], "REJECTED")
        self.assertIn("JOINT_PROPOSAL_DIGEST_MISMATCH", score["quality_flags"])

    def test_joint_dry_run_score_rejects_incomplete_actual_dst_day(self):
        target = date(2026, 10, 25)
        actual = MODULE.build_actual_bundle(
            target, exported_energy(), settled_at="2026-10-26T01:00:00+00:00"
        )
        capture_summary = accepted_joint_summary()
        start, end = MODULE.target_bounds(target)
        capture_summary["target_date"] = target.isoformat()
        capture_summary["valid_from_utc"] = start.isoformat()
        capture_summary["valid_until_utc"] = end.isoformat()

        score = MODULE.score_joint_dry_run(
            target,
            capture_summary,
            joint_proposals(),
            actual,
            settled_at="2026-10-26T01:00:00+00:00",
        )

        self.assertEqual(score["status"], "REJECTED")
        self.assertIn("JOINT_ACTUAL_INTERVALS_INVALID", score["quality_flags"])

    def test_joint_dry_run_score_rejects_any_dispatch_capability(self):
        proposals = joint_proposals()
        proposals[0]["transport"] = "HTTP"
        actual = MODULE.build_actual_bundle(
            date(2026, 10, 7), exported_energy(), settled_at="2026-10-07T23:00:00+00:00"
        )

        score = MODULE.score_joint_dry_run(
            date(2026, 10, 7),
            accepted_joint_summary(),
            proposals,
            actual,
            settled_at="2026-10-07T23:00:00+00:00",
        )

        self.assertEqual(score["status"], "REJECTED")
        self.assertIn("JOINT_PROPOSAL_WRITE_BOUNDARY_INVALID", score["quality_flags"])
        self.assertEqual(score["interval_scores"], [])

    def test_joint_dry_run_score_rejects_incomplete_target_coverage(self):
        exported = exported_energy()
        exported["series"]["battery_discharge"][0]["energy_kwh"] = 0.0
        actual = MODULE.build_actual_bundle(
            date(2026, 10, 7), exported, settled_at="2026-10-07T23:00:00+00:00"
        )

        score = MODULE.score_joint_dry_run(
            date(2026, 10, 7),
            accepted_joint_summary(),
            joint_proposals()[:1],
            actual,
            settled_at="2026-10-07T23:00:00+00:00",
        )

        self.assertEqual(score["status"], "REJECTED")
        self.assertIn("JOINT_TARGET_INTERVAL_COVERAGE_INVALID", score["quality_flags"])

    def test_joint_dry_run_score_rejects_interval_or_identity_tampering(self):
        exported = exported_energy()
        exported["series"]["battery_discharge"][0]["energy_kwh"] = 0.0
        actual = MODULE.build_actual_bundle(
            date(2026, 10, 7), exported, settled_at="2026-10-07T23:00:00+00:00"
        )

        for mutation in ("interval_end", "intent_id"):
            with self.subTest(mutation=mutation):
                proposals = joint_proposals()
                if mutation == "interval_end":
                    proposals[0]["target_interval"]["end_utc"] = (
                        "2026-10-06T22:30:00+00:00"
                    )
                else:
                    proposals[0]["intent_id"] = "forged-intent"
                score = MODULE.score_joint_dry_run(
                    date(2026, 10, 7),
                    accepted_joint_summary(),
                    proposals,
                    actual,
                    settled_at="2026-10-07T23:00:00+00:00",
                )

                self.assertEqual(score["status"], "REJECTED")
                self.assertIn(
                    "JOINT_PROPOSAL_OR_ACTUAL_VALUE_INVALID",
                    score["quality_flags"],
                )

    def test_joint_dry_run_score_rejects_summary_proposal_count_mismatch(self):
        summary = accepted_joint_summary()
        summary["proposal_count"] = 3
        exported = exported_energy()
        exported["series"]["battery_discharge"][0]["energy_kwh"] = 0.0
        actual = MODULE.build_actual_bundle(
            date(2026, 10, 7), exported, settled_at="2026-10-07T23:00:00+00:00"
        )

        score = MODULE.score_joint_dry_run(
            date(2026, 10, 7),
            summary,
            joint_proposals(),
            actual,
            settled_at="2026-10-07T23:00:00+00:00",
        )

        self.assertEqual(score["status"], "REJECTED")
        self.assertIn("JOINT_CAPTURE_PROPOSAL_MISMATCH", score["quality_flags"])

    def test_actual_bundle_uses_energy_balance_without_hiding_battery(self):
        result = MODULE.build_actual_bundle(
            date(2026, 10, 7), exported_energy(), settled_at="2026-10-07T23:00:00+00:00"
        )

        row = result["intervals"][0]
        self.assertAlmostEqual(row["load_actual_kwh"], 1.7)
        self.assertAlmostEqual(row["pv_actual_kwh"], 0.8)
        self.assertAlmostEqual(row["battery_charge_kwh"], 0.3)
        self.assertAlmostEqual(row["battery_discharge_kwh"], 0.4)
        self.assertAlmostEqual(row["ev_charge_kwh"], 0.1)

    def test_actual_bundle_preserves_source_quality_flags(self):
        exported = exported_energy()
        exported["series"]["grid_import"][0]["quality_flags"] = [
            "missing_5minute_bucket"
        ]

        result = MODULE.build_actual_bundle(
            date(2026, 10, 7), exported, settled_at="2026-10-07T23:00:00+00:00"
        )

        self.assertIn("grid_import:missing_5minute_bucket", result["intervals"][0]["quality_flags"])

    def test_missing_energy_value_becomes_rejecting_quality_flag(self):
        exported = exported_energy()
        exported["series"]["grid_import"][0]["energy_kwh"] = None

        result = MODULE.build_actual_bundle(
            date(2026, 10, 7), exported, settled_at="2026-10-07T23:00:00+00:00"
        )

        self.assertEqual(result["intervals"][0]["grid_import_kwh"], 0.0)
        self.assertIn(
            "grid_import:missing_energy_value",
            result["intervals"][0]["quality_flags"],
        )

    def test_primary_stratum_prioritizes_exception_days(self):
        self.assertEqual(
            MODULE.classify_primary_stratum(
                date(2026, 10, 7),
                minimum_market_price=-1.0,
                pv_forecast_kwh=20.0,
                ev_charge_kwh=8.0,
            ),
            "negative_price_day",
        )
        self.assertEqual(
            MODULE.classify_primary_stratum(
                date(2026, 10, 10),
                minimum_market_price=50.0,
                pv_forecast_kwh=5.0,
                ev_charge_kwh=0.0,
            ),
            "weekend",
        )

    def test_primary_stratum_covers_seasons_and_ordinary_days(self):
        self.assertEqual(
            MODULE.classify_primary_stratum(
                date(2026, 1, 7),
                minimum_market_price=50.0,
                pv_forecast_kwh=5.0,
                ev_charge_kwh=0.0,
            ),
            "winter_weekday",
        )
        self.assertEqual(
            MODULE.classify_primary_stratum(
                date(2026, 7, 7),
                minimum_market_price=50.0,
                pv_forecast_kwh=25.0,
                ev_charge_kwh=0.0,
            ),
            "summer_high_pv_weekday",
        )
        self.assertEqual(
            MODULE.classify_primary_stratum(
                date(2026, 10, 7),
                minimum_market_price=50.0,
                pv_forecast_kwh=10.0,
                ev_charge_kwh=0.0,
            ),
            "ordinary_shoulder_weekday",
        )

    def test_failure_outputs_are_explicit_and_read_only(self):
        settlement = MODULE.failure_settlement(
            date(2026, 10, 7), "SETTLEMENT_PIPELINE_ERROR:RuntimeError"
        )
        cohort = MODULE.failure_cohort_report(
            date(2026, 10, 7), "SETTLEMENT_PIPELINE_ERROR:RuntimeError"
        )

        self.assertEqual(settlement["status"], "REJECTED")
        self.assertFalse(settlement["physical_writes"])
        self.assertIn("SETTLEMENT_PIPELINE_ERROR", settlement["quality_flags"][0])
        self.assertEqual(cohort["status"], "IN_PROGRESS")
        self.assertEqual(cohort["rejected_days"][0]["target_date"], "2026-10-07")

    def test_target_bounds_follow_dst_day_lengths(self):
        spring_start, spring_end = MODULE.target_bounds(date(2026, 3, 29))
        autumn_start, autumn_end = MODULE.target_bounds(date(2026, 10, 25))

        self.assertEqual((spring_end - spring_start).total_seconds() / 3600, 23)
        self.assertEqual((autumn_end - autumn_start).total_seconds() / 3600, 25)

    def test_output_failure_rewrites_fail_closed_without_runtime_assignment(self):
        target = date(2026, 10, 7)
        paths = []
        failed_once = False

        def writer(path, value):
            nonlocal failed_once
            paths.append((path.name, value.get("status")))
            if path.name == "settlement-summary-2026-10-07.json" and not failed_once:
                failed_once = True
                raise OSError("simulated write failure")

        with patch.object(MODULE, "write_json_atomic", side_effect=writer):
            result = MODULE.persist_outputs(
                target=target,
                settled_at="2026-10-08T00:45:00+00:00",
                captures_dir=Path("captures"),
                cohort_output=Path("cohort.json"),
                runtime_config_path=Path("captures/cohort-runtime.json"),
                actual=MODULE.empty_actual_bundle(
                    target, "2026-10-08T00:45:00+00:00"
                ),
                settlement={
                    "status": "SETTLED",
                    "quality": "ACCEPTED_PROSPECTIVE_DAY",
                },
                summary={"status": "SETTLED", "target_date": "2026-10-07"},
                cohort={"status": "IN_PROGRESS"},
                runtime_config={"assignments": {"2026-10-07": "weekend"}},
            )

        self.assertEqual(result["settlement"]["status"], "REJECTED")
        self.assertEqual(result["cohort"]["status"], "IN_PROGRESS")
        self.assertNotIn("cohort-runtime.json", [name for name, _ in paths])

    def test_persistent_output_failure_still_attempts_every_fail_closed_artifact(self):
        target = date(2026, 10, 7)
        paths = []

        def writer(path, value):
            paths.append((path.name, value.get("status")))
            if path.name == "settlement-summary-2026-10-07.json":
                raise OSError("persistent simulated write failure")

        with patch.object(MODULE, "write_json_atomic", side_effect=writer):
            with self.assertRaisesRegex(OSError, "fail-closed output writes failed"):
                MODULE.persist_outputs(
                    target=target,
                    settled_at="2026-10-08T00:45:00+00:00",
                    captures_dir=Path("captures"),
                    cohort_output=Path("cohort.json"),
                    runtime_config_path=Path("captures/cohort-runtime.json"),
                    actual=MODULE.empty_actual_bundle(
                        target, "2026-10-08T00:45:00+00:00"
                    ),
                    settlement={
                        "status": "SETTLED",
                        "quality": "ACCEPTED_PROSPECTIVE_DAY",
                    },
                    summary={"status": "SETTLED", "target_date": "2026-10-07"},
                    cohort={"status": "IN_PROGRESS"},
                    runtime_config={"assignments": {"2026-10-07": "weekend"}},
                )

        names = [name for name, _ in paths]
        self.assertGreaterEqual(names.count("actual-2026-10-07.json"), 2)
        self.assertGreaterEqual(names.count("settlement-2026-10-07.json"), 2)
        self.assertGreaterEqual(
            names.count("settlement-summary-2026-10-07.json"), 2
        )
        self.assertEqual(names.count("cohort.json"), 1)
        self.assertNotIn("cohort-runtime.json", names)


if __name__ == "__main__":
    unittest.main()
