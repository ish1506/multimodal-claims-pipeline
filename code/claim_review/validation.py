from __future__ import annotations

import csv
from pathlib import Path

from .constants import (
    BOOLEAN_VALUES,
    CLAIM_OBJECTS,
    CLAIM_STATUS_VALUES,
    ISSUE_TYPE_VALUES,
    OBJECT_PART_VALUES,
    OUTPUT_COLUMNS,
    RISK_FLAG_VALUES,
    SEVERITY_VALUES,
)
from .context import image_id_from_path, split_image_paths


class ValidationError(ValueError):
    """Raised when a prediction CSV or row violates the output contract."""

    pass


def _read_with_header(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _fail(location: str, message: str) -> None:
    raise ValidationError(f"{location}: {message}")


def validate_prediction(prediction: dict[str, str], source_row: dict[str, str], row_number: int) -> None:
    """Validate one prediction row against schema, allowed values, and source row."""
    location = f"row {row_number}"
    if list(prediction.keys()) != OUTPUT_COLUMNS:
        _fail(location, "columns are not in the required order")

    for column in ["user_id", "image_paths", "user_claim", "claim_object"]:
        if prediction[column] != source_row[column]:
            _fail(location, f"{column} does not match source input")

    claim_object = prediction["claim_object"]
    if claim_object not in CLAIM_OBJECTS:
        _fail(location, f"invalid claim_object {claim_object!r}")
    if prediction["evidence_standard_met"] not in BOOLEAN_VALUES:
        _fail(location, "evidence_standard_met must be lowercase true/false")
    if prediction["valid_image"] not in BOOLEAN_VALUES:
        _fail(location, "valid_image must be lowercase true/false")
    if prediction["claim_status"] not in CLAIM_STATUS_VALUES:
        _fail(location, f"invalid claim_status {prediction['claim_status']!r}")
    if prediction["issue_type"] not in ISSUE_TYPE_VALUES:
        _fail(location, f"invalid issue_type {prediction['issue_type']!r}")
    if prediction["object_part"] not in OBJECT_PART_VALUES[claim_object]:
        _fail(location, f"invalid object_part {prediction['object_part']!r} for {claim_object}")
    if prediction["severity"] not in SEVERITY_VALUES:
        _fail(location, f"invalid severity {prediction['severity']!r}")

    risk_flags = prediction["risk_flags"].split(";") if prediction["risk_flags"] else []
    if not risk_flags:
        _fail(location, "risk_flags is required")
    if "none" in risk_flags and len(risk_flags) > 1:
        _fail(location, "risk_flags=none is exclusive")
    if any(flag not in RISK_FLAG_VALUES for flag in risk_flags):
        _fail(location, f"invalid risk_flags {prediction['risk_flags']!r}")
    expected_order = [flag for flag in RISK_FLAG_VALUES if flag in risk_flags]
    if risk_flags != expected_order:
        _fail(location, "risk_flags are not in canonical order")

    valid_ids = {image_id_from_path(path) for path in split_image_paths(source_row["image_paths"])}
    supporting_ids = prediction["supporting_image_ids"].split(";") if prediction["supporting_image_ids"] else []
    if not supporting_ids:
        _fail(location, "supporting_image_ids is required")
    if "none" in supporting_ids and len(supporting_ids) > 1:
        _fail(location, "supporting_image_ids=none is exclusive")
    if any(image_id != "none" and image_id not in valid_ids for image_id in supporting_ids):
        _fail(location, "supporting_image_ids references images outside the source row")

    for column in [
        "evidence_standard_met_reason",
        "claim_status_justification",
    ]:
        if not prediction[column].strip():
            _fail(location, f"{column} is required")


def validate_prediction_rows(predictions: list[dict[str, str]], source_rows: list[dict[str, str]]) -> None:
    """Validate all prediction rows and ensure row count matches the source CSV."""
    if len(predictions) != len(source_rows):
        raise ValidationError(f"row count mismatch: output has {len(predictions)} rows, source has {len(source_rows)} rows")
    for index, (prediction, source_row) in enumerate(zip(predictions, source_rows), start=1):
        validate_prediction(prediction, source_row, index)


def validate_output_file(output_path: Path, claims_path: Path) -> None:
    """Validate a prediction CSV file against its corresponding claim input CSV."""
    header, predictions = _read_with_header(output_path)
    if header != OUTPUT_COLUMNS:
        raise ValidationError(f"{output_path} header does not match required output columns")
    _, source_rows = _read_with_header(claims_path)
    validate_prediction_rows(predictions, source_rows)
