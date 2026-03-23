
import re
import uuid
import time
import hashlib
import random
from concurrent.futures import ThreadPoolExecutor
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
from model import rewrite_query, rewrite_query_history, detect_query, llm_answer, llm_answer_stream, llm_answer_procedure, llm_answer_procedure_stream, classify_category, check_classify_phan_anh_kien_nghi, check_classify_tuong_tac
from test_demo import classify_v2
from embedding import get_proc_embedding, get_embedding
from utils import SUBJECT_KEYWORDS, GENERAL_INFO_SUBJECT_KEYWORDS, classify, prepare_subject_keywords
from export_metadata import classify_llm, classify_with_tong_quan, classify_with_phan_anh, classify_with_tuong_tac
from cache_backend import create_cache_backend

from scope_detect import extract_scope

PREPARED = prepare_subject_keywords(SUBJECT_KEYWORDS)

load_dotenv()

app = Flask(__name__)
CORS(app)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

def _to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _paginate(page, per_page):
    page = page if isinstance(page, int) and page > 0 else 1
    per_page = per_page if isinstance(per_page, int) and per_page > 0 else 20
    per_page = min(per_page, 100)
    start = (page - 1) * per_page
    end = start + per_page - 1
    return page, per_page, start, end


def _v2_list_response(items, page, per_page, total=None):
    total_pages = None
    if isinstance(total, int) and total >= 0:
        total_pages = max(1, (total + per_page - 1) // per_page) if per_page > 0 else 1

    payload = {
        "data": items or [],
        "pagination": {
            "page": page,
            "per_page": per_page,
        },
        "links": {},
    }

    if total_pages is not None:
        payload["pagination"]["total_pages"] = total_pages
        payload["pagination"]["total_items"] = total

    return payload


def _require_json_object():
    data = request.json or {}
    if not isinstance(data, dict):
        return None, (jsonify({"error": "Invalid JSON payload"}), 400)
    return data, None


@app.route('/api/cache-health', methods=['GET'])
def cache_health():
    try:
        health = cache_backend.health()
        return jsonify({
            "cache": health,
            "timestamp": datetime.now().isoformat(),
        }), 200
    except Exception as e:
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }), 500

resolver = AbbreviationResolver(SINGLE_TOKEN_MAP, CONTEXT_RULES)

# Cache backend: Redis when available, local TTL fallback otherwise.
cache_backend = create_cache_backend()
print("Cache backend:", cache_backend.backend_name)
print("Cache health:", cache_backend.health())
_log_executor = ThreadPoolExecutor(max_workers=4)
_embedding_cache = "embedding"
_classify_llm_cache = "classify_llm"
_detect_query_cache = "detect_query"
_search_v6_cache = "search_v6"
_related_chunks_cache = "related_chunks"
_prompt_templates_cache = "prompt_templates"
_resolve_tenant_cache = "resolve_tenant"
_classify_v2_cache = "classify_v2"
_classify_tuong_tac_cache = "classify_tuong_tac"
_classify_phan_anh_cache = "classify_phan_anh"
_classify_tong_quan_cache = "classify_tong_quan"
_classify_llm_procedure_cache = "classify_llm_procedure"
_session_history_cache = "session_history"
_tenant_exists_cache = "tenant_exists"
_tenant_id_map_cache = "tenant_id_map"
_CACHE_MISS = object()
_NULL_SENTINEL = "__CACHE_NULL_SENTINEL__"

CACHE_KEY_VERSION = "v2"
CACHE_TTL_JITTER_RATIO = 0.10
CACHE_QUERY_STOPWORDS = {
    "ah",
    "ak",
    "cho",
    "giup",
    "ha",
    "nhe",
    "nha",
    "nho",
    "oi",
    "roi",
    "the",
    "thi",
    "vay",
    "voi",
}

EMBEDDING_CACHE_TTL = 30 * 60
LLM_CLASSIFY_CACHE_TTL = 10 * 60
DETECT_QUERY_CACHE_TTL = 5 * 60
SEARCH_V6_CACHE_TTL = 60
RELATED_CHUNKS_CACHE_TTL = 120
PROMPT_TEMPLATES_CACHE_TTL = 60
RESOLVE_TENANT_CACHE_TTL = 10 * 60
CLASSIFY_V2_CACHE_TTL = 10 * 60
CLASSIFY_TUONG_TAC_CACHE_TTL = 5 * 60
CLASSIFY_PHAN_ANH_CACHE_TTL = 5 * 60
CLASSIFY_TONG_QUAN_CACHE_TTL = 5 * 60
CLASSIFY_LLM_PROCEDURE_CACHE_TTL = 10 * 60
SESSION_HISTORY_CACHE_TTL = 10 * 60
TENANT_EXISTS_CACHE_TTL = 10 * 60
TENANT_ID_MAP_CACHE_TTL = 10 * 60

EMBEDDING_CACHE_MAX = 2000
LLM_CLASSIFY_CACHE_MAX = 1000
DETECT_QUERY_CACHE_MAX = 500
SEARCH_V6_CACHE_MAX = 1500
RELATED_CHUNKS_CACHE_MAX = 2000
PROMPT_TEMPLATES_CACHE_MAX = 20
RESOLVE_TENANT_CACHE_MAX = 500
CLASSIFY_V2_CACHE_MAX = 1000
CLASSIFY_TUONG_TAC_CACHE_MAX = 500
CLASSIFY_PHAN_ANH_CACHE_MAX = 500
CLASSIFY_TONG_QUAN_CACHE_MAX = 500
CLASSIFY_LLM_PROCEDURE_CACHE_MAX = 500
SESSION_HISTORY_CACHE_MAX = 5000
TENANT_EXISTS_CACHE_MAX = 2000
TENANT_ID_MAP_CACHE_MAX = 2000
SESSION_HISTORY_ITEMS_MAX = 5


def _cache_get(cache, key):
    cached = cache_backend.get(cache, key)
    if cached is None:
        return _CACHE_MISS
    return cached


def _cache_set(cache, key, value, ttl_seconds, max_items):
    value_to_cache = _NULL_SENTINEL if value is None else value
    cache_backend.set(cache, key, value_to_cache, _jitter_ttl(ttl_seconds), max_items)


def _jitter_ttl(ttl_seconds):
    ttl = int(ttl_seconds or 0)
    if ttl <= 1:
        return 1

    jitter = max(1, int(ttl * CACHE_TTL_JITTER_RATIO))
    return max(1, ttl + random.randint(-jitter, jitter))


def _hash_text(value: str):
    return hashlib.sha1((value or "").encode("utf-8")).hexdigest()


def _canonical_query_for_cache(user_text: str):
    normalized = normalize_text(user_text or "")
    if not normalized:
        return ""

    tokens = [t for t in normalized.split() if t and t not in CACHE_QUERY_STOPWORDS]
    return " ".join(tokens)


def _cache_key(feature: str, *parts):
    normalized_parts = [CACHE_KEY_VERSION, feature]
    for part in parts:
        normalized_parts.append("" if part is None else str(part).strip())
    return "|".join(normalized_parts)


def _clone_rows(rows):
    return [dict(r) for r in (rows or [])]


def normalize_tenant_code(value):
    if value is None:
        return None

    tenant_code = str(value).strip()
    return tenant_code or None


def normalize_tenant_id(value):
    """
    Chuẩn hóa tenant_id (ID số trong hệ thống chính).
    Chấp nhận int hoặc chuỗi số, trả về str hoặc None.
    """
    if value is None:
        return None

    s = str(value).strip()
    if not s:
        return None
    if not s.isdigit():
        return None
    return s


def tenant_code_from_id(tenant_id: str):
    """
    Nhận tenant_id (ID trong hệ thống chính) và trả về tenant_code tương ứng trong Supabase.tenants.
    """
    if tenant_id is None:
        return None

    key = _cache_key("tenant_id_map", tenant_id)
    cached = _cache_get(_tenant_id_map_cache, key)
    if cached is not _CACHE_MISS:
        if cached == _NULL_SENTINEL:
            return None
        return cached

    # Giả định bảng tenants có cột id (primary key) và tenant_code
    response = (
        supabase.table("tenants")
        .select("tenant_code")
        .eq("id", tenant_id)
        .limit(1)
        .execute()
    )
    row = (response.data or [None])[0] if isinstance(response.data, list) else response.data
    code = (row or {}).get("tenant_code") if isinstance(row, dict) else None
    normalized_code = normalize_tenant_code(code)
    _cache_set(
        _tenant_id_map_cache,
        key,
        normalized_code,
        TENANT_ID_MAP_CACHE_TTL,
        TENANT_ID_MAP_CACHE_MAX,
    )
    return normalized_code


def ensure_tenant_code(tenant_id=None, tenant_code=None):
    """
    Chuẩn hóa để luôn có tenant_code:
    - Nếu tenant_code truyền vào hợp lệ → dùng luôn.
    - Nếu không, nhưng có tenant_id → map sang tenant_code qua bảng tenants.
    Trả về (tenant_code, error_message_or_None).
    """
    norm_code = normalize_tenant_code(tenant_code)
    if norm_code:
        return norm_code, None

    norm_id = normalize_tenant_id(tenant_id)
    if not norm_id:
        return None, "tenant_id or tenant_code is required"

    mapped_code = tenant_code_from_id(norm_id)
    if not mapped_code:
        return None, f"tenant_id '{norm_id}' does not exist"

    return mapped_code, None


def tenant_exists(tenant_code: str) -> bool:
    if tenant_code is None:
        return False

    key = _cache_key("tenant_exists", tenant_code)
    cached = _cache_get(_tenant_exists_cache, key)
    if cached is not _CACHE_MISS:
        return bool(cached)

    response = supabase.table("tenants") \
        .select("tenant_code") \
        .eq("tenant_code", tenant_code) \
        .limit(1) \
        .execute()

    exists = bool(response.data)
    _cache_set(
        _tenant_exists_cache,
        key,
        exists,
        TENANT_EXISTS_CACHE_TTL,
        TENANT_EXISTS_CACHE_MAX,
    )
    return exists


def get_embedding_cached(user_text: str):
    canonical = _canonical_query_for_cache(user_text)
    key = _cache_key("embedding", _hash_text(canonical))
    cached = _cache_get(_embedding_cache, key)
    if cached is not _CACHE_MISS:
        return cached

    emb = get_embedding(user_text)
    _cache_set(_embedding_cache, key, emb, EMBEDDING_CACHE_TTL, EMBEDDING_CACHE_MAX)
    return emb


def classify_llm_cached(user_text: str, prompt_template: str = None):
    canonical = _canonical_query_for_cache(user_text)
    template_hash = hashlib.sha1((prompt_template or "").encode("utf-8")).hexdigest()
    key = _cache_key("classify_llm", _hash_text(canonical), template_hash)
    cached = _cache_get(_classify_llm_cache, key)
    if cached is not _CACHE_MISS:
        if cached == _NULL_SENTINEL:
            return None
        return cached

    value = classify_category(user_text, prompt_template=prompt_template)
    _cache_set(_classify_llm_cache, key, value, LLM_CLASSIFY_CACHE_TTL, LLM_CLASSIFY_CACHE_MAX)
    return value

