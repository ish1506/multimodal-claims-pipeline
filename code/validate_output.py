from __future__ import annotations

import argparse
from pathlib import Path

from claim_review.pipeline import repo_root_from_code
from claim_review.validation import validate_output_file


def parse_args() -> argparse.Namespace:
    """Parse validator CLI arguments."""
    repo_root = repo_root_from_code()
    parser = argparse.ArgumentParser(description="Validate a claim prediction CSV.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--claims", type=Path, default=repo_root / "dataset" / "claims.csv")
    return parser.parse_args()


def main() -> int:
    """Validate a prediction CSV against the source claim CSV."""
    args = parse_args()
    validate_output_file(args.input, args.claims)
    print(f"Validation passed for {args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
