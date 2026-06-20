from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class UsageSample:
    """Token usage reported by one completed VLM API call."""

    row_index: int
    prompt_config: str
    model: str
    image_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class UsageCollector:
    """Collect token usage from real VLM calls for reporting and cost estimates."""

    def __init__(self) -> None:
        self._samples: list[UsageSample] = []

    @property
    def samples(self) -> tuple[UsageSample, ...]:
        """Return immutable usage samples recorded so far."""
        return tuple(self._samples)

    def record(self, sample: UsageSample) -> None:
        """Record one API usage sample."""
        self._samples.append(sample)

    def summary(self) -> dict[str, float] | None:
        """Summarize observed token usage, returning None when no calls were made."""
        if not self._samples:
            return None

        calls = len(self._samples)
        images = sum(sample.image_count for sample in self._samples)
        prompt_tokens = sum(sample.prompt_tokens for sample in self._samples)
        completion_tokens = sum(sample.completion_tokens for sample in self._samples)
        total_tokens = sum(sample.total_tokens for sample in self._samples)
        return {
            "calls": float(calls),
            "images": float(images),
            "prompt_tokens": float(prompt_tokens),
            "completion_tokens": float(completion_tokens),
            "total_tokens": float(total_tokens),
            "prompt_tokens_per_call": mean(sample.prompt_tokens for sample in self._samples),
            "completion_tokens_per_call": mean(sample.completion_tokens for sample in self._samples),
            "total_tokens_per_call": mean(sample.total_tokens for sample in self._samples),
            "prompt_tokens_per_image": prompt_tokens / images if images else 0.0,
        }
