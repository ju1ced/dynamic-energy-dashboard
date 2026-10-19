import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "crosscheck_market_price_samples.py"


def load_module():
    spec = importlib.util.spec_from_file_location("price_crosscheck", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load cross-check module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MarketPriceCrosscheckTests(unittest.TestCase):
    def test_matches_and_mismatches_are_reported_by_local_interval(self):
        module = load_module()
        dataset = {
            "intervals": [
                {
                    "start_local": "2025-10-06T00:00:00+02:00",
                    "price_eur_per_mwh": 33.0,
                },
                {
                    "start_local": "2025-10-06T00:15:00+02:00",
                    "price_eur_per_mwh": 26.11,
                },
            ]
        }
        samples = {
            "source": "official fixture",
            "samples": [
                {
                    "start_local": "2025-10-06T00:00:00+02:00",
                    "price_eur_per_mwh": 33.0,
                },
                {
                    "start_local": "2025-10-06T00:15:00+02:00",
                    "price_eur_per_mwh": 26.12,
                },
            ],
        }

        report = module.crosscheck(dataset, samples)

        self.assertEqual(report["sample_count"], 2)
        self.assertEqual(report["match_count"], 1)
        self.assertEqual(report["mismatch_count"], 1)
        self.assertFalse(report["all_match"])
        self.assertEqual(report["comparisons"][1]["difference_eur_per_mwh"], -0.01)


if __name__ == "__main__":
    unittest.main()
