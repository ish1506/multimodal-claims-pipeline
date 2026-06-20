from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from claim_review.constants import DEFAULT_MODEL, DEFAULT_PROMPT_CONFIG
from claim_review.env import load_repo_dotenv
from claim_review.logging_config import default_log_file, setup_logging
from claim_review.pipeline import repo_root_from_code, run_predictions
from claim_review.prompts import PROMPT_CONFIGS

LOGGER = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options for the production prediction run."""
    repo_root = repo_root_from_code()
    loaded_env = load_repo_dotenv(repo_root)
    parser = argparse.ArgumentParser(description="Run multimodal claim evidence review.")
    parser.add_argument("--input", type=Path, default=repo_root / "dataset" / "claims.csv")
    parser.add_argument("--output", type=Path, default=repo_root / "output.csv")
    parser.add_argument("--model", default=os.environ.get("OPENAI_VISION_MODEL", DEFAULT_MODEL))
    parser.add_argument("--prompt-config", choices=sorted(PROMPT_CONFIGS), default=DEFAULT_PROMPT_CONFIG)
    parser.add_argument("--cache", type=Path, default=repo_root / "code" / ".cache" / "claim_review_cache.json")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--disable-rules", action="store_true", help="Disable deterministic post-processing safeguards.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--log-file", type=Path, default=None)
    args = parser.parse_args(argv)
    args.loaded_env = loaded_env
    return args


def main(argv: list[str] | None = None) -> int:
    """Run the claim review CLI and return a process-style exit code."""
    args = parse_args(argv)
    repo_root = repo_root_from_code()
    log_file = setup_logging(
        log_file=args.log_file or default_log_file(repo_root, "claims_run"),
        level=args.log_level,
    )
    print(f"Logging to {log_file}", file=sys.stderr)
    if args.loaded_env:
        print(f"Loaded environment variables from .env: {', '.join(sorted(args.loaded_env))}", file=sys.stderr)
    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY is required for VLM review. Set it in the environment, "
            "and optionally set OPENAI_VISION_MODEL.",
            file=sys.stderr,
        )
        return 2
    try:
        run_predictions(
            input_path=args.input,
            output_path=args.output,
            model=args.model,
            prompt_config=args.prompt_config,
            cache_path=args.cache,
            limit=args.limit,
            apply_rules=not args.disable_rules,
        )
    except Exception as error:
        LOGGER.exception("prediction_run_failed")
        print(f"Prediction run failed: {error}", file=sys.stderr)
        print(f"See log file: {log_file}", file=sys.stderr)
        return 1
    print(f"Wrote predictions to {args.output}")
    print(f"Log file: {log_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
