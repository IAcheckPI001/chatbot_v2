
import re
import json
import time
from utils import normalize_text


## extract similarity procedure block

CORE_GROUPS = {
    "khai_sinh": ["khai sinh"],
    "khai_tu": ["khai tu"],
    "ket_hon": ["ket hon"],
    "ly_hon": ["ly hon"],
    "tam_tru": ["tam tru"],
    "tam_vang": ["tam vang"],
    "ho_khau": ["ho khau"],
    "cu_tru": ["cu tru"],
    "chung_thuc": ["chung thuc"],
    "thuong_tru": ["thuong tru", "dang ky thuong tru"]
}

MODIFIERS = {
    "dang_ky_lai": ["dang ky lai", "cap lai", "lam lai"],
    "yeu_to_nuoc_ngoai": ["co yeu to nuoc ngoai", "nuoc ngoai"],
    "da_co_ho_so": ["da co ho so", "da co giay to"],
}

OPPOSITE_PAIRS = [
    ("khai_sinh", "khai_tu"),
    ("tam_tru", "tam_vang"),
    ("ket_hon", "ly_hon")
]

def contains_phrase(text, phrase):
    return re.search(r"\b" + re.escape(phrase) + r"\b", text) is not None

# def extract_modifiers(q_norm):
#     matched = set()
#     for key, phrases in MODIFIERS.items():
#         for p in phrases:
#             if p in q_norm:
#                 matched.add(key)
#     return matched

def extract_modifiers(q_norm):
    matched = set()
    for key, phrases in MODIFIERS.items():
        for p in phrases:
            if contains_phrase(q_norm, p):
                matched.add(key)
                break
    return matched

# def extract_core_tokens(q_norm):
#     matched = set()
#     for key, phrases in CORE_GROUPS.items():
#         for p in phrases:
#             if p in q_norm:
#                 matched.add(key)
#     return matched
def extract_core_tokens(q_norm):
    matched = set()
    for key, phrases in CORE_GROUPS.items():
        for p in phrases:
            if contains_phrase(q_norm, p):
                matched.add(key)
                break
    return matched

def semantic_guard_adjust(query_cores, query_mods, doc_text_norm):
    adjust = 0

    # -----------------------------
    # 1️⃣ HARD CORE FILTER
    # -----------------------------
    # if query_cores:
    #     doc_has_core = False

    #     for core in query_cores:
    #         if any(p in doc_text_norm for p in CORE_GROUPS[core]):
    #             doc_has_core = True
    #             break

    #     # Nếu doc không chứa core phù hợp → loại mạnh
    #     if not doc_has_core:
    #         return -5.0

    if query_cores:
        doc_has_core = any(
            contains_phrase(doc_text_norm, phrase)
            for core in query_cores
            for phrase in CORE_GROUPS[core]
        )
        if not doc_has_core:
            return -1.5

    # -----------------------------
    # 2️⃣ CORE BOOST
    # -----------------------------
    for core in query_cores:
        for phrase in CORE_GROUPS[core]:
            if phrase in doc_text_norm:
                adjust += 0.4

    # -----------------------------
    # 3️⃣ OPPOSITE PENALTY
    # -----------------------------
    for a, b in OPPOSITE_PAIRS:
        if a in query_cores:
            if any(p in doc_text_norm for p in CORE_GROUPS[b]):
                adjust -= 0.6
        if b in query_cores:
            if any(p in doc_text_norm for p in CORE_GROUPS[a]):
                adjust -= 0.6

    # -----------------------------
    # 4️⃣ MODIFIER LOGIC
    # -----------------------------
    if query_mods:
        for mod in query_mods:
            if any(p in doc_text_norm for p in MODIFIERS[mod]):
                adjust += 0.6
            else:
                adjust -= 0.3
    else:
        # Nếu query không có modifier
        # penalize doc có modifier
        for mod, phrases in MODIFIERS.items():
            if any(p in doc_text_norm for p in phrases):
                adjust -= 0.5

    return adjust


