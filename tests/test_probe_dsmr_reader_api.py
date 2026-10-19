import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "probe_dsmr_reader_api", ROOT / "scripts" / "probe_dsmr_reader_api.py"
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DsmrReaderApiProbeTests(unittest.TestCase):
    def test_url_builder_omits_empty_parameters(self):
        url = MODULE.build_url(
            "http://example.local/",
            "/api/v2/consumption/electricity",
            {"resolution": "hour", "start": None, "end": "", "limit": 25},
        )
        self.assertEqual(
            url,
            "http://example.local/api/v2/consumption/electricity?resolution=hour&limit=25",
        )

    def test_summary_reports_schema_without_measurement_values(self):
        payload = {
            "count": 1,
            "next": None,
            "results": [{"timestamp": "private", "currently_delivered": 123.4}],
        }
        summary = MODULE.summarize_payload(payload)
        self.assertEqual(summary["total_count"], 1)
        self.assertEqual(summary["record_count"], 1)
        self.assertEqual(summary["record_fields"], ["currently_delivered", "timestamp"])
        self.assertNotIn("private", str(summary))
        self.assertNotIn("123.4", str(summary))

    def test_env_loader_does_not_override_existing_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("DSMR_TEST_VALUE=file\n", encoding="utf-8")
            os.environ["DSMR_TEST_VALUE"] = "runtime"
            try:
                MODULE.load_env_file(path)
                self.assertEqual(os.environ["DSMR_TEST_VALUE"], "runtime")
            finally:
                os.environ.pop("DSMR_TEST_VALUE", None)


if __name__ == "__main__":
    unittest.main()
