from claim_review.response_parser import extract_prediction_json


FULL_JSON = """
{
  "evidence_standard_met": "true",
  "evidence_standard_met_reason": "clear",
  "risk_flags": "none",
  "issue_type": "dent",
  "object_part": "door",
  "claim_status": "supported",
  "claim_status_justification": "visible",
  "supporting_image_ids": "img_1",
  "valid_image": "true",
  "severity": "medium"
}
"""


def test_extracts_final_json_after_sentinel():
    text = "notes {\"foo\": 1}\nFINAL_JSON:\n" + FULL_JSON
    parsed = extract_prediction_json(text, "rubric_v1")
    assert parsed["claim_status"] == "supported"


def test_extracts_last_complete_object_for_rubric_without_sentinel():
    text = FULL_JSON.replace("supported", "contradicted") + "\n" + FULL_JSON
    parsed = extract_prediction_json(text, "rubric_v1")
    assert parsed["claim_status"] == "supported"

