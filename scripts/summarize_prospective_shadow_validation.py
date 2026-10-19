#!/usr/bin/env python3
"""Summarize the privacy-safe prospective shadow-validation cohort."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STRATA = [
    "winter_weekday",
    "summer_high_pv_weekday",
    "weekend",
    "negative_price_day",
    "high_load_ev_day",
    "ordinary_shoulder_weekday",
]


def parse_instant(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an offset-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an offset-aware timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be an offset-aware timestamp")
    return parsed.astimezone(timezone.utc)


def finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be finite")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _by_date(rows: list[dict[str, Any]], kind: str) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{kind} rows must be objects")
        target_date = row.get("target_date")
        if not isinstance(target_date, str):
            raise ValueError(f"{kind}.target_date must be a string")
        if target_date in output:
            raise ValueError(f"duplicate {kind} target_date: {target_date}")
        output[target_date] = row
    return output


def _plan_quality_flags(plan: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if plan.get("status") != "PLANNED":
        flags.append("SOURCE_PLAN_NOT_PLANNED")
    if plan.get("capture_quality") != "ACCEPTED_PROSPECTIVE_DAY":
        flags.append("SOURCE_CAPTURE_NOT_ACCEPTED")
    for field in (
        "physical_writes",
        "home_assistant_writes",
        "sma_writes",
        "smappee_writes",
    ):
        if plan.get(field) is not False:
            flags.append(f"INVALID_READ_ONLY_FLAG:{field}")
    try:
        generated_at = parse_instant(plan.get("generated_at"), "generated_at")
        target_start = parse_instant(plan.get("target_start_utc"), "target_start_utc")
        if generated_at >= target_start:
            flags.append("PLAN_GENERATED_AFTER_TARGET_START")
    except ValueError:
        flags.append("INVALID_SOURCE_PLAN_TIMESTAMPS")
    return sorted(set(flags))


def _settlement_quality_flags(settlement: dict[str, Any] | None) -> list[str]:
    if settlement is None:
        return ["SETTLEMENT_PENDING"]
    flags = []
    if settlement.get("status") != "SETTLED":
        flags.append("SOURCE_SETTLEMENT_NOT_SETTLED")
    if settlement.get("quality") != "ACCEPTED_PROSPECTIVE_DAY":
        flags.append("SOURCE_SETTLEMENT_NOT_ACCEPTED")
    if settlement.get("mode") != "READ_ONLY_SHADOW_SETTLEMENT":
        flags.append("INVALID_SETTLEMENT_MODE")
    if (
        settlement.get("classification")
        != "AFTER_THE_FACT_EXECUTION_SCORE_NO_CONTROL"
    ):
        flags.append("INVALID_SETTLEMENT_CLASSIFICATION")
    for field in (
        "physical_writes",
        "home_assistant_writes",
        "sma_writes",
        "smappee_writes",
    ):
        if settlement.get(field) is not False:
            flags.append(f"INVALID_READ_ONLY_FLAG:{field}")
    source_flags = settlement.get("quality_flags", [])
    if not isinstance(source_flags, list):
        flags.append("INVALID_SETTLEMENT_QUALITY_FLAGS")
    elif source_flags:
        flags.extend(str(value) for value in source_flags)
    return sorted(set(flags))


def build_cohort_report(
    plans: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    assignments: dict[str, str],
    *,
    strata: list[str] | None = None,
    required_per_stratum: int = 2,
) -> dict[str, Any]:
    strata = list(strata or DEFAULT_STRATA)
    if len(strata) != len(set(strata)) or not strata:
        raise ValueError("strata must be a non-empty unique list")
    if required_per_stratum <= 0:
        raise ValueError("required_per_stratum must be positive")
    unknown = sorted(set(assignments.values()) - set(strata))
    if unknown:
        raise ValueError(f"unknown cohort strata: {', '.join(unknown)}")

    plans_by_date = _by_date(plans, "plan")
    settlements_by_date = _by_date(settlements, "settlement")
    qualifying_by_stratum: dict[str, list[str]] = {name: [] for name in strata}
    rejected_days = []
    pending_days = []
    qualifying_dates = []
    policy_totals: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {
            "day_count": 0,
            "forecast_cost_eur": 0.0,
            "forecast_saving_eur": 0.0,
            "executed_cost_eur": 0.0,
            "executed_saving_eur": 0.0,
            "baseline_actual_cost_eur": 0.0,
        }
    )
    error_totals = {
        "load_mae_kwh": 0.0,
        "pv_mae_kwh": 0.0,
        "base_net_mae_kwh": 0.0,
    }

    for target_date in sorted(plans_by_date):
        plan = plans_by_date[target_date]
        plan_flags = _plan_quality_flags(plan)
        if plan_flags:
            rejected_days.append(
                {"target_date": target_date, "quality_flags": plan_flags}
            )
            continue

        settlement = settlements_by_date.get(target_date)
        settlement_flags = _settlement_quality_flags(settlement)
        if settlement_flags == ["SETTLEMENT_PENDING"]:
            pending_days.append(
                {"target_date": target_date, "reason": "SETTLEMENT_PENDING"}
            )
            continue
        if settlement_flags:
            rejected_days.append(
                {"target_date": target_date, "quality_flags": settlement_flags}
            )
            continue

        stratum = assignments.get(target_date)
        if stratum is None:
            pending_days.append(
                {"target_date": target_date, "reason": "PRIMARY_STRATUM_UNASSIGNED"}
            )
            continue

        assert settlement is not None
        qualifying_dates.append(target_date)
        qualifying_by_stratum[stratum].append(target_date)
        forecast_error = settlement.get("forecast_error")
        if not isinstance(forecast_error, dict):
            raise ValueError(f"missing forecast_error for {target_date}")
        for field in error_totals:
            error_totals[field] += finite_number(
                forecast_error.get(field), f"forecast_error.{field}"
            )
        policies = settlement.get("plans")
        if not isinstance(policies, list):
            raise ValueError(f"settlement plans must be a list for {target_date}")
        for policy in policies:
            if not isinstance(policy, dict) or policy.get("status") != "SETTLED":
                continue
            policy_id = policy.get("id")
            if not isinstance(policy_id, str):
                raise ValueError(f"settlement policy id must be a string for {target_date}")
            totals = policy_totals[policy_id]
            totals["day_count"] = int(totals["day_count"]) + 1
            for field in (
                "forecast_cost_eur",
                "forecast_saving_eur",
                "executed_cost_eur",
                "executed_saving_eur",
                "baseline_actual_cost_eur",
            ):
                totals[field] = float(totals[field]) + finite_number(
                    policy.get(field), f"plans.{policy_id}.{field}"
                )

    qualifying_count = len(qualifying_dates)
    required_days = len(strata) * required_per_stratum
    strata_report = {
        name: {
            "required_day_count": required_per_stratum,
            "qualifying_day_count": len(qualifying_by_stratum[name]),
            "remaining_day_count": max(
                0, required_per_stratum - len(qualifying_by_stratum[name])
            ),
            "qualifying_dates": qualifying_by_stratum[name],
        }
        for name in strata
    }
    complete = all(
        row["qualifying_day_count"] >= required_per_stratum
        for row in strata_report.values()
    )
    divisor = qualifying_count or 1

    return {
        "schema_version": 1,
        "mode": "READ_ONLY_SHADOW_VALIDATION_COHORT",
        "classification": "PROSPECTIVE_MULTI_DAY_EVIDENCE_NO_CONTROL",
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "status": "COMPLETE" if complete else "IN_PROGRESS",
        "required_day_count": required_days,
        "qualifying_day_count": qualifying_count,
        "remaining_day_count": sum(
            row["remaining_day_count"] for row in strata_report.values()
        ),
        "captured_plan_count": len(plans_by_date),
        "settlement_summary_count": len(settlements_by_date),
        "qualifying_dates": qualifying_dates,
        "pending_days": pending_days,
        "rejected_days": rejected_days,
        "strata": strata_report,
        "forecast_error_mean": {
            field: error_totals[field] / divisor if qualifying_count else None
            for field in error_totals
        },
        "policy_aggregates": {
            policy_id: values for policy_id, values in sorted(policy_totals.items())
        },
        "privacy": {
            "quarter_household_profile_included": False,
            "device_identifiers_included": False,
        },
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_matching(directory: Path, pattern: str) -> list[dict[str, Any]]:
    return [load_json(path) for path in sorted(directory.glob(pattern))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures-dir", type=Path, required=True)
    parser.add_argument("--cohort-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = load_json(args.cohort_config)
    assignments = config.get("assignments", {})
    if not isinstance(assignments, dict):
        raise ValueError("assignments must be an object")
    report = build_cohort_report(
        load_matching(args.captures_dir, "plan-*.json"),
        load_matching(args.captures_dir, "settlement-summary-*.json"),
        assignments,
        strata=config.get("strata", DEFAULT_STRATA),
        required_per_stratum=int(config.get("required_per_stratum", 2)),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "qualifying_day_count": report["qualifying_day_count"],
                "required_day_count": report["required_day_count"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
