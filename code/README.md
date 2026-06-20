# Multimodal Claims Pipeline

Python 3.12 solution for the HackerRank Orchestrate multimodal evidence review task.

## Setup

```bash
uv sync
```

Run type checking with Pyright:

```bash
uv run pyright
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

To calibrate token and cost estimates from real API usage, run a small uncached sample:

```bash
uv run python code/evaluation/main.py --limit 5 --no-cache --log-file logs/usage_calibration.log
```

The run logs `vlm_usage` lines with OpenAI-reported prompt, completion, and total tokens. When fresh usage is recorded, the evaluation report uses observed average input/output tokens per call instead of the static token assumptions.

Use `--log-file logs/evaluation.log` to pick a stable log path for evaluation.

## Recommended Runbook

Use this sequence for a submission-quality run:

```bash
uv sync
uv run ruff check .
uv run pytest -q
uv run python code/evaluation/main.py --log-file logs/evaluation.log
uv run python code/main.py --input dataset/claims.csv --output output.csv --prompt-config rubric_v1 --log-file logs/final_run.log
uv run python code/validate_output.py --input output.csv --claims dataset/claims.csv
```

The evaluation command is only for `dataset/sample_claims.csv`; it writes sample prediction files under `code/evaluation/` and must not be used as the submitted `output.csv`. The final prediction command must read `dataset/claims.csv` and write the root-level `output.csv`.

After the full run, confirm:

```bash
uv run python code/validate_output.py --input output.csv --claims dataset/claims.csv
```

Expected result:

```text
Validation passed for output.csv
```

The final `output.csv` should contain 44 prediction rows for `dataset/claims.csv`, with `images/test/...` paths copied from the source input. If it contains 20 rows or `images/sample/...` paths, it is a sample-evaluation artifact and must be regenerated with the full prediction command.

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
