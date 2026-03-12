# Backend Flow (/api/chat-stream)

This document describes the runtime flow in `backend/app.py` for the chat pipeline.

## 1. Main Endpoints

- `GET /api/get-chunks`
: Read chunk data from `documents` table.
- `GET /api/get-alias`
: Read alias data from `alias` table.
- `GET /api/get-logs`
: Read conversation logs from `log_query` table.
- `POST /api/chat-stream`
: Main realtime QA endpoint (SSE stream).
- `POST /api/chat`
: Legacy non-stream endpoint.

## 2. /api/chat-stream Request

Expected payload:

```json
{
  "message": "user question",
  "session_id": "session-key",
  "use_llm": true,
  "chunk_limit": 1
}
```

Key request fields:
- `message`: raw user input.
- `session_id`: conversation grouping key in `log_query.session_chat`.
- `use_llm`: if true, answer generation uses `llm_answer(...)`.
- `chunk_limit`: maximum chunks returned in final answer text.

## 3. Pipeline Stages

### Stage A: Normalize input

1. Load request data.
2. Apply abbreviation resolver (`resolver.process`).
3. Keep:
- `origin_mess`: original question.
- `user_message`: expanded version.
- `normalized_query`: normalized text for matching.

SSE logs emitted during this stage include `Nhan message`, `Kiem tra viet tat`, and normalized payload.

### Stage B: Blacklist gate

1. Check `BANNED_KEYWORDS` against both original and normalized text.
2. If matched:
- log `event_type = banned_topic` to `log_query`.
- stream blocked response.
- return early.

### Stage C: Session rewrite

1. Load up to 2 latest normal turns from `log_query` by `session_chat`.
2. If history exists, call `rewrite_query(user_message, last_question)`.
3. Recompute `normalized_query` after rewrite.

### Stage D: Classification

1. Rule classifier: `classify_v2(normalized_query, PREPARED)` from `backend/test_demo.py`.
2. Output includes:
- `category`, `subject`
- `need_llm`
- `signals`, `confidence`, `intent`
3. If `need_llm` is true:
- call `classify_llm(user_message)`.
- allow LLM override for category/subject.
- special interaction handling:
  - `tuong_tac/chao_hoi` => return help message.
  - `tuong_tac/phan_nan` => return complaint message and `event_type=complaint`.

### Stage E: Hybrid retrieval

Call Supabase RPC `search_documents_full_hybrid_v6` with:
- normalized query
- query embedding
- tenant `xa_ba_diem`
- detected `category`, `subject`

Then apply fallback retrieval in some cases:
- If `re_check` or subject in `[chuc_vu, nhan_su]` and top score is low, retry with `subject=None`.
- If subject is `thong_tin_lien_he` and score is low, retry with `category=to_chuc_bo_may`, `subject=None`.

### Stage F: Semantic guard and answering

1. Build context from top chunks.
2. If category is `thu_tuc_hanh_chinh`, apply `apply_semantic_guard` and reduce context.
3. Use confidence threshold:
- `score > 0.48`: answer directly.
- `score <= 0.48`: call `detect_query(user_message, context)` to decide final branch.

Branch behavior:
- `answerable`: answer with chunks (or LLM answer if `use_llm=true`).
- `banned`: return blocked message, log `banned_topic`.
- `out_of_scope`: return out-of-scope message.
- `qa_need_info`: ask for more details.

All branches write logs into `log_query` with latency and scores when available.

## 4. Data Dependencies

- Supabase tables:
- `documents`: chunks and metadata.
- `alias`: alias dictionary.
- `log_query`: runtime logs and history.
- `chunk_relations`: linked chunks for context expansion.

- Main helper modules:
- `normalize.py`: normalization, abbreviations, blacklist.
- `test_demo.py`: rule-first classifier (`classify_v2`).
- `model.py`: LLM classify, query-type detect, answer generation.
- `system.py`: semantic guard for procedure responses.
- `embedding.py`: query/chunk embeddings.

## 5. Event Types in Logs

Common `event_type` values in `log_query`:
- `normal`
- `banned_topic`
- `out_of_scope`
- `qa_need_info`
- `complaint`

## 6. Notes and Risks

- Thresholds (`0.48`, fallback thresholds `0.4`, `0.45`) are hard-coded in `app.py`.
- If classification returns weak/empty subject, retrieval quality may depend heavily on LLM fallback.
- SSE parser in external test scripts should treat logs as source of truth for final category/subject.
