from __future__ import annotations

import argparse
import ast
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
APPROVED_CONDITION_MAPPINGS_PATH = PROCESSED_DIR / "ddxplus_approved_condition_mappings.json"
OUTPUT_PATH = PROCESSED_DIR / "ddxplus_frequency_baseline.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _parse_evidences(value: str) -> list[str]:
    if not value:
        return []
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, list):
        raise ValueError("EVIDENCES must be a list")
    return [str(item) for item in parsed]


def _base_evidence_id(evidence_value: str) -> str:
    return evidence_value.split("_@_", 1)[0]


def _load_approved_condition_map(path: Path) -> dict[str, str]:
    mappings = _load_json(path)
    return {
        mapping["source_condition_name"]: mapping["internal_condition_code"]
        for mapping in mappings
        if mapping.get("approval_status") == "approved_draft"
    }


def build_frequency_baseline(
    patient_split_path: Path = RAW_DIR / "release_train_patients",
    approved_mapping_path: Path = APPROVED_CONDITION_MAPPINGS_PATH,
    output_path: Path = OUTPUT_PATH,
) -> dict[str, Any]:
    source_to_internal = _load_approved_condition_map(approved_mapping_path)
    internal_condition_counts: Counter[str] = Counter()
    source_condition_counts: Counter[str] = Counter()
    initial_evidence_counts: dict[str, Counter[str]] = defaultdict(Counter)
    evidence_counts: dict[str, Counter[str]] = defaultdict(Counter)
    total_rows = 0
    used_rows = 0

    with patient_split_path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            total_rows += 1
            source_condition = row.get("PATHOLOGY", "")
            internal_condition = source_to_internal.get(source_condition)
            if not internal_condition:
                continue

            used_rows += 1
            source_condition_counts[source_condition] += 1
            internal_condition_counts[internal_condition] += 1

            initial_evidence = row.get("INITIAL_EVIDENCE", "")
            if initial_evidence:
                initial_evidence_counts[internal_condition][initial_evidence] += 1

            for evidence in _parse_evidences(row.get("EVIDENCES", "")):
                evidence_counts[internal_condition][_base_evidence_id(evidence)] += 1

    conditions = []
    for internal_condition, row_count in sorted(internal_condition_counts.items()):
        conditions.append(
            {
                "internal_condition_code": internal_condition,
                "row_count": row_count,
                "prior_probability_within_approved_rows": row_count / used_rows if used_rows else 0,
                "top_initial_evidences": _top_counts(initial_evidence_counts[internal_condition], row_count),
                "top_evidences": _top_counts(evidence_counts[internal_condition], row_count),
            }
        )

    baseline = {
        "source": "DDXPlus",
        "baseline_type": "frequency",
        "training_split": patient_split_path.name,
        "approved_mapping_path": _display_path(approved_mapping_path),
        "total_train_rows": total_rows,
        "used_train_rows": used_rows,
        "coverage_ratio": used_rows / total_rows if total_rows else 0,
        "approved_source_condition_count": len(source_to_internal),
        "internal_condition_count": len(internal_condition_counts),
        "source_condition_counts": dict(sorted(source_condition_counts.items())),
        "conditions": conditions,
        "usage_policy": {
            "candidate_ranking_only": True,
            "red_flag_usage": False,
            "requires_human_review_before_service_integration": True,
        },
    }
    output_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    return baseline


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(DATA_DIR.parents[1]))
    except ValueError:
        return str(path)


def _top_counts(counter: Counter[str], denominator: int, limit: int = 30) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": evidence_id,
            "count": count,
            "frequency": count / denominator if denominator else 0,
        }
        for evidence_id, count in counter.most_common(limit)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a DDXPlus frequency baseline from approved mappings.")
    parser.parse_args()
    build_frequency_baseline()


if __name__ == "__main__":
    main()
