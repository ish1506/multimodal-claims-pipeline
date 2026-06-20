from __future__ import annotations

import json
import re
from typing import Any

from .constants import OUTPUT_COLUMNS

SEMANTIC_COLUMNS = [column for column in OUTPUT_COLUMNS if column not in {"user_id", "image_paths", "user_claim", "claim_object"}]


def _candidate_json_strings(text: str) -> list[str]:
    candidates: list[str] = []
    starts = [index for index, char in enumerate(text) if char == "{"]
    for start in starts:
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : index + 1])
                    break
    return candidates


def _loads_object(candidate: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def extract_prediction_json(text: str, prompt_config: str) -> dict[str, Any]:
    """Extract the final complete prediction JSON object from VLM text."""
    search_text = text
    if prompt_config == "rubric_v1":
        match = re.search(r"FINAL_JSON:\s*(.*)", text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            search_text = match.group(1)

    valid_objects: list[dict[str, Any]] = []
    for candidate in _candidate_json_strings(search_text):
        parsed = _loads_object(candidate)
        if parsed and all(column in parsed for column in SEMANTIC_COLUMNS):
            valid_objects.append(parsed)
    if valid_objects:
        return valid_objects[-1]

    if prompt_config == "rubric_v1":
        for candidate in _candidate_json_strings(text):
            parsed = _loads_object(candidate)
            if parsed and all(column in parsed for column in SEMANTIC_COLUMNS):
                valid_objects.append(parsed)
        if valid_objects:
            return valid_objects[-1]

    raise ValueError("Could not extract a complete prediction JSON object from VLM response")
