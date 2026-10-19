#!/usr/bin/env python3
"""Build a read-only current Ecopower Day-Ahead price dashboard feed."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ZONE = ZoneInfo("Europe/Brussels")
DEFAULT_TARIFF = ROOT / "config" / "tariffs" / "ecopower-dbs-2026-08-01.json"
DEFAULT_REFERENCE = ROOT / "config" / "tariffs" / "shadow-price-reference.json"
DEFAULT_OUTPUT = ROOT / "data" / "raw" / "day-ahead-prices.json"
DEFAULT_RAW_OUTPUT = ROOT / "data" / "raw" / "entsoe-current-day-ahead-prices.json"


def _load_ingest_module() -> Any:
    path = ROOT / "scripts" / "ingest_entsoe_day_ahead_prices.py"
    spec = importlib.util.spec_from_file_location("current_entsoe_ingest", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load ENTSO-E ingester")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INGEST = _load_ingest_module()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def parse_instant(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an offset-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an offset-aware timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be an offset-aware timestamp")
    return parsed


def finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be a finite number")
    return result


def ecopower_import_rate_eur_per_kwh(
    market_price_eur_per_mwh: float, tariff: dict[str, Any]
) -> float:
    import_energy = tariff["import_energy"]
    excl_vat = (
        finite_number(market_price_eur_per_mwh, "market_price_eur_per_mwh")
        * finite_number(import_energy["market_multiplier"], "market_multiplier")
        + finite_number(import_energy["offset_eur_per_kwh"], "import offset")
        + finite_number(
            tariff["green_certificates_eur_per_kwh"], "green certificates"
        )
        + finite_number(
            tariff["combined_heat_power_eur_per_kwh"], "combined heat power"
        )
    )
    return excl_vat * (1 + finite_number(tariff["vat_rate_import"], "import VAT"))


def ecopower_export_rate_eur_per_kwh(
    market_price_eur_per_mwh: float, tariff: dict[str, Any]
) -> float:
    export_energy = tariff["export_energy"]
    excl_vat = (
        finite_number(market_price_eur_per_mwh, "market_price_eur_per_mwh")
        * finite_number(export_energy["market_multiplier"], "export multiplier")
        + finite_number(export_energy["offset_eur_per_kwh"], "export offset")
    )
    return excl_vat * (
        1 + finite_number(tariff["vat_rate_private_export"], "private export VAT")
    )


def _iso_week(local_instant: datetime) -> str:
    iso_year, iso_week, _ = local_instant.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _aggregate(
    intervals: list[dict[str, Any]],
    key: Callable[[datetime], str],
    *,
    expected_intervals: Callable[[str], int | None],
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in intervals:
        buckets[key(parse_instant(row["start_local"], "start_local"))].append(row)

    output = []
    for period, rows in sorted(buckets.items()):
        rates = [float(row["ecopower_import_eur_per_kwh_incl_vat"]) for row in rows]
        reference = float(rows[0]["reference_eur_per_kwh_incl_vat"])
        average = sum(rates) / len(rates)
        expected = expected_intervals(period)
        output.append(
            {
                "period": period,
                "interval_count": len(rows),
                "expected_interval_count": expected,
                "partial_period": expected is None or len(rows) != expected,
                "average_eur_per_kwh_incl_vat": round(average, 6),
                "minimum_eur_per_kwh_incl_vat": round(min(rates), 6),
                "maximum_eur_per_kwh_incl_vat": round(max(rates), 6),
                "difference_vs_reference_eur_per_kwh": round(average - reference, 6),
                "difference_vs_reference_percent": round(
                    (average / reference - 1) * 100, 3
                ),
                "below_reference_interval_count": sum(rate < reference for rate in rates),
                "negative_market_interval_count": sum(
                    float(row["market_price_eur_per_mwh"]) < 0 for row in rows
                ),
            }
        )
    return output


def _expected_day_intervals(period: str) -> int:
    day = date.fromisoformat(period)
    start = datetime.combine(day, time.min, tzinfo=ZONE).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=ZONE).astimezone(
        timezone.utc
    )
    return int((end - start).total_seconds() // 900)


def _expected_week_intervals(period: str) -> int:
    iso_year_text, iso_week_text = period.split("-W")
    day = date.fromisocalendar(int(iso_year_text), int(iso_week_text), 1)
    start = datetime.combine(day, time.min, tzinfo=ZONE).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=7), time.min, tzinfo=ZONE).astimezone(
        timezone.utc
    )
    return int((end - start).total_seconds() // 900)


def _expected_month_intervals(period: str) -> int:
    year, month = (int(part) for part in period.split("-"))
    start_day = date(year, month, 1)
    end_day = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    start = datetime.combine(start_day, time.min, tzinfo=ZONE).astimezone(timezone.utc)
    end = datetime.combine(end_day, time.min, tzinfo=ZONE).astimezone(timezone.utc)
    return int((end - start).total_seconds() // 900)


def build_price_dashboard(
    price_report: dict[str, Any],
    *,
    tariff: dict[str, Any],
    reference: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not isinstance(price_report, dict) or not isinstance(
        price_report.get("intervals"), list
    ):
        raise ValueError("price report must contain an intervals list")

    reference_rate = finite_number(
        reference["reference_import_eur_per_kwh_incl_vat"],
        "reference import rate",
    )
    if reference_rate <= 0:
        raise ValueError("reference import rate must be positive")

    intervals: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in price_report["intervals"]:
        if not isinstance(source, dict):
            raise ValueError("price interval must be an object")
        start = parse_instant(source.get("start_utc"), "start_utc").astimezone(
            timezone.utc
        )
        end = parse_instant(source.get("end_utc"), "end_utc").astimezone(timezone.utc)
        source_local_start = parse_instant(source.get("start_local"), "start_local")
        if source_local_start.astimezone(timezone.utc) != start:
            raise ValueError("start_local and start_utc must represent the same instant")
        local_start = source_local_start.astimezone(ZONE)
        if end - start != timedelta(minutes=15):
            raise ValueError("price interval must last exactly 15 minutes")
        key = start.isoformat()
        if key in seen:
            raise ValueError(f"duplicate interval: {key}")
        seen.add(key)
        market = finite_number(source.get("price_eur_per_mwh"), "market price")
        import_rate = ecopower_import_rate_eur_per_kwh(market, tariff)
        export_rate = ecopower_export_rate_eur_per_kwh(market, tariff)
        intervals.append(
            {
                "start_utc": start.isoformat(),
                "end_utc": end.isoformat(),
                "start_local": local_start.isoformat(),
                "market_price_eur_per_mwh": market,
                "ecopower_import_eur_per_kwh_incl_vat": round(import_rate, 6),
                "ecopower_export_eur_per_kwh": round(export_rate, 6),
                "reference_eur_per_kwh_incl_vat": reference_rate,
                "difference_vs_reference_eur_per_kwh": round(
                    import_rate - reference_rate, 6
                ),
                "difference_vs_reference_percent": round(
                    (import_rate / reference_rate - 1) * 100, 3
                ),
                "source_resolution_minutes": source.get("source_resolution_minutes"),
                "quality_flags": source.get("quality_flags", []),
            }
        )
    intervals.sort(key=lambda row: row["start_utc"])

    source = price_report.get("source", {})
    if not isinstance(source, dict):
        raise ValueError("price report source must be an object")
    retrieved_at = parse_instant(source.get("retrieved_at"), "source.retrieved_at")
    source_quality = price_report.get("quality", {})
    missing_count = int(source_quality.get("missing_quarter_count", 0))
    duplicate_count = int(source_quality.get("duplicate_quarter_count", 0))
    sequence_complete = bool(source_quality.get("sequence_complete", False))
    requested_start_value = source.get("requested_start")
    requested_end_value = source.get("requested_end")
    if (requested_start_value is None) != (requested_end_value is None):
        raise ValueError("requested_start and requested_end must be provided together")
    requested_window_complete: bool | None = None
    requested_window_missing_count = 0
    requested_start: datetime | None = None
    requested_end: datetime | None = None
    if requested_start_value is not None and requested_end_value is not None:
        requested_start = parse_instant(
            requested_start_value, "source.requested_start"
        ).astimezone(timezone.utc)
        requested_end = parse_instant(
            requested_end_value, "source.requested_end"
        ).astimezone(timezone.utc)
        if requested_end <= requested_start:
            raise ValueError("source.requested_end must be after source.requested_start")
        duration_seconds = (requested_end - requested_start).total_seconds()
        if duration_seconds % 900:
            raise ValueError("requested window must align to quarter-hour intervals")
        expected_starts = {
            requested_start + timedelta(minutes=15 * index)
            for index in range(int(duration_seconds // 900))
        }
        available_starts = {
            parse_instant(row["start_utc"], "start_utc").astimezone(timezone.utc)
            for row in intervals
            if requested_start
            <= parse_instant(row["start_utc"], "start_utc").astimezone(timezone.utc)
            < requested_end
        }
        requested_window_missing_count = len(expected_starts - available_starts)
        requested_window_complete = requested_window_missing_count == 0

    stale = now_utc - retrieved_at.astimezone(timezone.utc) > timedelta(hours=36)
    upcoming = [
        row
        for row in intervals
        if parse_instant(row["end_utc"], "end_utc").astimezone(timezone.utc)
        > now_utc
    ]
    quality_status = (
        "STALE"
        if stale
        else "COMPLETE"
        if sequence_complete
        and missing_count == 0
        and duplicate_count == 0
        and requested_window_complete is not False
        else "PARTIAL"
    )

    daily = _aggregate(
        intervals,
        lambda instant: instant.date().isoformat(),
        expected_intervals=_expected_day_intervals,
    )
    weekly = _aggregate(
        intervals,
        _iso_week,
        expected_intervals=_expected_week_intervals,
    )
    monthly = _aggregate(
        intervals,
        lambda instant: instant.strftime("%Y-%m"),
        expected_intervals=_expected_month_intervals,
    )

    return {
        "schema_version": 1,
        "generated_at": now_utc.isoformat(),
        "mode": "READ_ONLY",
        "classification": "INDICATIVE_PRICE_SIGNAL_NOT_INVOICE",
        "physical_writes": False,
        "home_assistant_writes": False,
        "source": {
            "provider": source.get("provider"),
            "retrieved_at": retrieved_at.astimezone(timezone.utc).isoformat(),
            "requested_start": requested_start.isoformat() if requested_start else None,
            "requested_end": requested_end.isoformat() if requested_end else None,
            "timezone": price_report.get("timezone", "Europe/Brussels"),
        },
        "tariff_version": tariff["version"],
        "formula": {
            "import": "((market_EUR_per_MWh * 0.00102) + 0.004 + GSC + WKK) * (1 + VAT)",
            "subscription_eur_per_month_excl_vat": tariff[
                "subscription_eur_per_month"
            ],
            "excluded_from_interval_comparison": [
                "network tariffs",
                "capacity tariff",
                "excise and energy fund",
                "monthly subscription allocation",
            ],
        },
        "reference": {
            "eur_per_kwh_incl_vat": reference_rate,
            "classification": reference["classification"],
            "comparison_limit": reference.get("comparison_limit"),
        },
        "coverage": {
            "start_local": intervals[0]["start_local"] if intervals else None,
            "end_local": intervals[-1]["start_local"] if intervals else None,
            "interval_count": len(intervals),
            "upcoming_interval_count": len(upcoming),
        },
        "quality": {
            "status": quality_status,
            "stale": stale,
            "missing_quarter_count": missing_count,
            "duplicate_quarter_count": duplicate_count,
            "sequence_complete": sequence_complete,
            "requested_window_complete": requested_window_complete,
            "requested_window_missing_quarter_count": requested_window_missing_count,
        },
        "upcoming_intervals": upcoming,
        "aggregates": {
            "daily": daily,
            "weekly": weekly,
            "monthly": monthly,
        },
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def fetch_price_report(
    *, history_days: int, future_days: int, token_env: str
) -> dict[str, Any]:
    if history_days < 0 or future_days < 1:
        raise ValueError("history-days must be non-negative and future-days positive")
    token = os.environ.get(token_env, "")
    if not token:
        raise ValueError(f"missing required environment variable: {token_env}")
    today = datetime.now(ZONE).date()
    start_local = datetime.combine(
        today - timedelta(days=history_days), time.min, tzinfo=ZONE
    )
    end_local = datetime.combine(today + timedelta(days=future_days), time.min, tzinfo=ZONE)
    start = start_local.astimezone(timezone.utc)
    end = end_local.astimezone(timezone.utc)
    xml_text = INGEST.fetch_market_document(start, end, token)
    return INGEST.parse_market_document(
        xml_text,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        requested_start=start.isoformat(),
        requested_end=end.isoformat(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fetch", action="store_true")
    source.add_argument("--input", type=Path)
    parser.add_argument("--history-days", type=int, default=35)
    parser.add_argument("--future-days", type=int, default=2)
    parser.add_argument("--token-env", default="ENTSOE_SECURITY_TOKEN")
    parser.add_argument("--tariff", type=Path, default=DEFAULT_TARIFF)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = (
        fetch_price_report(
            history_days=args.history_days,
            future_days=args.future_days,
            token_env=args.token_env,
        )
        if args.fetch
        else load_json(args.input)
    )
    if args.fetch:
        atomic_write_json(args.raw_output, report)
    payload = build_price_dashboard(
        report,
        tariff=load_json(args.tariff),
        reference=load_json(args.reference),
    )
    atomic_write_json(args.output, payload)
    print(
        json.dumps(
            {
                "quality": payload["quality"]["status"],
                "interval_count": payload["coverage"]["interval_count"],
                "upcoming_interval_count": payload["coverage"][
                    "upcoming_interval_count"
                ],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
