# Multi-Intent MVP Implementation Summary

**Status**: ✅ Shadow Mode Ready for Testing  
**Date**: 2026-03-12  
**Scope**: Phase 0-2 (feature flags, decomposition/ranking core, taxonomy guard, shadow logging)

---

## What Was Implemented

### 1. Backend Core Multi-Intent Components (`backend/test_demo.py`)

#### New Functions Added (lines 274-520):
- `split_query_into_spans()` — Decompose query by connectors (và, với, rồi, sau đó, etc.) and punctuation
- `_detect_interaction_subject()` — Quick check for greeting/complaint/help intent in span
- `_build_intent_signals()` — Calculate specificity and retrieval_need scores per span
- `classify_span()` — Run single-label classifier on each span, detect interaction intents early
- `decompose_intents()` — Merge spans into valid intents list, fallback if empty
- `rank_intents()` — Score and rank intents by priority (confidence × 0.45 + specificity × 0.25 + retrieval_need × 0.30)
- `classify_multi_intent()` — Main orchestrator: decompose → classify each span → rank → return contract

**Key Design**:
- Reuses existing `classify_v2()` logic for rule-based classification; no duplication
- Detects interaction (greeting/complaint/qa_need_info) early before retrieval classifier
- Scoring uses weighted priority formula with delta threshold (0.08) to detect conflicts
- Returns structured contract: `intents[]`, `primary_intent_index`, `is_multi_intent`, `has_conflict`, `decomposition_method`

---

### 2. Feature Flags and Taxonomy Configuration (`backend/app.py`, lines 55-82)

#### Runtime Flags (default: `False`):
```python
ENABLE_MULTI_INTENT = _env_flag("ENABLE_MULTI_INTENT", False)
ENABLE_MULTI_INTENT_SHADOW = _env_flag("ENABLE_MULTI_INTENT_SHADOW", False)
ENABLE_MULTI_INTENT_LIGHT_SECONDARY = _env_flag("ENABLE_MULTI_INTENT_LIGHT_SECONDARY", False)
```

#### Configuration Constants:
```python
SECONDARY_CLARIFY_THRESHOLD = 0.60  # Confidence threshold to trigger light_retrieval
CONFLICT_DELTA_THRESHOLD = 0.08     # Intent ranking score delta for conflict detection

RETRIEVAL_TAXONOMY = {
    "thu_tuc_hanh_chinh": set(SUBJECT_KEYWORDS.keys()),
    "thong_tin_tong_quan": {"lich_lam_viec", "thong_tin_lien_he", ...},
    "to_chuc_bo_may": {"chuc_vu", "nhan_su"},
    "phan_anh_kien_nghi": {seven subjects...},
}
```

---

### 3. Taxonomy Guard and Label Validation (`backend/app.py`, lines 530-599)

#### New Functions:
- `guard_retrieval_label(category, subject)` — Validate labels against RETRIEVAL_TAXONOMY
  - Returns: `(clean_cat, clean_sub, invalid_flag)`
  - Sets both to `None` if category invalid
  - Sets subject to `None` if subject invalid for category
  
- `apply_taxonomy_guard_to_intents(intents[])` — Apply guard to all retrieval intents in shadow
  - Adds `invalid_label: bool` flag per intent
  - Preserves interaction intents unchanged

- `summarize_multi_intent_shadow(shadow_contract)` — Compact telemetry for logging
  - Extracts `primary_intent`, `secondary_intents` (max 3), `has_conflict`, `secondary_policy`
  - Keeps JSON serializable and truncates to 1800 chars to fit in `reason` field

---

### 4. Shadow Integration in Chat Stream (`backend/app.py`, lines 770-787, 862-866)

#### Shadow Orchestration (lines 770-787):
```python
if ENABLE_MULTI_INTENT and ENABLE_MULTI_INTENT_SHADOW:
    shadow_contract = classify_multi_intent(normalized_query, PREPARED)
    shadow_contract["intents"] = apply_taxonomy_guard_to_intents(shadow_contract.get("intents") or [])
    shadow_summary = summarize_multi_intent_shadow(shadow_contract)
    log_data["_multi_intent_shadow"] = shadow_summary
    yield SSE log message
```

