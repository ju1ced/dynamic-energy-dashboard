import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "analyze_fluvius_quarter_csv.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fluvius_analyzer", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load analyzer module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HEADERS = [
    "Van (datum)",
    "Van (tijdstip)",
    "Tot (datum)",
    "Tot (tijdstip)",
    "EAN-code",
    "Meter",
    "Metertype",
    "Register",
    "Volume",
    "Eenheid",
    "Validatiestatus",
    "Omschrijving",
]


def row(start_date, start_time, end_date, end_time, register, volume, status="Uitgelezen"):
    return [
        start_date,
        start_time,
        end_date,
        end_time,
        '="sensitive-ean"',
        "sensitive-meter",
        "Digitale meter",
        register,
        volume,
        "kWh",
        status,
        "private-description",
    ]


class FluviusQuarterCsvTests(unittest.TestCase):
    def analyze(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(HEADERS)
                writer.writerows(rows)
            return load_module().analyze_csv(path)

    def test_complete_intervals_are_summarized_without_identifiers(self):
        report = self.analyze(
            [
                row("01-06-2025", "00:00:00", "01-06-2025", "00:15:00", "Afname Nacht", "1,250"),
                row("01-06-2025", "00:00:00", "01-06-2025", "00:15:00", "Injectie Nacht", "0,100"),
                row("01-06-2025", "00:15:00", "01-06-2025", "00:30:00", "Afname Nacht", "0,750", "Geschat"),
                row("01-06-2025", "00:15:00", "01-06-2025", "00:30:00", "Injectie Nacht", "0,050", "Geschat"),
            ]
        )

        self.assertEqual(report["interval_count"], 2)
        self.assertTrue(report["sequence_complete"])
        self.assertTrue(report["all_intervals_have_import_and_export"])
        self.assertEqual(report["totals_kwh"], {"import": 2.0, "export": 0.15})
        self.assertEqual(report["estimated_interval_count"], 1)
        self.assertEqual(report["monthly_totals_kwh"]["2025-06"], {"import": 2.0, "export": 0.15})
        serialized = str(report)
        self.assertNotIn("sensitive-ean", serialized)
        self.assertNotIn("sensitive-meter", serialized)
        self.assertNotIn("private-description", serialized)

    def test_blank_volume_is_reported_as_unavailable_instead_of_zero(self):
        report = self.analyze(
            [
                row(
                    "25-04-2024",
                    "16:15:00",
                    "25-04-2024",
                    "16:30:00",
                    "Afname Dag",
                    "",
                    "Geen verbruik",
                ),
                row(
                    "25-04-2024",
                    "16:15:00",
                    "25-04-2024",
                    "16:30:00",
                    "Injectie Dag",
                    "0,100",
                ),
            ]
        )

        self.assertEqual(report["missing_volume_row_count"], 1)
        self.assertEqual(report["unavailable_interval_count"], 1)
        self.assertEqual(report["read_interval_count"], 0)
        self.assertEqual(report["estimated_interval_count"], 0)
        self.assertEqual(report["totals_kwh"], {"export": 0.1})
        self.assertIn("interval_0_has_missing_volume", report["issues"])

    def test_autumn_clock_change_is_canonicalized_when_rows_use_local_clock_order(self):
        intervals = [
            ("01:45:00", "02:00:00"),
            ("02:00:00", "02:15:00"),
            ("02:00:00", "02:15:00"),
            ("02:15:00", "02:30:00"),
            ("02:15:00", "02:30:00"),
            ("02:30:00", "02:45:00"),
            ("02:30:00", "02:45:00"),
            ("02:45:00", "02:00:00"),
            ("02:45:00", "03:00:00"),
            ("03:00:00", "03:15:00"),
        ]
        rows = []
        for start, end in intervals:
            rows.append(row("26-10-2025", start, "26-10-2025", end, "Afname Nacht", "0,100"))
            rows.append(row("26-10-2025", start, "26-10-2025", end, "Injectie Nacht", "0,000"))

        report = self.analyze(rows)

        self.assertEqual(report["interval_count"], 10)
        self.assertTrue(report["sequence_complete"])
        self.assertEqual(report["clock_transition_interval_count"], 1)

    def test_spring_clock_change_is_not_reported_as_missing_data(self):
        intervals = [
            ("01:30:00", "01:45:00"),
            ("01:45:00", "03:00:00"),
            ("03:00:00", "03:15:00"),
        ]
        rows = []
        for start, end in intervals:
            rows.append(row("29-03-2026", start, "29-03-2026", end, "Afname Nacht", "0,100"))
            rows.append(row("29-03-2026", start, "29-03-2026", end, "Injectie Nacht", "0,000"))

        report = self.analyze(rows)

        self.assertEqual(report["interval_count"], 3)
        self.assertTrue(report["sequence_complete"])
        self.assertEqual(report["clock_transition_interval_count"], 1)


if __name__ == "__main__":
    unittest.main()
