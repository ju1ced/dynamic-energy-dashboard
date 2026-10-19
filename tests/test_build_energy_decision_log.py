import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_energy_decision_log", ROOT / "scripts" / "build_energy_decision_log.py"
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EnergyDecisionLogTests(unittest.TestCase):
    def test_generated_log_is_auditable_read_only_and_reproducible(self):
        log = MODULE.build_decision_log(ROOT)

        self.assertEqual(log["schema_version"], 1)
        self.assertEqual(log["mode"], "READ_ONLY")
        self.assertGreaterEqual(len(log["entries"]), 5)
        self.assertEqual(
            {entry["entry_kind"] for entry in log["entries"]},
            {"MEASUREMENT_CONCLUSION", "SIMULATION_DECISION"},
        )

        for entry in log["entries"]:
            self.assertTrue(entry["id"])
            self.assertTrue(entry["recorded_at"])
            self.assertTrue(entry["scenario_id"])
            self.assertTrue(entry["inputs"]["evidence_refs"])
            self.assertTrue(entry["constraints"]["read_only"])
            self.assertFalse(entry["constraints"]["physical_writes_allowed"])
            self.assertFalse(entry["constraints"]["contract_change_allowed"])
            self.assertIn(entry["confidence"]["level"], {"HIGH", "MEDIUM", "LOW"})
            self.assertGreaterEqual(entry["confidence"]["score"], 0.0)
            self.assertLessEqual(entry["confidence"]["score"], 1.0)
            self.assertIsNone(entry["proposed_action"]["production_command"])
            self.assertIsNone(entry["proposed_action"]["setpoint"])
            self.assertTrue(entry["reproduction"]["script"])
            self.assertIsInstance(entry["reproduction"]["arguments"], list)

        tariff_entry = next(
            entry
            for entry in log["entries"]
            if entry["scenario_id"] == "dynamic_contract_component_reconciliation"
        )
        self.assertEqual(tariff_entry["entry_kind"], "MEASUREMENT_CONCLUSION")
        self.assertEqual(
            tariff_entry["outcome"]["metrics"]["dsmr_invoice_assessment"],
            "TOTAL_CLOSE_COMPONENT_MISMATCH",
        )
        self.assertAlmostEqual(
            tariff_entry["outcome"]["metrics"]["dsmr_invoice_total_difference_eur"],
            -24.37,
        )

    def test_writer_round_trips_the_generated_log(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "decision-log.json"
            generated = MODULE.write_decision_log(ROOT, output)
            stored = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(stored, generated)


if __name__ == "__main__":
    unittest.main()
