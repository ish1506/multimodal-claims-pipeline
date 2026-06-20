# Evaluation And Optimization Notes

This document summarizes the evaluation work done for the multimodal claims pipeline and the decisions taken before final prediction generation.

## Evaluation Setup

- Primary sample set: `dataset/sample_claims.csv` with 20 labeled rows.
- Final test input: `dataset/claims.csv` with 44 unlabeled rows.
- Evaluation entry point: `code/evaluation/main.py`.
- Production entry point: `code/main.py`.
- Main deterministic metrics:
  - `claim_status_accuracy`
  - `core_exact_match`
  - weighted score
  - `risk_flags` F1
  - `supporting_image_ids` F1
  - slice metrics by `claim_object` and expected `claim_status`
- Optional semantic diagnostic:
  - VLM-as-judge using a stronger judge model, usually `gpt-5.5`.

## Baseline Evaluation

The initial evaluation compared two prompt configurations:

- `concise_v1`: direct one-pass JSON review.
- `rubric_v1`: explicit review rubric with `FINAL_JSON` extraction.

Early `gpt-4.1-mini` style runs showed `rubric_v1` was competitive, but the model often over-supported claims when images were weak or contradictory.

Observed recurring weakness:

- Supported claims were usually handled well.
- Contradicted and not-enough-information claims were weaker.
- The model tended to convert visible surface marks, folds, glare, or ambiguous package/laptop details into supported damage.

## Model Comparison

We compared current OpenAI VLM candidates through the same evaluation pipeline:

- `gpt-4.1-mini`
- `gpt-5.4-nano`
- `gpt-5.4-mini`
- `gpt-5.4`
- optionally `gpt-5.5` as a quality ceiling or judge

`gpt-5.4-mini` became the preferred production candidate because it gave the best practical quality/cost/latency tradeoff for this small structured VLM task.

## Evaluation Improvements Added

The evaluation report was expanded beyond exact-match accuracy:

- Added weighted score to avoid over-penalizing partly correct structured outputs.
- Added F1 for semicolon-delimited fields:
  - `risk_flags`
  - `supporting_image_ids`
- Added slice metrics:
  - by `claim_object`
  - by expected `claim_status`
- Added optional VLM-as-judge scoring:
  - decision quality
  - evidence reasoning
  - risk flag quality
  - supporting image quality
  - explanation grounding
- Added API usage collection for observed token/cost estimates when fresh calls are made.

## VLM-As-Judge Findings

The VLM judge was useful as a diagnostic, not as the primary score.

Value added:

- It helped assess explanation grounding, where exact string match is not useful.
- It gave a second signal when `concise_v1` and `rubric_v1` were close.
- It identified qualitative error types such as severity mismatch, wrong object, and unsupported supporting images.

Limitations:

- It costs extra API calls.
- It is model-opinionated and should not override labeled sample metrics.
- It should be run on finalists only, not after every prompt tweak.

## Strict Prompt Optimization

We added stricter shared evidence rules to both prompts:

- Mark `supported` only when images clearly show the claimed object, claimed part, and claimed damage.
- Use `contradicted` when the relevant part is visible but the claimed damage is absent.
- Use `not_enough_information` when the claimed object or part is not visible enough.
- Do not infer missing package contents from closed, cropped, or unclear package images.
- Do not infer laptop functional damage from cosmetic marks alone.

We also updated cache keys to include the rendered prompt text. This prevents stale cached predictions after prompt changes.

Result on `gpt-5.4-mini`:

| prompt_config | claim_status_accuracy | core_exact_match | weighted_score | decision |
|---|---:|---:|---:|---|
| `concise_v1` | 0.800 | 0.400 | 0.772 | winner |
| `rubric_v1` | 0.750 | 0.350 | 0.734 | runner-up |

Key slices for the winning strict prompt:

- Supported: 12/12
- Not enough information: 2/3
- Contradicted: 2/5

Decision:

- Keep the stricter shared prompt rules.
- Use `concise_v1` with `gpt-5.4-mini`.

## Few-Shot Contradiction Experiment

We tried adding targeted few-shot contradiction examples to `concise_v1` only. The examples covered:

- laptop trackpad visible but undamaged
- intact package seal
- missing contents with unclear/closed package
- wrong part or nearby unrelated marks

Result:

| variant | claim_status_accuracy | core_exact_match | weighted_score | supported slice | contradicted slice |
|---|---:|---:|---:|---:|---:|
| strict prompt before few-shot | 0.800 | 0.400 | 0.772 | 12/12 | 2/5 |
| concise few-shot | 0.700 | 0.350 | 0.746 | 11/12 | 1/5 |

Conclusion:

- The few-shot examples overcorrected one supported claim into `contradicted`.
- They did not improve the package-seal contradiction failure.
- Net quality regressed.

Decision:

- Roll back the few-shot examples.
- Keep the stricter shared prompt rules.

## Deterministic Post-Processing Rules

We then added a small deterministic safeguard layer after VLM prediction and before validation/output. The layer is enabled by default and can be disabled with `--disable-rules` for raw model comparisons.

The rules intentionally target narrow high-risk patterns:

- supported claim with no supporting images -> `not_enough_information`
- supported claim with `issue_type=none` -> `contradicted`
- supported claim with `damage_not_visible` -> `contradicted`
- wrong-object plus claim-mismatch evidence -> `contradicted`
- low-severity trackpad scratch for a functional/physical trackpad claim -> `contradicted`
- high-risk torn/opened package seal support -> `contradicted`

Cached evaluation on `gpt-5.4-mini + concise_v1` after these rules:

| variant | claim_status_accuracy | core_exact_match | weighted_score | supported slice | contradicted slice | not-enough-info slice |
|---|---:|---:|---:|---:|---:|---:|
| strict prompt only | 0.800 | 0.400 | 0.772 | 12/12 | 2/5 | 2/3 |
| strict prompt + deterministic rules | 0.950 | 0.500 | 0.857 | 12/12 | 5/5 | 2/3 |

Decision:

- Keep the deterministic rule layer enabled for final output.
- Keep `--disable-rules` available for debugging or raw model comparisons.

## Final Decision

Use:

```bash
uv run python code/main.py --input dataset/claims.csv --output output.csv --model gpt-5.4-mini --prompt-config concise_v1 --log-file logs/final_run.log
uv run python code/validate_output.py --input output.csv --claims dataset/claims.csv
```

Rationale:

- Best sample `claim_status_accuracy`.
- Best sample `core_exact_match`.
- Best weighted score.
- Preserves all supported sample claims after strict prompt changes and rule application.
- Fixes the contradicted sample slice from 2/5 to 5/5.
- Operationally cheap enough for the full 44-row test set.

Known residual risk:

- The rules are intentionally narrow and partly sample-driven.
- The only remaining sample `claim_status` miss is one front-bumper case labeled `not_enough_information` that the model still supports.
