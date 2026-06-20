# Evaluation Report

Model: `gpt-5.4`
Sample rows: 20
Sample images processed per prompt: 29
Prompt configurations compared: concise_v1, rubric_v1
Chosen final strategy: `concise_v1`

## Metrics

| prompt_config | claim_status_accuracy | core_exact_match |
|---|---:|---:|
| concise_v1 | 0.750 | 0.200 |
| rubric_v1 | 0.750 | 0.200 |

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
| risk_flags | 0.450 |
| issue_type | 0.500 |
| object_part | 0.900 |
| claim_status | 0.750 |
| claim_status_justification | 0.000 |
| supporting_image_ids | 0.650 |
| valid_image | 0.950 |
| severity | 0.300 |

### rubric_v1

| column | accuracy |
|---|---:|
| user_id | 1.000 |
| image_paths | 1.000 |
| user_claim | 1.000 |
| claim_object | 1.000 |
| evidence_standard_met | 0.800 |
| evidence_standard_met_reason | 0.000 |
| risk_flags | 0.400 |
| issue_type | 0.400 |
| object_part | 0.900 |
| claim_status | 0.750 |
| claim_status_justification | 0.000 |
| supporting_image_ids | 0.800 |
| valid_image | 0.900 |
| severity | 0.400 |

## Operational Analysis

- Model calls for this sample comparison: 40 (20 rows x 2 prompt configs).
- Model calls for the full test set with the chosen prompt: 44 uncached calls.
- Images processed for sample comparison: 58.
- Images expected for full test processing: 82.
- Token estimate source: observed API usage from 40 fresh calls and 58 images.
- Observed average usage: 2629 input tokens/call, 140 output tokens/call, 2769 total tokens/call.
- Sample estimated usage: 105162 input tokens and 5594 output tokens.
- Full-test estimated usage: 115678 input tokens and 6153 output tokens.
- Pricing assumptions: $2.5000/1M input tokens and $15.0000/1M output tokens (override with CLAIM_REVIEW_EST_INPUT_COST_PER_1M_USD and CLAIM_REVIEW_EST_OUTPUT_COST_PER_1M_USD).
- Estimated full-test processing cost: $0.3815.
- Sample runtime used for planning: 109.8s total, 2.75s/call average.
- Estimated full-test runtime at that average latency: 120.8s.
- TPM/RPM considerations: processing is sequential, so request rate is roughly one in-flight call at a time; reduce --limit during debugging if quota or rate limits are tight.
- Cache keys include prompt config, model, claim content, user history, requirements, and image hashes.
- Sample claim_status distribution: {'supported': 12, 'not_enough_information': 3, 'contradicted': 5}.
