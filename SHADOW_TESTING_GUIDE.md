# Multi-Intent Shadow Testing Guide

## Quick Start

### 1. Enable Shadow Mode in Container

If using Docker, add to your `Dockerfile` or `docker-compose.yml`:
```yaml
environment:
  - ENABLE_MULTI_INTENT=true
  - ENABLE_MULTI_INTENT_SHADOW=true
```

Or set at runtime:
```bash
export ENABLE_MULTI_INTENT=true
export ENABLE_MULTI_INTENT_SHADOW=true
./start_backend.sh  # or your startup script
```

### 2. Test with Sample Queries

**Multi-intent queries (good test cases)**:
```
"cho em xin sdt chi thu va can giay to gi"
"chu tich ubnd xa la ai va bao lau co ket qua"
"ban giup gi dc cho toi va nop o dau"
"mat giay khai sinh va dang ky ket hon can giay to gi"
"toi rat buc xuc, can bo xu ly cham, va toi muon biet nop don khieu nai o dau"
```

**Single-intent queries (sanity check)**:
```
"cho em xin sdt chi Thu"
"chu tich ubnd xa la ai"
"nop ho so o dau"
```

### 3. Look for Shadow Logs

When sending a request to `/api/chat-stream`:
```bash
curl -X POST http://localhost:8001/api/chat-stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "cho em xin sdt chi thu va can giay to gi",
    "session_id": "test-shadow-001",
    "use_llm": true,
    "chunk_limit": 1
  }'
```

**Expected SSE stream** (partial output):
```
data: {"log": "Multi-intent shadow: {\"is_multi_intent\": true, \"intent_count\": 2, \"primary_intent\": {...}, ...}"}
data: {"log": "Category: to_chuc_bo_may, Subject: nhan_su"}
data: {"replies": "...answer...", "chunks": [...]}
```

---

## Testing Workflow

### Phase 1: Shadow Logging Verification

```bash
# 1. Extract latest logs from container
docker exec chatbot_backend curl -s http://localhost:8001/api/get-logs \
  | jq '.logs[] | select(.reason | contains("multi_intent_shadow"))' > shadow_logs.json

# 2. Check shadow telemetry was captured
cat shadow_logs.json | head -5 | jq '.'
```

**Expected**: Logs with reason field containing `[multi_intent_shadow]{...json...}`

---

### Phase 2: Regression Testing with Multi-Intent Metrics

#### Generate test cases:
```bash
python3 retest_classification.py \
  --generate-cases-from-chunks \
  --cases-output multi_intent_test_cases.json \
  --max-cases 50 \
  --api-base-url http://localhost:8001
```

#### Run custom retest:
```bash
python3 retest_classification.py \
  --custom-file multi_intent_test_cases.json \
  --api-base-url http://localhost:8001
```

**Output includes**:
```
========================================
MULTI-INTENT ANALYSIS
========================================
Multi-intent queries: 15
Single-intent queries: 35

Primary intent accuracy (multi-intent): 80.0% (12/15)
Single-intent accuracy: 88.6% (31/35)
Conflict cases: 3
Clarify-first secondary count: 8
```

#### Run against full logs:
```bash
python3 retest_classification.py logs_live_from_api.json --max-queries 100
```

---

### Phase 3: Validate Taxonomy Guard

Check logs for guard triggers:
```bash
docker exec chatbot_backend grep -i "taxonomy guard" logs.txt | wc -l
# Should be 0 for valid data, or small number for edge cases only
```

Extract invalid labels caught:
```bash
docker exec chatbot_backend curl -s http://localhost:8001/api/get-logs \
  | jq '.logs[] | select(.reason | contains("invalid")) | {raw_query, reason}' \
  | head -10
```

---

### Phase 4: Performance Check

Measure latency impact:
```python
import requests
import time

times = []
for i in range(100):
    start = time.time()
    requests.post("http://localhost:8001/api/chat-stream", json={
        "message": f"test query {i}",
        "session_id": f"perf-{i}"
    })
    times.append(time.time() - start)

p95 = sorted(times)[int(len(times)*0.95)]
print(f"p95 latency: {p95:.2f}s")
```

**Expected**: p95 latency increase <= +15% compared to shadow disabled

---

## Troubleshooting

### Shadow telemetry not appearing in logs

**Check**:
1. Verify flags are set: `env | grep ENABLE_MULTI_INTENT`
2. Verify backend reloaded after env change: restart container
3. Check backend logs for parser errors:
   ```
   docker logs chatbot_backend | grep -i "multi_intent\|shadow"
   ```
4. Check log entry `reason` field manually:
   ```bash
   curl -s http://localhost:8001/api/get-logs | jq '.logs[0].reason'
   ```

### Primary intent accuracy too low

**Investigate**:
1. Check if intents were decomposed correctly:
   ```bash
   cat shadow_logs.json | jq '.reason' | grep -o '"intent_count": [0-9]+'
   ```
2. Check if conflicts detected:
   ```bash
   cat shadow_logs.json | jq 'select(.reason | contains("\"has_conflict\": true"))'
   ```
3. Check primary intent scores:
   ```bash
   cat shadow_logs.json | jq '.reason' | grep -o '"priority_score": [0-9.]+' | sort | uniq -c
   ```

### Taxonomy guard triggers incorrectly

**Check**:
1. Verify RETRIEVAL_TAXONOMY matches actual chunks:
   ```bash
   curl -s http://localhost:8001/api/get-chunks \
     | jq '[.chunks[] | {category, subject}] | unique' | head -20
   ```
2. Manually test guard logic:
   ```python
   from backend.app import guard_retrieval_label
   cat, sub, invalid = guard_retrieval_label("thu_tuc_hanh_chinh", "tu_phap_ho_tich")
   print(invalid)  # Should be False if valid
   ```

---

## Manual Testing Checklist

- [ ] Backend starts without errors when ENABLE_MULTI_INTENT_SHADOW=true
- [ ] Single-intent query produces shadow contract with intent_count=1
- [ ] Multi-intent query produces shadow contract with intent_count>=2
- [ ] Primary intent matches expected category/subject for golden test cases
- [ ] Retest script runs and produces multi-intent analysis section
- [ ] No invalid labels reach retrieval RPC (check logs for "invalid_label_guard_triggered")
- [ ] Response time not degraded significantly (p95 <= baseline + 15%)
- [ ] Backward compatibility: single-intent accuracy unchanged

---

## Production Readiness Checklist

Before enabling active mode or going to production:

- [ ] Multi-intent accuracy >= 80% on test set
- [ ] Single-intent regression < 5% loss in accuracy
- [ ] No 5xx errors introduced
- [ ] Latency p95 increase <= 15%
- [ ] Can disable via env flag if needed
- [ ] Logs are readable and parsed correctly by monitoring tools
- [ ] Telemetry fields are stable (no schema thrashing)

---

## Next Steps

Once shadow metrics validated:
1. Update implementation plan with actual metrics
2. Design active mode routing logic
3. Implement secondary intent handling
4. Plan gradual rollout (10% → 30% → 100% traffic)
5. Monitor production metrics continuously
