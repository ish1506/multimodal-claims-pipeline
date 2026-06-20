from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_evaluation_module():
    spec = importlib.util.spec_from_file_location("evaluation_main", Path("code/evaluation/main.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_write_report_includes_concrete_operational_estimates(tmp_path: Path):
    evaluation = _load_evaluation_module()
    report = tmp_path / "evaluation_report.md"
    expected_row = {column: "same" for column in evaluation.OUTPUT_COLUMNS}
    expected_row.update(
        {
            "user_id": "u1",
            "image_paths": "images/sample/case_001/img_1.jpg;images/sample/case_001/img_2.jpg",
            "user_claim": "claim",
            "claim_object": "car",
            "claim_status": "supported",
            "evidence_standard_met": "true",
            "valid_image": "true",
            "issue_type": "dent",
            "object_part": "door",
            "severity": "low",
        }
    )
    expected = [expected_row]
    predictions = [dict(expected[0])]
    evaluation.write_report(
        report,
        model="test-model",
        expected=expected,
        test_rows=[{"image_paths": "images/test/case_001/img_1.jpg"} for _ in range(3)],
        results={"rubric_v1": predictions},
        chosen="rubric_v1",
        runtime_seconds=2.0,
    )

    text = report.read_text(encoding="utf-8")
    assert "| prompt_config | claim_status_accuracy | core_exact_match | weighted_score | risk_flags_f1 | supporting_image_ids_f1 |" in text
    assert "## Slice Metrics" in text
    assert "Model calls for this sample comparison: 1" in text
    assert "Model calls for the full test set with the chosen prompt: 3" in text
    assert "Images expected for full test processing: 3" in text
    assert "Estimated full-test processing cost: $" in text
    assert "Sample runtime used for planning: 2.0s total" in text
    assert "should be filled" not in text
    assert "depends on image encoding" not in text


def test_write_report_uses_observed_api_usage_when_available(tmp_path: Path):
    evaluation = _load_evaluation_module()
    report = tmp_path / "evaluation_report.md"
    expected_row = {column: "same" for column in evaluation.OUTPUT_COLUMNS}
    expected_row.update(
        {
            "user_id": "u1",
            "image_paths": "images/sample/case_001/img_1.jpg;images/sample/case_001/img_2.jpg",
            "user_claim": "claim",
            "claim_object": "car",
            "claim_status": "supported",
            "evidence_standard_met": "true",
            "valid_image": "true",
            "issue_type": "dent",
            "object_part": "door",
            "severity": "low",
        }
    )
    expected = [expected_row]
    predictions = [dict(expected[0])]
    evaluation.write_report(
        report,
        model="test-model",
        expected=expected,
        test_rows=[{"image_paths": "images/test/case_001/img_1.jpg"} for _ in range(3)],
        results={"rubric_v1": predictions},
        chosen="rubric_v1",
        runtime_seconds=2.0,
        usage_summary={
            "calls": 1.0,
            "images": 2.0,
            "prompt_tokens": 1000.0,
            "completion_tokens": 200.0,
            "total_tokens": 1200.0,
            "prompt_tokens_per_call": 1000.0,
            "completion_tokens_per_call": 200.0,
            "total_tokens_per_call": 1200.0,
            "prompt_tokens_per_image": 500.0,
        },
    )

    text = report.read_text(encoding="utf-8")
    assert "Token estimate source: observed API usage from 1 fresh calls and 2 images." in text
    assert "Observed average usage: 1000 input tokens/call, 200 output tokens/call" in text
    assert "Full-test estimated usage: 3000 input tokens and 600 output tokens." in text
    assert "Token estimate assumptions:" not in text


def test_write_report_includes_vlm_judge_metrics(tmp_path: Path):
    evaluation = _load_evaluation_module()
    report = tmp_path / "evaluation_report.md"
    expected_row = {column: "same" for column in evaluation.OUTPUT_COLUMNS}
    expected_row.update(
        {
            "user_id": "u1",
            "image_paths": "images/sample/case_001/img_1.jpg",
            "user_claim": "claim",
            "claim_object": "car",
            "claim_status": "supported",
            "evidence_standard_met": "true",
            "valid_image": "true",
            "risk_flags": "none",
            "issue_type": "dent",
            "object_part": "door",
            "supporting_image_ids": "img_1",
            "severity": "low",
        }
    )
    expected = [expected_row]
    predictions = [dict(expected[0])]

    evaluation.write_report(
        report,
        model="test-model",
        expected=expected,
        test_rows=[{"image_paths": "images/test/case_001/img_1.jpg"}],
        results={"rubric_v1": predictions},
        chosen="rubric_v1",
        runtime_seconds=2.0,
        judge_model="gpt-5.5",
        judge_results={
            "rubric_v1": [
                {
                    "row_index": "0",
                    "prompt_config": "rubric_v1",
                    "decision_score": "5",
                    "evidence_reasoning_score": "4",
                    "risk_flag_score": "3",
                    "supporting_images_score": "5",
                    "explanation_grounded": "true",
                    "major_error_type": "none",
                    "notes": "Looks grounded.",
                }
            ]
        },
    )

    text = report.read_text(encoding="utf-8")
    assert "## VLM Judge Metrics" in text
    assert "Judge model: `gpt-5.5`" in text
    assert "| rubric_v1 | 1 | 5.00 | 4.00 | 3.00 | 5.00 | 1.000 | none |" in text
    assert "VLM judge calls: 1 using gpt-5.5" in text


def test_weighted_score_uses_f1_for_set_fields():
    evaluation = _load_evaluation_module()
    actual = {
        "claim_status": "supported",
        "evidence_standard_met": "true",
        "valid_image": "true",
        "issue_type": "dent",
        "object_part": "door",
        "severity": "low",
        "risk_flags": "blurry_image;manual_review_required",
        "supporting_image_ids": "img_1;img_2",
    }
    predicted = dict(actual)
    predicted["risk_flags"] = "blurry_image"
    predicted["supporting_image_ids"] = "img_1"

    assert evaluation.set_f1(predicted["risk_flags"], actual["risk_flags"]) == 2 / 3
    assert evaluation.weighted_row_score(predicted, actual) > 0.9
