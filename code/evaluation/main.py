from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claim_review.constants import CORE_EVAL_FIELDS, DEFAULT_MODEL, OUTPUT_COLUMNS
from claim_review.context import build_claim_context
from claim_review.csv_io import load_claim_rows, load_evidence_requirements, load_user_history
from claim_review.env import load_repo_dotenv
from claim_review.images import PreparedImage, prepare_images
from claim_review.logging_config import default_log_file, setup_logging
from claim_review.pipeline import repo_root_from_code, run_predictions
from claim_review.prompts import PROMPT_CONFIGS
from claim_review.usage import UsageCollector
from claim_review.vlm import completion_token_limit_param, supports_custom_temperature

LOGGER = logging.getLogger(__name__)

EST_TEXT_INPUT_TOKENS_PER_CALL = 1200
EST_IMAGE_TOKENS_PER_IMAGE = 765
EST_OUTPUT_TOKENS_PER_CALL = 300

# ! config this acc to model. these are gpt-5.4-mini costs
EST_INPUT_COST_PER_1M_USD = 0.75
EST_OUTPUT_COST_PER_1M_USD = 4.5

WEIGHTED_METRIC_WEIGHTS = {
    "claim_status": 0.40,
    "evidence_standard_met": 0.15,
    "valid_image": 0.10,
    "issue_type": 0.10,
    "object_part": 0.10,
    "severity": 0.05,
    "risk_flags": 0.05,
    "supporting_image_ids": 0.05,
}

JUDGE_SCORE_FIELDS = [
    "decision_score",
    "evidence_reasoning_score",
    "risk_flag_score",
    "supporting_images_score",
]


def accuracy(predictions: list[dict[str, str]], expected: list[dict[str, str]], field: str) -> float:
    """Return exact-match accuracy for a single output field."""
    if not expected:
        return 0.0
    correct = sum(1 for predicted, actual in zip(predictions, expected) if predicted[field] == actual[field])
    return correct / len(expected)


def exact_match(predictions: list[dict[str, str]], expected: list[dict[str, str]], fields: list[str]) -> float:
    """Return row-level exact-match accuracy across several output fields."""
    if not expected:
        return 0.0
    correct = 0
    for predicted, actual in zip(predictions, expected):
        if all(predicted[field] == actual[field] for field in fields):
            correct += 1
    return correct / len(expected)


def split_semicolon_values(value: str) -> set[str]:
    """Return a set of semicolon-delimited values, treating none as empty."""
    values = {part.strip() for part in value.split(";") if part.strip()}
    values.discard("none")
    return values


def set_f1(predicted_value: str, expected_value: str) -> float:
    """Return F1 for semicolon-delimited set fields."""
    predicted = split_semicolon_values(predicted_value)
    expected_values = split_semicolon_values(expected_value)
    if not predicted and not expected_values:
        return 1.0
    if not predicted or not expected_values:
        return 0.0
    true_positive = len(predicted & expected_values)
    precision = true_positive / len(predicted)
    recall = true_positive / len(expected_values)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def average_set_f1(predictions: list[dict[str, str]], expected: list[dict[str, str]], field: str) -> float:
    """Return average F1 for a semicolon-delimited set field."""
    if not expected:
        return 0.0
    return sum(set_f1(predicted[field], actual[field]) for predicted, actual in zip(predictions, expected)) / len(expected)


def weighted_row_score(predicted: dict[str, str], actual: dict[str, str]) -> float:
    """Return weighted correctness for one prediction row."""
    total = 0.0
    for field, weight in WEIGHTED_METRIC_WEIGHTS.items():
        if field in {"risk_flags", "supporting_image_ids"}:
            total += weight * set_f1(predicted[field], actual[field])
        else:
            total += weight if predicted[field] == actual[field] else 0.0
    return total


def weighted_score(predictions: list[dict[str, str]], expected: list[dict[str, str]]) -> float:
    """Return average weighted score across rows."""
    if not expected:
        return 0.0
    return sum(weighted_row_score(predicted, actual) for predicted, actual in zip(predictions, expected)) / len(expected)


def count_images(rows: list[dict[str, str]]) -> int:
    """Count semicolon-delimited image references across CSV rows."""
    return sum(len([part for part in row["image_paths"].split(";") if part.strip()]) for row in rows)


