# Evaluation Report

Model: `gpt-5.4-mini`
Sample rows: 20
Sample images processed per prompt: 29
Prompt configurations compared: concise_v1, rubric_v1
Chosen final strategy: `concise_v1`

## Metrics

| prompt_config | claim_status_accuracy | core_exact_match | weighted_score | risk_flags_f1 | supporting_image_ids_f1 |
|---|---:|---:|---:|---:|---:|
| concise_v1 | 0.800 | 0.400 | 0.772 | 0.647 | 0.850 |
| rubric_v1 | 0.750 | 0.350 | 0.734 | 0.650 | 0.783 |

## Slice Metrics

### By Claim Object

| prompt_config | claim_object | rows | claim_status_accuracy | weighted_score |
|---|---|---:|---:|---:|
| concise_v1 | car | 8 | 0.875 | 0.758 |
| concise_v1 | laptop | 6 | 0.833 | 0.850 |
| concise_v1 | package | 6 | 0.667 | 0.714 |
| rubric_v1 | car | 8 | 0.750 | 0.665 |
| rubric_v1 | laptop | 6 | 0.833 | 0.843 |
| rubric_v1 | package | 6 | 0.667 | 0.717 |

### By Expected Claim Status

| prompt_config | expected_claim_status | rows | claim_status_accuracy | weighted_score |
|---|---|---:|---:|---:|
| concise_v1 | contradicted | 5 | 0.400 | 0.445 |
| concise_v1 | not_enough_information | 3 | 0.667 | 0.562 |
| concise_v1 | supported | 12 | 1.000 | 0.961 |
| rubric_v1 | contradicted | 5 | 0.400 | 0.439 |
| rubric_v1 | not_enough_information | 3 | 0.667 | 0.562 |
| rubric_v1 | supported | 12 | 0.917 | 0.900 |

## Per-Column Accuracy

### concise_v1

| column | accuracy |
|---|---:|
| user_id | 1.000 |
| image_paths | 1.000 |
| user_claim | 1.000 |
| claim_object | 1.000 |
| evidence_standard_met | 0.800 |
| evidence_standard_met_reason | 0.000 |
| risk_flags | 0.500 |
| issue_type | 0.500 |
| object_part | 0.950 |
| claim_status | 0.800 |
| claim_status_justification | 0.000 |
| supporting_image_ids | 0.750 |
| valid_image | 0.900 |
| severity | 0.450 |

### rubric_v1

| column | accuracy |
|---|---:|
| user_id | 1.000 |
| image_paths | 1.000 |
| user_claim | 1.000 |
| claim_object | 1.000 |
| evidence_standard_met | 0.750 |
| evidence_standard_met_reason | 0.000 |
| risk_flags | 0.450 |
| issue_type | 0.450 |
| object_part | 0.950 |
| claim_status | 0.750 |
| claim_status_justification | 0.000 |
| supporting_image_ids | 0.650 |
| valid_image | 0.900 |
| severity | 0.400 |

## Operational Analysis

- Model calls for this sample comparison: 40 (20 rows x 2 prompt configs).
- Model calls for the full test set with the chosen prompt: 44 uncached calls.
- Images processed for sample comparison: 58.
- Images expected for full test processing: 82.
- Token estimate source: observed API usage from 40 fresh calls and 58 images.
- Observed average usage: 2884 input tokens/call, 169 output tokens/call, 3053 total tokens/call.
- Sample estimated usage: 115342 input tokens and 6768 output tokens.
- Full-test estimated usage: 126876 input tokens and 7445 output tokens.
- Pricing assumptions: $0.7500/1M input tokens and $4.5000/1M output tokens (override with CLAIM_REVIEW_EST_INPUT_COST_PER_1M_USD and CLAIM_REVIEW_EST_OUTPUT_COST_PER_1M_USD).
- Estimated full-test processing cost: $0.1287.
- Sample runtime used for planning: 97.3s total, 2.43s/call average.
- Estimated full-test runtime at that average latency: 107.0s.
- TPM/RPM considerations: processing is sequential, so request rate is roughly one in-flight call at a time; reduce --limit during debugging if quota or rate limits are tight.
- Cache keys include prompt config, model, claim content, user history, requirements, and image hashes.
- Sample claim_status distribution: {'supported': 12, 'not_enough_information': 3, 'contradicted': 5}.
