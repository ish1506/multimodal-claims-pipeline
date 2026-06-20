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
