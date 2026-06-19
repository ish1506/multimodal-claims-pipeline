from pathlib import Path

from claim_review.pipeline import run_predictions


class FailingClient:
    def complete(self, *args, **kwargs):  # pragma: no cover - should not be called
        raise AssertionError("VLM should not be called for missing image files")


def test_pipeline_writes_safe_prediction_for_missing_image(tmp_path: Path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "user_history.csv").write_text(
        '"user_id","past_claim_count","accept_claim","manual_review_claim","rejected_claim","last_90_days_claim_count","history_flags","history_summary"\n'
        '"u1","0","0","0","0","0","none","new"\n',
        encoding="utf-8",
    )
    (dataset / "evidence_requirements.csv").write_text(
        '"requirement_id","claim_object","applies_to","minimum_image_evidence"\n'
        '"REQ","all","reviewability","visible"\n',
        encoding="utf-8",
    )
    claims = dataset / "claims.csv"
    claims.write_text(
        '"user_id","image_paths","user_claim","claim_object"\n'
        '"u1","images/test/missing/img_1.jpg","door dent","car"\n',
        encoding="utf-8",
    )
    output = tmp_path / "output.csv"
    predictions = run_predictions(
        input_path=claims,
        output_path=output,
        repo_root=tmp_path,
        client=FailingClient(),
        cache_path=None,
    )
    assert output.exists()
    assert predictions[0]["valid_image"] == "false"
    assert predictions[0]["claim_status"] == "not_enough_information"