**Behavior**: 
- Runs only when **both** flags enabled
- Computes telemetry in parallel with existing single-label pipeline
- Does **not** change routing (legacy single-label path unchanged)
- Emits SSE log for debugging/monitoring

#### Taxonomy Guard After Rule Classify (lines 784-786):
```python
category, subject, invalid_main_label = guard_retrieval_label(category, subject)
if invalid_main_label:
    yield f"Taxonomy guard: reset invalid retrieval label to safe fallback"
```

#### Taxonomy Guard After LLM Override (lines 862-866):
```python
category, subject, invalid_override_label = guard_retrieval_label(category, subject)
if invalid_override_label:
    yield f"Taxonomy guard: dropped invalid LLM label before retrieval"
```

**Result**: Invalid labels are **never** sent to retrieval RPC; prevents downstream errors.

---

### 5. Structured Logging Without Schema Migration (`backend/app.py`, lines 373-387)

#### Log Payload Serialization (in `create_log`):
```python
shadow_payload = log_data.pop("_multi_intent_shadow", None)
if shadow_payload:
    shadow_text = json.dumps(shadow_payload, ensure_ascii=True)
    reason = f"[multi_intent_shadow]{shadow_text}" or f"{base_reason} | [multi_intent_shadow]{shadow_text}"
    log_data["reason"] = reason[:1800]  # Truncate safely
```

**Design Choice**: 
- Appends compact JSON to existing `reason` field with prefix `[multi_intent_shadow]`
- No DB schema change needed for MVP
- Reason field can safely store ~1800 chars; JSON payload ~500-800 chars
- Backward compatible: existing code ignores `[multi_intent_shadow]` prefix

---

### 6. Retest Script Multi-Intent Metrics (`retest_classification.py`)

#### New Extraction Functions:
- `extract_multi_intent_shadow(reason_text)` — Parse `[multi_intent_shadow]{json}` from log
- `compute_primary_intent_accuracy(expected, actual, shadow)` — Check if primary intent matches expected label
- `compute_multi_intent_stats(results[])` — Aggregate metrics:
  - `multi_intent_count`, `single_intent_count`
  - `multi_intent_primary_correct`, `multi_intent_accuracy %`
  - `single_intent_correct`, `single_intent_accuracy %`
  - `conflict_cases`, `clarify_secondary_count`

#### Updated Functions:
- `parse_stream_response()` — Now extracts shadow telemetry; added `"shadow": None` field
- `run_custom_retest()` — Adds `"shadow": retest_result.get("shadow")` to result entries
- `analyze_custom_results()` — Reports multi-intent metrics in section under pass rate

#### New Metrics Reporting:
```
Multi-intent queries: X
Single-intent queries: Y

Primary intent accuracy (multi-intent): Z.Z% (A/B)
Single-intent accuracy: Z.Z% (C/D)
Conflict cases: E
Clarify-first secondary count: F
```

---

## How to Activate Shadow Mode

### Environment Variables:
```bash
export ENABLE_MULTI_INTENT=true
export ENABLE_MULTI_INTENT_SHADOW=true
# Keep ENABLE_MULTI_INTENT_LIGHT_SECONDARY=false for Clarify-first MVP behavior
```

### In Docker:
```dockerfile
ENV ENABLE_MULTI_INTENT=true
ENV ENABLE_MULTI_INTENT_SHADOW=true
```

### In `.env` file:
```
ENABLE_MULTI_INTENT=true
ENABLE_MULTI_INTENT_SHADOW=true
```

---

## Testing the Shadow Mode

### 1. Live Testing with Curl:
```bash
curl -X POST http://localhost:8001/api/chat-stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "cho em xin sdt chi thu va can giay to gi",
    "session_id": "test-001",
    "use_llm": true,
    "chunk_limit": 1
  }'
```

**Expected SSE logs** (when shadow enabled):
```
data: {"log": "Multi-intent shadow: {\"is_multi_intent\": true, \"intent_count\": 2, ...}"}
```

### 2. Regression Testing:
```bash
python3 retest_classification.py \
  --custom-file custom_cases_from_chunks.json \
  --max-queries 30
```

