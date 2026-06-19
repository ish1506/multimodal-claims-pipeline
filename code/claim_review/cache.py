from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .context import ClaimContext
from .images import PreparedImage


class PredictionCache:
    """JSON-backed cache for normalized predictions and raw VLM responses."""

    def __init__(self, path: Path | None):
        """Load an existing cache file when one is configured."""
        self.path = path
        self._data: dict[str, Any] = {}
        if path and path.exists():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    def key(
        self,
        context: ClaimContext,
        images: list[PreparedImage],
        *,
        prompt_config: str,
        model: str,
    ) -> str:
        """Create a cache key from claim content, images, prompt, and model."""
        payload = {
            "source_row": context.source_row,
            "user_history": context.user_history,
            "evidence_requirements": context.evidence_requirements,
            "image_hashes": [(image.source_path, image.bytes_sha256) for image in images],
            "prompt_config": prompt_config,
            "model": model,
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get(self, key: str) -> dict[str, str] | None:
        """Return a cached prediction for a key, if present."""
        value = self._data.get(key)
        if isinstance(value, dict) and isinstance(value.get("prediction"), dict):
            return {str(k): str(v) for k, v in value["prediction"].items()}
        return None

    def set(self, key: str, prediction: dict[str, str], raw_response: str) -> None:
        """Persist a prediction and raw response under a cache key."""
        if self.path is None:
            return
        self._data[key] = {"prediction": prediction, "raw_response": raw_response}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(self.path)
