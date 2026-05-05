
import re
import os
import json
import uuid
import time
import hashlib
import random
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from datetime import datetime
from openai import OpenAI
from pydantic import BaseModel
from typing import List, Tuple, Dict, Pattern, Set

from dotenv import load_dotenv
from corn import supabase
from normalize import SINGLE_TOKEN_MAP, CONTEXT_RULES, BANNED_KEYWORDS, normalize_text, normalize_subject_value, normalize_meta_primary, AbbreviationResolver
from model import rewrite_query, rewrite_query_history, detect_query, llm_answer, llm_answer_stream, llm_answer_procedure, llm_answer_procedure_stream, classify_category
from test_demo import classify_v2
from embedding import get_proc_embedding, get_embedding
from utils import SUBJECT_KEYWORDS, prepare_subject_keywords
from export_metadata import classify_llm, classify_with_tong_quan, classify_with_phan_anh, classify_with_tuong_tac
from cache_backend import create_cache_backend
from system import chunk_text
from scope_detect import extract_scope
from test_unit_type import resolve_unit_type
# from model import classify_category_doan_the, classify_subject_doan_the, classify_organization_type
from rule_base_fastCheck import classify_category_fast
from to_chuc_doan_the_v6 import detect_organization_intent_fast_v7
from schema_validate_intent_meta import SCORING_CONFIG, build_meta_payload
from schema_validate_intent_meta_V2 import classify_meta_without_intent, classify_meta_with_intent
from upload_chunk_system import extract_intent_and_meta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

PREPARED = prepare_subject_keywords(SUBJECT_KEYWORDS)
keyword_items: List[Tuple[str, str]] = []
patterns: List[Tuple[Pattern, str]] = []


tenant_context_cache: Dict[str, dict] = {}
tenant_code_by_id_cache: Dict[int, str] = {}
tenant_codes_with_documents: Set[str] = set()
tenant_context_last_loaded_at: float = 0.0
TENANT_CONTEXT_CACHE_TTL = 5 * 60
_tenant_context_lock = Lock()

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


def _v2_list_response(items, page, per_page, total=None, summary=None):
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
    
    if summary is not None:
        payload["summary"] = summary

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
_classify_category_fast_cache = "classify_category_fast"
_detect_org_intent_fast_cache = "detect_org_intent_fast"
_classify_meta_without_intent_cache = "classify_meta_without_intent"
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
CLASSIFY_CATEGORY_FAST_CACHE_TTL = 10 * 60
DETECT_ORG_INTENT_FAST_CACHE_TTL = 10 * 60
CLASSIFY_META_WITHOUT_INTENT_CACHE_TTL = 15 * 60
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
CLASSIFY_CATEGORY_FAST_CACHE_MAX = 2000
DETECT_ORG_INTENT_FAST_CACHE_MAX = 2000
CLASSIFY_META_WITHOUT_INTENT_CACHE_MAX = 1000
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


def _canonical_query_for_cache(normalized: str):
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


def load_tenant_context_to_memory():
    global tenant_context_cache, tenant_code_by_id_cache, tenant_context_last_loaded_at

    res = (
        supabase.table("tenants")
        .select("id, tenant_code, scope, parent_id, tenant_name, unit_type, domain_org_type")
        .order("tenant_code")
        .execute()
    )

    rows = res.data or []
    tenants_by_id: dict[int, dict] = {}
    tenant_context_cache = {}
    tenant_code_by_id_cache = {}

    for row in rows:
        tenant_id = row.get("id")
        tenant_code = normalize_tenant_code(row.get("tenant_code"))
        if tenant_id is None or not tenant_code:
            continue

        normalized_row = {
            "id": tenant_id,
            "tenant_code": tenant_code,
            "scope": row.get("scope"),
            "parent_id": row.get("parent_id"),
            "tenant_name": row.get("tenant_name"),
            "unit_type": row.get("unit_type"),
            "domain_org_type": row.get("domain_org_type"),
        }
        tenants_by_id[tenant_id] = normalized_row
        tenant_code_by_id_cache[tenant_id] = tenant_code

    for row in tenants_by_id.values():
        tenant_code = row["tenant_code"]
        parent_row = tenants_by_id.get(row.get("parent_id"))

        current_data = {
            "id": tenant_code,
            "unit_type": row.get("unit_type"),
            "domain_org_type": row.get("domain_org_type"),
            "scope_type": row.get("scope"),
            "name": row.get("tenant_name"),
        }

        parent_data = None
        if parent_row:
            parent_data = {
                "id": parent_row.get("tenant_code"),
                "unit_type": parent_row.get("unit_type"),
                "domain_org_type": parent_row.get("domain_org_type"),
                "scope_type": parent_row.get("scope"),
                "name": parent_row.get("tenant_name"),
            }

        tenant_context_cache[tenant_code] = {
            "current": current_data,
            "parent": parent_data
        }

    tenant_context_last_loaded_at = time.time()


def ensure_tenant_context_loaded(force: bool = False):
    now = time.time()
    cache_is_fresh = (
        bool(tenant_context_cache)
        and bool(tenant_code_by_id_cache)
        and (now - tenant_context_last_loaded_at) <= TENANT_CONTEXT_CACHE_TTL
    )
    if not force and cache_is_fresh:
        return

    with _tenant_context_lock:
        now = time.time()
        cache_is_fresh = (
            bool(tenant_context_cache)
            and bool(tenant_code_by_id_cache)
            and (now - tenant_context_last_loaded_at) <= TENANT_CONTEXT_CACHE_TTL
        )
        if not force and cache_is_fresh:
            return

        load_tenant_context_to_memory()


def load_tenant_has_documents_to_memory():
    global tenant_codes_with_documents

    res = (
        supabase.table("documents")
        .select("tenant_code")
        .execute()
    )

    rows = res.data or []
    tenant_codes_with_documents = {
        code
        for row in rows
        if (code := normalize_tenant_code(row.get("tenant_code")))
    }


def refresh_tenant_cache():
    ensure_tenant_context_loaded(force=True)
    load_tenant_has_documents_to_memory()


def tenant_code_from_id(tenant_id: int = None):
    if tenant_id is None:
        return None

    norm_id = _to_int(tenant_id)
    if norm_id is None:
        return None

    return tenant_code_by_id_cache.get(norm_id)


def get_tenant_and_parent_from_memory(tenant_code: str, has_chunks_only: bool = False):
    tenant_code = normalize_tenant_code(tenant_code)
    if not tenant_code:
        return None

    context = tenant_context_cache.get(tenant_code)
    if not context:
        return None

    if has_chunks_only and tenant_code not in tenant_codes_with_documents:
        return None

    return context


def get_resolved_tenant_from_memory(tenant_code: str, has_chunks_only: bool = False):
    context = get_tenant_and_parent_from_memory(tenant_code, has_chunks_only=has_chunks_only)
    if not context:
        return None

    return context

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

    ensure_tenant_context_loaded()

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


def get_embedding_cached(user_text: str, normalized_query: str = None):
    canonical = _canonical_query_for_cache(normalized_query)
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
            .table("prompt_templates")
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


def classify_category_fast_cached(query: str):
    """Cache wrapper for classify_category_fast - lightweight banned/interaction gate."""
    canonical = _canonical_query_for_cache(query)
    key = _cache_key("classify_category_fast", _hash_text(canonical))
    cached = _cache_get(_classify_category_fast_cache, key)
    if cached is not _CACHE_MISS:
        return cached

    result = classify_category_fast(query)
    _cache_set(
        _classify_category_fast_cache,
        key,
        result,
        CLASSIFY_CATEGORY_FAST_CACHE_TTL,
        CLASSIFY_CATEGORY_FAST_CACHE_MAX,
    )
    return result


def detect_organization_intent_fast_v7_cached(query: str):
    """Cache wrapper for detect_organization_intent_fast_v7."""
    canonical = _canonical_query_for_cache(query)
    key = _cache_key("detect_org_intent_fast", _hash_text(canonical))
    cached = _cache_get(_detect_org_intent_fast_cache, key)
    if cached is not _CACHE_MISS:
        return cached

    result = detect_organization_intent_fast_v7(query)
    _cache_set(
        _detect_org_intent_fast_cache,
        key,
        result,
        DETECT_ORG_INTENT_FAST_CACHE_TTL,
        DETECT_ORG_INTENT_FAST_CACHE_MAX,
    )
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


def classify_meta_without_intent_cached(user_message: str, org_type: str, normalized_query: str = None, org_type_is_fallback: bool = False):
    """Cache wrapper for classify_meta_without_intent - LLM-based intent extraction from org type."""
    canonical = _canonical_query_for_cache(normalized_query)
    key = _cache_key("classify_meta_without_intent", org_type, _hash_text(canonical))
    cached = _cache_get(_classify_meta_without_intent_cache, key)
    if cached is not _CACHE_MISS:
        if cached == _NULL_SENTINEL:
            return None
        return cached
    
    result = classify_meta_without_intent(user_message, org_type, org_type_is_fallback)
    _cache_set(
        _classify_meta_without_intent_cache,
        key,
        result,
        CLASSIFY_META_WITHOUT_INTENT_CACHE_TTL,
        CLASSIFY_META_WITHOUT_INTENT_CACHE_MAX,
    )
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


def get_keywords():
    response = (
        supabase
        .table("blocked_keywords")
        .select("id, keyword, normalized_keyword")
        .order("id")
        .execute()
    )
    return response.data or []


@app.route("/api/keywords", methods=["GET"])
def fetch_keywords():
    data = get_keywords()
    return {
        "success": True,
        "data": data
    }


def load_keywords_to_memory():
    global keyword_items

    data = get_keywords()
    keyword_items = [
        (item["normalized_keyword"], item["keyword"])
        for item in data
    ]


def refresh_keywords_cache():
    load_keywords_to_memory()


def find_blocked_keyword(normalized: str):
    for norm_kw, original_kw in keyword_items:
        if norm_kw in normalized:
            return original_kw
    return None


def update_keyword(keyword_id: int, new_keyword: str):
    response = (
        supabase
        .table("blocked_keywords")
        .update({
            "keyword": new_keyword,
            "normalized_keyword": normalize_text(new_keyword)
        })
        .eq("id", keyword_id)
        .execute()
    )

    return response.data or []


class UpdateKeywordRequest(BaseModel):
    new_keyword: str

