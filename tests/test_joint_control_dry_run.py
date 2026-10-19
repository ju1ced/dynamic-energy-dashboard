import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "joint_control_dry_run",
    ROOT / "scripts" / "joint_control_dry_run.py",
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

NOW = datetime(2026, 10, 12, 20, 0, tzinfo=timezone.utc)


def planner_output():
    return {
        "schema_version": 1,
        "plan_id": "shadow-2026-10-12",
        "generated_at": (NOW - timedelta(minutes=2)).isoformat(),
        "valid_from_utc": NOW.isoformat(),
        "valid_until_utc": (NOW + timedelta(minutes=30)).isoformat(),
        "selected_policy_id": "cap_7_kw",
        "shared_grid_import_limit_kw": 7.0,
        "intervals": [
            {
                "start_utc": NOW.isoformat(),
                "end_utc": (NOW + timedelta(minutes=15)).isoformat(),
                "forecast_base_load_kw": 2.0,
                "battery_power_kw": 1.5,
                "ev_power_kw": 3.0,
                "reason": "LOW_PRICE; shared headroom available",
            },
            {
                "start_utc": (NOW + timedelta(minutes=15)).isoformat(),
                "end_utc": (NOW + timedelta(minutes=30)).isoformat(),
                "forecast_base_load_kw": 4.0,
                "battery_power_kw": -1.0,
                "ev_power_kw": 0.0,
                "reason": "HIGH_PRICE; discharge to load",
            },
        ],
    }


def control_inputs():
    observed = (NOW - timedelta(minutes=1)).isoformat()
    return {
        "observed_at": observed,
        "battery": {
            "available": True,
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
            "available": True,
            "connected": True,
            "soc_percent": 40.0,
            "target_soc_percent": 80.0,
            "usable_capacity_kwh": 60.0,
            "departure_utc": (NOW + timedelta(hours=10)).isoformat(),
            "max_charge_power_kw": 7.4,
            "controller_owner": "SMAPPEE",
            "observed_at": observed,
        },
    }


def safety_state():
    return {
        "observed_at": (NOW - timedelta(seconds=15)).isoformat(),
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
            "soc_percent": 40.0,
        },
    }


class JointControlIntentTests(unittest.TestCase):
    def test_joint_plan_builds_actuator_neutral_battery_and_ev_intents(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)

        self.assertEqual(bundle["classification"], "DRY_RUN_CONTROL_INTENTS_NO_EXECUTION")
        self.assertEqual(bundle["status"], "READY_FOR_SAFETY_REVIEW")
        self.assertFalse(bundle["execution_allowed"])
        self.assertFalse(bundle["physical_writes"])
        self.assertEqual(len(bundle["intents"]), 4)
        first_battery, first_ev = bundle["intents"][:2]
        self.assertEqual(first_battery["target"], "BATTERY")
        self.assertEqual(first_battery["requested_action"], "CHARGE")
        self.assertEqual(first_battery["requested_power_kw"], 1.5)
        self.assertEqual(first_battery["ownership"]["expected_controller"], "SMA")
        self.assertEqual(first_ev["target"], "EV_CHARGER")
        self.assertEqual(first_ev["requested_action"], "CHARGE")
        self.assertEqual(first_ev["ownership"]["expected_controller"], "SMAPPEE")
        for intent in bundle["intents"]:
            self.assertEqual(intent["source_plan_id"], "shadow-2026-10-12")
            self.assertFalse(intent["execution_allowed"])
            self.assertIn("valid_until_utc", intent)
            self.assertIn("limits", intent)
            self.assertTrue(intent["reason"])

    def test_missing_ev_requirement_becomes_explicit_no_action(self):
        inputs = control_inputs()
        del inputs["ev"]

        bundle = MODULE.build_intent_bundle(planner_output(), inputs, now=NOW)
        ev_intents = [intent for intent in bundle["intents"] if intent["target"] == "EV_CHARGER"]

        self.assertTrue(ev_intents)
        self.assertTrue(all(intent["requested_action"] == "NO_ACTION" for intent in ev_intents))
        self.assertTrue(all(intent["reason"] == "MISSING_EV_REQUIREMENT" for intent in ev_intents))

    def test_invalid_or_overlapping_planner_intervals_fail_closed(self):
        plan = planner_output()
        plan["intervals"][1]["start_utc"] = plan["intervals"][0]["start_utc"]

        bundle = MODULE.build_intent_bundle(plan, control_inputs(), now=NOW)

        self.assertEqual(bundle["status"], "NO_ACTION")
        self.assertEqual(bundle["reason"], "INVALID_PLAN_INTERVALS")
        self.assertEqual(bundle["intents"], [])

    def test_plan_must_cover_its_complete_declared_validity_window(self):
        plan = planner_output()
        plan["intervals"] = plan["intervals"][:1]

        bundle = MODULE.build_intent_bundle(plan, control_inputs(), now=NOW)

        self.assertEqual(bundle["status"], "NO_ACTION")
        self.assertEqual(bundle["reason"], "INVALID_PLAN_OR_INPUT_CONTRACT")
        self.assertEqual(bundle["intents"], [])

    def test_schema_and_selected_policy_are_required(self):
        for mutation in (
            {"schema_version": 999},
            {"selected_policy_id": ""},
        ):
            with self.subTest(mutation=mutation):
                plan = planner_output()
                plan.update(mutation)
                result = MODULE.build_intent_bundle(plan, control_inputs(), now=NOW)
                self.assertEqual(result["status"], "NO_ACTION")
                self.assertEqual(result["reason"], "INVALID_PLAN_OR_INPUT_CONTRACT")


