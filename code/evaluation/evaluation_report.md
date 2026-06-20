# Evaluation Report

Model: `gpt-4.1-mini`
Sample rows: 20
Sample images processed per prompt: 29
Prompt configurations compared: concise_v1, rubric_v1
Chosen final strategy: `rubric_v1`

## Metrics

| prompt_config | claim_status_accuracy | core_exact_match |
|---|---:|---:|
| concise_v1 | 0.650 | 0.250 |
| rubric_v1 | 0.750 | 0.250 |

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
| issue_type | 0.500 |
| object_part | 0.800 |
| claim_status | 0.650 |
| claim_status_justification | 0.000 |
| supporting_image_ids | 0.850 |
| valid_image | 0.850 |
| severity | 0.500 |

### rubric_v1

| column | accuracy |
|---|---:|
| user_id | 1.000 |
| image_paths | 1.000 |
| user_claim | 1.000 |
| claim_object | 1.000 |
| evidence_standard_met | 0.750 |
| evidence_standard_met_reason | 0.000 |
| risk_flags | 0.500 |
| issue_type | 0.450 |
| object_part | 0.850 |
| claim_status | 0.750 |
| claim_status_justification | 0.000 |
| supporting_image_ids | 0.700 |
| valid_image | 0.900 |
| severity | 0.600 |

## Operational Analysis

- Model calls for this sample comparison: 40 (20 rows x 2 prompt configs).
- Model calls for the full test set with the chosen prompt: 44 uncached calls.
- Images processed for sample comparison: 58.
- Images expected for full test processing: 82.
- Token estimate source: observed API usage from 10 fresh calls and 16 images.
- Observed average usage: 2555 input tokens/call, 252 output tokens/call, 2807 total tokens/call.
- Sample estimated usage: 25546 input tokens and 2523 output tokens.
- Full-test estimated usage: 112402 input tokens and 11101 output tokens.
- Pricing assumptions: $0.4000/1M input tokens and $1.6000/1M output tokens (override with CLAIM_REVIEW_EST_INPUT_COST_PER_1M_USD and CLAIM_REVIEW_EST_OUTPUT_COST_PER_1M_USD).
- Estimated full-test processing cost: $0.0627.
- Sample runtime used for planning: 47.8s total, 4.78s/call average.
- Estimated full-test runtime at that average latency: 210.1s.
- TPM/RPM considerations: processing is sequential, so request rate is roughly one in-flight call at a time; reduce --limit during debugging if quota or rate limits are tight.
- Cache keys include prompt config, model, claim content, user history, requirements, and image hashes.
- Sample claim_status distribution: {'supported': 12, 'not_enough_information': 3, 'contradicted': 5}.
