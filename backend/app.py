
import re
import uuid
import time
import hashlib
from threading import Lock
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from openai import OpenAI

from dotenv import load_dotenv
import os
from corn import supabase
from flask import Response, stream_with_context
import json
from normalize import SINGLE_TOKEN_MAP, CONTEXT_RULES, BANNED_KEYWORDS, normalize_text, normalize_subject_value, AbbreviationResolver
from model import rewrite_query, detect_query, llm_answer, classify_category, check_classify_phan_anh_kien_nghi, check_classify_tuong_tac
from test_demo import classify_v2
from embedding import get_proc_embedding, get_embedding
from utils import SUBJECT_KEYWORDS, GENERAL_INFO_SUBJECT_KEYWORDS, classify, prepare_subject_keywords
from export_metadata import classify_llm, classify_with_tong_quan, classify_with_phan_anh, classify_with_tuong_tac

PREPARED = prepare_subject_keywords(SUBJECT_KEYWORDS)

load_dotenv()

app = Flask(__name__)
CORS(app)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

resolver = AbbreviationResolver(SINGLE_TOKEN_MAP, CONTEXT_RULES)

# Lightweight in-memory TTL cache to reduce duplicate LLM/embedding/RPC calls.
_cache_lock = Lock()
_embedding_cache = {}
_classify_llm_cache = {}
_detect_query_cache = {}
_search_v6_cache = {}
_related_chunks_cache = {}

EMBEDDING_CACHE_TTL = 30 * 60
LLM_CLASSIFY_CACHE_TTL = 10 * 60
DETECT_QUERY_CACHE_TTL = 5 * 60
SEARCH_V6_CACHE_TTL = 60
RELATED_CHUNKS_CACHE_TTL = 120

EMBEDDING_CACHE_MAX = 2000
LLM_CLASSIFY_CACHE_MAX = 1000
DETECT_QUERY_CACHE_MAX = 500
SEARCH_V6_CACHE_MAX = 1500
RELATED_CHUNKS_CACHE_MAX = 2000


def _cache_get(cache, key):
    now = time.time()
    with _cache_lock:
        item = cache.get(key)
        if not item:
            return None
        expire_at, value = item
        if expire_at < now:
            cache.pop(key, None)
            return None
        return value


def _cache_set(cache, key, value, ttl_seconds, max_items):
    now = time.time()
    expire_at = now + ttl_seconds
    with _cache_lock:
        # Lazy cleanup of expired entries.
        expired = [k for k, (exp, _) in cache.items() if exp < now]
        for k in expired:
            cache.pop(k, None)

        # Simple size guard: remove oldest-by-expiry key when full.
        if len(cache) >= max_items:
            oldest_key = min(cache, key=lambda k: cache[k][0])
            cache.pop(oldest_key, None)

        cache[key] = (expire_at, value)


def _clone_rows(rows):
    return [dict(r) for r in (rows or [])]


def get_embedding_cached(user_text: str):
    key = normalize_text(user_text or "")
    cached = _cache_get(_embedding_cache, key)
    if cached is not None:
        return cached

    emb = get_embedding(user_text)
    _cache_set(_embedding_cache, key, emb, EMBEDDING_CACHE_TTL, EMBEDDING_CACHE_MAX)
    return emb


def classify_llm_cached(user_text: str):
    key = normalize_text(user_text or "")
    cached = _cache_get(_classify_llm_cache, key)
    if cached is not None:
        return cached

    value = classify_category(user_text)
    _cache_set(_classify_llm_cache, key, value, LLM_CLASSIFY_CACHE_TTL, LLM_CLASSIFY_CACHE_MAX)
    return value


def detect_query_cached(user_text: str, context: str):
    context_hash = hashlib.sha1((context or "").encode("utf-8")).hexdigest()
    key = (normalize_text(user_text or ""), context_hash)
    cached = _cache_get(_detect_query_cache, key)
    if cached is not None:
        return cached

    value = detect_query(user_text, context)
    _cache_set(_detect_query_cache, key, value, DETECT_QUERY_CACHE_TTL, DETECT_QUERY_CACHE_MAX)
    return value


