#!/usr/bin/env python3
"""Serve the static dashboard read-only on a local or LAN interface."""

from __future__ import annotations

import argparse
import importlib.util
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = ROOT / "web-dashboard"
SHADOW_PLAN_DIRECTORY = ROOT / "data" / "raw"
DAY_AHEAD_PRICE_PATH = DASHBOARD_ROOT / "data" / "day-ahead-prices.json"


def _load_shadow_feed_module():
    path = ROOT / "scripts" / "build_shadow_plan_feed.py"
    spec = importlib.util.spec_from_file_location("dashboard_shadow_plan_feed", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load shadow-plan feed helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHADOW_FEED = _load_shadow_feed_module()



class DashboardHandler(SimpleHTTPRequestHandler):
    shadow_plan_directory = SHADOW_PLAN_DIRECTORY
    day_ahead_price_path = DAY_AHEAD_PRICE_PATH

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - inherited HTTP method name
        path = urlsplit(self.path).path
        if path == "/healthz":
            self._send_json({"status": "ok", "mode": "READ_ONLY"})
            return
        if path == "/data/shadow-plan.json":
            try:
                payload = SHADOW_FEED.build_latest_plan_entity_payload(
                    self.shadow_plan_directory,
                    price_feed=json.loads(
                        self.day_ahead_price_path.read_text(encoding="utf-8")
                    ),
                )
            except (OSError, ValueError, json.JSONDecodeError):
                payload = SHADOW_FEED.unavailable_plan_entity_payload(
                    "PLAN_UNAVAILABLE"
                )
            self._send_json(payload)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
        super().end_headers()

    def log_message(self, format, *args):
        print(f"dashboard: {self.address_string()} - {format % args}")


def make_handler(
    dashboard_root: Path = DASHBOARD_ROOT,
    shadow_plan_directory: Path = SHADOW_PLAN_DIRECTORY,
    day_ahead_price_path: Path = DAY_AHEAD_PRICE_PATH,
):
    class ConfiguredDashboardHandler(DashboardHandler):
        pass

    ConfiguredDashboardHandler.shadow_plan_directory = shadow_plan_directory
    ConfiguredDashboardHandler.day_ahead_price_path = day_ahead_price_path
    return lambda *handler_args, **handler_kwargs: ConfiguredDashboardHandler(
        *handler_args,
        directory=str(dashboard_root),
        **handler_kwargs,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()

    if not (DASHBOARD_ROOT / "data" / "dashboard-data.json").exists():
        raise SystemExit("dashboard data missing; run scripts/build_dashboard_data.py first")

    handler = make_handler()
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"read-only dashboard listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
