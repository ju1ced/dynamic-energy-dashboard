#!/usr/bin/env python3
"""Credential-safe read-only probe for the DSMR Reader v2 API."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = ROOT / ".env"
DEFAULT_ENDPOINT = "/api/v2/consumption/electricity"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def build_url(base_url: str, endpoint: str, params: dict[str, str | int | None]) -> str:
    query = urlencode({key: value for key, value in params.items() if value not in (None, "")})
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    return f"{url}?{query}" if query else url


def summarize_payload(payload: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {"top_level_type": type(payload).__name__}
    if isinstance(payload, dict):
        summary["top_level_keys"] = sorted(payload.keys())
        if isinstance(payload.get("count"), int):
            summary["total_count"] = payload["count"]
        for candidate in ("results", "data"):
            value = payload.get(candidate)
            if isinstance(value, list):
                summary["record_container"] = candidate
                summary["record_count"] = len(value)
                if value and isinstance(value[0], dict):
                    summary["record_fields"] = sorted(value[0].keys())
                break
        pagination = payload.get("next")
        summary["has_next_page"] = bool(pagination)
    elif isinstance(payload, list):
        summary["record_count"] = len(payload)
        if payload and isinstance(payload[0], dict):
            summary["record_fields"] = sorted(payload[0].keys())
    return summary


def fetch_json(url: str, api_key: str, timeout: int = 20) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "X-AUTHKEY": api_key,
            "User-Agent": "dynamic-energy-dashboard-read-only/1",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--base-url")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--resolution", choices=("minute", "hour", "day"))
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    load_env_file(args.env_file)
    base_url = args.base_url or os.getenv("DSMR_READER_BASE_URL", "")
    api_key = os.getenv("DSMR_READER_API_KEY", "")
    if not base_url:
        raise SystemExit("DSMR_READER_BASE_URL is missing")
    if not api_key:
        raise SystemExit("DSMR_READER_API_KEY is missing; add it locally to .env, never to chat")

    url = build_url(
        base_url,
        args.endpoint,
        {"resolution": args.resolution, "start": args.start, "end": args.end, "limit": args.limit},
    )
    try:
        payload = fetch_json(url, api_key)
    except HTTPError as exc:
        raise SystemExit(f"DSMR Reader returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise SystemExit(f"DSMR Reader connection failed: {exc.reason}") from exc

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(summarize_payload(payload), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
