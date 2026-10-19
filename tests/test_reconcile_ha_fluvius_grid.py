import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "reconcile_ha_fluvius_grid.py"


def load_module():
    spec = importlib.util.spec_from_file_location("grid_reconciliation", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load reconciliation module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ha_row(start, energy):
    return {
        "start_utc": start,
        "end_utc": start.replace(":00:00Z", ":00:00Z"),
        "energy_kwh": energy,
        "quality_flags": [] if energy is not None else ["missing_source_bucket"],
    }


class GridReconciliationTests(unittest.TestCase):
    def test_estimated_fluvius_hours_remain_separately_classified(self):
        module = load_module()
        ha_export = {
            "series": {
                "grid_import": [
                    ha_row("2026-01-22T00:00:00Z", 1.0),
                    ha_row("2026-01-22T01:00:00Z", 2.0),
                ],
                "grid_export": [
                    ha_row("2026-01-22T00:00:00Z", 0.2),
                    ha_row("2026-01-22T01:00:00Z", 0.4),
                ],
            }
        }
        fluvius = []
        for hour, import_total, export_total, estimated in (
            (0, 1.2, 0.1, False),
            (1, 1.8, 0.5, True),
        ):
            for quarter in range(4):
                fluvius.append(
                    {
                        "start_utc": f"2026-01-22T{hour:02d}:{quarter * 15:02d}:00Z",
                        "import_kwh": import_total / 4,
                        "export_kwh": export_total / 4,
                        "estimated": estimated,
                    }
                )

        report = module.reconcile_grid_data(ha_export, fluvius)

        self.assertEqual(report["overlap"]["expected_hour_count"], 2)
        self.assertEqual(report["overlap"]["comparable_hour_count"], 2)
        self.assertEqual(report["overlap"]["estimated_fluvius_hour_count"], 1)
        self.assertEqual(report["all_comparable"]["import"]["ha_total_kwh"], 3.0)
        self.assertEqual(report["all_comparable"]["import"]["fluvius_total_kwh"], 3.0)
        self.assertEqual(report["read_only"]["import"]["ha_total_kwh"], 1.0)
        self.assertEqual(report["read_only"]["import"]["fluvius_total_kwh"], 1.2)

    def test_missing_ha_hour_is_excluded_not_zero_filled(self):
        module = load_module()
        ha_export = {
            "series": {
                "grid_import": [ha_row("2026-01-22T00:00:00Z", None)],
                "grid_export": [ha_row("2026-01-22T00:00:00Z", 0.0)],
            }
        }
        fluvius = [
            {
                "start_utc": f"2026-01-22T00:{quarter * 15:02d}:00Z",
                "import_kwh": 0.25,
                "export_kwh": 0.0,
                "estimated": False,
            }
            for quarter in range(4)
        ]

        report = module.reconcile_grid_data(ha_export, fluvius)

        self.assertEqual(report["overlap"]["expected_hour_count"], 1)
        self.assertEqual(report["overlap"]["comparable_hour_count"], 0)
        self.assertEqual(report["overlap"]["ha_unusable_hour_count"], 1)
        self.assertEqual(report["all_comparable"]["import"]["ha_total_kwh"], 0.0)


if __name__ == "__main__":
    unittest.main()
