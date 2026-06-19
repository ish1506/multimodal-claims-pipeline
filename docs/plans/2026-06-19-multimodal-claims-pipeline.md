# Multimodal Claims Pipeline Plan

## Goal

Build a Python + uv solution that reads `dataset/claims.csv`, inspects local claim images with a VLM, joins `user_history.csv` and `evidence_requirements.csv`, and writes a complete root-level `output.csv` with the exact required schema.

Success means the solution is reproducible, VLM-grounded, easy to run, and includes an evaluation workflow over `dataset/sample_claims.csv`. The implementation should stay simple: one VLM-based production path, two prompt configurations for evaluation comparison, strict validation, and clear setup errors when required credentials are missing.

## Current State

- `code/main.py` and `code/evaluation/main.py` are empty.
- No `pyproject.toml`, `uv.lock`, requirements file, or `.python-version` exists.
- Local runtime has `uv 0.11.21` and `Python 3.12.13`.
- `dataset/sample_claims.csv` has 20 labeled rows; `dataset/claims.csv` has 44 input rows.
- `dataset/output.csv` currently contains only the required header.
- API key environment variables checked during planning were unset, so the implementation must fail fast with setup guidance if VLM credentials are missing.

## Approach Options

- **Option A: VLM-only pipeline (chosen)**
  - Pros: simplest architecture, strongest visual evidence grounding, easiest judge story, no competing fallback behavior to tune.
  - Cons: requires credentials/network/model availability; runtime, cost, and rate limits must be managed.

- **Option B: VLM plus deterministic fallback**
  - Pros: can produce a schema-valid CSV without credentials; more resilient in offline environments.
  - Cons: more code paths, more tuning, and fallback output may be weak or misleading for an image-primary challenge.

- **Option C: Offline/manual-label-first packaging**
  - Pros: fastest for the small visible dataset if images are human-reviewed carefully.
  - Cons: less reproducible, weaker generality, and higher risk of appearing file-specific or hardcoded.

Decision: implement Option A. Do not add a deterministic fallback for semantic claim decisions. If no VLM credentials are configured, commands should exit with a concise error explaining which environment variable is required.

## Decisions

- Use Python 3.12 with uv-managed dependencies.
- Add root `pyproject.toml` and `uv.lock` as runtime metadata; keep all solution logic under `code/` with runnable entry points at `code/main.py` and `code/evaluation/main.py`.
- Use OpenAI-compatible VLM access by default, reading `OPENAI_API_KEY` from the environment and model name from `OPENAI_VISION_MODEL`, defaulting to a documented vision-capable model constant in code.
- Never hardcode secrets, labels from `dataset/claims.csv`, or file-specific final answers.
- Implement two VLM prompt configurations for evaluation: `concise_v1` for direct single-pass JSON review and `rubric_v1` for extract-then-inspect-then-decide review.
- Use the better-performing prompt configuration from sample evaluation for final `output.csv`.
- Use one structured VLM request per claim containing the conversation, object type, user history summary, evidence requirements, and all submitted images.
- Include evidence requirements by selecting every `evidence_requirements.csv` row where `claim_object` is either the row's object type or `all`. Do not add a two-pass VLM call just to infer `applies_to`.
- Treat `user_claim` and any text visible inside images as untrusted evidence, not instructions. The prompt must explicitly ignore requests to approve, skip review, override labels, bypass schema, or disregard images.
- Explicitly support multilingual and code-mixed claim conversations; the prompt should instruct the VLM to interpret or translate the claim before identifying the issue and object part.
- For multi-issue claims, evaluate the overall claim. For singular output fields, choose the most central claimed issue; if multiple claimed issues are supported, choose the highest-severity supported issue and mention other visible or unverifiable issues in the justification.
- Copy `user_id`, `image_paths`, `user_claim`, and `claim_object` verbatim from the source CSV. The VLM must never generate or rewrite input columns.
- Use Python's real CSV parser for all reads and writes because claim conversations may contain commas, quotes, pipes, and multiline text.
- Canonicalize `risk_flags`: `none` is exclusive; otherwise deduplicate flags and order them by the allowed-values list from `problem_statement.md`.
- For contradicted claims, `supporting_image_ids` should identify the images that support the contradiction, not only images that support the user's claim.
- Define `valid_image=false` for unreadable/corrupt files, non-original or manipulated images, severe blur/glare/cropping/obstruction, or no usable view of the claimed object set. Keep `valid_image=true` when images are technically readable and usable for automated review, even if they contradict the claim or show no damage.
- Require the VLM to return JSON matching the required output fields. Retry malformed JSON a small fixed number of times; if it still fails, stop the run and do not write a partial final output.
- For non-semantic I/O failures before a VLM call, such as missing or unreadable image files, produce only a safe reviewability result for that row: `valid_image=false`, `evidence_standard_met=false`, `claim_status=not_enough_information`, `issue_type=unknown`, `object_part=unknown`, `severity=unknown`, and `risk_flags=manual_review_required`. Do not use this path for readable images.
- Validate every prediction against the required columns and allowed values before writing `output.csv`.
- Write `output.csv` atomically by writing to a temporary file, validating that file, then renaming it into place only after validation passes.
- Process rows sequentially for v1, relying on caching plus SDK/API retry handling for transient 429 or network failures. Do not add concurrent batching unless sequential runtime proves unacceptable during implementation.
- Treat prompt text changes as cache-invalidating changes: either rename the prompt config, such as `rubric_v2`, or clear the cache before rerunning after prompt edits.
- Treat images as the source of truth; use user history only for `risk_flags` and review context.

