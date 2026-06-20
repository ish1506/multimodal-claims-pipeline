# Evaluation Report

Model: `gpt-5.4-nano`
Sample rows: 20
Sample images processed per prompt: 29
Prompt configurations compared: rubric_v1
Chosen final strategy: `rubric_v1`

## Metrics

| prompt_config | claim_status_accuracy | core_exact_match |
|---|---:|---:|
| rubric_v1 | 0.500 | 0.150 |

## Per-Column Accuracy

### rubric_v1

| column | accuracy |
|---|---:|
| user_id | 1.000 |
| image_paths | 1.000 |
| user_claim | 1.000 |
| claim_object | 1.000 |
| evidence_standard_met | 0.650 |
| evidence_standard_met_reason | 0.000 |
| risk_flags | 0.400 |
| issue_type | 0.450 |
| object_part | 0.850 |
| claim_status | 0.500 |
| claim_status_justification | 0.000 |
| supporting_image_ids | 0.650 |
| valid_image | 0.900 |
| severity | 0.200 |

## Operational Analysis

- Model calls for this sample comparison: 20 (20 rows x 1 prompt configs).
- Model calls for the full test set with the chosen prompt: 44 uncached calls.
- Images processed for sample comparison: 29.
- Images expected for full test processing: 82.
- Token estimate source: observed API usage from 20 fresh calls and 29 images.
- Observed average usage: 2680 input tokens/call, 229 output tokens/call, 2909 total tokens/call.
- Sample estimated usage: 53601 input tokens and 4587 output tokens.
- Full-test estimated usage: 117922 input tokens and 10091 output tokens.
- Pricing assumptions: $0.2000/1M input tokens and $1.2500/1M output tokens (override with CLAIM_REVIEW_EST_INPUT_COST_PER_1M_USD and CLAIM_REVIEW_EST_OUTPUT_COST_PER_1M_USD).
- Estimated full-test processing cost: $0.0362.
- Sample runtime used for planning: 61.6s total, 3.08s/call average.
- Estimated full-test runtime at that average latency: 135.5s.
- TPM/RPM considerations: processing is sequential, so request rate is roughly one in-flight call at a time; reduce --limit during debugging if quota or rate limits are tight.
- Cache keys include prompt config, model, claim content, user history, requirements, and image hashes.
- Sample claim_status distribution: {'supported': 12, 'not_enough_information': 3, 'contradicted': 5}.
