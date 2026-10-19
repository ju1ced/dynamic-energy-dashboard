import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "export_ha_energy_statistics.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ha_export", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load HA exporter from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def statistics_response(entity_id, starts, states, changes, period="5minute"):
    return {
        "success": True,
        "source": "statistics",
        "entities": [
            {
                "entity_id": entity_id,
                "period": period,
                "statistics": [
                    {"start": start, "state": state, "change": change}
                    for start, state, change in zip(starts, states, changes)
                ],
            }
        ],
    }


class HomeAssistantEnergyExportTests(unittest.TestCase):
    def test_three_five_minute_changes_become_one_quarter_without_entity_id(self):
        module = load_module()
        start_ms = 1751328000000  # 2025-07-01T00:00:00Z
        response = statistics_response(
            "sensor.private_serial_counter",
            [start_ms, start_ms + 300000, start_ms + 600000],
            [100.1, 100.2, 100.3],
            [0.1, 0.1, 0.1],
        )

        report = module.build_export(
            [response],
            entity_map={
                "grid_import": {
                    "entity_id": "sensor.private_serial_counter",
                    "scale_to_kwh": 1.0,
                }
            },
            start="2025-07-01T00:00:00Z",
            end="2025-07-01T00:15:00Z",
            retrieved_at="2026-09-29T20:00:00Z",
        )

        self.assertEqual(report["series"]["grid_import"][0]["energy_kwh"], 0.3)
        self.assertEqual(report["series"]["grid_import"][0]["quality_flags"], [])
        self.assertTrue(report["quality"]["grid_import"]["complete"])
        self.assertNotIn("private_serial", str(report))

    def test_scale_to_kwh_is_applied_before_quarter_aggregation(self):
        module = load_module()
        start_ms = 1751328000000
        response = statistics_response(
            "sensor.pv_total",
            [start_ms, start_ms + 300000, start_ms + 600000],
            [50.0, 50.001, 50.003],
            [0.0, 0.001, 0.002],
        )

        report = module.build_export(
            [response],
            entity_map={
                "pv": {"entity_id": "sensor.pv_total", "scale_to_kwh": 1000.0}
            },
            start="2025-07-01T00:00:00Z",
            end="2025-07-01T00:15:00Z",
            retrieved_at="2026-09-29T20:00:00Z",
        )

        self.assertEqual(report["series"]["pv"][0]["energy_kwh"], 3.0)

    def test_missing_five_minute_bucket_is_visible_and_not_filled(self):
        module = load_module()
        start_ms = 1751328000000
        response = statistics_response(
            "sensor.counter",
            [start_ms, start_ms + 600000],
            [100.1, 100.3],
            [0.1, 0.2],
        )

        report = module.build_export(
            [response],
            entity_map={"grid": {"entity_id": "sensor.counter", "scale_to_kwh": 1.0}},
            start="2025-07-01T00:00:00Z",
            end="2025-07-01T00:15:00Z",
            retrieved_at="2026-09-29T20:00:00Z",
        )

        quarter = report["series"]["grid"][0]
        self.assertIsNone(quarter["energy_kwh"])
        self.assertEqual(quarter["quality_flags"], ["missing_5minute_bucket"])
        self.assertEqual(report["quality"]["grid"]["missing_5minute_count"], 1)
        self.assertFalse(report["quality"]["grid"]["complete"])

    def test_counter_decrease_is_reported(self):
        module = load_module()
        start_ms = 1751328000000
        response = statistics_response(
            "sensor.counter",
            [start_ms, start_ms + 300000, start_ms + 600000],
            [100.1, 2.0, 2.1],
            [0.1, 1.9, 0.1],
        )

        report = module.build_export(
            [response],
            entity_map={"grid": {"entity_id": "sensor.counter", "scale_to_kwh": 1.0}},
            start="2025-07-01T00:00:00Z",
            end="2025-07-01T00:15:00Z",
            retrieved_at="2026-09-29T20:00:00Z",
        )

        self.assertEqual(report["quality"]["grid"]["counter_decrease_count"], 1)
        self.assertIn("counter_decrease", report["series"]["grid"][0]["quality_flags"])

    def test_counter_state_delta_overrides_anomalous_reported_change(self):
        module = load_module()
        start_ms = 1751328000000
        response = statistics_response(
            "sensor.counter",
            [
                start_ms - 300000,
                start_ms,
                start_ms + 300000,
                start_ms + 600000,
            ],
            [100.0, 100.1, 100.2, 100.3],
            [0.0, 0.1, 0.1, 100.3],
        )

        report = module.build_export(
            [response],
            entity_map={"grid": {"entity_id": "sensor.counter", "scale_to_kwh": 1.0}},
            start="2025-07-01T00:00:00Z",
            end="2025-07-01T00:15:00Z",
            retrieved_at="2026-09-29T20:00:00Z",
        )

        quarter = report["series"]["grid"][0]
        self.assertEqual(quarter["energy_kwh"], 0.3)
        self.assertIn("reported_change_mismatch", quarter["quality_flags"])
        self.assertEqual(report["quality"]["grid"]["reported_change_mismatch_count"], 1)

    def test_gap_before_complete_quarter_does_not_use_reported_change(self):
        module = load_module()
        start_ms = 1751328000000
        response = statistics_response(
            "sensor.counter",
            [
                start_ms,
                start_ms + 300000,
                start_ms + 600000,
                start_ms + 1800000,
                start_ms + 2100000,
                start_ms + 2400000,
            ],
            [100.1, 100.2, 100.3, 200.0, 200.1, 200.2],
            [0.1, 0.1, 0.1, 99.7, 0.1, 0.1],
        )

        report = module.build_export(
            [response],
            entity_map={"grid": {"entity_id": "sensor.counter", "scale_to_kwh": 1.0}},
            start="2025-07-01T00:00:00Z",
            end="2025-07-01T00:45:00Z",
            retrieved_at="2026-09-30T10:00:00Z",
        )

        quarter_after_gap = report["series"]["grid"][2]
        self.assertIsNone(quarter_after_gap["energy_kwh"])
        self.assertIn("missing_change_value", quarter_after_gap["quality_flags"])

    def test_identical_chunk_seam_row_is_collapsed_without_duplicate_flag(self):
        module = load_module()
        start_ms = 1751328000000
        first = statistics_response(
            "sensor.counter",
            [start_ms - 300000, start_ms, start_ms + 300000],
            [100.0, 100.1, 100.2],
            [0.0, 0.1, 0.1],
        )
        second = statistics_response(
            "sensor.counter",
            [start_ms + 300000, start_ms + 600000],
            [100.2, 100.3],
            [0.1, 0.1],
        )

        report = module.build_export(
            [first, second],
            entity_map={"grid": {"entity_id": "sensor.counter", "scale_to_kwh": 1.0}},
            start="2025-07-01T00:00:00Z",
            end="2025-07-01T00:15:00Z",
            retrieved_at="2026-09-30T10:00:00Z",
        )

        self.assertEqual(report["series"]["grid"][0]["energy_kwh"], 0.3)
        self.assertEqual(report["quality"]["grid"]["duplicate_5minute_count"], 0)
        self.assertNotIn(
            "duplicate_5minute_bucket",
            report["series"]["grid"][0]["quality_flags"],
        )

    def test_hourly_statistics_produce_hourly_intervals(self):
        module = load_module()
        start_ms = 1751328000000
        response = statistics_response(
            "sensor.counter",
            [start_ms - 3600000, start_ms, start_ms + 3600000],
            [100.0, 101.5, 102.0],
            [0.0, 1.5, 0.5],
            period="hour",
        )

        report = module.build_export(
            [response],
            entity_map={"grid": {"entity_id": "sensor.counter", "scale_to_kwh": 1.0}},
            start="2025-07-01T00:00:00Z",
            end="2025-07-01T02:00:00Z",
            retrieved_at="2026-09-30T10:00:00Z",
            source_period="hour",
        )

        self.assertEqual(report["source"]["source_resolution_minutes"], 60)
        self.assertEqual(report["target_resolution_minutes"], 60)
        self.assertEqual(
            [row["energy_kwh"] for row in report["series"]["grid"]],
            [1.5, 0.5],
        )
        self.assertEqual(report["quality"]["grid"]["missing_source_count"], 0)

    def test_transient_counter_spike_is_not_counted_as_energy(self):
        module = load_module()
        start_ms = 1751328000000
        response = statistics_response(
            "sensor.counter",
            [start_ms - 3600000, start_ms, start_ms + 3600000],
            [100.0, 200.0, 100.2],
            [0.0, 100.0, -99.8],
            period="hour",
        )

        report = module.build_export(
            [response],
            entity_map={"pv": {"entity_id": "sensor.counter", "scale_to_kwh": 1.0}},
            start="2025-07-01T00:00:00Z",
            end="2025-07-01T02:00:00Z",
            retrieved_at="2026-09-30T10:00:00Z",
            source_period="hour",
        )

        self.assertIsNone(report["series"]["pv"][0]["energy_kwh"])
        self.assertIn(
            "transient_counter_spike",
            report["series"]["pv"][0]["quality_flags"],
        )
        self.assertEqual(report["quality"]["pv"]["transient_counter_spike_count"], 1)

    def test_recovery_after_transient_counter_drop_is_not_counted_as_energy(self):
        module = load_module()
        start_ms = 1751328000000
        response = statistics_response(
            "sensor.counter",
            [
                start_ms - 3600000,
                start_ms,
                start_ms + 3600000,
                start_ms + 7200000,
            ],
            [100.0, 20.0, 100.1, 100.2],
            [0.0, 20.0, 80.1, 0.1],
            period="hour",
        )

        report = module.build_export(
            [response],
            entity_map={"pv": {"entity_id": "sensor.counter", "scale_to_kwh": 1.0}},
            start="2025-07-01T00:00:00Z",
            end="2025-07-01T03:00:00Z",
            retrieved_at="2026-09-30T10:00:00Z",
            source_period="hour",
        )

        self.assertIsNone(report["series"]["pv"][1]["energy_kwh"])
        self.assertIn(
            "counter_recovery_after_drop",
            report["series"]["pv"][1]["quality_flags"],
        )
        self.assertEqual(
            report["quality"]["pv"]["counter_recovery_after_drop_count"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
