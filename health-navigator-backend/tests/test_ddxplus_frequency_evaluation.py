import csv
import json
from pathlib import Path

from tools.evaluate_ddxplus_frequency_baseline import evaluate_frequency_baseline


def test_evaluate_frequency_baseline_reports_top_k_metrics(tmp_path: Path):
    split_path = tmp_path / "validate.csv"
    baseline_path = tmp_path / "baseline.json"
    mapping_path = tmp_path / "approved.json"
    output_path = tmp_path / "metrics.json"

    baseline_path.write_text(
        json.dumps(
            {
                "source": "DDXPlus",
                "baseline_type": "frequency",
                "usage_policy": {"candidate_ranking_only": True, "red_flag_usage": False},
                "conditions": [
                    {
                        "internal_condition_code": "anemia",
                        "prior_probability_within_approved_rows": 0.7,
                        "top_initial_evidences": [{"evidence_id": "E_1", "frequency": 0.9}],
                        "top_evidences": [{"evidence_id": "E_1", "frequency": 0.9}],
                    },
                    {
                        "internal_condition_code": "otitis_media",
                        "prior_probability_within_approved_rows": 0.3,
                        "top_initial_evidences": [{"evidence_id": "E_2", "frequency": 0.8}],
                        "top_evidences": [{"evidence_id": "E_2", "frequency": 0.8}],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    mapping_path.write_text(
        json.dumps(
            [
                {
                    "source_condition_name": "Anemia",
                    "internal_condition_code": "anemia",
                    "approval_status": "approved_draft",
                },
                {
                    "source_condition_name": "Acute otitis media",
                    "internal_condition_code": "otitis_media",
                    "approval_status": "approved_draft",
                },
            ]
        ),
        encoding="utf-8",
    )

    with split_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["AGE", "DIFFERENTIAL_DIAGNOSIS", "SEX", "PATHOLOGY", "EVIDENCES", "INITIAL_EVIDENCE"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "AGE": "30",
                "DIFFERENTIAL_DIAGNOSIS": "[]",
                "SEX": "F",
                "PATHOLOGY": "Anemia",
                "EVIDENCES": "['E_1']",
                "INITIAL_EVIDENCE": "E_1",
            }
        )
        writer.writerow(
            {
                "AGE": "30",
                "DIFFERENTIAL_DIAGNOSIS": "[]",
                "SEX": "F",
                "PATHOLOGY": "Unmapped",
                "EVIDENCES": "['E_9']",
                "INITIAL_EVIDENCE": "E_9",
            }
        )

    metrics = evaluate_frequency_baseline([split_path], baseline_path, mapping_path, output_path)

    split_metrics = metrics["evaluated_splits"][0]
    assert split_metrics["total_rows"] == 2
    assert split_metrics["evaluated_rows"] == 1
    assert split_metrics["top_1_accuracy"] == 1
    assert split_metrics["top_3_accuracy"] == 1
    assert split_metrics["top_5_accuracy"] == 1
    assert split_metrics["candidate_set_metrics"]["primary_goal"] == "safe_explainable_candidate_set"
    assert split_metrics["candidate_set_metrics"]["candidate_set_recall"] == 1
    assert split_metrics["candidate_set_metrics"]["mean_expected_rank"] == 1
    assert split_metrics["baseline_usage_policy"]["candidate_usage"] == "tie_break_only"
    assert split_metrics["baseline_usage_policy"]["condition_specific_exclusions"] is False
    assert metrics["evaluation_policy"]["test_split_usage"] == "final_evaluation_only"
    assert metrics["evaluation_policy"]["do_not_tune_with_test"] is True
    assert output_path.exists()
