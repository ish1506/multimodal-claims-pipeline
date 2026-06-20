import pytest

from claim_review.context import build_claim_context
from claim_review.normalization import normalize_prediction
from claim_review.validation import ValidationError, validate_prediction


def _context():
    row = {
        "user_id": "u1",
        "image_paths": "images/test/case_001/img_1.jpg;images/test/case_001/img_2.jpg",
        "user_claim": "door dent",
        "claim_object": "car",
    }
    return build_claim_context(row, 0, {}, [])


def test_normalize_prediction_restores_inputs_and_orders_risk_flags():
    context = _context()
    prediction = normalize_prediction(
        {
            "evidence_standard_met": True,
            "evidence_standard_met_reason": "clear",
            "risk_flags": ["manual_review_required", "blurry_image", "blurry_image"],
            "issue_type": "Dent",
            "object_part": "door",
            "claim_status": "supported",
            "claim_status_justification": "visible in img_1",
            "supporting_image_ids": ["img_1.jpg", "not_submitted"],
            "valid_image": "yes",
            "severity": "Medium",
        },
        context,
    )
    assert prediction["user_claim"] == "door dent"
    assert prediction["risk_flags"] == "blurry_image;manual_review_required"
    assert prediction["supporting_image_ids"] == "img_1"
    validate_prediction(prediction, context.source_row, 1)


def test_validation_rejects_non_canonical_risk_order():
    context = _context()
    prediction = normalize_prediction(
        {
            "evidence_standard_met": "true",
            "evidence_standard_met_reason": "clear",
            "risk_flags": "blurry_image",
            "issue_type": "dent",
            "object_part": "door",
            "claim_status": "supported",
            "claim_status_justification": "visible",
            "supporting_image_ids": "img_1",
            "valid_image": "true",
            "severity": "medium",
        },
        context,
    )
    prediction["risk_flags"] = "manual_review_required;blurry_image"
    with pytest.raises(ValidationError):
        validate_prediction(prediction, context.source_row, 1)


@pytest.mark.parametrize(
    ("raw_flags", "expected_flags"),
    [
        ("none;user_history_risk", "user_history_risk"),
        (["none", "blurry_image"], "blurry_image"),
        ("none", "none"),
    ],
)
def test_normalize_prediction_discards_none_when_real_risk_flags_exist(raw_flags, expected_flags):
    context = _context()
    prediction = normalize_prediction(
        {
            "evidence_standard_met": "true",
            "evidence_standard_met_reason": "clear",
            "risk_flags": raw_flags,
            "issue_type": "dent",
            "object_part": "door",
            "claim_status": "supported",
            "claim_status_justification": "visible",
            "supporting_image_ids": "img_1",
            "valid_image": "true",
            "severity": "medium",
        },
        context,
    )
    assert prediction["risk_flags"] == expected_flags
    validate_prediction(prediction, context.source_row, 1)
