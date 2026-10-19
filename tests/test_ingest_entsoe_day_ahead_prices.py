import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "ingest_entsoe_day_ahead_prices.py"


def load_module():
    spec = importlib.util.spec_from_file_location("entsoe_prices", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load price ingester from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def market_document(
    resolution: str,
    points: list[tuple[int, str]],
    end: str,
    *,
    curve_type: str = "A01",
) -> str:
    point_xml = "".join(
        f"<Point><position>{position}</position><price.amount>{price}</price.amount></Point>"
        for position, price in points
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0">
  <mRID>document-1</mRID>
  <createdDateTime>2025-05-31T12:42:00Z</createdDateTime>
  <TimeSeries>
    <mRID>series-1</mRID>
    <curveType>{curve_type}</curveType>
    <Period>
      <timeInterval>
        <start>2025-06-01T00:00Z</start>
        <end>{end}</end>
      </timeInterval>
      <resolution>{resolution}</resolution>
      {point_xml}
    </Period>
  </TimeSeries>
</Publication_MarketDocument>
"""


class EntsoeDayAheadPriceTests(unittest.TestCase):
    def test_hourly_prices_expand_to_quarters_without_changing_price(self):
        report = load_module().parse_market_document(
            market_document("PT60M", [(1, "50.25"), (2, "-5.50")], "2025-06-01T02:00Z"),
            retrieved_at="2026-09-29T12:00:00Z",
        )

        self.assertEqual(len(report["intervals"]), 8)
        self.assertEqual(
            [row["price_eur_per_mwh"] for row in report["intervals"]],
            [50.25] * 4 + [-5.5] * 4,
        )
        self.assertEqual(report["intervals"][0]["source_resolution_minutes"], 60)
        self.assertIn("expanded_from_60_minutes", report["intervals"][0]["quality_flags"])
        self.assertEqual(report["quality"]["missing_quarter_count"], 0)
        self.assertTrue(report["quality"]["sequence_complete"])

    def test_native_quarter_prices_preserve_dst_safe_utc_and_local_times(self):
        xml = market_document(
            "PT15M",
            [(1, "10"), (2, "20"), (3, "30"), (4, "40")],
            "2025-06-01T01:00Z",
        )
        report = load_module().parse_market_document(
            xml,
            retrieved_at="2026-09-29T12:00:00Z",
        )

        self.assertEqual(report["intervals"][0]["start_utc"], "2025-06-01T00:00:00+00:00")
        self.assertEqual(report["intervals"][0]["start_local"], "2025-06-01T02:00:00+02:00")
        self.assertEqual(report["intervals"][0]["source_resolution_minutes"], 15)
        self.assertEqual(report["intervals"][0]["quality_flags"], [])

    def test_missing_source_position_is_reported_and_not_filled(self):
        report = load_module().parse_market_document(
            market_document("PT15M", [(1, "10"), (3, "30")], "2025-06-01T01:00Z"),
            retrieved_at="2026-09-29T12:00:00Z",
        )

        self.assertEqual(len(report["intervals"]), 2)
        self.assertEqual(report["quality"]["missing_quarter_count"], 2)
        self.assertFalse(report["quality"]["sequence_complete"])
        self.assertEqual(
            report["quality"]["missing_quarter_starts_utc"],
            ["2025-06-01T00:15:00+00:00", "2025-06-01T00:45:00+00:00"],
        )

    def test_variable_sized_blocks_apply_until_the_next_reported_position(self):
        report = load_module().parse_market_document(
            market_document(
                "PT15M",
                [(1, "10"), (5, "20")],
                "2025-06-01T02:00Z",
                curve_type="A03",
            ),
            retrieved_at="2026-09-29T12:00:00Z",
        )

        self.assertEqual(len(report["intervals"]), 8)
        self.assertEqual(
            [row["price_eur_per_mwh"] for row in report["intervals"]],
            [10.0] * 4 + [20.0] * 4,
        )
        self.assertEqual(report["quality"]["missing_quarter_count"], 0)
        self.assertTrue(report["quality"]["sequence_complete"])
        self.assertIn(
            "expanded_variable_sized_block",
            report["intervals"][1]["quality_flags"],
        )

    def test_requested_utc_window_excludes_api_boundary_expansion(self):
        report = load_module().parse_market_document(
            market_document(
                "PT60M",
                [(1, "10"), (2, "20")],
                "2025-06-01T02:00Z",
            ),
            retrieved_at="2026-09-29T12:00:00Z",
            requested_start="2025-06-01T00:15:00Z",
            requested_end="2025-06-01T01:15:00Z",
        )

        self.assertEqual(
            [row["start_utc"] for row in report["intervals"]],
            [
                "2025-06-01T00:15:00+00:00",
                "2025-06-01T00:30:00+00:00",
                "2025-06-01T00:45:00+00:00",
                "2025-06-01T01:00:00+00:00",
            ],
        )
        self.assertEqual(report["quality"]["expected_quarter_count"], 4)
        self.assertEqual(report["quality"]["missing_quarter_count"], 0)

    def test_document_metadata_is_kept_separate_from_market_issue_time(self):
        report = load_module().parse_market_document(
            market_document("PT15M", [(1, "10")], "2025-06-01T00:15Z"),
            retrieved_at="2026-09-29T12:00:00Z",
        )

        self.assertEqual(report["source"]["document_created_at"], "2025-05-31T12:42:00+00:00")
        self.assertIsNone(report["source"]["market_issue_time"])
        self.assertEqual(report["source"]["retrieved_at"], "2026-09-29T12:00:00+00:00")

    def test_identical_overlapping_timeseries_are_collapsed(self):
        xml = market_document(
            "PT15M",
            [(1, "10"), (2, "20"), (3, "30"), (4, "40")],
            "2025-06-01T01:00Z",
        )
        start = xml.index("  <TimeSeries>")
        end = xml.index("  </TimeSeries>") + len("  </TimeSeries>\n")
        series = xml[start:end]
        xml = xml[:end] + series.replace("series-1", "series-2") + xml[end:]

        report = load_module().parse_market_document(
            xml,
            retrieved_at="2026-10-01T08:00:00Z",
        )

        self.assertEqual(len(report["intervals"]), 4)
        self.assertEqual(report["quality"]["duplicate_quarter_count"], 0)
        self.assertEqual(report["quality"]["collapsed_identical_duplicate_quarter_count"], 4)
        self.assertTrue(report["quality"]["sequence_complete"])
        self.assertIn(
            "collapsed_identical_duplicate",
            report["intervals"][0]["quality_flags"],
        )


if __name__ == "__main__":
    unittest.main()
