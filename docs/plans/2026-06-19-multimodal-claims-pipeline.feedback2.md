## Plan Feedback (v2)

This is a substantially stronger plan — the improvements are real and targeted. Here's what's left worth flagging.

---

### Still unresolved from v1: the evidence requirements lookup

This is the same gap. `evidence_requirements.csv` keys on `claim_object + applies_to (issue family)`, but `applies_to` is essentially the issue type, which the VLM hasn't produced yet. "Applicable evidence requirements" in step 4 still doesn't say how you pick which rows to include before the VLM runs. The fix is simple — just commit to one approach in the plan: either include all requirements for the claim's object type (every row where `claim_object` matches or is `all`), or do a two-pass call. The former is simpler and probably fine since there are only a handful of rows per object type.

### Still no concurrency plan

The operational analysis section asks about TPM/RPM and batching strategy, but the implementation steps still describe implicit sequential processing. With 20 sample rows × 2 configs + 44 test rows = ~84 VLM calls, sequential is survivable, but the plan should at least state the concurrency approach rather than leaving it implied. Even "sequential with SDK-handled retries on 429" is a valid choice — just say it explicitly.

### `valid_image` still has no definition

The plan defines safe I/O fallback behavior (unreadable files → `valid_image=false`), but for readable images the VLM is expected to determine `valid_image`. There's no guidance in the prompt spec on what the VLM should base this on, or how it should relate to risk flags. A concrete rule would help: e.g., if `risk_flags` contains any of `{blurry_image, wrong_object, low_light_or_glare, wrong_angle}`, `valid_image` should be `false`, otherwise `true`. Whether that logic lives in the VLM prompt or in post-processing validation is worth deciding explicitly.

### `rubric_v1` chain-of-thought + JSON extraction interaction

The rubric config asks the VLM to reason step-by-step ("extract claimed issue → inspect each image → check requirements → assess flags → emit JSON"). This means there will be substantial reasoning text *before* the JSON block. The JSON extraction step needs to explicitly handle this — specifically, extracting the *last* valid JSON object (or the one following a sentinel like `"Final output:"`) rather than the first match, which might be a partial reasoning snippet. This is a distinct concern from the `concise_v1` case and should be called out in the plan.

---

### Things genuinely resolved from v1

Prompt injection defense, verbatim input column copying, canonical risk flag ordering, `supporting_image_ids` for contradicted claims, atomic output writes, the standalone validator, multi-issue collapse policy, multilingual support, and prompt versioning folded into config names are all solid additions. The plan is implementation-ready on all of those fronts.

The evidence requirements matching is the one most likely to cause real confusion mid-implementation — the implementer will hit it concretely when building step 4 and won't have guidance. Worth one more line in the plan before handing off.