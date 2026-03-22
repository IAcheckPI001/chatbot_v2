

import time
import hashlib
from threading import Lock
from flask import Flask
from flask_cors import CORS
from openai import OpenAI
import pandas as pd

from dotenv import load_dotenv
import os
from corn import supabase
import json
from normalize import SINGLE_TOKEN_MAP, CONTEXT_RULES, BANNED_KEYWORDS, normalize_text, AbbreviationResolver
from model import rewrite_query, detect_query, llm_answer, classify_category, check_classify_tuong_tac
from test_demo import classify_v2
from embedding import get_embedding
from utils import SUBJECT_KEYWORDS, prepare_subject_keywords
from export_metadata import classify_llm, classify_with_tong_quan, classify_with_phan_anh, classify_with_tuong_tac
from app import classify_llm_cached
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


def normalize_llm_label(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.lower() in {"none", "null", "unknown", "n/a"}:
        return None
    return s


def normalize_subject_value(value):
    # Some classifiers may return a dict like {"subject": "..."}.
    if isinstance(value, dict):
        value = value.get("subject")
    return normalize_llm_label(value)


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
    subject = normalize_subject_value(subject)
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

from model import llm_rewrite, _render_prompt_template

# def rewrite_history(query, last_question, prompt_template=None):
#     default_prompt = f"""Bạn là hệ thống viết lại câu hỏi theo ngữ cảnh cho chatbot hành chính cấp xã.

# NHIỆM VỤ
# Viết lại câu hỏi hiện tại thành đúng 1 câu hỏi độc lập, ngắn gọn, giữ nguyên ý nghĩa gốc.

# ĐẦU VÀO
# - Câu trước đó đã được viết lại đầy đủ: {last_question}
# - Câu hỏi hiện tại: {query}

# NGUYÊN TẮC CHUNG
# - Chỉ dùng thông tin có trong 2 câu trên.
# - Không bịa thêm thông tin mới.
# - Nếu không đủ chắc chắn để viết lại đúng, giữ nguyên câu hiện tại.
# - Nếu câu hiện tại đã là câu độc lập, giữ nguyên.
# - Chỉ trả về đúng 1 câu hỏi cuối cùng, không giải thích.

# ƯU TIÊN QUYẾT ĐỊNH
# 1. Nếu câu hiện tại là lời chào, cảm ơn, cảm thán, xác nhận ngắn, xúc phạm, hoặc quá mơ hồ không xác định chắc chắn được ý hỏi -> giữ nguyên.
# 2. Nếu câu hiện tại đã đủ chủ đề, đối tượng và ý định hỏi -> giữ nguyên.
# 3. Nếu câu hiện tại là câu tiếp nối thiếu chủ đề nhưng vẫn giữ ý hỏi cũ -> bổ sung chủ đề từ câu trước.
# 4. Nếu câu hiện tại đổi đối tượng mới nhưng giữ cách hỏi từ câu trước -> giữ mẫu hỏi cũ và thay đối tượng mới.
# 5. Nếu câu hiện tại chỉ còn trường thông tin cần hỏi (ví dụ: số điện thoại, địa chỉ, email, hotline, lệ phí, hồ sơ, giấy tờ, bao lâu, ở đâu, online được không) -> khôi phục câu hỏi đầy đủ từ câu trước nếu chắc chắn.
# 6. Nếu không chắc chắn -> giữ nguyên.

# QUY TẮC BẮT BUỘC
# - Không biến câu hỏi thông tin nhân sự thành câu hỏi thủ tục.
# - Không biến câu hỏi thủ tục thành câu hỏi nhân sự.
# - Không đổi tên người, chức danh, địa danh, số hiệu khu phố, số hiệu ấp.
# - Không được làm mất các phần *phân biệt quan trọng* của thủ tục như: "lại", "cấp lại", "trích lục", "bản sao", "có yếu tố nước ngoài", "khu vực biên giới", "thường trú", "tạm trú".
# - Không tự thêm các từ như "là gì", "ở đâu", "bao lâu", "như thế nào" nếu câu trước không cho thấy rõ ý định đó.
# - Từ "còn" không mặc định là tiếp tục cùng chủ đề. 
# VÍ DỤ

# 1. Thiếu chủ đề
# Câu trước: đăng ký khai sinh
# Câu hiện tại: nộp online được không
# Kết quả: đăng ký khai sinh nộp online được không

# Câu trước: đăng ký lại khai sinh
# Câu hiện tại: cần giấy tờ gì
# Kết quả: đăng ký lại khai sinh cần giấy tờ gì

# 2. Đổi đối tượng nhưng giữ mẫu hỏi
# Câu trước: đăng ký kết hôn làm sao
# Câu hiện tại: còn mất cccd
# Kết quả: còn mất cccd làm sao

# Câu trước: ai là trưởng khu phố 1 của xã
# Câu hiện tại: còn trưởng kp 2
# Kết quả: ai là trưởng khu phố 2 của xã

# 3. Chỉ còn trường thông tin cần hỏi
# Câu trước: địa chỉ ubnd xã ở đâu
# Câu hiện tại: số điện thoại
# Kết quả: số điện thoại của ubnd xã là gì

# Câu trước: đăng ký khai sinh có yếu tố nước ngoài
# Câu hiện tại: lệ phí bao nhiêu
# Kết quả: đăng ký khai sinh có yếu tố nước ngoài lệ phí là bao nhiêu

# 4. Đại từ hồi chỉ
# Câu trước: phó chủ tịch phụ trách văn hóa là ai
# Câu hiện tại: số của người đó
# Kết quả: số điện thoại của phó chủ tịch phụ trách văn hóa là gì

# 5. Chuyển chủ đề
# Câu trước: xã hiện tại có những đặc điểm gì
# Câu hiện tại: cần giấy tờ gì
# Kết quả: cần giấy tờ gì

# Câu trước: chủ tịch xã là ai
# Câu hiện tại: thủ tục khai sinh cần gì
# Kết quả: thủ tục khai sinh cần gì

# 6. Xã giao / cảm thán / quá mơ hồ
# Câu trước: đăng ký khai sinh cần gì
# Câu hiện tại: xin chào
# Kết quả: xin chào

# Câu trước: chủ tịch xã là ai
# Câu hiện tại: ok vậy thôi
# Kết quả: ok vậy thôi
# """
#     prompt = _render_prompt_template(
#         prompt_template,
#         default_prompt,
#         query=query,
#     )
#     try:
#         response = llm_rewrite.invoke(prompt)
#         return response.content.strip()
#     except:
#         return query

def rewrite_query(query: str, last_question, prompt_template: str = None) -> str:
    default_prompt = f"""Bạn là hệ thống viết lại câu hỏi theo ngữ cảnh cho chatbot hành chính cấp xã.

NHIỆM VỤ
Viết lại câu hỏi hiện tại thành đúng 1 câu hỏi độc lập, ngắn gọn, tự nhiên, giữ nguyên ý nghĩa.

ĐẦU VÀO
- Câu trước đã được viết lại đầy đủ: {last_question}
- Câu hỏi hiện tại: {query}

QUY TẮC
1. Nếu câu hiện tại là lời chào, cảm ơn, tạm biệt, xác nhận ngắn, cảm thán, phản hồi xã giao, hoặc không phải câu hỏi thật (ví dụ: xin chào, chào, hi, hello, cảm ơn, ok, oke, ok vậy, dạ, vâng, ừ, thôi, đúng rồi) thì giữ nguyên câu hiện tại sau khi làm sạch, không được nối với câu trước.
2. Trước hết, làm sạch câu hiện tại:
- Bỏ từ đệm, từ rào trước không cần thiết như: "anh nhầm", "ý tôi là", "tôi cần biết", "cho tôi hỏi".
- Chuẩn hóa viết tắt quen thuộc nếu chắc chắn: "cccd" -> "căn cước công dân", "ubnd" -> "ủy ban nhân dân", "tp" -> "thành phố", "kp" -> "khu phố".
- Sửa lỗi lặp từ, lỗi chính tả rõ ràng nếu chắc chắn.

3. Sau khi làm sạch:
- Nếu câu hiện tại đã đủ ý, là câu độc lập -> giữ nguyên.
- Nếu câu hiện tại thiếu chủ đề nhưng rõ là hỏi tiếp câu trước -> bổ sung chủ đề từ câu trước.
- Nếu câu hiện tại nêu đối tượng mới rõ ràng nhưng giữ cách hỏi cũ -> giữ mẫu hỏi cũ và thay đối tượng mới.
- Nếu câu hiện tại chỉ còn ý hỏi như: số điện thoại, địa chỉ, hồ sơ, giấy tờ, lệ phí, bao lâu, ở đâu, online được không -> khôi phục đầy đủ từ câu trước nếu chắc chắn.
- Nếu không chắc chắn -> giữ nguyên câu hiện tại sau khi làm sạch.

RÀNG BUỘC
- Không bịa thêm thông tin.
- Không đổi câu hỏi nhân sự thành thủ tục hoặc ngược lại.
- Không đổi tên người, chức danh, địa danh, số hiệu khu phố, số hiệu ấp.
- Không làm mất các từ phân biệt thủ tục như: "lại", "cấp lại", "trích lục", "bản sao", "có yếu tố nước ngoài", "khu vực biên giới", "thường trú", "tạm trú".
- Chỉ trả về đúng 1 câu hỏi cuối cùng, không giải thích."""
    prompt = _render_prompt_template(
        prompt_template,
        default_prompt,
        query=query,
    )
    try:
        response = llm_rewrite.invoke(prompt)
        return response.content.strip()
    except:
        return query

# ============================================================================
# TEST CASES FOR REWRITE PROMPT ACCURACY
# ============================================================================

test_cases = [
    # Sửa sai / đính chính
    {
        "last_question": "bí thư phường là ai",
        "query": "anh nhầm, anh hỏi bí thư tp là ai",
    },
    {
        "last_question": "bí thư phường là ai",
        "query": "tôi cần biết chủ tịch tp là ai",
    },
    {
        "last_question": "phó chủ tịch xã là ai",
        "query": "không phải phó chủ tịch, tôi hỏi chủ tịch",
    },
    # Không được biến sang thủ tục
    {
        "last_question": "chủ tịch xã là ai",
        "query": "còn khai sinh",
    },
    {
        "last_question": "bí thư phường là ai",
        "query": "thủ tục kết hôn cần gì",
    },
    # Hỏi tiếp cùng chủ đề
    {
        "last_question": "địa chỉ ubnd xã ở đâu",
        "query": "số điện thoại",
    },
    {
        "last_question": "xã có bao nhiêu khu phố",
        "query": "tên các khu phố là gì",
    },
    {
        "last_question": "ubnd phường làm việc mấy giờ",
        "query": "thứ 7 có làm không",
    },
    {
        "last_question": "xã thuộc quận nào",
        "query": "còn tỉnh",
    },
    # Đổi đối tượng nhưng giữ mẫu hỏi
    {
        "last_question": "địa chỉ ubnd xã ở đâu",
        "query": "còn trạm y tế",
    },
    {
        "last_question": "số điện thoại ubnd xã là gì",
        "query": "còn công an xã",
    },
    {
        "last_question": "xã có bao nhiêu khu phố",
        "query": "còn tổ dân phố",
    },

    # Mơ hồ / xã giao
    {
        "last_question": "địa chỉ ubnd xã ở đâu",
        "query": "xin chào",
    },
    {
        "last_question": "xã có bao nhiêu khu phố",
        "query": "ok",
    },
    {
        "last_question": "số điện thoại ubnd xã là gì",
        "query": "cảm ơn",
    },
    # =========================
    # 4. CASE GIAO THOA / THỰC TẾ CHAT
    # =========================

    # Người dùng đổi từ thông tin phường sang thủ tục
    {
        "last_question": "địa chỉ ubnd xã ở đâu",
        "query": "làm khai sinh cần gì",
    },
    {
        "last_question": "xã có bao nhiêu khu phố",
        "query": "đăng ký tạm trú ở đâu",
    },
    # Người dùng đổi từ thủ tục sang lãnh đạo
    {
        "last_question": "đăng ký kết hôn cần gì",
        "query": "chủ tịch xã là ai",
    },
    {
        "last_question": "làm cccd ở đâu",
        "query": "số điện thoại công an xã là gì",
    },
    # Người dùng hỏi ngắn, cần khôi phục hợp lý
    {
        "last_question": "số điện thoại ủy ban nhân dân xã là gì",
        "query": "còn địa chỉ",
    },
    {
        "last_question": "trưởng khu phố 1 là ai",
        "query": "số điện thoại",
    },
    {
        "last_question": "đăng ký khai sinh cần gì",
        "query": "ở đâu",
    },
    # Câu có từ đệm / câu rào trước
    {
        "last_question": "bí thư phường là ai",
        "query": "tôi cần biết số điện thoại",
    },
    {
        "last_question": "địa chỉ ubnd xã ở đâu",
        "query": "ý tôi là số điện thoại",
    },
    # Lỗi lặp từ / gõ sai nhẹ
    {
        "last_question": "",
        "query": "chu tich chu tich xa la ai",
    },
    {
        "last_question": "",
        "query": "dia chi dia chi ubnd xa o dau",
    },
    {
        "last_question": "đăng ký khai sinh cần gì",
        "query": "giấy tờ giấy tờ gì",
    },
]
    
if __name__ == "__main__":
    
    for item in test_cases:
        last_question = item["last_question"]
        query = item["query"]

        rewritten = rewrite_query(query, last_question)
        print(f"Last question: {last_question}")
        print(f"Query: {query}")
        print(f"Rewritten: {rewritten}")


