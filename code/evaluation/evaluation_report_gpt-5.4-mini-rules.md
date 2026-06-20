# Evaluation Report

Model: `gpt-5.4-mini`
Sample rows: 20
Sample images processed per prompt: 29
Prompt configurations compared: concise_v1
Chosen final strategy: `concise_v1`
Deterministic post-processing rules: enabled

## Metrics

| prompt_config | claim_status_accuracy | core_exact_match | weighted_score | risk_flags_f1 | supporting_image_ids_f1 |
|---|---:|---:|---:|---:|---:|
| concise_v1 | 0.950 | 0.500 | 0.857 | 0.695 | 0.850 |

## Slice Metrics

### By Claim Object

| prompt_config | claim_object | rows | claim_status_accuracy | weighted_score |
|---|---|---:|---:|---:|
| concise_v1 | car | 8 | 0.875 | 0.758 |
| concise_v1 | laptop | 6 | 1.000 | 0.946 |
| concise_v1 | package | 6 | 1.000 | 0.901 |

### By Expected Claim Status

| prompt_config | expected_claim_status | rows | claim_status_accuracy | weighted_score |
|---|---|---:|---:|---:|
| concise_v1 | contradicted | 5 | 1.000 | 0.785 |
| concise_v1 | not_enough_information | 3 | 0.667 | 0.562 |
| concise_v1 | supported | 12 | 1.000 | 0.961 |

## Per-Column Accuracy

### concise_v1

| column | accuracy |
|---|---:|
| user_id | 1.000 |
| image_paths | 1.000 |
| user_claim | 1.000 |
| claim_object | 1.000 |
| evidence_standard_met | 0.850 |
| evidence_standard_met_reason | 0.000 |
| risk_flags | 0.500 |
| issue_type | 0.600 |
| object_part | 0.950 |
| claim_status | 0.950 |
| claim_status_justification | 0.000 |
| supporting_image_ids | 0.750 |
| valid_image | 0.900 |
| severity | 0.550 |

## Operational Analysis

- Model calls for this sample comparison: 20 (20 rows x 1 prompt configs).
- Model calls for the full test set with the chosen prompt: 44 uncached calls.
- Images processed for sample comparison: 29.
- Images expected for full test processing: 82.
- Token estimate source: static assumptions because this evaluation did not record fresh API usage.
- Token estimate assumptions: 1200 text input tokens/call, 765 image tokens/image, 300 output tokens/call.
- Sample estimated usage: 46185 input tokens and 6000 output tokens.
- Full-test estimated usage: 115530 input tokens and 13200 output tokens.
- Pricing assumptions: $0.7500/1M input tokens and $4.5000/1M output tokens (override with CLAIM_REVIEW_EST_INPUT_COST_PER_1M_USD and CLAIM_REVIEW_EST_OUTPUT_COST_PER_1M_USD).
- Estimated full-test processing cost: $0.1460.
- Sample runtime used for planning: 0.1s total, 0.01s/call average.
- Estimated full-test runtime at that average latency: 0.3s.
- TPM/RPM considerations: processing is sequential, so request rate is roughly one in-flight call at a time; reduce --limit during debugging if quota or rate limits are tight.
- Cache keys include prompt config, rendered prompt text, model, claim content, user history, requirements, and image hashes.
- Sample claim_status distribution: {'supported': 12, 'not_enough_information': 3, 'contradicted': 5}.