def search_documents_full_hybrid_v6_cached(normalized_query, query_embedding, category, subject, p_limit=5, tenant="xa_ba_diem"):
    key = (tenant, normalized_query, category, subject, p_limit)
    cached = _cache_get(_search_v6_cache, key)
    if cached is not None:
        return _clone_rows(cached)

    response = supabase.rpc(
        "search_documents_full_hybrid_v6",
        {
            "p_query_format": normalized_query,
            "p_query_embedding": query_embedding,
            "p_tenant": tenant,
            "p_category": category,
            "p_subject": subject,
            "p_limit": p_limit
        }
    ).execute()

    rows = response.data or []
    _cache_set(_search_v6_cache, key, _clone_rows(rows), SEARCH_V6_CACHE_TTL, SEARCH_V6_CACHE_MAX)
    return rows

@app.route('/api/get-chunks', methods=['GET'])
def get_chunks():
    try:
        tenant_code = request.args.get("tenant_code", default=None, type=str)

        query = (
            supabase.table("documents")
            .select(
                "id, procedure_name, text_content, category, subject, "
                "is_active, effective_date, procedure_action, special_contexts, tenant_code"
            )
        )

        if tenant_code:
            query = query.eq("tenant_code", tenant_code)

        response = query.execute()


        if not response.data:
            return jsonify({
                "chunks": [],
                "message": "No chunks available"
            }), 200

        return jsonify({
            "chunks": response.data
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route('/api/get-alias', methods=['GET'])
def get_alias():
    try:
        response = supabase.table("alias") \
            .select("id, document_id, alias_text, normalized_alias") \
            .execute()

        if not response.data:
            return jsonify({
                "alias": [],
                "message": "No alias available"
            }), 200

        return jsonify({
            "alias": response.data
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/get-logs', methods=['GET'])
def get_logs():
    try:
        # Supabase select() defaults to 1000 rows. Paginate to return full log set.
        page_size = request.args.get("page_size", default=1000, type=int)
        max_rows = request.args.get("max_rows", default=None, type=int)
        tenant_code = request.args.get("tenant_code", default=None, type=str)

        if page_size is None or page_size <= 0:
            page_size = 1000
        page_size = min(page_size, 1000)

        fields = (
            "id, raw_query, expanded_query, detected_category, detected_subject, "
            "answer, event_type, reason, alias_score, document_score, confidence_score, "
            "response_time_ms, is_noted, tenant_code"
        )

        logs = []
        start = 0
        while True:
            query = supabase.table("log_query").select(fields)
            if tenant_code:
                query = query.eq("tenant_code", tenant_code)

            response = (
                query
                .order("created_at", desc=True)
                .range(start, start + page_size - 1)
                .execute()
            )

            batch = response.data or []
            if not batch:
                break

            logs.extend(batch)

            if max_rows is not None and max_rows > 0 and len(logs) >= max_rows:
                logs = logs[:max_rows]
                break

            if len(batch) < page_size:
                break

            start += page_size

        if not logs:
            return jsonify({
                "logs": [],
                "message": "No logs available"
            }), 200

        return jsonify({
            "logs": logs,
            "total": len(logs),
            "page_size": page_size,
            "max_rows": max_rows
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/delete-logs', methods=['GET'])
def delete_logs():
    try:
        response = supabase.table("log_query") \
            .select("id, raw_query, expanded_query, event_type, reason, alias_score, document_score, confidence_score, response_time_ms") \
            .execute()

        if not response.data:
            return jsonify({
                "logs": [],
                "message": "No alias available"
            }), 200

        return jsonify({
            "logs": response.data
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

def extract_procedure_name(chunk: str) -> str:
    m = re.search(r"^\s*Tên thủ tục:\s*(.+?)\s*$", chunk, re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None

@app.route('/api/create-chunk', methods=['POST'])
def create_chunk():
    try:
        data = request.json

        # Validate cơ bản
        if not data.get("text_content"):
            return jsonify({"error": "text_content is required"}), 400
        tenant_code = data.get("tenant_code") or None
        scope = (data.get("scope") or '').strip() or 'xa_phuong'
        
        if scope == "quoc_gia":
            tenant_code = None

        embedding = get_proc_embedding(data.get("text_content")) if data.get("text_content") else None
        if embedding is None:
            return jsonify({"error": "Không thể tạo embedding cho nội dung này. Vui lòng thử lại."}), 500

        text_content = data.get("text_content") or ''
        category = data.get("category") or None
        procedure_name = extract_procedure_name(text_content) if category == "thu_tuc_hanh_chinh" else None

        new_chunk = {
            "tenant_code": tenant_code,
            "scope": scope,
            "procedure_name": procedure_name,
            "text_content": text_content,
            "normalized_text": normalize_text(procedure_name or text_content),
            "category": category,
            "subject": data.get("subject") or None,
            "embedding": embedding
        }

        response = supabase.table("documents") \
            .insert(new_chunk) \
            .execute()

        return jsonify({
            "message": "Chunk created successfully",
            "data": response.data
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/create-alias', methods=['POST'])
def create_alias():
    try:
        data = request.json

        # Validate cơ bản
        if not data.get("alias_text"):
            return jsonify({"error": "alias_text is required"}), 400
        
        alias_embedding = client.embeddings.create(
            model="text-embedding-3-small",
            input=data.get("alias_text")
        ).data[0].embedding


        new_alias = {
            "document_id": data.get("document_id") or None,
            "alias_text": data.get("alias_text") or '',
            "normalized_alias": normalize_text(data.get("alias_text")) if data.get("alias_text") else '',
            "embedding": alias_embedding
        }

        response = supabase.table("alias") \
            .insert(new_alias) \
            .execute()

        return jsonify({
            "message": "Alias created successfully",
            "data": response.data
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def create_log(log_data):
    if log_data is None:
        return
    
    try:
        response = supabase.table("log_query") \
            .insert(log_data) \
            .execute()

        return jsonify({
            "message": "Log created successfully",
            "data": response.data
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete-alias/<alias_id>', methods=['DELETE'])
def delete_alias(alias_id):
    try:
        response = supabase.table("alias") \
            .delete() \
            .eq("id", alias_id) \
            .execute()

        if not response.data:
            return jsonify({"error": "Alias not found"}), 404

        return jsonify({
            "message": "Alias deleted successfully"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete-chunk/<chunk_id>', methods=['DELETE'])
def delete_chunk(chunk_id):
    try:
        response = supabase.table("documents") \
            .delete() \
            .eq("id", chunk_id) \
            .execute()

        if not response.data:
            return jsonify({"error": "Chunk not found"}), 404

        return jsonify({
            "message": "Chunk deleted successfully"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/update-chunk/<chunk_id>', methods=['PUT'])
def update_chunk(chunk_id):
    try:
        data = request.json

        text_content = data.get("text_content")

        response = supabase.table("documents") \
            .update({
                "text_content": data.get("text_content"),
                "normalized_text": normalize_text(text_content),
                "category": data.get("category") or None,
                "subject": data.get("subject") or None,
                "procedure_action": data.get("procedure_action") or None,
                "special_contexts": data.get("special_contexts") if isinstance(data.get("special_contexts"), list) else [],
                "embedding": get_proc_embedding(text_content)
            }) \
            .eq("id", chunk_id) \
            .execute()
        
        if not response.data:
            return jsonify({"error": "Chunk not found"}), 404

        return jsonify({
            "message": "Chunk updated successfully",
            "data": response.data
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route('/api/update-alias/<alias_id>', methods=['PUT'])
def update_alias(alias_id):
    try:
        data = request.json

        alias_embedding = client.embeddings.create(
            model="text-embedding-3-small",
            input=data.get("alias_text")
        ).data[0].embedding

        response = supabase.table("alias") \
            .update({
                "document_id": data.get("document_id") or None,
                "alias_text": data.get("alias_text") or '',
                "normalized_alias": normalize_text(data.get("alias_text")) or '',
                "embedding": alias_embedding
            }) \
            .eq("id", alias_id) \
            .execute()
        
        if not response.data:
            return jsonify({"error": "Alias not found"}), 404

        return jsonify({
            "message": "Alias updated successfully",
            "data": response.data
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

@app.route("/api/load-history", methods=["POST"])
def load_history():

    data = request.json
    session_id = data.get("session_id")
    tenant_code = data.get("tenant_code")

    query = (
        supabase
        .table("log_query")
        .select("raw_query, answer")
        .eq("session_chat", session_id)
        .eq("event_type", "normal")
    )

    if tenant_code:
        query = query.eq("tenant_code", tenant_code)

    logs = query.order("created_at").execute()

    return jsonify({
        "logs": logs.data
    })

@app.route('/api/clear-session', methods=['POST'])
def clear_session():

    return jsonify({"message": "Session cleared"})

def get_related_chunks(supabase, tenant_code: str, source_chunk_id: str):
    # Skip relation lookup when source chunk is missing/invalid.
    if not source_chunk_id:
        return []

    try:
        uuid.UUID(str(source_chunk_id))
    except (ValueError, TypeError, AttributeError):
        return []

    rel_res = supabase.table("chunk_relations") \
        .select("target_chunk_id") \
        .eq("tenant_code", tenant_code) \
        .eq("source_chunk_id", source_chunk_id) \
        .execute()

    rel_ids = [r["target_chunk_id"] for r in (rel_res.data or [])]
    if not rel_ids:
        return []

    doc_res = supabase.table("documents") \
        .select("id,text_content,category,subject") \
        .eq("tenant_code", tenant_code) \
        .eq("is_active", True) \
        .in_("id", rel_ids) \
        .execute()

    return doc_res.data or []


def get_related_chunks_cached(tenant_code: str, source_chunk_id: str):
    key = (tenant_code, source_chunk_id)
    cached = _cache_get(_related_chunks_cache, key)
    if cached is not None:
        return _clone_rows(cached)

    rows = get_related_chunks(supabase, tenant_code, source_chunk_id)
    _cache_set(_related_chunks_cache, key, _clone_rows(rows), RELATED_CHUNKS_CACHE_TTL, RELATED_CHUNKS_CACHE_MAX)
    return rows


def normalize_llm_label(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.lower() in {"none", "null", "unknown", "n/a"}:
        return None
    return s


def is_complaint_intent(text_norm: str) -> bool:
    complaint_kws = [
        "phan nan", "khieu nai", "to cao", "kien nghi", "gop y",
        "khong hai long", "buc xuc", "thai do", "phuc vu",
        "gay on", "on ao", "danh nhau", "trom cap", "bao cong an"
    ]
    text_norm = (text_norm or "").lower()
    return any(kw in text_norm for kw in complaint_kws)

@app.route('/api/toggle-note/<log_id>', methods=['POST'])
def toggle_note(log_id):
    try:
        # lấy trạng thái hiện tại
        res = supabase.table("log_query") \
            .select("is_noted") \
            .eq("id", log_id) \
            .single() \
            .execute()

        current = res.data["is_noted"]

        # đảo trạng thái
        updated = supabase.table("log_query") \
            .update({"is_noted": not current}) \
            .eq("id", log_id) \
            .execute()

        return jsonify({
            "success": True,
            "is_noted": not current
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/chat-stream', methods=['POST'])
def chat_stream():

    def generate():

        # ✅ LẤY DATA TRƯỚC
        data = request.json
        session_id = data.get("session_id")
        print("Session:", session_id)
        user_message = data.get('message', '').strip()
        origin_mess = user_message
        use_llm = data.get('use_llm', False)
        chunk_generate = data.get("chunk_limit", 1)
        tenant_code = data.get("tenant_code") or "xa_ba_diem"
        log_data = {}

        start = time.perf_counter()

        session_history = (
            supabase
            .table("log_query")
            .select("expanded_query")
            .eq("session_chat", session_id)
            .eq("event_type", "normal")
            .eq("tenant_code", tenant_code)
            .order("created_at", desc=True)
            .limit(2)
            .execute()
        )

        history_data = session_history.data or []

        help_content = "Kính chào anh/chị! Rất vui được hỗ trợ anh/chị. Anh/chị có thể hỏi về các thủ tục hành chính, thông tin chung, hoặc tổ chức bộ máy của phường. Anh/chị cần giúp đỡ về vấn đề gì ạ?"
        out_of_score_content = "Nội dung anh/chị hỏi nằm ngoài phạm vi hỗ trợ của hệ thống.\nAnh/chị vui lòng liên hệ đơn vị phù hợp hoặc đặt câu hỏi liên quan đến thủ tục hành chính để được hỗ trợ."
        not_have_content = "Dạ, hiện tại hệ thống đang cập nhật thêm thông tin về phường, các thủ tục để hỗ trợ anh/chị tốt hơn ạ. Anh/chị còn câu hỏi nào thắc mắc không ạ?" 
        banned_replies = "Dạ em chỉ hỗ trợ anh/chị về các thủ tục hành chính, thông tin chung, hoặc tổ chức bộ máy của phường thôi ạ. Anh/chị vui lòng đặt câu hỏi liên quan đến những chủ đề này để được hỗ trợ tốt nhất nhé."

        yield f"data: {json.dumps({'log': f'Nhận message...'})}\n\n"
        yield f"data: {json.dumps({'log': f'Kiểm tra viết tắt'})}\n\n"
        result = resolver.process(user_message)
        user_message = result["expanded"]
        normalized_query = result["normalized"]
        yield f"data: {json.dumps({'log': f'{result}'})}\n\n"
        # normalized_query = normalize_text(q)
        yield f"data: {json.dumps({'log': f'Kiểm tra blacklist'})}\n\n"
        # 1️⃣ So nguyên dấu
        matched_keyword = next(
            (
                kw for kw in BANNED_KEYWORDS
                if kw.lower() in user_message.lower()
                or normalize_text(kw) in normalized_query
            ),
            None
        )

        if matched_keyword:
            # end = time.perf_counter()
            # duration = (end - start) * 1000 
            # log_data["raw_query"] = user_message
            # log_data["expanded_query"] = normalized_query
            # log_data["event_type"] = "banned_topic"
            # log_data["reason"]= f"Nội dung có chứa từ khóa cấm => {matched_keyword}"
            # log_data["session_chat"]= session_id
            # log_data["response_time_ms"]= round(duration / 1000,2)
            # create_log(log_data)
            # yield f"data: {json.dumps({'log': f'[Blocked] Query: {user_message} => keyword: {matched_keyword}'})}\n\n"
            yield f"data: {json.dumps({'replies': banned_replies, 'chunks': []})}\n\n"
            return 

        if len(history_data) >= 1:
            yield f"data: {json.dumps({'log': f'Kiểm tra lịch sử hội thoại'})}\n\n"

            # last_answer = history_data[0]["answer"]
            # print(f"Câu trả lời trước: {last_answer}")
            last_question = history_data[0]["expanded_query"]
            print(f"Câu hỏi trước: {last_question}")

            user_message = rewrite_query(user_message, last_question)
            normalized_query = normalize_text(user_message)

            yield f"data: {json.dumps({'log': f'Câu hỏi hoàn chỉnh: {user_message}'})}\n\n"

        yield f"data: {json.dumps({'log': f'Normalized: {normalized_query}'})}\n\n"

        res = classify_v2(normalized_query, PREPARED)
        category, subject = res["category"], res["subject"]
        yield f"data: {json.dumps({'log': f'Category: {category}, Subject: {subject}'})}\n\n"

        if res["need_llm"]:
            re_check = True
            yield f"data: {json.dumps({'log': f'Bắt đầu sử dụng LLM để trích xuất'})}\n\n"
            category_llm = classify_llm_cached(user_message)
            yield f"data: {json.dumps({'log': f'LLM classify => Category: {category_llm}'})}\n\n"

            category = normalize_llm_label(category_llm)
        
        if category == "chu_de_cam":
            yield f"data: {json.dumps({'replies': banned_replies, 'chunks': []})}\n\n"
            return
            
        if category == "thu_tuc_hanh_chinh":
            meta = classify_llm(user_message)

            if not meta or not isinstance(meta, dict):
                return []

            query_mode = meta.get("query_mode")
            # print(f"Query mode: {query_mode}")

            procedures = meta.get("unit") or []
            if not procedures:
                return []

            chunk_response = []
            yield f"data: {json.dumps({'log': f'=> Phân tích thủ tục : {query_mode}'})}\n\n"

            if query_mode == "single_procedure":
                procedure_name = procedures[0].get("procedure")
                procedure_action = procedures[0].get("procedure_action")
                special_contexts = procedures[0].get("special_contexts") or []

                yield f"data: {json.dumps({'log': f'=> Tên thủ tục: {procedure_name}'})}\n\n"
                yield f"data: {json.dumps({'log': f'=> Procedure_action: {procedure_action}, Special_contexts: {special_contexts}'})}\n\n"
                response = supabase.rpc(
                    "search_documents_full_hybrid_v7",
                    {
                        "p_query_format": normalize_text(procedure_name),
                        "p_query_embedding": get_embedding_cached(procedure_name),
                        "p_tenant": None,
                        "p_category": category,
                        "p_subject": procedures[0]['subject'],
                        "p_procedure": normalize_text(procedure_name),
                        "p_procedure_action": procedure_action,
                        "p_special_contexts": special_contexts,
                        "p_limit": 4
                    }
                ).execute()
                chunks = response.data or []
            else:
                chunk_response = []
                for proc in procedures:
                    procedure_name = proc['procedure']
                    procedure_action = proc['procedure_action']
                    special_contexts = proc['special_contexts']
                    # print(f"Thủ tục chính: {proc['procedure']} - {proc['subject']}")
                    yield f"data: {json.dumps({'log': f'=> Tên thủ tục: {procedure_name}'})}\n\n"
                    yield f"data: {json.dumps({'log': f'=> Procedure_action: {procedure_action}, Special_contexts: {special_contexts}'})}\n\n"
                    response = supabase.rpc(
                        "search_documents_full_hybrid_v7",
                        {
                            "p_query_format": normalize_text(procedure_name),
                            "p_query_embedding": get_embedding_cached(procedure_name),
                            "p_tenant": None,
                            "p_category": category,
                            "p_subject": proc['subject'],
                            "p_procedure": normalize_text(procedure_name),
                            "p_procedure_action": procedure_action,
                            "p_special_contexts": special_contexts,
                            "p_limit": 1
                        }
                    ).execute()

                    chunks = response.data or []
                    if chunks:
                        chunk_response.append(chunks[0])
                chunks = chunk_response
            # chunks = export_metadata_filter_chunk(category, user_message)
            context = "\n\n".join(
                f"### Tài liệu {i+1}\n{chunk['text_content']}"
                for i, chunk in enumerate(chunks[:5])
            ) if chunks else "Không tìm thấy tài liệu phù hợp."

            print(f"Context for LLM:\n{context}")

                
            answer = "\n\n".join(
                f"Sử dụng các tài liệu sau:\n### Tài liệu {i+1}\n{chunk['text_content']}"
                for i, chunk in enumerate(chunks[:chunk_generate])
            )
    
            if use_llm:
                answer = llm_answer(user_message, context)
                if "chưa có thông tin trong hệ thống" in answer.lower():
                    answer = not_have_content

            end = time.perf_counter()
            duration = (end - start) * 1000 
            log_data["tenant_code"] = tenant_code
            log_data["raw_query"] = origin_mess
            log_data["expanded_query"] = user_message
            log_data["answer"]= answer
            log_data["detected_category"]= category
            log_data["detected_subject"]= subject
            log_data["event_type"] = "normal"
            log_data["alias_score"]= chunks[0]["alias_score"]
            log_data["document_score"]= chunks[0]["document_score"]
            log_data["confidence_score"]= chunks[0]["confidence_score"]
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            create_log(log_data)
            yield f"data: {json.dumps({'replies': answer, 'chunks': chunks})}\n\n"

            return

        if category == "phan_anh_kien_nghi":
            subject = classify_with_phan_anh(user_message)
            subject = normalize_subject_value(subject)
            if subject is None:
                category = check_classify_phan_anh_kien_nghi(user_message)
                category = normalize_subject_value(category)

            yield f"data: {json.dumps({'log': f'=> Trích xuất phản ánh kiến nghị'})}\n\n"
            yield f"data: {json.dumps({'log': f'=> Subject: {subject}'})}\n\n"

        if category == "thong_tin_tong_quan":
            subject = classify_with_tong_quan(user_message)
            subject = normalize_subject_value(subject)
            # subject = data.get("subject")
            yield f"data: {json.dumps({'log': f'=> Trích xuất thông tin tổng quan'})}\n\n"
            yield f"data: {json.dumps({'log': f'=> Subject: {subject}'})}\n\n"
            
        if category == "tuong_tac":
            subject = classify_with_tuong_tac(user_message)
            subject = normalize_subject_value(subject)
            # subject = data.get("subject")
            if subject is None:
                category = check_classify_tuong_tac(user_message)
                category = normalize_subject_value(category)
            
            yield f"data: {json.dumps({'log': f'=> Trích xuất tương tác'})}\n\n"
            yield f"data: {json.dumps({'log': f'=> Subject: {subject}'})}\n\n"

            if subject == "chao_hoi":
                end = time.perf_counter()
                duration = (end - start) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= help_content
                log_data["event_type"] = "normal"
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                create_log(log_data)
                yield f"data: {json.dumps({'log': f'=> Phân loại tương tác - chào hỏi'})}\n\n"
                yield f"data: {json.dumps({'replies': help_content, 'chunks': []})}\n\n"
                return
            if subject == "cam_on_tam_biet":
                end = time.perf_counter()
                duration = (end - start) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= "Dạ, cảm ơn anh/chị. Khi cần thêm thông tin, anh/chị cứ liên hệ lại."
                log_data["event_type"] = "normal"
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                create_log(log_data)
                yield f"data: {json.dumps({'log': f'=> Phân loại tương tác - cảm ơn/kết thúc'})}\n\n"
                yield f"data: {json.dumps({'replies': 'Dạ, cảm ơn anh/chị. Khi cần thêm thông tin, anh/chị cứ liên hệ lại.', 'chunks': []})}\n\n"
                return
            
            if subject == "yeu_cau_lam_ro":
                end = time.perf_counter()
                duration = (end - start) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= "Dạ được, tôi sẽ giải thích lại từng bước để anh/chị dễ theo dõi."
                log_data["event_type"] = "normal"
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                create_log(log_data)
                yield f"data: {json.dumps({'log': f'=> Phân loại tương tác - làm rõ'})}\n\n"
                yield f"data: {json.dumps({'replies': 'Dạ được, tôi sẽ giải thích lại từng bước để anh/chị dễ theo dõi.', 'chunks': []})}\n\n"
                return
            
            if subject == "phan_nan_buc_xuc":
                end = time.perf_counter()
                duration = (end - start) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= "Tôi rất tiếc vì anh/chị chưa hài lòng. Anh/chị hãy nói rõ phần còn vướng, tôi sẽ hỗ trợ lại ngay."
                log_data["event_type"] = "complaint"
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                create_log(log_data)
                yield f"data: {json.dumps({'log': f'=> Phân loại tương tác - phàn nàn'})}\n\n"
                yield f"data: {json.dumps({'replies': 'Tôi rất tiếc vì anh/chị chưa hài lòng. Anh/chị hãy nói rõ phần còn vướng, tôi sẽ hỗ trợ lại ngay.', 'chunks': []})}\n\n"
                return
            
            if subject == "xuc_pham_vi_pham":
                end = time.perf_counter()
                duration = (end - start) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= "Tôi vẫn sẵn sàng hỗ trợ anh/chị về nội dung hành chính. Anh/chị vui lòng sử dụng ngôn từ phù hợp để tôi có thể hỗ trợ tốt hơn."
                log_data["event_type"] = "banned_topic"
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                create_log(log_data)
                yield f"data: {json.dumps({'log': f'=> Phân loại tương tác - xúc phạm/vi phạm'})}\n\n"
                yield f"data: {json.dumps({'replies': 'Tôi vẫn sẵn sàng hỗ trợ anh/chị về nội dung hành chính. Anh/chị vui lòng sử dụng ngôn từ phù hợp để tôi có thể hỗ trợ tốt hơn.', 'chunks': []})}\n\n"
                return

            if subject == "chu_de_cam":
                end = time.perf_counter()
                duration = (end - start) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= banned_replies
                log_data["event_type"] = "banned_topic"
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                create_log(log_data)
                yield f"data: {json.dumps({'log': f'=> Phân loại tương tác - chủ đề cấm'})}\n\n"
                yield f"data: {json.dumps({'replies': 'Dạ em chỉ hỗ trợ anh/chị về các thủ tục hành chính, thông tin chung, hoặc tổ chức bộ máy của phường thôi ạ. Anh/chị vui lòng đặt câu hỏi liên quan đến những chủ đề này để được hỗ trợ tốt nhất nhé.', 'chunks': []})}\n\n"
                return


        query_embedding = get_embedding_cached(user_message)

        chunks = search_documents_full_hybrid_v6_cached(
            normalized_query=normalized_query,
            query_embedding=query_embedding,
            category=category,
            subject=subject,
            p_limit=5,
            tenant=tenant_code
        )
        
        if subject in ["chuc_vu", "nhan_su"]:
            yield f"data: {json.dumps({'log': f'Kiểm tra nội dung subject là None'})}\n\n"
            best_score = chunks[0]["confidence_score"] if chunks else 0
            if best_score < 0.4:
                chunks_all = search_documents_full_hybrid_v6_cached(
                    normalized_query=normalized_query,
                    query_embedding=query_embedding,
                    category=category,
                    subject=None,
                    p_limit=5,
                    tenant=tenant_code
                )

                best_score_all = chunks_all[0]["confidence_score"] if chunks_all else 0

                # Nếu không subject tốt hơn → dùng nó
                if best_score_all > best_score:
                    chunks = chunks_all
        
        id_chunk = chunks[0]["id"] if chunks else None

        primary_chunks = chunks[:5]
        context_parts = [
            f"### Tài liệu {i+1}\n{chunk['text_content']}"
            for i, chunk in enumerate(primary_chunks)
        ] if primary_chunks else []

        related_chunks = get_related_chunks_cached(tenant_code, id_chunk)
        if related_chunks:
            # Avoid duplicate documents when a related chunk already appears in top results.
            existing_ids = {c.get("id") for c in primary_chunks}
            unique_related = [c for c in related_chunks if c.get("id") not in existing_ids]

            if unique_related:
                yield f"data: {json.dumps({'log': f'Tìm thấy {len(unique_related)} tài liệu liên quan'})}\n\n"
                start_idx = len(context_parts)
                context_parts.extend(
                    f"### Tài liệu liên quan {start_idx + i + 1}\n{chunk['text_content']}"
                    for i, chunk in enumerate(unique_related[:3])
                )

        context = "\n\n".join(context_parts) if context_parts else "Không tìm thấy tài liệu phù hợp."

            
        answer = "\n\n".join(
            f"Sử dụng các tài liệu sau:\n### Tài liệu {i+1}\n{chunk['text_content']}"
            for i, chunk in enumerate(chunks[:5])
        )
        

        if use_llm:
            print(context)
            answer = llm_answer(user_message, context)
            if "chưa có thông tin trong hệ thống" in answer.lower():
                answer = not_have_content

        end = time.perf_counter()
        duration = (end - start) * 1000 
        log_data["tenant_code"] = tenant_code
        log_data["raw_query"] = origin_mess
        log_data["expanded_query"] = user_message
        log_data["answer"]= answer
        log_data["detected_category"]= category
        log_data["detected_subject"]= subject
        log_data["event_type"] = "normal"
        log_data["alias_score"]= chunks[0]["alias_score"] if chunks else 0
        log_data["document_score"]= chunks[0]["document_score"] if chunks else 0
        log_data["confidence_score"]= chunks[0]["confidence_score"] if chunks else 0
        log_data["session_chat"]= session_id
        log_data["response_time_ms"]= round(duration / 1000,2)
        create_log(log_data)
        yield f"data: {json.dumps({'replies': answer, 'chunks': chunks})}\n\n"
        return

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # cực quan trọng nếu có nginx
        }
    )   

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Receive user message and return relevant responses
    Request: {"message": "user message"}
    Response: {"replies": [{"content": "...", "score": 0.95}, ...]}
    """
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"error": "Message cannot be empty"}), 400

    q_format = normalize_text(user_message)
    category, subject = classify(q_format)
    print(f"Query: {q_format}\n=> Category: {category}, Subject: {subject}\n")

    log_data = f"""Query: {user_message}\n=> Category: {category}, Subject: {subject}"""

    query_embedding = client.embeddings.create(
        model="text-embedding-3-small",
        input=user_message
    ).data[0].embedding

    response = supabase.rpc(
        "search_documents_full_hybrid_v6",
        {
            "p_query_format": q_format,
            "p_query_embedding": query_embedding,
            "p_tenant": "xa_ba_diem",
            "p_category": category,
            "p_subject": subject,
            "p_limit": 5
        }
    ).execute()

    # Return all responses from knowledge base (you can add better matching logic here)
    return jsonify({
        "replies": response.data,
        "message": user_message,
        "log_data":log_data,
        "timestamp": datetime.now().isoformat()
    })



@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(debug=True)
