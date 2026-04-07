


import re
import unicodedata
from typing import List, Dict, Optional, Any


UNIT_TYPE_KEYWORDS = {
    "xa": [
        "xã", "xa"
    ],
    "phuong": [
        "phường", "phuong", "p"
    ],
    "tinh": [
        "tỉnh", "tinh"
    ],
    "thanh_pho": [
        "thành phố", "thanh pho", "tp", "tphcm", "tp hcm", "tp.hcm"
    ]
}

# Pattern explicit: có loại đơn vị + địa danh
EXPLICIT_PATTERNS = [
    ("xa", r"\b(xã|xa)\s+([A-ZÀ-Ỵa-zà-ỵ0-9\s\-]+?)(?=[,?.!;]|$)"),
    ("phuong", r"\b(phường|phuong|p\.?)\s+([A-ZÀ-Ỵa-zà-ỵ0-9\s\-]+?)(?=[,?.!;]|$)"),
    ("tinh", r"\b(tỉnh|tinh)\s+([A-ZÀ-Ỵa-zà-ỵ0-9\s\-]+?)(?=[,?.!;]|$)"),
    ("thanh_pho", r"\b(thành phố|thanh pho|tp\.?|tphcm)\s+([A-ZÀ-Ỵa-zà-ỵ0-9\s\-]+?)(?=[,?.!;]|$)")
]

UNIT_SCOPE_MAP = {
    "xa": "xa_phuong",
    "phuong": "xa_phuong",
    "tinh": "tinh_thanh",
    "thanh_pho": "tinh_thanh"
}


def remove_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", text)


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("tp.", "tp ")
    text = text.replace("p.", "p ")
    text = re.sub(r"\s+", " ", text)
    return text


def canonicalize_text(text: str) -> str:
    text = normalize_text(text)
    text = remove_accents(text)
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_scope_from_unit_type(unit_type: str) -> Optional[str]:
    return UNIT_SCOPE_MAP.get(unit_type)


def replace_span(text: str, start: int, end: int, replacement: str) -> str:
    return text[:start] + replacement + text[end:]