# def apply_semantic_guard(q_norm, results):
#     query_cores = extract_core_tokens(q_norm)
#     query_mods = extract_modifiers(q_norm)

#     for r in results:
#         doc_norm = normalize_text(r["text_content"])
#         adjust = semantic_guard_adjust(query_cores, query_mods, doc_norm)
#         r["confidence_score"] += adjust

#     results.sort(key=lambda x: x["confidence_score"], reverse=True)
#     return results

def apply_semantic_guard(q_norm, results):
    query_cores = extract_core_tokens(q_norm)
    query_mods = extract_modifiers(q_norm)

    for r in results:
        doc_norm = normalize_text(r["text_content"])
        adjust = semantic_guard_adjust(query_cores, query_mods, doc_norm)
        r["semantic_adjust"] = adjust
        r["final_score"] = r["confidence_score"] + adjust

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results

# def chunk_text(text, max_len=50):
#     # Tách theo dấu câu trước
#     sentences = re.split(r'(?<=[.!?])\s+', text)

#     chunks = []
#     for sentence in sentences:
#         words = sentence.split()

#         current = ""
#         for word in words:
#             if len(current) + len(word) + 1 <= max_len:
#                 current += (" " if current else "") + word
#             else:
#                 chunks.append(current)
#                 current = word

#         if current:
#             chunks.append(current)

#     return chunks

def chunk_text(text, max_len=100):
    if not isinstance(text, str):
        text = str(text or "")

    tokens = re.findall(r'\S+\s*', text)

    if not tokens:
        return [text]

    chunks = []
    current = ""

    for token in tokens:
        # 🔥 handle token quá dài
        if len(token) > max_len:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(token), max_len):
                chunks.append(token[i:i+max_len])
            continue

        # nếu thêm token vượt max_len
        if len(current) + len(token) > max_len:
            # 🔥 check dấu câu (không dùng regex)
            if current and current.rstrip().endswith(('.', '!', '?')):
                chunks.append(current)
                current = token
                continue

            if current:
                chunks.append(current)
                current = token
            else:
                current = token
        else:
            current += token

    if current:
        chunks.append(current)

    return chunks

# if __name__ == "__main__":
#     help_content = "Kính chào anh/chị! Rất vui được hỗ trợ anh/chị. Anh/chị có thể hỏi về các thủ tục hành chính, thông tin chung, hoặc tổ chức bộ máy của phường. Anh/chị cần giúp đỡ về vấn đề gì ạ?"
#     out_of_score_content = "Nội dung anh/chị hỏi nằm ngoài phạm vi hỗ trợ của hệ thống.\nAnh/chị vui lòng liên hệ đơn vị phù hợp hoặc đặt câu hỏi liên quan đến thủ tục hành chính để được hỗ trợ."
#     thanks_content = "Dạ, cảm ơn anh/chị. Khi cần thêm thông tin, anh/chị cứ liên hệ lại."
#     phan_nan_content = "Tôi rất tiếc vì anh/chị chưa hài lòng. Anh/chị hãy nói rõ phần còn vướng, tôi sẽ hỗ trợ lại ngay."
#     xuc_pham_content = "Tôi vẫn sẵn sàng hỗ trợ anh/chị về nội dung hành chính. Anh/chị vui lòng sử dụng ngôn từ phù hợp để tôi có thể hỗ trợ tốt hơn."
#     banned_replies = "Dạ em chỉ hỗ trợ anh/chị về các thủ tục hành chính, thông tin chung, hoặc tổ chức bộ máy của phường thôi ạ. Anh/chị vui lòng đặt câu hỏi liên quan đến những chủ đề này để được hỗ trợ tốt nhất nhé."

#     help_content = chunk_text(out_of_score_content)
    
#     for token in stream_tokens(help_content):
#         print(token, end="")
