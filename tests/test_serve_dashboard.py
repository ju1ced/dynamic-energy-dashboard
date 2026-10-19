import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "serve_dashboard", ROOT / "scripts" / "serve_dashboard.py"
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def plan_report(*, expired=False):
    if expired:
        start = "2000-01-01T00:00:00+00:00"
        second = "2000-01-01T00:15:00+00:00"
        end = "2000-01-01T00:30:00+00:00"
        target = "2000-01-01"
    else:
        start = "2099-01-01T00:00:00+00:00"
        second = "2099-01-01T00:15:00+00:00"
        end = "2099-01-01T00:30:00+00:00"
        target = "2099-01-01"
    schedule = [
        {
            "start_utc": start,
            "duration_hours": 0.25,
            "action": "HOLD",
            "reason": "No action",
            "planned_grid_import_kw": 0.2,
        },
        {
            "start_utc": second,
            "duration_hours": 0.25,
            "action": "HOLD",
            "reason": "No action",
            "planned_grid_import_kw": 0.2,
        },
    ]
    return {
        "mode": "READ_ONLY_SHADOW",
        "classification": "PROPOSED_PLAN_NO_CONTROL",
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "status": "PLANNED",
        "reason": "SHADOW_PLAN_READY",
        "target_date": target,
        "target_start_utc": start,
        "target_end_utc": end,
        "generated_at": start,
        "interval_count": 2,
        "selected_policy_id": "cap_7_kw",
        "plans": [{"id": "cap_7_kw", "status": "PLANNED", "schedule": schedule}],
    }


def price_feed():
    return {
        "mode": "READ_ONLY",
        "physical_writes": False,
        "home_assistant_writes": False,
        "source": {
            "provider": "ENTSO-E Transparency Platform Web API",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        },
        "tariff_version": "ECOPOWER_DBS_2026-08-01",
        "reference": {"eur_per_kwh_incl_vat": 0.277},
        "quality": {"stale": False, "sequence_complete": True},
        "upcoming_intervals": [
            {
                "start_utc": "2099-01-01T00:00:00+00:00",
                "end_utc": "2099-01-01T00:15:00+00:00",
                "market_price_eur_per_mwh": 50.0,
                "ecopower_import_eur_per_kwh_incl_vat": 0.071,
                "ecopower_export_eur_per_kwh": 0.034,
            }
        ],
        "aggregates": {
            "daily": [
                {
                    "period": "2099-01-01",
                    "interval_count": 1,
                    "expected_interval_count": 96,
                    "partial_period": True,
                    "average_eur_per_kwh_incl_vat": 0.071,
                    "difference_vs_reference_eur_per_kwh": -0.206,
                }
            ],
            "weekly": [
                {
                    "period": "2099-W01",
                    "interval_count": 1,
                    "expected_interval_count": 672,
                    "partial_period": True,
                    "average_eur_per_kwh_incl_vat": 0.071,
                    "difference_vs_reference_eur_per_kwh": -0.206,
                }
            ],
            "monthly": [
                {
                    "period": "2099-01",
                    "interval_count": 1,
                    "expected_interval_count": 2976,
                    "partial_period": True,
                    "average_eur_per_kwh_incl_vat": 0.071,
                    "difference_vs_reference_eur_per_kwh": -0.206,
                }
            ],
        },
    }


class DashboardServerTests(unittest.TestCase):
    def test_shadow_plan_endpoint_rechecks_expiry_on_every_request(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            dashboard_root = workspace / "dashboard"
            plan_directory = workspace / "raw"
            dashboard_root.mkdir()
            plan_directory.mkdir()
            price_path = dashboard_root / "data" / "day-ahead-prices.json"
            price_path.parent.mkdir()
            price_path.write_text(json.dumps(price_feed()), encoding="utf-8")
            plan_path = plan_directory / "shadow-controller-plan-current.json"
            plan_path.write_text(json.dumps(plan_report()), encoding="utf-8")

            handler = MODULE.make_handler(dashboard_root, plan_directory, price_path)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            try:
                with urllib.request.urlopen(
                    f"{base_url}/data/shadow-plan.json", timeout=5
                ) as response:
                    active = json.load(response)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")

                plan_path.write_text(
                    json.dumps(plan_report(expired=True)), encoding="utf-8"
                )
                with urllib.request.urlopen(
                    f"{base_url}/data/shadow-plan.json", timeout=5
                ) as response:
                    expired = json.load(response)

                plan_path.write_text("[]", encoding="utf-8")
                with urllib.request.urlopen(
                    f"{base_url}/data/shadow-plan.json", timeout=5
                ) as response:
                    malformed = json.load(response)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(active["state"], "PLANNED")
        self.assertEqual(len(active["schedule"]), 2)
        self.assertEqual(len(active["prices"]), 1)
        self.assertEqual(active["prices"][0]["import_eur_per_kwh"], 0.071)
        self.assertEqual(expired["state"], "NO_ACTION")
        self.assertEqual(expired["reason"], "PLAN_EXPIRED")
        self.assertEqual(expired["schedule"], [])
        self.assertEqual(malformed["state"], "NO_ACTION")
        self.assertEqual(malformed["reason"], "PLAN_UNAVAILABLE")
        self.assertEqual(malformed["schedule"], [])

    def test_day_course_endpoint_validates_parameters_and_reports_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            dashboard_root = workspace / "dashboard"
            plan_directory = workspace / "raw"
            dashboard_root.mkdir()
            plan_directory.mkdir()
            price_path = dashboard_root / "day-ahead-prices.json"
            handler = MODULE.make_handler(dashboard_root, plan_directory, price_path)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}/data/day-course.json"
            statuses = {}
            try:
                for name, query in (
                    ("invalid", "?max_grid_import_kw=banana"),
                    ("unavailable", ""),
                ):
                    try:
                        urllib.request.urlopen(base_url + query, timeout=5)
                    except urllib.error.HTTPError as error:
                        statuses[name] = (error.code, json.load(error))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(statuses["invalid"][0], 400)
        self.assertEqual(statuses["invalid"][1]["errors"], ["MAX_GRID_IMPORT_KW_INVALID"])
        self.assertEqual(statuses["unavailable"][0], 503)
        self.assertEqual(statuses["unavailable"][1]["status"], "PLAN_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
