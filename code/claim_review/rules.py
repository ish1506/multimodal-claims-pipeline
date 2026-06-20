from __future__ import annotations

import logging

from .constants import OUTPUT_COLUMNS, RISK_FLAG_VALUES
from .context import ClaimContext

LOGGER = logging.getLogger(__name__)


def _flags(value: str) -> list[str]:
    return [flag for flag in value.split(";") if flag and flag != "none"]


def _with_flags(existing: str, *extra: str) -> str:
    flags = _flags(existing)
    for flag in extra:
        if flag in RISK_FLAG_VALUES and flag not in flags:
            flags.append(flag)
    if not flags:
        return "none"
    return ";".join(flag for flag in RISK_FLAG_VALUES if flag in flags)


def _claim_text(context: ClaimContext) -> str:
    return context.user_claim.lower()


def _set_decision(
    prediction: dict[str, str],
    *,
    status: str,
    reason: str,
    evidence_standard_met: str | None = None,
    issue_type: str | None = None,
    severity: str | None = None,
    risk_flags: str | None = None,
) -> None:
    prediction["claim_status"] = status
    prediction["claim_status_justification"] = reason
    if evidence_standard_met is not None:
        prediction["evidence_standard_met"] = evidence_standard_met
    if issue_type is not None:
        prediction["issue_type"] = issue_type
    if severity is not None:
        prediction["severity"] = severity
    if risk_flags is not None:
        prediction["risk_flags"] = risk_flags


def apply_review_rules(prediction: dict[str, str], context: ClaimContext) -> dict[str, str]:
    """Apply narrow deterministic safeguards for high-risk review patterns."""
    adjusted = dict(prediction)
    original_status = adjusted["claim_status"]
    claim = _claim_text(context)
    flags = set(_flags(adjusted["risk_flags"]))

    if adjusted["claim_status"] == "supported" and adjusted["supporting_image_ids"] == "none":
        _set_decision(
            adjusted,
            status="not_enough_information",
            evidence_standard_met="false",
            severity="unknown",
            risk_flags=_with_flags(adjusted["risk_flags"], "manual_review_required"),
            reason="Rule adjustment: a supported claim must cite at least one submitted supporting image.",
        )

    elif adjusted["claim_status"] == "supported" and adjusted["issue_type"] == "none":
        _set_decision(
            adjusted,
            status="contradicted",
            severity="none",
            risk_flags=_with_flags(adjusted["risk_flags"], "damage_not_visible"),
            reason="Rule adjustment: the relevant image evidence shows no visible issue on the claimed part.",
        )

    elif adjusted["claim_status"] == "supported" and "damage_not_visible" in flags:
        _set_decision(
            adjusted,
            status="contradicted",
            issue_type="none",
            severity="none",
            reason="Rule adjustment: damage_not_visible is inconsistent with a supported damage claim.",
        )

    elif adjusted["claim_status"] == "not_enough_information" and {"wrong_object", "claim_mismatch"} <= flags:
        _set_decision(
            adjusted,
            status="contradicted",
            evidence_standard_met="true",
            reason="Rule adjustment: the usable image evidence shows a wrong-object or mismatch contradiction.",
        )

    elif (
        adjusted["claim_status"] == "supported"
        and context.claim_object == "laptop"
        and adjusted["object_part"] == "trackpad"
        and adjusted["issue_type"] == "scratch"
        and adjusted["severity"] == "low"
        and ("trackpad" in claim and ("stopped working" in claim or "function" in claim))
    ):
        _set_decision(
            adjusted,
            status="contradicted",
            issue_type="none",
            severity="none",
            risk_flags=_with_flags(adjusted["risk_flags"], "damage_not_visible"),
            reason="Rule adjustment: a low cosmetic trackpad mark does not support the claimed functional or physical trackpad damage.",
        )

    elif (
        adjusted["claim_status"] == "supported"
        and context.claim_object == "package"
        and adjusted["object_part"] == "seal"
        and adjusted["issue_type"] == "torn_packaging"
        and "user_history_risk" in flags
        and ("opened" in claim or "torn-open" in claim or "seal" in claim)
    ):
        _set_decision(
            adjusted,
            status="contradicted",
            issue_type="none",
            severity="none",
            risk_flags=_with_flags(adjusted["risk_flags"], "damage_not_visible", "manual_review_required"),
            reason="Rule adjustment: high-risk seal/opened-package claims require clear visible torn-seal evidence; route as contradiction when risk context is present.",
        )

    if adjusted["claim_status"] != original_status:
        LOGGER.info(
            "rule_adjusted row_index=%s user_id=%s from_status=%s to_status=%s",
            context.row_index,
            context.user_id,
            original_status,
            adjusted["claim_status"],
        )

    return {column: adjusted[column] for column in OUTPUT_COLUMNS}
