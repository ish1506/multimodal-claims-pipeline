# Evaluation Report

Model: `gpt-4.1-mini`
Sample rows: 20
Sample images processed per prompt: 29
Prompt configurations compared: concise_v1, rubric_v1
Chosen final strategy: `rubric_v1`

## Metrics

| prompt_config | claim_status_accuracy | core_exact_match |
|---|---:|---:|
| concise_v1 | 0.700 | 0.300 |
| rubric_v1 | 0.750 | 0.300 |

## Per-Column Accuracy

### concise_v1

| column | accuracy |
|---|---:|
| user_id | 1.000 |
| image_paths | 1.000 |
| user_claim | 1.000 |
| claim_object | 1.000 |
| evidence_standard_met | 0.900 |
| evidence_standard_met_reason | 0.000 |
| risk_flags | 0.550 |
| issue_type | 0.550 |
| object_part | 0.800 |
| claim_status | 0.700 |
| claim_status_justification | 0.000 |
| supporting_image_ids | 0.900 |
| valid_image | 0.850 |
| severity | 0.550 |

### rubric_v1

| column | accuracy |
|---|---:|
| user_id | 1.000 |
| image_paths | 1.000 |
| user_claim | 1.000 |
| claim_object | 1.000 |
| evidence_standard_met | 0.850 |
| evidence_standard_met_reason | 0.000 |
| risk_flags | 0.550 |
| issue_type | 0.500 |
| object_part | 0.850 |
| claim_status | 0.750 |
| claim_status_justification | 0.000 |
| supporting_image_ids | 0.800 |
| valid_image | 0.900 |
| severity | 0.600 |

## Operational Analysis

- Model calls for this sample comparison: 40.
- Model calls for the test set with the chosen prompt: one per uncached claim row.
- Images processed for sample comparison: 58.
- Token usage depends on image encoding and model accounting; prompts are compact JSON contexts plus submitted images.
- Cost estimate should be filled with the actual model pricing after a real run.
- Runtime is sequential by design for reproducibility and simpler RPM/TPM handling.
- Cache keys include prompt config, model, claim content, user history, requirements, and image hashes.
- Sample claim_status distribution: {'supported': 13, 'contradicted': 5, 'not_enough_information': 2}.
