import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "export_dsmr_reader_data", ROOT / "scripts" / "export_dsmr_reader_data.py"
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DsmrReaderExporterTests(unittest.TestCase):
    def test_paginated_export_collects_every_page_once(self):
        pages = {
            "http://dsmr.local/api/v2/statistics/day?limit=2": {
                "count": 3,
                "next": "http://dsmr.local/api/v2/statistics/day?limit=2&offset=2",
                "previous": None,
                "results": [{"id": 1}, {"id": 2}],
            },
            "http://dsmr.local/api/v2/statistics/day?limit=2&offset=2": {
                "count": 3,
                "next": None,
                "previous": "http://dsmr.local/api/v2/statistics/day?limit=2",
                "results": [{"id": 3}],
            },
        }
        requested = []

        def fake_fetch(url, api_key, timeout=20):
            requested.append((url, api_key, timeout))
            return pages[url]

        result = MODULE.fetch_paginated(
            "http://dsmr.local/api/v2/statistics/day?limit=2",
            "secret",
            fetch_page=fake_fetch,
        )

        self.assertEqual(result["declared_count"], 3)
        self.assertEqual(result["record_count"], 3)
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(result["records"], [{"id": 1}, {"id": 2}, {"id": 3}])
        self.assertEqual(len(requested), 2)

    def test_paginated_export_rejects_cross_origin_next_url(self):
        def fake_fetch(url, api_key, timeout=20):
            return {
                "count": 1,
                "next": "http://attacker.invalid/api/v2/statistics/day?offset=1",
                "previous": None,
                "results": [{"id": 1}],
            }

        with self.assertRaisesRegex(ValueError, "origin"):
            MODULE.fetch_paginated(
                "http://dsmr.local/api/v2/statistics/day?limit=1",
                "secret",
                fetch_page=fake_fetch,
            )

    def test_paginated_export_rejects_count_mismatch(self):
        def fake_fetch(url, api_key, timeout=20):
            return {
                "count": 2,
                "next": None,
                "previous": None,
                "results": [{"id": 1}],
            }

        with self.assertRaisesRegex(ValueError, "declared count"):
            MODULE.fetch_paginated(
                "http://dsmr.local/api/v2/statistics/day?limit=2",
                "secret",
                fetch_page=fake_fetch,
            )

    def test_resource_url_uses_resource_specific_time_filters(self):
        electricity = MODULE.build_resource_url(
            "http://dsmr.local",
            "electricity",
            start="2023-10-01T00:00:00+02:00",
            end="2026-10-01T00:00:00+02:00",
            limit=5000,
        )
        prices = MODULE.build_resource_url(
            "http://dsmr.local",
            "energy-supplier-prices",
            start="2023-10-01",
            end="2026-10-01",
            limit=5000,
        )

        self.assertIn("read_at__gte=2023-10-01T00%3A00%3A00%2B02%3A00", electricity)
        self.assertIn("read_at__lte=2026-10-01T00%3A00%3A00%2B02%3A00", electricity)
        self.assertIn("end__gte=2023-10-01", prices)
        self.assertIn("start__lte=2026-10-01", prices)


if __name__ == "__main__":
    unittest.main()