class SafetySupervisorTests(unittest.TestCase):
    def test_cumulative_battery_and_ev_soc_trajectories_fail_closed(self):
        plan = planner_output()
        plan["valid_until_utc"] = (NOW + timedelta(hours=1)).isoformat()
        plan["shared_grid_import_limit_kw"] = 20.0
        plan["intervals"] = []
        for index in range(4):
            start = NOW + timedelta(minutes=15 * index)
            plan["intervals"].append(
                {
                    "start_utc": start.isoformat(),
                    "end_utc": (start + timedelta(minutes=15)).isoformat(),
                    "forecast_base_load_kw": 0.0,
                    "battery_power_kw": 2.0,
                    "ev_power_kw": 7.0,
                    "reason": "cumulative SOC trajectory test",
                }
            )
        inputs = control_inputs()
        inputs["battery"]["soc_percent"] = 80.0
        inputs["battery"]["usable_capacity_kwh"] = 10.0
        inputs["ev"]["soc_percent"] = 70.0
        inputs["ev"]["target_soc_percent"] = 80.0
        inputs["ev"]["usable_capacity_kwh"] = 60.0
        state = safety_state()
        state["battery"]["soc_percent"] = 80.0
        state["ev"]["soc_percent"] = 70.0

        reviewed = MODULE.supervise_intents(
            MODULE.build_intent_bundle(plan, inputs, now=NOW), state, now=NOW
        )

        self.assertEqual(reviewed["status"], "REJECTED")
        battery_reasons = [
            reason
            for decision in reviewed["decisions"]
            if decision["target"] == "BATTERY"
            for reason in decision["reasons"]
        ]
        ev_reasons = [
            reason
            for decision in reviewed["decisions"]
            if decision["target"] == "EV_CHARGER"
            for reason in decision["reasons"]
        ]
        self.assertIn("BATTERY_CUMULATIVE_SOC_LIMIT", battery_reasons)
        self.assertIn("EV_CUMULATIVE_SOC_TARGET_EXCEEDED", ev_reasons)

    def test_normal_intents_are_accepted_for_dry_run_but_never_execution(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        result = MODULE.supervise_intents(bundle, safety_state(), now=NOW)

        self.assertEqual(result["status"], "ACCEPTED_DRY_RUN")
        self.assertFalse(result["execution_allowed"])
        self.assertTrue(all(item["decision"] == "ACCEPTED_DRY_RUN" for item in result["decisions"]))
        self.assertTrue(all(item["execution_action"] == "NO_ACTION" for item in result["decisions"]))
        self.assertEqual(result["decisions"][0]["dry_run_action"], "CHARGE")

    def test_stale_future_and_expired_inputs_are_rejected(self):
        for label, mutate in (
            (
                "stale",
                lambda bundle, state: state.update(
                    {"observed_at": (NOW - timedelta(minutes=20)).isoformat()}
                ),
            ),
            (
                "future",
                lambda bundle, state: state.update(
                    {"observed_at": (NOW + timedelta(minutes=1)).isoformat()}
                ),
            ),
            (
                "expired",
                lambda bundle, state: bundle.update(
                    {"valid_until_utc": (NOW - timedelta(seconds=1)).isoformat()}
                ),
            ),
        ):
            with self.subTest(label=label):
                bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
                state = safety_state()
                mutate(bundle, state)
                result = MODULE.supervise_intents(bundle, state, now=NOW)
                self.assertEqual(result["status"], "REJECTED")
                self.assertTrue(all(item["dry_run_action"] == "NO_ACTION" for item in result["decisions"]))

    def test_controller_conflict_manual_override_fallback_and_timeout_reject(self):
        cases = {
            "CONTROLLER_OWNERSHIP_CONFLICT": ("controller_owner", "HOME_ASSISTANT"),
            "MANUAL_OVERRIDE_ACTIVE": ("manual_override_active", True),
            "LOCAL_FALLBACK_ACTIVE": ("local_fallback_active", True),
            "ACKNOWLEDGEMENT_TIMEOUT": ("acknowledgement_timed_out", True),
        }
        for expected, (field, value) in cases.items():
            with self.subTest(expected=expected):
                bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
                state = safety_state()
                state["battery"][field] = value
                result = MODULE.supervise_intents(bundle, state, now=NOW)
                battery = [item for item in result["decisions"] if item["target"] == "BATTERY"]
                self.assertTrue(any(expected in item["reasons"] for item in battery))
                self.assertTrue(all(item["dry_run_action"] == "NO_ACTION" for item in battery))

    def test_power_soc_charger_and_shared_grid_limits_fail_closed(self):
        plan = planner_output()
        plan["intervals"][0]["battery_power_kw"] = 4.0
        plan["intervals"][0]["ev_power_kw"] = 4.0
        inputs = control_inputs()
        inputs["battery"]["soc_percent"] = 96.0
        state = safety_state()
        state["battery"]["soc_percent"] = 96.0
        state["ev"]["device_available"] = False

        bundle = MODULE.build_intent_bundle(plan, inputs, now=NOW)
        result = MODULE.supervise_intents(bundle, state, now=NOW)
        reasons = {reason for decision in result["decisions"] for reason in decision["reasons"]}

        self.assertIn("POWER_LIMIT_EXCEEDED", reasons)
        self.assertIn("BATTERY_SOC_LIMIT", reasons)
        self.assertIn("DEVICE_UNAVAILABLE", reasons)
        self.assertIn("SHARED_GRID_IMPORT_LIMIT_EXCEEDED", reasons)
        self.assertEqual(result["status"], "REJECTED")

    def test_malformed_interval_context_and_tampered_shared_cap_fail_closed(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        del bundle["intents"][0]["interval_context"]
        for intent in bundle["intents"]:
            intent["limits"]["shared_grid_import_limit_kw"] = 100.0

        result = MODULE.supervise_intents(bundle, safety_state(), now=NOW)
        reasons = {reason for decision in result["decisions"] for reason in decision["reasons"]}

        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("INTERVAL_CONTEXT_CONFLICT", reasons)
        self.assertIn("SHARED_GRID_LIMIT_CONFLICT", reasons)

    def test_missing_target_intent_for_an_interval_fails_closed(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        bundle["intents"] = [
            intent
            for intent in bundle["intents"]
            if not (
                intent["target"] == "BATTERY"
                and intent["target_interval"]["start_utc"] == NOW.isoformat()
            )
        ]

        result = MODULE.supervise_intents(bundle, safety_state(), now=NOW)

        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("INTENT_BUNDLE_INTEGRITY_INVALID", result["reasons"])
        self.assertIn("TARGET_INTERVAL_COVERAGE_INVALID", result["reasons"])

    def test_removing_complete_interval_cannot_be_hidden_with_recomputed_plain_sha256(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        removed_start = (NOW + timedelta(minutes=15)).isoformat()
        bundle["intents"] = [
            intent
            for intent in bundle["intents"]
            if intent["target_interval"]["start_utc"] != removed_start
        ]
        canonical = {
            key: value
            for key, value in bundle.items()
            if key != "bundle_integrity_hmac_sha256"
        }
        bundle["bundle_integrity_hmac_sha256"] = hashlib.sha256(
            json.dumps(
                canonical,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

        result = MODULE.supervise_intents(bundle, safety_state(), now=NOW)

        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("INTENT_BUNDLE_INTEGRITY_INVALID", result["reasons"])
        self.assertIn("TARGET_INTERVAL_COVERAGE_INVALID", result["reasons"])

    def test_consistent_action_and_limit_tampering_breaks_bundle_integrity(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        battery = bundle["intents"][0]
        battery.update(
            {
                "requested_action": "DISCHARGE",
                "requested_power_kw": 6.0,
                "requested_grid_effect_kw": -6.0,
            }
        )
        battery["limits"].update(
            {
                "max_discharge_power_kw": 10.0,
                "usable_capacity_kwh": 100.0,
            }
        )

        result = MODULE.supervise_intents(bundle, safety_state(), now=NOW)

        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("INTENT_BUNDLE_INTEGRITY_INVALID", result["decisions"][0]["reasons"])

    def test_unknown_and_internally_inconsistent_actions_fail_closed(self):
        mutations = (
            {"requested_action": "SETPOINT", "requested_power_kw": 999.0, "requested_grid_effect_kw": 0.0},
            {"requested_action": "HOLD", "requested_power_kw": 1.0, "requested_grid_effect_kw": 1.0},
            {"requested_action": "CHARGE", "requested_power_kw": 1.0, "requested_grid_effect_kw": -1.0},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
                bundle["intents"][0].update(mutation)
                result = MODULE.supervise_intents(bundle, safety_state(), now=NOW)
                first = result["decisions"][0]
                self.assertEqual(first["decision"], "REJECTED")
                self.assertIn("ACTION_CONTRACT_INVALID", first["reasons"])
                self.assertEqual(first["dry_run_action"], "NO_ACTION")

    def test_incomplete_ownership_or_safety_flags_are_rejected(self):
        for label, mutate in (
            (
                "ownership",
                lambda bundle, state: bundle["intents"][0]["ownership"].update(
                    {"observed_controller": None}
                ),
            ),
            (
                "override",
                lambda bundle, state: state["battery"].pop("manual_override_active"),
            ),
            (
                "fallback",
                lambda bundle, state: state["battery"].pop("local_fallback_active"),
            ),
            (
                "timeout",
                lambda bundle, state: state["battery"].pop("acknowledgement_timed_out"),
            ),
        ):
            with self.subTest(label=label):
                bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
                state = safety_state()
                mutate(bundle, state)
                result = MODULE.supervise_intents(bundle, state, now=NOW)
                self.assertEqual(result["decisions"][0]["decision"], "REJECTED")

    def test_projected_soc_and_mid_interval_departure_are_rejected(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        state = safety_state()
        state["battery"]["soc_percent"] = 93.0
        bundle["intents"][1]["limits"]["departure_utc"] = (
            NOW + timedelta(minutes=10)
        ).isoformat()

        result = MODULE.supervise_intents(bundle, state, now=NOW)

        self.assertIn("BATTERY_PROJECTED_SOC_LIMIT", result["decisions"][0]["reasons"])
        self.assertIn("EV_DEPARTURE_BEFORE_INTERVAL_END", result["decisions"][1]["reasons"])

    def test_duplicate_target_interval_is_rejected(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        bundle["intents"].append(deepcopy(bundle["intents"][0]))

        result = MODULE.supervise_intents(bundle, safety_state(), now=NOW)

        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(
            any("DUPLICATE_TARGET_INTERVAL" in item["reasons"] for item in result["decisions"])
        )

    def test_stale_plan_tampered_source_and_write_boundary_are_rejected(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        for intent in bundle["intents"]:
            intent["source_plan_generated_at"] = (NOW - timedelta(hours=19)).isoformat()
        bundle["intents"][0]["source_plan_id"] = "foreign-plan"
        bundle["intents"][0]["execution_allowed"] = True

        result = MODULE.supervise_intents(bundle, safety_state(), now=NOW)
        first_reasons = result["decisions"][0]["reasons"]

        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("STALE_INPUT", first_reasons)
        self.assertIn("SOURCE_PLAN_CONFLICT", first_reasons)
        self.assertIn("WRITE_BOUNDARY_INVALID", first_reasons)

    def test_tampered_intent_schema_identity_and_validity_are_rejected(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        battery = bundle["intents"][0]
        battery["schema_version"] = 999
        battery["intent_id"] = "tampered"
        battery["valid_from_utc"] = (NOW + timedelta(minutes=1)).isoformat()

        result = MODULE.supervise_intents(bundle, safety_state(), now=NOW)
        reasons = result["decisions"][0]["reasons"]

        self.assertIn("SCHEMA_VERSION_INVALID", reasons)
        self.assertIn("INTENT_ID_INVALID", reasons)
        self.assertIn("INTENT_VALIDITY_INVALID", reasons)

    def test_ev_charge_stops_when_target_soc_is_already_reached(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        state = safety_state()
        state["ev"]["soc_percent"] = 80.0

        result = MODULE.supervise_intents(bundle, state, now=NOW)
        ev_charge = next(
            decision
            for decision in result["decisions"]
            if decision["target"] == "EV_CHARGER"
            and decision["target_interval"]["start_utc"] == NOW.isoformat()
        )

        self.assertEqual(ev_charge["decision"], "REJECTED")
        self.assertIn("EV_SOC_TARGET_REACHED", ev_charge["reasons"])
        self.assertEqual(ev_charge["dry_run_action"], "NO_ACTION")

    def test_replay_is_deterministic_across_dst_offset_change(self):
        plan = planner_output()
        replay_now = datetime(2026, 10, 25, 0, 45, tzinfo=timezone.utc)
        plan["generated_at"] = (replay_now - timedelta(minutes=2)).isoformat()
        plan["valid_from_utc"] = "2026-10-25T00:45:00+00:00"
        plan["valid_until_utc"] = "2026-10-25T01:15:00+00:00"
        plan["intervals"] = [
            {
                "start_utc": "2026-10-25T02:45:00+02:00",
                "end_utc": "2026-10-25T02:00:00+01:00",
                "forecast_base_load_kw": 1.0,
                "battery_power_kw": 0.0,
                "ev_power_kw": 2.0,
                "reason": "NEGATIVE_PRICE",
            },
            {
                "start_utc": "2026-10-25T02:00:00+01:00",
                "end_utc": "2026-10-25T02:15:00+01:00",
                "forecast_base_load_kw": 1.0,
                "battery_power_kw": 0.0,
                "ev_power_kw": 2.0,
                "reason": "NEGATIVE_PRICE",
            },
        ]
        inputs = control_inputs()
        inputs["observed_at"] = replay_now.isoformat()
        inputs["battery"]["observed_at"] = replay_now.isoformat()
        inputs["ev"]["observed_at"] = replay_now.isoformat()
        inputs["ev"]["departure_utc"] = (replay_now + timedelta(hours=10)).isoformat()
        state = safety_state()
        state["observed_at"] = replay_now.isoformat()

        first = MODULE.supervise_intents(
            MODULE.build_intent_bundle(plan, inputs, now=replay_now), state, now=replay_now
        )
        second = MODULE.supervise_intents(
            MODULE.build_intent_bundle(plan, inputs, now=replay_now), state, now=replay_now
        )

        self.assertEqual(
            json.dumps(first, sort_keys=True),
            json.dumps(second, sort_keys=True),
        )
        self.assertEqual(first["status"], "ACCEPTED_DRY_RUN")

    def test_malformed_supervisor_input_returns_rejected_review(self):
        result = MODULE.supervise_intents(None, None, now=NOW)

        self.assertEqual(result["status"], "REJECTED")
        self.assertFalse(result["execution_allowed"])
        self.assertIn("INTENT_BUNDLE_INVALID", result["reasons"])

    def test_malformed_device_state_returns_rejected_decision(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        state = safety_state()
        state["battery"] = None

        result = MODULE.supervise_intents(bundle, state, now=NOW)

        self.assertEqual(result["decisions"][0]["decision"], "REJECTED")
        self.assertIn("DEVICE_STATE_MISSING", result["decisions"][0]["reasons"])


class DryRunAdapterTests(unittest.TestCase):
    def test_adapters_only_serialize_non_dispatchable_proposals(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        supervised = MODULE.supervise_intents(bundle, safety_state(), now=NOW)
        proposals = MODULE.build_dry_run_proposals(supervised)

        self.assertEqual(len(proposals), 4)
        self.assertEqual({proposal["adapter"] for proposal in proposals}, {"SMA_DRY_RUN", "SMAPPEE_DRY_RUN"})
        for proposal in proposals:
            self.assertEqual(proposal["transport"], "NONE")
            self.assertFalse(proposal["dispatch_supported"])
            self.assertFalse(proposal["execution_allowed"])
            self.assertEqual(proposal["execution_action"], "NO_ACTION")
            for forbidden in ("endpoint", "service", "topic", "device_id", "auth", "token"):
                self.assertNotIn(forbidden, proposal)

    def test_rejected_decision_serializes_no_action_only(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        state = safety_state()
        state["ev"]["connected"] = False
        supervised = MODULE.supervise_intents(bundle, state, now=NOW)

        ev_proposals = [
            proposal
            for proposal in MODULE.build_dry_run_proposals(supervised)
            if proposal["target"] == "EV_CHARGER"
        ]

        self.assertTrue(ev_proposals)
        self.assertTrue(all(proposal["proposed_action"] == "NO_ACTION" for proposal in ev_proposals))

    def test_adapter_rejects_forged_or_malformed_reviews(self):
        forged = {
            "schema_version": 1,
            "classification": "FORGED",
            "status": "ACCEPTED_DRY_RUN",
            "execution_allowed": True,
            "physical_writes": True,
            "decisions": [
                {
                    "intent_id": "forged",
                    "target": "BATTERY",
                    "target_interval": {},
                    "decision": "ACCEPTED_DRY_RUN",
                    "reasons": None,
                    "dry_run_action": "CHARGE",
                    "requested_power_kw": 999.0,
                }
            ],
        }

        proposal = MODULE.build_dry_run_proposals(forged)[0]

        self.assertEqual(proposal["proposed_action"], "NO_ACTION")
        self.assertEqual(proposal["proposed_power_kw"], 0.0)
        self.assertIn("SAFETY_REVIEW_INVALID", proposal["safety_reasons"])
        self.assertFalse(proposal["home_assistant_writes"])
        self.assertFalse(proposal["sma_writes"])
        self.assertFalse(proposal["smappee_writes"])

    def test_structurally_forged_accepted_decision_never_becomes_active_proposal(self):
        forged = {
            "schema_version": 1,
            "classification": "SAFETY_REVIEW_DRY_RUN_NO_EXECUTION",
            "source_plan_id": "forged",
            "reviewed_at": NOW.isoformat(),
            "status": "REJECTED",
            "reasons": [],
            "execution_allowed": False,
            "physical_writes": False,
            "home_assistant_writes": False,
            "sma_writes": False,
            "smappee_writes": False,
            "decisions": [
                {
                    "intent_id": "forged:BATTERY:now",
                    "target": "BATTERY",
                    "target_interval": {
                        "start_utc": NOW.isoformat(),
                        "end_utc": (NOW + timedelta(minutes=15)).isoformat(),
                    },
                    "decision": "ACCEPTED_DRY_RUN",
                    "reasons": [],
                    "dry_run_action": "CHARGE",
                    "requested_power_kw": 999.0,
                    "execution_action": "NO_ACTION",
                    "execution_allowed": False,
                }
            ],
        }

        proposal = MODULE.build_dry_run_proposals(forged)[0]

        self.assertEqual(proposal["proposed_action"], "NO_ACTION")
        self.assertEqual(proposal["proposed_power_kw"], 0.0)
        self.assertIn("SAFETY_REVIEW_INVALID", proposal["safety_reasons"])

    def test_plain_sha256_cannot_authenticate_a_forged_accepted_review(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        reviewed = MODULE.supervise_intents(bundle, safety_state(), now=NOW)
        reviewed["decisions"][0]["dry_run_action"] = "CHARGE"
        reviewed["decisions"][0]["requested_power_kw"] = 999.0
        canonical = {
            key: value
            for key, value in reviewed.items()
            if key != "review_integrity_hmac_sha256"
        }
        reviewed["review_integrity_hmac_sha256"] = hashlib.sha256(
            json.dumps(
                canonical,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

        proposal = MODULE.build_dry_run_proposals(reviewed)[0]

        self.assertEqual(proposal["proposed_action"], "NO_ACTION")
        self.assertEqual(proposal["proposed_power_kw"], 0.0)
        self.assertIn("SAFETY_REVIEW_INVALID", proposal["safety_reasons"])

    def test_malformed_unhashable_review_reasons_fail_closed_without_raising(self):
        bundle = MODULE.build_intent_bundle(planner_output(), control_inputs(), now=NOW)
        reviewed = MODULE.supervise_intents(bundle, safety_state(), now=NOW)
        reviewed["decisions"][0]["reasons"] = [{}]

        proposal = MODULE.build_dry_run_proposals(reviewed)[0]

        self.assertEqual(proposal["proposed_action"], "NO_ACTION")
        self.assertIn("SAFETY_REVIEW_INVALID", proposal["safety_reasons"])


class DryRunCliTests(unittest.TestCase):
    def test_malformed_json_writes_fail_closed_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            inputs_path = root / "inputs.json"
            state_path = root / "state.json"
            intent_path = root / "intents.json"
            review_path = root / "review.json"
            proposals_path = root / "proposals.json"
            plan_path.write_text("{malformed", encoding="utf-8")
            inputs_path.write_text(json.dumps(control_inputs()), encoding="utf-8")
            state_path.write_text(json.dumps(safety_state()), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "joint_control_dry_run.py"),
                    "--plan",
                    str(plan_path),
                    "--inputs",
                    str(inputs_path),
                    "--safety-state",
                    str(state_path),
                    "--now",
                    NOW.isoformat(),
                    "--intent-output",
                    str(intent_path),
                    "--review-output",
                    str(review_path),
                    "--proposals-output",
                    str(proposals_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertEqual(json.loads(intent_path.read_text())["status"], "NO_ACTION")
            self.assertEqual(json.loads(review_path.read_text())["status"], "REJECTED")
            self.assertEqual(json.loads(proposals_path.read_text()), [])


if __name__ == "__main__":
    unittest.main()