def grouped_metrics(
    predictions: list[dict[str, str]],
    expected: list[dict[str, str]],
    group_field: str,
) -> list[tuple[str, int, float, float]]:
    """Return status accuracy and weighted score grouped by an expected-row field."""
    groups = sorted({row[group_field] for row in expected})
    metrics = []
    for group in groups:
        pairs = [(predicted, actual) for predicted, actual in zip(predictions, expected) if actual[group_field] == group]
        if not pairs:
            continue
        group_predictions = [predicted for predicted, _ in pairs]
        group_expected = [actual for _, actual in pairs]
        metrics.append(
            (
                group,
                len(group_expected),
                accuracy(group_predictions, group_expected, "claim_status"),
                weighted_score(group_predictions, group_expected),
            )
        )
    return metrics


def float_env(name: str, default: float) -> float:
    """Read a float environment override, falling back on invalid values."""
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        LOGGER.warning("invalid_float_env name=%s value=%r default=%s", name, os.environ.get(name), default)
        return default


def estimate_tokens_and_cost(
    *,
    calls: int,
    images: int,
    observed_usage: dict[str, float] | None = None,
) -> dict[str, float]:
    """Estimate token usage and cost from explicit, configurable assumptions."""
    input_cost = float_env("CLAIM_REVIEW_EST_INPUT_COST_PER_1M_USD", EST_INPUT_COST_PER_1M_USD)
    output_cost = float_env("CLAIM_REVIEW_EST_OUTPUT_COST_PER_1M_USD", EST_OUTPUT_COST_PER_1M_USD)
    if observed_usage is not None:
        input_tokens_per_call = observed_usage["prompt_tokens_per_call"]
        output_tokens_per_call = observed_usage["completion_tokens_per_call"]
        estimated_input_tokens = calls * input_tokens_per_call
        estimated_output_tokens = calls * output_tokens_per_call
        text_tokens = 0.0
        image_tokens = 0.0
    else:
        text_tokens = float_env("CLAIM_REVIEW_EST_TEXT_INPUT_TOKENS_PER_CALL", EST_TEXT_INPUT_TOKENS_PER_CALL)
        image_tokens = float_env("CLAIM_REVIEW_EST_IMAGE_TOKENS_PER_IMAGE", EST_IMAGE_TOKENS_PER_IMAGE)
        output_tokens_per_call = float_env("CLAIM_REVIEW_EST_OUTPUT_TOKENS_PER_CALL", EST_OUTPUT_TOKENS_PER_CALL)
        estimated_input_tokens = (calls * text_tokens) + (images * image_tokens)
        estimated_output_tokens = calls * output_tokens_per_call

    estimated_cost = (estimated_input_tokens / 1_000_000 * input_cost) + (
        estimated_output_tokens / 1_000_000 * output_cost
    )
    return {
        "text_tokens_per_call": text_tokens,
        "image_tokens_per_image": image_tokens,
        "input_tokens_per_call": estimated_input_tokens / calls if calls else 0.0,
        "output_tokens_per_call": estimated_output_tokens / calls if calls else 0.0,
        "input_cost_per_1m": input_cost,
        "output_cost_per_1m": output_cost,
        "input_tokens": estimated_input_tokens,
        "output_tokens": estimated_output_tokens,
        "cost": estimated_cost,
    }


def render_prediction_for_judge(prediction: dict[str, str]) -> dict[str, str]:
    """Keep the judge payload focused on generated fields."""
    return {column: prediction[column] for column in OUTPUT_COLUMNS if column not in {"user_id", "image_paths", "user_claim", "claim_object"}}