def resolve_target_tenant_code_cached(current_tenant_code, scope):
    key = _cache_key("resolve_tenant", current_tenant_code, scope)
    cached = _cache_get(_resolve_tenant_cache, key)

    if cached is not _CACHE_MISS:
        if cached == _NULL_SENTINEL:
            return None
        return cached

    response = supabase.rpc(
        "resolve_target_tenant_code",
        {
            "p_current_tenant_code": current_tenant_code,
            "p_target_scope": scope
        }
    ).execute()

    value = response.data
    _cache_set(
        _resolve_tenant_cache,
        key,
        value,
        RESOLVE_TENANT_CACHE_TTL,
        RESOLVE_TENANT_CACHE_MAX
    )
    return value

def get_active_prompt_templates_map():
    """
    Xây map prompt templates để pick_prompt_template() dùng trong luồng chat.

    Legacy: prompt_templates.prompt_type -> content
    System: system_prompts.name -> content (ưu tiên system_prompts để bạn "copy nội dung" sang đây)
    """
    templates = {}

    # 1) Ưu tiên system_prompts (mặc định key lấy từ `name`)
    try:
        sys_res = (
            supabase
            .table("system_prompts")
            .select("name, content, created_at")
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
        )
        for row in (sys_res.data or []):
            prompt_type = (row.get("name") or "").strip()
            if not prompt_type or prompt_type in templates:
                continue
            content = (row.get("content") or "").strip()
            if content:
                templates[prompt_type] = content
    except Exception:
        # Nếu bảng system_prompts chưa sẵn thì fallback legacy bên dưới
        pass

    # 2) Fallback legacy prompt_templates cho các prompt_type chưa có trong system_prompts
    response = (
        supabase
        .table("prompt_templates")
        .select("prompt_type, content, version")
        .eq("is_active", True)
        .order("version", desc=True)
        .execute()
    )

    for row in (response.data or []):
        prompt_type = (row.get("prompt_type") or "").strip()
        if not prompt_type or prompt_type in templates:
            continue

        content = (row.get("content") or "").strip()
        if content:
            templates[prompt_type] = content

    return templates


def get_active_prompt_templates_map_cached():
    key = _cache_key("prompt_templates", "active")
    cached = _cache_get(_prompt_templates_cache, key)
    if cached is not _CACHE_MISS:
        return dict(cached)

    templates = get_active_prompt_templates_map()
    _cache_set(
        _prompt_templates_cache,
        key,
        dict(templates),
        PROMPT_TEMPLATES_CACHE_TTL,
        PROMPT_TEMPLATES_CACHE_MAX,
    )
    return templates


def classify_v2_cached(normalized_query: str, prepared, tenant_code: str):
    """Cache wrapper for classify_v2 - rule-based category/subject classification"""
    canonical = _canonical_query_for_cache(normalized_query)
    key = _cache_key("classify_v2", tenant_code, _hash_text(canonical))
    cached = _cache_get(_classify_v2_cache, key)
    if cached is not _CACHE_MISS:
        return cached
    
    result = classify_v2(normalized_query, prepared)
    _cache_set(_classify_v2_cache, key, result, CLASSIFY_V2_CACHE_TTL, CLASSIFY_V2_CACHE_MAX)
    return result


def classify_tuong_tac_cached(user_message: str, tenant_code: str, prompt_template: str = None):
    """Cache wrapper for classify_with_tuong_tac - interaction subject classification"""
    canonical = _canonical_query_for_cache(user_message)
    template_hash = _hash_text(prompt_template or "")
    key = _cache_key("classify_tuong_tac", tenant_code, _hash_text(canonical), template_hash)
    cached = _cache_get(_classify_tuong_tac_cache, key)
    if cached is not _CACHE_MISS:
        if cached == _NULL_SENTINEL:
            return None
        return cached
    
    result = classify_with_tuong_tac(user_message, prompt_template=prompt_template)
    _cache_set(_classify_tuong_tac_cache, key, result, CLASSIFY_TUONG_TAC_CACHE_TTL, CLASSIFY_TUONG_TAC_CACHE_MAX)
    return result


def classify_phan_anh_cached(user_message: str, tenant_code: str, prompt_template: str = None):
    """Cache wrapper for classify_with_phan_anh - feedback/suggestion subject classification"""
    canonical = _canonical_query_for_cache(user_message)
    template_hash = _hash_text(prompt_template or "")
    key = _cache_key("classify_phan_anh", tenant_code, _hash_text(canonical), template_hash)
    cached = _cache_get(_classify_phan_anh_cache, key)
    if cached is not _CACHE_MISS:
        if cached == _NULL_SENTINEL:
            return None
        return cached
    
    result = classify_with_phan_anh(user_message, prompt_template=prompt_template)
    _cache_set(_classify_phan_anh_cache, key, result, CLASSIFY_PHAN_ANH_CACHE_TTL, CLASSIFY_PHAN_ANH_CACHE_MAX)
    return result


def classify_tong_quan_cached(user_message: str, tenant_code: str, prompt_template: str = None):
    """Cache wrapper for classify_with_tong_quan - general information subject classification"""
    canonical = _canonical_query_for_cache(user_message)
    template_hash = _hash_text(prompt_template or "")
    key = _cache_key("classify_tong_quan", tenant_code, _hash_text(canonical), template_hash)
    cached = _cache_get(_classify_tong_quan_cache, key)
    if cached is not _CACHE_MISS:
        if cached == _NULL_SENTINEL:
            return None
        return cached
    
    result = classify_with_tong_quan(user_message, prompt_template=prompt_template)
    _cache_set(_classify_tong_quan_cache, key, result, CLASSIFY_TONG_QUAN_CACHE_TTL, CLASSIFY_TONG_QUAN_CACHE_MAX)
    return result


def classify_llm_procedure_cached(user_message: str, prompt_template: str = None):
    """Cache wrapper for classify_llm - procedure metadata extraction & classification"""
    canonical = _canonical_query_for_cache(user_message)
    template_hash = _hash_text(prompt_template or "")
    key = _cache_key("classify_llm_procedure", _hash_text(canonical), template_hash)
    cached = _cache_get(_classify_llm_procedure_cache, key)
    if cached is not _CACHE_MISS:
        if cached == _NULL_SENTINEL:
            return None
        return cached
    
    result = classify_llm(user_message, prompt_template=prompt_template)
    _cache_set(_classify_llm_procedure_cache, key, result, CLASSIFY_LLM_PROCEDURE_CACHE_TTL, CLASSIFY_LLM_PROCEDURE_CACHE_MAX)
    return result


def pick_prompt_template(templates_map, prompt_type: str):
    if not isinstance(templates_map, dict):
        return None
    return templates_map.get(prompt_type)


def invalidate_prompt_templates_cache():
    cache_backend.delete(_prompt_templates_cache, _cache_key("prompt_templates", "active"))


def _parse_prompt_description_meta(description):
    """
    Legacy `prompt_templates.description` (có thể) chứa JSON:
      {"scope":"general","channel":"all"}
    """
    scope = "general"
    channel = "all"

    if not description:
        return scope, channel

    try:
        obj = description if isinstance(description, dict) else json.loads(str(description))
        if isinstance(obj, dict):
            scope = (obj.get("scope") or scope) or "general"
            channel = (obj.get("channel") or channel) or "all"
    except Exception:
        pass

    return scope, channel


def detect_query_cached(user_text: str, context: str):
    canonical = _canonical_query_for_cache(user_text)
    context_hash = hashlib.sha1((context or "").encode("utf-8")).hexdigest()
    key = _cache_key("detect_query", _hash_text(canonical), context_hash)
    cached = _cache_get(_detect_query_cache, key)
    if cached is not _CACHE_MISS:
        return cached

    value = detect_query(user_text, context)
    _cache_set(_detect_query_cache, key, value, DETECT_QUERY_CACHE_TTL, DETECT_QUERY_CACHE_MAX)
    return value


def search_documents_full_hybrid_v6_cached(normalized_query, query_embedding, category, subject, p_limit=5, tenant=None):
    if category == _NULL_SENTINEL:
        category = None
    if subject == _NULL_SENTINEL:
        subject = None
    if tenant == _NULL_SENTINEL:
        tenant = None

    canonical = _canonical_query_for_cache(normalized_query)
    key = _cache_key("search_v6", tenant, _hash_text(canonical), category, subject, p_limit)
    cached = _cache_get(_search_v6_cache, key)
    if cached is not _CACHE_MISS:
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


# ----------------------------
# New API surface (for external integrations)
# Base URL in Laravel: https://chatbot.mysuite.vn/api  (so routes below are /api/*)
# ----------------------------

