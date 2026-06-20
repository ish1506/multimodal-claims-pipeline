from __future__ import annotations

import logging
import os
from pathlib import Path

from .cache import PredictionCache
from .constants import DEFAULT_MODEL, DEFAULT_PROMPT_CONFIG
from .context import build_claim_context
from .csv_io import load_claim_rows, load_evidence_requirements, load_user_history, write_predictions
from .images import prepare_images
from .normalization import io_failure_prediction, normalize_prediction
from .prompts import build_prompt
from .response_parser import extract_prediction_json
from .usage import UsageCollector
from .validation import validate_prediction, validate_prediction_rows
from .vlm import OpenAIVLMClient, VLMClient

LOGGER = logging.getLogger(__name__)


def repo_root_from_code() -> Path:
    """Resolve the repository root from this package location."""
    return Path(__file__).resolve().parents[2]


def _default_data_path(repo_root: Path, name: str) -> Path:
    return repo_root / "dataset" / name


def review_claim(
    context,
    images,
    *,
    client: VLMClient,
    prompt_config: str,
    model: str,
    cache: PredictionCache,
    max_parse_attempts: int = 2,
) -> dict[str, str]:
    """Review one claim through cache, VLM call, parsing, normalization, and validation."""
    prompt_text = build_prompt(context, prompt_config)
    cache_key = cache.key(context, images, prompt_config=prompt_config, prompt_text=prompt_text, model=model)
    cached = cache.get(cache_key)
    if cached is not None:
        LOGGER.info("cache_hit row_index=%s user_id=%s prompt_config=%s model=%s", context.row_index, context.user_id, prompt_config, model)
        return cached

    LOGGER.info("cache_miss row_index=%s user_id=%s prompt_config=%s model=%s", context.row_index, context.user_id, prompt_config, model)
    last_error: Exception | None = None
    last_response = ""
    for attempt in range(1, max_parse_attempts + 1):
        LOGGER.info("vlm_attempt row_index=%s attempt=%s", context.row_index, attempt)
        last_response = client.complete(context, images, prompt_config=prompt_config, model=model)
        try:
            raw = extract_prediction_json(last_response, prompt_config)
            prediction = normalize_prediction(raw, context)
            validate_prediction(prediction, context.source_row, context.row_index + 1)
            cache.set(cache_key, prediction, last_response)
            return prediction
        except ValueError as error:
            LOGGER.warning("vlm_parse_or_validation_error row_index=%s attempt=%s error=%s", context.row_index, attempt, error)
            last_error = error
    raise RuntimeError(f"VLM returned malformed or invalid output after retries: {last_error}") from last_error


def run_predictions(
    *,
    input_path: Path,
    output_path: Path,
    repo_root: Path | None = None,
    model: str = DEFAULT_MODEL,
    prompt_config: str = DEFAULT_PROMPT_CONFIG,
    cache_path: Path | None = None,
    limit: int | None = None,
    client: VLMClient | None = None,
    usage_collector: UsageCollector | None = None,
) -> list[dict[str, str]]:
    """Run sequential predictions for a CSV and atomically write the output file."""
    repo_root = repo_root or repo_root_from_code()
    histories = load_user_history(_default_data_path(repo_root, "user_history.csv"))
    requirements = load_evidence_requirements(_default_data_path(repo_root, "evidence_requirements.csv"))
    source_rows = load_claim_rows(input_path, labeled=False)
    if limit is not None:
        source_rows = source_rows[:limit]

    cache = PredictionCache(cache_path)
    vlm_client = client or OpenAIVLMClient(usage_collector=usage_collector)
    predictions: list[dict[str, str]] = []

    LOGGER.info(
        "prediction_run_started input=%s output=%s rows=%s prompt_config=%s model=%s cache=%s limit=%s",
        input_path,
        output_path,
        len(source_rows),
        prompt_config,
        model,
        cache_path,
        limit,
    )
    for index, row in enumerate(source_rows):
        context = build_claim_context(row, index, histories, requirements)
        LOGGER.info(
            "row_started row_index=%s user_id=%s claim_object=%s image_paths=%s",
            index,
            context.user_id,
            context.claim_object,
            ";".join(context.image_paths),
        )
        try:
            images = prepare_images(repo_root, context)
        except OSError as error:
            LOGGER.warning("image_read_error row_index=%s error=%s", index, error)
            prediction = io_failure_prediction(context, f"Image file could not be read: {error}")
        except ValueError as error:
            LOGGER.warning("image_prepare_error row_index=%s error=%s", index, error)
            prediction = io_failure_prediction(context, str(error))
        else:
            LOGGER.info(
                "images_prepared row_index=%s image_count=%s image_ids=%s",
                index,
                len(images),
                ",".join(image.image_id for image in images),
            )
            prediction = review_claim(
                context,
                images,
                client=vlm_client,
                prompt_config=prompt_config,
                model=model,
                cache=cache,
            )
        validate_prediction(prediction, row, index + 1)
        predictions.append(prediction)
        LOGGER.info(
            "row_completed row_index=%s claim_status=%s valid_image=%s evidence_standard_met=%s",
            index,
            prediction["claim_status"],
            prediction["valid_image"],
            prediction["evidence_standard_met"],
        )

    validate_prediction_rows(predictions, source_rows)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    write_predictions(temp_path, predictions)
    validate_prediction_rows(load_claim_rows(temp_path, labeled=True), source_rows)
    os.replace(temp_path, output_path)
    LOGGER.info("prediction_run_completed output=%s rows=%s", output_path, len(predictions))
    return predictions
