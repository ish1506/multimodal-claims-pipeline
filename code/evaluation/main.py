from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claim_review.constants import CORE_EVAL_FIELDS, DEFAULT_MODEL, OUTPUT_COLUMNS
from claim_review.csv_io import load_claim_rows
from claim_review.env import load_repo_dotenv
from claim_review.logging_config import default_log_file, setup_logging
from claim_review.pipeline import repo_root_from_code, run_predictions
from claim_review.prompts import PROMPT_CONFIGS
from claim_review.usage import UsageCollector

LOGGER = logging.getLogger(__name__)

EST_TEXT_INPUT_TOKENS_PER_CALL = 1200
EST_IMAGE_TOKENS_PER_IMAGE = 765
EST_OUTPUT_TOKENS_PER_CALL = 300
EST_INPUT_COST_PER_1M_USD = 0.40
EST_OUTPUT_COST_PER_1M_USD = 1.60


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


def count_images(rows: list[dict[str, str]]) -> int:
    """Count semicolon-delimited image references across CSV rows."""
    return sum(len([part for part in row["image_paths"].split(";") if part.strip()]) for row in rows)


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
        "| prompt_config | claim_status_accuracy | core_exact_match |",
        "|---|---:|---:|",
    ]
    for config, predictions in results.items():
        lines.append(
            f"| {config} | {accuracy(predictions, expected, 'claim_status'):.3f} | "
            f"{exact_match(predictions, expected, CORE_EVAL_FIELDS):.3f} |"
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

    chosen = max(
        results,
        key=lambda config: (
            accuracy(results[config], expected, "claim_status"),
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
    )
    print(f"Wrote evaluation report to {args.report}")
    print(f"Log file: {log_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