def build_judge_prompt(
    *,
    source_row: dict[str, str],
    expected_row: dict[str, str],
    prediction: dict[str, str],
    prompt_config: str,
) -> str:
    """Build the VLM-as-judge prompt for one sample prediction."""
    payload = {
        "task": "Judge a multimodal damage-claim prediction against the images and labeled sample answer.",
        "prompt_config_under_review": prompt_config,
        "input_claim": {
            "user_id": source_row["user_id"],
            "claim_object": source_row["claim_object"],
            "image_paths": source_row["image_paths"],
            "user_claim": source_row["user_claim"],
        },
        "expected_labeled_answer": render_prediction_for_judge(expected_row),
        "candidate_prediction": render_prediction_for_judge(prediction),
        "score_scale": "Use integer scores from 1 to 5, where 5 is correct, image-grounded, and complete.",
        "required_output": {
            "decision_score": 5,
            "evidence_reasoning_score": 5,
            "risk_flag_score": 5,
            "supporting_images_score": 5,
            "explanation_grounded": True,
            "major_error_type": "none",
            "notes": "One short sentence.",
        },
    }
    return (
        "You are an impartial evaluator for an insurance-style multimodal evidence review system. "
        "Inspect the attached images yourself. Use the labeled expected answer as the reference, but also "
        "penalize predictions whose explanations are not grounded in the visible images. Return exactly one JSON object.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def coerce_judge_result(raw: dict[str, Any], *, row_index: int, prompt_config: str) -> dict[str, str]:
    """Normalize one judge JSON result into string fields for reporting."""
    result = {
        "row_index": str(row_index),
        "prompt_config": prompt_config,
        "decision_score": str(raw.get("decision_score", "")),
        "evidence_reasoning_score": str(raw.get("evidence_reasoning_score", "")),
        "risk_flag_score": str(raw.get("risk_flag_score", "")),
        "supporting_images_score": str(raw.get("supporting_images_score", "")),
        "explanation_grounded": str(raw.get("explanation_grounded", "")).lower(),
        "major_error_type": str(raw.get("major_error_type", "other")).strip() or "other",
        "notes": str(raw.get("notes", "")).strip(),
    }
    for field in JUDGE_SCORE_FIELDS:
        try:
            score = int(float(result[field]))
        except ValueError:
            score = 1
        result[field] = str(min(5, max(1, score)))
    if result["explanation_grounded"] not in {"true", "false"}:
        result["explanation_grounded"] = "false"
    return result


class VLMJudgeClient:
    """Small OpenAI-backed judge used only for optional sample evaluation."""

    def __init__(self) -> None:
        from openai import OpenAI

        self._client = OpenAI()

    def judge(
        self,
        *,
        source_row: dict[str, str],
        expected_row: dict[str, str],
        prediction: dict[str, str],
        images: list[PreparedImage],
        prompt_config: str,
        judge_model: str,
        row_index: int,
    ) -> dict[str, str]:
        """Judge one prediction with the source images attached."""
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": build_judge_prompt(
                    source_row=source_row,
                    expected_row=expected_row,
                    prediction=prediction,
                    prompt_config=prompt_config,
                ),
            }
        ]
        for image in images:
            content.append({"type": "image_url", "image_url": {"url": image.data_url, "detail": "high"}})

        request: dict[str, Any] = {
            "model": judge_model,
            "messages": [{"role": "user", "content": content}],
            completion_token_limit_param(judge_model): 800,
            "response_format": {"type": "json_object"},
        }
        if supports_custom_temperature(judge_model):
            request["temperature"] = 0
        response = self._client.chat.completions.create(**request)
        try:
            raw = json.loads(response.choices[0].message.content or "{}")
        except json.JSONDecodeError as error:
            raise ValueError(f"Judge returned invalid JSON for row {row_index + 1}") from error
        if not isinstance(raw, dict):
            raise ValueError(f"Judge returned non-object JSON for row {row_index + 1}")
        LOGGER.info(
            "judge_completed row_index=%s prompt_config=%s judge_model=%s image_count=%s",
            row_index,
            prompt_config,
            judge_model,
            len(images),
        )
        return coerce_judge_result(raw, row_index=row_index, prompt_config=prompt_config)


def run_judge_evaluation(
    *,
    repo_root: Path,
    source_rows: list[dict[str, str]],
    expected: list[dict[str, str]],
    results: dict[str, list[dict[str, str]]],
    judge_model: str,
    judge_limit: int | None,
) -> dict[str, list[dict[str, str]]]:
    """Run VLM-as-judge over generated sample predictions."""
    histories = load_user_history(repo_root / "dataset" / "user_history.csv")
    requirements = load_evidence_requirements(repo_root / "dataset" / "evidence_requirements.csv")
    judge_client = VLMJudgeClient()
    judged_rows = len(expected) if judge_limit is None else min(len(expected), judge_limit)
    judge_results: dict[str, list[dict[str, str]]] = {config: [] for config in results}
    for row_index, source_row in enumerate(source_rows[:judged_rows]):
        context = build_claim_context(source_row, row_index, histories, requirements)
        images = prepare_images(repo_root, context)
        for config, predictions in results.items():
            judge_results[config].append(
                judge_client.judge(
                    source_row=source_row,
                    expected_row=expected[row_index],
                    prediction=predictions[row_index],
                    images=images,
                    prompt_config=config,
                    judge_model=judge_model,
                    row_index=row_index,
                )
            )
    return judge_results