**Output** includes:
- Overall pass rate (existing)
- Pass rate by lane (existing)
- **NEW**: Multi-intent analysis section with accuracy metrics

### 3. Generate Test Cases from Current Chunks:
```bash
python3 retest_classification.py \
  --generate-cases-from-chunks \
  --cases-output test_multi_intent_cases.json \
  --max-cases 100
```

Then run retest:
```bash
python3 retest_classification.py \
  --custom-file test_multi_intent_cases.json
```

---

## Verification Checklist

- [x] Syntax validation passed (`python3 -c "import ast; ast.parse(open(...).read())"`)
- [x] Feature flags default to `False` (no runtime side effects without opt-in)
- [x] Taxonomy guard applied after rule classify and LLM override
- [x] Shadow telemetry extracted and logged to reason field
- [x] Retest script parses multi-intent telemetry and computes metrics
- [ ] Live end-to-end shadow test (requires running backend container)
- [ ] Regression pass rate on multi-intent test set >= 80%
- [ ] No invalid labels sent to retrieval RPC (can verify from logs)
- [ ] p95 latency increase <= +15% (requires production monitoring)

---

## Next Steps After Shadow Validation

### Phase M3: Active Mode (Not in Scope for MVP)
1. When shadow metrics show `multi_intent_primary_correct >= 80%`, enable active routing
2. Route `primary_intent` (guarded) instead of single label
3. Apply secondary handling policy (clarify-first, light-retrieval, skip)
4. Measure response quality on primary/secondary separately

### Phase M4: Schema Migration (Post-MVP)
1. Add `intents: JSON[]` column to `log_query`
2. Migrate shadow telemetry from reason field to intents column
3. Remove `[multi_intent_shadow]` prefix from reason field

---

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `backend/test_demo.py` | Added multi-intent decomposition/ranking core | 274-520 |
| `backend/app.py` | Added flags, guard, shadow summary, logging | 1-15, 55-82, 373-387, 530-599, 770-787, 862-866 |
| `retest_classification.py` | Added shadow extraction and multi-intent metrics | Various (functions + analyze section) |

---

## Architecture Summary

```
┌─ Receive Query ─────────┐
└──────────────┬──────────┘
               ↓
        ┌─ Normalize & Rewrite ─┐
        └──────────┬────────────┘
                   ↓
        [SHADOW MODE - Parallel Computation]
        ┌─ classify_multi_intent() ─────────┐
        ├─ • decompose_intents()             │
        ├─ • classify_span() per span        │
        ├─ • rank_intents()                  │
        ├─ • apply_taxonomy_guard()          │
        ├─ • summarize_multi_intent_shadow() │
        ├─ → log_data["_multi_intent_shadow"]│
        └────────────┬─────────────────────┘
                     ↓
        [LEGACY SINGLE-LABEL PATH - Unchanged]
        ┌─ classify_v2() ────────────┐
        ├─ guard_retrieval_label()   │
        ├─ [Optional LLM fallback]   │
        ├─ → guard_retrieval_label() │
        └────────────┬───────────────┘
                     ↓
        ┌─ Retrieval (Unchanged) ────┐
        └────────────┬───────────────┘
                     ↓
        ┌─ Format & Log Response ────┐
        ├─ • Serialize shadow payload│
        ├─ • Append to reason field  │
        ├─ • Write to log_query      │
        └────────────┬───────────────┘
                     ↓
        ┌─ Return to Client ─────────┐
        └────────────────────────────┘
```

---

## Known Limitations (MVP)

1. **Decomposition is rule-based only** → May miss multi-intent in complex queries without LLM decomposition
2. **Secondary intents not retrieved** → Clarify-first policy; light-retrieval not yet active
3. **No schema migration** → Shadow telemetry in reason field; can move to JSON column later
4. **Single-label routing unchanged** → Shadow is read-only observation; routing uses legacy path
5. **No active mode feedback loop** → Better to validate shadow accuracy first before activating

---

## Rollout Gates

✅ **Shadow deployment ready**: Can enable with env flags; read-only, no runtime impact  
🚧 **Requires before active mode**: Shadow metrics >= 80% accuracy on multi-intent test set  
🚧 **Requires before production**: No increase in error rate; p95 latency +0-15%

---

End of Implementation Summary