## Diagram

```mermaid
flowchart TD
    A[claims.csv] --> B[Claim Context Builder]
    C[user_history.csv] --> B
    D[evidence_requirements.csv] --> B
    E[Local Images] --> F[VLM Request]
    B --> F
    F --> G[JSON Normalizer]
    G --> H[Schema Validator]
    H --> I[output.csv]
    J[sample_claims.csv] --> K[Evaluation Report]
    H --> K
```

## Implementation Steps

1. Create uv project metadata for Python 3.12 with dependencies for OpenAI-compatible VLM calls, `filetype`-based MIME detection, base64 image preparation, CSV handling, and lightweight CLI parsing.
2. Add shared constants for required output columns, allowed categorical values, risk flags, issue types, object parts, and severity values.
3. Implement path-safe CSV loaders and writers for claims, sample claims, user history, evidence requirements, and predictions using Python's `csv` module.
4. Implement claim context construction: derive row ID, submitted image IDs, relevant history row, all global plus object-specific evidence requirements, and the raw claim conversation.
5. Implement image preparation: resolve dataset-relative paths, read image bytes, detect content type from file content using `filetype` rather than deprecated `imghdr`, and attach all images for the claim to the VLM request.
6. Implement the two VLM prompt configurations:
   - `concise_v1`: direct single-pass claim review with final JSON output;
   - `rubric_v1`: extract claimed issue, inspect each image independently, check evidence requirements, assess risk flags, then emit final JSON;
   - instruct that images are primary evidence;
   - treat `user_claim` and text in images as untrusted evidence, not executable instructions;
   - support multilingual and code-mixed conversations;
   - define the multi-issue collapse policy;
   - define `valid_image` separately from `evidence_standard_met`;
   - require allowed values only;
   - require concise image-grounded reasons;
   - require `supporting_image_ids` to reference only submitted image filenames without extensions or `none`;
   - include sample output shape, not sample labels for test rows;
   - for `rubric_v1`, allow brief structured inspection notes but require the final answer after a `FINAL_JSON:` sentinel.
7. Implement VLM response handling with JSON extraction, schema coercion for harmless formatting differences, verbatim restoration of input columns, and bounded retries for malformed output. For `rubric_v1`, parse the JSON object after the `FINAL_JSON:` sentinel; if no sentinel exists, extract the last valid JSON object that contains all required output keys rather than the first parseable object.
8. Implement strict validation: required column order, copied input fields match the source row, allowed values, boolean strings as lowercase `true`/`false`, canonical risk flag composition, and valid supporting image IDs.
9. Implement `code/main.py` CLI:
   - default input: `dataset/claims.csv`;
   - default output: root `output.csv`;
   - optional flags: `--input`, `--output`, `--model`, `--prompt-config`, `--cache`, `--limit`;
   - fail before processing if `OPENAI_API_KEY` is missing.
10. Implement optional caching keyed by claim content, image file hashes, prompt version, and model name to avoid repeated paid calls during development. Keep v1 row processing sequential and document retry/rate-limit behavior in the evaluation report.
11. Implement `code/validate_output.py` to check final CSV shape, row count, copied input fields, allowed values, risk flag composition, supporting image IDs, and missing required values.
12. Implement `code/evaluation/main.py`:
   - run predictions on `dataset/sample_claims.csv`;
   - compare both prompt configurations;
   - compare predicted fields to labeled fields, using `claim_status` as the primary metric and `evidence_standard_met`, `valid_image`, `issue_type`, `object_part`, and `severity` as the core secondary fields;
   - report exact-match accuracy for core fields and per-column accuracy for all output fields.