@app.route('/api/chunks', methods=['GET'])
def v2_list_chunks():
    try:
        page = _to_int(request.args.get("page"), 1)
        per_page = _to_int(request.args.get("per_page"), 20)
        category = (request.args.get("category") or "").strip() or None
        subject = (request.args.get("subject") or "").strip() or None
        scope = (request.args.get("scope") or "").strip() or None
        search = (request.args.get("search") or "").strip() or None

        # Hỗ trợ cả tenant_id (từ hệ thống chính) và tenant_code (cũ)
        # Nếu không truyền tenant thì trả về all tenants (phục vụ màn hình quản trị tổng hợp).
        tenant_id = request.args.get("tenant_id")
        raw_tenant_code = request.args.get("tenant_code")
        tenant_code = None
        if (tenant_id and str(tenant_id).strip()) or (raw_tenant_code and str(raw_tenant_code).strip()):
            tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
            if err:
                return jsonify({"error": err}), 400
            if not tenant_exists(tenant_code):
                return jsonify({"error": "tenant_code does not exist"}), 400

        page, per_page, start, end = _paginate(page, per_page)

        base_query = supabase.table("documents").select(
            "id, text_content, category, subject, scope, tenant_code, updated_at"
        )

        if tenant_code:
            base_query = base_query.eq("tenant_code", tenant_code)

        if category:
            base_query = base_query.eq("category", category)
        if subject:
            base_query = base_query.eq("subject", subject)
        if scope:
            base_query = base_query.eq("scope", scope)

        # Fetch all matching rows first to compute total and then page in memory.
        # This keeps pagination and search consistent for now.
        res_all = base_query.order("updated_at", desc=True).execute()
        all_rows = res_all.data or []

        if search:
            needle = search.lower()
            all_rows = [
                r for r in all_rows
                if (r.get("text_content") or "").lower().find(needle) != -1
            ]

        total_items = len(all_rows)
        total_pages = max(1, (total_items + per_page - 1) // per_page) if per_page > 0 else 1

        page_rows = all_rows[start:end + 1] if total_items else []

        items = [
            {
                "id": row.get("id"),
                "content": row.get("text_content"),
                "category": row.get("category"),
                "subject": row.get("subject"),
                "scope": row.get("scope"),
                "tenant_code": row.get("tenant_code"),
                "source": None,
                "sourceType": None,
                "tokens": None,
                "createdAt": row.get("updated_at"),
            }
            for row in page_rows
        ]

        payload = _v2_list_response(items, page, per_page, total=total_items)
        return jsonify(payload), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/chunks/filters', methods=['GET'])
def v2_chunk_filters():
    try:
        # Distinct is not always supported consistently; pull limited fields and dedupe.
        res = supabase.table("documents").select("category, subject").execute()
        rows = res.data or []
        categories = sorted({(r.get("category") or "").strip() for r in rows if (r.get("category") or "").strip()})
        subjects = sorted({(r.get("subject") or "").strip() for r in rows if (r.get("subject") or "").strip()})
        return jsonify({"data": {"categories": categories, "subjects": subjects}}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/chunks', methods=['POST'])
def v2_create_chunk():
    try:
        data, err = _require_json_object()
        if err:
            return err

        content = (data.get("content") or "").strip()
        if not content:
            return jsonify({"error": "content is required"}), 400

        category = (data.get("category") or "").strip() or None
        subject = (data.get("subject") or "").strip() or None
        scope = (data.get("scope") or "").strip() or "xa_phuong"

        # Hỗ trợ cả tenant_id và tenant_code.
        # Riêng `scope == "quoc_gia"`: cho phép tạo chunk "null tenant" (tenant_code = None)
        # theo logic legacy ở `/api/create-chunk`.
        tenant_code = None
        if scope != "quoc_gia":
            tenant_id = data.get("tenant_id") or request.args.get("tenant_id")
            raw_tenant_code = data.get("tenant_code") or request.args.get("tenant_code")
            tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
            if err:
                return jsonify({"error": err}), 400
            if not tenant_exists(tenant_code):
                return jsonify({"error": "tenant_code does not exist"}), 400
        embedding = get_proc_embedding(content)
        if embedding is None:
            return jsonify({"error": "Failed to create embedding"}), 500

        procedure_name = extract_procedure_name(content) if category == "thu_tuc_hanh_chinh" else None

        row = {
            "tenant_code": tenant_code,
            "scope": scope,
            "procedure_name": procedure_name,
            "text_content": content,
            "normalized_text": normalize_text(procedure_name or content),
            "category": category,
            "subject": subject,
            "embedding": embedding,
        }

        res = supabase.table("documents").insert(row).execute()
        created = (res.data or [None])[0] if isinstance(res.data, list) else res.data

        out = {
            "id": created.get("id") if isinstance(created, dict) else None,
            "content": created.get("text_content") if isinstance(created, dict) else content,
            "category": created.get("category") if isinstance(created, dict) else category,
            "subject": created.get("subject") if isinstance(created, dict) else subject,
            "scope": created.get("scope") if isinstance(created, dict) else scope,
            "tenant_code": created.get("tenant_code") if isinstance(created, dict) else tenant_code,
            "source": None,
            "sourceType": None,
            "tokens": None,
            "createdAt": (created.get("created_at") or created.get("updated_at")) if isinstance(created, dict) else None,
        }

        return jsonify({"data": out}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/chunks/<chunk_id>', methods=['PUT'])
def v2_update_chunk(chunk_id):
    try:
        data, err = _require_json_object()
        if err:
            return err

        if "content" in data:
            content = (data.get("content") or "").strip()
            if not content:
                return jsonify({"error": "content is required"}), 400
        else:
            content = None

        patch = {}
        if content is not None:
            patch["text_content"] = content
            patch["embedding"] = get_proc_embedding(content)
            patch["normalized_text"] = normalize_text(content)

        if "category" in data:
            patch["category"] = (data.get("category") or "").strip() or None
        if "subject" in data:
            patch["subject"] = (data.get("subject") or "").strip() or None
        if "scope" in data:
            patch["scope"] = (data.get("scope") or "").strip() or None
        if "source" in data:
            patch["source"] = (data.get("source") or "").strip() or None
        if "sourceType" in data:
            patch["sourceType"] = (data.get("sourceType") or "").strip() or None
        if "tokens" in data:
            patch["tokens"] = _to_int(data.get("tokens"), None)

        if not patch:
            return jsonify({"error": "No fields to update"}), 400

        res = supabase.table("documents").update(patch).eq("id", chunk_id).execute()
        if not res.data:
            return jsonify({"error": "Chunk not found"}), 404

        updated = res.data[0] if isinstance(res.data, list) else res.data
        out = {
            "id": updated.get("id"),
            "content": updated.get("text_content"),
            "category": updated.get("category"),
            "subject": updated.get("subject"),
            "scope": updated.get("scope"),
            "tenant_code": updated.get("tenant_code"),
            "source": updated.get("source"),
            "sourceType": updated.get("sourceType"),
            "tokens": updated.get("tokens"),
            "createdAt": updated.get("created_at") or updated.get("updated_at"),
        }
        return jsonify({"data": out}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/chunks/<chunk_id>', methods=['DELETE'])
def v2_delete_chunk(chunk_id):
    try:
        res = supabase.table("documents").delete().eq("id", chunk_id).execute()
        if not res.data:
            return jsonify({"error": "Chunk not found"}), 404
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# System prompts (adapter)
# Legacy hiện tại dùng table `prompt_templates`, nên expose endpoint `/api/system-prompts` theo format dashboard.
@app.route('/api/system-prompts', methods=['GET'])
def v2_list_system_prompts():
    try:
        res = (
            supabase
            .table("prompt_templates")
            .select("id, prompt_name, content, description, is_active, created_at")
            .order("created_at", desc=True)
            .execute()
        )
        rows = res.data or []
        items = []
        for r in rows:
            scope, channel = _parse_prompt_description_meta(r.get("description"))
            items.append(
                {
                    "id": r.get("id"),
                    "name": r.get("prompt_name"),
                    "content": r.get("content"),
                    "scope": scope,
                    "channel": channel,
                    "isActive": bool(r.get("is_active")),
                    "createdAt": r.get("created_at"),
                }
            )
        return jsonify({"data": items}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/system-prompts', methods=['POST'])
def v2_create_system_prompt():
    try:
        data, err = _require_json_object()
        if err:
            return err

        name = (data.get("name") or "").strip()
        content = (data.get("content") or "").strip()
        scope = (data.get("scope") or "").strip()
        channel = (data.get("channel") or "").strip() or None
        is_active = _to_bool(data.get("isActive"), False)

        if not name:
            return jsonify({"error": "name is required"}), 400
        if not content:
            return jsonify({"error": "content is required"}), 400
        if not scope:
            return jsonify({"error": "scope is required"}), 400

        # Adapter: hệ thống hiện tại chỉ có legacy `prompt_templates`.
        # prompt_type bắt buộc => tạm set theo name để có thể tạo record.
        prompt_type = name
        description_meta = {"scope": scope, "channel": channel or "all"}

        row = {
            "prompt_name": name,
            "prompt_type": prompt_type,
            "content": content,
            "description": json.dumps(description_meta),
            "version": 1,
            "is_active": is_active,
        }
        res = supabase.table("prompt_templates").insert(row).execute()
        created = (res.data or [None])[0] if isinstance(res.data, list) else res.data

        out = {
            "id": created.get("id") if isinstance(created, dict) else None,
            "name": created.get("prompt_name") if isinstance(created, dict) else name,
            "content": created.get("content") if isinstance(created, dict) else content,
            "scope": scope,
            "channel": channel or "all",
            "isActive": bool(created.get("is_active")) if isinstance(created, dict) else is_active,
            "createdAt": created.get("created_at") if isinstance(created, dict) else None,
        }
        # Prompt templates (chat) depend on active prompt contents.
        invalidate_prompt_templates_cache()
        return jsonify({"data": out}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/system-prompts/<prompt_id>', methods=['PUT'])
def v2_update_system_prompt(prompt_id):
    try:
        data, err = _require_json_object()
        if err:
            return err

        current_res = (
            supabase
            .table("prompt_templates")
            .select("id, prompt_name, content, description, is_active, created_at")
            .eq("id", prompt_id)
            .single()
            .execute()
        )
        current = current_res.data or {}
        if not current:
            return jsonify({"error": "System prompt not found"}), 404

        cur_scope, cur_channel = _parse_prompt_description_meta(current.get("description"))
        new_scope = cur_scope
        new_channel = cur_channel

        patch = {}
        if "name" in data:
            new_name = (data.get("name") or "").strip()
            if not new_name:
                return jsonify({"error": "name is required"}), 400
            patch["prompt_name"] = new_name

        if "content" in data:
            new_content = (data.get("content") or "").strip()
            if not new_content:
                return jsonify({"error": "content is required"}), 400
            patch["content"] = new_content

        if "scope" in data:
            new_scope = (data.get("scope") or "").strip()
            if not new_scope:
                return jsonify({"error": "scope is required"}), 400

        if "channel" in data:
            ch = (data.get("channel") or "").strip()
            new_channel = ch or "all"

        if "scope" in data or "channel" in data:
            patch["description"] = json.dumps({"scope": new_scope, "channel": new_channel})

        if "isActive" in data:
            patch["is_active"] = _to_bool(data.get("isActive"), False)

        if not patch:
            return jsonify({"error": "No fields to update"}), 400

        supabase.table("prompt_templates").update(patch).eq("id", prompt_id).execute()

        out = {
            "id": prompt_id,
            "name": patch.get("prompt_name", current.get("prompt_name")),
            "content": patch.get("content", current.get("content")),
            "scope": new_scope,
            "channel": new_channel,
            "isActive": bool(patch.get("is_active", current.get("is_active"))),
            "createdAt": current.get("created_at"),
        }
        invalidate_prompt_templates_cache()
        return jsonify({"data": out}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/system-prompts/<prompt_id>', methods=['DELETE'])
def v2_delete_system_prompt(prompt_id):
    try:
        res = supabase.table("prompt_templates").delete().eq("id", prompt_id).execute()
        if not res.data:
            return jsonify({"error": "System prompt not found"}), 404
        invalidate_prompt_templates_cache()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Safety filters (expects a table named `safety_filters`)
@app.route('/api/safety-filters', methods=['GET'])
def v2_list_safety_filters():
    try:
        res = (
            supabase
            .table("safety_filters")
            .select("id, name, keywords, action, replacement, is_active, created_at")
            .order("created_at", desc=True)
            .execute()
        )
        rows = res.data or []
        items = [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "keywords": r.get("keywords") or [],
                "action": r.get("action"),
                "replacement": r.get("replacement"),
                "isActive": bool(r.get("is_active")),
                "createdAt": r.get("created_at"),
            }
            for r in rows
        ]
        return jsonify({"data": items}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/safety-filters', methods=['POST'])
def v2_create_safety_filter():
    try:
        data, err = _require_json_object()
        if err:
            return err

        name = (data.get("name") or "").strip()
        keywords = data.get("keywords")
        action = (data.get("action") or "").strip()
        replacement = (data.get("replacement") or "").strip() or None
        is_active = _to_bool(data.get("isActive"), False)

        if not name:
            return jsonify({"error": "name is required"}), 400
        if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
            return jsonify({"error": "keywords must be an array of strings"}), 400
        if not action:
            return jsonify({"error": "action is required"}), 400

        row = {
            "name": name,
            "keywords": keywords,
            "action": action,
            "replacement": replacement,
            "is_active": is_active,
        }
        res = supabase.table("safety_filters").insert(row).execute()
        created = (res.data or [None])[0] if isinstance(res.data, list) else res.data

        out = {
            "id": created.get("id") if isinstance(created, dict) else None,
            "name": created.get("name") if isinstance(created, dict) else name,
            "keywords": created.get("keywords") if isinstance(created, dict) else keywords,
            "action": created.get("action") if isinstance(created, dict) else action,
            "replacement": created.get("replacement") if isinstance(created, dict) else replacement,
            "isActive": bool(created.get("is_active")) if isinstance(created, dict) else is_active,
            "createdAt": created.get("created_at") if isinstance(created, dict) else None,
        }
        return jsonify({"data": out}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/safety-filters/<filter_id>', methods=['PUT'])
def v2_update_safety_filter(filter_id):
    try:
        data, err = _require_json_object()
        if err:
            return err

        patch = {}
        if "name" in data:
            patch["name"] = (data.get("name") or "").strip()
            if not patch["name"]:
                return jsonify({"error": "name is required"}), 400
        if "keywords" in data:
            keywords = data.get("keywords")
            if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
                return jsonify({"error": "keywords must be an array of strings"}), 400
            patch["keywords"] = keywords
        if "action" in data:
            patch["action"] = (data.get("action") or "").strip()
            if not patch["action"]:
                return jsonify({"error": "action is required"}), 400
        if "replacement" in data:
            patch["replacement"] = (data.get("replacement") or "").strip() or None
        if "isActive" in data:
            patch["is_active"] = _to_bool(data.get("isActive"), False)

        if not patch:
            return jsonify({"error": "No fields to update"}), 400

        res = supabase.table("safety_filters").update(patch).eq("id", filter_id).execute()
        if not res.data:
            return jsonify({"error": "Safety filter not found"}), 404
        updated = res.data[0] if isinstance(res.data, list) else res.data
        out = {
            "id": updated.get("id"),
            "name": updated.get("name"),
            "keywords": updated.get("keywords") or [],
            "action": updated.get("action"),
            "replacement": updated.get("replacement"),
            "isActive": bool(updated.get("is_active")),
            "createdAt": updated.get("created_at"),
        }
        return jsonify({"data": out}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/safety-filters/<filter_id>', methods=['DELETE'])
def v2_delete_safety_filter(filter_id):
    try:
        res = supabase.table("safety_filters").delete().eq("id", filter_id).execute()
        if not res.data:
            return jsonify({"error": "Safety filter not found"}), 404
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# FAQs (expects a table named `faqs`)
@app.route('/api/faqs', methods=['GET'])
def v2_list_faqs():
    try:
        page = _to_int(request.args.get("page"), 1)
        per_page = _to_int(request.args.get("per_page"), 20)
        category = (request.args.get("category") or "").strip() or None
        search = (request.args.get("search") or "").strip() or None

        page, per_page, start, end = _paginate(page, per_page)
        query = supabase.table("faqs").select(
            "id, question, answer, category, is_active, views, created_at"
        )
        if category:
            query = query.eq("category", category)

        res = query.order("created_at", desc=True).range(start, end).execute()
        rows = res.data or []

        if search:
            needle = search.lower()
            rows = [
                r for r in rows
                if (r.get("question") or "").lower().find(needle) != -1
                or (r.get("answer") or "").lower().find(needle) != -1
            ]

        items = [
            {
                "id": r.get("id"),
                "question": r.get("question"),
                "answer": r.get("answer"),
                "category": r.get("category"),
                "isActive": bool(r.get("is_active")),
                "views": r.get("views") or 0,
                "createdAt": r.get("created_at"),
            }
            for r in rows
        ]

        return jsonify(_v2_list_response(items, page, per_page)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/faqs', methods=['POST'])
def v2_create_faq():
    try:
        data, err = _require_json_object()
        if err:
            return err

        question = (data.get("question") or "").strip()
        answer = (data.get("answer") or "").strip()
        category = (data.get("category") or "").strip()
        is_active = _to_bool(data.get("isActive"), False)

        if not question:
            return jsonify({"error": "question is required"}), 400
        if not answer:
            return jsonify({"error": "answer is required"}), 400
        if not category:
            return jsonify({"error": "category is required"}), 400

        row = {
            "question": question,
            "answer": answer,
            "category": category,
            "is_active": is_active,
            "views": 0,
        }
        res = supabase.table("faqs").insert(row).execute()
        created = (res.data or [None])[0] if isinstance(res.data, list) else res.data

        out = {
            "id": created.get("id") if isinstance(created, dict) else None,
            "question": created.get("question") if isinstance(created, dict) else question,
            "answer": created.get("answer") if isinstance(created, dict) else answer,
            "category": created.get("category") if isinstance(created, dict) else category,
            "isActive": bool(created.get("is_active")) if isinstance(created, dict) else is_active,
            "views": created.get("views") if isinstance(created, dict) else 0,
            "createdAt": created.get("created_at") if isinstance(created, dict) else None,
        }
        return jsonify({"data": out}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/faqs/<faq_id>', methods=['PUT'])
def v2_update_faq(faq_id):
    try:
        data, err = _require_json_object()
        if err:
            return err

        patch = {}
        if "question" in data:
            patch["question"] = (data.get("question") or "").strip()
            if not patch["question"]:
                return jsonify({"error": "question is required"}), 400
        if "answer" in data:
            patch["answer"] = (data.get("answer") or "").strip()
            if not patch["answer"]:
                return jsonify({"error": "answer is required"}), 400
        if "category" in data:
            patch["category"] = (data.get("category") or "").strip()
            if not patch["category"]:
                return jsonify({"error": "category is required"}), 400
        if "isActive" in data:
            patch["is_active"] = _to_bool(data.get("isActive"), False)

        if not patch:
            return jsonify({"error": "No fields to update"}), 400

        res = supabase.table("faqs").update(patch).eq("id", faq_id).execute()
        if not res.data:
            return jsonify({"error": "FAQ not found"}), 404

        updated = res.data[0] if isinstance(res.data, list) else res.data
        out = {
            "id": updated.get("id"),
            "question": updated.get("question"),
            "answer": updated.get("answer"),
            "category": updated.get("category"),
            "isActive": bool(updated.get("is_active")),
            "views": updated.get("views") or 0,
            "createdAt": updated.get("created_at"),
        }
        return jsonify({"data": out}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/faqs/<faq_id>', methods=['DELETE'])
def v2_delete_faq(faq_id):
    try:
        res = supabase.table("faqs").delete().eq("id", faq_id).execute()
        if not res.data:
            return jsonify({"error": "FAQ not found"}), 404
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Chat sessions (derived from `log_query.session_chat`)
@app.route('/api/chat-sessions', methods=['GET'])
def v2_list_chat_sessions():
    try:
        page = _to_int(request.args.get("page"), 1)
        per_page = _to_int(request.args.get("per_page"), 20)
        search = (request.args.get("search") or "").strip() or None
        channel = (request.args.get("channel") or "").strip() or None  # not stored currently
        from_ts = (request.args.get("from") or "").strip() or None
        to_ts = (request.args.get("to") or "").strip() or None
        tenant_id = request.args.get("tenant_id")
        raw_tenant_code = request.args.get("tenant_code")

        tenant_code = None
        if (tenant_id and str(tenant_id).strip()) or (raw_tenant_code and str(raw_tenant_code).strip()):
            tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
            if err:
                return jsonify({"error": err}), 400
            if not tenant_exists(tenant_code):
                return jsonify({"error": "tenant_code does not exist"}), 400

        page, per_page, start, end = _paginate(page, per_page)

        q = supabase.table("log_query").select(
            "session_chat, raw_query, answer, created_at, tenant_code"
        ).eq("event_type", "normal").order("created_at", desc=True)

        if tenant_code:
            q = q.eq("tenant_code", tenant_code)

        if from_ts:
            q = q.gte("created_at", from_ts)
        if to_ts:
            q = q.lte("created_at", to_ts)

        res = q.range(0, 2000).execute()
        rows = res.data or []

        if search:
            needle = search.lower()
            rows = [
                r for r in rows
                if (r.get("raw_query") or "").lower().find(needle) != -1
                or (r.get("answer") or "").lower().find(needle) != -1
            ]

        # Deduplicate by session_chat keeping latest message (already ordered desc).
        seen = set()
        sessions = []
        for r in rows:
            sid = r.get("session_chat")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            sessions.append({
                "id": sid,
                "channel": channel,  # best-effort; no persisted channel in log_query
                "tenantCode": r.get("tenant_code"),
                "lastMessageAt": r.get("created_at"),
                "lastUserMessage": r.get("raw_query"),
                "lastBotMessage": r.get("answer"),
            })

        paged = sessions[start:start + per_page]
        return jsonify(_v2_list_response(paged, page, per_page, total=len(sessions))), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/chat-sessions/<session_id>', methods=['GET'])
def v2_get_chat_session(session_id):
    try:
        tenant_id = request.args.get("tenant_id")
        raw_tenant_code = request.args.get("tenant_code")

        tenant_code = None
        if (tenant_id and str(tenant_id).strip()) or (raw_tenant_code and str(raw_tenant_code).strip()):
            tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
            if err:
                return jsonify({"error": err}), 400
            if not tenant_exists(tenant_code):
                return jsonify({"error": "tenant_code does not exist"}), 400

        res = (
            supabase
            .table("log_query")
            .select("raw_query, answer, created_at, event_type, tenant_code")
            .eq("session_chat", session_id)
            .eq("event_type", "normal")
        )
        if tenant_code:
            res = res.eq("tenant_code", tenant_code)

        res = res.order("created_at").execute()
        rows = res.data or []
        messages = []
        for r in rows:
            ts = r.get("created_at")
            uq = (r.get("raw_query") or "").strip()
            aq = (r.get("answer") or "").strip()
            if uq:
                messages.append({"role": "user", "content": uq, "timestamp": ts})
            if aq:
                messages.append({"role": "bot", "content": aq, "timestamp": ts})

        payload = {
            "session": {"id": session_id},
            "messages": messages,
        }
        return jsonify({"data": payload}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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


@app.route('/api/get-tenants', methods=['GET'])
def get_tenants():
    try:
        has_chunks_only = _to_bool(request.args.get("has_chunks_only"), default=False)

        response = supabase.table("tenants") \
            .select("id, tenant_code, scope, parent_id") \
            .order("tenant_code") \
            .execute()

        tenants = response.data or []

        if has_chunks_only:
            # Chỉ giữ tenant có ít nhất 1 chunk trong bảng documents
            docs_res = supabase.table("documents") \
                .select("tenant_code") \
                .execute()
            docs = docs_res.data or []
            tenant_codes_with_chunks = {
                (row.get("tenant_code") or "").strip()
                for row in docs
                if (row.get("tenant_code") or "").strip()
            }

            tenants = [
                t for t in tenants
                if (t.get("tenant_code") or "").strip() in tenant_codes_with_chunks
            ]

        return jsonify({
            "tenants": tenants
        }), 200
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route('/api/get-prompts', methods=['GET'])
def get_prompts():
    try:
        response = supabase.table("prompt_templates") \
            .select("id, prompt_name, prompt_type, content, description, version, is_active, created_at") \
            .order("prompt_name") \
            .execute()

        return jsonify({
            "prompts": response.data or []
        }), 200
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route('/api/create-prompt', methods=['POST'])
def create_prompt():
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON payload"}), 400

        prompt_name = (data.get("prompt_name") or "").strip()
        prompt_type = (data.get("prompt_type") or "").strip()
        content = (data.get("content") or "").strip()
        description = data.get("description")
        version = data.get("version", 1)
        is_active = data.get("is_active", True)

        if not prompt_name:
            return jsonify({"error": "prompt_name is required"}), 400
        if not prompt_type:
            return jsonify({"error": "prompt_type is required"}), 400
        if not content:
            return jsonify({"error": "content is required"}), 400

        try:
            version = int(version)
        except (TypeError, ValueError):
            return jsonify({"error": "version must be an integer"}), 400

        if version <= 0:
            return jsonify({"error": "version must be greater than 0"}), 400

        if not isinstance(is_active, bool):
            return jsonify({"error": "is_active must be a boolean"}), 400

        if description is not None:
            description = str(description).strip() or None

        payload = {
            "prompt_name": prompt_name,
            "prompt_type": prompt_type,
            "content": content,
            "description": description,
            "version": version,
            "is_active": is_active,
        }

        response = supabase.table("prompt_templates") \
            .insert(payload) \
            .execute()

        invalidate_prompt_templates_cache()

        return jsonify({
            "message": "Prompt created successfully",
            "data": response.data
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/update-prompt/<prompt_id>', methods=['PUT'])
def update_prompt(prompt_id):
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON payload"}), 400

        prompt_name = (data.get("prompt_name") or "").strip()
        prompt_type = (data.get("prompt_type") or "").strip()
        content = (data.get("content") or "").strip()
        description = data.get("description")
        version = data.get("version", 1)
        is_active = data.get("is_active", True)

        if not prompt_name:
            return jsonify({"error": "prompt_name is required"}), 400
        if not prompt_type:
            return jsonify({"error": "prompt_type is required"}), 400
        if not content:
            return jsonify({"error": "content is required"}), 400

        try:
            version = int(version)
        except (TypeError, ValueError):
            return jsonify({"error": "version must be an integer"}), 400

        if version <= 0:
            return jsonify({"error": "version must be greater than 0"}), 400

        if not isinstance(is_active, bool):
            return jsonify({"error": "is_active must be a boolean"}), 400

        if description is not None:
            description = str(description).strip() or None

        payload = {
            "prompt_name": prompt_name,
            "prompt_type": prompt_type,
            "content": content,
            "description": description,
            "version": version,
            "is_active": is_active,
        }

        response = supabase.table("prompt_templates") \
            .update(payload) \
            .eq("id", prompt_id) \
            .execute()

        if not response.data:
            return jsonify({"error": "Prompt not found"}), 404

        invalidate_prompt_templates_cache()

        return jsonify({
            "message": "Prompt updated successfully",
            "data": response.data
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/delete-prompt/<prompt_id>', methods=['DELETE'])
def delete_prompt(prompt_id):
    try:
        response = supabase.table("prompt_templates") \
            .delete() \
            .eq("id", prompt_id) \
            .execute()

        if not response.data:
            return jsonify({"error": "Prompt not found"}), 404

        invalidate_prompt_templates_cache()

        return jsonify({
            "message": "Prompt deleted successfully"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/toggle-prompt/<prompt_id>', methods=['POST'])
def toggle_prompt(prompt_id):
    try:
        current_res = supabase.table("prompt_templates") \
            .select("is_active") \
            .eq("id", prompt_id) \
            .single() \
            .execute()

        current_value = bool(current_res.data.get("is_active", True))

        updated = supabase.table("prompt_templates") \
            .update({"is_active": not current_value}) \
            .eq("id", prompt_id) \
            .execute()

        if not updated.data:
            return jsonify({"error": "Prompt not found"}), 404

        invalidate_prompt_templates_cache()

        return jsonify({
            "success": True,
            "is_active": (not current_value)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        data = request.json or {}

        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON payload"}), 400

        # Validate cơ bản
        if not data.get("text_content"):
            return jsonify({"error": "text_content is required"}), 400
        tenant_code = normalize_tenant_code(data.get("tenant_code"))
        scope = (data.get("scope") or '').strip() or 'xa_phuong'
        
        if scope == "quoc_gia":
            tenant_code = None
        elif tenant_code is None:
            return jsonify({"error": "tenant_code is required"}), 400
        elif not tenant_exists(tenant_code):
            return jsonify({"error": f"tenant_code '{tenant_code}' does not exist"}), 400

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
        print(f"Error creating chunk: {e}")
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

        _update_session_history_cache(log_data)

        return jsonify({
            "message": "Log created successfully",
            "data": response.data
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def enqueue_log(log_data):
    if not isinstance(log_data, dict):
        return

    payload = dict(log_data)

    def _write_log(record):
        try:
            supabase.table("log_query").insert(record).execute()
            _update_session_history_cache(record)
        except Exception as e:
            print(f"enqueue_log failed: {e}")

    _log_executor.submit(_write_log, payload)

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

    data = request.json or {}
    session_id = data.get("session_id")

    # Hỗ trợ cả tenant_id và tenant_code
    tenant_id = data.get("tenant_id")
    raw_tenant_code = data.get("tenant_code")
    tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
    if err:
        return jsonify({"error": err}), 400

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


# @app.route('/api/chunk-relations', methods=['GET'])
# def get_chunk_relations():
#     try:
#         source_chunk_id = request.args.get("source_chunk_id", default=None, type=str)
#         tenant_code = request.args.get("tenant_code", default=None, type=str)

#         if not source_chunk_id:
#             return jsonify({"error": "source_chunk_id is required"}), 400

#         query = (
#             supabase
#             .table("chunk_relations")
#             .select("source_chunk_id,target_chunk_id,tenant_code,create_at")
#             .eq("source_chunk_id", source_chunk_id)
#         )

#         if tenant_code:
#             query = query.eq("tenant_code", tenant_code)

#         rel_res = query.execute()
#         relations = rel_res.data or []
#         target_ids = [r.get("target_chunk_id") for r in relations if r.get("target_chunk_id")]

#         targets = []
#         if target_ids:
#             doc_query = (
#                 supabase
#                 .table("documents")
#                 .select("id,text_content,category,subject,tenant_code")
#                 .in_("id", target_ids)
#             )
#             if tenant_code:
#                 doc_query = doc_query.eq("tenant_code", tenant_code)
#             doc_res = doc_query.execute()
#             targets = doc_res.data or []

#         return jsonify({
#             "relations": relations,
#             "targets": targets
#         }), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


@app.route('/api/chunk-relations/bulk-create', methods=['POST'])
def bulk_create_chunk_relations():
    try:
        data = request.json or {}
        source_chunk_id = data.get("source_chunk_id")
        # Hỗ trợ cả tenant_id và tenant_code
        tenant_id = data.get("tenant_id")
        raw_tenant_code = data.get("tenant_code")
        tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
        if err:
            return jsonify({"error": err}), 400
        target_chunk_ids = data.get("target_chunk_ids") or []

        if not source_chunk_id:
            return jsonify({"error": "source_chunk_id is required"}), 400
        if not isinstance(target_chunk_ids, list) or not target_chunk_ids:
            return jsonify({"error": "target_chunk_ids is required"}), 400

        unique_ids = [str(tid) for tid in dict.fromkeys(target_chunk_ids) if tid and str(tid) != str(source_chunk_id)]
        if not unique_ids:
            return jsonify({"message": "No valid target ids", "inserted": 0}), 200

        rows = [
            {
                "tenant_code": tenant_code,
                "source_chunk_id": source_chunk_id,
                "target_chunk_id": tid,
            }
            for tid in unique_ids
        ]

        inserted = 0
        skipped = 0
        for row in rows:
            exists_query = (
                supabase
                .table("chunk_relations")
                .select("source_chunk_id")
                .eq("source_chunk_id", row["source_chunk_id"])
                .eq("target_chunk_id", row["target_chunk_id"])
            )
            if row.get("tenant_code"):
                exists_query = exists_query.eq("tenant_code", row["tenant_code"])
            exists = exists_query.limit(1).execute()
            if exists.data:
                skipped += 1
                continue

            supabase.table("chunk_relations").insert(row).execute()
            inserted += 1

        return jsonify({
            "message": "Chunk relations processed",
            "inserted": inserted,
            "skipped": skipped
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/chunk-relations/bulk-delete', methods=['POST'])
def bulk_delete_chunk_relations():
    try:
        data = request.json or {}
        source_chunk_id = data.get("source_chunk_id")
        # Hỗ trợ cả tenant_id và tenant_code
        tenant_id = data.get("tenant_id")
        raw_tenant_code = data.get("tenant_code")
        tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
        if err:
            return jsonify({"error": err}), 400
        target_chunk_ids = data.get("target_chunk_ids") or []

        if not source_chunk_id:
            return jsonify({"error": "source_chunk_id is required"}), 400
        if not isinstance(target_chunk_ids, list) or not target_chunk_ids:
            return jsonify({"error": "target_chunk_ids is required"}), 400

        query = (
            supabase
            .table("chunk_relations")
            .delete()
            .eq("source_chunk_id", source_chunk_id)
            .in_("target_chunk_id", target_chunk_ids)
        )
        if tenant_code:
            query = query.eq("tenant_code", tenant_code)

        response = query.execute()
        deleted_count = len(response.data or [])

        return jsonify({
            "message": "Chunk relations deleted",
            "deleted": deleted_count
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    key = _cache_key("related_chunks", tenant_code, source_chunk_id)
    cached = _cache_get(_related_chunks_cache, key)
    if cached is not _CACHE_MISS:
        return _clone_rows(cached)

    rows = get_related_chunks(supabase, tenant_code, source_chunk_id)
    _cache_set(_related_chunks_cache, key, _clone_rows(rows), RELATED_CHUNKS_CACHE_TTL, RELATED_CHUNKS_CACHE_MAX)
    return rows


def _session_history_cache_key(session_id: str, tenant_code: str):
    return _cache_key("session_history", tenant_code, session_id)


def get_recent_session_history_cached(session_id: str, tenant_code: str, limit: int = 2):
    limit = limit if isinstance(limit, int) and limit > 0 else 2
    key = _session_history_cache_key(session_id, tenant_code)
    cached = _cache_get(_session_history_cache, key)
    if cached is not _CACHE_MISS:
        return _clone_rows((cached or [])[:limit])

    response = (
        supabase
        .table("log_query")
        .select("expanded_query")
        .eq("session_chat", session_id)
        .eq("event_type", "normal")
        .eq("tenant_code", tenant_code)
        .order("created_at", desc=True)
        .limit(max(limit, SESSION_HISTORY_ITEMS_MAX))
        .execute()
    )

    rows = response.data or []
    _cache_set(
        _session_history_cache,
        key,
        _clone_rows(rows),
        SESSION_HISTORY_CACHE_TTL,
        SESSION_HISTORY_CACHE_MAX,
    )
    return rows[:limit]


def _update_session_history_cache(log_data):
    if not isinstance(log_data, dict):
        return
    if log_data.get("event_type") != "normal":
        return

    session_id = (log_data.get("session_chat") or "").strip()
    tenant_code = normalize_tenant_code(log_data.get("tenant_code"))
    expanded_query = (log_data.get("expanded_query") or "").strip()
    if not session_id or not tenant_code or not expanded_query:
        return

    key = _session_history_cache_key(session_id, tenant_code)
    cached = _cache_get(_session_history_cache, key)
    rows = _clone_rows(cached) if cached is not _CACHE_MISS else []

    rows = [{"expanded_query": expanded_query}] + [
        row for row in rows
        if (row.get("expanded_query") or "").strip() != expanded_query
    ]
    rows = rows[:SESSION_HISTORY_ITEMS_MAX]

    _cache_set(
        _session_history_cache,
        key,
        rows,
        SESSION_HISTORY_CACHE_TTL,
        SESSION_HISTORY_CACHE_MAX,
    )


def normalize_llm_label(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.lower() in {"none", "null", "unknown", "n/a"}:
        return None
    return s


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
        data = request.json or {}
        session_id = data.get("session_id")
        print("Session:", session_id)
        user_message = data.get('message', '').strip()
        origin_mess = user_message
        try:
            chunk_generate = int(data.get("chunk_limit", 1))
        except (TypeError, ValueError):
            chunk_generate = 1
        chunk_generate = max(1, min(chunk_generate, 6))

        # Hỗ trợ cả tenant_id và tenant_code
        tenant_id = data.get("tenant_id")
        raw_tenant_code = data.get("tenant_code")
        tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
        log_data = {}

        LOG_FLUSH_INTERVAL_SECONDS = 0.08
        LOG_BUFFER_MAX = 64
        pending_logs = []
        last_log_flush_at = time.perf_counter()

        def flush_logs(force=False):
            nonlocal last_log_flush_at
            if not pending_logs:
                return

            now = time.perf_counter()
            if not force and (now - last_log_flush_at) < LOG_FLUSH_INTERVAL_SECONDS:
                return

            batch = "\n".join(pending_logs)
            pending_logs.clear()
            last_log_flush_at = now
            yield f"data: {json.dumps({'thought': batch}, ensure_ascii=False)}\n\n"

        def emit_log(message, force=False):
            if message is None:
                return

            if len(pending_logs) >= LOG_BUFFER_MAX:
                pending_logs.pop(0)
            pending_logs.append(str(message))
            yield from flush_logs(force=force)

        if err:
            yield f"data: {json.dumps({'replies': err, 'chunks': []})}\n\n"
            return

        if not tenant_exists(tenant_code):
            yield f"data: {json.dumps({'replies': 'Tenant được chọn không tồn tại trong hệ thống.', 'chunks': []})}\n\n"
            return
        
        yield from emit_log(f"Đã nhận câu hỏi anh/chị: {origin_mess}")

        try:
            prompt_templates = get_active_prompt_templates_map_cached()
        except Exception as e:
            prompt_templates = {}
            yield from emit_log(f"Không thể tải prompt templates: {str(e)}", force=True)

        history_rewrite_prompt = pick_prompt_template(prompt_templates, "history_rewrite")
        classify_category_prompt = pick_prompt_template(prompt_templates, "classify_category")
        classify_subject_procedure_prompt = pick_prompt_template(prompt_templates, "classify_subject_procedure")
        answer_procedure_prompt = pick_prompt_template(prompt_templates, "answer_procedure")
        classify_subject_qa_prompt = pick_prompt_template(prompt_templates, "classify_subject_QA")
        classify_subject_tuong_tac_prompt = pick_prompt_template(prompt_templates, "classify_subject_tuong_tac")
        classify_subject_phan_anh_prompt = pick_prompt_template(prompt_templates, "classify_subject_phan_anh")
        answer_qa_prompt = pick_prompt_template(prompt_templates, "answer_QA")

        start_flow = time.perf_counter()

        history_data = get_recent_session_history_cached(session_id, tenant_code, limit=2)

        help_content = [
            "Kính chào anh/chị! ",
            "Rất vui được hỗ trợ anh/chị. ",
            "Anh/chị có thể hỏi về các thủ tục hành chính, thông tin chung, ",
            "hoặc tổ chức bộ máy của phường. ",
            "Anh/chị cần giúp đỡ về vấn đề gì ạ?"
        ]

        thank_you_content = ["Cảm ơn anh/chị đã đặt câu hỏi. ", "Hy vọng những thông tin", "trên sẽ hữu ích cho anh/chị. Nếu còn thắc mắc nào khác,", "anh/chị đừng ngần ngại"," hỏi thêm nhé. Chúc anh/chị một ngày tốt lành!"]

        out_of_score_content = "Nội dung anh/chị hỏi nằm ngoài phạm vi hỗ trợ của hệ thống.\nAnh/chị vui lòng liên hệ đơn vị phù hợp hoặc đặt câu hỏi liên quan đến thủ tục hành chính để được hỗ trợ."
        not_have_content = "Dạ, hiện tại hệ thống đang cập nhật thêm thông tin về phường, các thủ tục để hỗ trợ anh/chị tốt hơn ạ. Anh/chị còn câu hỏi nào thắc mắc không ạ?" 
        banned_replies = "Dạ em chỉ hỗ trợ anh/chị về các thủ tục hành chính, thông tin chung, hoặc tổ chức bộ máy của phường thôi ạ. Anh/chị vui lòng đặt câu hỏi liên quan đến những chủ đề này để được hỗ trợ tốt nhất nhé."

        yield f"data: {json.dumps({'log': f'Nhận message...'})}\n\n"

        yield f"data: {json.dumps({'log': f'Kiểm tra viết tắt'})}\n\n"
        result = resolver.process(user_message)
        user_message = result["expanded"]
        normalized_query = result["normalized"]

        yield f"data: {json.dumps({'log': f'{result}'})}\n\n"
        yield f"data: {json.dumps({'log': f'Kiểm tra blacklist'})}\n\n"
        yield from emit_log("Đang xử lý nội dung câu hỏi\n")
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
            yield f"data: {json.dumps({'log': f'[Blocked] Query: {user_message} => keyword: {matched_keyword}'})}\n\n"
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'replies': banned_replies, 'chunks': []})}\n\n"
            return

        if not history_data:
            start = time.perf_counter()
            user_message = rewrite_query(user_message, prompt_template=None)

            normalized_query = normalize_text(user_message)

            end = time.perf_counter()
            duration = (end - start) * 1000 

            yield f"data: {json.dumps({'log': f'[{round(duration / 1000,2)}s] - Câu hỏi hoàn chỉnh (không có lịch sử hội thoại): {user_message}'})}\n\n"

        if history_data:

            # last_answer = history_data[0]["answer"]
            # print(f"Câu trả lời trước: {last_answer}")
            last_question = history_data[0]["expanded_query"]
            yield f"data: {json.dumps({'log': f'Câu hỏi trước đó: {last_question}'})}\n\n"

            user_message = rewrite_query_history(user_message, last_question, prompt_template=history_rewrite_prompt)
            normalized_query = normalize_text(user_message)

            yield f"data: {json.dumps({'log': f'Câu hỏi hoàn chỉnh (có lịch sử): {user_message}'})}\n\n"

        yield from emit_log("Đang xác định thông tin cần tra cứu")

        res = classify_v2_cached(normalized_query, PREPARED, tenant_code)
        category, subject = res["category"], res["subject"]
        yield f"data: {json.dumps({'log': f'Category: {category}, Subject: {subject}'})}\n\n"
        

        if res["need_llm"]:
            # print(f"Cần LLM để phân loại thêm, đang thực hiện phân loại bằng LLM...")
            # yield f"data: {json.dumps({'log': f'Bắt đầu sử dụng LLM để trích xuất'})}\n\n"
            category_llm = classify_llm_cached(user_message, prompt_template=classify_category_prompt)
            yield f"data: {json.dumps({'log': f'LLM classify => Category: {category_llm}'})}\n\n"

            category = normalize_llm_label(category_llm)
        
        print(f"Category: {category}")
        
        if category == "chu_de_cam":
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'replies': banned_replies, 'chunks': []})}\n\n"
            return
            
        if category == "thu_tuc_hanh_chinh":
            yield from emit_log("=> Đang xác định các thủ tục liên quan")
            meta = classify_llm_procedure_cached(user_message, prompt_template=classify_subject_procedure_prompt)

            if not meta or not isinstance(meta, dict):
                return

            query_mode = meta.get("query_mode")
            # print(f"Query mode: {query_mode}")

            procedures = meta.get("unit") or []
            if not procedures:
                return

            chunk_response = []
            yield f"data: {json.dumps({'log': f'=> Phân tích thủ tục : {query_mode}'})}\n\n"

            if query_mode == "single_procedure":
                procedure_name = procedures[0].get("procedure")
                procedure_action = procedures[0].get("procedure_action")
                special_contexts = procedures[0].get("special_contexts") or []


                yield from emit_log(f"=> Đã xác định tên thủ tục: {procedure_name}")
                yield from emit_log("Đang tìm các tài liệu liên quan")
                yield f"data: {json.dumps({'log': f'=> Tên thủ tục: {procedure_name}'})}\n\n"
                yield f"data: {json.dumps({'log': f'=> Procedure_action: {procedure_action}, Special_contexts: {special_contexts}'})}\n\n"
                response = supabase.rpc(
                    "search_documents_full_hybrid_thu_tuc_v1",
                    {
                        "p_query_format": normalize_text(procedure_name),
                        "p_query_embedding": get_embedding_cached(procedure_name),
                        "p_tenant": None,
                        "p_category": category,
                        "p_subject": procedures[0]['subject'],
                        "p_procedure": normalize_text(procedure_name),
                        "p_procedure_action": procedure_action,
                        "p_special_contexts": special_contexts,
                        "p_limit": 3
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
                    yield from emit_log(f"=> Đã xác định tên thủ tục: {procedure_name}")
                    yield from emit_log("Đang tìm các tài liệu liên quan")
                    yield f"data: {json.dumps({'log': f'=> Tên thủ tục: {procedure_name}'})}\n\n"
                    yield f"data: {json.dumps({'log': f'=> Procedure_action: {procedure_action}, Special_contexts: {special_contexts}'})}\n\n"
                    response = supabase.rpc(
                        "search_documents_full_hybrid_thu_tuc_v1",
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
                for i, chunk in enumerate(chunks)
            ) if chunks else "Không tìm thấy tài liệu phù hợp."

            print(f"Context length for LLM: {len(context)}")

            yield from emit_log("Anh/chị chờ chút, đang tổng hợp câu trả lời", force=True)
            # answer = "\n\n".join(
            #     f"Sử dụng các tài liệu sau:\n### Tài liệu {i+1}\n{chunk['text_content']}"
            #     for i, chunk in enumerate(chunks)
            # )
    
            full_answer = ""
            for token in llm_answer_procedure_stream(user_message, context, prompt_template=answer_procedure_prompt):
                full_answer += token
                yield from flush_logs()
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        
            answer = full_answer
            yield f"data: {json.dumps({'done': True, 'chunks': chunks}, ensure_ascii=False)}\n\n"

            end = time.perf_counter()
            duration = (end - start_flow) * 1000 
            log_data["tenant_code"] = tenant_code
            log_data["raw_query"] = origin_mess
            log_data["expanded_query"] = user_message
            log_data["answer"]= answer
            log_data["detected_category"]= category
            log_data["detected_subject"]= subject
            log_data["event_type"] = "normal"
            top_chunk = chunks[0] if chunks else {}
            log_data["alias_score"]= top_chunk.get("alias_score", 0)
            log_data["document_score"]= top_chunk.get("document_score", 0)
            log_data["confidence_score"]= top_chunk.get("confidence_score", 0)
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            enqueue_log(log_data)
            yield from flush_logs(force=True)

            return

        if category == "tuong_tac":
            subject = classify_tuong_tac_cached(user_message, tenant_code, prompt_template=classify_subject_tuong_tac_prompt)
            subject = normalize_subject_value(subject)
            if subject is None:
                subject = "chao_hoi"
            
            print(f"Subject for tuong_tac: {subject}")
            
            yield from emit_log("Đang xử lý nội dung câu hỏi")
            yield f"data: {json.dumps({'log': f'=> Subject: {subject}'})}\n\n"

            if subject == "chao_hoi":
                full_answer = ""
                for token in help_content:
                    full_answer += token
                    yield from flush_logs()
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                # yield f"data: {json.dumps({'replies': help_content, 'chunks': []})}\n\n"
                end = time.perf_counter()
                duration = (end - start_flow) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= full_answer
                log_data["event_type"] = "normal"
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                enqueue_log(log_data)
                yield from flush_logs(force=True)
                return
            if subject == "cam_on_tam_biet":
                full_answer = ""
                for token in thank_you_content:
                    full_answer += token
                    yield from flush_logs()
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                end = time.perf_counter()
                duration = (end - start_flow) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= full_answer
                log_data["event_type"] = "normal"
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                enqueue_log(log_data)
                yield from flush_logs(force=True)
                return
        
            if subject == "phan_nan_buc_xuc":
                end = time.perf_counter()
                duration = (end - start_flow) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= "Tôi rất tiếc vì anh/chị chưa hài lòng. Anh/chị hãy nói rõ phần còn vướng, tôi sẽ hỗ trợ lại ngay."
                log_data["event_type"] = "complaint"
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                enqueue_log(log_data)
                yield from emit_log("=> Phân loại tương tác - phàn nàn", force=True)
                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'replies': 'Tôi rất tiếc vì anh/chị chưa hài lòng. Anh/chị hãy nói rõ phần còn vướng, tôi sẽ hỗ trợ lại ngay.', 'chunks': []})}\n\n"
                return
            
            if subject == "xuc_pham_vi_pham":
                end = time.perf_counter()
                duration = (end - start_flow) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= "Tôi vẫn sẵn sàng hỗ trợ anh/chị về nội dung hành chính. Anh/chị vui lòng sử dụng ngôn từ phù hợp để tôi có thể hỗ trợ tốt hơn."
                log_data["event_type"] = "banned_topic"
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                enqueue_log(log_data)
                yield from emit_log("=> Phân loại tương tác - xúc phạm/vi phạm", force=True)
                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'replies': 'Tôi vẫn sẵn sàng hỗ trợ anh/chị về nội dung hành chính. Anh/chị vui lòng sử dụng ngôn từ phù hợp để tôi có thể hỗ trợ tốt hơn.', 'chunks': []})}\n\n"
                return

            if subject == "chu_de_cam":
                end = time.perf_counter()
                duration = (end - start_flow) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= banned_replies
                log_data["event_type"] = "banned_topic"
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                enqueue_log(log_data)
                yield from emit_log("=> Phân loại tương tác - chủ đề cấm", force=True)
                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'replies': 'Dạ em chỉ hỗ trợ anh/chị về các thủ tục hành chính, thông tin chung, hoặc tổ chức bộ máy của phường thôi ạ. Anh/chị vui lòng đặt câu hỏi liên quan đến những chủ đề này để được hỗ trợ tốt nhất nhé.', 'chunks': []})}\n\n"
                return
            
        scope = extract_scope(user_message)
        resolved_tenant_code = resolve_target_tenant_code_cached(tenant_code, scope)
        if resolved_tenant_code is None and scope == "xa_phuong":
            resolved_tenant_code = tenant_code
        tenant_code = resolved_tenant_code

        end = time.perf_counter()
        duration = (end - start_flow) * 1000 

        yield f"data: {json.dumps({'log': f'[{round(duration / 1000,2)}s]=> Xác định scope: {scope}'})}\n\n"
        yield f"data: {json.dumps({'log': f'=> Tenant code tham vấn: {tenant_code}'})}\n\n"

        if category == "phan_anh_kien_nghi":
            subject = classify_phan_anh_cached(user_message, tenant_code, prompt_template=classify_subject_phan_anh_prompt)
            subject = normalize_subject_value(subject)
            tenant_code = None
            subject = None
            # if subject is None:
            #     category = check_classify_phan_anh_kien_nghi(user_message)
            #     category = normalize_subject_value(category)
            #     tenant_code = origin_tenant_code

            yield from emit_log("Thuộc phạm vi - phản ánh kiến nghị")
            yield f"data: {json.dumps({'log': f'=> Subject: {subject}'})}\n\n"

        if category == "thong_tin_tong_quan":
            subject = classify_tong_quan_cached(user_message, tenant_code, prompt_template=classify_subject_qa_prompt)
            subject = normalize_subject_value(subject)
            # subject = data.get("subject")
            yield from emit_log("Đang tra cứu thông tin tổng quan")
            yield f"data: {json.dumps({'log': f'=> Subject: {subject}'})}\n\n"
        

        query_embedding = get_embedding_cached(user_message)

        chunks = search_documents_full_hybrid_v6_cached(
            normalized_query=normalized_query,
            query_embedding=query_embedding,
            category=category,
            subject=subject,
            p_limit=5,
            tenant=tenant_code
        )

        print(f"Initial chunks: {chunks}")
        
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


        yield from emit_log("Đang tim các tài liệu liên quan")

        related_chunks = get_related_chunks_cached(tenant_code, id_chunk)
        if related_chunks:
            # Avoid duplicate documents when a related chunk already appears in top results.
            existing_ids = {c.get("id") for c in primary_chunks}
            unique_related = [c for c in related_chunks if c.get("id") not in existing_ids]

            if unique_related:
                start_idx = len(context_parts)
                context_parts.extend(
                    f"### Tài liệu liên quan {start_idx + i + 1}\n{chunk['text_content']}"
                    for i, chunk in enumerate(unique_related[:3])
                )

        context = "\n\n".join(context_parts) if context_parts else "Không tìm thấy tài liệu phù hợp."

            
        # answer = "\n\n".join(
        #     f"Sử dụng các tài liệu sau:\n### Tài liệu {i+1}\n{chunk['text_content']}"
        #     for i, chunk in enumerate(chunks[:5])
        # )
        
        yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

        full_answer = ""
        for token in llm_answer_stream(user_message, context, prompt_template=answer_qa_prompt):
            full_answer += token
            yield from flush_logs()
            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'done': True, 'chunks': chunks}, ensure_ascii=False)}\n\n"
        answer = full_answer

        end = time.perf_counter()
        duration = (end - start_flow)
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
        log_data["response_time_ms"]= round(duration, 2)
        enqueue_log(log_data)
        yield from flush_logs(force=True)
        # yield f"data: {json.dumps({'replies': answer, 'chunks': chunks})}\n\n"
        return

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # cực quan trọng nếu có nginx
        }
    )   

# --------------- API xử lý chat (non-streaming)

@app.route('/api/chat', methods=['POST'])
def chat():
    start_all_flow = time.perf_counter()
    step_start = start_all_flow

    def _log_step(ten_buoc: str):
        nonlocal step_start
        now = time.perf_counter()
        step_elapsed = now - step_start
        total_elapsed = now - start_all_flow
        print(f"[ThoiGian][chat] {ten_buoc}: {step_elapsed:.3f}s | tong={total_elapsed:.3f}s")
        step_start = now

    help_content = "Kính chào anh/chị! Rất vui được hỗ trợ anh/chị. Anh/chị có thể hỏi về các thủ tục hành chính, thông tin chung, hoặc tổ chức bộ máy của phường. Anh/chị cần giúp đỡ về vấn đề gì ạ?"
    out_of_score_content = "Nội dung anh/chị hỏi nằm ngoài phạm vi hỗ trợ của hệ thống.\nAnh/chị vui lòng liên hệ đơn vị phù hợp hoặc đặt câu hỏi liên quan đến thủ tục hành chính để được hỗ trợ."
    thanks_content = "Dạ, cảm ơn anh/chị. Khi cần thêm thông tin, anh/chị cứ liên hệ lại."
    phan_nan_content = "Tôi rất tiếc vì anh/chị chưa hài lòng. Anh/chị hãy nói rõ phần còn vướng, tôi sẽ hỗ trợ lại ngay."
    xuc_pham_content = "Tôi vẫn sẵn sàng hỗ trợ anh/chị về nội dung hành chính. Anh/chị vui lòng sử dụng ngôn từ phù hợp để tôi có thể hỗ trợ tốt hơn."
    banned_replies = "Dạ em chỉ hỗ trợ anh/chị về các thủ tục hành chính, thông tin chung, hoặc tổ chức bộ máy của phường thôi ạ. Anh/chị vui lòng đặt câu hỏi liên quan đến những chủ đề này để được hỗ trợ tốt nhất nhé."

    try:

        data = request.json or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON payload"}), 400

        raw_message = data.get('message', '')
        if not isinstance(raw_message, str):
            return jsonify({"error": "message must be a string"}), 400
        if not raw_message.strip():
            return jsonify({"error": "Message cannot be empty"}), 400

        user_message = raw_message.strip()
        origin_mess = user_message

        raw_session_id = data.get("session_id")
        if not isinstance(raw_session_id, str) or not raw_session_id.strip():
            return jsonify({"error": "session_id is required"}), 400
        
        session_id = raw_session_id.strip()
        if len(session_id) > 128:
            return jsonify({"error": "session_id is too long"}), 400

        _log_step("Xác thực dữ liệu đầu vào")

        # Hỗ trợ cả tenant_id và tenant_code
        tenant_id = data.get("tenant_id")
        raw_tenant_code = data.get("tenant_code")
        tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
        
        if err:
            return jsonify({"error": err}), 400

        if not tenant_exists(tenant_code):
            return jsonify({"error": f"tenant_code '{tenant_code}' does not exist"}), 400

        _log_step("Xác thực tenant")

        origin_tenant_code = tenant_code

        try:
            prompt_templates = get_active_prompt_templates_map_cached()
        except Exception as e:
            prompt_templates = {}
            return jsonify({"error": f"Không thể tải prompt templates: {str(e)}"}), 400

        _log_step("Tải prompt template")

        history_rewrite_prompt = pick_prompt_template(prompt_templates, "history_rewrite")
        classify_category_prompt = pick_prompt_template(prompt_templates, "classify_category")
        classify_subject_procedure_prompt = pick_prompt_template(prompt_templates, "classify_subject_procedure")
        answer_procedure_prompt = pick_prompt_template(prompt_templates, "answer_procedure")
        classify_subject_qa_prompt = pick_prompt_template(prompt_templates, "classify_subject_QA")
        classify_subject_tuong_tac_prompt = pick_prompt_template(prompt_templates, "classify_subject_tuong_tac")
        classify_subject_phan_anh_prompt = pick_prompt_template(prompt_templates, "classify_subject_phan_anh")
        answer_qa_prompt = pick_prompt_template(prompt_templates, "answer_QA")

        history_data = get_recent_session_history_cached(session_id, tenant_code, limit=2)
        print(f"History data: {history_data}")

        _log_step("Lấy lịch sử hội thoại")

        result = resolver.process(user_message)
        user_message = result["expanded"]
        normalized_query = result["normalized"]

        matched_keyword = next(
            (
                kw for kw in BANNED_KEYWORDS
                if kw.lower() in user_message.lower()
                or normalize_text(kw) in normalized_query
            ),
            None
        )
        if matched_keyword:
            _log_step("Chặn bởi blacklist")
            return jsonify({
                "response": {"can_reply": True, "response": banned_replies},
                "chunks": [],
                "message": user_message,
                "timestamp": datetime.now().isoformat()
            }), 200

        _log_step("Mở rộng viết tắt và kiểm tra blacklist")
        
        if not history_data:
            user_message = rewrite_query(user_message, prompt_template=None)
            normalized_query = normalize_text(user_message)
            _log_step("Rewrite câu hỏi không có lịch sử")

        if history_data:
            start_check_rewrite_history = time.perf_counter()
            print("Có lịch sử hội thoại, kiểm tra rewrite dựa trên lịch sử...")
            last_question = history_data[0]["expanded_query"]
            print(f"Câu hỏi trước: {last_question}")
            user_message = rewrite_query_history(user_message, last_question, prompt_template=history_rewrite_prompt)
            print(f"Prompt sử dụng cho rewrite câu hỏi: {history_rewrite_prompt}")
            normalized_query = normalize_text(user_message)
            end_check_rewrite_history = time.perf_counter() - start_check_rewrite_history
            print(f'[{round(end_check_rewrite_history, 2)}s] - Câu hỏi sau khi rewrite (có lịch sử hội thoại): {user_message}')
            _log_step("Rewrite câu hỏi theo lịch sử")
        
        print(f"Câu hỏi sau khi rewrite: {user_message}")

        res = classify_v2_cached(normalized_query, PREPARED, tenant_code)
        category, subject = res["category"], res["subject"]
        if res["need_llm"]:
            category_llm = classify_llm_cached(user_message, prompt_template=classify_category_prompt)
            category = normalize_llm_label(category_llm)

        _log_step("Phân loại category")

        if category == "chu_de_cam":
            _log_step("LLM xác định chặn vì thuộc chủ đề cấm")
            return jsonify({
                "response": {"can_reply": True, "response": banned_replies},
                "chunks": [],
                "message": user_message,
                "timestamp": datetime.now().isoformat()
            }), 200

        if category == "tuong_tac":
            subject = classify_tuong_tac_cached(user_message, tenant_code, prompt_template=classify_subject_tuong_tac_prompt)
            subject = normalize_subject_value(subject)
            # if subject is None:
            #     category = check_classify_tuong_tac(user_message)
            #     category = normalize_subject_value(category)

            if subject == "chao_hoi":
                answer_text = help_content
            elif subject == "cam_on_tam_biet":
                answer_text = thanks_content
            elif subject == "phan_nan_buc_xuc":
                answer_text = phan_nan_content
            elif subject == "xuc_pham_vi_pham":
                answer_text = xuc_pham_content
            elif subject == "chu_de_cam":
                answer_text = banned_replies
            else:
                answer_text = None

            if answer_text is not None:
                _log_step("Trả lời nhanh nhóm tương tác")
                return jsonify({
                    "response": {"can_reply": True, "response": answer_text},
                    "chunks": [],
                    "message": user_message,
                    "timestamp": datetime.now().isoformat()
                }), 200
        if category == "thu_tuc_hanh_chinh":
            
            meta = classify_llm_procedure_cached(user_message, prompt_template=classify_subject_procedure_prompt)
            if not meta or not isinstance(meta, dict):
                return jsonify({"error": "Không trích xuất được thông tin thủ tục"}), 422

            _log_step("Trích xuất metadata thủ tục")

            procedures = meta.get("unit") or []
            query_mode = meta.get("query_mode")
            if not procedures:
                return jsonify({"error": "Không xác định được thủ tục"}), 422

            if query_mode == "single_procedure":
                procedure_name = (procedures[0].get("procedure") or "").strip()
                if not procedure_name:
                    return jsonify({"error": "Không xác định được tên thủ tục"}), 422

                procedure_action = procedures[0].get("procedure_action")
                special_contexts = procedures[0].get("special_contexts") or []
                normalized_procedure = normalize_text(procedure_name)
                response = supabase.rpc(
                    "search_documents_full_hybrid_thu_tuc_v1",
                    {
                        "p_query_format": normalized_procedure,
                        "p_query_embedding": get_embedding_cached(procedure_name),
                        "p_tenant": None,
                        "p_category": category,
                        "p_subject": procedures[0]['subject'],
                        "p_procedure": normalized_procedure,
                        "p_procedure_action": procedure_action,
                        "p_special_contexts": special_contexts,
                        "p_limit": 3
                    }
                ).execute()
                chunks = response.data or []
            else:
                chunks = []
                valid_procedure_count = 0
                for proc in procedures:
                    procedure_name = (proc.get('procedure') or '').strip()
                    if not procedure_name:
                        continue

                    valid_procedure_count += 1
                    procedure_action = proc.get('procedure_action')
                    special_contexts = proc.get('special_contexts') or []
                    normalized_procedure = normalize_text(procedure_name)
                    response = supabase.rpc(
                        "search_documents_full_hybrid_thu_tuc_v1",
                        {
                            "p_query_format": normalized_procedure,
                            "p_query_embedding": get_embedding_cached(procedure_name),
                            "p_tenant": None,
                            "p_category": category,
                            "p_subject": proc.get('subject'),
                            "p_procedure": normalized_procedure,
                            "p_procedure_action": procedure_action,
                            "p_special_contexts": special_contexts,
                            "p_limit": 1
                        }
                    ).execute()
                    hit = response.data or []
                    if hit:
                        chunks.append(hit[0])

                if valid_procedure_count == 0:
                    return jsonify({"error": "Không xác định được tên thủ tục"}), 422

            context = "\n\n".join(
                f"### Tài liệu {i+1}\n{chunk['text_content']}"
                for i, chunk in enumerate(chunks[:5])
            ) if chunks else "Không tìm thấy tài liệu phù hợp."
            
            answer_text = llm_answer_procedure(user_message, context, prompt_template=answer_procedure_prompt)
            if "chưa có thông tin trong hệ thống" in answer_text.lower():
                answer_text = out_of_score_content

            _log_step("Sinh câu trả lời thủ tục")

            end = time.perf_counter() - start_all_flow
            print(f"Thời gian xử lý tổng thể (thu_tuc_hanh_chinh): [{round(end, 2)}s]")
            # duration = (end - start) * 1000
            log_data = {
                "tenant_code": tenant_code,
                "raw_query": origin_mess,
                "expanded_query": user_message,
                "answer": answer_text,
                "detected_category": category,
                "detected_subject": subject,
                "event_type": "normal",
                "alias_score": chunks[0]["alias_score"] if chunks else 0,
                "document_score": chunks[0]["document_score"] if chunks else 0,
                "confidence_score": chunks[0]["confidence_score"] if chunks else 0,
                "session_chat": session_id,
                "response_time_ms": round(end, 2)
            }
            create_log(log_data)
            _log_step("Lưu lịch sử hội thoại")

            return jsonify({
                "response": {"can_reply": True, "response": answer_text},
                "chunks": chunks,
                "message": user_message,
                "timestamp": datetime.now().isoformat()
            }), 200

        scope = extract_scope(user_message)
        resolved_tenant_code = resolve_target_tenant_code_cached(tenant_code, scope)
        if resolved_tenant_code is None and scope == "xa_phuong":
            resolved_tenant_code = tenant_code
        tenant_code = resolved_tenant_code
        
        if category == "phan_anh_kien_nghi":
            subject = classify_phan_anh_cached(user_message, tenant_code, prompt_template=classify_subject_phan_anh_prompt)
            subject = normalize_subject_value(subject)
            tenant_code = None
            subject = None
            # if subject is None:
            #     category = check_classify_phan_anh_kien_nghi(user_message)
            #     category = normalize_subject_value(category)

        if category == "thong_tin_tong_quan":
            subject = classify_tong_quan_cached(user_message, tenant_code, prompt_template=classify_subject_qa_prompt)
            subject = normalize_subject_value(subject)
        
        print(f"Câu hỏi truy vấn: {user_message}")

        query_embedding = get_embedding_cached(user_message)
        print(f"Subject: {subject}")

        print(f"Scope: {scope}, Tenant code after resolving scope: {tenant_code}")
        _log_step("Tạo embedding và xác định scope")

        chunks = search_documents_full_hybrid_v6_cached(
            normalized_query=normalized_query,
            query_embedding=query_embedding,
            category=category,
            subject=subject,
            p_limit=5,
            tenant=tenant_code
        )
        _log_step("Truy vấn tài liệu chunk")

        if subject in ["chuc_vu", "nhan_su"]:
            best_score = chunks[0]["confidence_score"] if chunks else 0
            if best_score < 0.4:
                chunks_all = search_documents_full_hybrid_v6_cached(
                    normalized_query=normalized_query,
                    query_embedding=query_embedding,
                    category="to_chuc_bo_may",
                    subject=None,
                    p_limit=5,
                    tenant=tenant_code
                )
                best_score_all = chunks_all[0]["confidence_score"] if chunks_all else 0
                if best_score_all > best_score:
                    chunks = chunks_all

            _log_step("Kiểm tra fallback với subject là None cho nhóm chuc_vu/nhan_su")
        
        if subject in ["lich_su_hanh_chinh", "gioi_thieu_dia_phuong"]:
            best_score = chunks[0]["confidence_score"] if chunks else 0
            if best_score < 0.4:
                chunks_all = search_documents_full_hybrid_v6_cached(
                    normalized_query=normalized_query,
                    query_embedding=query_embedding,
                    category="thong_tin_tong_quan",
                    subject=None,
                    p_limit=5,
                    tenant=tenant_code
                )
                best_score_all = chunks_all[0]["confidence_score"] if chunks_all else 0
                if best_score_all > best_score:
                    chunks = chunks_all

            _log_step("Kiểm tra fallback với subject là None cho nhóm chuc_vu/nhan_su")

        id_chunk = chunks[0]["id"] if chunks else None
        primary_chunks = chunks[:5]
        context_parts = [
            f"### Tài liệu {i+1}\n{chunk['text_content']}"
            for i, chunk in enumerate(primary_chunks)
        ] if primary_chunks else []

        related_chunks = get_related_chunks_cached(tenant_code, id_chunk)
        if related_chunks:
            existing_ids = {c.get("id") for c in primary_chunks}
            unique_related = [c for c in related_chunks if c.get("id") not in existing_ids]
            if unique_related:
                start_idx = len(context_parts)
                context_parts.extend(
                    f"### Tài liệu liên quan {start_idx + i + 1}\n{chunk['text_content']}"
                    for i, chunk in enumerate(unique_related[:3])
                )

        _log_step("Gắn tài liệu liên quan")

        context = "\n\n".join(context_parts) if context_parts else "Không tìm thấy tài liệu phù hợp."
        answer_text = llm_answer(user_message, context, prompt_template=answer_qa_prompt)
        if "chưa có thông tin trong hệ thống" in answer_text.lower():
            answer_text = out_of_score_content
        print(f"Context for LLM:\n{context}")

        _log_step("Sinh câu trả lời chung")

        end = time.perf_counter() - start_all_flow
        print(f"Thời gian xử lý tổng thể: [{round(end, 2)}s]")
        log_data = {
            "tenant_code": origin_tenant_code,
            "raw_query": origin_mess,
            "expanded_query": user_message,
            "answer": answer_text,
            "detected_category": category,
            "detected_subject": subject,
            "event_type": "normal",
            "alias_score": chunks[0]["alias_score"] if chunks else 0,
            "document_score": chunks[0]["document_score"] if chunks else 0,
            "confidence_score": chunks[0]["confidence_score"] if chunks else 0,
            "session_chat": session_id,
            "response_time_ms": round(end, 2)
        }
        create_log(log_data)
        _log_step("Lưu lịch sử hội thoại")

        return jsonify({
            "response": {"can_reply": True, "response": answer_text},
            "chunks": chunks,
            "message": user_message,
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({"error": f"Chat processing failed: {str(e)}"}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(debug=True)