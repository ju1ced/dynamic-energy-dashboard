#!/usr/bin/env python3
"""Cross-check normalized market prices against official interval samples."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def crosscheck(dataset: dict[str, Any], samples: dict[str, Any]) -> dict[str, Any]:
    indexed = {
        row["start_local"]: float(row["price_eur_per_mwh"])
        for row in dataset["intervals"]
    }
    comparisons = []
    for sample in samples["samples"]:
        start_local = sample["start_local"]
        expected = float(sample["price_eur_per_mwh"])
        actual = indexed.get(start_local)
        difference = None if actual is None else round(actual - expected, 6)
        comparisons.append(
            {
                "start_local": start_local,
                "official_price_eur_per_mwh": expected,
                "dataset_price_eur_per_mwh": actual,
                "difference_eur_per_mwh": difference,
                "match": difference == 0.0,
            }
        )
    match_count = sum(1 for row in comparisons if row["match"])
    return {
        "schema_version": 1,
        "source": samples.get("source"),
        "source_url": samples.get("source_url"),
        "delivery_date": samples.get("delivery_date"),
        "sample_count": len(comparisons),
        "match_count": match_count,
        "mismatch_count": len(comparisons) - match_count,
        "all_match": match_count == len(comparisons),
        "comparisons": comparisons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    samples = json.loads(args.samples.read_text(encoding="utf-8"))
    report = crosscheck(dataset, samples)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["all_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
