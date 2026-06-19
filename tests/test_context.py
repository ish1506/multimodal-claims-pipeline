from claim_review.context import build_claim_context, image_id_from_path, split_image_paths


def test_split_image_paths_and_ids():
    paths = split_image_paths("images/test/case_001/img_1.jpg; images/test/case_001/img_2.jpg")
    assert paths == ["images/test/case_001/img_1.jpg", "images/test/case_001/img_2.jpg"]
    assert [image_id_from_path(path) for path in paths] == ["img_1", "img_2"]


def test_build_context_selects_global_and_object_requirements():
    row = {
        "user_id": "u1",
        "image_paths": "images/test/case_001/img_1.jpg",
        "user_claim": "door dent",
        "claim_object": "car",
    }
    requirements = [
        {"claim_object": "all", "requirement_id": "all"},
        {"claim_object": "car", "requirement_id": "car"},
        {"claim_object": "laptop", "requirement_id": "laptop"},
    ]
    context = build_claim_context(row, 0, {"u1": {"history_flags": "none"}}, requirements)
    assert context.image_ids == ["img_1"]
    assert [item["requirement_id"] for item in context.evidence_requirements] == ["all", "car"]
    assert context.user_history == {"history_flags": "none"}

