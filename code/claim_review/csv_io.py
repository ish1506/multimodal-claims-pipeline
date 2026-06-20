from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .constants import INPUT_COLUMNS, OUTPUT_COLUMNS


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV file with Python's real CSV parser."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def require_columns(rows: list[dict[str, str]], columns: list[str], path: Path) -> None:
    """Raise when a non-empty CSV is missing required columns."""
    if not rows:
        return
    missing = [column for column in columns if column not in rows[0]]
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")


def load_claim_rows(path: Path, *, labeled: bool = False) -> list[dict[str, str]]:
    """Load input or labeled claim rows and validate the expected columns."""
    rows = read_csv(path)
    required = OUTPUT_COLUMNS if labeled else INPUT_COLUMNS
    require_columns(rows, required, path)
    return rows


def load_user_history(path: Path) -> dict[str, dict[str, str]]:
    """Load user history rows keyed by user_id."""
    rows = read_csv(path)
    require_columns(rows, ["user_id", "history_flags", "history_summary"], path)
    return {row["user_id"]: row for row in rows}


def load_evidence_requirements(path: Path) -> list[dict[str, str]]:
    """Load minimum evidence requirement rows."""
    rows = read_csv(path)
    require_columns(
        rows,
        ["requirement_id", "claim_object", "applies_to", "minimum_image_evidence"],
        path,
    )
    return rows


def write_predictions(path: Path, predictions: Iterable[dict[str, str]]) -> None:
    """Write predictions with the required output column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, extrasaction="raise")
        writer.writeheader()
        for row in predictions:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})
