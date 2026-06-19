from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claim_review.constants import CORE_EVAL_FIELDS, DEFAULT_MODEL, OUTPUT_COLUMNS
from claim_review.csv_io import load_claim_rows
from claim_review.env import load_repo_dotenv
from claim_review.logging_config import default_log_file, setup_logging
from claim_review.pipeline import repo_root_from_code, run_predictions
from claim_review.prompts import PROMPT_CONFIGS

LOGGER = logging.getLogger(__name__)


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


def write_report(
    path: Path,
    *,
    model: str,
    expected: list[dict[str, str]],
    results: dict[str, list[dict[str, str]]],
    chosen: str,
) -> None:
    """Write the sample evaluation report with metrics and operational notes."""
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
            f"- Model calls for this sample comparison: {len(expected) * len(results)}.",
            "- Model calls for the test set with the chosen prompt: one per uncached claim row.",
            f"- Images processed for sample comparison: {count_images(expected) * len(results)}.",
            "- Token usage depends on image encoding and model accounting; prompts are compact JSON contexts plus submitted images.",
            "- Cost estimate should be filled with the actual model pricing after a real run.",
            "- Runtime is sequential by design for reproducibility and simpler RPM/TPM handling.",
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
    expected = load_claim_rows(sample_path, labeled=True)
    if args.limit is not None:
        expected = expected[: args.limit]

    results: dict[str, list[dict[str, str]]] = {}
    for config in args.prompt_configs:
        output_path = repo_root / "code" / "evaluation" / f"sample_predictions_{config}.csv"
        try:
            predictions = run_predictions(
                input_path=sample_path,
                output_path=output_path,
                model=args.model,
                prompt_config=config,
                cache_path=repo_root / "code" / ".cache" / f"claim_review_cache_{config}.json",
                limit=args.limit,
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
    write_report(args.report, model=args.model, expected=expected, results=results, chosen=chosen)
    print(f"Wrote evaluation report to {args.report}")
    print(f"Log file: {log_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