class LocationIndex:
    """
    Mock index để demo.
    Thực tế anh/chị nên load từ DB tenant / bảng địa danh / alias.
    """
    def __init__(self, items: List[Dict[str, Any]]):
        self.items = items

    def find(self, location_text: str, scope_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        key = canonicalize_text(location_text)

        if not key:
            return None

        # 1) exact alias/name
        for item in self.items:
            if scope_type is not None and item.get("scope_type") != scope_type:
                continue

            candidates = [item.get("name", "")] + item.get("aliases", [])
            for c in candidates:
                c_key = canonicalize_text(c)
                if c_key == key:
                    return item

        # 2) prefix match an toàn hơn contains hai chiều
        # ví dụ: "thoi an" khớp "thoi an", nhưng tránh match quá bừa
        for item in self.items:
            if scope_type is not None and item.get("scope_type") != scope_type:
                continue

            candidates = [item.get("name", "")] + item.get("aliases", [])
            for c in candidates:
                c_key = canonicalize_text(c)
                if c_key.startswith(key + " ") or key.startswith(c_key + " "):
                    return item

        return None

INVALID_LOCATION_EXACT = {
    "minh", "mình",
    "dia phuong", "địa phương",
    "cho minh", "chỗ mình",
    "noi nay", "nơi này",
    "o dau", "ở đâu",
    "la ai", "là ai",
    "la gi", "là gì",
}

INVALID_LOCATION_CONTAINS = [
    " la ai",
    " o dau",
    " la gi",
    " bao nhieu",
    " khi nao",
    " lam giay",
    " chung thuc",
    " lam viec may gio",
    " ten gi",
    " co lam",
    " xac nhan",
    " ket hon",
    " khai sinh",
    " khai tu",
]

def is_valid_location_text(text: str) -> bool:
    if not text:
        return False

    raw = text.strip()
    norm = canonicalize_text(raw)

    if not norm:
        return False

    if norm in INVALID_LOCATION_EXACT:
        return False

    if any(invalid in norm for invalid in INVALID_LOCATION_CONTAINS):
        return False

    # tránh các cụm mở đầu không phải địa danh
    invalid_prefixes = [
        "la ",
        "o ",
        "bao ",
        "khi ",
        "ten ",
        "co ",
        "lam ",
        "xac ",
    ]
    if any(norm.startswith(p) for p in invalid_prefixes):
        return False

    # địa danh quá ngắn thường là nhiễu
    if len(norm) < 2:
        return False

    return True

def extract_admin_mentions(query: str) -> List[Dict[str, Any]]:
    mentions = []
    seen_spans = []

    # 1) Explicit patterns: "phường Thới An", "tỉnh Long An", ...
    for unit_type, pattern in EXPLICIT_PATTERNS:
        for m in re.finditer(pattern, query, flags=re.IGNORECASE):
            raw = m.group(0).strip()
            raw_location_text = m.group(2).strip()
            location_text = clean_location_text(raw_location_text)

            print(f"DEBUG: Found explicit pattern match: raw='{raw}', location_text='{location_text}'")

            # chỉ giữ explicit nếu location thực sự hợp lệ
            if not is_valid_location_text(location_text):
                continue

            mention = {
                "raw": raw,
                "matched_keyword": m.group(1),
                "unit_type": unit_type,
                "scope_type": build_scope_from_unit_type(unit_type),
                "location_text": location_text,
                "raw_location_text": raw_location_text,
                "start": m.start(),
                "end": m.end(),
                "confidence": 0.98
            }
            mentions.append(mention)
            seen_spans.append((m.start(), m.end()))

    # 2) Unit type only
    normalized = normalize_text(query)

    unit_only_patterns = [
        ("xa", r"\b(xã|xa)\b"),
        ("phuong", r"\b(phường|phuong|p)\b"),
        ("tinh", r"\b(tỉnh|tinh)\b"),
        ("thanh_pho", r"\b(thành phố|thanh pho|tp|tphcm|tp hcm)\b"),
    ]

    for unit_type, pattern in unit_only_patterns:
        for m in re.finditer(pattern, normalized, flags=re.IGNORECASE):
            overlapped = False
            for s, e in seen_spans:
                if m.start() >= s and m.end() <= e:
                    overlapped = True
                    break
            if overlapped:
                continue

            mentions.append({
                "raw": m.group(0).strip(),
                "matched_keyword": m.group(1),
                "unit_type": unit_type,
                "scope_type": build_scope_from_unit_type(unit_type),
                "location_text": None,
                "start": m.start(),
                "end": m.end(),
                "confidence": 0.85
            })

    mentions.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
    return mentions


def has_explicit_location(mentions: List[Dict[str, Any]]) -> bool:
    return any(m.get("location_text") for m in mentions)


def has_unit_type_only(mentions: List[Dict[str, Any]]) -> bool:
    if not mentions:
        return False
    return any(m.get("unit_type") and not m.get("location_text") for m in mentions)


def pick_best_explicit_mention(mentions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    explicit_mentions = [m for m in mentions if m.get("location_text")]
    if not explicit_mentions:
        return None

    # ưu tiên confidence cao hơn, raw dài hơn
    explicit_mentions.sort(key=lambda x: (x.get("confidence", 0), len(x.get("raw", ""))), reverse=True)
    return explicit_mentions[0]


def pick_best_unit_type_mention(mentions: List[Dict[str, Any]], scope: Optional[str] = None) -> Optional[Dict[str, Any]]:
    candidates = [m for m in mentions if m.get("unit_type") and not m.get("location_text")]
    if scope:
        scoped = [m for m in candidates if m.get("scope_type") == scope]
        if scoped:
            candidates = scoped

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x.get("confidence", 0), len(x.get("raw", ""))), reverse=True)
    return candidates[0]


