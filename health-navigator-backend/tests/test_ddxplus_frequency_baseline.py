import csv
import json
from pathlib import Path

from tools.build_ddxplus_frequency_baseline import (
    _base_evidence_id,
    _parse_evidences,
    build_frequency_baseline,
)


def test_parse_evidences_preserves_value_tokens():
    assert _parse_evidences("['E_1', 'E_2_@_V_3']") == ["E_1", "E_2_@_V_3"]


def test_base_evidence_id_removes_value_suffix():
    assert _base_evidence_id("E_55_@_V_25") == "E_55"
    assert _base_evidence_id("E_91") == "E_91"


def test_build_frequency_baseline_uses_only_approved_conditions(tmp_path: Path):
    patient_path = tmp_path / "patients.csv"
    mapping_path = tmp_path / "approved.json"
    output_path = tmp_path / "baseline.json"

    with patient_path.open("w", encoding="utf-8", newline="") as file:
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
                "EVIDENCES": "['E_1', 'E_2_@_V_3']",
                "INITIAL_EVIDENCE": "E_1",
            }
        )
        writer.writerow(
            {
                "AGE": "30",
                "DIFFERENTIAL_DIAGNOSIS": "[]",
                "SEX": "F",
                "PATHOLOGY": "GERD",
                "EVIDENCES": "['E_9']",
                "INITIAL_EVIDENCE": "E_9",
            }
        )

    mapping_path.write_text(
        json.dumps(
            [
                {
                    "source_condition_name": "Anemia",
                    "internal_condition_code": "anemia",
                    "approval_status": "approved_draft",
                }
            ]
        ),
        encoding="utf-8",
    )

    baseline = build_frequency_baseline(patient_path, mapping_path, output_path)

    assert baseline["total_train_rows"] == 2
    assert baseline["used_train_rows"] == 1
    assert baseline["internal_condition_count"] == 1
    assert baseline["conditions"][0]["internal_condition_code"] == "anemia"
    assert baseline["conditions"][0]["top_evidences"][0]["evidence_id"] == "E_1"
