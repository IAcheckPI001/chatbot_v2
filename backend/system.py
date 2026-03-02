

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



def extract_modifiers(q_norm):
    matched = set()
    for key, phrases in MODIFIERS.items():
        for p in phrases:
            if p in q_norm:
                matched.add(key)
    return matched

def extract_core_tokens(q_norm):
    matched = set()
    for key, phrases in CORE_GROUPS.items():
        for p in phrases:
            if p in q_norm:
                matched.add(key)
    return matched

def semantic_guard_adjust(query_cores, query_mods, doc_text_norm):
    adjust = 0

    # -----------------------------
    # 1️⃣ HARD CORE FILTER
    # -----------------------------
    if query_cores:
        doc_has_core = False

        for core in query_cores:
            if any(p in doc_text_norm for p in CORE_GROUPS[core]):
                doc_has_core = True
                break

        # Nếu doc không chứa core phù hợp → loại mạnh
        if not doc_has_core:
            return -5.0

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


def apply_semantic_guard(q_norm, results):
    query_cores = extract_core_tokens(q_norm)
    query_mods = extract_modifiers(q_norm)

    for r in results:
        doc_norm = normalize_text(r["text_content"])
        adjust = semantic_guard_adjust(query_cores, query_mods, doc_norm)
        r["score"] += adjust

    results.sort(key=lambda x: x["score"], reverse=True)
    return results