def keep_original_or_normalize_alias(query: str) -> str:
    """
    Chỉ normalize nhẹ alias, không đổi target.
    """
    q = query
    q = re.sub(r"\bTP\.\s*HCM\b", "thành phố Hồ Chí Minh", q, flags=re.IGNORECASE)
    q = re.sub(r"\bTP\.\b", "thành phố", q, flags=re.IGNORECASE)
    q = re.sub(r"\bP\.\b", "phường", q, flags=re.IGNORECASE)
    return q


def rewrite_unit_type(query: str, from_unit_type: str, to_unit_type: str) -> str:
    """
    Đổi unit_type trong câu hỏi.
    Chỉ dùng cho case không có địa danh explicit.
    """
    if from_unit_type == to_unit_type:
        return keep_original_or_normalize_alias(query)

    replace_patterns = {
        "xa": r"\b(xã|xa)\b",
        "phuong": r"\b(phường|phuong|p)\b",
        "tinh": r"\b(tỉnh|tinh)\b",
        "thanh_pho": r"\b(thành phố|thanh pho|tp|tphcm|tp hcm)\b",
    }

    replace_values = {
        "xa": "xã",
        "phuong": "phường",
        "tinh": "tỉnh",
        "thanh_pho": "thành phố"
    }

    pattern = replace_patterns[from_unit_type]
    replacement = replace_values[to_unit_type]

    rewritten = re.sub(pattern, replacement, query, count=1, flags=re.IGNORECASE)
    return keep_original_or_normalize_alias(rewritten)

# def rewrite_unit_type(query: str, from_unit_type: str, to_unit_type: str) -> str:
#     if from_unit_type == to_unit_type:
#         return query

#     replace_map = {
#         "xa": "xã",
#         "phuong": "phường",
#         "tinh": "tỉnh",
#         "thanh_pho": "thành phố"
#     }

#     pattern_map = {
#         "xa": r"\b(xã|xa)\b",
#         "phuong": r"\b(phường|phuong|p)\b",
#         "tinh": r"\b(tỉnh|tinh)\b",
#         "thanh_pho": r"\b(thành phố|thanh pho|tp)\b",
#     }

#     pattern = pattern_map[from_unit_type]
#     replacement = replace_map[to_unit_type]

#     return re.sub(pattern, replacement, query, flags=re.IGNORECASE)


# def inject_default_unit_type_if_needed(query: str, actual_unit_type: str, scope: str) -> str:
#     """
#     Với câu không có unit_type rõ, có thể inject nhẹ nếu câu rất mơ hồ.
#     Ví dụ:
#     - 'bí thư là ai' -> 'bí thư xã là ai'
#     - 'chủ tịch là ai' -> 'chủ tịch thành phố là ai'
#     """
#     q = query.strip()
#     q_norm = normalize_text(q)

#     vague_titles = ["bí thư", "chủ tịch", "phó chủ tịch", "ubnd", "ủy ban nhân dân"]

#     if any(vt in q_norm for vt in vague_titles):
#         unit_label = {
#             "xa": "xã",
#             "phuong": "phường",
#             "tinh": "tỉnh",
#             "thanh_pho": "thành phố"
#         }[actual_unit_type]

#         # inject sau title đầu tiên nếu chưa có unit_type
#         if not re.search(r"\b(xã|xa|phường|phuong|tỉnh|tinh|thành phố|thanh pho|tp)\b", q_norm, flags=re.IGNORECASE):
#             if " là ai" in q_norm:
#                 idx = q_norm.find(" là ai")
#                 original_idx = len(q[:idx])
#                 return q[:original_idx] + f" {unit_label}" + q[original_idx:]
#             return f"{q} ({unit_label})"

#     return q

