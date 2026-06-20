from claim_review.cache import PredictionCache
from claim_review.context import ClaimContext
from claim_review.images import PreparedImage


def test_cache_key_changes_when_prompt_text_changes():
    context = ClaimContext(
        row_index=0,
        source_row={
            "user_id": "u1",
            "image_paths": "images/sample/case_001/img_1.jpg",
            "user_claim": "door dent",
            "claim_object": "car",
        },
        image_paths=["images/sample/case_001/img_1.jpg"],
        image_ids=["img_1"],
        user_history={"history_flags": "none", "history_summary": "No risk."},
        evidence_requirements=[],
    )
    image = PreparedImage(
        source_path="images/sample/case_001/img_1.jpg",
        image_id="img_1",
        mime_type="image/jpeg",
        bytes_sha256="abc123",
        data_url="data:image/jpeg;base64,",
    )
    cache = PredictionCache(None)

    first = cache.key(context, [image], prompt_config="rubric_v1", prompt_text="prompt A", model="gpt-5.4-mini")
    second = cache.key(context, [image], prompt_config="rubric_v1", prompt_text="prompt B", model="gpt-5.4-mini")

    assert first != second
