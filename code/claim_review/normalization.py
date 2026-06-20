from __future__ import annotations

from typing import Any

from .constants import (
    CLAIM_STATUS_VALUES,
    ISSUE_TYPE_VALUES,
    OBJECT_PART_VALUES,
    OUTPUT_COLUMNS,
    RISK_FLAG_VALUES,
    SEVERITY_VALUES,
)
from .context import ClaimContext


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def canonical_bool(value: Any) -> str:
    """Coerce common boolean spellings to lowercase true/false strings."""
    text = _stringify(value).lower()
    if text in {"true", "1", "yes", "y"}:
        return "true"
    if text in {"false", "0", "no", "n"}:
        return "false"
    return text


def canonical_choice(value: Any, allowed: list[str], *, fallback: str) -> str:
    """Normalize a categorical value to an allowed value or fallback."""
    text = _stringify(value).lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "not_enough_info": "not_enough_information",
        "insufficient_information": "not_enough_information",
        "glass_shattered": "glass_shatter",
        "shattered_glass": "glass_shatter",
        "broken": "broken_part",
        "missing": "missing_part",
        "unknown_part": "unknown",
    }
    text = aliases.get(text, text)
    return text if text in allowed else fallback


def canonical_risk_flags(value: Any) -> str:
    """Deduplicate and sort risk flags in required canonical order."""
    if isinstance(value, list):
        raw_parts = [_stringify(part) for part in value]
    else:
        raw_parts = _stringify(value).replace(",", ";").split(";")
    normalized = []
    for part in raw_parts:
        flag = part.strip().lower().replace(" ", "_").replace("-", "_")
        if flag and flag in RISK_FLAG_VALUES and flag not in normalized:
            normalized.append(flag)
    real_flags = [flag for flag in normalized if flag != "none"]
    if not real_flags:
        return "none"
    return ";".join(flag for flag in RISK_FLAG_VALUES if flag in real_flags)


def canonical_supporting_ids(value: Any, valid_ids: list[str]) -> str:
    """Normalize supporting image IDs and drop IDs not submitted with the claim."""
    if isinstance(value, list):
        raw_parts = [_stringify(part) for part in value]
    else:
        raw_parts = _stringify(value).replace(",", ";").split(";")
    ids = []
    for part in raw_parts:
        image_id = part.strip()
        if not image_id or image_id.lower() == "none":
            continue
        image_id = image_id.rsplit(".", 1)[0]
        if image_id in valid_ids and image_id not in ids:
            ids.append(image_id)
    return ";".join(ids) if ids else "none"


def normalize_prediction(raw: dict[str, Any], context: ClaimContext) -> dict[str, str]:
    """Normalize VLM JSON and restore source input columns verbatim."""
    row = {column: context.source_row[column] for column in ["user_id", "image_paths", "user_claim", "claim_object"]}
    row.update(
        {
            "evidence_standard_met": canonical_bool(raw.get("evidence_standard_met", "")),
            "evidence_standard_met_reason": _stringify(raw.get("evidence_standard_met_reason", "")),
            "risk_flags": canonical_risk_flags(raw.get("risk_flags", "none")),
            "issue_type": canonical_choice(raw.get("issue_type", ""), ISSUE_TYPE_VALUES, fallback="unknown"),
            "object_part": canonical_choice(
                raw.get("object_part", ""),
                OBJECT_PART_VALUES[context.claim_object],
                fallback="unknown",
            ),
            "claim_status": canonical_choice(
                raw.get("claim_status", ""),
                CLAIM_STATUS_VALUES,
                fallback="not_enough_information",
            ),
            "claim_status_justification": _stringify(raw.get("claim_status_justification", "")),
            "supporting_image_ids": canonical_supporting_ids(raw.get("supporting_image_ids", "none"), context.image_ids),
            "valid_image": canonical_bool(raw.get("valid_image", "")),
            "severity": canonical_choice(raw.get("severity", ""), SEVERITY_VALUES, fallback="unknown"),
        }
    )
    return {column: row.get(column, "") for column in OUTPUT_COLUMNS}


def io_failure_prediction(context: ClaimContext, reason: str) -> dict[str, str]:
    """Build the safe reviewability result used only for image I/O failures."""
    raw = {
        "evidence_standard_met": "false",
        "evidence_standard_met_reason": reason,
        "risk_flags": "manual_review_required",
        "issue_type": "unknown",
        "object_part": "unknown",
        "claim_status": "not_enough_information",
        "claim_status_justification": reason,
        "supporting_image_ids": "none",
        "valid_image": "false",
        "severity": "unknown",
    }
    return normalize_prediction(raw, context)