def inject_default_unit_type_if_needed(query: str, actual_unit_type: str, scope: str) -> str:
    """
    Chỉ inject unit_type cho các câu hỏi mơ hồ về chức danh/cơ quan địa phương.
    Không inject cho chức danh cấp trung ương/quốc gia như:
    - chủ tịch nước
    - chủ tịch quốc hội
    - thủ tướng
    - bộ trưởng
    - tổng bí thư
    """
    q = query.strip()
    q_norm = normalize_text(q)
    q_canon = canonicalize_text(q)

    unit_label = {
        "xa": "xã",
        "phuong": "phường",
        "tinh": "tỉnh",
        "thanh_pho": "thành phố"
    }[actual_unit_type]

    # 1) Nếu đã có unit_type rõ rồi thì không inject nữa
    if re.search(r"\b(xã|xa|phường|phuong|tỉnh|tinh|thành phố|thanh pho|tp|tphcm|tp hcm)\b", q_norm, flags=re.IGNORECASE):
        return q

    # 2) Chặn các chức danh/cơ quan cấp trung ương hoặc ngoài phạm vi địa phương
    NATIONAL_TITLE_PATTERNS = [
        r"\bch[uủ]\s*t[iị]ch\s*n[uướ]c\b",
        r"\bph[oó]\s*ch[uủ]\s*t[iị]ch\s*n[uướ]c\b",
        r"\bch[uủ]\s*t[iị]ch\s*qu[oố]c\s*h[oộ]i\b",
        r"\bph[oó]\s*ch[uủ]\s*t[iị]ch\s*qu[oố]c\s*h[oộ]i\b",
        r"\bth[uủ]\s*t[uướ]ng\b",
        r"\bph[oó]\s*th[uủ]\s*t[uướ]ng\b",
        r"\bb[oộ]\s*tr[uưở]ng\b",
        r"\bth[uứ]\s*tr[uưở]ng\b",
        r"\bt[oổ]ng\s*b[ií]\s*th[uư]\b",
        r"\bch[aá]nh\s*[aá]n\s*t[oò]a\s*[aá]n\b",
        r"\bvi[eệ]n\s*tr[uưở]ng\s*vi[eệ]n\s*ki[eể]m\s*s[aá]t\b",
        r"\bqu[oố]c\s*h[oộ]i\b",
        r"\bch[ií]nh\s*ph[uủ]\b",
        r"\bb[oộ]\s+[a-z0-9\s]+\b",
    ]

    for pat in NATIONAL_TITLE_PATTERNS:
        if re.search(pat, q_canon, flags=re.IGNORECASE):
            return q

    # 3) Chỉ inject cho các pattern mơ hồ nhưng có khả năng rất cao là hỏi cấp địa phương
    LOCAL_AMBIGUOUS_PATTERNS = [
        r"^\s*b[ií]\s*th[uư]\s+l[aà]\s*ai\s*\??\s*$",
        r"^\s*ph[oó]\s*b[ií]\s*th[uư]\s+l[aà]\s*ai\s*\??\s*$",
        r"^\s*ch[uủ]\s*t[iị]ch\s+l[aà]\s*ai\s*\??\s*$",
        r"^\s*ph[oó]\s*ch[uủ]\s*t[iị]ch\s+l[aà]\s*ai\s*\??\s*$",
        r"^\s*ch[uủ]\s*t[iị]ch\s*ubnd\s+l[aà]\s*ai\s*\??\s*$",
        r"^\s*ph[oó]\s*ch[uủ]\s*t[iị]ch\s*ubnd\s+l[aà]\s*ai\s*\??\s*$",
        r"^\s*[uủ]y\s*ban\s*nh[aâ]n\s*d[aâ]n\s+[oở]\s*[dđ][aâ]u\s*\??\s*$",
        r"^\s*ubnd\s+[oở]\s*[dđ][aâ]u\s*\??\s*$",
        r"^\s*[uủ]y\s*ban\s*nh[aâ]n\s*d[aâ]n\s*l[aà]\s*g[iì]\s*\??\s*$",
        r"^\s*ubnd\s*l[aà]\s*g[iì]\s*\??\s*$",
    ]

    matched_local_ambiguous = any(
        re.search(pat, q_canon, flags=re.IGNORECASE)
        for pat in LOCAL_AMBIGUOUS_PATTERNS
    )

    if not matched_local_ambiguous:
        return q

    # 4) Inject đúng vị trí, ưu tiên trước "là ai", "ở đâu", "là gì"
    tail_patterns = [
        r"\s+là ai\b",
        r"\s+ở đâu\b",
        r"\s+là gì\b",
    ]

    for tail_pat in tail_patterns:
        m = re.search(tail_pat, q, flags=re.IGNORECASE)
        if m:
            return q[:m.start()] + f" {unit_label}" + q[m.start():]

    return q


