# Multimodal Claims Pipeline

Python 3.12 solution for the HackerRank Orchestrate multimodal evidence review task.

## Setup

```bash
uv sync
```

Set credentials either in the shell or in a root-level `.env` file:

```bash
OPENAI_API_KEY=...
OPENAI_VISION_MODEL=gpt-4.1-mini
```

`OPENAI_VISION_MODEL` is optional. Shell environment variables take precedence over `.env` values. The default model is configured in `claim_review.constants.DEFAULT_MODEL`.

## Run Predictions

```bash
uv run python code/main.py --input dataset/claims.csv --output output.csv
```

Useful development options:

```bash
uv run python code/main.py --input dataset/sample_claims.csv --output /tmp/sample_predictions.csv --prompt-config rubric_v1 --limit 5
uv run python code/main.py --input dataset/claims.csv --output output.csv --model "$OPENAI_VISION_MODEL"
```

The pipeline fails before processing if `OPENAI_API_KEY` is missing. It does not fabricate semantic outputs without a VLM.

Runtime logs are written to stderr and to a timestamped file under `logs/` by default:

```bash
uv run python code/main.py --input dataset/claims.csv --output output.csv --log-level INFO
uv run python code/main.py --input dataset/claims.csv --output output.csv --log-file logs/final_run.log
```

The HTTP log records outgoing method/URL, response status, and duration for OpenAI requests. It intentionally does not log request bodies, image bytes, Authorization headers, or API keys.

## Evaluation

```bash
uv run python code/evaluation/main.py
```

Evaluation compares `concise_v1` and `rubric_v1` on `dataset/sample_claims.csv`, writes per-prompt sample predictions under `code/evaluation/`, and updates `code/evaluation/evaluation_report.md`.

Use `--log-file logs/evaluation.log` to pick a stable log path for evaluation.

## Validation

```bash
uv run python code/validate_output.py --input output.csv --claims dataset/claims.csv
```

Validation checks required column order, row count, verbatim copied input fields, allowed values, canonical risk flags, and supporting image IDs.

## Caching

The default runtime cache is `code/.cache/claim_review_cache.json`. Cache keys include claim content, user history, evidence requirements, image hashes, prompt config, and model name. Prompt edits should use a new prompt config name or a cleared cache.

## Submission Checklist

- Run sample evaluation and inspect `code/evaluation/evaluation_report.md`.
- Generate root-level `output.csv`.
- Validate `output.csv`.
- Zip `code/` excluding `.cache`, `.env`, `.venv`, and generated debug artifacts.