def average_judge_score(rows: list[dict[str, str]], field: str) -> float:
    """Average one integer judge score field."""
    if not rows:
        return 0.0
    return sum(float(row[field]) for row in rows) / len(rows)


def grounded_rate(rows: list[dict[str, str]]) -> float:
    """Return fraction of judge rows whose explanation is grounded."""
    if not rows:
        return 0.0
    return sum(1 for row in rows if row["explanation_grounded"] == "true") / len(rows)


def write_report(
    path: Path,
    *,
    model: str,
    expected: list[dict[str, str]],
    test_rows: list[dict[str, str]],
    results: dict[str, list[dict[str, str]]],
    chosen: str,
    runtime_seconds: float,
    usage_summary: dict[str, float] | None = None,
    judge_model: str | None = None,
    judge_results: dict[str, list[dict[str, str]]] | None = None,
) -> None:
    """Write the sample evaluation report with metrics and operational notes."""
    sample_calls = len(expected) * len(results)
    sample_images = count_images(expected) * len(results)
    test_calls = len(test_rows)
    test_images = count_images(test_rows)
    sample_estimates = estimate_tokens_and_cost(calls=sample_calls, images=sample_images, observed_usage=usage_summary)
    test_estimates = estimate_tokens_and_cost(calls=test_calls, images=test_images, observed_usage=usage_summary)
    average_seconds_per_call = runtime_seconds / sample_calls if sample_calls else 0.0
    estimated_test_runtime_seconds = average_seconds_per_call * test_calls

    lines = [
        "# Evaluation Report",
        "",
        f"Model: `{model}`",
        f"Sample rows: {len(expected)}",
        f"Sample images processed per prompt: {count_images(expected)}",
        f"Prompt configurations compared: {', '.join(sorted(results))}",
        f"Chosen final strategy: `{chosen}`",
        "",
        "## Metrics",
        "",
        "| prompt_config | claim_status_accuracy | core_exact_match | weighted_score | risk_flags_f1 | supporting_image_ids_f1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for config, predictions in results.items():
        lines.append(
            f"| {config} | {accuracy(predictions, expected, 'claim_status'):.3f} | "
            f"{exact_match(predictions, expected, CORE_EVAL_FIELDS):.3f} | "
            f"{weighted_score(predictions, expected):.3f} | "
            f"{average_set_f1(predictions, expected, 'risk_flags'):.3f} | "
            f"{average_set_f1(predictions, expected, 'supporting_image_ids'):.3f} |"
        )

    lines.extend(
        [
            "",
            "## Slice Metrics",
            "",
            "### By Claim Object",
            "",
            "| prompt_config | claim_object | rows | claim_status_accuracy | weighted_score |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for config, predictions in results.items():
        for group, row_count, status_accuracy, score in grouped_metrics(predictions, expected, "claim_object"):
            lines.append(f"| {config} | {group} | {row_count} | {status_accuracy:.3f} | {score:.3f} |")

    lines.extend(
        [
            "",
            "### By Expected Claim Status",
            "",
            "| prompt_config | expected_claim_status | rows | claim_status_accuracy | weighted_score |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for config, predictions in results.items():
        for group, row_count, status_accuracy, score in grouped_metrics(predictions, expected, "claim_status"):
            lines.append(f"| {config} | {group} | {row_count} | {status_accuracy:.3f} | {score:.3f} |")

    if judge_results is not None:
        lines.extend(
            [
                "",
                "## VLM Judge Metrics",
                "",
                f"Judge model: `{judge_model}`",
                "",
                "| prompt_config | judged_rows | decision | evidence_reasoning | risk_flags | supporting_images | grounded_rate | top_error_types |",
                "|---|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for config, rows in judge_results.items():
            error_counts = Counter(row["major_error_type"] for row in rows if row["major_error_type"] != "none")
            top_errors = "; ".join(f"{error}:{count}" for error, count in error_counts.most_common(3)) or "none"
            lines.append(
                f"| {config} | {len(rows)} | "
                f"{average_judge_score(rows, 'decision_score'):.2f} | "
                f"{average_judge_score(rows, 'evidence_reasoning_score'):.2f} | "
                f"{average_judge_score(rows, 'risk_flag_score'):.2f} | "
                f"{average_judge_score(rows, 'supporting_images_score'):.2f} | "
                f"{grounded_rate(rows):.3f} | {top_errors} |"
            )

    lines.extend(["", "## Per-Column Accuracy", ""])
    for config, predictions in results.items():
        lines.extend([f"### {config}", "", "| column | accuracy |", "|---|---:|"])
        for column in OUTPUT_COLUMNS:
            lines.append(f"| {column} | {accuracy(predictions, expected, column):.3f} |")
        lines.append("")

    claim_status_counts = Counter(row["claim_status"] for row in expected)
    lines.extend(
        [
            "## Operational Analysis",
            "",
            f"- Model calls for this sample comparison: {sample_calls} ({len(expected)} rows x {len(results)} prompt configs).",
            f"- Model calls for the full test set with the chosen prompt: {test_calls} uncached calls.",
            f"- Images processed for sample comparison: {sample_images}.",
            f"- Images expected for full test processing: {test_images}.",
        ]
    )
    if usage_summary is not None:
        lines.extend(
            [
                "- Token estimate source: observed API usage from "
                f"{usage_summary['calls']:.0f} fresh calls and {usage_summary['images']:.0f} images.",
                "- Observed average usage: "
                f"{usage_summary['prompt_tokens_per_call']:.0f} input tokens/call, "
                f"{usage_summary['completion_tokens_per_call']:.0f} output tokens/call, "
                f"{usage_summary['total_tokens_per_call']:.0f} total tokens/call.",
            ]
        )
    else:
        lines.append(
            "- Token estimate source: static assumptions because this evaluation did not record fresh API usage."
        )
        lines.append(
            "- Token estimate assumptions: "
            f"{sample_estimates['text_tokens_per_call']:.0f} text input tokens/call, "
            f"{sample_estimates['image_tokens_per_image']:.0f} image tokens/image, "
            f"{sample_estimates['output_tokens_per_call']:.0f} output tokens/call."
        )

    lines.extend(
        [
            "- Sample estimated usage: "
            f"{sample_estimates['input_tokens']:.0f} input tokens and {sample_estimates['output_tokens']:.0f} output tokens.",
            "- Full-test estimated usage: "
            f"{test_estimates['input_tokens']:.0f} input tokens and {test_estimates['output_tokens']:.0f} output tokens.",
            "- Pricing assumptions: "
            f"${sample_estimates['input_cost_per_1m']:.4f}/1M input tokens and "
            f"${sample_estimates['output_cost_per_1m']:.4f}/1M output tokens "
            "(override with CLAIM_REVIEW_EST_INPUT_COST_PER_1M_USD and CLAIM_REVIEW_EST_OUTPUT_COST_PER_1M_USD).",
            f"- Estimated full-test processing cost: ${test_estimates['cost']:.4f}.",
            f"- Sample runtime used for planning: {runtime_seconds:.1f}s total, {average_seconds_per_call:.2f}s/call average.",
            f"- Estimated full-test runtime at that average latency: {estimated_test_runtime_seconds:.1f}s.",
            "- TPM/RPM considerations: processing is sequential, so request rate is roughly one in-flight call at a time; "
            "reduce --limit during debugging if quota or rate limits are tight.",
            "- Cache keys include prompt config, model, claim content, user history, requirements, and image hashes.",
            f"- Sample claim_status distribution: {dict(claim_status_counts)}.",
        ]
    )
    if judge_results is not None:
        judge_calls = sum(len(rows) for rows in judge_results.values())
        lines.append(
            f"- VLM judge calls: {judge_calls} using {judge_model}; these are evaluation-only calls and are not part of production processing."
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options for sample evaluation."""
    repo_root = repo_root_from_code()
    loaded_env = load_repo_dotenv(repo_root)
    parser = argparse.ArgumentParser(description="Evaluate prompt configs on sample_claims.csv.")
    parser.add_argument("--model", default=os.environ.get("OPENAI_VISION_MODEL", DEFAULT_MODEL))
    parser.add_argument("--prompt-configs", nargs="+", choices=sorted(PROMPT_CONFIGS), default=["concise_v1", "rubric_v1"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report", type=Path, default=repo_root / "code" / "evaluation" / "evaluation_report.md")
    parser.add_argument("--no-cache", action="store_true", help="Force fresh VLM calls so API usage can be measured.")
    parser.add_argument("--judge-model", default=None, help="Optional VLM-as-judge model for semantic sample scoring.")
    parser.add_argument("--judge-limit", type=int, default=None, help="Limit rows judged per prompt config to control cost.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--log-file", type=Path, default=None)
    args = parser.parse_args(argv)
    args.loaded_env = loaded_env
    return args


def main(argv: list[str] | None = None) -> int:
    """Run prompt comparison on sample claims and return an exit code."""
    args = parse_args(argv)
    repo_root = repo_root_from_code()
    log_file = setup_logging(
        log_file=args.log_file or default_log_file(repo_root, "evaluation"),
        level=args.log_level,
    )
    print(f"Logging to {log_file}", file=sys.stderr)
    if args.loaded_env:
        print(f"Loaded environment variables from .env: {', '.join(sorted(args.loaded_env))}", file=sys.stderr)
    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY is required for sample evaluation because both prompt configs use VLM review.",
            file=sys.stderr,
        )
        return 2

    sample_path = repo_root / "dataset" / "sample_claims.csv"
    test_path = repo_root / "dataset" / "claims.csv"
    expected = load_claim_rows(sample_path, labeled=True)
    if args.limit is not None:
        expected = expected[: args.limit]
    source_rows = load_claim_rows(sample_path, labeled=False)
    if args.limit is not None:
        source_rows = source_rows[: args.limit]
    test_rows = load_claim_rows(test_path, labeled=False)

    results: dict[str, list[dict[str, str]]] = {}
    usage_collector = UsageCollector()
    started_at = time.perf_counter()
    for config in args.prompt_configs:
        output_path = repo_root / "code" / "evaluation" / f"sample_predictions_{config}.csv"
        try:
            predictions = run_predictions(
                input_path=sample_path,
                output_path=output_path,
                model=args.model,
                prompt_config=config,
                cache_path=None if args.no_cache else repo_root / "code" / ".cache" / f"claim_review_cache_{config}.json",
                limit=args.limit,
                usage_collector=usage_collector,
            )
        except Exception as error:
            LOGGER.exception("evaluation_run_failed prompt_config=%s", config)
            print(f"Evaluation failed for {config}: {error}", file=sys.stderr)
            print(f"See log file: {log_file}", file=sys.stderr)
            return 1
        results[config] = predictions
        print(
            f"{config}: claim_status_accuracy={accuracy(predictions, expected, 'claim_status'):.3f} "
            f"core_exact_match={exact_match(predictions, expected, CORE_EVAL_FIELDS):.3f}"
        )

    judge_results = None
    if args.judge_model:
        try:
            judge_results = run_judge_evaluation(
                repo_root=repo_root,
                source_rows=source_rows,
                expected=expected,
                results=results,
                judge_model=args.judge_model,
                judge_limit=args.judge_limit,
            )
        except Exception as error:
            LOGGER.exception("judge_evaluation_failed judge_model=%s", args.judge_model)
            print(f"Judge evaluation failed: {error}", file=sys.stderr)
            print(f"See log file: {log_file}", file=sys.stderr)
            return 1

    chosen = max(
        results,
        key=lambda config: (
            accuracy(results[config], expected, "claim_status"),
            weighted_score(results[config], expected),
            exact_match(results[config], expected, CORE_EVAL_FIELDS),
        ),
    )
    runtime_seconds = time.perf_counter() - started_at
    write_report(
        args.report,
        model=args.model,
        expected=expected,
        test_rows=test_rows,
        results=results,
        chosen=chosen,
        runtime_seconds=runtime_seconds,
        usage_summary=usage_collector.summary(),
        judge_model=args.judge_model,
        judge_results=judge_results,
    )
    print(f"Wrote evaluation report to {args.report}")
    print(f"Log file: {log_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