def rewrite_explicit_unit_type(query: str, mention: Dict[str, Any], actual_unit_type: str) -> str:
    if mention["unit_type"] == actual_unit_type:
        return keep_original_or_normalize_alias(query)

    replace_values = {
        "xa": "xã",
        "phuong": "phường",
        "tinh": "tỉnh",
        "thanh_pho": "thành phố",
    }

    replacement = replace_values[actual_unit_type]

    # chỉ thay đúng keyword đơn vị đã match, không đụng phần còn lại
    start = mention["start"]
    kw = mention["matched_keyword"]
    end = start + len(kw)

    rewritten = query[:start] + replacement + query[end:]
    return keep_original_or_normalize_alias(rewritten)

def resolve_by_location(
    query: str,
    mentions: List[Dict[str, Any]],
    tenant_ctx: Dict[str, Any],
    location_index: LocationIndex
) -> Dict[str, Any]:
    best = pick_best_explicit_mention(mentions)

    if not best:
        return {
            "original_query": query,
            "target_mode": "explicit_location_unresolved",
            "target_tenant_id": None,
            "target_tenant_name": None,
            "target_tenant_level": None,
            "target_unit_type": None,
            "target_scope": None,
            "normalized_query": query,
            "rewrite_needed": False,
            "confidence": 0.2,
            "mapping_reason": "no_explicit_mention"
        }

    matched_tenant = location_index.find(best["location_text"], best["scope_type"])

    if matched_tenant:
        normalized_query = rewrite_explicit_unit_type(
            query=query,
            mention=best,
            actual_unit_type=matched_tenant["unit_type"]
        )
        rewrite_needed = normalized_query != query

        mapping_reason = "resolved_by_explicit_location"
        if best["unit_type"] != matched_tenant["unit_type"]:
            mapping_reason = "resolved_by_explicit_location_equivalent_unit"

        return {
            "original_query": query,
            "target_mode": "explicit_location",
            "target_tenant_id": matched_tenant["id"],
            "target_tenant_name": matched_tenant["name"],
            "target_tenant_level": "explicit_location",
            "target_unit_type": matched_tenant["unit_type"],
            "target_scope": matched_tenant["scope_type"],
            "normalized_query": normalized_query,
            "rewrite_needed": rewrite_needed,
            "confidence": 0.98,
            "mapping_reason": mapping_reason,
            "matched_mention": best
        }

    return {
        "original_query": query,
        "target_mode": "explicit_location_unresolved",
        "target_tenant_id": None,
        "target_tenant_name": None,
        "target_tenant_level": None,
        "target_unit_type": best["unit_type"],
        "target_scope": best["scope_type"],
        "normalized_query": query,
        "rewrite_needed": False,
        "confidence": 0.4,
        "mapping_reason": "explicit_location_not_found",
        "matched_mention": best
    }


# def resolve_by_scope_and_tenant(
#     query: str,
#     scope: str,
#     mentions: List[Dict[str, Any]],
#     tenant_ctx: Dict[str, Any]
# ) -> Optional[Dict[str, Any]]:
#     mention = pick_best_unit_type_mention(mentions, scope=scope)
#     if not mention:
#         return None

#     if scope == "xa_phuong":
#         current = tenant_ctx.get("current")
#         if not current:
#             return None

#         actual = current["unit_type"]
#         normalized_query = rewrite_unit_type(query, mention["unit_type"], actual)

