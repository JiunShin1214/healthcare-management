from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from build_ddxplus_frequency_baseline import (
        APPROVED_CONDITION_MAPPINGS_PATH,
        OUTPUT_PATH as BASELINE_PATH,
        RAW_DIR,
        PROCESSED_DIR,
        _base_evidence_id,
        _load_approved_condition_map,
        _load_json,
        _parse_evidences,
    )
except ModuleNotFoundError:
    from tools.build_ddxplus_frequency_baseline import (
        APPROVED_CONDITION_MAPPINGS_PATH,
        OUTPUT_PATH as BASELINE_PATH,
        RAW_DIR,
        PROCESSED_DIR,
        _base_evidence_id,
        _load_approved_condition_map,
        _load_json,
        _parse_evidences,
    )


OUTPUT_PATH = PROCESSED_DIR / "ddxplus_frequency_baseline_metrics.json"


def _condition_indexes(baseline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        condition["internal_condition_code"]: condition
        for condition in baseline.get("conditions", [])
    }


def _score_condition(condition: dict[str, Any], initial_evidence: str, evidence_ids: set[str]) -> float:
    score = condition.get("prior_probability_within_approved_rows", 0.0) * 0.1
    initial_frequency = {
        item["evidence_id"]: item["frequency"]
        for item in condition.get("top_initial_evidences", [])
    }
    evidence_frequency = {
        item["evidence_id"]: item["frequency"]
        for item in condition.get("top_evidences", [])
    }

    if initial_evidence in initial_frequency:
        score += initial_frequency[initial_evidence] * 2.0

    for evidence_id in evidence_ids:
        score += evidence_frequency.get(evidence_id, 0.0)

    return score


def _rank_conditions(baseline: dict[str, Any], initial_evidence: str, evidence_ids: set[str]) -> list[str]:
    scored = []
    for condition in baseline.get("conditions", []):
        condition_code = condition["internal_condition_code"]
        scored.append(
            (
                _score_condition(condition, initial_evidence, evidence_ids),
                condition_code,
            )
        )
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [condition_code for _, condition_code in scored]


def evaluate_frequency_baseline(
    split_paths: list[Path] | None = None,
    baseline_path: Path = BASELINE_PATH,
    approved_mapping_path: Path = APPROVED_CONDITION_MAPPINGS_PATH,
    output_path: Path = OUTPUT_PATH,
) -> dict[str, Any]:
    split_paths = split_paths or [
        RAW_DIR / "release_validate_patients",
    ]
    baseline = _load_json(baseline_path)
    source_to_internal = _load_approved_condition_map(approved_mapping_path)
    condition_indexes = _condition_indexes(baseline)

    split_metrics = []
    for split_path in split_paths:
        split_metrics.append(
            _evaluate_split(
                split_path,
                baseline,
                source_to_internal,
                condition_indexes,
            )
        )

    metrics = {
        "source": "DDXPlus",
        "baseline_type": "frequency",
        "baseline_path": _display_path(baseline_path),
        "approved_mapping_path": _display_path(approved_mapping_path),
        "evaluated_splits": split_metrics,
        "evaluation_policy": {
            "default_splits": ["validate"],
            "test_split_usage": "final_evaluation_only",
            "do_not_tune_with_test": True,
        },
        "usage_policy": baseline.get("usage_policy", {}),
    }
    output_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def _evaluate_split(
    split_path: Path,
    baseline: dict[str, Any],
    source_to_internal: dict[str, str],
    condition_indexes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    total_rows = 0
    evaluated_rows = 0
    hits = Counter()
    rank_sum = 0
    reciprocal_rank_sum = 0.0
    condition_rows = Counter()
    condition_top1_hits = Counter()
    condition_rank_sum = Counter()
    condition_reciprocal_rank_sum = Counter()

    with split_path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            total_rows += 1
            expected_condition = source_to_internal.get(row.get("PATHOLOGY", ""))
            if not expected_condition or expected_condition not in condition_indexes:
                continue

            evaluated_rows += 1
            condition_rows[expected_condition] += 1
            evidence_ids = {
                _base_evidence_id(evidence)
                for evidence in _parse_evidences(row.get("EVIDENCES", ""))
            }
            ranked = _rank_conditions(
                baseline,
                row.get("INITIAL_EVIDENCE", ""),
                evidence_ids,
            )

            if ranked and ranked[0] == expected_condition:
                hits["top_1"] += 1
                condition_top1_hits[expected_condition] += 1
            if expected_condition in ranked[:3]:
                hits["top_3"] += 1
            if expected_condition in ranked[:5]:
                hits["top_5"] += 1

            expected_rank = ranked.index(expected_condition) + 1
            rank_sum += expected_rank
            reciprocal_rank = 1 / expected_rank
            reciprocal_rank_sum += reciprocal_rank
            condition_rank_sum[expected_condition] += expected_rank
            condition_reciprocal_rank_sum[expected_condition] += reciprocal_rank

    condition_metrics = []
    for condition_code, rows in sorted(condition_rows.items()):
        top_1_accuracy = condition_top1_hits[condition_code] / rows if rows else 0
        condition_metrics.append(
            {
                "internal_condition_code": condition_code,
                "rows": rows,
                "top_1_accuracy": top_1_accuracy,
                "mean_expected_rank": condition_rank_sum[condition_code] / rows if rows else 0,
                "mean_reciprocal_rank": condition_reciprocal_rank_sum[condition_code] / rows if rows else 0,
                "review_note": "needs_mapping_review" if top_1_accuracy < 0.5 else "no_action_from_metric_alone",
            }
        )

    return {
        "split": split_path.name,
        "total_rows": total_rows,
        "evaluated_rows": evaluated_rows,
        "coverage_ratio": evaluated_rows / total_rows if total_rows else 0,
        "top_1_accuracy": hits["top_1"] / evaluated_rows if evaluated_rows else 0,
        "top_3_accuracy": hits["top_3"] / evaluated_rows if evaluated_rows else 0,
        "top_5_accuracy": hits["top_5"] / evaluated_rows if evaluated_rows else 0,
        "candidate_set_metrics": {
            "candidate_set_size": 5,
            "candidate_set_recall": hits["top_5"] / evaluated_rows if evaluated_rows else 0,
            "mean_expected_rank": rank_sum / evaluated_rows if evaluated_rows else 0,
            "mean_reciprocal_rank": reciprocal_rank_sum / evaluated_rows if evaluated_rows else 0,
            "primary_goal": "safe_explainable_candidate_set",
        },
        "baseline_usage_policy": {
            "candidate_usage": "tie_break_only",
            "condition_specific_exclusions": False,
            "reason": "Avoid cherry-picking condition-level behavior from validation metrics.",
        },
        "condition_metrics": condition_metrics,
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROCESSED_DIR.parents[2]))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the DDXPlus frequency baseline.")
    parser.add_argument(
        "--include-test",
        action="store_true",
        help="Also evaluate the test split. Use only for final reporting, not tuning.",
    )
    args = parser.parse_args()

    split_paths = [RAW_DIR / "release_validate_patients"]
    if args.include_test:
        split_paths.append(RAW_DIR / "release_test_patients")

    evaluate_frequency_baseline(split_paths=split_paths)


if __name__ == "__main__":
    main()