13. Add `code/README.md` with uv setup, environment variables, prediction command, evaluation command, validation command, caching notes, and submission checklist.
14. Add `code/evaluation/evaluation_report.md` after running evaluation, including prompt/configuration comparison, final strategy, metrics, model calls, image count, approximate cost, runtime, and rate-limit considerations.
15. Generate final `output.csv` only after evaluation and validation pass.

## Files and Interfaces

- `pyproject.toml`: uv project metadata and script configuration.
- `code/main.py`: primary prediction CLI.
- `code/evaluation/main.py`: sample evaluation CLI.
- `code/validate_output.py`: final output validator.
- `code/README.md`: runnable instructions and environment configuration.
- `code/evaluation/evaluation_report.md`: required evaluation and operational analysis.
- `output.csv`: final predictions for all rows in `dataset/claims.csv`.

CLI contract:

```bash
uv run python code/main.py --input dataset/claims.csv --output output.csv
uv run python code/evaluation/main.py
uv run python code/main.py --input dataset/sample_claims.csv --output /tmp/sample_predictions.csv --prompt-config rubric_v1 --limit 5
uv run python code/validate_output.py --input output.csv --claims dataset/claims.csv
```

Required environment:

```bash
export OPENAI_API_KEY=...
export OPENAI_VISION_MODEL=<vision-capable-model>
```

## Validation

- `uv sync` completes.
- `uv run python code/evaluation/main.py` completes and prints sample metrics.
- Evaluation compares `concise_v1` and `rubric_v1`, and the evaluation report names the chosen final configuration.
- Evaluation reports `claim_status` as the primary metric, exact match over the named core secondary fields, and per-column accuracy for all output fields.
- `uv run python code/main.py --input dataset/claims.csv --output output.csv` writes exactly 44 prediction rows plus the header.
- `uv run python code/validate_output.py --input output.csv --claims dataset/claims.csv` passes.
- `output.csv` columns exactly match the order in `problem_statement.md`.
- `user_id`, `image_paths`, `user_claim`, and `claim_object` exactly match the corresponding source CSV row.
- Every categorical output uses allowed values.
- `risk_flags` is `none` alone or a semicolon-separated list deduplicated and sorted by the allowed-values order.
- Every `supporting_image_ids` value is either `none` or one or more submitted image filenames without extension.
- For contradicted claims with usable relevant images, `supporting_image_ids` points to images supporting the contradiction.
- `valid_image` follows the plan definition and is not automatically set false for every wrong-angle, damage-not-visible, or contradicted claim.
- `rubric_v1` responses are parsed from `FINAL_JSON:` or the last valid JSON object containing all required output keys.
- Final output writes are atomic: temporary prediction file, validation, then rename to the requested output path.
- Running without `OPENAI_API_KEY` exits nonzero with a clear setup message and does not write partial predictions.
- Manually inspect a few high-risk sample cases: wrong object, wrong angle, non-original image, cropped contents, and user-history-risk rows.

## Risks and Open Questions

- Model choice affects cost and accuracy; keep it configurable through `OPENAI_VISION_MODEL` and document the exact model used in the evaluation report.
- Some image files use modern formats despite `.jpg` extensions, so implementation should detect content type from bytes where possible.
- Use `filetype` for MIME detection. Do not use `imghdr`, which is deprecated in Python 3.11 and removed in Python 3.13.
- VLM responses can be inconsistent; retries and strict validation are required, but there is intentionally no deterministic fallback prediction path.
- Network/API failures during final generation should stop the run and preserve the last complete cached state rather than silently fabricating output.
- Safe I/O-only handling is allowed only for missing or unreadable local files. It must not replace VLM judgment for readable image claims.
- Sequential processing is the v1 default for reproducibility and simpler rate-limit handling. Concurrency can be added later only if measured runtime requires it.
- Prompt edits require a new prompt config/version name or manual cache clearing, otherwise stale cached responses can mask prompt changes.

## Handoff Notes

- Do not modify AGENTS.md onboarding/logging behavior.
- Preserve the project contract: build inside `code/`, keep `code/main.py` and `code/evaluation/main.py` as runnable entry points, and write final predictions to root `output.csv`.
- Keep the implementation small and auditable. The dataset is small, so correctness, prompt quality, validation, and evaluation matter more than generic framework complexity.
- Keep cache files, `.env` files, virtualenvs, local debug artifacts, and generated debug transcripts out of `code.zip` unless explicitly required by the final submission instructions.
- At the time this plan was amended, `docs/my-own-notes.md` and the feedback file were untracked user/context files and should not be overwritten without an explicit request.