#         return {
#             "original_query": query,
#             "target_mode": "tenant_current",
#             "target_tenant_id": current.get("id"),
#             "target_tenant_name": current.get("name"),
#             "target_tenant_level": "current",
#             "target_unit_type": actual,
#             "target_scope": "xa_phuong",
#             "normalized_query": normalized_query,
#             "rewrite_needed": normalized_query != query,
#             "confidence": 0.95,
#             "mapping_reason": "same_scope_xa_phuong_map_to_current_tenant",
#             "matched_mention": mention
#         }

#     if scope == "tinh_thanh":
#         parent = tenant_ctx.get("parent")
#         if not parent:
#             return None

#         actual = parent["unit_type"]
#         normalized_query = rewrite_unit_type(query, mention["unit_type"], actual)

#         return {
#             "original_query": query,
#             "target_mode": "tenant_parent",
#             "target_tenant_id": parent.get("id"),
#             "target_tenant_name": parent.get("name"),
#             "target_tenant_level": "parent",
#             "target_unit_type": actual,
#             "target_scope": "tinh_thanh",
#             "normalized_query": normalized_query,
#             "rewrite_needed": normalized_query != query,
#             "confidence": 0.95,
#             "mapping_reason": "same_scope_tinh_thanh_map_to_parent_tenant",
#             "matched_mention": mention
#         }

#     return None


