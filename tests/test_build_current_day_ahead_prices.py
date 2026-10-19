import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_current_day_ahead_prices",
    ROOT / "scripts" / "build_current_day_ahead_prices.py",
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

TARIFF = {
    "version": "ECOPOWER_DBS_2026-08-01",
    "import_energy": {"market_multiplier": 0.00102, "offset_eur_per_kwh": 0.004},
    "export_energy": {"market_multiplier": 0.00098, "offset_eur_per_kwh": -0.015},
    "green_certificates_eur_per_kwh": 0.011,
    "combined_heat_power_eur_per_kwh": 0.00392,
    "subscription_eur_per_month": 5.0,
    "vat_rate_import": 0.06,
    "vat_rate_private_export": 0.0,
}
REFERENCE = {
    "reference_import_eur_per_kwh_incl_vat": 0.2770,
    "classification": "OWNER_PROVIDED_INDICATIVE_AVERAGE",
}


def price_report():
    rows = []
    for day, prices in (
        ("2026-10-05", (50.0, 100.0)),
        ("2026-10-06", (-10.0, 200.0)),
        ("2026-10-07", (25.0, 75.0)),
    ):
        for hour, price in enumerate(prices):
            rows.append(
                {
                    "start_utc": f"{day}T{hour:02d}:00:00+00:00",
                    "end_utc": f"{day}T{hour:02d}:15:00+00:00",
                    "start_local": f"{day}T{hour + 2:02d}:00:00+02:00",
                    "end_local": f"{day}T{hour + 2:02d}:15:00+02:00",
                    "price_eur_per_mwh": price,
                    "source_resolution_minutes": 15,
                    "quality_flags": [],
                }
            )
    return {
        "schema_version": 1,
        "source": {
            "provider": "ENTSO-E Transparency Platform Web API",
            "retrieved_at": "2026-10-06T08:00:00+00:00",
        },
        "timezone": "Europe/Brussels",
        "target_resolution_minutes": 15,
        "intervals": rows,
        "quality": {
            "missing_quarter_count": 0,
            "duplicate_quarter_count": 0,
            "sequence_complete": True,
        },
    }


class CurrentDayAheadPriceTests(unittest.TestCase):
    def test_active_quarter_remains_in_upcoming_prices(self):
        result = MODULE.build_price_dashboard(
            price_report(),
            tariff=TARIFF,
            reference=REFERENCE,
            now=datetime(2026, 10, 5, 0, 7, tzinfo=timezone.utc),
        )

        self.assertEqual(
            result["upcoming_intervals"][0]["start_utc"],
            "2026-10-05T00:00:00+00:00",
        )

    def test_ecopower_formula_includes_gsc_wkc_and_private_vat(self):
        rate = MODULE.ecopower_import_rate_eur_per_kwh(100.0, TARIFF)
        self.assertAlmostEqual(rate, (0.102 + 0.004 + 0.011 + 0.00392) * 1.06)

    def test_builds_upcoming_intervals_and_reference_comparison(self):
        result = MODULE.build_price_dashboard(
            price_report(),
            tariff=TARIFF,
            reference=REFERENCE,
            now=datetime(2026, 10, 6, 8, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(result["mode"], "READ_ONLY")
        self.assertFalse(result["physical_writes"])
        self.assertEqual(result["tariff_version"], "ECOPOWER_DBS_2026-08-01")
        self.assertEqual(result["reference"]["eur_per_kwh_incl_vat"], 0.277)
        self.assertEqual(len(result["upcoming_intervals"]), 2)
        self.assertEqual(result["upcoming_intervals"][0]["start_local"][:10], "2026-10-07")
        self.assertIn("difference_vs_reference_eur_per_kwh", result["upcoming_intervals"][0])

    def test_requested_window_detects_missing_period_even_when_source_claims_complete(self):
        report = price_report()
        report["source"]["requested_start"] = "2026-10-05T00:00:00+00:00"
        report["source"]["requested_end"] = "2026-10-08T00:00:00+00:00"

        result = MODULE.build_price_dashboard(
            report,
            tariff=TARIFF,
            reference=REFERENCE,
            now=datetime(2026, 10, 6, 8, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(result["quality"]["status"], "PARTIAL")
        self.assertFalse(result["quality"]["requested_window_complete"])
        self.assertGreater(result["quality"]["requested_window_missing_quarter_count"], 0)

    def test_rejects_local_timestamp_that_represents_another_instant(self):
        report = price_report()
        report["intervals"][0]["start_local"] = "2026-10-05T03:00:00+02:00"

        with self.assertRaisesRegex(ValueError, "same instant"):
            MODULE.build_price_dashboard(
                report,
                tariff=TARIFF,
                reference=REFERENCE,
                now=datetime(2026, 10, 6, 8, 30, tzinfo=timezone.utc),
            )

    def test_aggregates_day_week_and_month_without_hiding_partial_periods(self):
        result = MODULE.build_price_dashboard(
            price_report(),
            tariff=TARIFF,
            reference=REFERENCE,
            now=datetime(2026, 10, 6, 8, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(len(result["aggregates"]["daily"]), 3)
        self.assertEqual(len(result["aggregates"]["weekly"]), 1)
        self.assertEqual(len(result["aggregates"]["monthly"]), 1)
        self.assertTrue(result["aggregates"]["weekly"][0]["partial_period"])
        self.assertTrue(result["aggregates"]["monthly"][0]["partial_period"])
        self.assertEqual(result["aggregates"]["daily"][1]["period"], "2026-10-06")

    def test_invalid_or_incomplete_source_is_visible_in_quality(self):
        report = price_report()
        report["quality"]["missing_quarter_count"] = 96
        report["quality"]["sequence_complete"] = False
        result = MODULE.build_price_dashboard(
            report,
            tariff=TARIFF,
            reference=REFERENCE,
            now=datetime(2026, 10, 6, 8, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(result["quality"]["status"], "PARTIAL")
        self.assertEqual(result["quality"]["missing_quarter_count"], 96)
        self.assertFalse(result["quality"]["sequence_complete"])


if __name__ == "__main__":
    unittest.main()
