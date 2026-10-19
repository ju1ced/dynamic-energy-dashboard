import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "summarize_prospective_shadow_validation",
    ROOT / "scripts" / "summarize_prospective_shadow_validation.py",
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

STRATA = [
    "winter_weekday",
    "summer_high_pv_weekday",
    "weekend",
    "negative_price_day",
    "high_load_ev_day",
    "ordinary_shoulder_weekday",
]


def plan(target_date="2026-10-06", *, generated_at="2026-10-05T21:59:00+00:00"):
    return {
        "target_date": target_date,
        "status": "PLANNED",
        "capture_quality": "ACCEPTED_PROSPECTIVE_DAY",
        "generated_at": generated_at,
        "target_start_utc": "2026-10-05T22:00:00+00:00",
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
    }


def settlement(target_date="2026-10-06"):
    return {
        "target_date": target_date,
        "status": "SETTLED",
        "quality": "ACCEPTED_PROSPECTIVE_DAY",
        "mode": "READ_ONLY_SHADOW_SETTLEMENT",
        "classification": "AFTER_THE_FACT_EXECUTION_SCORE_NO_CONTROL",
        "physical_writes": False,
        "home_assistant_writes": False,
        "sma_writes": False,
        "smappee_writes": False,
        "forecast_error": {
            "load_mae_kwh": 0.1,
            "pv_mae_kwh": 0.2,
            "base_net_mae_kwh": 0.3,
        },
        "plans": [
            {
                "id": "peak_neutral",
                "status": "SETTLED",
                "forecast_cost_eur": 4.0,
                "forecast_saving_eur": 1.0,
                "executed_cost_eur": 5.0,
                "executed_saving_eur": 0.5,
                "baseline_actual_cost_eur": 5.5,
            }
        ],
    }


class ProspectiveShadowCohortSummaryTests(unittest.TestCase):
    def test_settled_assigned_day_counts_and_aggregates_without_profiles(self):
        report = MODULE.build_cohort_report(
            [plan()],
            [settlement()],
            {"2026-10-06": "ordinary_shoulder_weekday"},
            strata=STRATA,
            required_per_stratum=2,
        )

        self.assertEqual(report["qualifying_day_count"], 1)
        self.assertEqual(report["remaining_day_count"], 11)
        self.assertEqual(
            report["strata"]["ordinary_shoulder_weekday"]["qualifying_dates"],
            ["2026-10-06"],
        )
        policy = report["policy_aggregates"]["peak_neutral"]
        self.assertEqual(policy["day_count"], 1)
        self.assertAlmostEqual(policy["executed_saving_eur"], 0.5)
        self.assertNotIn("intervals", str(report))
        self.assertFalse(report["physical_writes"])

    def test_late_plan_is_rejected_even_when_a_settlement_exists(self):
        report = MODULE.build_cohort_report(
            [plan(generated_at="2026-10-05T22:00:00+00:00")],
            [settlement()],
            {"2026-10-06": "ordinary_shoulder_weekday"},
            strata=STRATA,
            required_per_stratum=2,
        )

        self.assertEqual(report["qualifying_day_count"], 0)
        self.assertEqual(report["rejected_days"][0]["target_date"], "2026-10-06")
        self.assertIn(
            "PLAN_GENERATED_AFTER_TARGET_START",
            report["rejected_days"][0]["quality_flags"],
        )

    def test_write_enabled_settlement_is_rejected(self):
        unsafe = settlement()
        unsafe["physical_writes"] = True

        report = MODULE.build_cohort_report(
            [plan()],
            [unsafe],
            {"2026-10-06": "ordinary_shoulder_weekday"},
            strata=STRATA,
            required_per_stratum=2,
        )

        self.assertEqual(report["qualifying_day_count"], 0)
        self.assertIn(
            "INVALID_READ_ONLY_FLAG:physical_writes",
            report["rejected_days"][0]["quality_flags"],
        )

    def test_complete_requires_two_days_in_every_stratum(self):
        plans = []
        settlements = []
        assignments = {}
        for stratum_index, stratum in enumerate(STRATA):
            for day_index in range(2):
                day = 10 + stratum_index * 2 + day_index
                target_date = f"2026-01-{day:02d}"
                item = plan(target_date=target_date)
                item["target_start_utc"] = f"2026-01-{day - 1:02d}T23:00:00+00:00"
                item["generated_at"] = f"2026-01-{day - 1:02d}T22:59:00+00:00"
                plans.append(item)
                settlements.append(settlement(target_date))
                assignments[target_date] = stratum

        report = MODULE.build_cohort_report(
            plans,
            settlements,
            assignments,
            strata=STRATA,
            required_per_stratum=2,
        )

        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["qualifying_day_count"], 12)
        self.assertEqual(report["remaining_day_count"], 0)


if __name__ == "__main__":
    unittest.main()