def map_scope_unit_type(scope: str, tenant_ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if scope == "xa_phuong":
        current = tenant_ctx.get("current")
        if not current:
            return None
        return {
            "target_tenant_id": current.get("id"),
            "target_tenant_name": current.get("name"),
            "target_tenant_level": "current",
            "target_unit_type": current.get("unit_type"),
            "target_scope": "xa_phuong",
        }

    if scope == "tinh_thanh":
        parent = tenant_ctx.get("parent")
        if not parent:
            return None
        return {
            "target_tenant_id": parent.get("id"),
            "target_tenant_name": parent.get("name"),
            "target_tenant_level": "parent",
            "target_unit_type": parent.get("unit_type"),
            "target_scope": "tinh_thanh",
        }

    return None

def resolve_by_scope_and_tenant(
    query: str,
    scope: str,
    mentions: List[Dict[str, Any]],
    tenant_ctx: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    mention = pick_best_unit_type_mention(mentions, scope=scope)
    if not mention:
        return None

    mapped = map_scope_unit_type(scope, tenant_ctx)
    if not mapped:
        return None

    actual_unit_type = mapped["target_unit_type"]
    normalized_query = rewrite_unit_type(query, mention["unit_type"], actual_unit_type)

    return {
        "original_query": query,
        # "target_mode": f"tenant_{mapped['target_tenant_level']}",
        # "target_tenant_id": mapped["target_tenant_id"],
        # "target_tenant_name": mapped["target_tenant_name"],
        # "target_tenant_level": mapped["target_tenant_level"],
        # "target_unit_type": actual_unit_type,
        # "target_scope": mapped["target_scope"],
        "normalized_query": normalized_query,
        # "rewrite_needed": normalized_query != query,
        # "confidence": 0.95,
        # "mapping_reason": f"same_scope_{mapped['target_scope']}_map_to_{mapped['target_tenant_level']}_tenant",
        # "matched_mention": mention,
    }

def fallback_to_tenant_scope(
    query: str,
    scope: str,
    tenant_ctx: Dict[str, Any]
) -> Dict[str, Any]:
    current = tenant_ctx.get("current")
    parent = tenant_ctx.get("parent")

    if scope == "xa_phuong" and current:
        normalized_query = inject_default_unit_type_if_needed(query, current["unit_type"], scope)
        return {
            "original_query": query,
            "target_mode": "fallback_scope",
            "target_tenant_id": current.get("id"),
            "target_tenant_name": current.get("name"),
            "target_tenant_level": "current",
            "target_unit_type": current["unit_type"],
            "target_scope": "xa_phuong",
            "normalized_query": normalized_query,
            "rewrite_needed": normalized_query != query,
            "confidence": 0.7,
            "mapping_reason": "fallback_to_current_scope"
        }

    if scope == "tinh_thanh" and parent:
        normalized_query = inject_default_unit_type_if_needed(query, parent["unit_type"], scope)
        return {
            "original_query": query,
            "target_mode": "fallback_scope",
            "target_tenant_id": parent.get("id"),
            "target_tenant_name": parent.get("name"),
            "target_tenant_level": "parent",
            "target_unit_type": parent["unit_type"],
            "target_scope": "tinh_thanh",
            "normalized_query": normalized_query,
            "rewrite_needed": normalized_query != query,
            "confidence": 0.7,
            "mapping_reason": "fallback_to_parent_scope"
        }

    if current:
        normalized_query = inject_default_unit_type_if_needed(query, current["unit_type"], current["scope_type"])
        return {
            "original_query": query,
            "target_mode": "fallback_scope",
            "target_tenant_id": current.get("id"),
            "target_tenant_name": current.get("name"),
            "target_tenant_level": "current",
            "target_unit_type": current["unit_type"],
            "target_scope": current["scope_type"],
            "normalized_query": normalized_query,
            "rewrite_needed": normalized_query != query,
            "confidence": 0.6,
            "mapping_reason": "fallback_to_current_default"
        }

    return {
        "original_query": query,
        "target_mode": "unresolved",
        "target_tenant_id": None,
        "target_tenant_name": None,
        "target_tenant_level": None,
        "target_unit_type": None,
        "target_scope": scope,
        "normalized_query": query,
        "rewrite_needed": False,
        "confidence": 0.2,
        "mapping_reason": "cannot_resolve"
    }


def resolve_unit_type(query, scope, tenant_ctx):
    mentions = extract_admin_mentions(query)

    # Có unit_type rõ -> map theo tenant hiện tại / tenant cha
    if has_unit_type_only(mentions):
        result = resolve_by_scope_and_tenant(query, scope, mentions, tenant_ctx)
        if result:
            result["mentions"] = mentions
            return result

    # Không có gì rõ -> fallback theo tenant
    result = fallback_to_tenant_scope(query, scope, tenant_ctx)
    result["mentions"] = mentions
    return result

QUESTION_TAIL_PATTERNS = [
    r"\s+là ai$",
    r"\s+ở đâu$",
    r"\s+là gì$",
    r"\s+bao nhiêu$",
    r"\s+khi nào$",
    r"\s+làm gì$",
    r"\s+làm giấy khai sinh ở đâu$",
    r"\s+chứng thực ở đâu$",
    r"\s+xác nhận cư trú ở đâu$",
    r"\s+làm kết hôn ở đâu$",
    r"\s+làm khai tử ở đâu$",
    r"\s+làm việc mấy giờ$",
    r"\s+có làm căn cước không$",
    r"\s+có làm sơ yếu lý lịch không$",
    r"\s+mình ở đâu$",
    r"\s+mình là gì$",
    r"\s+tên gì$",
]

def clean_location_text(text: str) -> str:
    s = text.strip()
    for pat in QUESTION_TAIL_PATTERNS:
        s = re.sub(pat, "", s, flags=re.IGNORECASE)
    return s.strip(" ,.-")


# from scope_detect import extract_scope

# if __name__ == "__main__":


    # tenant_ctx = {
    #     "current": {
    #         "id": "tenant_xa_badiem",
    #         "unit_type": "xa",
    #         "scope_type": "xa_phuong",
    #         "name": "Bà Điểm"
    #     },
    #     "parent": {
    #         "id": "tenant_hcm",
    #         "unit_type": "thanh_pho",
    #         "scope_type": "tinh_thanh",
    #         "name": "Hồ Chí Minh"
    #     }
    # }

#     query = input("Nhập câu hỏi: ")

#     scope = extract_scope(query)

#     result = resolve_unit_type(
#         query=query,
#         scope=scope,
#         tenant_ctx=tenant_ctx
#     )
#     print("=" * 100)
#     print("Câu hỏi trước:", query)
#     print("Câu hỏi sau khi xử lý:", result["normalized_query"])