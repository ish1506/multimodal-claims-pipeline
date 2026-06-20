from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ClaimContext:
    """All non-image context needed to review one claim row."""

    row_index: int
    source_row: dict[str, str]
    image_paths: list[str]
    image_ids: list[str]
    user_history: dict[str, str] | None
    evidence_requirements: list[dict[str, str]]

    @property
    def user_id(self) -> str:
        return self.source_row["user_id"]

    @property
    def claim_object(self) -> str:
        return self.source_row["claim_object"]

    @property
    def user_claim(self) -> str:
        return self.source_row["user_claim"]


def split_image_paths(value: str) -> list[str]:
    """Split a semicolon-delimited image path field into clean path strings."""
    return [part.strip() for part in value.split(";") if part.strip()]


def image_id_from_path(value: str) -> str:
    """Return the required image ID, defined as the filename stem."""
    return Path(value).stem


def build_claim_context(
    row: dict[str, str],
    row_index: int,
    histories: dict[str, dict[str, str]],
    requirements: list[dict[str, str]],
) -> ClaimContext:
    """Build review context by joining claim rows to history and requirements."""
    image_paths = split_image_paths(row.get("image_paths", ""))
    relevant_requirements = [
        requirement
        for requirement in requirements
        if requirement.get("claim_object") in {"all", row.get("claim_object")}
    ]
    return ClaimContext(
        row_index=row_index,
        source_row=row,
        image_paths=image_paths,
        image_ids=[image_id_from_path(path) for path in image_paths],
        user_history=histories.get(row.get("user_id", "")),
        evidence_requirements=relevant_requirements,
    )