@app.route("/api/keywords/<keyword_id>", methods=["PUT"])
def put_keyword(keyword_id: int):
    try:
        body = request.get_json(silent=True) or {}
        new_keyword = str(body.get("new_keyword", "")).strip()

        if not new_keyword:
            return {
                "success": False,
                "error": "Từ khóa không được để trống"
            }

        result = update_keyword(keyword_id, new_keyword)

        if not result:
            return {
                "success": False,
                "error": "Không tìm thấy từ khóa để cập nhật"
            }

        refresh_keywords_cache()

        return {
            "success": True,
            "message": "Cập nhật từ khóa thành công",
            "data": result[0]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def get_default_answers():
    response = (
        supabase
        .table("default_answers")
        .select("id, key, content, description")
        .order("id")
        .execute()
    )
    return response.data or []

@app.route("/api/default-answers", methods=["GET"])
def fetch_default_answers():
    data = get_default_answers()

    return {
        "success": True,
        "data": data
    }

def update_default_answer(answer_id: int, new_content: str):
    response = (
        supabase
        .table("default_answers")
        .update({
            "content": new_content
        })
        .eq("id", answer_id)
        .execute()
    )

    return response.data or []

class UpdateDefaultAnswerRequest(BaseModel):
    content: str

default_answers_cache: Dict[str, str] = {}
def load_default_answers_to_memory():
    global default_answers_cache

    data = get_default_answers()

    default_answers_cache = {
        item["key"]: item["content"]
        for item in data
    }

def refresh_default_answers_cache():
    load_default_answers_to_memory()

def get_default_answer(key: str):
    return default_answers_cache.get(key)

@app.route("/api/default-answers/<answer_id>", methods=["PUT"])
def put_default_answer(answer_id: int):
    try:
        body = request.get_json(silent=True) or {}
        new_content = str(body.get("content", "")).strip()

        if not new_content:
            return {
                "success": False,
                "error": "Content không được để trống"
            }

        result = update_default_answer(answer_id, new_content)

        if not result:
            return {
                "success": False,
                "error": "Không tìm thấy bản ghi để update"
            }

        # 🔥 nếu có cache thì refresh
        refresh_default_answers_cache()

        return {
            "success": True,
            "message": "Cập nhật thành công",
            "data": result[0]
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.route('/api/get-chunks', methods=['GET'])
def get_chunks():
    try:
        tenant_code = request.args.get("tenant_code", default=None, type=str)

        query = (
            supabase.table("documents")
            .select(
                "id, procedure_name, text_content, category, subject, scope, "
                "procedure_action, tenant_code, intent_type, meta_primary, mode_values"
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
        logger.info(f"Tenant_id: {tenant_id}, tenant_code: {request.args.get('tenant_code')}")
        raw_tenant_code = request.args.get("tenant_code")
        tenant_code = None
        if (tenant_id and str(tenant_id).strip()) or (raw_tenant_code and str(raw_tenant_code).strip()):
            ensure_tenant_context_loaded()
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


# # Chat sessions (derived from `log_query.session_chat`)
# @app.route('/api/chat-sessions', methods=['GET'])
# def v2_list_chat_sessions():
#     try:
#         page = _to_int(request.args.get("page"), 1)
#         per_page = _to_int(request.args.get("per_page"), 20)
#         search = (request.args.get("search") or "").strip() or None
#         channel = (request.args.get("channel") or "").strip() or None  # not stored currently
#         from_ts = (request.args.get("from") or "").strip() or None
#         to_ts = (request.args.get("to") or "").strip() or None
#         # tenant_id = request.args.get("tenant_id")
#         # raw_tenant_code = request.args.get("tenant_code")

#         # tenant_code = None
#         # if (tenant_id and str(tenant_id).strip()) or (raw_tenant_code and str(raw_tenant_code).strip()):
#         #     tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
#         #     if err:
#         #         return jsonify({"error": err}), 400
#         #     if not tenant_exists(tenant_code):
#         #         return jsonify({"error": "tenant_code does not exist"}), 400

#         page, per_page, start, end = _paginate(page, per_page)

#         q = supabase.table("log_query").select(
#             "session_chat, raw_query, answer, created_at, tenant_code"
#         ).eq("event_type", "normal").order("created_at", desc=True)

#         # if tenant_code:
#         #     q = q.eq("tenant_code", tenant_code)

#         if from_ts:
#             q = q.gte("created_at", from_ts)
#         if to_ts:
#             q = q.lte("created_at", to_ts)

#         res = q.range(0, 2000).execute()
#         rows = res.data or []

#         if search:
#             needle = search.lower()
#             rows = [
#                 r for r in rows
#                 if (r.get("raw_query") or "").lower().find(needle) != -1
#                 or (r.get("answer") or "").lower().find(needle) != -1
#             ]

#         # Deduplicate by session_chat keeping latest message (already ordered desc).
#         seen = set()
#         sessions = []
#         for r in rows:
#             sid = r.get("session_chat")
#             if not sid or sid in seen:
#                 continue
#             seen.add(sid)
#             sessions.append({
#                 "id": sid,
#                 "channel": channel,  # best-effort; no persisted channel in log_query
#                 "tenantCode": r.get("tenant_code"),
#                 "lastMessageAt": r.get("created_at"),
#                 "lastUserMessage": r.get("raw_query"),
#                 "lastBotMessage": r.get("answer"),
#             })

#         paged = sessions[start:start + per_page]
#         return jsonify(_v2_list_response(paged, page, per_page, total=len(sessions))), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500



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
        # tenant_id = request.args.get("tenant_id")
        # raw_tenant_code = request.args.get("tenant_code")

        # tenant_code = None
        # if (tenant_id and str(tenant_id).strip()) or (raw_tenant_code and str(raw_tenant_code).strip()):
        #     tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
        #     if err:
        #         return jsonify({"error": err}), 400
        #     if not tenant_exists(tenant_code):
        #         return jsonify({"error": "tenant_code does not exist"}), 400

        page, per_page, start, end = _paginate(page, per_page)

        q = supabase.table("log_query").select(
            "session_chat, raw_query, expanded_query, detected_category, detected_subject, "
            "event_type, alias_score, document_score, confidence_score, response_time_ms, "
            "answer, created_at, tenant_code"
        ).order("created_at", desc=True)

        # if tenant_code:
        #     q = q.eq("tenant_code", tenant_code)

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
                if needle in (r.get("raw_query") or "").lower()
                or needle in (r.get("expanded_query") or "").lower()
                or needle in (r.get("answer") or "").lower()
                or needle in (r.get("detected_category") or "").lower()
                or needle in (r.get("detected_subject") or "").lower()
            ]

        # Deduplicate by session_chat keeping latest message (already ordered desc).
        items = []
        for r in rows:
            items.append({
                "id": str(r.get("id") or f"{r.get('session_chat', '')}_{r.get('created_at', '')}"),
                "sessionId": r.get("session_chat"),
                "userName": "",
                "channel": channel,
                "messages": r.get("raw_query") or "",
                "expandedQuery": r.get("expanded_query"),
                "answer": r.get("answer") or "",
                "category": r.get("detected_category") or "",
                "subject": r.get("detected_subject") or "",
                "responseType": r.get("event_type") or "",
                "aliasScore": float(r.get("alias_score") or 0),
                "documentScore": float(r.get("document_score") or 0),
                "totalScore": float(r.get("confidence_score") or 0),
                "processingTime": float(r.get("response_time_ms") or 0),
                "createdAt": r.get("created_at"),
                "tenantCode": r.get("tenant_code"),
            })
        
        total_conversations = len(items)
        average_score = (
            sum(item["totalScore"] for item in items) / total_conversations
            if total_conversations > 0 else 0
        )
        average_processing_time_ms = (
            sum(item["processingTime"] for item in items) / total_conversations
            if total_conversations > 0 else 0
        )

        paged = items[start:start + per_page]

        summary = {
            "total_conversations": total_conversations,
            "average_score": round(average_score, 2),
            "average_processing_time_ms": round(average_processing_time_ms, 2),
        }

        return jsonify(_v2_list_response(paged, page, per_page, total=total_conversations, summary=summary)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat-sessions/<session_id>', methods=['GET'])
def v2_get_chat_session(session_id):
    try:
        tenant_id = request.args.get("tenant_id")
        raw_tenant_code = request.args.get("tenant_code")

        # tenant_code = None
        # if (tenant_id and str(tenant_id).strip()) or (raw_tenant_code and str(raw_tenant_code).strip()):
        #     tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
        #     if err:
        #         return jsonify({"error": err}), 400
        #     if not tenant_exists(tenant_code):
        #         return jsonify({"error": "tenant_code does not exist"}), 400
        query = (
            supabase
            .table("log_query")
            .select("raw_query, answer, created_at")
            .eq("session_chat", session_id)
            .eq("event_type", "normal")
            .order("created_at")
        )

        res = query.execute()
        rows = res.data or []

        messages = []
        for r in rows:
            if r.get("raw_query"):
                messages.append({
                    "role": "user",
                    "content": r["raw_query"],
                    "timestamp": r["created_at"]
                })
            if r.get("answer"):
                messages.append({
                    "role": "bot",
                    "content": r["answer"],
                    "timestamp": r["created_at"]
                })

        return jsonify({
            "session": {
                "id": session_id
            },
            "messages": messages
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# @app.route('/api/chat-sessions/<session_id>', methods=['GET'])
# def v2_get_chat_session(session_id):
#     try:
#         tenant_id = request.args.get("tenant_id")
#         raw_tenant_code = request.args.get("tenant_code")

#         tenant_code = None
#         if (tenant_id and str(tenant_id).strip()) or (raw_tenant_code and str(raw_tenant_code).strip()):
#             tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
#             if err:
#                 return jsonify({"error": err}), 400
#             if not tenant_exists(tenant_code):
#                 return jsonify({"error": "tenant_code does not exist"}), 400

#         res = (
#             supabase
#             .table("log_query")
#             .select("raw_query, answer, created_at, event_type, tenant_code")
#             .eq("session_chat", session_id)
#             .eq("event_type", "normal")
#         )
#         if tenant_code:
#             res = res.eq("tenant_code", tenant_code)

#         res = res.order("created_at").execute()
#         rows = res.data or []
#         messages = []
#         for r in rows:
#             ts = r.get("created_at")
#             uq = (r.get("raw_query") or "").strip()
#             aq = (r.get("answer") or "").strip()
#             if uq:
#                 messages.append({"role": "user", "content": uq, "timestamp": ts})
#             if aq:
#                 messages.append({"role": "bot", "content": aq, "timestamp": ts})

#         payload = {
#             "session": {"id": session_id},
#             "messages": messages,
#         }
#         return jsonify({"data": payload}), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500




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
            .select("id, tenant_code, scope, parent_id, tenant_name, unit_type") \
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

@app.route('/api/tenants', methods=['POST'])
def sync_tenant():
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON payload"}), 400

        tenant_id = data.get("tenant_id")
        tenant_code = data.get("tenant_code")

        if tenant_id is None:
            return jsonify({"error": "tenant_id is required"}), 400
        if not tenant_code:
            return jsonify({"error": "tenant_code is required"}), 400

        tenant_code = str(tenant_code).strip()

        # Check if exists
        existing = supabase.table("tenants").select("id").eq("tenant_code", tenant_code).execute()
        if existing.data:
            return jsonify({"message": "Tenant already exists", "data": existing.data[0]}), 200

        # Insert new tenant
        payload = {
            "id": int(tenant_id),
            "tenant_code": tenant_code,
            "scope": "xa_phuong",
        }
        res = supabase.table("tenants").insert(payload).execute()
        
        return jsonify({
            "message": "Tenant synced successfully",
            "data": res.data
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
            

        text_content = data.get("text_content") or ''
        category = data.get("category") or None

        procedure_action = data.get("procedure_action")
        print(procedure_action)
        if procedure_action == "ubnd":
            procedure_action = None
            procedure_name = extract_procedure_name(text_content) if category == "thu_tuc_hanh_chinh" else None
            embedding = get_proc_embedding(data.get("text_content")) if data.get("text_content") else None
            if embedding is None:
                return jsonify({"error": "Không thể tạo embedding cho nội dung này. Vui lòng thử lại."}), 500

            new_chunk = {
                "tenant_code": tenant_code,
                "scope": scope,
                "procedure_name": procedure_name,
                "text_content": text_content,
                "normalized_text": normalize_text(procedure_name or text_content),
                "category": category,
                "subject": data.get("subject") or None,
                "procedure_action": procedure_action,
                "embedding": embedding
            }

            response = supabase.table("documents") \
                .insert(new_chunk) \
                .execute()
        else:
            result = extract_intent_and_meta(text_content, procedure_action)
            intent_type = result['intent']
            meta = result['meta']
            meta_normalized = build_meta_payload(intent_type, meta)
            primary_value = meta_normalized['primary_values']
            meta_modes = meta_normalized['mode_values']
            logging.info(f"Extracted meta for procedure_action '{procedure_action}': intent='{intent_type}', primary_value='{primary_value}', meta_modes={meta_modes}")
            embedding = get_proc_embedding(data.get("text_content")) if data.get("text_content") else None
            if embedding is None:
                return jsonify({"error": "Không thể tạo embedding cho nội dung này. Vui lòng thử lại."}), 500
            
            new_chunk = {
                "tenant_code": tenant_code,
                "scope": scope or 'xa_phuong',
                "text_content": text_content,
                "normalized_text": normalize_text(text_content),
                "intent_type": intent_type,
                "meta_primary": normalize_meta_primary(primary_value),
                "mode_values": meta_modes,
                "procedure_action": procedure_action,
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

        meta_primary_raw = data.get("meta_primary")
        meta_primary = None
        if isinstance(meta_primary_raw, (dict, list)):
            meta_primary = meta_primary_raw
        elif meta_primary_raw is not None:
            meta_primary_text = str(meta_primary_raw).strip()
            meta_primary = meta_primary_text or None

        mode_values_raw = data.get("mode_values")
        mode_values = []
        if isinstance(mode_values_raw, list):
            mode_values = [str(item).strip() for item in mode_values_raw if str(item).strip()]

        response = supabase.table("documents") \
            .update({
                "text_content": data.get("text_content"),
                "normalized_text": normalize_text(text_content),
                "category": data.get("category") or None,
                "subject": data.get("subject") or None,
                "procedure_action": data.get("procedure_action") or None,
                "intent_type": (data.get("intent_type") or '').strip() or None,
                "meta_primary": meta_primary,
                "mode_values": mode_values,
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

@app.route('/api/chat-stream-v2', methods=['POST'])
def chat_stream_v2():

    def generate():
        request_started_at = time.perf_counter()

        # ✅ LẤY DATA TRƯỚC
        data = request.json or {}
        session_id = data.get("session_id")
        user_message = data.get('question', '').strip()
        origin_mess = user_message
        logger.info(f"Câu hỏi người dùng: {user_message}")

        # Hỗ trợ cả tenant_id và tenant_code
        tenant_id = data.get("tenant_id")
        raw_tenant_code = data.get("tenant_code")
        tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
        log_data = {}
        logger.info(f"Tenant id: {tenant_id}")
        logger.info(f"Tenant code: {tenant_code}")
        
        help_content = get_default_answer("help")
        # out_of_score_content = get_default_answer("out_of_scope")
        thanks_content = get_default_answer("thanks")
        phan_nan_content = get_default_answer("complaint")
        xuc_pham_content = get_default_answer("abuse")
        banned_replies = get_default_answer("banned")
        support_content = get_default_answer("support")

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
            total_ms = (time.perf_counter() - request_started_at) * 1000
            logger.info(
                "[perf][chat_stream_v2] session=%s tenant=%s stage=tenant_resolve_failed total_ms=%.2f err=%s",
                session_id,
                tenant_code,
                total_ms,
                err,
            )
            message = err
            for token in chunk_text(message):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        if not tenant_exists(tenant_code):
            total_ms = (time.perf_counter() - request_started_at) * 1000
            logger.info(
                "[perf][chat_stream_v2] session=%s tenant=%s stage=tenant_not_found total_ms=%.2f",
                session_id,
                tenant_code,
                total_ms,
            )
            message = "Tenant được chọn không tồn tại trong hệ thống."
            for token in chunk_text(message):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
        
        # yield from emit_log(f"Đã nhận câu hỏi anh/chị: {origin_mess}")

        start_flow = request_started_at
        stage_started_at = start_flow

        def log_stage(stage: str, **extra):
            nonlocal stage_started_at
            now = time.perf_counter()
            step_ms = (now - stage_started_at) * 1000
            total_ms = (now - start_flow) * 1000
            extras = " ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
            if extras:
                logger.info(
                    "[perf][chat_stream_v2] session=%s tenant=%s stage=%s step_ms=%.2f total_ms=%.2f %s",
                    session_id,
                    tenant_code,
                    stage,
                    step_ms,
                    total_ms,
                    extras,
                )
            else:
                logger.info(
                    "[perf][chat_stream_v2] session=%s tenant=%s stage=%s step_ms=%.2f total_ms=%.2f",
                    session_id,
                    tenant_code,
                    stage,
                    step_ms,
                    total_ms,
                )
            stage_started_at = now

        ## --------- Bước 1: Rule-based từ tắt, viết tắt
        
        result = resolver.process(user_message)
        user_message = result["expanded"]
        normalized_query = result["normalized"]

        # logger.info(f"Câu hỏi sau khi xử rule-base từ tắt: {user_message}")
        log_stage("Normalized text", user_message=user_message)

        # yield from emit_log("Đang xử lý nội dung câu hỏi\n")

        matched_keyword = find_blocked_keyword(normalized_query) or None
        fast_check = classify_category_fast_cached(normalized_query)

        check_label = fast_check['label']
        topic_label = fast_check["debug_hits"]
        log_stage("fast_gate_classified", label=check_label, has_blocked_keyword=bool(matched_keyword))

        if matched_keyword or check_label == "chu_de_cam":
            # yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)
            banned_replies_stream = chunk_text(banned_replies)
            for token in banned_replies_stream:
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            log_stage("banned_response_streamed", reason="matched_keyword" if matched_keyword else "fast_check")

            end = time.perf_counter()
            duration = (end - start_flow) * 1000 
            log_data["raw_query"] = user_message
            log_data["expanded_query"] = normalized_query
            log_data["event_type"] = "banned_topic"
            log_data["answer"]= banned_replies
            log_data["reason"]= f"Nội dung có chứa từ khóa cấm: {matched_keyword}" if matched_keyword else f"Nội dung có chứa chủ đề cấm: {topic_label}"
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            enqueue_log(log_data)
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        if check_label == "tuong_tac":
            interaction_subject = fast_check['interaction_type']

            # yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

            if interaction_subject in ["hoi_kha_nang_bot", "chao_hoi"]:
                answer_stream = chunk_text(help_content)
                answer = help_content
                event_type = "normal"
            if interaction_subject == "cam_on_tam_biet":
                answer_stream = chunk_text(thanks_content)
                answer = thanks_content
                event_type = "normal"
            if interaction_subject == "phan_nan":
                answer_stream = chunk_text(phan_nan_content)
                answer = phan_nan_content
                event_type = "complaint"
            if interaction_subject == "xuc_pham":
                answer_stream = chunk_text(xuc_pham_content)
                answer = xuc_pham_content
                event_type = "banned_topic"

            for token in answer_stream:
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            log_stage("interaction_response_streamed", interaction_subject=interaction_subject, event_type=event_type)

            end = time.perf_counter()
            duration = (end - start_flow) * 1000 
            log_data["tenant_code"] = tenant_code
            log_data["raw_query"] = origin_mess
            log_data["expanded_query"] = user_message
            log_data["answer"]= answer
            log_data["event_type"] = event_type
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            enqueue_log(log_data)
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        try:
            prompt_templates = get_active_prompt_templates_map_cached()
        except Exception as e:
            prompt_templates = {}
            yield from emit_log(f"Không thể tải prompt templates: {str(e)}", force=True)

        history_rewrite_prompt = pick_prompt_template(prompt_templates, "history_rewrite")
        # classify_category_prompt = pick_prompt_template(prompt_templates, "classify_category")
        # classify_subject_procedure_prompt = pick_prompt_template(prompt_templates, "classify_subject_procedure")
        # answer_procedure_prompt = pick_prompt_template(prompt_templates, "answer_procedure")
        # classify_subject_qa_prompt = pick_prompt_template(prompt_templates, "classify_subject_QA")
        # classify_subject_tuong_tac_prompt = pick_prompt_template(prompt_templates, "classify_subject_tuong_tac")
        # classify_subject_phan_anh_prompt = pick_prompt_template(prompt_templates, "classify_subject_phan_anh")
        # answer_qa_prompt = pick_prompt_template(prompt_templates, "answer_QA")

        # history_data = get_recent_session_history_cached(session_id, tenant_code, limit=2)
        history_data = None
        log_stage("session_history_loaded", has_history=bool(history_data), history_items=len(history_data or []))
        
        logger.info(f"Câu hỏi người dùng: {origin_mess}")
        if not history_data:
            logger.info(f"Chuẩn hóa không có lịch sử với {user_message}")
            start = time.perf_counter()
            user_message = rewrite_query(user_message, prompt_template=None)

            normalized_query = normalize_text(user_message)
            end = time.perf_counter()
            yield f"data: {json.dumps({'log': f'{(end - start):.2f}s Câu hỏi sau khi viết lại (không có lịch sử): {user_message}'})}\n\n"
            log_stage("rewrite_query_no_history")

        if history_data:
            last_question = history_data[0]["expanded_query"]
            # logger.info(f"Câu hỏi trước: {last_question}")

            user_message = rewrite_query_history(user_message, last_question, prompt_template=history_rewrite_prompt)
            normalized_query = normalize_text(user_message)
            yield f"data: {json.dumps({'log': f'Câu hỏi sau khi viết lại (Có lịch sử): {user_message}'})}\n\n"
            log_stage("rewrite_query_with_history")
        
        tenant_ctx = get_resolved_tenant_from_memory(tenant_code)
        current_tenance = tenant_ctx.get("current") if tenant_ctx else None
        parent_tenance = tenant_ctx.get("parent") if tenant_ctx and tenant_ctx.get("parent") else None
        domain_org_type = current_tenance.get("domain_org_type") if current_tenance else None
        logger.info(f"Org current type: {tenant_ctx}")
        log_stage("tenant_context_loaded", has_domain_org=bool(domain_org_type))

        scope = extract_scope(user_message)

        logger.info(f"Scope extracted: {scope}")
        
        result = resolve_unit_type(
            query=user_message,
            scope=scope,
            tenant_ctx=tenant_ctx
        )

        logger.info(f"Org type after resolve_unit_type: {result}")

        resolved_tenant_code = resolve_target_tenant_code_cached(tenant_code, scope)
        if resolved_tenant_code is None and scope == "xa_phuong":
            resolved_tenant_code = tenant_code
        tenant_code = resolved_tenant_code

        extract_meta = detect_organization_intent_fast_v7_cached(normalized_query)

        org_type = extract_meta['organization_type']
        org_type_is_fallback = False
        if org_type is None:
            org_type = domain_org_type
            org_type_is_fallback = True
            yield f"data: {json.dumps({'log': f'Organization default fallback: {org_type}'})}\n\n"
            log_stage("org_fallback_applied", fallback_org=org_type)
        
        # TARGET = {"mttq", "doan_thanh_nien", "hoi_phu_nu", "dang_uy", "cong_doan"}
        logger.info(f"is_fallback: {org_type_is_fallback}")
        # if org_type in TARGET:
        intent = extract_meta['intent']
        log_stage("Intent (rule-base)", intent=intent)

        yield f"data: {json.dumps({'log': f'Organization (rule-base): {org_type}, Intent (rule-base): {intent}'})}\n\n"

        if intent:
            meta = classify_meta_with_intent(user_message, org_type, intent, org_type_is_fallback)
        else:
            meta = classify_meta_without_intent_cached(user_message, org_type, normalized_query, org_type_is_fallback)
            intent = meta.get("intent") or intent
            level = meta.get("level")
            score = meta.get("confidence")
            log_stage("Intent (LLM extracting)", intent=intent)
            yield f"data: {json.dumps({'log': f'Intent (LLM extracting): {intent}, Level: {level}, Score: {score}'})}\n\n"
        if (org_type, intent) not in SCORING_CONFIG:
            return support_content
    
        cfg = SCORING_CONFIG[(org_type, intent)]
        log_stage("Scoring Config", score_config=cfg)

        fields = meta.get("meta") or {}
        meta_payload = build_meta_payload(intent, fields)
        primary_values = meta_payload["primary_values"]
        mode_values = meta_payload["mode_values"]
        yield f"data: {json.dumps({'log': f'Primary value: {primary_values}, mode values: {mode_values}'})}\n\n"

        log_stage("Extracted Meta", primary_value=primary_values, mode_values=mode_values)

        try:
            response = supabase.rpc(
                "search_documents_meta_generic",
                {
                    "p_query_format": normalized_query,
                    "p_query_embedding": get_embedding_cached(user_message, normalized_query),
                    "p_tenant": tenant_code,
                    "p_org_type": None if org_type_is_fallback else org_type,
                    "p_intent": intent,

                    "p_primary_values": primary_values,
                    "p_mode_values": mode_values,

                    "p_w_intent": cfg["w_intent"],
                    "p_w_primary": cfg["w_primary"],
                    "p_w_mode": cfg["w_mode"],
                    "p_meta_cap": cfg["meta_cap"],

                    "p_limit": 3,
                }
            ).execute()
            chunks = response.data or []
        except Exception as e:
            logger.error(f"[RPC ERROR] search_documents_meta_generic failed: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'log': f'Lỗi tìm kiếm tài liệu: {str(e)}'})}\n\n"
            for token in chunk_text(support_content):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        if not chunks:
            for token in chunk_text(support_content):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
        # top_score = chunks[0]["confidence_score"] if chunks else 0
        # logger.info(f"=> Điểm tài liệu tốt nhất: {top_score}")

        # if top_score < 0.2:
        #     for token in chunk_text(support_content):
        #         yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

        #     end = time.perf_counter()
        #     duration = (end - start_flow) * 1000 
        #     log_data["tenant_code"] = tenant_code
        #     log_data["raw_query"] = origin_mess
        #     log_data["expanded_query"] = user_message
        #     log_data["answer"]= support_content
        #     log_data["event_type"] = "low_confidence"
        #     log_data["alias_score"]= top_chunk.get("alias_score", 0)
        #     log_data["document_score"]= top_score
        #     log_data["confidence_score"]= top_chunk.get("confidence_score", 0)
        #     log_data["session_chat"]= session_id
        #     log_data["response_time_ms"]= round(duration / 1000,2)
        #     enqueue_log(log_data)
        #     yield from flush_logs(force=True)
        #     yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        #     return

        context = "\n\n".join(
            f"**Tài liệu {i+1}**: ({chunk.get('confidence_score', 0):.2f} điểm)\n{chunk['text_content']}"
            for i, chunk in enumerate(chunks)
        )

        content_new_flow_stream = chunk_text(context)
        for token in content_new_flow_stream:
            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        
        yield from flush_logs(force=True)
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        return
        # yield f"data: {json.dumps({'log': f'Primary value: {primary_values}, mode values: {mode_values}'})}\n\n"

        # res = classify_v2_cached(normalized_query, PREPARED, tenant_code)
        # category, subject = res["category"], res["subject"]

        # if res["need_llm"]:
        #     category_llm = classify_llm_cached(user_message, prompt_template=classify_category_prompt)
        #     category = normalize_llm_label(category_llm)
        
        # logger.info(f"Category được xác định: {category}")
        # yield f"data: {json.dumps({'log': f'Category được xác định: {category}'})}\n\n"

        # if category == "chu_de_cam":
        #     banned_replies_stream = chunk_text(banned_replies)
        #     for token in banned_replies_stream:
        #         yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        #     end = time.perf_counter()
        #     duration = (end - start_flow) * 1000 
        #     log_data["raw_query"] = user_message
        #     log_data["expanded_query"] = normalized_query
        #     log_data["detected_category"] = category
        #     log_data["event_type"] = "banned_topic"
        #     log_data["answer"]= banned_replies
        #     log_data["reason"]= "LLm xác định nội dung thuộc chủ đề cấm"
        #     log_data["session_chat"]= session_id
        #     log_data["response_time_ms"]= round(duration / 1000,2)
        #     enqueue_log(log_data)
        #     yield from flush_logs(force=True)
        #     yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        #     return
            
        # if category == "thu_tuc_hanh_chinh":
        #     yield from emit_log("=> Xác định nội dung thuộc thủ tục hành chính\n", force=True)
        #     meta = classify_llm_procedure_cached(user_message, prompt_template=classify_subject_procedure_prompt)

        #     if not meta or not isinstance(meta, dict):
        #         message = "Không thể xác định thủ tục hành chính từ câu hỏi. Anh/chị vui lòng đặt câu hỏi rõ ràng hơn hoặc liên hệ trực tiếp để được hỗ trợ."
        #         for token in chunk_text(message):
        #             yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        #         yield from flush_logs(force=True)
        #         yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        #         return

        #     query_mode = meta.get("query_mode")

        #     procedures = meta.get("unit") or []
        #     if not procedures:
        #         message = "Không thể xác định thủ tục hành chính từ câu hỏi. Anh/chị vui lòng đặt câu hỏi rõ ràng hơn hoặc liên hệ trực tiếp để được hỗ trợ."
        #         for token in chunk_text(message):
        #             yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        #         yield from flush_logs(force=True)
        #         yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        #         return
            
        #     logger.info(f"=> Phân tích thủ tục : {meta}")

        #     procedure_name = procedures[0].get("procedure")
        #     if not procedure_name:
        #         message = "Dạ anh/chị, hệ thống khác xác định được rõ tên thủ tục, anh/chị đang hỏi cụ thể về thủ tục nào ạ?"
        #         for token in chunk_text(message):
        #             yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        #         yield from flush_logs(force=True)
        #         yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        #         return

        #     chunk_response = []

        #     if query_mode == "single_procedure":
        #         procedure_name = procedures[0].get("procedure")
        #         procedure_action = procedures[0].get("procedure_action")
        #         special_contexts = procedures[0].get("special_contexts") or []


        #         yield from emit_log(f"=> Đã xác định tên thủ tục: {procedure_name}\n")
        #         yield from emit_log("Đang chọn lọc các tài liệu liên quan\n")
        #         yield f"data: {json.dumps({'log': f'=> Tên thủ tục: {procedure_name}'})}\n\n"
        #         response = supabase.rpc(
        #             "search_documents_full_hybrid_thu_tuc_v1",
        #             {
        #                 "p_query_format": normalize_text(procedure_name),
        #                 "p_query_embedding": get_embedding_cached(procedure_name, normalized_query),
        #                 "p_tenant": None,
        #                 "p_category": category,
        #                 "p_subject": procedures[0]['subject'],
        #                 "p_procedure": normalize_text(procedure_name),
        #                 "p_procedure_action": procedure_action,
        #                 "p_special_contexts": special_contexts,
        #                 "p_limit": 3
        #             }
        #         ).execute()
        #         chunks = response.data or []
        #     else:
        #         chunk_response = []
        #         for proc in procedures:
        #             procedure_name = proc['procedure']
        #             procedure_action = proc['procedure_action']
        #             special_contexts = proc['special_contexts']
        #             yield from emit_log(f"=> Đã xác định tên thủ tục: {procedure_name}\n")
        #             yield from emit_log("Đang chọn lọc các tài liệu liên quan\n")
        #             yield f"data: {json.dumps({'log': f'=> Tên thủ tục: {procedure_name}'})}\n\n"
        #             response = supabase.rpc(
        #                 "search_documents_full_hybrid_thu_tuc_v1",
        #                 {
        #                     "p_query_format": normalize_text(procedure_name),
        #                     "p_query_embedding": get_embedding_cached(procedure_name, normalized_query),
        #                     "p_tenant": None,
        #                     "p_category": category,
        #                     "p_subject": proc['subject'],
        #                     "p_procedure": normalize_text(procedure_name),
        #                     "p_procedure_action": procedure_action,
        #                     "p_special_contexts": special_contexts,
        #                     "p_limit": 1
        #                 }
        #             ).execute()

        #             chunks = response.data or []
        #             if chunks:
        #                 chunk_response.append(chunks[0])
        #         chunks = chunk_response
        #     if not chunks:
        #         for token in chunk_text(support_content):
        #             yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

        #         yield from flush_logs(force=True)
        #         yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        #         return
        #     top_chunk = chunks[0] if chunks else {}
        #     logger.info(f"=> Điểm tài liệu tốt nhất: {top_chunk.get('confidence_score', 0)}")

        #     if top_chunk.get('confidence_score', 0) < 0.2:
        #         for token in chunk_text(support_content):
        #             yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

        #         end = time.perf_counter()
        #         duration = (end - start_flow) * 1000 
        #         log_data["tenant_code"] = tenant_code
        #         log_data["raw_query"] = origin_mess
        #         log_data["expanded_query"] = user_message
        #         log_data["answer"]= support_content
        #         log_data["detected_category"]= category
        #         log_data["detected_subject"]= subject
        #         log_data["event_type"] = "low_confidence"
        #         log_data["alias_score"]= top_chunk.get("alias_score", 0)
        #         log_data["document_score"]= top_chunk.get("confidence_score", 0)
        #         log_data["confidence_score"]= top_chunk.get("confidence_score", 0)
        #         log_data["session_chat"]= session_id
        #         log_data["response_time_ms"]= round(duration / 1000,2)
        #         enqueue_log(log_data)
        #         yield from flush_logs(force=True)
        #         yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        #         return

        #     context = "\n\n".join(
        #         f"Tài liệu {i+1}:\n{chunk['text_content']}"
        #         for i, chunk in enumerate(chunks)
        #     )

        #     yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

        #     full_answer = ""
        #     for token in llm_answer_procedure_stream(user_message, context, prompt_template=answer_procedure_prompt):
        #         full_answer += token
        #         yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        
        #     answer = full_answer

        #     end = time.perf_counter()
        #     duration = (end - start_flow) * 1000 
        #     log_data["tenant_code"] = tenant_code
        #     log_data["raw_query"] = origin_mess
        #     log_data["expanded_query"] = user_message
        #     log_data["answer"]= full_answer
        #     log_data["detected_category"]= category
        #     log_data["detected_subject"]= subject
        #     log_data["event_type"] = "normal"
        #     top_chunk = chunks[0] if chunks else {}
        #     log_data["alias_score"]= top_chunk.get("alias_score", 0)
        #     log_data["document_score"]= top_chunk.get("confidence_score", 0)
        #     log_data["confidence_score"]= top_chunk.get("confidence_score", 0)
        #     log_data["session_chat"]= session_id
        #     log_data["response_time_ms"]= round(duration / 1000,2)
        #     enqueue_log(log_data)
        #     yield from flush_logs(force=True)
        #     yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

        #     return

        # if category == "tuong_tac":
        #     subject = classify_tuong_tac_cached(user_message, tenant_code, prompt_template=classify_subject_tuong_tac_prompt)
        #     subject = normalize_subject_value(subject)
        #     if subject is None:
        #         subject = "chao_hoi"
            
        #     yield f"data: {json.dumps({'log': f'Subject: {subject}'})}\n\n"
        #     logger.info(f"=> Subject: {subject}")
            
        #     yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

        #     if subject == "chao_hoi":
        #         answer_stream = chunk_text(help_content)
        #         answer = help_content
        #         event_type = "normal"
        #     if subject == "cam_on_tam_biet":
        #         answer_stream = chunk_text(thanks_content)
        #         answer = thanks_content
        #         event_type = "normal"
        #     if subject == "phan_nan_buc_xuc":
        #         answer_stream = chunk_text(phan_nan_content)
        #         answer = phan_nan_content
        #         event_type = "complaint"
        #     if subject == "xuc_pham_vi_pham":
        #         answer_stream = chunk_text(xuc_pham_content)
        #         answer = xuc_pham_content
        #         event_type = "banned_topic"
        #     if subject == "chu_de_cam":
        #         answer_stream = chunk_text(banned_replies)
        #         answer = banned_replies
        #         event_type = "banned_topic"

        #     for token in answer_stream:
        #         yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

        #     end = time.perf_counter()
        #     duration = (end - start_flow) * 1000 
        #     log_data["tenant_code"] = tenant_code
        #     log_data["raw_query"] = origin_mess
        #     log_data["expanded_query"] = user_message
        #     log_data["answer"]= answer
        #     log_data["event_type"] = event_type
        #     log_data["session_chat"]= session_id
        #     log_data["response_time_ms"]= round(duration / 1000,2)
        #     enqueue_log(log_data)
        #     yield from flush_logs(force=True)
        #     yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        #     return
        
        # scope = extract_scope(user_message)
        
        # start = time.perf_counter()

        # result = resolve_unit_type(
        #     query=user_message,
        #     scope=scope,
        #     tenant_ctx=tenant_ctx
        # )

        # end_time = time.perf_counter()
        # duration = (end_time - start) * 1000
        # yield f"data: {json.dumps({'log': f'Thời gian xử lý unit type: {duration / 1000:.2f} s'})}\n\n"

        # user_message = result["normalized_query"]
        # yield f"data: {json.dumps({'log': f'Câu hỏi đã xử lý unit type: {user_message}'})}\n\n"
            
        # resolved_tenant_code = resolve_target_tenant_code_cached(tenant_code, scope)
        # if resolved_tenant_code is None and scope == "xa_phuong":
        #     resolved_tenant_code = tenant_code
        # tenant_code = resolved_tenant_code

        # logger.info(f"=> Scope: {scope}, Resolved tenant code: {tenant_code}")
        # yield f"data: {json.dumps({'log': f'Scope: {scope}, Resolved tenant code: {tenant_code}'})}\n\n"

        # if category == "phan_anh_kien_nghi":
        #     subject = classify_phan_anh_cached(user_message, tenant_code, prompt_template=classify_subject_phan_anh_prompt)
        #     subject = normalize_subject_value(subject)
        #     tenant_code = None
        #     logger.info(f"=> Subject: {subject}")
        #     yield f"data: {json.dumps({'log': f'Subject: {subject}'})}\n\n"


        #     yield from emit_log("Thuộc phạm vi - phản ánh kiến nghị\n")

        # if category == "thong_tin_tong_quan":
        #     subject = classify_tong_quan_cached(user_message, tenant_code, prompt_template=classify_subject_qa_prompt)
        #     subject = normalize_subject_value(subject)
        #     logger.info(f"=> Subject: {subject}")
        #     yield f"data: {json.dumps({'log': f'Subject: {subject}'})}\n\n"
        #     yield from emit_log("Đang tra cứu thông tin tổng quan\n")

        # query_embedding = get_embedding_cached(user_message, normalized_query)

        # chunks = search_documents_full_hybrid_v6_cached(
        #     normalized_query=normalized_query,
        #     query_embedding=query_embedding,
        #     category=category,
        #     subject=subject,
        #     p_limit=5,
        #     tenant=tenant_code
        # )

        # if subject in ["chuc_vu", "nhan_su"]:
        #     best_score = chunks[0]["confidence_score"] if chunks else 0
        #     if best_score < 0.4:
        #         chunks_all = search_documents_full_hybrid_v6_cached(
        #             normalized_query=normalized_query,
        #             query_embedding=query_embedding,
        #             category="to_chuc_bo_may",
        #             subject=None,
        #             p_limit=5,
        #             tenant=tenant_code
        #         )

        #         best_score_all = chunks_all[0]["confidence_score"] if chunks_all else 0

        #         # Nếu không subject tốt hơn → dùng nó
        #         if best_score_all > best_score:
        #             chunks = chunks_all
        
        # # id_chunk = chunks[0]["id"] if chunks else None

        # if not chunks:
        #     for token in chunk_text(support_content):
        #         yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

        #     yield from flush_logs(force=True)
        #     yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        #     return

        # top_score = chunks[0]["confidence_score"] if chunks else 0
        # logger.info(f"=> Điểm tài liệu tốt nhất: {top_score}")
        # logger.info(f"=> Chunks: {chunks}")

        # if top_score < 0.2:
        #     for token in chunk_text(support_content):
        #         yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

        #     end = time.perf_counter()
        #     duration = (end - start_flow) * 1000 
        #     log_data["tenant_code"] = tenant_code
        #     log_data["raw_query"] = origin_mess
        #     log_data["expanded_query"] = user_message
        #     log_data["answer"]= support_content
        #     log_data["detected_category"]= category
        #     log_data["detected_subject"]= subject
        #     log_data["event_type"] = "low_confidence"
        #     log_data["session_chat"]= session_id
        #     log_data["response_time_ms"]= round(duration / 1000,2)
        #     enqueue_log(log_data)
        #     yield from flush_logs(force=True)
        #     yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        #     return
        
        # # primary_chunks = chunks[:5]
        # # context_parts = [
        # #     f"### Tài liệu {i+1}\n{chunk['text_content']}"
        # #     for i, chunk in enumerate(chunks)
        # # ] if chunks else []

        # # yield from emit_log("Đang tìm các tài liệu liên quan")

        # # related_chunks = get_related_chunks_cached(tenant_code, id_chunk)
        # # if related_chunks:
        # #     # Avoid duplicate documents when a related chunk already appears in top results.
        # #     existing_ids = {c.get("id") for c in primary_chunks}
        # #     unique_related = [c for c in related_chunks if c.get("id") not in existing_ids]

        # #     if unique_related:
        # #         start_idx = len(context_parts)
        # #         context_parts.extend(
        # #             f"### Tài liệu liên quan {start_idx + i + 1}\n{chunk['text_content']}"
        # #             for i, chunk in enumerate(unique_related[:3])
        # #         )

        # # context = "\n\n".join(context_parts)
        # context = "\n\n".join(
        #     f"Tài liệu {i+1}:\n{chunk['text_content']}"
        #     for i, chunk in enumerate(chunks)
        # )

        # yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

        # full_answer = ""
        # for token in llm_answer_stream(user_message, context, prompt_template=answer_qa_prompt):
        #     full_answer += token
        #     yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        # answer = full_answer

        # end = time.perf_counter()
        # duration = (end - start_flow)
        # log_data["tenant_code"] = tenant_code
        # log_data["raw_query"] = origin_mess
        # log_data["expanded_query"] = user_message
        # log_data["answer"]= answer
        # log_data["detected_category"]= category
        # log_data["detected_subject"]= subject
        # log_data["event_type"] = "normal"
        # log_data["alias_score"]= chunks[0]["alias_score"] if chunks else 0
        # log_data["document_score"]= chunks[0]["document_score"] if chunks else 0
        # log_data["confidence_score"]= top_score
        # log_data["session_chat"]= session_id
        # log_data["response_time_ms"]= round(duration, 2)
        # enqueue_log(log_data)
        # yield from flush_logs(force=True)
        # yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        # return

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # cực quan trọng nếu có nginx
        }
    )   

@app.route('/api/chat-stream-v3', methods=['POST'])
def chat_stream_v3():

    def generate():
        request_started_at = time.perf_counter()

        # ✅ LẤY DATA TRƯỚC
        data = request.json or {}
        session_id = data.get("session_id")
        user_message = data.get('question', '').strip()
        origin_mess = user_message
        logger.info(f"Câu hỏi người dùng: {user_message}")

        # Hỗ trợ cả tenant_id và tenant_code
        tenant_id = data.get("tenant_id")
        raw_tenant_code = data.get("tenant_code")
        tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
        log_data = {}
        logger.info(f"Tenant id: {tenant_id}")
        logger.info(f"Tenant code: {tenant_code}")
        
        help_content = get_default_answer("help")
        # out_of_score_content = get_default_answer("out_of_scope")
        thanks_content = get_default_answer("thanks")
        phan_nan_content = get_default_answer("complaint")
        xuc_pham_content = get_default_answer("abuse")
        banned_replies = get_default_answer("banned")
        support_content = get_default_answer("support")

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
            total_ms = (time.perf_counter() - request_started_at) * 1000
            logger.info(
                "[perf][chat_stream_v2] session=%s tenant=%s stage=tenant_resolve_failed total_ms=%.2f err=%s",
                session_id,
                tenant_code,
                total_ms,
                err,
            )
            message = err
            for token in chunk_text(message):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        if not tenant_exists(tenant_code):
            total_ms = (time.perf_counter() - request_started_at) * 1000
            logger.info(
                "[perf][chat_stream_v2] session=%s tenant=%s stage=tenant_not_found total_ms=%.2f",
                session_id,
                tenant_code,
                total_ms,
            )
            message = "Tenant được chọn không tồn tại trong hệ thống."
            for token in chunk_text(message):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
        
        # yield from emit_log(f"Đã nhận câu hỏi anh/chị: {origin_mess}")

        start_flow = request_started_at
        stage_started_at = start_flow

        def log_stage(stage: str, **extra):
            nonlocal stage_started_at
            now = time.perf_counter()
            step_ms = (now - stage_started_at) * 1000
            total_ms = (now - start_flow) * 1000
            extras = " ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
            if extras:
                logger.info(
                    "[perf][chat_stream_v2] session=%s tenant=%s stage=%s step_ms=%.2f total_ms=%.2f %s",
                    session_id,
                    tenant_code,
                    stage,
                    step_ms,
                    total_ms,
                    extras,
                )
            else:
                logger.info(
                    "[perf][chat_stream_v2] session=%s tenant=%s stage=%s step_ms=%.2f total_ms=%.2f",
                    session_id,
                    tenant_code,
                    stage,
                    step_ms,
                    total_ms,
                )
            stage_started_at = now

        ## --------- Bước 1: Rule-based từ tắt, viết tắt
        
        result = resolver.process(user_message)
        user_message = result["expanded"]
        normalized_query = result["normalized"]

        # logger.info(f"Câu hỏi sau khi xử rule-base từ tắt: {user_message}")
        log_stage("Normalized text", user_message=user_message)

        # yield from emit_log("Đang xử lý nội dung câu hỏi\n")

        matched_keyword = find_blocked_keyword(normalized_query) or None
        fast_check = classify_category_fast_cached(normalized_query)

        check_label = fast_check['label']
        topic_label = fast_check["debug_hits"]
        log_stage("fast_gate_classified", label=check_label, has_blocked_keyword=bool(matched_keyword))

        if matched_keyword or check_label == "chu_de_cam":
            # yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)
            banned_replies_stream = chunk_text(banned_replies)
            for token in banned_replies_stream:
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            log_stage("banned_response_streamed", reason="matched_keyword" if matched_keyword else "fast_check")

            end = time.perf_counter()
            duration = (end - start_flow) * 1000 
            log_data["raw_query"] = user_message
            log_data["expanded_query"] = normalized_query
            log_data["event_type"] = "banned_topic"
            log_data["answer"]= banned_replies
            log_data["reason"]= f"Nội dung có chứa từ khóa cấm: {matched_keyword}" if matched_keyword else f"Nội dung có chứa chủ đề cấm: {topic_label}"
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            enqueue_log(log_data)
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        if check_label == "tuong_tac":
            interaction_subject = fast_check['interaction_type']

            # yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

            if interaction_subject in ["hoi_kha_nang_bot", "chao_hoi"]:
                answer_stream = chunk_text(help_content)
                answer = help_content
                event_type = "normal"
            if interaction_subject == "cam_on_tam_biet":
                answer_stream = chunk_text(thanks_content)
                answer = thanks_content
                event_type = "normal"
            if interaction_subject == "phan_nan":
                answer_stream = chunk_text(phan_nan_content)
                answer = phan_nan_content
                event_type = "complaint"
            if interaction_subject == "xuc_pham":
                answer_stream = chunk_text(xuc_pham_content)
                answer = xuc_pham_content
                event_type = "banned_topic"

            for token in answer_stream:
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            log_stage("interaction_response_streamed", interaction_subject=interaction_subject, event_type=event_type)

            end = time.perf_counter()
            duration = (end - start_flow) * 1000 
            log_data["tenant_code"] = tenant_code
            log_data["raw_query"] = origin_mess
            log_data["expanded_query"] = user_message
            log_data["answer"]= answer
            log_data["event_type"] = event_type
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            enqueue_log(log_data)
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        try:
            prompt_templates = get_active_prompt_templates_map_cached()
        except Exception as e:
            prompt_templates = {}
            yield from emit_log(f"Không thể tải prompt templates: {str(e)}", force=True)

        history_rewrite_prompt = pick_prompt_template(prompt_templates, "history_rewrite")
        # classify_category_prompt = pick_prompt_template(prompt_templates, "classify_category")
        classify_subject_procedure_prompt = pick_prompt_template(prompt_templates, "classify_subject_procedure")
        answer_procedure_prompt = pick_prompt_template(prompt_templates, "answer_procedure")
        # classify_subject_qa_prompt = pick_prompt_template(prompt_templates, "classify_subject_QA")
        # classify_subject_tuong_tac_prompt = pick_prompt_template(prompt_templates, "classify_subject_tuong_tac")
        # classify_subject_phan_anh_prompt = pick_prompt_template(prompt_templates, "classify_subject_phan_anh")
        answer_qa_prompt = pick_prompt_template(prompt_templates, "answer_QA")

        # history_data = get_recent_session_history_cached(session_id, tenant_code, limit=2)
        history_data = None
        log_stage("session_history_loaded", has_history=bool(history_data), history_items=len(history_data or []))
        
        logger.info(f"Câu hỏi người dùng: {origin_mess}")
        if not history_data:
            logger.info(f"Chuẩn hóa không có lịch sử với {user_message}")
            start = time.perf_counter()
            user_message = rewrite_query(user_message, prompt_template=None)

            normalized_query = normalize_text(user_message)
            end = time.perf_counter()
            yield f"data: {json.dumps({'log': f'{(end - start):.2f}s Câu hỏi sau khi viết lại (không có lịch sử): {user_message}'})}\n\n"
            log_stage("rewrite_query_no_history")

        if history_data:
            last_question = history_data[0]["expanded_query"]
            # logger.info(f"Câu hỏi trước: {last_question}")

            user_message = rewrite_query_history(user_message, last_question, prompt_template=history_rewrite_prompt)
            normalized_query = normalize_text(user_message)
            yield f"data: {json.dumps({'log': f'Câu hỏi sau khi viết lại (Có lịch sử): {user_message}'})}\n\n"
            log_stage("rewrite_query_with_history")
        
        tenant_ctx = get_resolved_tenant_from_memory(tenant_code)
        current_tenance = tenant_ctx.get("current") if tenant_ctx else None
        parent_tenance = tenant_ctx.get("parent") if tenant_ctx and tenant_ctx.get("parent") else None
        tenant_code_cur = current_tenance.get("id") if current_tenance else None
        tenant_code_parent = parent_tenance.get("id") if parent_tenance else None
        logger.info(f"{current_tenance}, {parent_tenance}")
        tenances = [tenant_code_cur, tenant_code_parent, None]
        domain_org_type = current_tenance.get("domain_org_type") if current_tenance else None
        logger.info(f"Org current type: {tenances}")
        log_stage("tenant_context_loaded", has_domain_org=bool(domain_org_type))
        yield f"data: {json.dumps({'log': f'tenances: {tenances}'})}\n\n"

        scope = extract_scope(user_message)
        if scope in ["tinh_thanh","quoc_gia"]:
            tenances = [None]
            if scope == "tinh_thanh":
                tenances = [tenant_code_parent] 

        logger.info(f"Scope extracted: {scope}")
        
        # result = resolve_unit_type(
        #     query=user_message,
        #     scope=scope,
        #     tenant_ctx=tenant_ctx
        # )

        # logger.info(f"Org type after resolve_unit_type: {result}")

        # resolved_tenant_code = resolve_target_tenant_code_cached(tenant_code, scope)
        # if resolved_tenant_code is None and scope == "xa_phuong":
        #     resolved_tenant_code = tenant_code
        # tenant_code = resolved_tenant_code

        extract_meta = detect_organization_intent_fast_v7_cached(normalized_query)

        org_type = extract_meta['organization_type']
        org_type_is_fallback = False
        if org_type is None:
            org_type = domain_org_type
            org_type_is_fallback = True
            yield f"data: {json.dumps({'log': f'Organization default fallback: {org_type}'})}\n\n"
            log_stage("org_fallback_applied", fallback_org=org_type)
        
        # TARGET = {"mttq", "doan_thanh_nien", "hoi_phu_nu", "dang_uy", "cong_doan"}
        logger.info(f"is_fallback: {org_type_is_fallback}")
        # if org_type in TARGET:
        intent = extract_meta['intent']
        log_stage("Intent (rule-base)", intent=intent)

        yield f"data: {json.dumps({'log': f'Organization (rule-base): {org_type}, Intent (rule-base): {intent}'})}\n\n"

        if intent:
            meta = classify_meta_with_intent(user_message, org_type, intent, org_type_is_fallback)
        else:
            meta = classify_meta_without_intent_cached(user_message, org_type, normalized_query, org_type_is_fallback)
            intent = meta.get("intent") or intent
            level = meta.get("level")
            if len(tenances) != 1:
                if level == "nation":
                    tenances = [None]
                elif level == "province":
                    tenances = [tenant_code_parent]
            score = meta.get("confidence")
            log_stage("Intent (LLM extracting)", intent=intent)
            yield f"data: {json.dumps({'log': f'Intent (LLM extracting): {intent}, Level: {level}, Score: {score}'})}\n\n"
        if (org_type, intent) not in SCORING_CONFIG:
            for token in chunk_text(support_content):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
    
        cfg = SCORING_CONFIG[(org_type, intent)]
        log_stage("Scoring Config", score_config=cfg)

        fields = meta.get("meta") or {}
        meta_payload = build_meta_payload(intent, fields)
        primary_values = meta_payload["primary_values"]
        mode_values = meta_payload["mode_values"]
        yield f"data: {json.dumps({'log': f'Primary value: {primary_values}, mode values: {mode_values}'})}\n\n"

        if intent == "hoi_thu_tuc":
            yield from emit_log("=> Xác định nội dung thuộc thủ tục hành chính\n", force=True)
            meta = classify_llm_procedure_cached(user_message, prompt_template=classify_subject_procedure_prompt)

            if not meta or not isinstance(meta, dict):
                message = "Không thể xác định thủ tục hành chính từ câu hỏi. Anh/chị vui lòng đặt câu hỏi rõ ràng hơn hoặc liên hệ trực tiếp để được hỗ trợ."
                for token in chunk_text(message):
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                return

            query_mode = meta.get("query_mode")

            procedures = meta.get("unit") or []
            if not procedures:
                message = "Không thể xác định thủ tục hành chính từ câu hỏi. Anh/chị vui lòng đặt câu hỏi rõ ràng hơn hoặc liên hệ trực tiếp để được hỗ trợ."
                for token in chunk_text(message):
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                return
            
            logger.info(f"=> Phân tích thủ tục : {meta}")

            procedure_name = procedures[0].get("procedure")
            if not procedure_name:
                message = "Dạ anh/chị, hệ thống khác xác định được rõ tên thủ tục, anh/chị đang hỏi cụ thể về thủ tục nào ạ?"
                for token in chunk_text(message):
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                return
            
            if query_mode == "single_procedure":
                procedure_name = procedures[0].get("procedure")
                primary_values = procedures[0].get("subject")
                procedure_action = procedures[0].get("procedure_action")
                special_contexts = procedures[0].get("special_contexts") or []
                
                mode_values = [
                    x for x in (special_contexts or []) + [procedure_action]
                    if x is not None
                ]
                yield f"data: {json.dumps({'log': f'=> Tên thủ tục: {procedure_name}, primary_value: {primary_values}, mode_values: {mode_values}'})}\n\n"
                try:
                    response = supabase.rpc(
                        "search_documents_meta_generic_v3",
                        {
                            "p_query_format": normalize_text(procedure_name),
                            "p_query_embedding": get_embedding_cached(procedure_name, normalized_query),

                            "p_tenants": [None],

                            "p_org_type": None,
                            "p_intent": intent,

                            "p_primary_values": [primary_values],
                            "p_mode_values": mode_values,

                            "p_procedure": normalize_text(procedure_name),

                            "p_w_intent": cfg["w_intent"],
                            "p_w_primary": cfg["w_primary"],
                            "p_w_mode": cfg["w_mode"],
                            "p_meta_cap": cfg["meta_cap"],

                            "p_limit": 3,
                            "p_per_tenant_limit": 30,
                        }
                    ).execute()
                    chunks = response.data or []
                except Exception as e:
                    logger.error(f"[RPC ERROR] search_documents_meta_generic failed: {str(e)}", exc_info=True)
                    yield f"data: {json.dumps({'log': f'Lỗi tìm kiếm tài liệu: {str(e)}'})}\n\n"
                    for token in chunk_text(support_content):
                        yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                    yield from flush_logs(force=True)
                    yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                    return
            else:
                chunk_response = []
                for proc in procedures:
                    procedure_name = proc['procedure']
                    procedure_action = proc['procedure_action']
                    primary_values = proc['subject']
                    special_contexts = proc['special_contexts'] or []
                    mode_values = [
                        x for x in (special_contexts or []) + [procedure_action]
                        if x is not None
                    ]

                    yield f"data: {json.dumps({'log': f'=> Tên thủ tục: {procedure_name}, primary_value: {primary_values}, mode_values: {mode_values}'})}\n\n"
                    try:
                        response = supabase.rpc(
                            "search_documents_meta_generic_v3",
                            {
                                "p_query_format": normalize_text(procedure_name),
                                "p_query_embedding": get_embedding_cached(procedure_name, normalized_query),

                                "p_tenants": [None],

                                "p_org_type": None,
                                "p_intent": intent,

                                "p_primary_values": [primary_values],
                                "p_mode_values": mode_values,

                                "p_procedure": normalize_text(procedure_name),

                                "p_w_intent": cfg["w_intent"],
                                "p_w_primary": cfg["w_primary"],
                                "p_w_mode": cfg["w_mode"],
                                "p_meta_cap": cfg["meta_cap"],

                                "p_limit": 3,
                                "p_per_tenant_limit": 30,
                            }
                        ).execute()
                        chunks = response.data or []
                        if chunks:
                            chunk_response.append(chunks[0])
                    except Exception as e:
                        logger.error(f"[RPC ERROR] search_documents_meta_generic failed: {str(e)}", exc_info=True)
                        yield f"data: {json.dumps({'log': f'Lỗi tìm kiếm tài liệu: {str(e)}'})}\n\n"
                        for token in chunk_text(support_content):
                            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                        yield from flush_logs(force=True)
                        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                        return
                chunks = chunk_response
            if not chunks:
                for token in chunk_text(support_content):
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                return

            top_chunk = chunks[0] if chunks else {}
            top_score = top_chunk.get("confidence_score", 0)
            logger.info(f"=> Điểm tài liệu tốt nhất: {top_score}")
            logger.info(f"=> Chunks: {chunks}")

            if top_score < 0.2:
                for token in chunk_text(support_content):
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

                end = time.perf_counter()
                duration = (end - start_flow) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= support_content
                log_data["event_type"] = "low_confidence"
                log_data["alias_score"]= top_chunk.get("alias_score", 0)
                log_data["document_score"]= top_score
                log_data["confidence_score"]= top_chunk.get("confidence_score", 0)
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                enqueue_log(log_data)
                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                return

            # context = "\n\n".join(
            #     f"Tài liệu {i+1}:\n{chunk['text_content']}"
            #     for i, chunk in enumerate(chunks)
            # )

            context = "\n\n".join(
                f"**Tài liệu {i+1}**: ({chunk.get('confidence_score', 0):.2f} điểm)\n{chunk['text_content']}"
                for i, chunk in enumerate(chunks)
            )

            yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

            for token in chunk_text(context):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            # full_answer = ""
            # for token in llm_answer_procedure_stream(user_message, context, prompt_template=answer_procedure_prompt):
            #     full_answer += token
            #     yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        
            # answer = full_answer

            # end = time.perf_counter()
            # duration = (end - start_flow) * 1000 
            # log_data["tenant_code"] = tenant_code
            # log_data["raw_query"] = origin_mess
            # log_data["expanded_query"] = user_message
            # log_data["answer"]= answer
            # log_data["event_type"] = "normal"
            # log_data["alias_score"]= top_chunk.get("alias_score", 0)
            # log_data["document_score"]= top_score
            # log_data["confidence_score"]= top_chunk.get("confidence_score", 0)
            # log_data["session_chat"]= session_id
            # log_data["response_time_ms"]= round(duration / 1000,2)
            # enqueue_log(log_data)
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        embedding_query = get_embedding_cached(user_message, normalized_query)

        # for tenant in tenances:
        #     try:
        #         response = supabase.rpc(
        #             "search_documents_meta_generic",
        #             {
        #                 "p_query_format": normalized_query,
        #                 "p_query_embedding": embedding_query,
        #                 "p_tenant": tenant,
        #                 "p_org_type": None if org_type_is_fallback else org_type,
        #                 "p_intent": intent,

        #                 "p_primary_values": primary_values,
        #                 "p_mode_values": mode_values,

        #                 "p_w_intent": cfg["w_intent"],
        #                 "p_w_primary": cfg["w_primary"],
        #                 "p_w_mode": cfg["w_mode"],
        #                 "p_meta_cap": cfg["meta_cap"],

        #                 "p_limit": 3,
        #             }
        #         ).execute()
        #         # chunks = response.data or []
        #         if response.data:
        #             all_chunks.extend(response.data)
        #     except Exception as e:
        #         logger.error(f"[RPC ERROR] search_documents_meta_generic failed: {str(e)}", exc_info=True)
        #         yield f"data: {json.dumps({'log': f'Lỗi tìm kiếm tài liệu: {str(e)}'})}\n\n"
        #         for token in chunk_text(support_content):
        #             yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        #         yield from flush_logs(force=True)
        #         yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        #         return

        try:
            response = supabase.rpc(
                "search_documents_meta_generic_v3",
                {
                    "p_query_format": normalized_query,
                    "p_query_embedding": embedding_query,

                    "p_tenants": tenances,

                    "p_org_type": None,
                    "p_intent": intent,

                    "p_primary_values": primary_values,
                    "p_mode_values": mode_values,

                    "p_w_intent": cfg["w_intent"],
                    "p_w_primary": cfg["w_primary"],
                    "p_w_mode": cfg["w_mode"],
                    "p_meta_cap": cfg["meta_cap"],

                    "p_limit": 5,
                    "p_per_tenant_limit": 30,
                }
            ).execute()
            chunks = response.data or []
        except Exception as e:
            logger.error(f"[RPC ERROR] search_documents_meta_generic failed: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'log': f'Lỗi tìm kiếm tài liệu: {str(e)}'})}\n\n"
            for token in chunk_text(support_content):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        if not chunks:
            for token in chunk_text(support_content):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        top_chunk = chunks[0] if chunks else {}
        top_score = top_chunk.get("confidence_score", 0)
        logger.info(f"=> Điểm tài liệu tốt nhất: {top_score}")
        logger.info(f"=> Chunks: {chunks}")

        if top_score < 0.2:
            for token in chunk_text(support_content):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            end = time.perf_counter()
            duration = (end - start_flow) * 1000 
            log_data["tenant_code"] = tenant_code
            log_data["raw_query"] = origin_mess
            log_data["expanded_query"] = user_message
            log_data["answer"]= support_content
            log_data["event_type"] = "low_confidence"
            log_data["alias_score"]= top_chunk.get("alias_score", 0)
            log_data["document_score"]= top_score
            log_data["confidence_score"]= top_chunk.get("confidence_score", 0)
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            enqueue_log(log_data)
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        context = "\n\n".join(
            f"**Tài liệu {i+1}**: ({chunk.get('confidence_score', 0):.2f} điểm)\n{chunk['text_content']}"
            for i, chunk in enumerate(chunks)
        )

        logger.info(f"Context for answer generation: {context}")
        for token in chunk_text(context):
            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        # full_answer = ""
        # for token in llm_answer_stream(user_message, context, prompt_template=answer_qa_prompt):
        #     full_answer += token
        #     yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        # answer = full_answer

        # end = time.perf_counter()
        # duration = (end - start_flow) * 1000 
        # log_data["tenant_code"] = tenant_code
        # log_data["raw_query"] = origin_mess
        # log_data["expanded_query"] = user_message
        # log_data["answer"]= answer
        # log_data["event_type"] = "normal"
        # log_data["alias_score"]= top_chunk.get("alias_score", 0)
        # log_data["document_score"]= top_score
        # log_data["confidence_score"]= top_chunk.get("confidence_score", 0)
        # log_data["session_chat"]= session_id
        # log_data["response_time_ms"]= round(duration / 1000,2)
        # enqueue_log(log_data)
        yield from flush_logs(force=True)
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        return
       

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # cực quan trọng nếu có nginx
        }
    )   

@app.route('/api/chat-stream', methods=['POST'])
def chat_stream():

    def generate():

        # ✅ LẤY DATA TRƯỚC
        data = request.json or {}
        session_id = data.get("session_id")
        user_message = data.get('question', '').strip()
        origin_mess = user_message
        logger.info(f"Câu hỏi người dùng: {user_message}")

        # Hỗ trợ cả tenant_id và tenant_code
        tenant_id = data.get("tenant_id")
        raw_tenant_code = data.get("tenant_code")
        tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
        log_data = {}
        logger.info(f"Tenant id: {tenant_id}")
        logger.info(f"Tenant code: {tenant_code}")

        help_content = get_default_answer("help")
        out_of_score_content = get_default_answer("out_of_scope")
        thanks_content = get_default_answer("thanks")
        phan_nan_content = get_default_answer("complaint")
        xuc_pham_content = get_default_answer("abuse")
        banned_replies = get_default_answer("banned")
        support_content = get_default_answer("support")

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
            message = err
            for token in chunk_text(message):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        if not tenant_exists(tenant_code):
            message = "Tenant được chọn không tồn tại trong hệ thống."
            for token in chunk_text(message):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
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
        
        result = resolver.process(user_message)
        user_message = result["expanded"]
        normalized_query = result["normalized"]

        logger.info(f"Câu hỏi sau khi xử rule-base từ tắt: {user_message}")

        yield from emit_log("Đang xử lý nội dung câu hỏi\n")

        matched_keyword = find_blocked_keyword(normalized_query)

        if matched_keyword:
            yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)
            banned_replies_stream = chunk_text(banned_replies)
            for token in banned_replies_stream:
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            end = time.perf_counter()
            duration = (end - start_flow) * 1000 
            log_data["raw_query"] = user_message
            log_data["expanded_query"] = normalized_query
            log_data["event_type"] = "banned_topic"
            log_data["answer"]= banned_replies
            log_data["reason"]= f"Nội dung có chứa từ khóa cấm => {matched_keyword}"
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            enqueue_log(log_data)
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
        logger.info(f"Câu hỏi người dùng: {origin_mess}")
        if not history_data:
            logger.info(f"Chuẩn hóa không có lịch sử")
            start = time.perf_counter()
            user_message = rewrite_query(user_message, prompt_template=None)

            normalized_query = normalize_text(user_message)
            yield f"data: {json.dumps({'log': f'Câu hỏi sau khi viết lại (không có lịch sử): {user_message}'})}\n\n"

        if history_data:
            last_question = history_data[0]["expanded_query"]
            logger.info(f"Câu hỏi trước: {last_question}")

            user_message = rewrite_query_history(user_message, last_question, prompt_template=history_rewrite_prompt)
            normalized_query = normalize_text(user_message)
            yield f"data: {json.dumps({'log': f'Câu hỏi sau khi viết lại (Có lịch sử): {user_message}'})}\n\n"

        yield from emit_log("Đang xác định thông tin cần tra cứu\n")
        
        logger.info(f"Normalized query: {user_message}")
        res = classify_v2_cached(normalized_query, PREPARED, tenant_code)
        category, subject = res["category"], res["subject"]
        logger.info(f"Category được xác định(rule-base): {category}")

        if res["need_llm"]:
            category_llm = classify_llm_cached(user_message, prompt_template=classify_category_prompt)
            category = normalize_llm_label(category_llm)
            logger.info(f"Category được xác định(llm): {category}")
            logger.info(f"Prompt xác định category(llm): {classify_category_prompt}")
        
        logger.info(f"Category được xác định: {category}")
        yield f"data: {json.dumps({'log': f'Category được xác định: {category}'})}\n\n"

        if category == "chu_de_cam":
            banned_replies_stream = chunk_text(banned_replies)
            for token in banned_replies_stream:
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            end = time.perf_counter()
            duration = (end - start_flow) * 1000 
            log_data["raw_query"] = user_message
            log_data["expanded_query"] = normalized_query
            log_data["detected_category"] = category
            log_data["event_type"] = "banned_topic"
            log_data["answer"]= banned_replies
            log_data["reason"]= "LLm xác định nội dung thuộc chủ đề cấm"
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            enqueue_log(log_data)
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
            
        if category == "thu_tuc_hanh_chinh":
            yield from emit_log("=> Xác định nội dung thuộc thủ tục hành chính\n", force=True)
            meta = classify_llm_procedure_cached(user_message, prompt_template=classify_subject_procedure_prompt)

            if not meta or not isinstance(meta, dict):
                message = "Không thể xác định thủ tục hành chính từ câu hỏi. Anh/chị vui lòng đặt câu hỏi rõ ràng hơn hoặc liên hệ trực tiếp để được hỗ trợ."
                for token in chunk_text(message):
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                return

            query_mode = meta.get("query_mode")

            procedures = meta.get("unit") or []
            if not procedures:
                message = "Không thể xác định thủ tục hành chính từ câu hỏi. Anh/chị vui lòng đặt câu hỏi rõ ràng hơn hoặc liên hệ trực tiếp để được hỗ trợ."
                for token in chunk_text(message):
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                return
            
            logger.info(f"=> Phân tích thủ tục : {meta}")

            procedure_name = procedures[0].get("procedure")
            if not procedure_name:
                message = "Dạ anh/chị, hệ thống khác xác định được rõ tên thủ tục, anh/chị đang hỏi cụ thể về thủ tục nào ạ?"
                for token in chunk_text(message):
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                return

            chunk_response = []

            if query_mode == "single_procedure":
                procedure_name = procedures[0].get("procedure")
                procedure_action = procedures[0].get("procedure_action")
                special_contexts = procedures[0].get("special_contexts") or []


                yield from emit_log(f"=> Đã xác định tên thủ tục: {procedure_name}\n")
                yield from emit_log("Đang chọn lọc các tài liệu liên quan\n")
                yield f"data: {json.dumps({'log': f'=> Tên thủ tục: {procedure_name}'})}\n\n"
                response = supabase.rpc(
                    "search_documents_full_hybrid_thu_tuc_v1",
                    {
                        "p_query_format": normalize_text(procedure_name),
                        "p_query_embedding": get_embedding_cached(procedure_name, normalized_query),
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
                    yield from emit_log(f"=> Đã xác định tên thủ tục: {procedure_name}\n")
                    yield from emit_log("Đang chọn lọc các tài liệu liên quan\n")
                    yield f"data: {json.dumps({'log': f'=> Tên thủ tục: {procedure_name}'})}\n\n"
                    response = supabase.rpc(
                        "search_documents_full_hybrid_thu_tuc_v1",
                        {
                            "p_query_format": normalize_text(procedure_name),
                            "p_query_embedding": get_embedding_cached(procedure_name, normalized_query),
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
            if not chunks:
                for token in chunk_text(support_content):
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                return
            top_chunk = chunks[0] if chunks else {}
            top_score = top_chunk.get("confidence_score", 0)
            logger.info(f"=> Điểm tài liệu tốt nhất: {top_chunk.get('confidence_score', 0)}")

            if top_score < 0.2:
                for token in chunk_text(support_content):
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

                end = time.perf_counter()
                duration = (end - start_flow) * 1000 
                log_data["tenant_code"] = tenant_code
                log_data["raw_query"] = origin_mess
                log_data["expanded_query"] = user_message
                log_data["answer"]= support_content
                log_data["detected_category"]= category
                log_data["detected_subject"]= subject
                log_data["event_type"] = "low_confidence"
                log_data["alias_score"]= top_chunk.get("alias_score", 0)
                log_data["document_score"]= top_score
                log_data["confidence_score"]= top_chunk.get("confidence_score", 0)
                log_data["session_chat"]= session_id
                log_data["response_time_ms"]= round(duration / 1000,2)
                enqueue_log(log_data)
                yield from flush_logs(force=True)
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                return

            context = "\n\n".join(
                f"Tài liệu {i+1}:\n{chunk['text_content']}"
                for i, chunk in enumerate(chunks)
            )

            yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

            full_answer = ""
            for token in llm_answer_procedure_stream(user_message, context, prompt_template=answer_procedure_prompt):
                full_answer += token
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        
            answer = full_answer

            end = time.perf_counter()
            duration = (end - start_flow) * 1000 
            log_data["tenant_code"] = tenant_code
            log_data["raw_query"] = origin_mess
            log_data["expanded_query"] = user_message
            log_data["answer"]= full_answer
            log_data["detected_category"]= category
            log_data["detected_subject"]= subject
            log_data["event_type"] = "normal"
            top_chunk = chunks[0] if chunks else {}
            log_data["alias_score"]= top_chunk.get("alias_score", 0)
            log_data["document_score"]= top_score
            log_data["confidence_score"]= top_chunk.get("confidence_score", 0)
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            enqueue_log(log_data)
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

            return

        if category == "tuong_tac":
            subject = classify_tuong_tac_cached(user_message, tenant_code, prompt_template=classify_subject_tuong_tac_prompt)
            subject = normalize_subject_value(subject)
            if subject is None:
                subject = "chao_hoi"
            
            yield f"data: {json.dumps({'log': f'Subject: {subject}'})}\n\n"
            logger.info(f"=> Subject: {subject}")
            
            yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

            if subject == "chao_hoi":
                answer_stream = chunk_text(help_content)
                answer = help_content
                event_type = "normal"
            if subject == "cam_on_tam_biet":
                answer_stream = chunk_text(thanks_content)
                answer = thanks_content
                event_type = "normal"
            if subject == "phan_nan_buc_xuc":
                answer_stream = chunk_text(phan_nan_content)
                answer = phan_nan_content
                event_type = "complaint"
            if subject == "xuc_pham_vi_pham":
                answer_stream = chunk_text(xuc_pham_content)
                answer = xuc_pham_content
                event_type = "banned_topic"
            if subject == "chu_de_cam":
                answer_stream = chunk_text(banned_replies)
                answer = banned_replies
                event_type = "banned_topic"

            for token in answer_stream:
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            end = time.perf_counter()
            duration = (end - start_flow) * 1000 
            log_data["tenant_code"] = tenant_code
            log_data["raw_query"] = origin_mess
            log_data["expanded_query"] = user_message
            log_data["answer"]= answer
            log_data["event_type"] = event_type
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            enqueue_log(log_data)
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
        
        scope = extract_scope(user_message)
        
        start = time.perf_counter()

        tenant_ctx = get_resolved_tenant_from_memory(tenant_code)

        logger.info(f"=> {tenant_ctx}")

        result = resolve_unit_type(
            query=user_message,
            scope=scope,
            tenant_ctx=tenant_ctx
        )

        end_time = time.perf_counter()
        duration = (end_time - start) * 1000
        yield f"data: {json.dumps({'log': f'Thời gian xử lý unit type: {duration / 1000:.2f} s'})}\n\n"

        user_message = result["normalized_query"]
        yield f"data: {json.dumps({'log': f'Câu hỏi đã xử lý unit type: {user_message}'})}\n\n"
            
        resolved_tenant_code = resolve_target_tenant_code_cached(tenant_code, scope)
        if resolved_tenant_code is None and scope == "xa_phuong":
            resolved_tenant_code = tenant_code
        tenant_code = resolved_tenant_code

        logger.info(f"=> Scope: {scope}, Resolved tenant code: {tenant_code}")
        yield f"data: {json.dumps({'log': f'Scope: {scope}, Resolved tenant code: {tenant_code}'})}\n\n"

        if category == "phan_anh_kien_nghi":
            subject = classify_phan_anh_cached(user_message, tenant_code, prompt_template=classify_subject_phan_anh_prompt)
            subject = normalize_subject_value(subject)
            tenant_code = None
            logger.info(f"=> Subject: {subject}")
            yield f"data: {json.dumps({'log': f'Subject: {subject}'})}\n\n"


            yield from emit_log("Thuộc phạm vi - phản ánh kiến nghị\n")

        if category == "thong_tin_tong_quan":
            subject = classify_tong_quan_cached(user_message, tenant_code, prompt_template=classify_subject_qa_prompt)
            subject = normalize_subject_value(subject)
            logger.info(f"=> Subject: {subject}")
            yield f"data: {json.dumps({'log': f'Subject: {subject}'})}\n\n"
            yield from emit_log("Đang tra cứu thông tin tổng quan\n")

        

        query_embedding = get_embedding_cached(user_message, normalized_query)

        chunks = search_documents_full_hybrid_v6_cached(
            normalized_query=normalized_query,
            query_embedding=query_embedding,
            category=category,
            subject=subject,
            p_limit=5,
            tenant=tenant_code
        )

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

                # Nếu không subject tốt hơn → dùng nó
                if best_score_all > best_score:
                    chunks = chunks_all
        
        # id_chunk = chunks[0]["id"] if chunks else None

        if not chunks:
            for token in chunk_text(support_content):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        top_chunk = chunks[0] if chunks else {}
        top_score = top_chunk.get("confidence_score", 0)
        logger.info(f"=> Điểm tài liệu tốt nhất: {top_score}")
        logger.info(f"=> Chunks: {chunks}")

        if top_score < 0.2:
            for token in chunk_text(support_content):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            end = time.perf_counter()
            duration = (end - start_flow) * 1000 
            log_data["tenant_code"] = tenant_code
            log_data["raw_query"] = origin_mess
            log_data["expanded_query"] = user_message
            log_data["answer"]= support_content
            log_data["detected_category"]= category
            log_data["detected_subject"]= subject
            log_data["event_type"] = "low_confidence"
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            enqueue_log(log_data)
            yield from flush_logs(force=True)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
        
        # primary_chunks = chunks[:5]
        # context_parts = [
        #     f"### Tài liệu {i+1}\n{chunk['text_content']}"
        #     for i, chunk in enumerate(chunks)
        # ] if chunks else []

        # yield from emit_log("Đang tìm các tài liệu liên quan")

        # related_chunks = get_related_chunks_cached(tenant_code, id_chunk)
        # if related_chunks:
        #     # Avoid duplicate documents when a related chunk already appears in top results.
        #     existing_ids = {c.get("id") for c in primary_chunks}
        #     unique_related = [c for c in related_chunks if c.get("id") not in existing_ids]

        #     if unique_related:
        #         start_idx = len(context_parts)
        #         context_parts.extend(
        #             f"### Tài liệu liên quan {start_idx + i + 1}\n{chunk['text_content']}"
        #             for i, chunk in enumerate(unique_related[:3])
        #         )

        # context = "\n\n".join(context_parts)
        context = "\n\n".join(
            f"Tài liệu {i+1}:\n{chunk['text_content']}"
            for i, chunk in enumerate(chunks)
        )

        yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

        full_answer = ""
        for token in llm_answer_stream(user_message, context, prompt_template=answer_qa_prompt):
            full_answer += token
            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
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
        log_data["confidence_score"]= top_score
        log_data["session_chat"]= session_id
        log_data["response_time_ms"]= round(duration, 2)
        enqueue_log(log_data)
        yield from flush_logs(force=True)
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        return

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # cực quan trọng nếu có nginx
        }
    )      

# @app.route('/api/chat-stream-v2', methods=['POST'])
# def chat_stream_v2():

#     def generate():

#         # ✅ LẤY DATA TRƯỚC
#         data = request.json or {}
#         session_id = data.get("session_id")
#         user_message = data.get('question', '').strip()
#         origin_mess = user_message
#         logger.info(f"Câu hỏi người dùng: {user_message}")

#         # Hỗ trợ cả tenant_id và tenant_code
#         tenant_id = data.get("tenant_id")
#         raw_tenant_code = data.get("tenant_code")
#         tenant_code, err = ensure_tenant_code(tenant_id=tenant_id, tenant_code=raw_tenant_code)
#         log_data = {}
#         logger.info(f"Tenant id: {tenant_id}")
#         logger.info(f"Tenant code: {tenant_code}")

#         help_content = get_default_answer("help")
#         out_of_score_content = get_default_answer("out_of_scope")
#         thanks_content = get_default_answer("thanks")
#         phan_nan_content = get_default_answer("complaint")
#         xuc_pham_content = get_default_answer("abuse")
#         banned_replies = get_default_answer("banned")
#         support_content = get_default_answer("support")

#         LOG_FLUSH_INTERVAL_SECONDS = 0.08
#         LOG_BUFFER_MAX = 64
#         pending_logs = []
#         last_log_flush_at = time.perf_counter()

#         def flush_logs(force=False):
#             nonlocal last_log_flush_at
#             if not pending_logs:
#                 return

#             now = time.perf_counter()
#             if not force and (now - last_log_flush_at) < LOG_FLUSH_INTERVAL_SECONDS:
#                 return

#             batch = "\n".join(pending_logs)
#             pending_logs.clear()
#             last_log_flush_at = now
#             yield f"data: {json.dumps({'thought': batch}, ensure_ascii=False)}\n\n"

#         def emit_log(message, force=False):
#             if message is None:
#                 return

#             if len(pending_logs) >= LOG_BUFFER_MAX:
#                 pending_logs.pop(0)
#             pending_logs.append(str(message))
#             yield from flush_logs(force=force)

#         if err:
#             message = err
#             for token in chunk_text(message):
#                 yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
#             yield from flush_logs(force=True)
#             yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#             return

#         if not tenant_exists(tenant_code):
#             message = "Tenant được chọn không tồn tại trong hệ thống."
#             for token in chunk_text(message):
#                 yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
#             yield from flush_logs(force=True)
#             yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#             return
        
#         yield from emit_log(f"Đã nhận câu hỏi anh/chị: {origin_mess}")

#         try:
#             prompt_templates = get_active_prompt_templates_map_cached()
#         except Exception as e:
#             prompt_templates = {}
#             yield from emit_log(f"Không thể tải prompt templates: {str(e)}", force=True)

#         history_rewrite_prompt = pick_prompt_template(prompt_templates, "history_rewrite")
#         classify_category_prompt = pick_prompt_template(prompt_templates, "classify_category")
#         classify_subject_procedure_prompt = pick_prompt_template(prompt_templates, "classify_subject_procedure")
#         answer_procedure_prompt = pick_prompt_template(prompt_templates, "answer_procedure")
#         classify_subject_qa_prompt = pick_prompt_template(prompt_templates, "classify_subject_QA")
#         classify_subject_tuong_tac_prompt = pick_prompt_template(prompt_templates, "classify_subject_tuong_tac")
#         classify_subject_phan_anh_prompt = pick_prompt_template(prompt_templates, "classify_subject_phan_anh")
#         answer_qa_prompt = pick_prompt_template(prompt_templates, "answer_QA")

#         start_flow = time.perf_counter()

#         history_data = get_recent_session_history_cached(session_id, tenant_code, limit=2)
        
#         result = resolver.process(user_message)
#         user_message = result["expanded"]
#         normalized_query = result["normalized"]

#         logger.info(f"Câu hỏi sau khi xử rule-base từ tắt: {user_message}")

#         yield from emit_log("Đang xử lý nội dung câu hỏi\n")
#         # matched_keyword = next(
#         #     (
#         #         kw for kw in BANNED_KEYWORDS
#         #         if kw.lower() in user_message.lower()
#         #         or normalize_text(kw) in normalized_query
#         #     ),
#         #     None
#         # )

#         matched_keyword = find_blocked_keyword(normalized_query)

#         if matched_keyword:
#             yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)
#             banned_replies_stream = chunk_text(banned_replies)
#             for token in banned_replies_stream:
#                 yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

#             end = time.perf_counter()
#             duration = (end - start_flow) * 1000 
#             log_data["raw_query"] = user_message
#             log_data["expanded_query"] = normalized_query
#             log_data["event_type"] = "banned_topic"
#             log_data["answer"]= banned_replies
#             log_data["reason"]= f"Nội dung có chứa từ khóa cấm => {matched_keyword}"
#             log_data["session_chat"]= session_id
#             log_data["response_time_ms"]= round(duration / 1000,2)
#             enqueue_log(log_data)
#             yield from flush_logs(force=True)
#             yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#             return
#         logger.info(f"Câu hỏi người dùng: {origin_mess}")
#         if not history_data:
#             logger.info(f"Chuẩn hóa không có lịch sử")
#             start = time.perf_counter()
#             user_message = rewrite_query(user_message, prompt_template=None)

#             normalized_query = normalize_text(user_message)
#             yield f"data: {json.dumps({'log': f'Câu hỏi sau khi viết lại (không có lịch sử): {user_message}'})}\n\n"

#         if history_data:
#             last_question = history_data[0]["expanded_query"]
#             logger.info(f"Câu hỏi trước: {last_question}")

#             user_message = rewrite_query_history(user_message, last_question, prompt_template=history_rewrite_prompt)
#             normalized_query = normalize_text(user_message)
#             yield f"data: {json.dumps({'log': f'Câu hỏi sau khi viết lại (Có lịch sử): {user_message}'})}\n\n"

#         yield from emit_log("Đang xác định thông tin cần tra cứu\n")
        
#         logger.info(f"Normalized query: {user_message}")

#         metadata_rb = detect_organization_metadata_fast_v5(normalized_query)

#         rb_organization_type = metadata_rb.get("organization_type")
#         yield f"data: {json.dumps({'log': f'Organization Type (rule-base): {rb_organization_type}'})}\n\n"
#         if rb_organization_type is None:
#             start = time.perf_counter()
#             rb_organization_type = classify_organization_type(user_message)
#             end = time.perf_counter()
#             duration = (end - start)
#             yield f"data: {json.dumps({'log': f'[{duration:.2f} s]Organization Type (LLM extract): {rb_organization_type}'})}\n\n"

#         if rb_organization_type:
#             rb_category = metadata_rb.get("category")
#             rb_subject = metadata_rb.get("subject")
            
#             category = rb_category
#             subject = rb_subject

#             yield f"data: {json.dumps({'log': f'Category (rule-base): {category}'})}\n\n"
#             yield f"data: {json.dumps({'log': f'Subject (rule-base): {subject}'})}\n\n"

#             if category is None:
#                 category = classify_category_doan_the(user_message, rb_organization_type)
#                 yield f"data: {json.dumps({'log': f'Category (LLM extract): {category}'})}\n\n"
            
#             if subject is None:
#                 if category == "to_chuc_bo_may":
#                     subject = "chuc_vu"

#                 if category == "thong_tin_tong_quan":
#                     subject = classify_subject_doan_the(user_message, rb_organization_type)
#                     yield f"data: {json.dumps({'log': f'Subject (LLM extract): {subject}'})}\n\n"
            

#             yield f"data: {json.dumps({'log': f'p_query_format {normalized_query}'})}\n\n"
#             yield f"data: {json.dumps({'log': f'p_query_embedding {user_message}'})}\n\n"
#             yield f"data: {json.dumps({'log': f'p_tenant {tenant_code}'})}\n\n"
#             yield f"data: {json.dumps({'log': f'p_organization_type {rb_organization_type}'})}\n\n"
#             yield f"data: {json.dumps({'log': f'p_category {category}, p_subject {subject}'})}\n\n"
#             response = supabase.rpc(
#                 "search_documents_v2",
#                 {
#                     "p_query_format": normalized_query,
#                     "p_query_embedding": get_embedding_cached(user_message, normalized_query),
#                     "p_tenant": tenant_code,
#                     "p_organization_type": rb_organization_type,
#                     "p_category": category,
#                     "p_subject": subject,
#                     "p_limit": 1 if subject == "thu_tuc_quy_trinh" else 5
#                 }
#             ).execute()

#             chunks = response.data or []
#             yield f"data: {json.dumps({'log': f'Filter chunk xong {chunks}'})}\n\n"
#             if not chunks:
#                 for token in chunk_text(support_content):
#                     yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

#                 yield from flush_logs(force=True)
#                 yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#                 return
            
#             top_score = chunks[0]["confidence_score"] if chunks else 0
#             alias_score = chunks[0]["alias_score"] if chunks else 0
#             document_score = chunks[0]["document_score"] if chunks else 0
            
#             context = "\n\n".join(
#                 f"Tài liệu {i+1}:\n{chunk['text_content']}"
#                 for i, chunk in enumerate(chunks)
#             )

#             yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

#             full_answer = ""
#             for token in llm_answer_stream(user_message, context, prompt_template=answer_qa_prompt):
#                 full_answer += token
#                 yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        
#             answer = full_answer

#             end = time.perf_counter()
#             duration = (end - start_flow) * 1000 
#             log_data["tenant_code"] = tenant_code
#             log_data["raw_query"] = origin_mess
#             log_data["expanded_query"] = user_message
#             log_data["answer"]= full_answer
#             log_data["detected_category"]= category
#             log_data["detected_subject"]= subject
#             log_data["event_type"] = "normal"
#             log_data["alias_score"]= alias_score
#             log_data["document_score"]= document_score
#             log_data["confidence_score"]= top_score
#             log_data["session_chat"]= session_id
#             log_data["response_time_ms"]= round(duration / 1000,2)
#             enqueue_log(log_data)
#             yield from flush_logs(force=True)
#             yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

#             return
            
#         res = classify_v2_cached(normalized_query, PREPARED, tenant_code)
#         category, subject = res["category"], res["subject"]

#         if res["need_llm"]:
#             category_llm = classify_llm_cached(user_message, prompt_template=classify_category_prompt)
#             category = normalize_llm_label(category_llm)
        
#         logger.info(f"Category được xác định: {category}")
#         yield f"data: {json.dumps({'log': f'Category được xác định: {category}'})}\n\n"

#         if category == "chu_de_cam":
#             banned_replies_stream = chunk_text(banned_replies)
#             for token in banned_replies_stream:
#                 yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
#             end = time.perf_counter()
#             duration = (end - start_flow) * 1000 
#             log_data["raw_query"] = user_message
#             log_data["expanded_query"] = normalized_query
#             log_data["detected_category"] = category
#             log_data["event_type"] = "banned_topic"
#             log_data["answer"]= banned_replies
#             log_data["reason"]= "LLm xác định nội dung thuộc chủ đề cấm"
#             log_data["session_chat"]= session_id
#             log_data["response_time_ms"]= round(duration / 1000,2)
#             enqueue_log(log_data)
#             yield from flush_logs(force=True)
#             yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#             return
            
#         if category == "thu_tuc_hanh_chinh":
#             yield from emit_log("=> Xác định nội dung thuộc thủ tục hành chính\n", force=True)
#             meta = classify_llm_procedure_cached(user_message, prompt_template=classify_subject_procedure_prompt)

#             if not meta or not isinstance(meta, dict):
#                 message = "Không thể xác định thủ tục hành chính từ câu hỏi. Anh/chị vui lòng đặt câu hỏi rõ ràng hơn hoặc liên hệ trực tiếp để được hỗ trợ."
#                 for token in chunk_text(message):
#                     yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
#                 yield from flush_logs(force=True)
#                 yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#                 return

#             query_mode = meta.get("query_mode")

#             procedures = meta.get("unit") or []
#             if not procedures:
#                 message = "Không thể xác định thủ tục hành chính từ câu hỏi. Anh/chị vui lòng đặt câu hỏi rõ ràng hơn hoặc liên hệ trực tiếp để được hỗ trợ."
#                 for token in chunk_text(message):
#                     yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
#                 yield from flush_logs(force=True)
#                 yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#                 return
            
#             logger.info(f"=> Phân tích thủ tục : {meta}")

#             procedure_name = procedures[0].get("procedure")
#             if not procedure_name:
#                 message = "Dạ anh/chị, hệ thống khác xác định được rõ tên thủ tục, anh/chị đang hỏi cụ thể về thủ tục nào ạ?"
#                 for token in chunk_text(message):
#                     yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
#                 yield from flush_logs(force=True)
#                 yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#                 return

#             chunk_response = []

#             if query_mode == "single_procedure":
#                 procedure_name = procedures[0].get("procedure")
#                 procedure_action = procedures[0].get("procedure_action")
#                 special_contexts = procedures[0].get("special_contexts") or []


#                 yield from emit_log(f"=> Đã xác định tên thủ tục: {procedure_name}\n")
#                 yield from emit_log("Đang chọn lọc các tài liệu liên quan\n")
#                 yield f"data: {json.dumps({'log': f'=> Tên thủ tục: {procedure_name}'})}\n\n"
#                 response = supabase.rpc(
#                     "search_documents_full_hybrid_thu_tuc_v1",
#                     {
#                         "p_query_format": normalize_text(procedure_name),
#                         "p_query_embedding": get_embedding_cached(procedure_name, normalized_query),
#                         "p_tenant": None,
#                         "p_category": category,
#                         "p_subject": procedures[0]['subject'],
#                         "p_procedure": normalize_text(procedure_name),
#                         "p_procedure_action": procedure_action,
#                         "p_special_contexts": special_contexts,
#                         "p_limit": 3
#                     }
#                 ).execute()
#                 chunks = response.data or []
#             else:
#                 chunk_response = []
#                 for proc in procedures:
#                     procedure_name = proc['procedure']
#                     procedure_action = proc['procedure_action']
#                     special_contexts = proc['special_contexts']
#                     yield from emit_log(f"=> Đã xác định tên thủ tục: {procedure_name}\n")
#                     yield from emit_log("Đang chọn lọc các tài liệu liên quan\n")
#                     yield f"data: {json.dumps({'log': f'=> Tên thủ tục: {procedure_name}'})}\n\n"
#                     response = supabase.rpc(
#                         "search_documents_full_hybrid_thu_tuc_v1",
#                         {
#                             "p_query_format": normalize_text(procedure_name),
#                             "p_query_embedding": get_embedding_cached(procedure_name, normalized_query),
#                             "p_tenant": None,
#                             "p_category": category,
#                             "p_subject": proc['subject'],
#                             "p_procedure": normalize_text(procedure_name),
#                             "p_procedure_action": procedure_action,
#                             "p_special_contexts": special_contexts,
#                             "p_limit": 1
#                         }
#                     ).execute()

#                     chunks = response.data or []
#                     if chunks:
#                         chunk_response.append(chunks[0])
#                 chunks = chunk_response
#             if not chunks:
#                 for token in chunk_text(support_content):
#                     yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

#                 yield from flush_logs(force=True)
#                 yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#                 return
#             top_score = chunks[0]["confidence_score"] if chunks else 0
#             logger.info(f"=> Điểm tài liệu tốt nhất: {top_score}")

#             if top_score < 0.2:
#                 for token in chunk_text(support_content):
#                     yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

#                 end = time.perf_counter()
#                 duration = (end - start_flow) * 1000 
#                 log_data["tenant_code"] = tenant_code
#                 log_data["raw_query"] = origin_mess
#                 log_data["expanded_query"] = user_message
#                 log_data["answer"]= support_content
#                 log_data["detected_category"]= category
#                 log_data["detected_subject"]= subject
#                 log_data["event_type"] = "low_confidence"
#                 log_data["alias_score"]= top_chunk.get("alias_score", 0)
#                 log_data["document_score"]= top_score
#                 log_data["confidence_score"]= top_chunk.get("confidence_score", 0)
#                 log_data["session_chat"]= session_id
#                 log_data["response_time_ms"]= round(duration / 1000,2)
#                 enqueue_log(log_data)
#                 yield from flush_logs(force=True)
#                 yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#                 return

#             context = "\n\n".join(
#                 f"Tài liệu {i+1}:\n{chunk['text_content']}"
#                 for i, chunk in enumerate(chunks)
#             )

#             yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

#             full_answer = ""
#             for token in llm_answer_procedure_stream(user_message, context, prompt_template=answer_procedure_prompt):
#                 full_answer += token
#                 yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        
#             answer = full_answer

#             end = time.perf_counter()
#             duration = (end - start_flow) * 1000 
#             log_data["tenant_code"] = tenant_code
#             log_data["raw_query"] = origin_mess
#             log_data["expanded_query"] = user_message
#             log_data["answer"]= full_answer
#             log_data["detected_category"]= category
#             log_data["detected_subject"]= subject
#             log_data["event_type"] = "normal"
#             top_chunk = chunks[0] if chunks else {}
#             log_data["alias_score"]= top_chunk.get("alias_score", 0)
#             log_data["document_score"]= top_score
#             log_data["confidence_score"]= top_chunk.get("confidence_score", 0)
#             log_data["session_chat"]= session_id
#             log_data["response_time_ms"]= round(duration / 1000,2)
#             enqueue_log(log_data)
#             yield from flush_logs(force=True)
#             yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

#             return

#         if category == "tuong_tac":
#             subject = classify_tuong_tac_cached(user_message, tenant_code, prompt_template=classify_subject_tuong_tac_prompt)
#             subject = normalize_subject_value(subject)
#             if subject is None:
#                 subject = "chao_hoi"
            
#             yield f"data: {json.dumps({'log': f'Subject: {subject}'})}\n\n"
#             logger.info(f"=> Subject: {subject}")
            
#             yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

#             if subject == "chao_hoi":
#                 answer_stream = chunk_text(help_content)
#                 answer = help_content
#                 event_type = "normal"
#             if subject == "cam_on_tam_biet":
#                 answer_stream = chunk_text(thanks_content)
#                 answer = thanks_content
#                 event_type = "normal"
#             if subject == "phan_nan_buc_xuc":
#                 answer_stream = chunk_text(phan_nan_content)
#                 answer = phan_nan_content
#                 event_type = "complaint"
#             if subject == "xuc_pham_vi_pham":
#                 answer_stream = chunk_text(xuc_pham_content)
#                 answer = xuc_pham_content
#                 event_type = "banned_topic"
#             if subject == "chu_de_cam":
#                 answer_stream = chunk_text(banned_replies)
#                 answer = banned_replies
#                 event_type = "banned_topic"

#             for token in answer_stream:
#                 yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

#             end = time.perf_counter()
#             duration = (end - start_flow) * 1000 
#             log_data["tenant_code"] = tenant_code
#             log_data["raw_query"] = origin_mess
#             log_data["expanded_query"] = user_message
#             log_data["answer"]= answer
#             log_data["event_type"] = event_type
#             log_data["session_chat"]= session_id
#             log_data["response_time_ms"]= round(duration / 1000,2)
#             enqueue_log(log_data)
#             yield from flush_logs(force=True)
#             yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#             return
        
#         scope = extract_scope(user_message)
        
#         start = time.perf_counter()

#         tenant_ctx = get_resolved_tenant_from_memory(tenant_code)

#         logger.info(f"=> {tenant_ctx}")

#         result = resolve_unit_type(
#             query=user_message,
#             scope=scope,
#             tenant_ctx=tenant_ctx
#         )

#         end_time = time.perf_counter()
#         duration = (end_time - start) * 1000
#         yield f"data: {json.dumps({'log': f'Thời gian xử lý unit type: {duration / 1000:.2f} s'})}\n\n"

#         user_message = result["normalized_query"]
#         yield f"data: {json.dumps({'log': f'Câu hỏi đã xử lý unit type: {user_message}'})}\n\n"
            
#         resolved_tenant_code = resolve_target_tenant_code_cached(tenant_code, scope)
#         if resolved_tenant_code is None and scope == "xa_phuong":
#             resolved_tenant_code = tenant_code
#         tenant_code = resolved_tenant_code

#         logger.info(f"=> Scope: {scope}, Resolved tenant code: {tenant_code}")
#         yield f"data: {json.dumps({'log': f'Scope: {scope}, Resolved tenant code: {tenant_code}'})}\n\n"

#         if category == "phan_anh_kien_nghi":
#             subject = classify_phan_anh_cached(user_message, tenant_code, prompt_template=classify_subject_phan_anh_prompt)
#             subject = normalize_subject_value(subject)
#             tenant_code = None
#             logger.info(f"=> Subject: {subject}")
#             yield f"data: {json.dumps({'log': f'Subject: {subject}'})}\n\n"


#             yield from emit_log("Thuộc phạm vi - phản ánh kiến nghị\n")

#         if category == "thong_tin_tong_quan":
#             subject = classify_tong_quan_cached(user_message, tenant_code, prompt_template=classify_subject_qa_prompt)
#             subject = normalize_subject_value(subject)
#             logger.info(f"=> Subject: {subject}")
#             yield f"data: {json.dumps({'log': f'Subject: {subject}'})}\n\n"
#             yield from emit_log("Đang tra cứu thông tin tổng quan\n")

        

#         query_embedding = get_embedding_cached(user_message, normalized_query)

#         chunks = search_documents_full_hybrid_v6_cached(
#             normalized_query=normalized_query,
#             query_embedding=query_embedding,
#             category=category,
#             subject=subject,
#             p_limit=5,
#             tenant=tenant_code
#         )

#         if subject in ["chuc_vu", "nhan_su"]:
#             best_score = chunks[0]["confidence_score"] if chunks else 0
#             if best_score < 0.4:
#                 chunks_all = search_documents_full_hybrid_v6_cached(
#                     normalized_query=normalized_query,
#                     query_embedding=query_embedding,
#                     category="to_chuc_bo_may",
#                     subject=None,
#                     p_limit=5,
#                     tenant=tenant_code
#                 )

#                 best_score_all = chunks_all[0]["confidence_score"] if chunks_all else 0

#                 # Nếu không subject tốt hơn → dùng nó
#                 if best_score_all > best_score:
#                     chunks = chunks_all
        
#         # id_chunk = chunks[0]["id"] if chunks else None

#         if not chunks:
#             for token in chunk_text(support_content):
#                 yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

#             yield from flush_logs(force=True)
#             yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#             return

#         top_score = chunks[0]["confidence_score"] if chunks else 0
#         logger.info(f"=> Điểm tài liệu tốt nhất: {top_score}")
#         logger.info(f"=> Chunks: {chunks}")

#         if top_score < 0.2:
#             for token in chunk_text(support_content):
#                 yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

#             end = time.perf_counter()
#             duration = (end - start_flow) * 1000 
#             log_data["tenant_code"] = tenant_code
#             log_data["raw_query"] = origin_mess
#             log_data["expanded_query"] = user_message
#             log_data["answer"]= support_content
#             log_data["detected_category"]= category
#             log_data["detected_subject"]= subject
#             log_data["event_type"] = "low_confidence"
#             log_data["session_chat"]= session_id
#             log_data["response_time_ms"]= round(duration / 1000,2)
#             enqueue_log(log_data)
#             yield from flush_logs(force=True)
#             yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#             return
        
#         # primary_chunks = chunks[:5]
#         # context_parts = [
#         #     f"### Tài liệu {i+1}\n{chunk['text_content']}"
#         #     for i, chunk in enumerate(chunks)
#         # ] if chunks else []

#         # yield from emit_log("Đang tìm các tài liệu liên quan")

#         # related_chunks = get_related_chunks_cached(tenant_code, id_chunk)
#         # if related_chunks:
#         #     # Avoid duplicate documents when a related chunk already appears in top results.
#         #     existing_ids = {c.get("id") for c in primary_chunks}
#         #     unique_related = [c for c in related_chunks if c.get("id") not in existing_ids]

#         #     if unique_related:
#         #         start_idx = len(context_parts)
#         #         context_parts.extend(
#         #             f"### Tài liệu liên quan {start_idx + i + 1}\n{chunk['text_content']}"
#         #             for i, chunk in enumerate(unique_related[:3])
#         #         )

#         # context = "\n\n".join(context_parts)
#         context = "\n\n".join(
#             f"Tài liệu {i+1}:\n{chunk['text_content']}"
#             for i, chunk in enumerate(chunks)
#         )

#         yield from emit_log("Anh/chị chờ trong giây lát, đang tổng hợp câu trả lời...", force=True)

#         full_answer = ""
#         for token in llm_answer_stream(user_message, context, prompt_template=answer_qa_prompt):
#             full_answer += token
#             yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
#         answer = full_answer

#         end = time.perf_counter()
#         duration = (end - start_flow)
#         log_data["tenant_code"] = tenant_code
#         log_data["raw_query"] = origin_mess
#         log_data["expanded_query"] = user_message
#         log_data["answer"]= answer
#         log_data["detected_category"]= category
#         log_data["detected_subject"]= subject
#         log_data["event_type"] = "normal"
#         log_data["alias_score"]= chunks[0]["alias_score"] if chunks else 0
#         log_data["document_score"]= chunks[0]["document_score"] if chunks else 0
#         log_data["confidence_score"]= top_score
#         log_data["session_chat"]= session_id
#         log_data["response_time_ms"]= round(duration, 2)
#         enqueue_log(log_data)
#         yield from flush_logs(force=True)
#         yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
#         return

#     return Response(
#         stream_with_context(generate()),
#         mimetype="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "X-Accel-Buffering": "no"  # cực quan trọng nếu có nginx
#         }
#     )   

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
                        "p_query_embedding": get_embedding_cached(procedure_name, normalized_procedure),
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
                            "p_query_embedding": get_embedding_cached(procedure_name, normalized_procedure),
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

        query_embedding = get_embedding_cached(user_message, normalized_query)
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

def init_cache():
    refresh_keywords_cache()
    refresh_default_answers_cache()
    refresh_tenant_cache()
    logger.info("Cache initialized successfully.")

init_cache()

if __name__ == '__main__':
    app.run(debug=True)

