from claim_review.context import ClaimContext
from claim_review.prompts import build_prompt


def _context(claim_object: str = "package") -> ClaimContext:
    return ClaimContext(
        row_index=0,
        source_row={
            "user_id": "u1",
            "image_paths": "images/sample/case_001/img_1.jpg",
            "user_claim": "The item was not inside the package.",
            "claim_object": claim_object,
        },
        image_paths=["images/sample/case_001/img_1.jpg"],
        image_ids=["img_1"],
        user_history={"history_flags": "none", "history_summary": "No risk."},
        evidence_requirements=[],
    )


def test_prompt_requires_clear_visual_evidence_for_supported_claims():
    prompt = build_prompt(_context(), "rubric_v1")

    assert 'Decide "supported" only when the submitted images clearly show' in prompt
    assert "Do not infer missing contents from a closed, cropped, or unclear package image" in prompt
    assert "Avoid supporting a claim from weak, ambiguous, or inferred evidence" in prompt


def test_prompt_distinguishes_absent_damage_from_insufficient_evidence():
    prompt = build_prompt(_context("laptop"), "concise_v1")

    assert 'claim_status="contradicted"' in prompt
    assert 'claim_status="not_enough_information"' in prompt
    assert "Do not infer laptop functional damage from a cosmetic mark alone" in prompt
