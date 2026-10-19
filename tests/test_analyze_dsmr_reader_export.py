import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_dsmr_reader_export", ROOT / "scripts" / "analyze_dsmr_reader_export.py"
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DsmrReaderExportAnalysisTests(unittest.TestCase):
    def test_quarter_timestamp_jitter_is_normalized_in_utc(self):
        self.assertEqual(
            MODULE.normalize_quarter_start("2026-03-29T03:15:05+02:00"),
            datetime(2026, 3, 29, 1, 15, tzinfo=timezone.utc),
        )

    def test_contiguous_ranges_keep_separate_gaps(self):
        values = [
            datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc),
        ]
        ranges = MODULE.contiguous_ranges(values, timedelta(minutes=15))
        self.assertEqual([item["count"] for item in ranges], [2, 1])

    def test_contract_coverage_reports_overlap_and_gap(self):
        contracts = [
            {"start": "2026-01-01", "end": "2026-01-02"},
            {"start": "2026-01-02", "end": "2026-01-03"},
        ]
        result = MODULE.analyze_contract_coverage(
            contracts,
            start="2026-01-01",
            end="2026-01-05",
        )
        self.assertEqual(result["covered_once_days"], 2)
        self.assertEqual(result["overlapping_days"], ["2026-01-02"])
        self.assertEqual(result["uncovered_days"], ["2026-01-04"])

    def test_historical_tariff_ledger_uses_owner_confirmed_ha_prices_for_2026(self):
        contracts = [
            {
                "start": "2025-12-01",
                "end": "2026-01-31",
                "description": "EcoPower",
                "electricity_delivered_1_price": "0.2500",
                "electricity_delivered_2_price": "0.2500",
                "electricity_returned_1_price": "0.0400",
                "electricity_returned_2_price": "0.0400",
                "fixed_daily_cost": "1.1000",
            },
            {
                "start": "2026-02-01",
                "end": "2026-02-28",
                "description": "EcoPower",
                "electricity_delivered_1_price": "0.2600",
                "electricity_delivered_2_price": "0.2600",
                "electricity_returned_1_price": "0.0410",
                "electricity_returned_2_price": "0.0410",
                "fixed_daily_cost": "1.1000",
            },
        ]
        ha_config = {
            "classification": "OWNER_CONFIRMED_AUTHORITATIVE_FOR_2026_HISTORICAL_MONTHS",
            "values": {"2026-01": 0.2841, "2026-02": 0.2716},
            "usage": {
                "historical_through": "2026-09-30",
                "component_scope_requires_confirmation": True,
                "vat_inclusion_requires_confirmation": True,
            },
        }

        ledger = MODULE.build_historical_tariff_ledger(
            contracts,
            ha_config,
            start="2026-01-01",
            end="2026-03-01",
        )

        self.assertEqual(len(ledger["months"]), 2)
        self.assertEqual(ledger["months"][0]["selected_import_source"], "HA_OWNER_CONFIRMED")
        self.assertEqual(ledger["months"][0]["selected_import_eur_per_kwh"], 0.2841)
        self.assertEqual(ledger["months"][0]["dsmr_import_eur_per_kwh"], 0.25)
        self.assertEqual(ledger["months"][0]["dsmr_export_eur_per_kwh"], 0.04)
        self.assertAlmostEqual(ledger["months"][0]["ha_dsmr_difference_eur_per_kwh"], 0.0341)
        self.assertEqual(ledger["months"][0]["calculation_scope"], "CONFIGURED_ALL_IN_RATE_SENSITIVITY")
        self.assertTrue(ledger["limitations"]["component_scope_requires_confirmation"])

    def test_historical_tariff_ledger_preserves_provider_transition(self):
        contracts = [
            {
                "start": "2024-02-01",
                "end": "2024-02-29",
                "description": "eMobility",
                "electricity_delivered_1_price": "0.327156",
                "electricity_delivered_2_price": "0.327156",
                "electricity_returned_1_price": "0.045920",
                "electricity_returned_2_price": "0.045920",
                "fixed_daily_cost": "1.155300",
            },
            {
                "start": "2024-03-01",
                "end": "2024-03-31",
                "description": "EcoPower",
                "electricity_delivered_1_price": "0.260400",
                "electricity_delivered_2_price": "0.260400",
                "electricity_returned_1_price": "0.075000",
                "electricity_returned_2_price": "0.075000",
                "fixed_daily_cost": "0.920500",
            },
        ]

        ledger = MODULE.build_historical_tariff_ledger(
            contracts,
            {"values": {}, "usage": {}},
            start="2024-02-01",
            end="2024-04-01",
        )

        self.assertEqual(
            [row["provider"] for row in ledger["months"]],
            ["eMobility", "EcoPower"],
        )
        self.assertTrue(all(row["selected_import_source"] == "DSMR" for row in ledger["months"]))


if __name__ == "__main__":
    unittest.main()
