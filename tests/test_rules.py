from claim_review.context import build_claim_context
from claim_review.rules import apply_review_rules


def _context(user_claim: str, claim_object: str):
    row = {
        "user_id": "u1",
        "image_paths": "images/sample/case_001/img_1.jpg;images/sample/case_001/img_2.jpg",
        "user_claim": user_claim,
        "claim_object": claim_object,
    }
    return build_claim_context(row, 0, {}, [])


def _prediction(**overrides):
    prediction = {
        "user_id": "u1",
        "image_paths": "images/sample/case_001/img_1.jpg;images/sample/case_001/img_2.jpg",
        "user_claim": "claim",
        "claim_object": "car",
        "evidence_standard_met": "true",
        "evidence_standard_met_reason": "clear",
        "risk_flags": "none",
        "issue_type": "dent",
        "object_part": "door",
        "claim_status": "supported",
        "claim_status_justification": "visible",
        "supporting_image_ids": "img_1",
        "valid_image": "true",
        "severity": "medium",
    }
    prediction.update(overrides)
    return prediction


def test_rules_contradict_low_trackpad_scratch_for_functional_claim():
    context = _context("The laptop trackpad has stopped working and has physical damage around the trackpad.", "laptop")
    prediction = _prediction(
        claim_object="laptop",
        issue_type="scratch",
        object_part="trackpad",
        severity="low",
    )

    adjusted = apply_review_rules(prediction, context)

    assert adjusted["claim_status"] == "contradicted"
    assert adjusted["issue_type"] == "none"
    assert adjusted["severity"] == "none"
    assert "damage_not_visible" in adjusted["risk_flags"]


def test_rules_convert_wrong_object_claim_mismatch_to_contradicted():
    context = _context("The shipping box arrived badly crushed.", "package")
    prediction = _prediction(
        claim_object="package",
        evidence_standard_met="false",
        risk_flags="wrong_object;claim_mismatch;user_history_risk",
        issue_type="none",
        object_part="unknown",
        claim_status="not_enough_information",
        severity="none",
    )

    adjusted = apply_review_rules(prediction, context)

    assert adjusted["claim_status"] == "contradicted"
    assert adjusted["evidence_standard_met"] == "true"


def test_rules_contradict_high_risk_supported_torn_seal_claim():
    context = _context("The package seal area looked torn-open when I received it.", "package")
    prediction = _prediction(
        claim_object="package",
        risk_flags="user_history_risk",
        issue_type="torn_packaging",
        object_part="seal",
        severity="medium",
    )

    adjusted = apply_review_rules(prediction, context)

    assert adjusted["claim_status"] == "contradicted"
    assert adjusted["issue_type"] == "none"
    assert adjusted["severity"] == "none"
    assert adjusted["risk_flags"] == "damage_not_visible;user_history_risk;manual_review_required"


def test_rules_leave_supported_door_dent_unchanged():
    context = _context("There is a dent on the door panel area.", "car")
    prediction = _prediction(issue_type="dent", object_part="door", severity="medium")

    adjusted = apply_review_rules(prediction, context)

    assert adjusted == prediction
