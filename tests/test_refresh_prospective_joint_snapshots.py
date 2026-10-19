import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "refresh_prospective_joint_snapshots",
    ROOT / "scripts" / "refresh_prospective_joint_snapshots.py",
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RefreshProspectiveJointSnapshotsTests(unittest.TestCase):
    def valid_config_and_states(self):
        observed = "2026-10-13T21:43:00+00:00"
        config = {
            "max_age_minutes": 15,
            "battery": {
                "minimum_soc_percent": 3.0,
                "maximum_soc_percent": 97.0,
                "usable_capacity_kwh": 14.24,
                "max_charge_power_kw": 5.0,
                "max_discharge_power_kw": 5.0,
            },
            "ev": {
                "usable_capacity_kwh": 74.0,
                "max_charge_power_kw": 7.4,
            },
        }
        states = {
            "battery_soc": {"state": "55", "last_reported": observed},
            "battery_device_available": {"state": "on", "last_reported": observed},
            "ev_soc": {"state": "62", "last_reported": observed},
            "ev_device_available": {"state": "on", "last_reported": observed},
            "ev_connected": {"state": "on", "last_reported": observed},
            "ev_target_soc": {"state": "80", "last_reported": observed},
            "ev_departure_utc": {
                "state": "2026-10-14T06:30:00+00:00",
                "last_reported": observed,
            },
            "battery_manual_override": {"state": "off", "last_reported": observed},
            "battery_local_fallback": {"state": "off", "last_reported": observed},
            "battery_acknowledgement_timed_out": {
                "state": "off",
                "last_reported": observed,
            },
            "ev_manual_override": {"state": "off", "last_reported": observed},
            "ev_local_fallback": {"state": "off", "last_reported": observed},
            "ev_acknowledgement_timed_out": {
                "state": "off",
                "last_reported": observed,
            },
        }
        return config, states

    def test_builds_control_and_safety_snapshots_from_observed_states(self):
        captured_at = datetime(2026, 10, 13, 21, 44, tzinfo=timezone.utc)
        config, states = self.valid_config_and_states()

        control, safety = MODULE.build_joint_snapshots(
            config, states, captured_at=captured_at
        )

        self.assertEqual(control["battery"]["soc_percent"], 55.0)
        self.assertEqual(control["ev"]["target_soc_percent"], 80.0)
        self.assertTrue(control["ev"]["connected"])
        self.assertEqual(control["battery"]["controller_owner"], "SMA")
        self.assertEqual(control["ev"]["controller_owner"], "SMAPPEE")
        self.assertFalse(safety["battery"]["manual_override_active"])
        self.assertFalse(safety["ev"]["acknowledgement_timed_out"])
        self.assertTrue(safety["battery"]["device_available"])
        self.assertEqual(
            control["snapshot_generation_id"], safety["snapshot_generation_id"]
        )
        self.assertFalse(control["execution_allowed"] if "execution_allowed" in control else False)

    def test_observed_device_unavailability_is_preserved(self):
        captured_at = datetime(2026, 10, 13, 21, 44, tzinfo=timezone.utc)
        config, states = self.valid_config_and_states()
        states["battery_device_available"]["state"] = "off"

        _, safety = MODULE.build_joint_snapshots(
            config, states, captured_at=captured_at
        )

        self.assertFalse(safety["battery"]["device_available"])

    def test_rejects_one_stale_observation_instead_of_hiding_it(self):
        captured_at = datetime(2026, 10, 13, 21, 44, tzinfo=timezone.utc)
        config, states = self.valid_config_and_states()
        states["ev_local_fallback"]["last_reported"] = (
            captured_at - timedelta(minutes=16)
        ).isoformat()

        with self.assertRaisesRegex(ValueError, "stale: ev_local_fallback"):
            MODULE.build_joint_snapshots(config, states, captured_at=captured_at)

    def test_rejects_unavailable_required_safety_state(self):
        captured_at = datetime(2026, 10, 13, 21, 44, tzinfo=timezone.utc)
        config, states = self.valid_config_and_states()
        states["battery_manual_override"]["state"] = "unavailable"

        with self.assertRaisesRegex(ValueError, "unavailable: battery_manual_override"):
            MODULE.build_joint_snapshots(config, states, captured_at=captured_at)

    def test_rejects_inverted_battery_soc_bounds(self):
        captured_at = datetime(2026, 10, 13, 21, 44, tzinfo=timezone.utc)
        config, states = self.valid_config_and_states()
        config["battery"]["minimum_soc_percent"] = 98.0

        with self.assertRaisesRegex(ValueError, "minimum SOC must be below maximum"):
            MODULE.build_joint_snapshots(config, states, captured_at=captured_at)

    def test_rejects_past_ev_departure(self):
        captured_at = datetime(2026, 10, 13, 21, 44, tzinfo=timezone.utc)
        config, states = self.valid_config_and_states()
        states["ev_departure_utc"]["state"] = "2026-10-13T21:43:00+00:00"

        with self.assertRaisesRegex(ValueError, "EV departure must be after capture"):
            MODULE.build_joint_snapshots(config, states, captured_at=captured_at)

    def test_rejects_ev_target_below_current_soc(self):
        captured_at = datetime(2026, 10, 13, 21, 44, tzinfo=timezone.utc)
        config, states = self.valid_config_and_states()
        states["ev_target_soc"]["state"] = "61"

        with self.assertRaisesRegex(ValueError, "EV target SOC must not be below current SOC"):
            MODULE.build_joint_snapshots(config, states, captured_at=captured_at)

    def test_rejects_duplicate_entity_mappings(self):
        config, alias_states = self.valid_config_and_states()
        config["entities"] = {
            alias: f"sensor.fixture_{alias}" for alias in alias_states
        }
        config["entities"]["ev_soc"] = config["entities"]["battery_soc"]
        raw_states = {
            config["entities"][alias]: state for alias, state in alias_states.items()
        }

        with self.assertRaisesRegex(ValueError, "entity mappings must be unique"):
            MODULE._map_states(config, raw_states)

    def test_persists_both_snapshots_atomically_after_validation(self):
        captured_at = datetime(2026, 10, 13, 21, 44, tzinfo=timezone.utc)
        config, states = self.valid_config_and_states()
        control, safety = MODULE.build_joint_snapshots(
            config, states, captured_at=captured_at
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control_path = root / "control.json"
            safety_path = root / "safety.json"
            MODULE.persist_snapshot_pair(control_path, safety_path, control, safety)

            self.assertEqual(json.loads(control_path.read_text()), control)
            self.assertEqual(json.loads(safety_path.read_text()), safety)
            self.assertEqual(list(root.glob("*.tmp")), [])

    def test_second_replace_failure_removes_both_snapshot_outputs(self):
        captured_at = datetime(2026, 10, 13, 21, 44, tzinfo=timezone.utc)
        config, states = self.valid_config_and_states()
        control, safety = MODULE.build_joint_snapshots(
            config, states, captured_at=captured_at
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control_path = root / "control.json"
            safety_path = root / "safety.json"
            control_path.write_text('{"old": true}')
            safety_path.write_text('{"old": true}')
            real_replace = MODULE.os.replace
            calls = 0

            def fail_second_replace(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected second replace failure")
                return real_replace(source, target)

            with mock.patch.object(MODULE.os, "replace", side_effect=fail_second_replace):
                with self.assertRaisesRegex(OSError, "second replace failure"):
                    MODULE.persist_snapshot_pair(
                        control_path, safety_path, control, safety
                    )

            self.assertFalse(control_path.exists())
            self.assertFalse(safety_path.exists())

    def test_predictable_legacy_temp_symlink_is_never_followed(self):
        captured_at = datetime(2026, 10, 13, 21, 44, tzinfo=timezone.utc)
        config, states = self.valid_config_and_states()
        control, safety = MODULE.build_joint_snapshots(
            config, states, captured_at=captured_at
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control_path = root / "control.json"
            safety_path = root / "safety.json"
            victim = root / "victim.txt"
            victim.write_text("unchanged")
            legacy_temp = root / f".{control_path.name}.{MODULE.os.getpid()}.tmp"
            legacy_temp.symlink_to(victim)

            MODULE.persist_snapshot_pair(control_path, safety_path, control, safety)

            self.assertEqual(victim.read_text(), "unchanged")

    def test_rollback_cleanup_failure_is_hard_even_with_soft_fail(self):
        config, alias_states = self.valid_config_and_states()
        config["entities"] = {
            alias: f"sensor.fixture_{alias}" for alias in alias_states
        }
        raw_states = {
            config["entities"][alias]: state for alias, state in alias_states.items()
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "source.json"
            states_path = root / "states.json"
            control_path = root / "control.json"
            safety_path = root / "safety.json"
            config_path.write_text(json.dumps(config))
            states_path.write_text(json.dumps({"states": raw_states}))
            real_replace = MODULE.os.replace
            replace_calls = 0
            real_unlink = Path.unlink

            def fail_second_replace(source, target):
                nonlocal replace_calls
                replace_calls += 1
                if replace_calls == 2:
                    raise OSError("injected second replace failure")
                return real_replace(source, target)

            def fail_rollback_unlink(path, *args, **kwargs):
                if path == control_path and path.exists():
                    raise PermissionError("injected rollback cleanup failure")
                if path.suffix == ".tmp" and path.exists():
                    raise PermissionError("injected temporary cleanup failure")
                return real_unlink(path, *args, **kwargs)

            with mock.patch.object(MODULE.os, "replace", side_effect=fail_second_replace):
                with mock.patch.object(Path, "unlink", new=fail_rollback_unlink):
                    result = MODULE.main(
                        [
                            "--config",
                            str(config_path),
                            "--states-fixture",
                            str(states_path),
                            "--control-output",
                            str(control_path),
                            "--safety-output",
                            str(safety_path),
                            "--now",
                            "2026-10-13T21:44:00+00:00",
                            "--soft-fail",
                        ]
                    )

            self.assertEqual(result, 2)

    def test_extracts_sdk_structured_content_and_rejects_tool_errors(self):
        class Result:
            def __init__(self, *, is_error=False):
                self.is_error = is_error

            def model_dump(self, mode="json"):
                return {
                    "is_error": self.is_error,
                    "structured_content": {"data": {"states": {}}},
                    "content": [],
                }

        self.assertEqual(MODULE._extract_tool_data(Result()), {"states": {}})
        with self.assertRaisesRegex(ValueError, "reported an error"):
            MODULE._extract_tool_data(Result(is_error=True))

    def test_soft_fail_catches_runtime_transport_errors_after_cleanup(self):
        config, alias_states = self.valid_config_and_states()
        config["entities"] = {
            alias: f"sensor.fixture_{alias}" for alias in alias_states
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "source.json"
            control_path = root / "control.json"
            safety_path = root / "safety.json"
            config_path.write_text(json.dumps(config))
            control_path.write_text('{"old": true}')
            safety_path.write_text('{"old": true}')

            async def fail_transport(config, wrapper):
                raise RuntimeError("transport failed")

            with mock.patch.object(
                MODULE, "_fetch_live_states", side_effect=fail_transport
            ):
                result = MODULE.main(
                    [
                        "--config",
                        str(config_path),
                        "--control-output",
                        str(control_path),
                        "--safety-output",
                        str(safety_path),
                        "--soft-fail",
                    ]
                )

            self.assertEqual(result, 0)
            self.assertFalse(control_path.exists())
            self.assertFalse(safety_path.exists())

    def test_cleanup_failure_is_reported_and_never_soft_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control_path = root / "control.json"
            safety_path = root / "safety.json"
            control_path.write_text('{"old": true}')
            safety_path.write_text('{"old": true}')
            real_unlink = Path.unlink

            def fail_control_unlink(path, *args, **kwargs):
                if path == control_path:
                    raise PermissionError("injected cleanup failure")
                return real_unlink(path, *args, **kwargs)

            with mock.patch.object(Path, "unlink", new=fail_control_unlink):
                result = MODULE.main(
                    [
                        "--config",
                        str(root / "missing.json"),
                        "--control-output",
                        str(control_path),
                        "--safety-output",
                        str(safety_path),
                        "--soft-fail",
                    ]
                )

            self.assertEqual(result, 2)

    def test_cli_fixture_writes_snapshots_without_network_access(self):
        config, alias_states = self.valid_config_and_states()
        config["entities"] = {
            alias: f"sensor.fixture_{alias}" for alias in alias_states
        }
        raw_states = {
            config["entities"][alias]: state for alias, state in alias_states.items()
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "source.json"
            states_path = root / "states.json"
            control_path = root / "control.json"
            safety_path = root / "safety.json"
            config_path.write_text(json.dumps(config))
            states_path.write_text(json.dumps({"states": raw_states}))

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "refresh_prospective_joint_snapshots.py"),
                    "--config",
                    str(config_path),
                    "--states-fixture",
                    str(states_path),
                    "--control-output",
                    str(control_path),
                    "--safety-output",
                    str(safety_path),
                    "--now",
                    "2026-10-13T21:44:00+00:00",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(control_path.exists())
            self.assertTrue(safety_path.exists())
            self.assertEqual(json.loads(result.stdout)["status"], "READY")


if __name__ == "__main__":
    unittest.main()
