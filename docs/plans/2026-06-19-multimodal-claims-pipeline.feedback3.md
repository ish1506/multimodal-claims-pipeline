## Plan Feedback (v3)

All three major gaps from v1 and v2 are now resolved: evidence requirements lookup has a concrete rule, sequential processing is explicitly stated and justified, `valid_image` has a meaningful definition that correctly decouples image usability from claim validity, and `rubric_v1` JSON extraction has a sentinel strategy with a sensible fallback. The plan is implementation-ready.

The remaining issues are smaller, but two of them are likely to bite mid-implementation.

---

### `FINAL_JSON:` fallback needs a stricter definition

Step 7 says: "if no sentinel exists, extract the last valid JSON object rather than the first." But `rubric_v1` responses will contain partial JSON-like fragments in reasoning (e.g., `{"issue_type": "dent"}` mid-inspection). "Last valid JSON object" is ambiguous — a syntactically valid but incomplete fragment could match before the actual final answer. The fallback should specify "last JSON object containing all required output keys," not just any parseable object.

### Cache invalidation during prompt iteration

The cache key includes `prompt version`, fulfilled by the config name (`concise_v1`, `rubric_v1`). But if the prompt *text within a config* changes during development — which is likely during hackathon iteration — the cache won't invalidate since the config name didn't change. The plan should note that devs need to either rename the config (e.g., `concise_v2`) or manually clear the cache when iterating on prompt content. One line in the caching decision or README is enough.

### "Core fields" still undefined for evaluation comparison

Step 12 says "report exact-match accuracy for core fields" but never defines which fields are core. This has been an open gap across all three versions. `claim_status` is the obvious primary metric; `evidence_standard_met`, `valid_image`, and `severity` are secondary. The implementer will make a reasonable call, but naming them explicitly in the plan removes ambiguity and makes the evaluation report more defensible to judges.

### Image content-type detection: name a concrete tool

Step 5 says "detect content type from file content where possible" but leaves the approach unspecified. `imghdr` is deprecated as of Python 3.11 and removed in 3.13 — risky on 3.12 and worth avoiding. The plan should name either `filetype` (pure Python, zero system deps, easy `uv add`) or manual magic-byte inspection. Since `uv` is already managing deps, `filetype` is the simplest drop-in.

---

### Summary

The plan is in very good shape. The `FINAL_JSON:` fallback ambiguity and cache invalidation note are worth fixing before handoff; the other two are minor clarifications that reduce implementer guesswork.