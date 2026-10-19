#!/usr/bin/env python3
"""Export DSMR Reader v2 resources using read-only paginated GET requests."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = ROOT / ".env"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "raw" / "dsmr-reader-export"

RESOURCE_CONFIG = {
    "electricity": {
        "endpoint": "/api/v2/consumption/electricity",
        "start_filter": "read_at__gte",
        "end_filter": "read_at__lte",
    },
    "energy-supplier-prices": {
        "endpoint": "/api/v2/consumption/energy-supplier-prices",
        "start_filter": "end__gte",
        "end_filter": "start__lte",
    },
    "day-statistics": {
        "endpoint": "/api/v2/statistics/day",
        "start_filter": "day__gte",
        "end_filter": "day__lte",
    },
    "hour-statistics": {
        "endpoint": "/api/v2/statistics/hour",
        "start_filter": "hour_start__gte",
        "end_filter": "hour_start__lte",
    },
    "quarter-hour-peaks": {
        "endpoint": "/api/v2/consumption/quarter-hour-peak-electricity",
        "start_filter": "read_at_start__gte",
        "end_filter": "read_at_start__lte",
    },
}


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_resource_url(
    base_url: str,
    resource: str,
    *,
    start: str | None,
    end: str | None,
    limit: int,
) -> str:
    if resource not in RESOURCE_CONFIG:
        raise ValueError(f"Unsupported DSMR Reader resource: {resource}")
    config = RESOURCE_CONFIG[resource]
    params: dict[str, str | int] = {"limit": limit}
    if start:
        params[str(config["start_filter"])] = start
    if end:
        params[str(config["end_filter"])] = end
    endpoint = str(config["endpoint"])
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}?{urlencode(params)}"


def fetch_json(url: str, api_key: str, timeout: int = 60) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "X-AUTHKEY": api_key,
            "User-Agent": "dynamic-energy-dashboard-read-only/1",
        },
        method="GET",
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    return parsed.scheme, parsed.hostname or "", parsed.port


def fetch_paginated(
    initial_url: str,
    api_key: str,
    *,
    timeout: int = 60,
    fetch_page: Callable[[str, str, int], Any] = fetch_json,
) -> dict[str, Any]:
    expected_origin = origin(initial_url)
    next_url: str | None = initial_url
    visited: set[str] = set()
    records: list[dict[str, Any]] = []
    declared_count: int | None = None
    page_count = 0

    while next_url:
        if origin(next_url) != expected_origin:
            raise ValueError("DSMR Reader pagination next URL changed origin")
        if next_url in visited:
            raise ValueError("DSMR Reader pagination loop detected")
        visited.add(next_url)

        payload = fetch_page(next_url, api_key, timeout)
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ValueError("Unexpected DSMR Reader paginated response schema")
        page_declared_count = payload.get("count")
        if not isinstance(page_declared_count, int):
            raise ValueError("DSMR Reader response does not declare an integer count")
        if declared_count is None:
            declared_count = page_declared_count
        elif page_declared_count != declared_count:
            raise ValueError("DSMR Reader declared count changed during pagination")

        for record in payload["results"]:
            if not isinstance(record, dict):
                raise ValueError("DSMR Reader returned a non-object record")
            records.append(record)
        page_count += 1

        raw_next = payload.get("next")
        next_url = urljoin(next_url, raw_next) if raw_next else None

    if declared_count is None:
        declared_count = 0
    if len(records) != declared_count:
        raise ValueError(
            f"DSMR Reader declared count {declared_count}, exported {len(records)} records"
        )

    return {
        "declared_count": declared_count,
        "record_count": len(records),
        "page_count": page_count,
        "records": records,
    }


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    fields = sorted({key for record in records for key in record})
    return {
        "record_count": len(records),
        "record_fields": fields,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--base-url")
    parser.add_argument(
        "--resource",
        action="append",
        choices=sorted(RESOURCE_CONFIG),
        dest="resources",
        help="Repeat to export multiple resources; defaults to all resources",
    )
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if args.limit <= 0:
        raise SystemExit("--limit must be positive")
    load_env_file(args.env_file)
    base_url = args.base_url or os.getenv("DSMR_READER_BASE_URL", "")
    api_key = os.getenv("DSMR_READER_API_KEY", "")
    if not base_url:
        raise SystemExit("DSMR_READER_BASE_URL is missing")
    if not api_key:
        raise SystemExit("DSMR_READER_API_KEY is missing; keep it in the local .env")

    resources = args.resources or list(RESOURCE_CONFIG)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    run_summary: dict[str, Any] = {
        "schema_version": 1,
        "classification": "PRIVATE_RAW_READ_ONLY_EXPORT",
        "retrieved_at": retrieved_at,
        "requested_start": args.start,
        "requested_end": args.end,
        "resources": {},
    }

    for resource in resources:
        url = build_resource_url(
            base_url,
            resource,
            start=args.start,
            end=args.end,
            limit=args.limit,
        )
        result = fetch_paginated(url, api_key, timeout=args.timeout)
        output = {
            "schema_version": 1,
            "classification": "PRIVATE_RAW_READ_ONLY_EXPORT",
            "source": "DSMR Reader v2 API",
            "resource": resource,
            "retrieved_at": retrieved_at,
            "requested_start": args.start,
            "requested_end": args.end,
            "declared_count": result["declared_count"],
            "page_count": result["page_count"],
            "records": result["records"],
        }
        path = args.output_dir / f"{resource}.json"
        path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        run_summary["resources"][resource] = {
            **summarize_records(result["records"]),
            "declared_count": result["declared_count"],
            "page_count": result["page_count"],
            "output_file": path.name,
        }

    summary_path = args.output_dir / "export-summary.json"
    summary_path.write_text(
        json.dumps(run_summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(run_summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
